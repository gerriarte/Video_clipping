"""
Componente custom de Streamlit: las pantallas de clips en React.

Hay UN componente y un build; cada pantalla se elige con el argumento `screen`,
que `frontend/src/main.tsx` despacha. Así las dos comparten el bridge, los
tokens de estilo y los iconos de formato sin trucos de resolución de módulos.

- `clip_gallery(...)`  Paso 3: grilla de tarjetas para elegir qué cortar y en
                       qué formato, con el recorte dibujado sobre la foto.
- `clip_publish(...)`  Paso 5: lista + detalle para dejar los textos listos.

El frontend es React puro y NO sabe que existe Streamlit: toda la atadura vive
en `frontend/src/bridge.streamlit.ts`. Este archivo es el otro extremo — el día
que el host sea una API HTTP, se reemplazan los dos y las pantallas no cambian.
"""

import os
import streamlit.components.v1 as components

# Poné _RELEASE = False y corré `npm run dev` en frontend/ para desarrollar con
# hot-reload. En True usa el build commiteado (no necesita Node en runtime).
_RELEASE = True

_DIR = os.path.dirname(os.path.abspath(__file__))

if not _RELEASE:
    # Puerto distinto al de clip_editor (5173) para tener los dos a la vez.
    _component_func = components.declare_component("clip_ui", url="http://localhost:5174")
else:
    _component_func = components.declare_component(
        "clip_ui", path=os.path.join(_DIR, "frontend", "build")
    )


def clip_gallery(
    clips: list,
    formats: list,
    types: list,
    video_url: str,
    source_aspect: float = 16 / 9,
    pickable: bool = True,
    show_timeline: bool = True,
    key: str | None = None,
):
    """
    Pasos 3 y 4. Dibuja la galería y devuelve el estado editado de los clips.

    Args:
        clips:  [{id, title, start, end, type, reason, selected, format,
                  speakerFollow, followShot, thumbs:[{url,label}], shot:{...}}]
        formats: [{key, label, short, crop, aspect, autoLayout}]
        types:   opciones del selector de tipo.
        video_url: URL del video fuente (servido con Range) para ver un tramo.
        source_aspect: relación de aspecto de la fuente (ancho/alto).
        pickable: si se elige qué clips entran al corte (Paso 3). En el Paso 4
                  ya están cortados: la tarjeta muestra el número del clip y el
                  foco viaja en `selected` para que el host dibuje el encuadre.
        show_timeline: si se ofrece saltar al editor de timeline.

    Returns:
        {"clips": [...], "selected": int, "action": "timeline"|None,
         "nonce": int} o None si el componente todavía no mandó nada.
    """
    return _component_func(
        screen="gallery",
        clips=clips,
        formats=formats,
        types=types,
        videoUrl=video_url,
        sourceAspect=float(source_aspect),
        pickable=bool(pickable),
        showTimeline=bool(show_timeline),
        key=key,
        default=None,
    )


def clip_publish(
    clips: list,
    formats: list,
    platforms: list,
    key: str | None = None,
):
    """
    Paso 5. Lista + detalle de los clips renderizados y sus textos.

    Args:
        clips: [{id, index, title, start, end, duration, type, reason, format,
                 aspect, videoUrl, coverUrl, captions:{plataforma: texto}}]
        formats:   [{key, label, short, crop, aspect, autoLayout}]
        platforms: [{key, label}] — las columnas de texto.

    Returns:
        {"clips": [{id, format, captions}], "selected": int,
         "action": {"kind": "rerender", "id": int}|None, "nonce": int}
        o None si el componente todavía no mandó nada.
    """
    return _component_func(
        screen="publish",
        clips=clips,
        formats=formats,
        platforms=platforms,
        key=key,
        default=None,
    )
