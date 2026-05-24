"""
Corta clips del video fuente usando ffmpeg.
"""

import re
import subprocess
from pathlib import Path
from typing import Callable


def cut_clip(
    video_path: Path,
    start: float,
    end: float,
    output_path: Path,
    pad_seconds: float = 0.25,
    progress_fn: Callable[[str], None] | None = None,
) -> Path:
    """
    Corta un fragmento del video entre start y end (segundos).
    progress_fn: callback que recibe cada línea de progreso de ffmpeg.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    actual_start = max(0.0, start - pad_seconds)
    duration     = end - start + pad_seconds

    cmd = [
        "ffmpeg",
        "-ss", str(actual_start),
        "-i", str(video_path),
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        "-avoid_negative_ts", "make_zero",
        "-stats",             # una línea de stats por segundo
        "-loglevel", "error", # solo errores en stderr (stats van a stdout con -stats)
        "-y",
        str(output_path),
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    stderr_lines = []

    # ffmpeg -stats escribe a stderr; leemos en tiempo real
    for line in iter(proc.stderr.readline, ""):
        line = line.rstrip()
        if not line:
            continue
        stderr_lines.append(line)
        if progress_fn:
            progress_fn(_parse_ffmpeg_line(line, duration))

    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg falló al cortar clip:\n" + "\n".join(stderr_lines[-10:])
        )

    return output_path


def cut_clips(
    video_path: Path,
    clips: list[dict],
    clips_dir: Path,
    video_id: str,
    progress_fn: Callable[[str], None] | None = None,
    start_index: int = 1,
) -> list[dict]:
    """Corta todos los clips y retorna la lista enriquecida con clip_path."""
    results = []
    for i, clip in enumerate(clips, start_index):
        name        = _clip_filename(clip.get("title", f"Clip {i}"), i)
        output_path = clips_dir / f"{name}.mp4"
        dur         = clip["end"] - clip["start"]

        total_display = start_index + len(clips) - 1
        def _progress(line, idx=i, total=total_display):
            if progress_fn:
                progress_fn(f"[{idx}/{total}] {line}")

        cut_clip(video_path, clip["start"], clip["end"], output_path, progress_fn=_progress)
        results.append({**clip, "clip_path": output_path, "index": i})

    return results


def _parse_ffmpeg_line(line: str, total_duration: float) -> str:
    """Convierte una línea de stats de ffmpeg en texto legible con porcentaje."""
    m = re.search(r"time=(\d+):(\d+):([\d.]+)", line)
    if m and total_duration > 0:
        elapsed = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        pct     = min(100, int(elapsed / total_duration * 100))
        speed_m = re.search(r"speed=([\d.]+)x", line)
        speed   = f" · {speed_m.group(1)}x" if speed_m else ""
        return f"Procesando… {pct}%{speed}"
    return line[:120]


def _clip_filename(title: str, index: int, max_len: int = 80) -> str:
    """Genera nombre de archivo legible a partir del título que asignó Claude."""
    # Eliminar caracteres inválidos en nombres de archivo de Windows/Mac
    clean = re.sub(r'[\\/:*?"<>|]', "", title)
    clean = re.sub(r"\s+", " ", clean).strip()
    # Truncar preservando palabras completas
    if len(clean) > max_len:
        clean = clean[:max_len].rsplit(" ", 1)[0]
    return f"{index:02d} - {clean}"
