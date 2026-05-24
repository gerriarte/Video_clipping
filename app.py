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
from pathlib import Path

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
    from modules.downloader  import download_video
    from modules.analyzer    import parse_vtt, identify_clips, get_cues_for_clip
    from modules.clipper     import cut_clips
    from modules.renderer    import render_clips
    from modules.caption_gen import generate_all_captions
    CONFIG_OK    = True
    CONFIG_ERROR = None
except EnvironmentError as e:
    CONFIG_OK    = False
    CONFIG_ERROR = str(e)

# ── Persistencia de estado en disco ──────────────────────────────────────────
_STATE_FILE = Path(__file__).parent / ".pipeline_state.json"


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
            for k in ("stage", "video_info", "cues", "clips", "clipped", "final_clips")}
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
    "stage":        "idle",
    "video_info":   None,
    "cues":         [],
    "clips":        [],
    "clipped":      [],
    "final_clips":  [],
    "ch_name":      "Zumo Streaming",
    "ch_desc":      "Canal de YouTube sobre Negocios, Tecnología, Marketing y temas afines. Orientado a profesionales y empresas latinoamericanas.",
    "ch_hosts":     _ZUMO_HOSTS,
    "ch_tone":      "Relajado pero profesional, con insights accionables para emprendedores.",
}
# Cargar estado persistido solo la primera vez en esta sesión
if "stage" not in st.session_state:
    for k, v in DEFAULTS.items():
        st.session_state[k] = v
    load_state()


def reset():
    for k, v in DEFAULTS.items():
        st.session_state[k] = v
    if _STATE_FILE.exists():
        _STATE_FILE.unlink()


def go_back():
    """Retrocede un paso conservando los datos del paso anterior."""
    transitions = {
        "analyzed": ("downloaded", {"clips": [], "clipped": [], "final_clips": []}),
        "clipped":  ("analyzed",   {"clipped": [], "final_clips": []}),
        "captioned":("clipped",    {"final_clips": []}),
    }
    prev_stage, clear_keys = transitions.get(st.session_state.stage, (None, {}))
    if prev_stage:
        st.session_state.stage = prev_stage
        for k, v in clear_keys.items():
            st.session_state[k] = v
        save_state()


# ── Helpers ───────────────────────────────────────────────────────────────────

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


def copy_btn(label: str, text: str, key: str):
    """Botón que copia texto al portapapeles vía JS."""
    safe = text.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
    st.components.v1.html(
        f"""
        <button onclick="navigator.clipboard.writeText(`{safe}`)
                         .then(()=>{{
                           this.textContent='✅ Copiado!';
                           setTimeout(()=>this.textContent='{label}',2000)
                         }})"
                style="background:#ff4b4b;color:white;border:none;padding:8px 18px;
                       border-radius:6px;cursor:pointer;font-size:13px;width:100%;
                       font-family:sans-serif;font-weight:600">
          {label}
        </button>""",
        height=44,
    )


def clips_to_df(clips: list) -> pd.DataFrame:
    return pd.DataFrame([{
        "✓":       c.get("_selected", True),
        "Título":  c["title"],
        "Formato": c.get("formato", "9:16 vertical"),
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
            clip["formato"] = row["Formato"]
            clip["start"]   = float(row["Inicio"])
            clip["end"]     = float(row["Fin"])
            clip["type"]    = row["Tipo"]
            clip["reason"]  = row["Razón"]
            result.append(clip)
    return result


def build_csv(clips: list, video_info: dict) -> str:
    output = io.StringIO()
    fields = [
        "video_id", "video_title", "clip_index", "clip_title",
        "start", "end", "duration", "type", "reason",
        "output_path", "caption_tiktok", "caption_instagram", "caption_youtube",
    ]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for clip in clips:
        caps = clip.get("captions", {})
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
            "output_path":       str(clip.get("output_path", clip.get("clip_path", ""))),
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

    st.caption("Esta info guía a Claude al analizar el video y generar los captions.")


# ── Layout principal ──────────────────────────────────────────────────────────

st.title("🎬 Fast Video Clipping")

if not CONFIG_OK:
    st.error(f"Falta configuración: {CONFIG_ERROR}")
    st.code("set ANTHROPIC_API_KEY=sk-ant-...")
    st.stop()

# Barra de progreso
STAGES = ["idle", "downloaded", "analyzed", "clipped", "captioned"]
LABELS = ["—", "1· Descargado", "2· Analizado", "3· Clips cortados", "4· Captions listos"]
stage_idx = STAGES.index(st.session_state.stage)
st.progress(
    stage_idx / (len(STAGES) - 1),
    text=LABELS[stage_idx] if stage_idx > 0 else "Pegá una URL para empezar",
)
st.divider()


# ══════════════════════════════════════════════════════════════════════════════
# PASO 1 — URL + Descarga
# ══════════════════════════════════════════════════════════════════════════════

col_url, col_dl, col_rst = st.columns([5, 1.5, 1])

with col_url:
    url = st.text_input(
        "URL",
        placeholder="https://youtube.com/watch?v=...",
        disabled=st.session_state.stage != "idle",
        label_visibility="collapsed",
    )

with col_dl:
    if st.session_state.stage == "idle":
        if st.button("▶ Descargar", type="primary", use_container_width=True):
            if not url.strip():
                st.warning("Pegá una URL primero.")
            else:
                with st.status("Descargando…", expanded=True) as s:
                    log_box = st.empty()
                    try:
                        info = download_video(
                            url.strip(),
                            config.DOWNLOADS_DIR,
                            progress_fn=make_live_logger(log_box),
                        )
                        cues = parse_vtt(info["vtt_path"]) if info["vtt_path"] else []
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

    if not st.session_state.cues:
        st.warning("⚠️ No hay transcript VTT. Claude necesita subtítulos automáticos para identificar timestamps precisos. Probá con un video que los tenga habilitados.")

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

    if st.button("🤖 Analizar con Claude", type="primary"):
        with st.status("Analizando transcript…", expanded=True) as s:
            st.write(f"Enviando {len(st.session_state.cues)} cues a Claude… (puede tardar ~20 segundos)")
            try:
                clips = identify_clips(
                    st.session_state.cues,
                    st.session_state.video_info["title"],
                    target_clips=int(target_clips),
                    min_seconds=dur_range[0],
                    max_seconds=dur_range[1],
                    channel_context=build_channel_context(),
                )
                st.session_state.clips = clips
                st.session_state.stage = "analyzed"
                save_state()
                s.update(label=f"✅ {len(clips)} clips identificados", state="complete")
                st.rerun()
            except Exception as e:
                s.update(label="❌ Error en análisis", state="error")
                st.session_state["_last_error"] = f"Error en análisis: {e}"


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

    # Botones de selección rápida
    col_sel, col_desel, col_spacer = st.columns([1, 1, 6])
    if col_sel.button("☑ Todos", use_container_width=True):
        for c in st.session_state.clips:
            c["_selected"] = True
    if col_desel.button("☐ Ninguno", use_container_width=True):
        for c in st.session_state.clips:
            c["_selected"] = False

    st.caption("Marcá los clips que querés cortar. Podés editar título, tiempos y tipo.")

    edited_df = st.data_editor(
        clips_to_df(st.session_state.clips),
        use_container_width=True,
        hide_index=True,
        column_config={
            "✓":       st.column_config.CheckboxColumn("Cortar", width="small"),
            "Título":  st.column_config.TextColumn(width="large"),
            "Formato": st.column_config.SelectboxColumn(
                "Formato",
                options=["9:16 vertical", "Original 16:9"],
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
        key="clips_editor_v3",
    )

    approved = df_to_clips(edited_df, st.session_state.clips)
    n_sel = len(approved)
    st.info(f"**{n_sel} de {total_clips} clips seleccionados** para cortar"
            + ("" if n_sel else " — seleccioná al menos uno para continuar"))

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

    # Preview en columnas
    preview_cols = st.columns(min(len(clipped), 3))
    for i, clip in enumerate(clipped):
        with preview_cols[i % 3]:
            fmt_badge = "📱 9:16" if clip.get("formato") == "9:16 vertical" else "🖥 16:9"
            st.caption(f"**Clip {clip['index']}** {fmt_badge} — {clip['title']}")
            if Path(clip["clip_path"]).exists():
                st.video(str(clip["clip_path"]))
            m, s_ = divmod(int(clip["end"] - clip["start"]), 60)
            st.caption(f"_{clip['type']} · {m}:{s_:02d}_")

    st.divider()

    vertical_clips = [c for c in clipped if c.get("formato") == "9:16 vertical"]
    if vertical_clips:
        st.info(f"📱 **{len(vertical_clips)}** clip{'s' if len(vertical_clips)!=1 else ''} en 9:16 — se renderizarán con Remotion antes de generar captions.")

    if st.button("✍️ Generar captions con Claude", type="primary"):
        clips_to_caption = list(clipped)
        video_id = st.session_state.video_info["video_id"]

        if vertical_clips:
            out_dir = config.OUTPUT_DIR / video_id
            with st.status(f"Renderizando {len(vertical_clips)} clips en 9:16…", expanded=True) as s:
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
                        vertical_clips, out_dir, video_id, progress_fn=_render_progress
                    )
                    # Reemplazar en clips_to_caption los que se renderizaron
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

    for clip in final_clips:
        caps = clip.get("captions", {})
        dur  = int(clip["end"] - clip["start"])
        m, s_ = divmod(dur, 60)

        with st.expander(
            f"Clip {clip['index']} · **{clip['title']}** · {m}:{s_:02d} · _{clip['type']}_",
            expanded=True,
        ):
            col_vid, col_caps = st.columns([1, 2])

            with col_vid:
                vid_path = clip.get("output_path", clip.get("clip_path"))
                if vid_path and Path(str(vid_path)).exists():
                    st.video(str(vid_path))
                st.caption(clip.get("reason", ""))

            with col_caps:
                tab_tt, tab_ig, tab_yt = st.tabs(["TikTok", "Instagram", "YouTube Shorts"])

                with tab_tt:
                    tt = caps.get("tiktok", "")
                    st.text_area(
                        "TikTok", tt, height=200,
                        key=f"tt_{clip['index']}", label_visibility="collapsed"
                    )
                    copy_btn("📋 Copiar TikTok", tt, f"cp_tt_{clip['index']}")

                with tab_ig:
                    ig = caps.get("instagram", "")
                    st.text_area(
                        "Instagram", ig, height=200,
                        key=f"ig_{clip['index']}", label_visibility="collapsed"
                    )
                    copy_btn("📋 Copiar Instagram", ig, f"cp_ig_{clip['index']}")

                with tab_yt:
                    yt = caps.get("youtube", "")
                    st.text_area(
                        "YouTube", yt, height=140,
                        key=f"yt_{clip['index']}", label_visibility="collapsed"
                    )
                    copy_btn("📋 Copiar YouTube Shorts", yt, f"cp_yt_{clip['index']}")

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
