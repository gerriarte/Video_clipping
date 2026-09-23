"""
Genera captions para TikTok, Instagram y YouTube.

Usa la capa `modules.llm`, que enruta a Claude (Anthropic) o a un modelo local
(Ollama) según config.LLM_PROVIDER. La salida estructurada se garantiza con el
JSON Schema de `_CAPTIONS_TOOL["input_schema"]`.
"""

import config
from modules import llm


# La salida estructurada se garantiza vía JSON Schema: con Anthropic se usa como
# herramienta forzada; con Ollama, como `format`. En ambos casos siempre recibimos
# un objeto válido (antes, sin esto, el modelo a veces respondía en prosa).
_CAPTIONS_TOOL = {
    "name": "submit_captions",
    "description": "Registra los captions optimizados para cada plataforma.",
    "input_schema": {
        "type": "object",
        "properties": {
            "tiktok": {
                "type": "string",
                "description": "Caption para TikTok: máx 150 chars, primera línea = gancho, + 5-7 hashtags.",
            },
            "instagram": {
                "type": "string",
                "description": "Caption para Instagram: primera línea impactante, 2-3 líneas de apoyo, CTA, y 15-20 hashtags en bloque al final.",
            },
            "youtube": {
                "type": "string",
                "description": "Título/caption para YouTube Shorts: máx 100 chars, keyword al inicio, sin hashtags.",
            },
        },
        "required": ["tiktok", "instagram", "youtube"],
    },
}


def generate_captions(clip: dict, video_title: str, channel_context: str | None = None) -> dict:
    """
    Genera captions para las 3 plataformas para un clip dado.

    clip: {title, reason, type, start, end, subtitles (cues)}

    Returns:
        {
            "tiktok":    str,
            "instagram": str,
            "youtube":   str,
        }
    """
    # Armar texto del clip a partir de los subtítulos
    subs = clip.get("subtitles", [])
    clip_transcript = " ".join(s["text"] for s in subs) if subs else "(sin transcript disponible)"
    duration = clip["end"] - clip["start"]

    ctx = channel_context or config.DEFAULT_CHANNEL_CONTEXT
    prompt = f"""{ctx}

Estás creando captions para un clip de {duration:.0f} segundos del episodio "{video_title}".

TÍTULO DEL CLIP: {clip["title"]}
TIPO DE MOMENTO: {clip["type"]}
POR QUÉ ES VALIOSO: {clip["reason"]}

TRANSCRIPCIÓN DEL CLIP:
{clip_transcript[:1500]}

---

Generá captions optimizados para cada plataforma en español latino (neutro, profesional).
Basate en lo que REALMENTE se dice en la transcripción; no inventes datos ni cifras que no aparezcan.

**TIKTOK** (máx 150 chars + 5-7 hashtags):
- Primera línea = gancho que genere curiosidad o FOMO
- Tono directo, energético, joven pero profesional
- Hashtags: mezcla trending + nicho (#negocios, #marketing, #emprendimiento, etc.)

**INSTAGRAM** (máx 220 chars antes del "ver más" + 15-20 hashtags al final):
- Primera línea impactante (es lo único visible antes del "más")
- 2-3 líneas de apoyo con bullets o emojis
- CTA claro (comenta, guarda, comparte)
- Hashtags separados en bloque al final

**YOUTUBE SHORTS** (máx 100 chars):
- Descriptivo y con keyword relevante al inicio
- Sin hashtags (YouTube los pondrá del video padre)

Devolvé los captions llamando a la herramienta `submit_captions`."""

    data = llm.complete_structured(
        prompt,
        _CAPTIONS_TOOL["input_schema"],
        tool_name="submit_captions",
        tool_description=_CAPTIONS_TOOL["description"],
        max_tokens=2000,
        num_ctx=8192,
    )
    return {
        "tiktok":    data.get("tiktok", ""),
        "instagram": data.get("instagram", ""),
        "youtube":   data.get("youtube", ""),
    }


def generate_all_captions(clips: list[dict], video_title: str, channel_context: str | None = None) -> list[dict]:
    """Genera captions para todos los clips y los añade al dict de cada clip."""
    results = []
    for i, clip in enumerate(clips, 1):
        print(f"  ✍️  Generando captions clip {i}/{len(clips)}: {clip['title']}")
        captions = generate_captions(clip, video_title, channel_context=channel_context)
        results.append({**clip, "captions": captions})
    return results
