"""
Zumo Streaming Pipeline — Configuración central
"""

import os
import sys
from pathlib import Path

# En Windows el stdout/stderr suele quedar en cp1252 (charmap) y los emojis de
# los print() revientan con UnicodeEncodeError. Eso, dentro de la app, se reporta
# como "Error en Remotion" aunque el render ande bien. Forzamos UTF-8 al arranque.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        # Streamlit u otros wrappers pueden no exponer reconfigure(): se ignora.
        pass

# Cargar .env antes de leer variables (por si no se setearon en la sesión)
_env = Path(__file__).parent / ".env"
if _env.exists():
    for _l in _env.read_text(encoding="utf-8").splitlines():
        _l = _l.strip()
        if _l and not _l.startswith("#") and "=" in _l:
            _k, _v = _l.split("=", 1)
            os.environ[_k.strip()] = _v.strip()

# ── Modelo / Proveedor de LLM ─────────────────────────────────────────────────
# LLM_PROVIDER elige quién hace el análisis y los captions:
#   "anthropic" → Claude (nube, mejor calidad)
#   "ollama"    → modelo local (gratis, privado, sin internet; menor calidad)
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic").strip().lower()

CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

# Ollama (solo aplica si LLM_PROVIDER == "ollama").
OLLAMA_HOST    = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL   = os.environ.get("OLLAMA_MODEL", "qwen2.5:14b")   # gemma4 es flojo p/ clips
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "600"))  # segundos
# Temperatura para Ollama. El default de muchos modelos (gemma) es 1.0, demasiado
# alto para extracción: aluciona timestamps y es inconsistente. 0.3 da salidas
# más fieles y estables para identificar clips y copiar tiempos exactos.
OLLAMA_TEMPERATURE = float(os.environ.get("OLLAMA_TEMPERATURE", "0.3"))
# Ventana de contexto para la pasada de análisis (transcript completo). El default
# de Ollama es chico (~4k) y truncaría el transcript en SILENCIO; lo subimos.
# Bajalo si te quedás sin memoria (RAM/VRAM); subilo para transcripts muy largos.
OLLAMA_NUM_CTX_ANALYZE = int(os.environ.get("OLLAMA_NUM_CTX_ANALYZE", "32768"))

# ── Rutas base ───────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent
DOWNLOADS_DIR = BASE_DIR / "downloads"
CLIPS_DIR     = BASE_DIR / "clips"
OUTPUT_DIR    = BASE_DIR / "output"
REMOTION_DIR  = BASE_DIR / "remotion"
MODELS_DIR    = BASE_DIR / "models"

# Modelo de MediaPipe Tasks para Face Landmarker (detección multi-cara + boca).
# Se usa para seguir a la persona que habla en el recorte 9:16. Si falta, el
# detector intenta descargarlo automáticamente; si no puede, cae al método Haar.
FACE_LANDMARKER_MODEL = MODELS_DIR / "face_landmarker.task"
FACE_LANDMARKER_URL   = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)

# ── Parámetros de clip ────────────────────────────────────────────────────────
MAX_CLIP_SECONDS   = 60
MIN_CLIP_SECONDS   = 15
TARGET_CLIPS       = 10     # Cantidad de clips a extraer por video

# ── Formato de salida ─────────────────────────────────────────────────────────
# Default 9:16 (se conserva para consumidores que no eligen formato explícito).
OUTPUT_WIDTH       = 1080
OUTPUT_HEIGHT      = 1920   # 9:16
OUTPUT_FPS         = 30
OUTPUT_CRF         = 18     # calidad del archivo FINAL (menor = mejor; 18 ≈ visualmente sin pérdida)

# Calidad del render intermedio de Remotion. Es un archivo temporal que después
# vuelve a pasar por ffmpeg en el arte final, así que se guarda con más calidad
# que la de salida: si se encodeara ya a 18, la segunda pasada partiría de algo
# degradado y sumaría una generación de pérdida encima.
RENDER_CRF         = 14

# Arte final (modules/finish.py): realce que recupera parte de la definición que
# pierde el escalador del navegador al ampliar el recorte vertical.
# Ponelo en False si preferís el render crudo.
FINISH_SHARPEN     = True
# Destramado previo. Apagado: sobre este material no cambió nada medible y de
# más ablanda. Encendelo si la fuente viene ruidosa.
FINISH_DENOISE     = False

# Cuántos clips se renderizan a la vez. Cada render levanta su propio Chromium,
# así que esto multiplica la RAM: 2 es un buen default y con 8+ núcleos rinde.
# Bajalo a 1 si la máquina se queda sin memoria; subilo si te sobra.
_default_render_workers = 2 if (os.cpu_count() or 1) >= 8 else 1
RENDER_CONCURRENCY = max(1, int(os.environ.get("RENDER_CONCURRENCY", _default_render_workers)))

# ── Formatos por clip ─────────────────────────────────────────────────────────
# Cada clip elige su formato en la UI. Campos:
#   width/height : dimensiones del render.
#   base         : layout de Remotion cuando NO se autodetecta ("fill", "split"
#                  o "letterbox" = plano entero centrado sobre negro).
#   auto_layout  : si True, detect_layout busca al hablante para centrar el
#                  recorte. Si False, se usa `base` fijo.
#   allow_fit    : si False, el recorte SIEMPRE llena la pantalla aunque no se
#                  detecte una cara grande (si no, detect_layout caería a "fit",
#                  plano completo sobre fondo borroso). Para el 9:16 completo ya
#                  está el preset propio con barras negras, así que "9:16" no
#                  necesita ese fallback y se vuelve predecible.
#   crop         : si el formato recorta algo (habilita el encuadre manual y el
#                  modo "seguir la toma"). 16:9 y 9:16 completo muestran el plano
#                  entero: no hay nada que encuadrar.
FORMAT_PRESETS = {
    "9:16":      {"label": "9:16 vertical",        "width": 1080, "height": 1920, "base": "fill",      "auto_layout": True,  "allow_fit": False, "crop": True},
    "9:16-full": {"label": "9:16 completo",        "width": 1080, "height": 1920, "base": "letterbox", "auto_layout": False, "crop": False},
    "1:1":       {"label": "1:1 cuadrado",         "width": 1080, "height": 1080, "base": "fill",      "auto_layout": True,  "crop": True},
    "16:9":      {"label": "16:9 horizontal",      "width": 1920, "height": 1080, "base": "fill",      "auto_layout": False, "crop": False},
    "split":     {"label": "9:16 dividido",        "width": 1080, "height": 1920, "base": "split",     "auto_layout": False, "crop": True},
}
DEFAULT_FORMAT = "9:16"


def crops(fmt_key: str) -> bool:
    """Si el formato recorta (y por lo tanto se puede encuadrar a mano)."""
    return bool(FORMAT_PRESETS.get(fmt_key, {}).get("crop"))

# ── Marca Zumo ───────────────────────────────────────────────────────────────
ZUMO_CONTEXT = """
Zumo Streaming es un canal de YouTube sobre Negocios, Tecnología, Marketing y temas afines.
El tono es relajado pero profesional, orientado a profesionales y empresas latinoamericanas.

Los hosts son:
- David Guerrero: Diseñador de Marca y Gerente de MTM (Marca tu Marca)
- Carolina Betancurt: Social Media Manager en MTM
- Camila Garavito: Ventas y Gestión de Proyectos en MTM
- Ger: Especialista en Marketing e Inteligencia Artificial

El contenido mezcla conversación fluida con insights accionables para emprendedores y profesionales.
"""

# ── API Key ───────────────────────────────────────────────────────────────────
# Solo es obligatoria si el proveedor activo es Anthropic. Con Ollama (local) no
# hace falta ninguna key.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
if LLM_PROVIDER == "anthropic" and not ANTHROPIC_API_KEY:
    raise EnvironmentError(
        "Falta ANTHROPIC_API_KEY (proveedor activo: anthropic). "
        "Ejecutá: set ANTHROPIC_API_KEY=tu_key  (o agregala al .env), "
        "o cambiá a local con LLM_PROVIDER=ollama."
    )

# ── Postiz (programación de publicaciones) ────────────────────────────────────
# Self-hosted: la base termina en /api/public/v1. Cloud sería https://api.postiz.com/public/v1
POSTIZ_API_URL = os.environ.get("POSTIZ_API_URL", "https://redes.abralatam.com/api/public/v1")
POSTIZ_API_KEY = os.environ.get("POSTIZ_API_KEY", "")
