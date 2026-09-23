#!/usr/bin/env python3
"""
Zumo Streaming — Pipeline con UI de validación
Ejecutar: streamlit run app.py
"""

import csv
import io
import json
import os
import sys
import traceback
from pathlib import Path
from datetime import datetime, timedelta, time as _time

# Cargar .env si existe (evita tener que setear la variable en cada terminal)
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ[_k.strip()] = _v.strip()

# Windows: forzar UTF-8 en stdout/stderr para que los emojis no rompan
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

# ── Page config (debe ir primero) ─────────────────────────────────────────────
st.set_page_config(
    page_title="Fast Video Clipping",
    page_icon="🎬",
    layout="wide",
)

# ── Imports del pipeline ──────────────────────────────────────────────────────
try:
    import config
    from modules import llm
    from modules.downloader  import download_video, load_local_video
    from modules.analyzer    import parse_vtt, identify_clips, get_cues_for_clip, transcript_coverage
    from modules.clipper     import cut_clips
    from modules.renderer    import render_clips, speaker_follow, clip_aspect
    from modules.caption_gen import generate_all_captions
    from modules.transcriber import transcribe_video
    from modules.postiz      import PostizClient, build_posts_for_clip, maybe_upload_cover, to_utc_iso, PLATFORM_CAPTION_FIELD
    from modules.peaks       import compute_peaks
    from modules.proxy       import ensure_proxy, proxy_path_for
    from modules.media_server import MediaServer
    from modules.segment_preview import analyze_segment
    from modules.ui_state    import (
        normalize_format, gallery_formats,
        clips_to_gallery, apply_gallery,
        clips_to_publish, apply_publish,
        FORMAT_LABELS, LABEL_TO_KEY, FORMAT_OPTIONS, PUBLISH_PLATFORMS,
    )
    from components.clip_editor import clip_editor
    from components.zumo_ui     import clip_gallery, clip_publish
    CONFIG_OK    = True
    CONFIG_ERROR = None
except EnvironmentError as e:
    CONFIG_OK    = False
    CONFIG_ERROR = str(e)

try:
    import faster_whisper as _fw  # noqa
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

# ── Persistencia de estado en disco ──────────────────────────────────────────
_STATE_FILE = Path(
    os.environ.get("ZUMO_STATE_FILE") or (Path(__file__).parent / ".pipeline_state.json")
)


def _paths_to_str(obj):
    """Serializa Path → str recursivamente para JSON."""
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _paths_to_str(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_paths_to_str(i) for i in obj]
    return obj


def _restore_paths(obj, path_keys=("video_path", "vtt_path", "clip_path", "output_path")):
    """Restaura str → Path para las claves conocidas."""
    if isinstance(obj, dict):
        return {
            k: (Path(v) if k in path_keys and isinstance(v, str) and v else
                _restore_paths(v, path_keys))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_restore_paths(i, path_keys) for i in obj]
    return obj


def save_state():
    data = {k: _paths_to_str(st.session_state[k])
            for k in ("stage", "source_mode", "video_info", "cues", "clips", "clipped", "final_clips")}
    # El nonce de la última acción ya consumida en la galería viaja con el
    # estado: si no, al reiniciar la app con la pestaña abierta Streamlit le
    # reenvía al componente su último valor y la acción ("✂ Timeline") se
    # vuelve a disparar sola en la sesión nueva, que no la recuerda.
    if "_gallery_nonce" in st.session_state:
        data["_gallery_nonce"] = st.session_state["_gallery_nonce"]
    _STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_state():
    if not _STATE_FILE.exists():
        return
    try:
        data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
        for k, v in data.items():
            st.session_state[k] = _restore_paths(v)
    except Exception:
        pass  # archivo corrupto — arrancamos desde cero


# ── Session state ─────────────────────────────────────────────────────────────
_ZUMO_HOSTS = (
    "David Guerrero: Diseñador de Marca y Gerente de MTM (Marca tu Marca)\n"
    "Carolina Betancurt: Social Media Manager en MTM\n"
    "Camila Garavito: Ventas y Gestión de Proyectos en MTM\n"
    "Ger: Especialista en Marketing e Inteligencia Artificial"
)

DEFAULTS = {
    "stage":           "idle",
    "source_mode":     "youtube",
    "video_info":      None,
    "cues":            [],
    "clips":           [],
    "clipped":         [],
    "final_clips":     [],
    "ch_name":         "Zumo Streaming",
    "ch_desc":         "Canal de YouTube sobre Negocios, Tecnología, Marketing y temas afines. Orientado a profesionales y empresas latinoamericanas.",
    "ch_hosts":        _ZUMO_HOSTS,
    "ch_tone":         "Relajado pero profesional, con insights accionables para emprendedores.",
    "clips_editor_rev":    0,
    "last_dur_range":      (config.MIN_CLIP_SECONDS, config.MAX_CLIP_SECONDS),
    "extra_clips_pending": [],   # clips encontrados por "Buscar más", aún sin cortar
}
# Cargar estado persistido solo la primera vez en esta sesión
if "stage" not in st.session_state:
    for k, v in DEFAULTS.items():
        st.session_state[k] = v
    load_state()


def reset():
    for k in list(DEFAULTS.keys()):
        st.session_state.pop(k, None)
    if _STATE_FILE.exists():
        _STATE_FILE.unlink()


def go_back():
    """Retrocede un paso conservando los datos del paso anterior."""
    transitions = {
        "analyzed": ("downloaded", {"clips": [], "clipped": [], "final_clips": []}),
        "clipped":  ("analyzed",   {"clipped": [], "final_clips": [], "extra_clips_pending": []}),
        "captioned":("clipped",    {"final_clips": []}),
    }
    prev_stage, clear_keys = transitions.get(st.session_state.stage, (None, {}))
    if prev_stage:
        st.session_state.stage = prev_stage
        for k, v in clear_keys.items():
            st.session_state[k] = v
        save_state()


# ── Helpers ───────────────────────────────────────────────────────────────────

# Umbral mínimo de cobertura del transcript (fracción del video con cues).
# Por debajo de esto consideramos el VTT escaso y caemos a Whisper.
MIN_TRANSCRIPT_COVERAGE = 0.5


def whisper_fallback(info: dict, cues: list, progress_fn=None) -> tuple[list, object]:
    """
    Fallback automático: si el transcript falta o cubre poco del video,
    transcribe el audio con Whisper y devuelve los cues mejorados.

    Devuelve (cues, vtt_path). Si Whisper no está disponible o no mejora la
    cobertura, devuelve los cues originales sin cambios.
    """
    duration = info.get("duration", 0) or 0
    coverage = transcript_coverage(cues, duration)
    sparse   = (not cues) or (duration > 0 and coverage < MIN_TRANSCRIPT_COVERAGE)

    if not sparse or not WHISPER_AVAILABLE:
        return cues, info.get("vtt_path")

    if progress_fn:
        estado = "sin subtítulos" if not cues else f"transcript escaso ({coverage:.0%} del video)"
        progress_fn(f"⚠️ {estado} — transcribiendo el audio con Whisper…")
    try:
        vtt    = transcribe_video(info["video_path"], progress_fn=progress_fn)
        w_cues = parse_vtt(vtt)
    except Exception as e:
        if progress_fn:
            progress_fn(f"No se pudo transcribir con Whisper: {e}")
        return cues, info.get("vtt_path")

    # Solo reemplazamos si Whisper realmente cubre más del video
    if transcript_coverage(w_cues, duration) > coverage:
        if progress_fn:
            progress_fn(f"✅ Whisper generó {len(w_cues)} cues (mejor cobertura)")
        return w_cues, vtt
    return cues, info.get("vtt_path")


def make_live_logger(placeholder):
    """
    Devuelve un callback progress_fn que actualiza un st.empty() en tiempo real.
    Muestra las últimas 6 líneas en un bloque de código.
    """
    lines = []
    def _log(line: str):
        if line:
            lines.append(line)
            preview = "\n".join(lines[-6:])
            placeholder.code(preview, language=None)
    return _log



# ── Formatos por clip ─────────────────────────────────────────────────────────
# Las etiquetas y la normalización viven en modules/ui_state.py (con tests);
# acá quedan solo los alias que usa la UI vieja y el badge, que es cosmético.
_FORMAT_LABELS  = FORMAT_LABELS
_LABEL_TO_KEY   = LABEL_TO_KEY
_FORMAT_OPTIONS = FORMAT_OPTIONS
_FORMAT_BADGE   = {
    "9:16":      "📱 9:16",
    "9:16-full": "📱⬛ 9:16 completo",
    "1:1":       "⬛ 1:1",
    "16:9":      "🖥 16:9",
    "split":     "⧉ split",
}



def clips_to_df(clips: list) -> pd.DataFrame:
    return pd.DataFrame([{
        "✓":       c.get("_selected", True),
        "Título":  c["title"],
        "Formato": _FORMAT_LABELS[normalize_format(c.get("formato"))],
        "Inicio":  c["start"],
        "Fin":     c["end"],
        "Dur(s)":  round(c["end"] - c["start"], 1),
        "Tipo":    c["type"],
        "Razón":   c["reason"],
    } for c in clips])


def df_to_clips(df: pd.DataFrame, original: list) -> list:
    result = []
    for i, row in df.iterrows():
        if row["✓"]:
            clip = original[i].copy()
            clip["title"]   = row["Título"]
            clip["formato"] = _LABEL_TO_KEY.get(row["Formato"], config.DEFAULT_FORMAT)
            clip["start"]   = float(row["Inicio"])
            clip["end"]     = float(row["Fin"])
            clip["type"]    = row["Tipo"]
            clip["reason"]  = row["Razón"]
            result.append(clip)
    return result



# ── Preview del tramo antes de elegir el formato ──────────────────────────────
# El formato se elige cuando el clip TODAVÍA no se cortó, así que sin esto la
# decisión es a ciegas. Sacamos fotos del tramo del video original y contamos
# personas para sugerir "split" (dos) o 9:16 (una).

def segment_analysis(clip: dict, info: dict) -> dict:
    """Análisis de la toma del tramo, cacheado por tramo (sesión + disco)."""
    # El sufijo de versión evita leer análisis viejos (de otra forma) que hayan
    # quedado en la sesión con menos campos.
    key = f"_segprev2_{info.get('video_id','')}_{clip['start']:.2f}_{clip['end']:.2f}"
    if key not in st.session_state:
        st.session_state[key] = analyze_segment(
            info["video_path"], clip["start"], clip["end"],
            video_id=info.get("video_id", "video"),
        )
    return st.session_state[key]



def segment_video_url(info: dict) -> str:
    """URL del video para el reproductor: proxy 480p si ya existe, si no el original."""
    src = Path(info["video_path"])
    proxy = proxy_path_for(src)
    if proxy.exists() and proxy.stat().st_size > 0:
        src = proxy
    return get_media_server().url_for(src)



# ── Galería de clips (componente custom) ──────────────────────────────────────
# Reemplaza a la planilla + el panel de previews: cada clip es una tarjeta con
# la foto del tramo y el recorte del formato dibujado encima. Ver
# components/clip_gallery/.


def get_preview_server():
    """
    Server HTTP de sesión para `clips/` (miniaturas de los tramos).

    Va aparte del de `downloads/` a propósito: cada MediaServer sirve UNA raíz,
    y ensancharla hasta la raíz del proyecto pondría el `.env` a un GET de
    distancia.
    """
    srv = st.session_state.get("_preview_server")
    if srv is None:
        srv = MediaServer(config.CLIPS_DIR)  # puerto efímero
        srv.start()
        st.session_state["_preview_server"] = srv
    return srv


def source_aspect(info: dict) -> float:
    """Aspecto del video fuente (cacheado en sesión). 16:9 si no se puede leer."""
    key = f"_srcaspect_{info.get('video_id', '')}"
    if key not in st.session_state:
        st.session_state[key] = clip_aspect(info["video_path"])
    return st.session_state[key]



# ── Pantalla de publicación (Paso 5) ──────────────────────────────────────────


def get_output_server():
    """Server HTTP de sesión para `output/` (clips renderizados y portadas)."""
    srv = st.session_state.get("_output_server")
    if srv is None:
        srv = MediaServer(config.OUTPUT_DIR)  # puerto efímero
        srv.start()
        st.session_state["_output_server"] = srv
    return srv


def _media_url(srv, path) -> str:
    """
    URL del archivo, o "" si todavía no existe.

    Lleva la marca de tiempo como query: sin eso, después de re-renderizar un
    clip el navegador seguiría mostrando el video viejo de su caché (la ruta no
    cambia). `translate_path` ignora la query, así que el server no se entera.
    """
    if not path:
        return ""
    p = Path(str(path))
    if not p.exists():
        return ""
    return f"{srv.url_for(p)}?v={int(p.stat().st_mtime)}"



# ── Encuadre manual por clip ──────────────────────────────────────────────────

# Momentos del clip que se previsualizan al encuadrar. Con uno solo no se ve si
# la persona se mueve y el recorte la pierde a mitad de camino.
_FRAMING_FRACTIONS = (0.25, 0.5, 0.75)


def _clip_frames_bgr(clip: dict) -> list:
    """Frames repartidos a lo largo del clip (BGR), cacheados por clip."""
    key = f"_frames_{clip['index']}"
    if key in st.session_state:
        return st.session_state[key]
    import cv2, tempfile, subprocess
    dur = clip.get("clip_duration") or (clip["end"] - clip["start"])
    imgs = []
    for frac in _FRAMING_FRACTIONS:
        t = max(0.0, float(dur) * frac)
        tmp = Path(tempfile.mktemp(suffix=".png"))
        subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", str(clip["clip_path"]),
             "-frames:v", "1", "-loglevel", "error", str(tmp)],
            capture_output=True,
        )
        if tmp.exists():
            img = cv2.imread(str(tmp))
            if img is not None:
                imgs.append(img)
            try:
                tmp.unlink()
            except OSError:
                pass
    st.session_state[key] = imgs
    return imgs


from modules.framing import crop_rect as _crop_rect, crop_from_rect as _crop_from_rect


def _fmt_aspect(fmt_key: str) -> float:
    p = config.FORMAT_PRESETS[fmt_key]
    return p["width"] / p["height"]


def _face_center_y(img) -> float:
    """Centro vertical (0–1) de la cara más grande (Haar) para el default vertical
    del recorte; 0.42 (headroom típico) si no se detecta cara."""
    try:
        import cv2
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        faces = cascade.detectMultiScale(
            gray, 1.1, 5, minSize=(int(w * 0.06), int(h * 0.06))
        )
        if len(faces):
            fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
            return min(0.9, max(0.1, (fy + fh / 2) / h))
    except Exception:
        pass
    return 0.42


def _rerun_here() -> None:
    """
    Rerun del bloque actual, sin recargar toda la página si estamos en un
    fragment (que es lo que hace saltar el scroll).
    """
    try:
        st.rerun(scope="fragment")
    except Exception:
        st.rerun()


_FRAMING_LABELS = ("arranque", "medio", "final")


def _framing_preview(frames: list, crop_fn, big: bool = False) -> None:
    """
    Muestra el recorte aplicado a varios momentos del clip.

    En modo `big` se muestra solo el del medio, a todo el ancho: los tres juntos
    sirven para ver si el encuadre aguanta, pero para afinarlo hace falta verlo
    grande.
    """
    import cv2
    if big:
        frame = frames[len(frames) // 2]
        st.image(cv2.cvtColor(crop_fn(frame), cv2.COLOR_BGR2RGB),
                 width="stretch", caption="medio")
        return
    cols = st.columns(len(frames))
    for i, (col, frame) in enumerate(zip(cols, frames)):
        with col:
            st.image(
                cv2.cvtColor(crop_fn(frame), cv2.COLOR_BGR2RGB),
                width="stretch",
                caption=_FRAMING_LABELS[i] if i < len(_FRAMING_LABELS) else "",
            )


def framing_controls(clip: dict) -> None:
    """Controles de encuadre manual para un clip (9:16, 1:1 o split)."""
    import cv2
    fmt = normalize_format(clip.get("formato"))
    idx = clip["index"]

    if not config.crops(fmt):
        st.caption(f"**{_FORMAT_LABELS[fmt]}** muestra el plano completo — "
                   "no hay recorte que ajustar.")
        return

    frames = _clip_frames_bgr(clip)
    if not frames:
        st.caption("⚠️ No se pudo extraer un frame para el preview.")
        return
    img = frames[len(frames) // 2]          # el del medio manda para los defaults
    src_h, src_w = img.shape[:2]

    manual = st.toggle(
        "🎯 Elegir encuadre a mano",
        value=clip.get("crop_manual", False),
        key=f"cropman_{idx}",
        help="Por defecto el recorte es automático (sigue al que habla). "
             "Activalo para elegir a quién recortar y qué tan cerrado.",
    )
    clip["crop_manual"] = manual
    if not manual:
        # Sin encuadre manual hay dos decisiones, independientes entre sí: si la
        # cámara sigue al hablante y si el recorte sigue la toma. Con encuadre
        # manual no se ofrecen: sería contradictorio (y en el render gana el
        # manual, que es la decisión explícita del usuario).
        if config.FORMAT_PRESETS[fmt].get("auto_layout"):
            sfollow = st.checkbox(
                "🎥 Seguir al hablante (la cámara se mueve dentro del clip)",
                value=speaker_follow(clip),
                key=f"spkfollow_{idx}",
                help="Encendido, el recorte se desplaza para acompañar a quien "
                     "habla. Apagado, queda fijo en la posición media de la cara: "
                     "un plano quieto en vez de una cámara que panea.",
            )
            if sfollow != speaker_follow(clip):
                clip["speaker_follow"] = sfollow
        follow = st.checkbox(
            "🔀 Seguir la toma (cambiar el recorte cuando cambia el plano)",
            value=bool(clip.get("follow_shot")),
            key=f"followf_{idx}",
            help="Split mientras están los dos en cuadro y recorte cerrado cuando "
                 "la cámara va a uno solo, dentro del mismo clip. Se combina con "
                 "el seguimiento del hablante: no lo reemplaza.",
        )
        clip["follow_shot"] = follow
        return

    # Default vertical basado en la cara detectada (headroom), cacheado.
    if "crop_cy_default" not in clip:
        clip["crop_cy_default"] = _face_center_y(img)
    cy_def = clip["crop_cy_default"]

    big = st.checkbox(
        "🔍 Ver el preview grande", key=f"cropbig_{idx}",
        help="Muestra solo el momento del medio, a todo el ancho.",
    )

    # Preview a la IZQUIERDA, controles a la DERECHA. Se previsualiza en varios
    # momentos del clip: con uno solo no se ve si la persona se corre y el
    # recorte la pierde a la mitad.
    col_prev, col_ctrl = st.columns([2, 1.2])

    if fmt == "split":
        preset = config.FORMAT_PRESETS[fmt]
        half_aspect = preset["width"] / (preset["height"] / 2)
        with col_ctrl:
            st.markdown("**Arriba**")
            top = st.slider("Posición ← →", 0.0, 1.0, float(clip.get("crop_top", 0.7)),
                            0.01, key=f"croptop_{idx}", help="0 = izquierda · 1 = derecha")
            vyt = st.slider("Vertical ↑↓", 0.0, 1.0, float(clip.get("crop_cy_top", cy_def)),
                            0.01, key=f"cyt_{idx}", help="0 = arriba · 1 = abajo (afecta al hacer zoom)")
            zt  = st.slider("Zoom (cerrar)", 1.0, 3.0, float(clip.get("zoom_top", 1.0)),
                            0.05, key=f"zoomtop_{idx}")
            st.markdown("**Abajo**")
            bot = st.slider("Posición ← →", 0.0, 1.0, float(clip.get("crop_bottom", 0.3)),
                            0.01, key=f"cropbot_{idx}", help="0 = izquierda · 1 = derecha")
            vyb = st.slider("Vertical ↑↓", 0.0, 1.0, float(clip.get("crop_cy_bottom", cy_def)),
                            0.01, key=f"cyb_{idx}", help="0 = arriba · 1 = abajo (afecta al hacer zoom)")
            zb  = st.slider("Zoom (cerrar)", 1.0, 3.0, float(clip.get("zoom_bottom", 1.0)),
                            0.05, key=f"zoombot_{idx}")
            if st.button("↕ Intercambiar arriba/abajo", key=f"swap_{idx}"):
                clip["crop_top"], clip["crop_bottom"] = bot, top
                clip["zoom_top"], clip["zoom_bottom"] = zb, zt
                clip["crop_cy_top"], clip["crop_cy_bottom"] = vyb, vyt
                for k in (f"croptop_{idx}", f"cropbot_{idx}", f"zoomtop_{idx}",
                          f"zoombot_{idx}", f"cyt_{idx}", f"cyb_{idx}"):
                    st.session_state.pop(k, None)
                _rerun_here()
        clip["crop_top"], clip["crop_bottom"] = top, bot
        clip["zoom_top"], clip["zoom_bottom"] = zt, zb
        clip["crop_cy_top"], clip["crop_cy_bottom"] = vyt, vyb
        rt = _crop_rect(src_w, src_h, half_aspect, top, zt, center_y=vyt)
        rb = _crop_rect(src_w, src_h, half_aspect, bot, zb, center_y=vyb)
        # Los rects llevan metido el aspecto del formato: hay que recordar cuál,
        # para no reusarlos si después se cambia de formato.
        clip["crop_rect_top"], clip["crop_rect_bottom"] = rt, rb
        clip["crop_fmt"] = fmt

        def _stacked(frame, _rt=rt, _rb=rb):
            ct, cb = _crop_from_rect(frame, _rt), _crop_from_rect(frame, _rb)
            wmin = min(ct.shape[1], cb.shape[1])
            ct = cv2.resize(ct, (wmin, max(1, int(ct.shape[0] * wmin / ct.shape[1]))))
            cb = cv2.resize(cb, (wmin, max(1, int(cb.shape[0] * wmin / cb.shape[1]))))
            return cv2.vconcat([ct, cb])

        with col_prev:
            _framing_preview(frames, _stacked, big=big)
    else:
        with col_ctrl:
            center = st.slider("Posición ← →", 0.0, 1.0, float(clip.get("crop_center", 0.5)),
                               0.01, key=f"cropc_{idx}", help="0 = izquierda · 1 = derecha")
            vy = st.slider("Vertical ↑↓", 0.0, 1.0, float(clip.get("crop_cy", cy_def)),
                           0.01, key=f"cropcy_{idx}", help="0 = arriba · 1 = abajo (afecta al hacer zoom)")
            z = st.slider("Zoom (cerrar)", 1.0, 3.0, float(clip.get("zoom", 1.0)),
                          0.05, key=f"zoom_{idx}")
        clip["crop_center"], clip["crop_cy"], clip["zoom"] = center, vy, z
        rect = _crop_rect(src_w, src_h, _fmt_aspect(fmt), center, z, center_y=vy)
        clip["crop_rect"] = rect
        clip["crop_fmt"] = fmt
        with col_prev:
            _framing_preview(frames, lambda frame: _crop_from_rect(frame, rect), big=big)


@st.fragment

@st.fragment
def clip_framing_fragment(clip: dict) -> None:
    """Encuadre de un clip ya renderizado (Paso 5), aislado del resto de la página."""
    if st.checkbox("🎯 Ver y ajustar el encuadre", key=f"p5frame_{clip['index']}"):
        framing_controls(clip)
        save_state()


# ── Editor de timeline (componente custom) ────────────────────────────────────
_EDITOR_TYPES = ["insight", "advice", "humor", "stat", "story"]


def get_media_server():
    """Server HTTP de sesión (con Range, puerto efímero) que sirve downloads/ al iframe."""
    srv = st.session_state.get("_media_server")
    if srv is None:
        srv = MediaServer(config.DOWNLOADS_DIR)  # puerto efímero
        srv.start()
        st.session_state["_media_server"] = srv
    return srv


def get_peaks(info: dict):
    """
    Forma de onda del video (None si no se pudo calcular). Cacheada en memoria
    (sesión) y en disco (<video>.peaks.json) para no recomputar cada vez.
    """
    key = f"_peaks_{info.get('video_id', '')}"
    if key in st.session_state:
        return st.session_state[key]

    vp = Path(info["video_path"])
    cache_file = vp.with_suffix(vp.suffix + ".peaks.json")
    if cache_file.exists():
        try:
            peaks = json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            peaks = None
    else:
        try:
            peaks = compute_peaks(vp)
        except Exception:
            peaks = None
        if peaks is not None:
            try:
                cache_file.write_text(json.dumps(peaks), encoding="utf-8")
            except Exception:
                pass

    st.session_state[key] = peaks
    return peaks


def clips_to_editor_seed(clips: list) -> list:
    """Convierte los clips actuales al formato de semilla del editor."""
    return [{
        "start": float(c["start"]),
        "end":   float(c["end"]),
        "title": c.get("title", ""),
        "type":  c.get("type", "insight"),
    } for c in clips]


def build_display_cues(cues: list, block_seconds: float = 6.0) -> list:
    """
    Agrupa los cues en bloques ~frase para mostrar un transcript limpio en el editor
    (los auto-subs de YouTube son 'rolling' y repiten palabras; los fusionamos).
    Devuelve [{start, end, text}, ...].
    """
    if not cues:
        return []
    from modules.analyzer import _merge_rolling_texts
    blocks = []
    cur, start = [], float(cues[0]["start"])
    for c in cues:
        if float(c["start"]) >= start + block_seconds and cur:
            text = _merge_rolling_texts([x.get("text", "") for x in cur])
            if text:
                blocks.append({"start": start, "end": float(cur[-1]["end"]), "text": text})
            cur, start = [], float(c["start"])
        cur.append(c)
    if cur:
        text = _merge_rolling_texts([x.get("text", "") for x in cur])
        if text:
            blocks.append({"start": start, "end": float(cur[-1]["end"]), "text": text})
    return blocks


def editor_to_clips(items: list) -> list:
    """Convierte la salida del editor a clips del pipeline."""
    out = []
    for n, it in enumerate(items, 1):
        out.append({
            "start":  float(it["start"]),
            "end":    float(it["end"]),
            "title":  (it.get("title") or "").strip() or f"Corte {n}",
            "type":   it.get("type") or "insight",
            "reason": "Corte manual (timeline)",
            "topic":  "",
            "_selected": True,
        })
    return out


def build_csv(clips: list, video_info: dict) -> str:
    output = io.StringIO()
    fields = [
        "video_id", "video_title", "clip_index", "clip_title",
        "start", "end", "duration", "type", "reason",
        "serie", "parte",
        "output_path", "cover_path",
        "caption_tiktok", "caption_instagram", "caption_youtube",
    ]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for clip in clips:
        caps = clip.get("captions", {})
        total = clip.get("part_total", 0)
        if total and total > 1:
            serie, parte = clip.get("topic", ""), f"{clip.get('part', '')}/{total}"
        else:
            serie, parte = "", ""
        writer.writerow({
            "video_id":          video_info["video_id"],
            "video_title":       video_info["title"],
            "clip_index":        clip.get("index", ""),
            "clip_title":        clip.get("title", ""),
            "start":             clip.get("start", ""),
            "end":               clip.get("end", ""),
            "duration":          f"{clip.get('end',0) - clip.get('start',0):.1f}",
            "type":              clip.get("type", ""),
            "reason":            clip.get("reason", ""),
            "serie":             serie,
            "parte":             parte,
            "output_path":       str(clip.get("output_path", clip.get("clip_path", ""))),
            "cover_path":        str(clip.get("cover_path") or ""),
            "caption_tiktok":    caps.get("tiktok", ""),
            "caption_instagram": caps.get("instagram", ""),
            "caption_youtube":   caps.get("youtube", ""),
        })
    return output.getvalue()


def build_channel_context() -> str:
    name  = st.session_state.ch_name.strip()
    desc  = st.session_state.ch_desc.strip()
    hosts = st.session_state.ch_hosts.strip()
    tone  = st.session_state.ch_tone.strip()
    hosts_block = "\n".join(
        f"- {h.strip()}" for h in hosts.splitlines() if h.strip()
    )
    ctx = f"{name} es {desc}\nEl tono es {tone}."
    if hosts_block:
        ctx += f"\n\nLos hosts son:\n{hosts_block}"
    return ctx


@st.cache_data(ttl=30, show_spinner=False)
def _list_ollama_models() -> list:
    """Lista los modelos descargados en Ollama (vacío si no responde)."""
    try:
        import requests
        r = requests.get(f"{config.OLLAMA_HOST.rstrip('/')}/api/tags", timeout=3)
        r.raise_for_status()
        return sorted(m["name"] for m in r.json().get("models", []))
    except Exception:
        return []


# ── Sidebar: configuración del canal ─────────────────────────────────────────

with st.sidebar:
    st.header("Canal")

    st.text_input(
        "Nombre del canal",
        key="ch_name",
        placeholder="Ej: Mi Canal de Cocina",
    )
    st.text_area(
        "Descripción / temática",
        key="ch_desc",
        height=90,
        placeholder="Canal de YouTube sobre... orientado a...",
    )
    st.text_area(
        "Hosts (uno por línea — Nombre: Rol)",
        key="ch_hosts",
        height=120,
        placeholder="Ana García: Conductora principal\nJuan López: Editor y co-host",
    )
    st.text_input(
        "Tono",
        key="ch_tone",
        placeholder="Ej: Educativo y cercano, con humor ocasional",
    )

    st.caption("Esta info guía al modelo al analizar el video y generar los captions.")

    # ── Motor de IA (proveedor + modelo) ──────────────────────────────────────
    if CONFIG_OK:
        st.divider()
        st.header("Motor de IA")

        _prov_labels = {"anthropic": "Anthropic (nube)", "ollama": "Ollama (local)"}
        _prov_keys   = list(_prov_labels.keys())
        _cur_prov    = config.LLM_PROVIDER if config.LLM_PROVIDER in _prov_keys else "anthropic"

        _sel_prov = st.radio(
            "Proveedor",
            options=_prov_keys,
            format_func=lambda k: _prov_labels[k],
            index=_prov_keys.index(_cur_prov),
            key="llm_provider_sel",
            help="Anthropic = mejor calidad (requiere API key). Ollama = local, gratis y privado.",
        )
        config.LLM_PROVIDER = _sel_prov

        if _sel_prov == "ollama":
            models = _list_ollama_models()
            if models:
                _idx = models.index(config.OLLAMA_MODEL) if config.OLLAMA_MODEL in models else 0
                config.OLLAMA_MODEL = st.selectbox(
                    "Modelo local", options=models, index=_idx, key="ollama_model_sel"
                )
            else:
                config.OLLAMA_MODEL = st.text_input(
                    "Modelo local (Ollama no responde — escribí el nombre)",
                    value=config.OLLAMA_MODEL, key="ollama_model_txt",
                )
                st.caption("¿Está corriendo `ollama serve`? Bajá modelos con `ollama pull qwen2.5:14b`.")
            st.caption(f"🖥 Local · {config.OLLAMA_MODEL} — sin costo, más lento que la nube.")
        else:
            st.caption(f"☁ {config.CLAUDE_MODEL}")


# ── Layout principal ──────────────────────────────────────────────────────────

st.title("🎬 Fast Video Clipping")

if not CONFIG_OK:
    st.error(f"Falta configuración: {CONFIG_ERROR}")
    st.code("set ANTHROPIC_API_KEY=sk-ant-...")
    st.stop()

# Barra de progreso
STAGES = ["idle", "downloaded", "analyzed", "clipped", "captioned"]
LABELS = ["—", "1· Descargado", "2· Analizado", "3· Clips cortados", "4· Captions listos"]
# "editing" es un sub-modo (editor de timeline) que vive entre descargar y cortar;
# a efectos de la barra de progreso lo tratamos como "descargado".
stage_idx = STAGES.index(st.session_state.stage) if st.session_state.stage in STAGES else 1
st.progress(
    stage_idx / (len(STAGES) - 1),
    text=LABELS[stage_idx] if stage_idx > 0 else "Pegá una URL o elegí un archivo local para empezar",
)
st.divider()


# ══════════════════════════════════════════════════════════════════════════════
# PASO 1 — Fuente + Carga
# ══════════════════════════════════════════════════════════════════════════════

if st.session_state.stage == "idle":
    # Nota: no usamos key="source_mode" porque Streamlit purga las claves
    # ligadas a un widget cuando éste no se dibuja (al avanzar de stage),
    # y más abajo leemos source_mode incondicionalmente. Guardamos el valor
    # en una clave plana que nunca se recolecta.
    st.session_state.source_mode = st.radio(
        "Fuente",
        options=["youtube", "local"],
        format_func=lambda x: "▶ YouTube URL" if x == "youtube" else "📂 Archivo local",
        index=0 if st.session_state.source_mode == "youtube" else 1,
        horizontal=True,
        label_visibility="collapsed",
    )

_is_youtube = st.session_state.source_mode == "youtube"

col_input, col_btn, col_rst = st.columns([5, 1.5, 1])

with col_input:
    _placeholder = (
        "https://youtube.com/watch?v=..."
        if _is_youtube else
        r"C:\Videos\mi_video.mp4"
    )
    _input_val = st.text_input(
        "Entrada",
        placeholder=_placeholder,
        disabled=st.session_state.stage != "idle",
        label_visibility="collapsed",
    )

with col_btn:
    if st.session_state.stage == "idle":
        _btn_label = "▶ Descargar" if _is_youtube else "📂 Cargar"
        if st.button(_btn_label, type="primary", use_container_width=True):
            _val = _input_val.strip().strip('"').strip("'")
            if not _val:
                st.warning("Ingresá una URL o ruta de video.")
            elif _is_youtube:
                with st.status("Descargando…", expanded=True) as s:
                    log_box = st.empty()
                    try:
                        info = download_video(
                            _val,
                            config.DOWNLOADS_DIR,
                            progress_fn=make_live_logger(log_box),
                        )
                        cues = parse_vtt(info["vtt_path"]) if info["vtt_path"] else []
                        # Fallback automático a Whisper si el VTT falta o es escaso
                        cues, info["vtt_path"] = whisper_fallback(
                            info, cues, progress_fn=make_live_logger(log_box)
                        )
                        log_box.empty()
                        st.session_state.video_info = info
                        st.session_state.cues       = cues
                        st.session_state.stage      = "downloaded"
                        save_state()
                        s.update(label=f"✅ {info['title']}", state="complete")
                        st.rerun()
                    except Exception as e:
                        log_box.empty()
                        s.update(label="❌ Error al descargar", state="error")
                        st.session_state["_last_error"] = str(e)
            else:
                with st.status("Cargando video…", expanded=True) as s:
                    log_box = st.empty()
                    try:
                        info = load_local_video(
                            _val,
                            config.DOWNLOADS_DIR,
                            progress_fn=make_live_logger(log_box),
                        )
                        cues = parse_vtt(info["vtt_path"]) if info["vtt_path"] else []
                        # Fallback automático a Whisper si el VTT falta o es escaso
                        cues, info["vtt_path"] = whisper_fallback(
                            info, cues, progress_fn=make_live_logger(log_box)
                        )
                        log_box.empty()
                        st.session_state.video_info = info
                        st.session_state.cues       = cues
                        st.session_state.stage      = "downloaded"
                        save_state()
                        s.update(label=f"✅ {info['title']}", state="complete")
                        st.rerun()
                    except Exception as e:
                        log_box.empty()
                        s.update(label="❌ Error al cargar", state="error")
                        st.session_state["_last_error"] = str(e)

if st.session_state.get("_last_error"):
    st.error(st.session_state.pop("_last_error"))

with col_rst:
    if st.session_state.stage != "idle":
        if st.button("↺ Reset", use_container_width=True):
            reset()
            st.rerun()

# Info del video (una vez descargado)
if st.session_state.video_info:
    info = st.session_state.video_info
    m, s = divmod(info["duration"], 60)
    c1, c2, c3 = st.columns([4, 1, 1])
    with c1:
        st.markdown(f"**{info['title']}**")
    with c2:
        st.metric("Duración", f"{m}:{s:02d}")
    with c3:
        n = len(st.session_state.cues)
        st.metric("Cues VTT", n if n else "Sin VTT")

st.divider()


# ══════════════════════════════════════════════════════════════════════════════
# PASO 2 — Análisis Claude
# ══════════════════════════════════════════════════════════════════════════════

if st.session_state.stage == "downloaded":
    if st.button("← Volver a descargar", key="back_to_idle"):
        reset()
        st.rerun()

    _dur     = st.session_state.video_info.get("duration", 0) or 0
    _cov     = transcript_coverage(st.session_state.cues, _dur)
    _no_cues = not st.session_state.cues
    _sparse  = _no_cues or (_dur > 0 and _cov < MIN_TRANSCRIPT_COVERAGE)

    if _sparse:
        if not WHISPER_AVAILABLE:
            _msg = (
                "⚠️ No hay transcript VTT y **faster-whisper no está instalado**."
                if _no_cues else
                f"⚠️ El transcript cubre solo ~{_cov:.0%} del video y **faster-whisper no está instalado** para mejorarlo."
            )
            st.error(_msg + " Instalalo con `pip install faster-whisper`.")
        else:
            # El fallback automático ya corrió al descargar; este botón permite
            # re-transcribir manualmente (p. ej. con un modelo más grande).
            if _no_cues:
                st.info("Sin subtítulos VTT. Transcribí el audio con Whisper para que Claude pueda analizar el video.")
            else:
                st.warning(
                    f"⚠️ El transcript es escaso (cubre ~{_cov:.0%} del video). "
                    "Podés re-transcribir con Whisper para mejorar el análisis."
                )
            _col_model, _col_wbtn = st.columns([2, 1])
            with _col_model:
                _whisper_model = st.selectbox(
                    "Modelo Whisper",
                    options=["tiny", "base", "small", "medium", "large-v2"],
                    index=2,
                    help="tiny/base = rápido pero menos preciso · small = buen equilibrio · medium/large = mejor calidad, más lento",
                    label_visibility="collapsed",
                )
            with _col_wbtn:
                _btn_label = "🎙️ Transcribir" if _no_cues else "🎙️ Re-transcribir"
                if st.button(_btn_label, type="primary", use_container_width=True):
                    with st.status("Transcribiendo audio…", expanded=True) as _ws:
                        _wlog = st.empty()
                        try:
                            _vtt = transcribe_video(
                                st.session_state.video_info["video_path"],
                                progress_fn=make_live_logger(_wlog),
                                model_size=_whisper_model,
                            )
                            _cues = parse_vtt(_vtt)
                            _wlog.empty()
                            st.session_state.video_info["vtt_path"] = _vtt
                            st.session_state.cues = _cues
                            save_state()
                            _ws.update(label=f"✅ {len(_cues)} cues generados", state="complete")
                            st.rerun()
                        except Exception as _e:
                            _wlog.empty()
                            _ws.update(label="❌ Error al transcribir", state="error")
                            st.session_state["_last_error"] = str(_e)
    elif st.session_state.cues:
        st.caption(f"📝 Transcript: {len(st.session_state.cues)} cues · cobertura ~{_cov:.0%} del video")

    col_n, col_dur = st.columns(2)
    with col_n:
        target_clips = st.number_input(
            "Cantidad de clips a identificar",
            min_value=1, max_value=30,
            value=config.TARGET_CLIPS,
            help="Claude va a buscar exactamente esta cantidad de momentos destacados.",
        )
    with col_dur:
        dur_range = st.slider(
            "Duración de cada clip (segundos)",
            min_value=10, max_value=180,
            value=(config.MIN_CLIP_SECONDS, config.MAX_CLIP_SECONDS),
            step=5,
            help="Rango de duración aceptado para cada clip.",
        )

    if st.button("🤖 AI Analyzer", type="primary"):
        with st.status("Analizando transcript…", expanded=True) as s:
            st.write(f"Enviando {len(st.session_state.cues)} cues a {llm.active_model_label()}… (puede tardar ~20 segundos)")
            try:
                clips = identify_clips(
                    st.session_state.cues,
                    st.session_state.video_info["title"],
                    target_clips=int(target_clips),
                    min_seconds=dur_range[0],
                    max_seconds=dur_range[1],
                    channel_context=build_channel_context(),
                )
                st.session_state.clips          = clips
                st.session_state.stage          = "analyzed"
                st.session_state.last_dur_range = (dur_range[0], dur_range[1])
                save_state()
                s.update(label=f"✅ {len(clips)} clips identificados", state="complete")
                st.rerun()
            except Exception as e:
                s.update(label="❌ Error en análisis", state="error")
                st.error(f"Error en análisis: {e}")
                with st.expander("Detalle técnico"):
                    st.code(traceback.format_exc())

    st.divider()
    st.caption("¿Preferís marcar los cortes a mano? Abrí el editor de timeline "
               "(no depende de Claude).")
    if st.button("✂️ Editar en timeline (manual)", key="go_editor_from_dl"):
        st.session_state.stage = "editing"
        save_state()
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PASO 2b — Editor de timeline (manual, Claude-opcional)
# ══════════════════════════════════════════════════════════════════════════════

if st.session_state.stage == "editing":
    info = st.session_state.video_info
    if not info:
        st.error("No hay video cargado.")
        st.stop()

    col_t, col_b = st.columns([5, 1])
    col_t.subheader("✂️ Editor de timeline")
    if col_b.button("← Volver", key="editor_back", use_container_width=True):
        st.session_state.stage = "downloaded"
        st.session_state.pop("editor_result", None)
        save_state()
        st.rerun()

    st.caption(
        "Arrastrá sobre la onda o **seleccioná texto del transcript** para crear "
        "cortes. Ajustá los bordes (se pegan a los límites de frase), ponéle título "
        "y tipo, y tocá **Aplicar**. Atajos: espacio = play · I/O = marcar in/out."
    )

    server = get_media_server()

    # Proxy 480p para editar fluido (una sola vez); el corte usa el ORIGINAL.
    proxy_key = f"_proxy_{info.get('video_id','')}"
    if proxy_key not in st.session_state:
        with st.spinner("Preparando video para edición (proxy 480p, una sola vez)…"):
            st.session_state[proxy_key] = str(ensure_proxy(info["video_path"]))
    video_url = server.url_for(Path(st.session_state[proxy_key]))

    with st.spinner("Preparando la forma de onda…"):
        peaks = get_peaks(info)
    if peaks is None:
        st.caption("⚠️ No se pudo precomputar la onda (¿el video tiene audio?). "
                   "El editor igual funciona con el video.")

    # Transcript en bloques ~frase para edición basada en contenido (snap a frases,
    # clic para saltar, seleccionar texto para crear cortes).
    cues = build_display_cues(st.session_state.cues)

    seed = clips_to_editor_seed(st.session_state.clips)
    result = clip_editor(
        video_url=video_url,
        duration=float(info.get("duration", 0) or 0),
        clips=seed,
        peaks=peaks,
        cues=cues,
        types=_EDITOR_TYPES,
        storage_key=str(info.get("video_id", "")),
        key=f"clip_editor_{info.get('video_id','')}",
    )
    if result is not None:
        st.session_state["editor_result"] = result

    res = st.session_state.get("editor_result")
    if res:
        st.success(f"✅ {len(res)} corte(s) definidos.")
        if st.button("➡️ Continuar a formato y corte", type="primary", key="editor_continue"):
            st.session_state.clips          = editor_to_clips(res)
            st.session_state.stage          = "analyzed"
            st.session_state.last_dur_range = st.session_state.get(
                "last_dur_range", (config.MIN_CLIP_SECONDS, config.MAX_CLIP_SECONDS)
            )
            st.session_state.pop("editor_result", None)
            save_state()
            st.rerun()
    else:
        st.info("Definí al menos un corte y tocá **✓ Aplicar** dentro del editor.")


# ══════════════════════════════════════════════════════════════════════════════
# PASO 3 — Editar clips y cortar
# ══════════════════════════════════════════════════════════════════════════════

if st.session_state.stage == "analyzed":
    total_clips = len(st.session_state.clips)
    col_title, col_back = st.columns([5, 1])
    col_title.subheader(f"📋 {total_clips} clips identificados")
    if col_back.button("← Re-analizar", key="back_to_downloaded", use_container_width=True):
        go_back()
        st.rerun()

    st.caption("Elegí qué clips cortar y en qué formato.")

    _info = st.session_state.video_info

    # Análisis de la toma de cada tramo. Está cacheado en sesión y en disco
    # (clips/_previews/<tramo>/faces.json), así que el costo es solo la primera vez.
    _analyses = {}
    if _info:
        with st.spinner("Analizando la toma de cada tramo (la primera vez tarda un poco)…"):
            for _pos, _clip in enumerate(st.session_state.clips):
                _analyses[_pos] = segment_analysis(_clip, _info)

    _result = clip_gallery(
        clips=clips_to_gallery(
            st.session_state.clips, _analyses, get_preview_server().url_for
        ),
        formats=gallery_formats(),
        types=_EDITOR_TYPES,
        video_url=segment_video_url(_info) if _info else "",
        source_aspect=source_aspect(_info) if _info else 16 / 9,
        key=f"gallery_{_info.get('video_id', '') if _info else 'none'}",
    )

    if _result:
        if apply_gallery(_result.get("clips"), st.session_state.clips):
            save_state()
        # La acción viaja con la última tanda de datos, y Streamlit devuelve ese
        # mismo valor en cada rerun: sin el nonce, "Timeline" se dispararía solo
        # cada vez que la página se vuelve a dibujar.
        if (_result.get("action") == "timeline"
                and _result.get("nonce") != st.session_state.get("_gallery_nonce")):
            st.session_state["_gallery_nonce"] = _result.get("nonce")
            st.session_state.stage = "editing"
            save_state()
            st.rerun()

    approved = [c for c in st.session_state.clips if c.get("_selected", True)]
    n_sel = len(approved)
    if not n_sel:
        st.warning("Seleccioná al menos un clip para continuar.")

    # ── Cómo cortar (ajustes guiados por el audio) ────────────────────────────
    col_snap, col_jump = st.columns(2)
    snap_to_audio = col_snap.checkbox(
        "🎧 Ajustar los bordes al audio", value=True, key="cut_snap",
        help="Los tiempos vienen del transcript de YouTube y traen 1–2 s de error. "
             "Esto pega el inicio y el fin a la pausa más cercana (hasta 1,5 s) "
             "para que el clip no arranque ni termine con media palabra.",
    )
    remove_silences = col_jump.checkbox(
        "✂️ Sacar silencios internos (jump cuts)", value=False, key="cut_jumpcuts",
        help="Elimina las pausas de más de 0,7 s dentro del clip y pega los "
             "trozos. Acelera el ritmo; en charlas pausadas puede sonar brusco.",
    )
    st.caption("El audio siempre se normaliza a -14 LUFS (el nivel que usan TikTok, "
               "Instagram y Shorts).")

    if st.button(
        "✂️ Cortar clips con ffmpeg", type="primary", disabled=len(approved) == 0
    ):
        with st.status("Cortando clips…", expanded=True) as s:
            log_box = st.empty()
            try:
                clipped = cut_clips(
                    st.session_state.video_info["video_path"],
                    approved,
                    config.CLIPS_DIR,
                    st.session_state.video_info["video_id"],
                    progress_fn=make_live_logger(log_box),
                    snap_to_audio=snap_to_audio,
                    remove_silences=remove_silences,
                )
                for clip in clipped:
                    clip["subtitles"] = get_cues_for_clip(
                        st.session_state.cues, clip["start"], clip["end"]
                    )
                log_box.empty()
                st.session_state.clipped = clipped
                st.session_state.stage   = "clipped"
                save_state()
                s.update(label=f"✅ {len(clipped)} clips cortados", state="complete")
                st.rerun()
            except Exception as e:
                log_box.empty()
                s.update(label="❌ Error al cortar", state="error")
                st.session_state["_last_error"] = str(e)


# ══════════════════════════════════════════════════════════════════════════════
# PASO 4 — Preview + Captions
# ══════════════════════════════════════════════════════════════════════════════

if st.session_state.stage == "clipped":
    clipped = st.session_state.clipped
    col_title, col_back = st.columns([5, 1])
    col_title.subheader(f"🎥 {len(clipped)} clips listos")
    if col_back.button("← Volver a selección", key="back_to_analyzed", use_container_width=True):
        go_back()
        st.rerun()

    st.caption(
        "Última mirada antes de renderizar: el marco sobre cada foto es lo que "
        "se queda el formato. Tocá una tarjeta para ajustarle el encuadre abajo."
    )

    _info4 = st.session_state.video_info

    # El análisis de la toma ya está cacheado desde el Paso 3 (mismo tramo).
    _an4 = {}
    if _info4:
        with st.spinner("Preparando las fotos de cada clip…"):
            for _pos, _clip in enumerate(clipped):
                _an4[_pos] = segment_analysis(_clip, _info4)

    _srv4 = get_preview_server()
    _res4 = clip_gallery(
        clips=clips_to_gallery(
            clipped, _an4, _srv4.url_for,
            # Acá el corte ya existe: la tarjeta reproduce el archivo real, que
            # es lo que se va a renderizar (con los jump cuts ya aplicados).
            clip_url=lambda c: _media_url(_srv4, c.get("clip_path")),
        ),
        formats=gallery_formats(),
        types=_EDITOR_TYPES,
        video_url=segment_video_url(_info4) if _info4 else "",
        source_aspect=source_aspect(_info4) if _info4 else 16 / 9,
        pickable=False,       # ya están cortados: no hay nada que tildar
        show_timeline=False,  # el timeline corta, y eso ya pasó
        key=f"gallery4_{_info4.get('video_id', '') if _info4 else 'none'}",
    )

    _foco4 = 0
    if _res4:
        if apply_gallery(_res4.get("clips"), clipped):
            save_state()
        try:
            _foco4 = int(_res4.get("selected") or 0)
        except (TypeError, ValueError):
            _foco4 = 0

    # El encuadre manual se queda en Streamlit: saca frames del clip en el
    # servidor y los dibuja, que es lo que el componente no puede hacer.
    if 0 <= _foco4 < len(clipped):
        _c4 = clipped[_foco4]
        if config.crops(normalize_format(_c4.get("formato"))):
            st.caption(
                f"**Clip {_c4.get('index', _foco4 + 1)}** — en **9:16** y **1:1** elegís a "
                "qué persona recortar cuando hay más de una; en **split**, quién va "
                "arriba y quién abajo. Sin encuadre manual el recorte sigue al hablante."
            )
            clip_framing_fragment(_c4)
        else:
            st.caption(
                f"**Clip {_c4.get('index', _foco4 + 1)}** — este formato muestra el plano "
                "entero: no hay nada que encuadrar."
            )

    # ── Buscar más clips ──────────────────────────────────────────────────────
    with st.expander("➕ Buscar más clips"):
        st.caption("Claude identificará clips nuevos en las partes del video aún no usadas.")
        extra_n = st.number_input(
            "Clips adicionales a identificar",
            min_value=1, max_value=20, value=5,
            key="extra_clips_n",
        )
        if st.button("🔍 Buscar más clips", key="btn_more_clips"):
            excluded = [(c["start"], c["end"]) for c in st.session_state.clipped]
            with st.status("Buscando más clips…", expanded=True) as s:
                st.write(f"Claude buscando {int(extra_n)} clips en las zonas no usadas…")
                try:
                    dr = st.session_state.last_dur_range
                    new_clips = identify_clips(
                        st.session_state.cues,
                        st.session_state.video_info["title"],
                        target_clips=int(extra_n),
                        min_seconds=dr[0],
                        max_seconds=dr[1],
                        channel_context=build_channel_context(),
                        excluded_ranges=excluded,
                    )
                    st.session_state.extra_clips_pending = new_clips
                    save_state()
                    s.update(label=f"✅ {len(new_clips)} clips encontrados — revisalos abajo", state="complete")
                    st.rerun()
                except Exception as e:
                    s.update(label="❌ Error al buscar clips", state="error")
                    st.session_state["_last_error"] = f"Error: {e}"

        if st.session_state.extra_clips_pending:
            pending = st.session_state.extra_clips_pending
            st.markdown(f"**{len(pending)} clips nuevos** — seleccioná cuáles cortar:")
            extra_df = st.data_editor(
                clips_to_df(pending),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "✓":       st.column_config.CheckboxColumn("Cortar", width="small"),
                    "Título":  st.column_config.TextColumn(width="large"),
                    "Formato": st.column_config.SelectboxColumn(
                        "Formato",
                        options=_FORMAT_OPTIONS,
                        width="medium",
                        required=True,
                    ),
                    "Inicio":  st.column_config.NumberColumn("Inicio (s)", format="%.1f", step=0.5),
                    "Fin":     st.column_config.NumberColumn("Fin (s)",    format="%.1f", step=0.5),
                    "Dur(s)":  st.column_config.NumberColumn("Duración", disabled=True),
                    "Tipo":    st.column_config.SelectboxColumn(
                        options=["insight", "advice", "humor", "stat", "story"]
                    ),
                    "Razón":   st.column_config.TextColumn(width="large"),
                },
                key="extra_clips_editor",
            )
            extra_approved = df_to_clips(extra_df, pending)

            col_cut, col_cancel = st.columns([2, 1])
            if col_cut.button(
                f"✂️ Cortar {len(extra_approved)} clips adicionales",
                type="primary",
                disabled=len(extra_approved) == 0,
                key="btn_cut_extra",
            ):
                with st.status("Cortando clips adicionales…", expanded=True) as s:
                    log_box = st.empty()
                    try:
                        next_idx = max((c["index"] for c in st.session_state.clipped), default=0) + 1
                        extra_clipped = cut_clips(
                            st.session_state.video_info["video_path"],
                            extra_approved,
                            config.CLIPS_DIR,
                            st.session_state.video_info["video_id"],
                            progress_fn=make_live_logger(log_box),
                            start_index=next_idx,
                            # Mismos ajustes de audio que eligió arriba para el lote principal.
                            snap_to_audio=st.session_state.get("cut_snap", True),
                            remove_silences=st.session_state.get("cut_jumpcuts", False),
                        )
                        for clip in extra_clipped:
                            clip["subtitles"] = get_cues_for_clip(
                                st.session_state.cues, clip["start"], clip["end"]
                            )
                        log_box.empty()
                        st.session_state.clipped += extra_clipped
                        st.session_state.extra_clips_pending = []
                        save_state()
                        s.update(label=f"✅ {len(extra_clipped)} clips cortados y agregados", state="complete")
                        st.rerun()
                    except Exception as e:
                        log_box.empty()
                        s.update(label="❌ Error al cortar", state="error")
                        st.session_state["_last_error"] = str(e)

            if col_cancel.button("✕ Descartar", key="btn_cancel_extra"):
                st.session_state.extra_clips_pending = []
                st.rerun()

    st.divider()

    # Resumen de formatos elegidos (todos se renderizan con Remotion).
    _fmt_counts: dict[str, int] = {}
    for c in clipped:
        k = normalize_format(c.get("formato"))
        _fmt_counts[k] = _fmt_counts.get(k, 0) + 1
    _resumen = " · ".join(
        f"{_FORMAT_BADGE.get(k, k)} ×{n}" for k, n in _fmt_counts.items()
    )
    st.info(f"🎬 Se renderizarán **{len(clipped)}** clips con Remotion: {_resumen}")

    if st.button("✍️ Generar captions con Claude", type="primary"):
        video_id = st.session_state.video_info["video_id"]
        out_dir  = config.OUTPUT_DIR / video_id

        with st.status(f"Renderizando {len(clipped)} clips…", expanded=True) as s:
            prog_bar  = st.progress(0.0)
            prog_text = st.empty()
            try:
                def _render_progress(done: int, total: int, title: str):
                    pct = done / total if total else 0
                    prog_bar.progress(pct)
                    if done < total:
                        prog_text.caption(f"🎬 Clip {done + 1} / {total} — *{title}*")
                    else:
                        prog_text.caption(f"✅ {total} clip{'s' if total != 1 else ''} renderizados")

                rendered = render_clips(
                    clipped, out_dir, video_id, progress_fn=_render_progress
                )
                rendered_by_idx = {c["index"]: c for c in rendered}
                clips_to_caption = [
                    rendered_by_idx.get(c["index"], c) for c in clipped
                ]
                s.update(label=f"✅ {len(rendered)} clips renderizados", state="complete")
            except Exception as e:
                s.update(label="❌ Error en Remotion", state="error")
                st.session_state["_last_error"] = f"Error en Remotion: {e}"
                st.stop()

        with st.status("Generando captions…", expanded=True) as s:
            try:
                n = len(clips_to_caption)
                st.write(f"Claude generando captions para {n} clip{'s' if n>1 else ''}…")
                final = generate_all_captions(
                    clips_to_caption,
                    st.session_state.video_info["title"],
                    channel_context=build_channel_context(),
                )
                st.session_state.final_clips = final
                st.session_state.stage       = "captioned"
                save_state()
                s.update(label="✅ Captions generados", state="complete")
                st.rerun()
            except Exception as e:
                s.update(label="❌ Error al generar captions", state="error")
                st.session_state["_last_error"] = f"Error generando captions: {e}"


# ══════════════════════════════════════════════════════════════════════════════
# PASO 5 — Captions para publicar
# ══════════════════════════════════════════════════════════════════════════════

if st.session_state.stage == "captioned":
    final_clips = st.session_state.final_clips
    video_info  = st.session_state.video_info

    col_title, col_back = st.columns([5, 1])
    col_title.subheader("✅ Captions listos para publicar")
    if col_back.button("← Volver a clips", key="back_to_clipped", use_container_width=True):
        go_back()
        st.rerun()

    _pub = clip_publish(
        clips=clips_to_publish(final_clips, lambda p: _media_url(get_output_server(), p)),
        formats=gallery_formats(),
        platforms=PUBLISH_PLATFORMS,
        key=f"publish_{video_info['video_id']}",
    )

    _sel_pos = 0
    if _pub:
        if apply_publish(_pub.get("clips"), final_clips):
            save_state()
        try:
            _sel_pos = int(_pub.get("selected") or 0)
        except (TypeError, ValueError):
            _sel_pos = 0

        # Igual que en la galería: la acción viaja en el valor y Streamlit lo
        # devuelve en cada rerun, así que el nonce es lo que evita re-renderizar
        # en loop.
        _act = _pub.get("action") or {}
        if (_act.get("kind") == "rerender"
                and _pub.get("nonce") != st.session_state.get("_publish_nonce")):
            st.session_state["_publish_nonce"] = _pub.get("nonce")
            _pos = int(_act.get("id", -1))
            if 0 <= _pos < len(final_clips):
                _clip = final_clips[_pos]
                with st.status(f"Re-renderizando clip {_clip.get('index', _pos + 1)}…",
                               expanded=True) as _s:
                    try:
                        _out_dir = config.OUTPUT_DIR / video_info["video_id"]
                        _re = render_clips([_clip], _out_dir, video_info["video_id"])
                        if _re:
                            _clip.update(_re[0])  # nuevo output_path/cover_path
                            save_state()
                        _s.update(label="✅ Clip re-renderizado", state="complete")
                        st.rerun()
                    except Exception as _e:
                        _s.update(label="❌ Error al re-renderizar", state="error")
                        st.error(f"Re-render: {_e}")

    # El encuadre manual se queda en Streamlit: saca frames del clip en el
    # servidor y los dibuja, que es justo lo que el componente no puede hacer.
    if 0 <= _sel_pos < len(final_clips):
        _sel_clip = final_clips[_sel_pos]
        if config.crops(normalize_format(_sel_clip.get("formato"))):
            st.caption(f"Encuadre del clip {_sel_clip.get('index', _sel_pos + 1)} — "
                       "después de ajustarlo, tocá **Re-renderizar este clip**.")
            clip_framing_fragment(_sel_clip)

    st.divider()

    # CSV download
    csv_str  = build_csv(final_clips, video_info)
    vid_id   = video_info["video_id"]

    col_dl2, col_spacer = st.columns([1, 3])
    with col_dl2:
        st.download_button(
            label="⬇️ Descargar CSV",
            data=csv_str,
            file_name=f"zumo_{vid_id}_captions.csv",
            mime="text/csv",
            type="primary",
            use_container_width=True,
        )

    # ══════════════════════════════════════════════════════════════════════════
    # PASO 6 — Programar en Postiz
    # ══════════════════════════════════════════════════════════════════════════
    st.divider()
    st.subheader("📤 Paso 6 — Programar en Postiz")

    if not config.POSTIZ_API_KEY:
        st.info(
            "Configurá `POSTIZ_API_KEY` y `POSTIZ_API_URL` en el `.env` para "
            "programar las publicaciones desde acá."
        )
    else:
        _PLATS = list(PLATFORM_CAPTION_FIELD)  # tiktok, instagram, youtube

        c1, c2, c3 = st.columns([1.2, 1, 1])
        with c1:
            start_date = st.date_input(
                "Fecha del 1er post",
                value=(datetime.now() + timedelta(days=1)).date(),
                key="pz_date",
            )
        with c2:
            start_time = st.time_input("Hora", value=_time(9, 0), key="pz_time")
        with c3:
            interval_h = st.number_input(
                "Horas entre clips", min_value=0.0, value=24.0, step=1.0, key="pz_interval"
            )

        c4, c5 = st.columns([2, 1])
        with c4:
            sel_plats = st.multiselect(
                "Plataformas", _PLATS, default=_PLATS, key="pz_plats"
            )
        with c5:
            post_type = st.selectbox(
                "Modo", ["schedule", "draft", "now"], key="pz_type",
                help="schedule = programado · draft = borrador para revisar en Postiz · now = publicar ya",
            )

        start_dt = datetime.combine(start_date, start_time)

        if sel_plats:
            # Horarios base: escalonado desde el 1er post según el intervalo.
            auto_times = [
                start_dt + timedelta(hours=interval_h * i)
                for i in range(len(final_clips))
            ]

            manual = st.toggle(
                "Editar fecha/hora por post",
                key="pz_manual",
                help="Activalo para fijar el día y la hora de cada clip por separado "
                     "(así decidís cuántos posts por día). Los valores arrancan desde "
                     "la fecha/hora y el intervalo de arriba.",
            )

            # Identidad estable de cada clip (su video de salida es único). La usamos
            # para recordar cuáles ya se programaron y traerlos destildados.
            def _clip_key(c):
                return str(c.get("output_path") or c.get("clip_path") or c.get("title") or "")

            scheduled = st.session_state.setdefault("pz_scheduled", set())

            sched_df = pd.DataFrame({
                # Por defecto se marcan los que aún NO se programaron.
                "Programar": [_clip_key(c) not in scheduled for c in final_clips],
                "Estado":    ["✅ programado" if _clip_key(c) in scheduled else "—"
                              for c in final_clips],
                "Clip":      [c.get("title", "") for c in final_clips],
                "Cuándo":    auto_times,
                "Plataformas": [
                    ", ".join(
                        p for p in sel_plats
                        if (c.get("captions", {}).get(p) or "").strip()
                    )
                    for c in final_clips
                ],
            })

            # "Cuándo" editable solo en modo manual; el resto siempre de solo lectura.
            disabled_cols = ["Estado", "Clip", "Plataformas"] + ([] if manual else ["Cuándo"])
            edited = st.data_editor(
                sched_df,
                key="pz_sched_editor",
                use_container_width=True,
                hide_index=True,
                disabled=disabled_cols,
                column_config={
                    "Programar": st.column_config.CheckboxColumn(
                        "Programar",
                        help="Destildá los que ya programaste para no duplicarlos.",
                    ),
                    "Cuándo": st.column_config.DatetimeColumn(
                        "Cuándo", format="YYYY-MM-DD HH:mm", step=60, required=True
                    ),
                },
            )
            schedule_times = [pd.Timestamp(x).to_pydatetime() for x in edited["Cuándo"]]
            sel_mask       = list(edited["Programar"])

            n_sel = sum(bool(x) for x in sel_mask)
            if scheduled:
                cc1, cc2 = st.columns([3, 1])
                cc1.caption(f"☑️ {n_sel} marcados · ✅ {len(scheduled)} ya programados en esta sesión.")
                if cc2.button("↺ Reset marcas", key="pz_reset_sched",
                              help="Olvida qué se programó y vuelve a marcar todos."):
                    st.session_state["pz_scheduled"] = set()
                    st.session_state.pop("pz_sched_editor", None)
                    st.rerun()

            n_req = n_sel * 2
            if post_type != "draft" and n_req > 30:
                st.warning(
                    f"Son ~{n_req} requests y Postiz limita a 30/hora. "
                    "Programá por tandas o subí el intervalo."
                )

            def _run_postiz(items, post_type):
                """
                items: lista de (clip, when). Programa cada uno y devuelve
                (ok, failed) donde failed es [{clip, when, error}] para reintentar.
                """
                client   = PostizClient()
                channels = client.channel_map()
                usables  = [p for p in sel_plats if p in channels]
                faltan   = [p for p in sel_plats if p not in channels]
                if faltan:
                    st.write(f"⚠️ Sin canal conectado para: {faltan} (se omiten).")
                if not usables:
                    raise RuntimeError("Ninguna plataforma elegida tiene canal en Postiz.")

                prog = st.progress(0.0)
                ok = 0
                failed = []
                total = len(items)
                for i, (clip, when) in enumerate(items):
                    title = clip.get("title", f"clip {i+1}")
                    vid   = Path(str(clip.get("output_path", clip.get("clip_path", ""))))
                    try:
                        if not vid.exists():
                            raise FileNotFoundError(f"video no encontrado ({vid.name})")
                        media       = client.upload(vid)
                        cover_media = maybe_upload_cover(client, clip, usables)  # solo YouTube
                        posts       = build_posts_for_clip(clip, channels, media, usables, cover_media=cover_media)
                        if cover_media:
                            st.write(f"🖼️ {title}: portada adjuntada al Short de YouTube")
                        if not posts:
                            st.write(f"⚠️ {title}: sin captions para las plataformas elegidas.")
                            prog.progress((i + 1) / total)
                            continue
                        client.create_post(posts, to_utc_iso(when), post_type=post_type)
                        st.write(f"✅ {title} → {when:%Y-%m-%d %H:%M} ({len(posts)} canales)")
                        # Recordamos que este clip ya salió: la tabla lo destilda solo.
                        st.session_state["pz_scheduled"].add(_clip_key(clip))
                        ok += 1
                    except Exception as ce:
                        st.write(f"❌ {title}: {ce}")
                        failed.append({"clip": clip, "when": when, "error": str(ce)})
                    prog.progress((i + 1) / total)
                return ok, failed

            btn_label = f"📤 Programar {n_sel} en Postiz" if n_sel else "📤 Programar en Postiz"
            if st.button(btn_label, type="primary", disabled=not sel_plats or n_sel == 0):
                with st.status("Programando en Postiz…", expanded=True) as s:
                    try:
                        # Solo los clips tildados en la tabla.
                        items = [
                            (final_clips[i], schedule_times[i])
                            for i in range(len(final_clips)) if sel_mask[i]
                        ]
                        ok, failed = _run_postiz(items, post_type)
                        st.session_state["pz_failed"] = failed
                        # Refrescamos la tabla para reflejar lo recién programado.
                        st.session_state.pop("pz_sched_editor", None)
                        verbo = "publicados" if post_type == "now" else "programados"
                        s.update(
                            label=f"✅ {ok} {verbo}" + (f", {len(failed)} con error" if failed else ""),
                            state="complete" if not failed else "error",
                        )
                    except Exception as e:
                        s.update(label="❌ Error al programar en Postiz", state="error")
                        st.session_state["_last_error"] = f"Error Postiz: {e}"

            # Reintento de los posts que fallaron en el último intento. Muchos
            # fallos son cortes de red transitorios (ConnectionReset 10054): el
            # cliente ya reintenta por su cuenta, y desde acá podés reintentar los
            # que aun así quedaron afuera sin volver a tocar los que ya salieron.
            pz_failed = st.session_state.get("pz_failed") or []
            if pz_failed:
                st.warning(f"⚠️ {len(pz_failed)} post(s) quedaron con error:")
                for f in pz_failed:
                    st.write(f"• **{f['clip'].get('title', '')}** — {f['error']}")
                if st.button("🔁 Reintentar fallidos", key="pz_retry", disabled=not sel_plats):
                    with st.status("Reintentando…", expanded=True) as s:
                        try:
                            items = [(f["clip"], f["when"]) for f in pz_failed]
                            ok, failed = _run_postiz(items, post_type)
                            st.session_state["pz_failed"] = failed
                            st.session_state.pop("pz_sched_editor", None)
                            verbo = "publicados" if post_type == "now" else "programados"
                            s.update(
                                label=f"✅ {ok} {verbo}" + (f", {len(failed)} aún con error" if failed else ""),
                                state="complete" if not failed else "error",
                            )
                        except Exception as e:
                            s.update(label="❌ Error al reintentar en Postiz", state="error")
                            st.session_state["_last_error"] = f"Error Postiz: {e}"
