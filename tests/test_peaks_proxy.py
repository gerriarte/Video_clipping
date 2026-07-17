import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from modules.peaks import compute_peaks
from modules.proxy import proxy_path_for


def test_proxy_path_naming():
    assert proxy_path_for("/tmp/some/video.mp4").name == "video.proxy480.mp4"
    assert proxy_path_for(Path("C:/x/y z/clip.mkv")).name == "clip.proxy480.mp4"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg no disponible")
def test_compute_peaks_on_tone():
    d = Path(tempfile.mkdtemp())
    f = d / "tone.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-loglevel", "error", str(f)],
        check=True,
    )
    peaks = compute_peaks(f, n_buckets=100)
    assert peaks is not None
    assert len(peaks) == 100
    assert all(0.0 <= p <= 1.0 for p in peaks)
    assert max(peaks) == 1.0  # normalizado


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg no disponible")
def test_compute_peaks_silence_is_low():
    d = Path(tempfile.mkdtemp())
    f = d / "sil.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=8000:cl=mono",
         "-t", "1", "-loglevel", "error", str(f)],
        check=True,
    )
    peaks = compute_peaks(f, n_buckets=50)
    assert peaks is not None
    assert max(peaks) == 0.0  # silencio → todo 0
