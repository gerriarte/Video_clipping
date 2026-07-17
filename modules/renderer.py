"""
Renderiza clips con Remotion en el formato elegido por clip (9:16, 1:1, 16:9 o
split), sin subtítulos quemados. El encuadre (recorte al hablante / split) se
resuelve automáticamente con el detector de caras.
"""

import json
import math
import platform
import subprocess
import tempfile
from pathlib import Path

import config
from modules.layout_detector import detect_layout, detect_split
from modules.media_server import MediaServer

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

    if preset.get("auto_layout"):
        det = detect_layout(clip_path, clip_duration, target_aspect=width / height)
        kf  = det.get("focus_keyframes", [])
        if det["layout"] == "fill" and len(kf) > 1:
            badge = f"🎯 sigue al hablante ({len(kf)} kf)"
        elif det["layout"] == "fill":
            badge = "📐 recorte al hablante"
        else:
            badge = "🖥 plano completo (fondo borroso)"
        base.update(
            layout=det["layout"], focus_x=det["focus_x"],
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
) -> Path:
    """
    Llama a Remotion para renderizar el clip en las dimensiones dadas.

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


def render_clips(
    clips_with_subs: list[dict],
    output_dir: Path,
    video_id: str,
    progress_fn: "Callable[[int, int, str], None] | None" = None,
) -> list[dict]:
    """
    Renderiza todos los clips y retorna la lista con output_path añadido.
    progress_fn(done, total, titulo) se llama antes de cada clip y al finalizar.
    """
    server = MediaServer(config.CLIPS_DIR)  # puerto efímero + Range
    server.start()

    total   = len(clips_with_subs)
    results = []
    try:
        for done, clip in enumerate(clips_with_subs):
            idx   = clip["index"]
            title = clip.get("title", f"Clip {idx}")
            name  = _clip_filename(title, idx)
            output_path = output_dir / f"{name} - vertical.mp4"

            if progress_fn:
                progress_fn(done, total, title)

            clip_url = server.url_for(clip["clip_path"])

            # Duración real del archivo de clip (incluye los pads de corte).
            # Fallback para clips cortados antes de exponer clip_duration.
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

            _log(f"  🎬 [{done+1}/{total}] {title} — {preset['label']} · {enc['badge']}")

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
                )
            except Exception as e:
                _log(f"     ⚠️  No se pudo generar la portada: {e}")
                cover_path = None

            results.append({
                **clip,
                "output_path": output_path,
                "formato":     fmt_key,
                "layout":      layout,
                "cover_path":  cover_path,
            })

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
