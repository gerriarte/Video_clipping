"""
Proxy de baja resolución para editar con fluidez.

Scrubbear un archivo original de varios GB en el navegador es pesado. Generamos
una vez un proxy 480p liviano (faststart) que el editor usa para previsualizar y
hacer seek; el corte final sigue saliendo del ORIGINAL (calidad intacta).
"""

import subprocess
from pathlib import Path


def proxy_path_for(video_path) -> Path:
    vp = Path(video_path)
    return vp.with_name(vp.stem + ".proxy480.mp4")


def ensure_proxy(video_path, height: int = 480, progress_fn=None) -> Path:
    """
    Devuelve la ruta del proxy 480p (lo genera si falta). Si ffmpeg falla,
    devuelve el original (que igual se sirve con Range). Cacheado en disco.
    """
    vp = Path(video_path)
    proxy = proxy_path_for(vp)
    if proxy.exists() and proxy.stat().st_size > 0:
        return proxy

    if progress_fn:
        progress_fn("Generando proxy de edición (480p)… se hace una sola vez.")

    cmd = [
        "ffmpeg", "-y", "-i", str(vp),
        "-vf", f"scale=-2:{height}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
        "-c:a", "aac", "-b:a", "96k",
        "-movflags", "+faststart",
        "-loglevel", "error",
        str(proxy),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode == 0 and proxy.exists() and proxy.stat().st_size > 0:
            return proxy
    except Exception:
        pass

    # Fallback: usar el original (funciona, solo menos fluido).
    return vp
