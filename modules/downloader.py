"""
Descarga video + transcript VTT de YouTube usando yt-dlp.
"""

import subprocess
import json
import sys
from pathlib import Path
from typing import Callable

# Usa siempre el yt-dlp del mismo entorno Python que el script en ejecución
_YT_DLP = [sys.executable, "-m", "yt_dlp"]


def download_video(
    url: str,
    output_dir: Path,
    progress_fn: Callable[[str], None] | None = None,
) -> dict:
    """
    Descarga el video y el transcript VTT automático de YouTube.

    progress_fn: callback opcional que recibe cada línea de output de yt-dlp.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    template = str(output_dir / "%(id)s.%(ext)s")

    meta     = _get_metadata(url, progress_fn)
    video_id = meta.get("id", "unknown")
    title    = meta.get("title", "Sin título")
    duration = int(meta.get("duration", 0))

    cmd = _YT_DLP + [
        "--format", "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "--merge-output-format", "mp4",
        "--write-auto-subs",
        "--sub-langs", "es,es-419,es-ES,es-MX,es.*",
        "--convert-subs", "vtt",
        "--no-playlist",
        "--js-runtimes", "node",
        "--remote-components", "ejs:github",
        "--newline",
        "--output", template,
        url,
    ]

    _run_streaming(cmd, progress_fn)

    video_path = output_dir / f"{video_id}.mp4"
    if not video_path.exists():
        candidates = list(output_dir.glob(f"{video_id}*.mp4"))
        if not candidates:
            raise FileNotFoundError(f"No se encontró el video descargado para {video_id}")
        video_path = candidates[0]

    vtt_candidates = list(output_dir.glob(f"{video_id}*.vtt"))
    vtt_path = vtt_candidates[0] if vtt_candidates else None

    return {
        "video_path": video_path,
        "vtt_path":   vtt_path,
        "title":      title,
        "video_id":   video_id,
        "duration":   duration,
    }


def _get_metadata(
    url: str,
    progress_fn: Callable[[str], None] | None = None,
) -> dict:
    if progress_fn:
        progress_fn("Obteniendo metadatos del video...")
    cmd = _YT_DLP + ["--dump-json", "--no-playlist", "--js-runtimes", "node", "--remote-components", "ejs:github", url]
    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        raise RuntimeError(f"No se pudieron obtener metadatos:\n{result.stderr[-1000:]}")
    return json.loads(result.stdout)


def _run_streaming(
    cmd: list,
    progress_fn: Callable[[str], None] | None,
) -> None:
    """Corre un comando y pasa cada línea de stderr al callback."""
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    stderr_lines = []
    for line in iter(proc.stderr.readline, ""):
        line = line.rstrip()
        if not line:
            continue
        stderr_lines.append(line)
        if progress_fn:
            progress_fn(line)

    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(
            f"yt-dlp falló (código {proc.returncode}):\n" +
            "\n".join(stderr_lines[-20:])
        )
