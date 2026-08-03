"""
Genera public/captions.json a partir del VO, con timestamps por palabra.

Alternativa a scripts/transcribe.ts (whisper.cpp): reusa faster-whisper, que
ya está instalado en el .venv del repo y tiene los modelos cacheados, así no
hay que bajar 1.5 GB de whisper.cpp.

    ../.venv/Scripts/python.exe scripts/transcribe_fw.py public/audio/vo-criterio.mp3 public/captions.json

La salida es el formato de @remotion/captions (mismo que produce toCaptions),
que es lo que consumen useCue() y <Subtitles/>.
"""

import json
import os
import sys
from pathlib import Path

# La consola de Windows es cp1252: sin esto, cualquier caracter fuera de ASCII
# en un print revienta el script (y el traceback tapa el error real).
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

SOURCE = Path(sys.argv[1] if len(sys.argv) > 1 else "public/audio/vo-criterio.mp3")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "public/captions.json")
MODEL = os.environ.get("WHISPER_MODEL", "large-v2")
FPS = 30

# Frases que Whisper inventa cuando el archivo termina en silencio.
HALLUCINATIONS = (
    "amara.org",
    "subtítulos realizados por",
    "subtitulos realizados por",
    "www.",
)


def load_model():
    from faster_whisper import WhisperModel

    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() > 0:
            try:
                print(f"→ Cargando '{MODEL}' en GPU…", flush=True)
                return WhisperModel(MODEL, device="cuda", compute_type="float16")
            except Exception as e:  # falta cuDNN, VRAM, etc.
                print(f"⚠️  GPU no disponible ({type(e).__name__}); voy a CPU", flush=True)
    except Exception:
        pass
    print(f"→ Cargando '{MODEL}' en CPU…", flush=True)
    return WhisperModel(MODEL, device="cpu", compute_type="int8")


def main() -> None:
    model = load_model()

    print(f"→ Transcribiendo {SOURCE}…", flush=True)
    segments, info = model.transcribe(
        str(SOURCE),
        language="es",
        beam_size=5,
        word_timestamps=True,
        # Sin VAD: el VO es continuo y el filtro desplaza timestamps.
        vad_filter=False,
    )

    captions = []
    text_parts = []
    for seg in segments:
        # Whisper alucina créditos sobre el silencio ("Subtítulos realizados
        # por la comunidad de Amara.org"). Si entra, se cuela como subtítulo
        # y además estira la duración del episodio con aire muerto.
        if any(h in seg.text.lower() for h in HALLUCINATIONS):
            print(f"   (descarto alucinación en {seg.start:.0f}s: {seg.text.strip()[:60]})", flush=True)
            continue
        for w in seg.words or []:
            start_ms = round(w.start * 1000)
            end_ms = round(w.end * 1000)
            captions.append(
                {
                    "text": w.word,
                    "startMs": start_ms,
                    "endMs": end_ms,
                    "timestampMs": round((start_ms + end_ms) / 2),
                    "confidence": round(float(w.probability), 4),
                }
            )
        text_parts.append(seg.text.strip())
        if len(captions) % 200 < 5:
            print(f"   … {len(captions)} palabras ({seg.end:.0f}s)", flush=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(captions, ensure_ascii=False, indent=2), encoding="utf-8")

    # Transcripción plana, para poder leer el guion real y verificar los cues.
    txt = OUT.with_suffix(".txt")
    txt.write_text("\n".join(text_parts), encoding="utf-8")

    dur = captions[-1]["endMs"] / 1000 if captions else 0
    print(f"✓ {len(captions)} palabras → {OUT}")
    print(f"  Texto plano → {txt}")
    print(f"  Duración del VO: {dur:.1f}s ({int(dur * FPS + 0.5)} frames a {FPS}fps)")


if __name__ == "__main__":
    main()
