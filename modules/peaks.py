"""
Precómputo de la forma de onda (peaks) del audio de un video, para pasársela a
wavesurfer.js. Así el editor no tiene que descargar y decodificar todo el audio
en el navegador (clave en videos largos).
"""

import subprocess
from pathlib import Path


def compute_peaks(video_path: Path, n_buckets: int = 4000, sample_rate: int = 8000) -> list | None:
    """
    Devuelve una lista de `n_buckets` valores 0–1 (máx absoluto por bucket) que
    representan la envolvente del audio. None si falla (ffmpeg/numpy no disponibles
    o el video no tiene audio).
    """
    try:
        import numpy as np
    except ImportError:
        return None

    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-ac", "1", "-ar", str(sample_rate),
        "-f", "s16le", "-v", "quiet", "-",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True)
    except Exception:
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None

    data = np.frombuffer(proc.stdout, dtype=np.int16)
    if data.size == 0:
        return None
    data = np.abs(data.astype(np.float32)) / 32768.0

    n = int(min(n_buckets, data.size))
    if n <= 0:
        return None
    edges = np.linspace(0, data.size, n + 1).astype(int)
    peaks = np.zeros(n, dtype=np.float32)
    for i in range(n):
        a, b = edges[i], edges[i + 1]
        if b > a:
            peaks[i] = data[a:b].max()

    # Normalizar para aprovechar todo el alto de la onda.
    mx = float(peaks.max())
    if mx > 0:
        peaks = peaks / mx
    return [round(float(v), 4) for v in peaks]
