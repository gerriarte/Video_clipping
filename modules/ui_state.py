"""
Traducción entre los clips del pipeline y lo que dibujan las pantallas React.

Vive acá y no en `app.py` para poder probarlo. Es el punto donde un error
significa **perder ediciones en silencio**: el Paso 5 dibujó los captions en un
`text_area` que nunca se leía de vuelta, así que editarlos no hacía nada y el
CSV salía con el texto original. Eso no se ve mirando la pantalla — se ve con un
test.

Las funciones no saben servir archivos: reciben un `url_for(path) -> str` que se
lo inyecta `app.py` (que es quien tiene los MediaServer de la sesión).
"""

from pathlib import Path
from typing import Callable

import config
from modules.renderer import speaker_follow

# ── Formatos ──────────────────────────────────────────────────────────────────

FORMAT_LABELS = {k: v["label"] for k, v in config.FORMAT_PRESETS.items()}
LABEL_TO_KEY  = {v: k for k, v in FORMAT_LABELS.items()}
FORMAT_OPTIONS = list(FORMAT_LABELS.values())

# Valores viejos que pudieron quedar en el estado persistido.
LEGACY_FORMAT = {"9:16 vertical": "9:16", "Original 16:9": "16:9"}

# Nombre corto para los botones de las tarjetas (el largo va en el tooltip).
FORMAT_SHORT = {
    "9:16":      "9:16",
    "9:16-full": "completo",
    "1:1":       "1:1",
    "16:9":      "16:9",
    "split":     "split",
}

# Las columnas de texto del Paso 5. El orden es el que se ve en pantalla.
PUBLISH_PLATFORMS = [
    {"key": "tiktok",    "label": "TikTok"},
    {"key": "instagram", "label": "Instagram"},
    {"key": "youtube",   "label": "YouTube Shorts"},
]


def normalize_format(val) -> str:
    """Normaliza cualquier valor de formato (clave, label o legacy) a una clave."""
    if not val:
        return config.DEFAULT_FORMAT
    if val in config.FORMAT_PRESETS:
        return val
    if val in LEGACY_FORMAT:
        return LEGACY_FORMAT[val]
    if val in LABEL_TO_KEY:
        return LABEL_TO_KEY[val]
    return config.DEFAULT_FORMAT


def gallery_formats() -> list:
    """Los formatos, con lo que la tarjeta necesita para dibujar el recorte."""
    return [
        {
            "key":        k,
            "label":      p["label"],
            "short":      FORMAT_SHORT.get(k, p["label"]),
            "crop":       bool(p.get("crop")),
            "aspect":     p["width"] / p["height"],
            "autoLayout": bool(p.get("auto_layout")),
        }
        for k, p in config.FORMAT_PRESETS.items()
    ]


# ── Galería (Pasos 3 y 4) ─────────────────────────────────────────────────────

def clips_to_gallery(
    clips: list,
    analyses: dict,
    url_for: Callable[[Path], str],
    clip_url: Callable[[dict], str] | None = None,
) -> list:
    """
    Payload de la galería. `id` es la posición en la lista — es la identidad.

    Args:
        clips:    los clips del pipeline.
        analyses: {posición: análisis de la toma} (puede estar vacío).
        url_for:  cómo servir la foto de un tramo.
        clip_url: si se pasa, la URL del archivo ya cortado de ese clip; la
                  tarjeta lo reproduce entero en vez de buscar el tramo dentro
                  del video fuente (Paso 4, donde el corte ya existe y puede
                  traer jump cuts que el original no tiene).
    """
    out = []
    for pos, c in enumerate(clips):
        a = analyses.get(pos) or {}
        shot = None
        if a.get("samples"):
            shot = {
                "samples":    a["samples"],
                "twoShot":    a.get("two_shot_ratio", 0.0),
                "solo":       a.get("solo_ratio", 0.0),
                "empty":      a.get("empty_ratio", 0.0),
                "mixed":      bool(a.get("mixed")),
                "suggestion": a.get("suggestion", ""),
                "centersX":   a.get("centers_x") or [],
            }
        out.append({
            "id":            pos,
            "index":         c.get("index", pos + 1),
            "title":         c.get("title", ""),
            "start":         float(c["start"]),
            "end":           float(c["end"]),
            "type":          c.get("type", "insight"),
            "reason":        c.get("reason", ""),
            "selected":      bool(c.get("_selected", True)),
            "format":        normalize_format(c.get("formato")),
            "speakerFollow": speaker_follow(c),
            "followShot":    bool(c.get("follow_shot")),
            "thumbs":        [
                {"url": url_for(Path(f)), "label": lbl}
                for f, lbl in (a.get("thumbs") or [])
            ],
            "shot":          shot,
            "clipUrl":       clip_url(c) if clip_url else "",
        })
    return out


# Campo de la galería → clave del clip. El encuadre manual (crop_*) NO está acá:
# se edita en los Pasos 4 y 5 y la galería no debe pisarlo.
_GALLERY_FIELDS = (
    ("title",         "title"),
    ("start",         "start"),
    ("end",           "end"),
    ("type",          "type"),
    ("selected",      "_selected"),
    ("format",        "formato"),
    ("speakerFollow", "speaker_follow"),
    ("followShot",    "follow_shot"),
)


def _gallery_current(clip: dict) -> dict:
    """El estado actual del clip, en el vocabulario de la galería."""
    return {
        "title":          clip.get("title", ""),
        "start":          float(clip["start"]),
        "end":            float(clip["end"]),
        "type":           clip.get("type", "insight"),
        "_selected":      bool(clip.get("_selected", True)),
        "formato":        normalize_format(clip.get("formato")),
        "speaker_follow": speaker_follow(clip),
        "follow_shot":    bool(clip.get("follow_shot")),
    }


def apply_gallery(patch: list, clips: list) -> bool:
    """Vuelca lo editado en la galería sobre los clips. True si algo cambió."""
    changed = False
    for row in patch or []:
        try:
            pos = int(row.get("id", -1))
        except (TypeError, ValueError):
            continue
        if not (0 <= pos < len(clips)):
            continue
        clip    = clips[pos]
        current = _gallery_current(clip)
        for src_key, field in _GALLERY_FIELDS:
            if src_key not in row:
                continue
            val = row[src_key]
            if field in ("start", "end"):
                val = float(val)
            elif field in ("_selected", "speaker_follow", "follow_shot"):
                val = bool(val)
            elif field == "formato":
                val = normalize_format(val)
            else:
                val = str(val)
            if current[field] != val:
                clip[field] = val
                changed = True
    return changed


# ── Publicación (Paso 5) ──────────────────────────────────────────────────────

def clips_to_publish(clips: list, url_for: Callable[[str], str]) -> list:
    """Payload del Paso 5. `url_for` devuelve "" si el archivo no existe."""
    out = []
    for pos, c in enumerate(clips):
        fmt    = normalize_format(c.get("formato"))
        preset = config.FORMAT_PRESETS[fmt]
        caps   = c.get("captions") or {}
        out.append({
            "id":       pos,
            "index":    c.get("index", pos + 1),
            "title":    c.get("title", ""),
            "start":    float(c["start"]),
            "end":      float(c["end"]),
            # La duración real: con jump cuts ya no es end - start.
            "duration": float(c.get("clip_duration") or (c["end"] - c["start"])),
            "type":     c.get("type", ""),
            "reason":   c.get("reason", ""),
            "format":   fmt,
            "aspect":   preset["width"] / preset["height"],
            "videoUrl": url_for(c.get("output_path")),
            "coverUrl": url_for(c.get("cover_path")),
            "captions": {p["key"]: caps.get(p["key"], "") for p in PUBLISH_PLATFORMS},
        })
    return out


def apply_publish(patch: list, clips: list) -> bool:
    """
    Vuelca el formato y los textos editados sobre los clips.

    Hasta la versión con `text_area` esto no existía: los captions se dibujaban
    y no se leían nunca, así que editarlos no hacía nada y el CSV salía con el
    texto original de Claude.
    """
    changed = False
    for row in patch or []:
        try:
            pos = int(row.get("id", -1))
        except (TypeError, ValueError):
            continue
        if not (0 <= pos < len(clips)):
            continue
        clip = clips[pos]

        fmt = normalize_format(row.get("format"))
        if normalize_format(clip.get("formato")) != fmt:
            clip["formato"] = fmt
            changed = True

        caps = dict(clip.get("captions") or {})
        for plat, texto in (row.get("captions") or {}).items():
            texto = str(texto)
            if caps.get(plat, "") != texto:
                caps[plat] = texto
                changed = True
        clip["captions"] = caps
    return changed
