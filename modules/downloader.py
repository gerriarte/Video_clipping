"""
Descarga video + transcript VTT de YouTube usando yt-dlp,
o carga un video local desde el filesystem.
"""

import re
import subprocess
import json
import sys
from pathlib import Path
from typing import Callable

# Usa siempre el yt-dlp del mismo entorno Python que el script en ejecución
_YT_DLP = [sys.executable, "-m", "yt_dlp"]


def _safe_folder_name(name: str, fallback: str = "video") -> str:
    """Convierte un título en un nombre de carpeta válido en Windows."""
    # Quita caracteres no permitidos en Windows: \ / : * ? " < > |
    cleaned = re.sub(r'[\\/:*?"<>|]', "", name)
    # Colapsa espacios y normaliza
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # Windows no admite puntos/espacios al final del nombre de carpeta
    cleaned = cleaned.rstrip(". ")
    # Limita longitud para no exceder límites de ruta
    cleaned = cleaned[:120].rstrip(". ")
    return cleaned or fallback


def download_video(
    url: str,
    output_dir: Path,
    progress_fn: Callable[[str], None] | None = None,
) -> dict:
    """
    Descarga el video y el transcript VTT automático de YouTube.

    progress_fn: callback opcional que recibe cada línea de output de yt-dlp.
    """
    meta     = _get_metadata(url, progress_fn)
    video_id = meta.get("id", "unknown")
    title    = meta.get("title", "Sin título")
    duration = int(meta.get("duration", 0))

    # Cada video va a su propia subcarpeta nombrada con el título, para
    # poder identificarlo fácilmente en el filesystem.
    folder_name = _safe_folder_name(title, fallback=video_id)
    output_dir  = output_dir / folder_name
    output_dir.mkdir(parents=True, exist_ok=True)
    template = str(output_dir / "%(id)s.%(ext)s")

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


def load_local_video(
    file_path: str | Path,
    output_dir: Path,
    progress_fn: Callable[[str], None] | None = None,
) -> dict:
    """
    Carga un video guardado en disco (sin descargar nada).
    Busca un archivo .vtt con el mismo nombre en la misma carpeta.
    Devuelve el mismo dict que download_video.
    """
    src = Path(file_path)
    if not src.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {src}")
    if not src.is_file():
        raise ValueError(f"La ruta no es un archivo: {src}")

    output_dir.mkdir(parents=True, exist_ok=True)

    video_id = re.sub(r"[^\w-]", "_", src.stem)[:60].strip("_") or "local"
    title = src.stem

    if progress_fn:
        progress_fn(f"Leyendo metadatos de: {src.name}")

    duration = _get_local_duration(src)

    # Buscar VTT con el mismo stem en el mismo directorio
    vtt_path = None
    for candidate in sorted(src.parent.glob(f"{src.stem}*.vtt")):
        vtt_path = candidate
        break

    if progress_fn:
        status = "con subtítulos VTT" if vtt_path else "sin subtítulos"
        progress_fn(f"✅ Video cargado ({duration}s, {status})")

    return {
        "video_path": src,
        "vtt_path":   vtt_path,
        "title":      title,
        "video_id":   video_id,
        "duration":   duration,
    }


def _get_local_duration(video_path: Path) -> int:
    """Obtiene la duración del video con ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(video_path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return int(float(data.get("format", {}).get("duration", 0)))
    except Exception:
        pass
    return 0


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
