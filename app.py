#!/usr/bin/env python3
"""
Clip Studio — clips verticales a partir de un video largo
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
    page_title="Clip Studio",
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
    from modules.renderer    import (
        render_clips, speaker_follow, clip_aspect,
        preview_encuadre, overlay_preview,
    )
    from modules.caption_gen import generate_all_captions
    from modules.transcriber import transcribe_video
    from modules.peaks       import compute_peaks
    from modules.proxy       import ensure_proxy, proxy_path_for
    from modules.media_server import MediaServer
    from modules.segment_preview import analyze_segment
    from modules.library    import find_videos, label_for
    from modules.imaging    import imread
    from modules.overlays   import (
        normalize as normalize_overlays, parse_hosts, describe as describe_overlays,
        for_render as overlays_for_render, collision as overlays_collision,
    )
    from modules.settings   import (
        load_settings, save_settings, settings_exist,
        env_read, env_upsert, mask_key,
    )
    from modules.ui_state    import (
        normalize_format, gallery_formats,
        clips_to_gallery, apply_gallery,
        clips_to_publish, apply_publish,
        FORMAT_LABELS, LABEL_TO_KEY, FORMAT_OPTIONS, PUBLISH_PLATFORMS,
    )
    from components.clip_editor import clip_editor
    from components.clip_ui     import clip_gallery, clip_publish
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
    os.environ.get("CLIP_STUDIO_STATE_FILE") or os.environ.get("ZUMO_STATE_FILE") or (Path(__file__).parent / ".pipeline_state.json")
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
DEFAULTS = {
    "stage":           "idle",
    "source_mode":     "youtube",
    "video_info":      None,
    "cues":            [],
    "clips":           [],
    "clipped":         [],
    "final_clips":     [],
    # Vacíos a propósito: el canal lo carga cada usuario en la pantalla de
    # configuración y queda en settings.json. Traer uno puesto desde el código
    # significa que el modelo trabaja con el contexto de otro.
    "ch_name":         "",
    "ch_desc":         "",
    "ch_hosts":        "",
    "ch_tone":         "",
    "clips_editor_rev":    0,
    "last_dur_range":      (config.MIN_CLIP_SECONDS, config.MAX_CLIP_SECONDS),
    "extra_clips_pending": [],   # clips encontrados por "Buscar más", aún sin cortar
}
# Cargar estado persistido solo la primera vez en esta sesión
if "stage" not in st.session_state:
    for k, v in DEFAULTS.items():
        st.session_state[k] = v
    load_state()


# Dónde va a parar el estado al empezar de nuevo. Uno solo: el anterior se pisa.
_STATE_BACKUP = _STATE_FILE.with_suffix(_STATE_FILE.suffix + ".bak")


def reset():
    """
    Vuelve a cero. El estado anterior NO se borra: se guarda al lado.

    Antes hacía `unlink()`. Empezar de nuevo es un clic, y del otro lado hay un
    episodio entero de trabajo —qué clips, con qué títulos, formatos y textos—
    que no está en ningún otro lado. Renombrarlo cuesta lo mismo y deja una
    salida: `mv .pipeline_state.json.bak .pipeline_state.json`.
    """
    for k in list(DEFAULTS.keys()):
        st.session_state.pop(k, None)
    if _STATE_FILE.exists():
        try:
            _STATE_BACKUP.unlink(missing_ok=True)
            _STATE_FILE.rename(_STATE_BACKUP)
        except OSError:
            # Si no se puede renombrar (permisos, otro proceso), se deja estar:
            # es preferible un estado viejo a perderlo.
            pass


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



# ── Preview de las capas ──────────────────────────────────────────────────────
# Un frame del clip tal como va a salir, con las capas dibujadas. Es el mismo
# `remotion still` y la misma composición que el render final, así que lo que se
# ve acá es lo que va a salir.
#
# No se regenera solo al mover un control: el still tarda ~5 s y el encuadre
# ~11 s la primera vez. Va con botón, y si después tocás algo el preview queda
# marcado como viejo en vez de mentir.

_PREVIEW_DIR = config.CLIPS_DIR / "_overlay_preview"


def _encuadre_firma(clip: dict) -> str:
    """Lo que cambia el encuadre. No incluye las capas: son independientes."""
    partes = [str(clip.get("clip_path")), normalize_format(clip.get("formato")),
              str(speaker_follow(clip)), str(bool(clip.get("follow_shot")))]
    partes += [f"{k}={clip.get(k)}" for k in sorted(clip) if k.startswith("crop")]
    return "|".join(partes)


def _capas_firma(clip: dict) -> str:
    return json.dumps(clip.get("overlays") or {}, sort_keys=True, ensure_ascii=False)


def _preview_encuadre_cacheado(clip: dict) -> dict:
    """El encuadre, resuelto una vez por clip (y de nuevo si cambia el formato)."""
    key = f"_ovenc_{clip.get('index')}"
    firma = _encuadre_firma(clip)
    guardado = st.session_state.get(key)
    if guardado and guardado[0] == firma:
        return guardado[1]
    enc = preview_encuadre(clip)
    st.session_state[key] = (firma, enc)
    return enc


def overlay_preview_panel(clip: dict) -> None:
    """Botón de preview + las imágenes generadas."""
    capas = overlays_for_render(clip)
    if not capas:
        st.caption("Prendé una capa para poder previsualizarla.")
        return

    idx   = clip.get("index", 0)
    key   = f"_ovprev_{idx}"
    firma = _capas_firma(clip)
    guardado = st.session_state.get(key)
    viejo = bool(guardado) and guardado.get("firma") != firma

    col_btn, col_aviso = st.columns([1.3, 3])
    generar = col_btn.button(
        "👁 Ver cómo queda" if not guardado else "↻ Actualizar preview",
        key=f"ov_prev_btn_{idx}", use_container_width=True,
    )
    if viejo:
        col_aviso.caption("⚠️ Cambiaste algo: este preview es de antes.")
    elif not guardado:
        col_aviso.caption("Tarda unos segundos: renderiza un frame de verdad.")

    if generar:
        try:
            srv = get_preview_server()
            url = srv.url_for(Path(clip["clip_path"]))
            with st.spinner("Resolviendo el encuadre…"):
                enc = _preview_encuadre_cacheado(clip)
            imgs = []
            momentos = []
            if "hook" in capas:
                h = capas["hook"]
                momentos.append((h["start"] + h["dur"] / 2, "Gancho"))
            if "lower" in capas:
                l = capas["lower"]
                momentos.append((l["start"] + l["dur"] / 2, "Nombre"))
            if "intro" in capas:
                momentos.append((capas["intro"]["dur"] / 2, "Apertura"))
            if "outro" in capas:
                # La de cierre se ancla al final, así que su momento también.
                _dur_clip = clip.get("clip_duration") or (clip["end"] - clip["start"])
                momentos.append((_dur_clip - capas["outro"]["dur"] / 2, "Cierre"))
            with st.spinner(f"Renderizando {len(momentos)} frame(s)…"):
                for i, (seg, etiqueta) in enumerate(momentos):
                    destino = _PREVIEW_DIR / f"{idx}_{i}.jpg"
                    overlay_preview(clip, seg, destino, clip_url=url, enc=enc)
                    imgs.append((str(destino), f"{etiqueta} · segundo {seg:.1f}"))
            st.session_state[key] = {"firma": firma, "imgs": imgs}
            _rerun_here()
        except Exception as e:
            st.error(f"No se pudo generar el preview: {e}")

    guardado = st.session_state.get(key)
    if guardado and guardado.get("imgs"):
        # Cuatro columnas aunque haya dos imágenes: un 9:16 a todo el ancho de
        # media pantalla es una torre de mil pixeles de alto y hay que scrollear
        # para ver el pie.
        cols = st.columns(4)
        for col, (ruta, etiqueta) in zip(cols, guardado["imgs"]):
            if Path(ruta).exists():
                col.image(ruta, caption=etiqueta, width="stretch")


# ── Capas encima del clip (gancho y placa de nombre) ──────────────────────────
# Van como overlay: NO alargan el clip ni obligan a volver a cortar, solo
# afectan al render. Por eso los controles viven acá, en el paso previo al
# render, y no antes de cortar.

@st.fragment
def overlay_controls(clip: dict) -> None:
    """
    Gancho y placa de un clip. Es un fragment: tocar un control no vuelve a
    dibujar la galería entera de arriba.
    """
    capas   = normalize_overlays(clip.get("overlays"),
                                 clip.get("clip_duration") or (clip["end"] - clip["start"]))
    hook    = capas["hook"]
    lower   = capas["lower"]
    idx     = clip.get("index", 0)
    cambio  = False

    col_h, col_l = st.columns(2)

    with col_h:
        _on = st.checkbox("✨ Gancho", value=hook["on"], key=f"ov_hook_on_{idx}",
                          help="Una frase grande al arranque. Si la dejás vacía, "
                               "usa el título del clip.")
        if _on != hook["on"]:
            hook["on"] = _on; cambio = True
        if _on:
            _txt = st.text_input("Texto", value=hook["text"], key=f"ov_hook_txt_{idx}",
                                 placeholder=clip.get("title", ""))
            _est = st.selectbox(
                "Entrada", options=["pop", "slide", "type"],
                format_func=lambda k: {"pop": "Aparece de golpe",
                                       "slide": "Sube desde abajo",
                                       "type": "Se escribe sola"}[k],
                index=["pop", "slide", "type"].index(hook["style"]),
                key=f"ov_hook_est_{idx}",
            )
            _pos = st.radio(
                "Dónde", options=["top", "center", "bottom"],
                format_func=lambda k: {"top": "Arriba", "center": "Al medio",
                                       "bottom": "Abajo"}[k],
                index=["top", "center", "bottom"].index(hook["position"]),
                horizontal=True, key=f"ov_hook_pos_{idx}",
            )
            _t0, _dur = st.columns(2)
            _s = _t0.number_input("Desde (s)", 0.0, 60.0, float(hook["start"]), 0.1,
                                  key=f"ov_hook_s_{idx}")
            _d = _dur.number_input("Dura (s)", 0.3, 30.0, float(hook["dur"]), 0.1,
                                   key=f"ov_hook_d_{idx}")
            for clave, val in (("text", _txt), ("style", _est), ("position", _pos),
                               ("start", _s), ("dur", _d)):
                if hook[clave] != val:
                    hook[clave] = val; cambio = True

    with col_l:
        _on = st.checkbox("🪪 Placa de nombre", value=lower["on"], key=f"ov_low_on_{idx}",
                          help="Nombre y rol de quien habla, abajo a un costado.")
        if _on != lower["on"]:
            lower["on"] = _on; cambio = True
        if _on:
            # Los hosts ya están cargados en Ajustes: no hay por qué escribirlos
            # de nuevo. "Otro…" queda para un invitado.
            _hosts = parse_hosts(st.session_state.get("ch_hosts", ""))
            _OTRO  = "Otro…"
            _nombres = [h["name"] for h in _hosts] + [_OTRO]
            _idx_sel = _nombres.index(lower["name"]) if lower["name"] in _nombres else len(_nombres) - 1
            _quien = st.selectbox("Quién", options=_nombres, index=_idx_sel,
                                  key=f"ov_low_quien_{idx}")
            if _quien == _OTRO:
                _nom = st.text_input("Nombre", value=lower["name"], key=f"ov_low_nom_{idx}")
                _rol = st.text_input("Rol", value=lower["role"], key=f"ov_low_rol_{idx}")
            else:
                _nom = _quien
                _rol = next((h["role"] for h in _hosts if h["name"] == _quien), "")
                st.caption(_rol or "sin rol cargado")
            _lado = st.radio("Lado", options=["left", "right"],
                             format_func=lambda k: "Izquierda" if k == "left" else "Derecha",
                             index=["left", "right"].index(lower["side"]),
                             horizontal=True, key=f"ov_low_lado_{idx}")
            _t0, _dur = st.columns(2)
            _s = _t0.number_input("Desde (s)", 0.0, 60.0, float(lower["start"]), 0.1,
                                  key=f"ov_low_s_{idx}")
            _d = _dur.number_input("Dura (s)", 0.3, 30.0, float(lower["dur"]), 0.1,
                                   key=f"ov_low_d_{idx}")
            for clave, val in (("name", _nom), ("role", _rol), ("side", _lado),
                               ("start", _s), ("dur", _d)):
                if lower[clave] != val:
                    lower[clave] = val; cambio = True

    st.divider()
    col_i, col_o = st.columns(2)

    for col, clave, titulo_ui, ayuda, semilla in (
        (col_i, "intro", "🎬 Placa de apertura",
         "Un título sobre los primeros segundos. No tapa el video: lo oscurece.",
         st.session_state.get("ch_name", "")),
        (col_o, "outro", "🏁 Placa de cierre",
         "Lo mismo, anclado al final del clip.",
         ""),
    ):
        card = capas[clave]
        with col:
            _on = st.checkbox(titulo_ui, value=card["on"], key=f"ov_{clave}_on_{idx}",
                              help=ayuda)
            if _on != card["on"]:
                card["on"] = _on
                # Al prenderla por primera vez se propone el nombre del canal:
                # es lo que uno pone ahí el 90% de las veces.
                if _on and not card["title"] and semilla:
                    card["title"] = semilla
                cambio = True
            if _on:
                _tit = st.text_input("Título", value=card["title"],
                                     key=f"ov_{clave}_tit_{idx}")
                _sub = st.text_input("Bajada", value=card["subtitle"],
                                     key=f"ov_{clave}_sub_{idx}",
                                     placeholder="opcional")
                _c1, _c2 = st.columns(2)
                _d = _c1.number_input("Dura (s)", 0.3, 15.0, float(card["dur"]), 0.1,
                                      key=f"ov_{clave}_d_{idx}")
                _dim = _c2.slider("Oscurece el video", 0.0, 1.0, float(card["dim"]), 0.05,
                                  key=f"ov_{clave}_dim_{idx}",
                                  help="0 = se ve el video entero detrás · 1 = placa opaca")
                for k, v in (("title", _tit), ("subtitle", _sub), ("dur", _d), ("dim", _dim)):
                    if card[k] != v:
                        card[k] = v; cambio = True

    if cambio:
        clip["overlays"] = capas
        save_state()
        _rerun_here()

    choque = overlays_collision(clip)
    if choque:
        st.warning(choque)

    st.divider()
    overlay_preview_panel(clip)


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
    """
    Server HTTP de sesión para la carpeta de salida.

    Se cachea junto con la carpeta que está sirviendo: la de salida se puede
    cambiar en Ajustes sin reiniciar, y un server apuntando a la carpeta
    anterior devolvería 404 en todos los videos del Paso 5 sin decir por qué.
    """
    actual = str(config.OUTPUT_DIR)
    guardado = st.session_state.get("_output_server")
    if guardado and guardado[0] == actual:
        return guardado[1]
    if guardado:
        try:
            guardado[1].stop()
        except Exception:
            pass
    srv = MediaServer(config.OUTPUT_DIR)  # puerto efímero
    srv.start()
    st.session_state["_output_server"] = (actual, srv)
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
            img = imread(str(tmp))
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
            # La real: con jump cuts el archivo dura menos que end - start.
            "duration":          f"{clip.get('clip_duration') or (clip.get('end', 0) - clip.get('start', 0)):.1f}",
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
    # Sin datos cargados devuelve "", y quien llama cae a
    # config.DEFAULT_CHANNEL_CONTEXT. Armar "  es .\nEl tono es ." sería
    # mandarle ruido al modelo creyendo que le dimos contexto.
    if not (name or desc or tone or hosts_block):
        return ""
    partes = []
    if name or desc:
        partes.append(f"{name or 'El canal'} es {desc}".strip())
    if tone:
        partes.append(f"El tono es {tone}")
    ctx = ".\n".join(p.rstrip(".") for p in partes)
    if ctx:
        ctx += "."
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


# ── Identidad visual ──────────────────────────────────────────────────────────
# La paleta vive en .streamlit/config.toml, y desde ahí llega también a los
# componentes React (leen el tema del host). Acá va solo lo que el tema no
# alcanza a decir: densidad, tipografía y el encabezado.

ACCENT = "#FFD000"

st.markdown(
    """
    <style>
      /* Streamlit deja ~6rem de aire arriba; en una herramienta que se usa
         scrolleando, eso es media pantalla perdida en cada recarga. */
      .stMainBlockContainer { padding-top: 2.2rem; padding-bottom: 4rem; }

      /* Los títulos de sección venían con tamaño de landing page. */
      .stMainBlockContainer h3 { font-size: 1.15rem; letter-spacing: -.01em; }

      /* Botones: una sola altura en toda la app. Streamlit los deja crecer
         según el texto y las filas quedan desparejas. */
      .stButton button, .stDownloadButton button {
        min-height: 2.35rem; border-radius: 8px; font-weight: 500;
      }

      /* Encabezado propio. */
      .cs-head { display:flex; align-items:baseline; gap:.6rem; margin-bottom:1.1rem; }
      .cs-head b { font-size:1.45rem; font-weight:700; letter-spacing:-.02em; }
      .cs-head span { font-size:.82rem; opacity:.55; }
      .cs-head i { width:9px; height:9px; border-radius:2px; background:ACCENT_COLOR;
                     display:inline-block; transform:translateY(-2px); }

      /* Los pasos: dónde estás, sin gastar una pantalla en decirlo. */
      .cs-steps { display:flex; gap:0; margin:0 0 1.4rem; font-size:.78rem; }
      .cs-steps div { flex:1; padding:.42rem .6rem; border-top:2px solid rgba(255,255,255,.10);
                        color:rgba(255,255,255,.38); }
      .cs-steps div.done { border-top-color:rgba(255,255,255,.28); color:rgba(255,255,255,.55); }
      .cs-steps div.now  { border-top-color:ACCENT_COLOR; color:ACCENT_COLOR; font-weight:600; }
      .cs-steps b { display:block; font-weight:inherit; }
    </style>
    """.replace("ACCENT_COLOR", ACCENT),
    unsafe_allow_html=True,
)

_STEP_LABELS = ["Fuente", "Clips", "Corte", "Render", "Publicar"]
_STEP_OF_STAGE = {"idle": 0, "downloaded": 1, "editing": 1, "analyzed": 2,
                  "clipped": 3, "captioned": 4}


def header(stage: str) -> None:
    """Nombre de la app y en qué paso está, en dos líneas."""
    actual = _STEP_OF_STAGE.get(stage, 0)
    pasos = "".join(
        f'<div class="{"now" if i == actual else "done" if i < actual else ""}">'
        f"<b>{i + 1}. {label}</b></div>"
        for i, label in enumerate(_STEP_LABELS)
    )
    canal = st.session_state.get("ch_name") or "Sin canal configurado"
    st.markdown(
        f'<div class="cs-head"><i></i><b>Clip Studio</b><span>{canal}</span></div>'
        f'<div class="cs-steps">{pasos}</div>',
        unsafe_allow_html=True,
    )


# ── Pantalla de configuración ─────────────────────────────────────────────────
# Es lo primero que se ve la primera vez. Antes, sin ANTHROPIC_API_KEY la app no
# arrancaba: mostraba `set ANTHROPIC_API_KEY=...` y se detenía ahí. La key se
# pone acá y va al .env (que ya está en .gitignore), nunca a settings.json ni al
# estado del pipeline, que se copian y se comparten sin pensarlo.

_CH_FIELDS = {
    "ch_name":      "channel_name",
    "ch_desc":      "channel_desc",
    "ch_hosts":     "channel_hosts",
    "ch_tone":      "channel_tone",
    "material_dir": "material_dir",
    "output_dir":   "output_dir",
}


def load_user_settings() -> None:
    """Vuelca settings.json en la sesión. Lo guardado pisa a los defaults."""
    data = load_settings()
    for ss_key, file_key in _CH_FIELDS.items():
        if data.get(file_key):
            st.session_state[ss_key] = data[file_key]
    config.apply_settings(data)


def setup_screen() -> None:
    """Configuración del canal y del modelo. Dibuja y corta el script acá."""
    header(st.session_state.stage)

    primera_vez = not settings_exist()
    if primera_vez:
        st.subheader("Configurá tu canal")
        st.caption(
            "Se pregunta una sola vez. Esta información es la que recibe el "
            "modelo para elegir los clips y escribir los textos: cuanto más "
            "concreta, mejor salen."
        )
    else:
        st.subheader("Ajustes")

    # Los widgets NO se atan a ch_* directamente: Streamlit purga de session_state
    # las claves ligadas a un widget en cuanto ese widget deja de dibujarse, así
    # que al salir de Ajustes los datos del canal desaparecían — y con ellos el
    # contexto que recibe el modelo. Los campos usan claves propias y vuelcan
    # sobre las plantas al guardar. Es el mismo problema que el de `source_mode`.
    nombre = st.text_input(
        "Nombre del canal", value=st.session_state.get("ch_name", ""),
        key="setup_ch_name", placeholder="Ej: Café con Ideas",
    )
    desc = st.text_area(
        "¿De qué trata? ¿Para quién?", value=st.session_state.get("ch_desc", ""),
        key="setup_ch_desc", height=80, placeholder="Canal sobre… orientado a…",
    )
    hosts = st.text_area(
        "Quiénes aparecen (uno por línea — Nombre: Rol)",
        value=st.session_state.get("ch_hosts", ""),
        key="setup_ch_hosts", height=110,
        placeholder="Ana García: Conductora\nJuan López: Editor y co-host",
    )
    tono = st.text_input(
        "Tono", value=st.session_state.get("ch_tone", ""),
        key="setup_ch_tone",
        placeholder="Ej: Relajado pero profesional, con insights accionables",
    )

    material = st.text_input(
        "Carpeta donde están tus videos",
        value=st.session_state.get("material_dir") or config.MATERIAL_DIR,
        key="setup_material_dir",
        help="Desde acá se listan los archivos al elegir «Archivo local». "
             "Puede ser cualquier carpeta del disco.",
    )
    if material and not Path(material).is_dir():
        st.caption("⚠️ Esa carpeta no existe todavía.")
    else:
        st.caption(f"{len(find_videos(material))} videos encontrados.")

    salida = st.text_input(
        "Carpeta donde se guardan los clips terminados",
        value=st.session_state.get("output_dir") or str(config.OUTPUT_DIR),
        key="setup_output_dir",
        help="El video renderizado, su portada y el CSV. Puede ser otro disco: "
             "esto crece rápido.",
    )
    if salida and not Path(salida).is_dir():
        st.caption("Todavía no existe; se crea al renderizar el primer clip.")

    st.divider()
    st.markdown("**¿Con qué modelo trabajás?**")

    prov = st.radio(
        "Proveedor",
        options=["anthropic", "ollama"],
        format_func=lambda k: (
            "Claude — mejor calidad, se paga por uso"
            if k == "anthropic" else
            "Ollama — corre en esta máquina, gratis y privado, más lento"
        ),
        index=0 if config.LLM_PROVIDER != "ollama" else 1,
        key="setup_provider",
        label_visibility="collapsed",
    )

    key_nueva = ""
    if prov == "anthropic":
        guardada = env_read("ANTHROPIC_API_KEY")
        key_nueva = st.text_input(
            "API key de Anthropic",
            type="password",
            key="setup_api_key",
            placeholder=(
                f"Ya hay una guardada ({mask_key(guardada)}) — dejalo vacío para conservarla"
                if guardada else "sk-ant-…"
            ),
            help="Se guarda en el archivo .env de esta carpeta, que no se sube a git. "
                 "Se saca de console.anthropic.com.",
        )
        st.text_input("Modelo", key="setup_claude_model", value=config.CLAUDE_MODEL)
    else:
        modelos = _list_ollama_models()
        if modelos:
            st.selectbox(
                "Modelo local", options=modelos, key="setup_ollama_model",
                index=modelos.index(config.OLLAMA_MODEL) if config.OLLAMA_MODEL in modelos else 0,
            )
        else:
            st.text_input("Modelo local", key="setup_ollama_model", value=config.OLLAMA_MODEL)
            st.caption("Ollama no responde. ¿Está corriendo `ollama serve`? "
                       "Los modelos se bajan con `ollama pull qwen2.5:14b`.")

    st.divider()

    falta_key = (
        prov == "anthropic"
        and not key_nueva.strip()
        and not env_read("ANTHROPIC_API_KEY")
    )
    if falta_key:
        st.info("Sin la API key, Claude no puede analizar el video. "
                "También podés elegir Ollama y trabajar sin key.")

    col_ok, col_cancel, _ = st.columns([1.4, 1, 3])
    if col_ok.button("Guardar y empezar" if primera_vez else "Guardar",
                     type="primary", disabled=falta_key, use_container_width=True):
        if key_nueva.strip():
            # Al .env y solo al .env. Y a os.environ, para que valga ya mismo.
            env_upsert("ANTHROPIC_API_KEY", key_nueva.strip())
            os.environ["ANTHROPIC_API_KEY"] = key_nueva.strip()

        st.session_state.ch_name  = nombre
        st.session_state.material_dir = material
        st.session_state.output_dir   = salida
        st.session_state.ch_desc  = desc
        st.session_state.ch_hosts = hosts
        st.session_state.ch_tone  = tono

        datos = {
            "channel_name":  nombre,
            "channel_desc":  desc,
            "channel_hosts": hosts,
            "channel_tone":  tono,
            "material_dir":  material,
            "output_dir":    salida,
            "llm_provider":  prov,
            "claude_model":  st.session_state.get("setup_claude_model") or config.CLAUDE_MODEL,
            "ollama_model":  st.session_state.get("setup_ollama_model") or config.OLLAMA_MODEL,
        }
        save_settings(datos)
        config.apply_settings(datos)
        st.session_state.show_settings = False
        st.rerun()

    if not primera_vez and col_cancel.button("Cancelar", use_container_width=True):
        st.session_state.show_settings = False
        load_user_settings()  # descartar lo tipeado
        st.rerun()

    st.stop()

# Lo guardado en settings.json pisa a los defaults, una vez por sesión.
if "_settings_loaded" not in st.session_state:
    load_user_settings()
    st.session_state["_settings_loaded"] = True


# ── Sidebar ───────────────────────────────────────────────────────────────────
# Antes vivía acá toda la configuración del canal: cuatro campos que se llenan
# una vez, ocupando 245 px de ancho en todas las pantallas para siempre. Ahora
# está en Ajustes y la barra dice lo único que cambia seguido.

def motor_label() -> str:
    if config.LLM_PROVIDER == "ollama":
        return f"Local · {config.OLLAMA_MODEL}"
    return f"Claude · {config.CLAUDE_MODEL}"


with st.sidebar:
    st.markdown(f"**{st.session_state.get('ch_name') or 'Sin canal'}**")
    st.caption(motor_label())
    if st.button("⚙ Ajustes", use_container_width=True, key="open_settings"):
        st.session_state.show_settings = True
        st.rerun()
    if st.session_state.stage != "idle":
        st.divider()
        # En dos pasos a propósito: está siempre a la vista y del otro lado hay
        # un episodio entero de trabajo.
        if st.session_state.get("_confirm_reset"):
            st.caption("¿Seguro? Se descarta el episodio en curso.")
            c_si, c_no = st.columns(2)
            if c_si.button("Sí, empezar", use_container_width=True, key="reset_yes"):
                st.session_state.pop("_confirm_reset", None)
                reset()
                st.rerun()
            if c_no.button("No", use_container_width=True, key="reset_no"):
                st.session_state.pop("_confirm_reset", None)
                st.rerun()
        elif st.button("↺ Empezar de nuevo", use_container_width=True, key="reset_side"):
            st.session_state["_confirm_reset"] = True
            st.rerun()


if not CONFIG_OK:
    st.error(f"Falta configuración: {CONFIG_ERROR}")
    st.stop()

# Primera vez, o cuando el usuario abre Ajustes: la pantalla de configuración
# reemplaza a todo lo demás (hace st.stop()).
if not settings_exist() or st.session_state.get("show_settings"):
    setup_screen()

header(st.session_state.stage)



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

# La fila de entrada solo existe antes de cargar nada: antes quedaba arriba
# para siempre, deshabilitada y con una ruta de ejemplo adentro.
if st.session_state.stage == "idle":
    col_input, col_btn = st.columns([6, 1.5])

    with col_input:
        if _is_youtube:
            _input_val = st.text_input(
                "Entrada",
                placeholder="https://youtube.com/watch?v=...",
                label_visibility="collapsed",
            )
        else:
            # El archivo está en el disco de esta misma máquina, así que un
            # file_uploader significaría subir varios GB por HTTP para dejarlos
            # donde ya estaban. Se listan los que hay y se elige.
            _material = find_videos(config.MATERIAL_DIR)
            _OTRA = "Otra ruta…"
            _opciones = [label_for(v) for v in _material] + [_OTRA]
            _elegido = st.selectbox(
                "Archivo local",
                options=_opciones,
                index=0 if _material else len(_opciones) - 1,
                label_visibility="collapsed",
            )
            if _elegido == _OTRA:
                _input_val = st.text_input(
                    "Ruta del archivo",
                    placeholder=r"C:\Videos\mi_video.mp4",
                    label_visibility="collapsed",
                )
            else:
                _input_val = _material[_opciones.index(_elegido)]["path"]

            if not _material:
                st.caption(
                    f"No hay videos en `{config.MATERIAL_DIR}`. Cambiá la carpeta "
                    "en ⚙ Ajustes, o pegá la ruta acá arriba."
                )

    with col_btn:
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
        st.markdown(f"**Clip {_c4.get('index', _foco4 + 1)}**")

        _tab_enc, _tab_cap = st.tabs(["🎯 Encuadre", "✨ Capas"])
        with _tab_enc:
            if config.crops(normalize_format(_c4.get("formato"))):
                st.caption(
                    "En **9:16** y **1:1** elegís a qué persona recortar cuando hay más "
                    "de una; en **split**, quién va arriba y quién abajo. Sin encuadre "
                    "manual el recorte sigue al hablante."
                )
                clip_framing_fragment(_c4)
            else:
                st.caption("Este formato muestra el plano entero: no hay nada que encuadrar.")
        with _tab_cap:
            st.caption(
                "Se dibujan encima del video: no alargan el clip ni hace falta volver "
                "a cortar. Se ven al renderizar."
            )
            overlay_controls(_c4)

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

    _carpeta = config.OUTPUT_DIR / vid_id
    st.caption(
        f"Los videos, las portadas y el CSV quedan en `{_carpeta}` "
        "— se cambia en ⚙ Ajustes."
    )

    col_dl2, col_spacer = st.columns([1, 3])
    with col_dl2:
        st.download_button(
            label="⬇️ Descargar CSV",
            data=csv_str,
            file_name=f"clips_{vid_id}.csv",
            mime="text/csv",
            type="primary",
            use_container_width=True,
        )

