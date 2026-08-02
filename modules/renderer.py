"""
Renderiza clips con Remotion en el formato elegido por clip (9:16, 1:1, 16:9 o
split), sin subtítulos quemados. El encuadre (recorte al hablante / split) se
resuelve automáticamente con el detector de caras.
"""

import json
import math
import os
import platform
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import config
from modules.layout_detector import (
    detect_layout,
    detect_split,
    _face_x_to_object_position,
    _visible_frac,
)
from modules.media_server import MediaServer
from modules.segment_preview import analyze_clip_file, shot_segments

# En Windows, subprocess no puede ejecutar npx.ps1; usa npx.cmd
_NPX = "npx.cmd" if platform.system() == "Windows" else "npx"


def _log(msg: str) -> None:
    """print() a prueba de stdout no-UTF8 (Windows/charmap): nunca debe tumbar el render."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "ignore").decode())


# Valores de formato viejos que pudieron quedar en el estado persistido.
_LEGACY_FORMAT = {"9:16 vertical": "9:16", "Original 16:9": "16:9"}


def _format_key(val) -> str:
    """Normaliza el valor de 'formato' de un clip a una clave de FORMAT_PRESETS."""
    if not val:
        return config.DEFAULT_FORMAT
    if val in config.FORMAT_PRESETS:
        return val
    if val in _LEGACY_FORMAT:
        return _LEGACY_FORMAT[val]
    for k, p in config.FORMAT_PRESETS.items():
        if p.get("label") == val:
            return k
    return config.DEFAULT_FORMAT


def _resolve_encuadre(clip_path: Path, clip_duration: float, fmt_key: str,
                      preset: dict, clip: dict | None = None) -> dict:
    """
    Decide layout y foco para un clip según su formato:
      - manual      → usa el foco fijado a mano en la UI (clip["crop_manual"])
      - auto_layout → detect_layout (fill/fit + seguimiento del hablante)
      - split       → detect_split (foco de cada mitad)
      - fijo        → fill centrado (la fuente ya tiene el aspecto de salida, p. ej. 16:9)
    Devuelve layout, focus_x, focus_keyframes, focus_top, focus_bottom, cover_time y badge.
    """
    width, height = preset["width"], preset["height"]
    clip = clip or {}
    base = {
        "layout": "fill", "focus_x": 0.5, "focus_keyframes": [],
        "focus_top": 0.5, "focus_bottom": 0.5, "manual_crops": None,
        "cover_time": (clip_duration / 2) if clip_duration else 1.0,
        "badge": "📐 recorte centrado",
    }

    # ── Override manual (elegido en la UI) ────────────────────────────────────
    # Recorte por rectángulo explícito (permite zoom). Tiene prioridad sobre la
    # autodetección. En 9:16/1:1 recorta a UNA persona aunque haya dos.
    #
    # El rectángulo se calculó PARA UN FORMATO (su aspecto está metido en el
    # ancho/alto guardados): si después se cambió el formato, reusarlo estiraría
    # la imagen. En ese caso se ignora y decide la autodetección. Los clips
    # viejos no guardan `crop_fmt`; a esos se les cree (eran del formato actual).
    _crop_fmt = clip.get("crop_fmt")
    if _crop_fmt and _crop_fmt != fmt_key:
        clip = {k: v for k, v in clip.items() if k != "crop_manual"}

    if clip.get("crop_manual"):
        if preset.get("base") == "split":
            rt, rb = clip.get("crop_rect_top"), clip.get("crop_rect_bottom")
            if rt and rb:
                base.update(layout="split", manual_crops=[rt, rb], badge="⧉ split manual")
                return base
        elif preset.get("auto_layout"):
            rect = clip.get("crop_rect")
            if rect:
                base.update(layout="fill", manual_crops=[rect], badge="🎯 encuadre manual")
                return base
        # 16:9 fijo (o faltan rects): cae a la autodetección de abajo.

    if preset.get("base") == "letterbox":
        # Plano completo sobre negro: no hay recorte, así que tampoco hace falta
        # buscar caras (nos ahorramos la detección entera).
        base.update(layout="letterbox", badge="⬛ plano completo sobre negro")
        return base

    if preset.get("auto_layout"):
        det = detect_layout(clip_path, clip_duration, target_aspect=width / height)
        kf  = det.get("focus_keyframes", [])
        layout = det["layout"]
        # `allow_fit: False` → el recorte llena la pantalla sí o sí. La caída a
        # "fit" (fondo borroso) existía para no recortar mal cuando no hay una
        # cara grande; ahora eso se elige a mano con el formato "9:16 completo".
        if layout == "fit" and preset.get("allow_fit") is False:
            layout = "fill"
        if layout == "fill" and len(kf) > 1:
            badge = f"🎯 sigue al hablante ({len(kf)} kf)"
        elif layout == "fill":
            badge = "📐 recorte al hablante"
        else:
            badge = "🖥 plano completo (fondo borroso)"
        base.update(
            layout=layout, focus_x=det["focus_x"],
            focus_keyframes=kf, cover_time=det.get("cover_time", base["cover_time"]),
            badge=badge,
        )
        return base

    if preset.get("base") == "split":
        half_aspect = width / (height / 2)
        det = detect_split(clip_path, clip_duration, target_aspect=half_aspect)
        base.update(
            layout="split",
            focus_top=det["focus_top"], focus_bottom=det["focus_bottom"],
            cover_time=det.get("cover_time", base["cover_time"]),
            badge="⧉ dos recortes apilados",
        )
        return base

    # Formato fijo (16:9): la fuente ya es 16:9 → fill centrado (cover ≈ identidad).
    base["badge"] = "🖥 plano completo"
    return base


def _source_aspect(frame_path) -> float:
    """Aspecto (ancho/alto) de la fuente, leído de una muestra del análisis."""
    try:
        import cv2
        img = cv2.imread(str(frame_path))
        if img is not None:
            h, w = img.shape[:2]
            if h:
                return w / h
    except Exception:
        pass
    return 16.0 / 9.0


def follow_shot_segments(clip_path, clip_duration: float, width: int, height: int,
                         fps: int) -> list | None:
    """
    Tramos de layout para "seguir la toma": split mientras están los dos,
    recorte cerrado cuando la cámara va a uno solo.

    Se analiza el ARCHIVO DE CLIP (no el tramo del original) porque después del
    ajuste de bordes y de los jump cuts los tiempos ya no coinciden.

    Devuelve None si el clip no cambia de plano: ahí un layout fijo es mejor
    (menos trabajo y sin riesgo de parpadeo).
    """
    analysis = analyze_clip_file(clip_path, clip_duration)
    segs = shot_segments(analysis.get("timeline") or [], clip_duration)
    if len(segs) < 2:
        return None

    frames = analysis.get("frames") or []
    src_aspect = _source_aspect(frames[0]) if frames else 16.0 / 9.0
    full_r = _visible_frac(width / height, src_aspect)
    half_r = _visible_frac(width / (height / 2), src_aspect)

    out = []
    for s in segs:
        item = {"fromFrame": max(0, int(round(s["start"] * fps)))}
        if s["kind"] == "two":
            xs = s["xs"]
            item["layout"] = "split"
            item["focusTop"]    = round(_face_x_to_object_position(xs[0], half_r), 3)
            item["focusBottom"] = round(_face_x_to_object_position(xs[-1], half_r), 3)
        else:
            item["layout"] = "fill"
            item["focusX"] = round(_face_x_to_object_position(s["xs"][0], full_r), 3)
        out.append(item)

    # El primero tiene que arrancar en 0 sí o sí (el componente busca hacia atrás).
    out[0]["fromFrame"] = 0
    return out


def render_clip(
    clip_path: Path,
    output_path: Path,
    width: int,
    height: int,
    clip_title: str = "",
    clip_url: str | None = None,
    duration_frames: int | None = None,
    layout: str = "fit",
    focus_x: float = 0.5,
    focus_keyframes: list | None = None,
    focus_top: float = 0.5,
    focus_bottom: float = 0.5,
    manual_crops: list | None = None,
    layout_segments: list | None = None,
    concurrency: int | None = None,
) -> Path:
    """
    Llama a Remotion para renderizar el clip en las dimensiones dadas.

    concurrency: hilos que usa ESTE render. Cuando corren varios renders en
                 paralelo hay que repartir los núcleos, si no cada uno cree que
                 tiene la máquina entera y se pelean.
    width/height: dimensiones de salida del formato elegido.
    clip_url: URL HTTP del clip (si se sirve via _ClipServer).
              Si None, usa clip_path como string (puede fallar en Chromium).
    duration_frames: frames totales del clip; si se pasa, evita que calculateMetadata
                     intente cargar el video antes de renderizar.
    layout:   "fill" (recorte a pantalla completa), "fit" (plano completo 16:9 sobre
              fondo borroso) o "split" (dos recortes apilados).
    focus_x:  objectPosition X fijo en modo "fill" (0–1); fallback si no hay keyframes.
    focus_keyframes: [{"t": seg, "x": 0–1}, ...] cámara dinámica que sigue al hablante.
    focus_top/focus_bottom: objectPosition X de cada mitad en modo "split".
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    props = {
        "clipPath":  clip_url or str(clip_path).replace("\\", "/"),
        "title":     clip_title,
        "width":     width,
        "height":    height,
        "fps":       config.OUTPUT_FPS,
        "layout":    layout,
        "focusX":    focus_x,
        "focusKeyframes": focus_keyframes or [],
        "focusTop":    focus_top,
        "focusBottom": focus_bottom,
    }
    if manual_crops:
        props["manualCrops"] = manual_crops
    if layout_segments:
        props["layoutSegments"] = layout_segments
    if duration_frames is not None:
        props["durationInFrames"] = duration_frames

    # Escribir props en archivo JSON sin BOM (Remotion en Windows lo requiere)
    props_file = Path(tempfile.mktemp(suffix=".json"))
    props_file.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")

    try:
        cmd = [
            _NPX, "remotion", "render",
            "src/index.ts",
            "ClipComposition",
            str(output_path).replace("\\", "/"),
            f"--props={props_file}",
            "--width",  str(width),
            "--height", str(height),
            "--fps",    str(config.OUTPUT_FPS),
            "--crf",    str(config.OUTPUT_CRF),
        ]
        if concurrency:
            cmd.append(f"--concurrency={concurrency}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(config.REMOTION_DIR),
        )
    finally:
        props_file.unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(f"Remotion falló:\n{result.stderr[-2000:]}")

    return output_path


def render_cover(
    clip_path: Path,
    output_path: Path,
    width: int,
    height: int,
    clip_url: str | None = None,
    cover_frame: int = 0,
    layout: str = "fit",
    focus_x: float = 0.5,
    focus_keyframes: list | None = None,
    focus_top: float = 0.5,
    focus_bottom: float = 0.5,
    manual_crops: list | None = None,
    layout_segments: list | None = None,
) -> Path:
    """
    Genera la portada (JPG) renderizando UN frame del clip con la misma composición
    Remotion (mismo recorte fill/fit/split/manual), en las dimensiones del formato.

    cover_frame: número de frame del archivo de clip a usar como portada.
                 El foco dinámico se evalúa en ese frame, así la portada queda
                 centrada en quien hablaba en ese momento.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    props = {
        "clipPath":  clip_url or str(clip_path).replace("\\", "/"),
        "title":     "",
        "width":     width,
        "height":    height,
        "fps":       config.OUTPUT_FPS,
        "layout":    layout,
        "focusX":    focus_x,
        "focusKeyframes": focus_keyframes or [],
        "focusTop":    focus_top,
        "focusBottom": focus_bottom,
    }
    if manual_crops:
        props["manualCrops"] = manual_crops
    if layout_segments:
        props["layoutSegments"] = layout_segments

    props_file = Path(tempfile.mktemp(suffix=".json"))
    props_file.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")

    try:
        cmd = [
            _NPX, "remotion", "still",
            "src/index.ts",
            "ClipComposition",
            str(output_path).replace("\\", "/"),
            f"--props={props_file}",
            "--frame", str(max(0, cover_frame)),
            "--width",  str(width),
            "--height", str(height),
            "--image-format", "jpeg",
            "--jpeg-quality", "90",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(config.REMOTION_DIR),
        )
    finally:
        props_file.unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(f"Remotion still (portada) falló:\n{result.stderr[-2000:]}")

    return output_path


def _render_one(clip: dict, output_dir: Path, clip_url: str,
                concurrency: int | None) -> dict:
    """Renderiza un clip + su portada. Pensado para correr en un worker del pool."""
    idx   = clip["index"]
    title = clip.get("title", f"Clip {idx}")
    name  = _clip_filename(title, idx)
    output_path = output_dir / f"{name} - vertical.mp4"

    # Duración real del archivo de clip (incluye los pads de corte y, si hubo
    # jump cuts, ya viene medida del archivo). Fallback para clips viejos.
    clip_duration = clip.get("clip_duration")
    if not clip_duration:
        clip_duration = clip["end"] - clip["start"]
    duration_frames = math.ceil(clip_duration * config.OUTPUT_FPS)

    # Formato elegido por clip → dimensiones + cómo encuadrar.
    fmt_key = _format_key(clip.get("formato"))
    preset  = config.FORMAT_PRESETS[fmt_key]
    width, height = preset["width"], preset["height"]

    enc = _resolve_encuadre(clip["clip_path"], clip_duration, fmt_key, preset, clip)
    layout       = enc["layout"]
    focus        = enc["focus_x"]
    keyframes    = enc["focus_keyframes"]
    focus_top    = enc["focus_top"]
    focus_bottom = enc["focus_bottom"]
    manual_crops = enc["manual_crops"]
    cover_time   = enc["cover_time"]

    # ── Seguir la toma: layout que cambia dentro del clip ──────────────────────
    # El encuadre manual es una decisión explícita del usuario: si lo puso, manda.
    layout_segments = None
    # Solo tiene sentido en formatos que recortan: 16:9 y "9:16 completo"
    # muestran el plano entero, no hay toma que seguir.
    if clip.get("follow_shot") and not manual_crops and config.crops(fmt_key):
        try:
            layout_segments = follow_shot_segments(
                clip["clip_path"], clip_duration, width, height, config.OUTPUT_FPS
            )
        except Exception as e:
            _log(f"     ⚠️  No se pudo seguir la toma ({e}); layout fijo.")
        if layout_segments:
            kinds = "→".join(
                "⧉" if s["layout"] == "split" else "📱" for s in layout_segments
            )
            enc["badge"] = f"🔀 sigue la toma ({len(layout_segments)} tramos: {kinds})"

    _log(f"  🎬 {title} — {preset['label']} · {enc['badge']}")

    render_clip(
        clip_path=clip["clip_path"],
        output_path=output_path,
        width=width,
        height=height,
        clip_title=title,
        clip_url=clip_url,
        duration_frames=duration_frames,
        layout=layout,
        focus_x=focus,
        focus_keyframes=keyframes,
        focus_top=focus_top,
        focus_bottom=focus_bottom,
        manual_crops=manual_crops,
        layout_segments=layout_segments,
        concurrency=concurrency,
    )

    # Portada: mejor frame con cara (o punto medio), mismo recorte, sin texto.
    cover_path  = output_dir / f"{name} - portada.jpg"
    cover_frame = int(round(cover_time * config.OUTPUT_FPS))
    cover_frame = max(0, min(cover_frame, max(0, duration_frames - 1)))
    try:
        render_cover(
            clip_path=clip["clip_path"],
            output_path=cover_path,
            width=width,
            height=height,
            clip_url=clip_url,
            cover_frame=cover_frame,
            layout=layout,
            focus_x=focus,
            focus_keyframes=keyframes,
            focus_top=focus_top,
            focus_bottom=focus_bottom,
            manual_crops=manual_crops,
            layout_segments=layout_segments,
        )
    except Exception as e:
        _log(f"     ⚠️  No se pudo generar la portada: {e}")
        cover_path = None

    return {
        **clip,
        "output_path": output_path,
        "formato":     fmt_key,
        "layout":      layout,
        "cover_path":  cover_path,
    }


def render_clips(
    clips_with_subs: list[dict],
    output_dir: Path,
    video_id: str,
    progress_fn: "Callable[[int, int, str], None] | None" = None,
    workers: int | None = None,
) -> list[dict]:
    """
    Renderiza todos los clips y retorna la lista con output_path añadido.

    Corre `workers` renders en paralelo (default `config.RENDER_CONCURRENCY`).
    progress_fn(done, total, titulo) se llama SIEMPRE desde este hilo — no desde
    los workers — porque quien lo pasa suele estar pintando en Streamlit.
    """
    server = MediaServer(config.CLIPS_DIR)  # puerto efímero + Range
    server.start()

    total   = len(clips_with_subs)
    workers = max(1, min(workers or config.RENDER_CONCURRENCY, total or 1))
    # Repartir los núcleos entre los renders simultáneos: si cada uno usa la
    # máquina entera se pelean y no se gana nada.
    per_render = max(1, (os.cpu_count() or 2) // (2 * workers)) if workers > 1 else None

    results = []
    try:
        if workers == 1:
            for done, clip in enumerate(clips_with_subs):
                if progress_fn:
                    progress_fn(done, total, clip.get("title", ""))
                results.append(_render_one(clip, output_dir, server.url_for(clip["clip_path"]), None))
        else:
            _log(f"  ⚡ Renderizando {total} clips de a {workers} en paralelo "
                 f"({per_render} hilos cada uno)")
            if progress_fn:
                progress_fn(0, total, clips_with_subs[0].get("title", ""))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(
                        _render_one, clip, output_dir,
                        server.url_for(clip["clip_path"]), per_render,
                    ): clip
                    for clip in clips_with_subs
                }
                for done, future in enumerate(as_completed(futures)):
                    # Un fallo se propaga acá (el `with` espera a los que ya arrancaron).
                    results.append(future.result())
                    if progress_fn:
                        progress_fn(done + 1, total, futures[future].get("title", ""))
            # Los renders terminan en cualquier orden; el usuario espera el suyo.
            results.sort(key=lambda c: c.get("index", 0))

        if progress_fn:
            progress_fn(total, total, "")
    finally:
        server.stop()

    return results


def _clip_filename(title: str, index: int, max_len: int = 80) -> str:
    import re
    clean = re.sub(r'[\\/:*?"<>|]', "", title)
    clean = re.sub(r"\s+", " ", clean).strip()
    if len(clean) > max_len:
        clean = clean[:max_len].rsplit(" ", 1)[0]
    return f"{index:02d} - {clean}"
