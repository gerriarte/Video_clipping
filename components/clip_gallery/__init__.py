"""
Componente custom de Streamlit: galería de clips (grilla de tarjetas).

Reemplaza a la planilla + el panel de previews del Paso 3: cada clip es una
tarjeta con la foto del tramo, el recorte del formato dibujado encima, la
evidencia del análisis y sus controles.

El frontend (frontend/src) es React puro y NO sabe que existe Streamlit: toda
la atadura vive en `frontend/src/bridge.streamlit.ts`. Este archivo es el otro
extremo de esa atadura — el día que el host sea una API HTTP, se borran los dos
y el componente sigue igual.
"""

import os
import streamlit.components.v1 as components

# Poné _RELEASE = False y corré `npm run dev` en frontend/ para desarrollar con
# hot-reload. En True usa el build commiteado (no necesita Node en runtime).
_RELEASE = True

_DIR = os.path.dirname(os.path.abspath(__file__))

if not _RELEASE:
    # Puerto distinto al de clip_editor (5173) para poder tener los dos a la vez.
    _component_func = components.declare_component(
        "clip_gallery", url="http://localhost:5174"
    )
else:
    _build_dir = os.path.join(_DIR, "frontend", "build")
    _component_func = components.declare_component("clip_gallery", path=_build_dir)


def clip_gallery(
    clips: list,
    formats: list,
    types: list,
    video_url: str,
    source_aspect: float = 16 / 9,
    key: str | None = None,
):
    """
    Dibuja la galería y devuelve el estado editado de los clips.

    Args:
        clips:  [{id, title, start, end, type, reason, selected, format,
                  speakerFollow, followShot, thumbs:[{url,label}], shot:{...}}]
        formats: [{key, label, short, crop, aspect, autoLayout}]
        types:   opciones del selector de tipo.
        video_url: URL del video fuente (servido con Range) para ver un tramo.
        source_aspect: relación de aspecto de la fuente (ancho/alto).
        key: key de Streamlit.

    Returns:
        {"clips": [...], "action": "timeline"|None, "nonce": int} o None si el
        componente todavía no mandó nada.
    """
    return _component_func(
        clips=clips,
        formats=formats,
        types=types,
        videoUrl=video_url,
        sourceAspect=float(source_aspect),
        key=key,
        default=None,
    )
