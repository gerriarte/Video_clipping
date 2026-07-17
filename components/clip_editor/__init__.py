"""
Componente custom de Streamlit: editor visual de timeline para cortar clips.

Frontend en React + wavesurfer.js (ver frontend/). En release usa los assets
compilados de frontend/build; en dev apunta al server de Vite (localhost:5173).
"""

import os
import streamlit.components.v1 as components

# Poné _RELEASE = False y corré `npm run dev` en frontend/ para desarrollar el
# componente con hot-reload. En True usa el build commiteado (no necesita Node).
_RELEASE = True

_DIR = os.path.dirname(os.path.abspath(__file__))

if not _RELEASE:
    _component_func = components.declare_component(
        "clip_editor", url="http://localhost:5173"
    )
else:
    _build_dir = os.path.join(_DIR, "frontend", "build")
    _component_func = components.declare_component("clip_editor", path=_build_dir)


def clip_editor(
    video_url: str,
    duration: float,
    clips: list | None = None,
    peaks: list | None = None,
    types: list | None = None,
    key: str | None = None,
):
    """
    Muestra el editor de timeline y devuelve la lista de cortes al tocar "Aplicar".

    Args:
        video_url: URL HTTP del video (servido para el iframe).
        duration:  duración del video en segundos.
        clips:     cortes iniciales [{start, end, title, type}, ...] (semilla).
        peaks:     forma de onda precomputada (lista de floats) para videos largos.
        types:     opciones de tipo para el selector.
        key:       key de Streamlit.

    Returns:
        Lista de cortes [{start, end, title, type}, ...] tras "Aplicar", o None
        si todavía no se aplicó nada.
    """
    return _component_func(
        video_url=video_url,
        duration=duration,
        clips=clips or [],
        peaks=peaks,
        types=types,
        key=key,
        default=None,
    )
