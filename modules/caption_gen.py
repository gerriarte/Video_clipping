"""
Genera captions para TikTok, Instagram y YouTube usando Claude API.
"""

import re
import json
import anthropic

import config


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
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    # Armar texto del clip a partir de los subtítulos
    subs = clip.get("subtitles", [])
    clip_transcript = " ".join(s["text"] for s in subs) if subs else "(sin transcript disponible)"
    duration = clip["end"] - clip["start"]

    ctx = channel_context or config.ZUMO_CONTEXT
    prompt = f"""{ctx}

Estás creando captions para un clip de {duration:.0f} segundos del episodio "{video_title}".

TÍTULO DEL CLIP: {clip["title"]}
TIPO DE MOMENTO: {clip["type"]}
POR QUÉ ES VALIOSO: {clip["reason"]}

TRANSCRIPCIÓN DEL CLIP:
{clip_transcript[:1500]}

---

Generá captions optimizados para cada plataforma en español latino (neutro, profesional):

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

Respondé ÚNICAMENTE en JSON válido:
{{
  "tiktok":    "...",
  "instagram": "...",
  "youtube":   "..."
}}"""

    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text.strip()

    if "```" in response_text:
        response_text = re.sub(r"```(?:json)?\n?", "", response_text).strip()

    return json.loads(response_text)


def generate_all_captions(clips: list[dict], video_title: str, channel_context: str | None = None) -> list[dict]:
    """Genera captions para todos los clips y los añade al dict de cada clip."""
    results = []
    for i, clip in enumerate(clips, 1):
        print(f"  ✍️  Generando captions clip {i}/{len(clips)}: {clip['title']}")
        captions = generate_captions(clip, video_title, channel_context=channel_context)
        results.append({**clip, "captions": captions})
    return results
