"""
Transcribe el audio de un video con faster-whisper y genera un archivo VTT.
"""

import json
import subprocess
from pathlib import Path
from typing import Callable


def _probe_duration(video_path: Path) -> float:
    """Duración real del archivo (segundos) vía ffprobe; 0 si no se puede."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", str(video_path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return float(data.get("format", {}).get("duration", 0))
    except Exception:
        pass
    return 0.0


def _pick_device() -> tuple[str, str]:
    """
    Elige el mejor backend para Whisper: GPU (CUDA) si está disponible, si no CPU.
    En GPU usamos float16 (rápido y preciso); en CPU, int8 (lo más liviano).
    Devuelve (device, compute_type).
    """
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "float16"
    except Exception:
        pass
    return "cpu", "int8"


def transcribe_video(
    video_path: Path | str,
    progress_fn: Callable[[str], None] | None = None,
    model_size: str = "small",
    language: str = "es",
) -> Path:
    """
    Transcribe el audio con faster-whisper.
    Guarda el VTT junto al video original.
    Retorna el path al archivo VTT generado.
    """
    import os

    # Sube el timeout de descarga de HF Hub (por defecto solo 10 s, insuficiente
    # para modelos grandes como large-v2 ~3 GB con conexión lenta) y silencia el
    # aviso de "unauthenticated requests". Si tienes un token de HF, ponlo en la
    # variable de entorno HF_TOKEN y se usará automáticamente.
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

    from faster_whisper import WhisperModel

    video_path = Path(video_path)

    device, compute_type = _pick_device()

    if progress_fn:
        destino = "GPU (CUDA)" if device == "cuda" else "CPU"
        progress_fn(f"Cargando modelo Whisper '{model_size}' en {destino}… (primera vez descarga el modelo)")

    try:
        model = WhisperModel(model_size, device=device, compute_type=compute_type)
    except Exception as e:
        # Si la GPU falla (p. ej. faltan librerías CUDA/cuDNN), caemos a CPU.
        if device == "cuda":
            if progress_fn:
                progress_fn(f"⚠️ No se pudo usar la GPU ({type(e).__name__}); usando CPU…")
            device, compute_type = "cpu", "int8"
            model = WhisperModel(model_size, device=device, compute_type=compute_type)
        else:
            raise

    if progress_fn:
        progress_fn("Transcribiendo audio… (puede tardar varios minutos según la duración)")

    segments, info = model.transcribe(
        str(video_path),
        language=language,
        beam_size=5,
        vad_filter=True,
    )

    vtt_lines = ["WEBVTT", ""]
    # Duración real del video para el progreso. NO usamos info.duration: con
    # vad_filter activo, faster-whisper devuelve ahí la duración de voz (post-VAD),
    # no la del video, lo que hacía mostrar porcentajes inflados (ej. 96% al 4:22).
    total_secs = _probe_duration(video_path) or (getattr(info, "duration", 0) or 0)
    last_pct   = 0

    for seg in segments:
        text = seg.text.strip()
        if text:
            vtt_lines.append(f"{_secs_to_vtt(seg.start)} --> {_secs_to_vtt(seg.end)}")
            vtt_lines.append(text)
            vtt_lines.append("")

        if progress_fn and total_secs > 0:
            pct = min(100, int(seg.end / total_secs * 100))
            if pct >= last_pct + 5:
                last_pct = pct
                snippet = text[:55] + "…" if len(text) > 55 else text
                progress_fn(f"[{_secs_to_vtt(seg.start)}]  {snippet}  ({pct}%)")

    vtt_path = video_path.parent / f"{video_path.stem}.es.vtt"
    vtt_path.write_text("\n".join(vtt_lines), encoding="utf-8")

    if progress_fn:
        progress_fn(f"✅ Transcripción guardada: {vtt_path.name}")

    return vtt_path


def _secs_to_vtt(secs: float) -> str:
    h = int(secs // 3600)
    m = int((secs % 3600) // 60)
    s = secs % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"
