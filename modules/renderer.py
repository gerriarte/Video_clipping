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
from modules.imaging import imread
from modules.overlays import for_render as overlays_for_render

import config
from modules.finish import finish
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


def speaker_follow(clip: dict | None) -> bool:
    """
    Si el recorte de ESTE clip sigue al hablante (la "cámara" que se desplaza
    dentro del clip). Los clips guardados antes de que existiera el control no
    tienen la clave: para ellos vale el default del proyecto.
    """
    val = (clip or {}).get("speaker_follow")
    return config.SPEAKER_FOLLOW_DEFAULT if val is None else bool(val)


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
        # Seguir al hablante es OPCIONAL y se elige por clip. Apagado, el recorte
        # queda clavado en focus_x (la posición mediana de la cara a lo largo del
        # clip): un plano fijo bien encuadrado en vez de uno que se mueve solo.
        follow = speaker_follow(clip)
        if not follow:
            kf = []
        if layout != "fill":
            badge = "🖥 plano completo (fondo borroso)"
        elif len(kf) > 1:
            badge = f"🎯 sigue al hablante ({len(kf)} kf)"
        elif follow:
            badge = "📐 recorte al hablante"
        else:
            badge = "📌 recorte fijo al hablante (sin seguimiento)"
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


def clip_aspect(clip_path) -> float:
    """
    Aspecto (ancho/alto) del archivo de clip, leído con ffprobe.

    La composición lo necesita para calcular el recorte horizontal: el <Video>
    de @remotion/media dibuja en canvas y no tiene `object-position`, así que ya
    no lo resuelve el CSS. Si no se puede leer, 16:9 (todo el material del canal
    lo es) — mejor un encuadre razonable que reventar el render.
    """
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "json", str(clip_path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        s = json.loads(r.stdout)["streams"][0]
        w, h = float(s["width"]), float(s["height"])
        if w > 0 and h > 0:
            return w / h
    except Exception:
        pass
    return 16.0 / 9.0


def clip_fps(clip_path) -> float | None:
    """
    Fotogramas por segundo reales del clip (None si no se pueden leer).

    Se prefiere `avg_frame_rate` sobre `r_frame_rate`: en archivos de frame rate
    variable el segundo devuelve la base de tiempo (a veces 1000) y no el ritmo
    real. Ambos vienen como fracción ("60/1", "30000/1001").
    """
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=avg_frame_rate,r_frame_rate",
             "-of", "json", str(clip_path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        s = json.loads(r.stdout)["streams"][0]
    except Exception:
        return None

    for clave in ("avg_frame_rate", "r_frame_rate"):
        valor = s.get(clave) or ""
        try:
            num, den = valor.split("/")
            fps = float(num) / float(den)
        except (ValueError, ZeroDivisionError):
            continue
        if fps > 0:
            return fps
    return None


def output_fps(clip_path) -> int:
    """
    Fps con los que se renderiza este clip: los de la fuente, redondeados.

    El redondeo absorbe los ritmos NTSC (29.97 → 30, 59.94 → 60), que es lo que
    quiere Remotion. Si no se puede leer nada, se cae al valor de config.
    """
    if not config.MATCH_SOURCE_FPS:
        return config.OUTPUT_FPS
    fps = clip_fps(clip_path)
    if not fps:
        return config.OUTPUT_FPS
    return max(1, min(config.MAX_OUTPUT_FPS, int(round(fps))))


def _source_aspect(frame_path) -> float:
    """Aspecto (ancho/alto) de la fuente, leído de una muestra del análisis."""
    try:
        import cv2
        img = imread(str(frame_path))
        if img is not None:
            h, w = img.shape[:2]
            if h:
                return w / h
    except Exception:
        pass
    return 16.0 / 9.0


def _focus_at(keyframes: list, t: float) -> float:
    """
    Valor de la trayectoria de foco en el segundo `t`. Interpolación lineal
    entre keyframes con clamp en los extremos: el mismo cálculo que hace
    `focusAt` en el componente de Remotion.
    """
    if not keyframes:
        return 0.5
    if t <= keyframes[0]["t"]:
        return float(keyframes[0]["x"])
    for a, b in zip(keyframes, keyframes[1:]):
        if t <= b["t"]:
            span = b["t"] - a["t"]
            if span <= 0:
                return float(b["x"])
            f = (t - a["t"]) / span
            return float(a["x"]) + (float(b["x"]) - float(a["x"])) * f
    return float(keyframes[-1]["x"])


def _slice_keyframes(keyframes: list, t0: float, t1: float) -> list:
    """
    Trozo de la trayectoria de foco que cae dentro del tramo [t0, t1), en tiempo
    del clip (el mismo reloj que usa el componente, así no hay que reajustar
    nada del lado de Remotion).

    Los bordes se interpolan en vez de recortarse a secas: si no, el tramo
    arrancaría en el keyframe anterior al corte y la cámara pegaría un salto al
    entrar. Devuelve [] si adentro del tramo la cámara no se mueve — ahí un
    foco fijo hace lo mismo con menos props.
    """
    if not keyframes or t1 <= t0:
        return []
    inner = [{"t": round(float(k["t"]), 3), "x": round(float(k["x"]), 3)}
             for k in keyframes if t0 < float(k["t"]) < t1]
    out = ([{"t": round(t0, 3), "x": round(_focus_at(keyframes, t0), 3)}]
           + inner
           + [{"t": round(t1, 3), "x": round(_focus_at(keyframes, t1), 3)}])
    xs = {k["x"] for k in out}
    return out if len(xs) > 1 else []


def follow_shot_segments(clip_path, clip_duration: float, width: int, height: int,
                         fps: int, focus_keyframes: list | None = None) -> list | None:
    """
    Tramos de layout para "seguir la toma": split mientras están los dos,
    recorte cerrado cuando la cámara va a uno solo.

    Se analiza el ARCHIVO DE CLIP (no el tramo del original) porque después del
    ajuste de bordes y de los jump cuts los tiempos ya no coinciden.

    `focus_keyframes` es la trayectoria de la cámara que sigue al hablante (la
    del clip entero, ya resuelta por detect_layout). Se reparte entre los tramos
    de recorte cerrado para que seguir la toma SUME el seguimiento en vez de
    reemplazarlo por un plano fijo. En los tramos "split" no aplica: ahí cada
    mitad tiene su propio foco.

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
            kf = _slice_keyframes(focus_keyframes or [], s["start"], s["end"])
            if kf:
                item["focusKeyframes"] = kf
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
    source_aspect: float | None = None,
    overlays: dict | None = None,
    fps: int | None = None,
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
        "fps":       fps or config.OUTPUT_FPS,
        "layout":    layout,
        "focusX":    focus_x,
        "focusKeyframes": focus_keyframes or [],
        "focusTop":    focus_top,
        "focusBottom": focus_bottom,
        "sourceAspect": source_aspect or clip_aspect(clip_path),
    }
    if overlays:
        props["overlays"] = overlays
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
            "--fps",    str(fps or config.OUTPUT_FPS),
            # Render intermedio: lo vuelve a tocar el arte final, así que se
            # guarda con más calidad que la del archivo de salida.
            "--crf",    str(config.RENDER_CRF),
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
    source_aspect: float | None = None,
    fps: int | None = None,
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
        "fps":       fps or config.OUTPUT_FPS,
        "layout":    layout,
        "focusX":    focus_x,
        "focusKeyframes": focus_keyframes or [],
        "focusTop":    focus_top,
        "focusBottom": focus_bottom,
        "sourceAspect": source_aspect or clip_aspect(clip_path),
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
            # La portada es una sola imagen: no hay razón para ahorrar acá.
            "--jpeg-quality", "95",
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

    # Aspecto y fps se leen una vez y se reusan en el video, en la portada y en
    # el seguimiento de la toma: si cada uno los resolviera por su cuenta, la
    # portada podría quedar encuadrada distinto que el clip.
    src_aspect = clip_aspect(clip["clip_path"])
    fps        = output_fps(clip["clip_path"])

    duration_frames = math.ceil(clip_duration * fps)

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
        fallo = False
        try:
            layout_segments = follow_shot_segments(
                clip["clip_path"], clip_duration, width, height, fps,
                focus_keyframes=keyframes,
            )
        except Exception as e:
            fallo = True
            _log(f"     ⚠️  No se pudo seguir la toma ({e}); layout fijo.")
        if layout_segments:
            kinds = "→".join(
                "⧉" if s["layout"] == "split" else "📱" for s in layout_segments
            )
            con_kf = sum(1 for s in layout_segments if s.get("focusKeyframes"))
            extra = f" · {con_kf} con seguimiento" if con_kf else ""
            enc["badge"] = (
                f"🔀 sigue la toma ({len(layout_segments)} tramos: {kinds}{extra})"
            )
        elif not fallo:
            # Sin este aviso el toggle parecía no hacer nada: el clip sale igual
            # que con el layout fijo y el badge no lo delataba.
            _log("     ℹ️  Seguir la toma: este clip no cambia de plano; "
                 "queda el encuadre fijo.")

    _log(f"  🎬 {title} — {preset['label']} · {fps} fps · {enc['badge']}")

    # Remotion escribe un crudo y el arte final produce el archivo definitivo.
    # El crudo va al lado del destino (mismo disco) para que no haya que copiar
    # entre volúmenes, y se borra apenas termina.
    raw_path = output_path.with_name(f".{output_path.stem}.raw.mp4")

    render_clip(
        clip_path=clip["clip_path"],
        output_path=raw_path,
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
        source_aspect=src_aspect,
        overlays=overlays_for_render(clip),
        fps=fps,
        concurrency=concurrency,
    )

    # ── Arte final ────────────────────────────────────────────────────────────
    # Si falla, el crudo igual sirve: se lo renombra al destino y se avisa. Es
    # preferible entregar el clip sin realce que perder el render entero.
    try:
        finish(
            raw_path, output_path,
            sharpen=config.FINISH_SHARPEN,
            denoise=config.FINISH_DENOISE,
            crf=config.OUTPUT_CRF,
        )
        raw_path.unlink(missing_ok=True)
    except Exception as e:
        _log(f"     ⚠️  Arte final falló ({e}); queda el render crudo.")
        raw_path.replace(output_path)

    # Portada: mejor frame con cara (o punto medio), mismo recorte, sin texto.
    cover_path  = output_dir / f"{name} - portada.jpg"
    cover_frame = int(round(cover_time * fps))
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
            source_aspect=src_aspect,
            fps=fps,
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
