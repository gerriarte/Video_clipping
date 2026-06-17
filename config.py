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

# ── Modelo ──────────────────────────────────────────────────────────────────
CLAUDE_MODEL = "claude-sonnet-4-6"

# ── Rutas base ───────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent
DOWNLOADS_DIR = BASE_DIR / "downloads"
CLIPS_DIR     = BASE_DIR / "clips"
OUTPUT_DIR    = BASE_DIR / "output"
REMOTION_DIR  = BASE_DIR / "remotion"

# ── Parámetros de clip ────────────────────────────────────────────────────────
MAX_CLIP_SECONDS   = 60
MIN_CLIP_SECONDS   = 15
TARGET_CLIPS       = 10     # Cantidad de clips a extraer por video

# ── Formato de salida ─────────────────────────────────────────────────────────
OUTPUT_WIDTH       = 1080
OUTPUT_HEIGHT      = 1920   # 9:16
OUTPUT_FPS         = 30

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
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
if not ANTHROPIC_API_KEY:
    raise EnvironmentError(
        "Falta ANTHROPIC_API_KEY. "
        "Ejecutá: set ANTHROPIC_API_KEY=tu_key  (o agregala al .env)"
    )

# ── Postiz (programación de publicaciones) ────────────────────────────────────
# Self-hosted: la base termina en /api/public/v1. Cloud sería https://api.postiz.com/public/v1
POSTIZ_API_URL = os.environ.get("POSTIZ_API_URL", "https://redes.abralatam.com/api/public/v1")
POSTIZ_API_KEY = os.environ.get("POSTIZ_API_KEY", "")
