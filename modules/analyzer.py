"""
Parsea el transcript VTT y usa Claude API para identificar los mejores momentos.
"""

import re
import json
import anthropic
from pathlib import Path

import config


# ── VTT parsing ───────────────────────────────────────────────────────────────

def parse_vtt(vtt_path: Path) -> list[dict]:
    """
    Parsea un archivo VTT y retorna lista de cues:
    [{"start": float, "end": float, "text": str}, ...]
    """
    text = vtt_path.read_text(encoding="utf-8", errors="ignore")
    cues = []

    # Regex para timestamps VTT: HH:MM:SS.mmm --> HH:MM:SS.mmm
    pattern = re.compile(
        r"(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})[^\n]*\n([\s\S]*?)(?=\n\n|\Z)",
        re.MULTILINE,
    )

    for match in pattern.finditer(text):
        start_s = _timestamp_to_seconds(match.group(1))
        end_s   = _timestamp_to_seconds(match.group(2))
        if end_s - start_s < 0.5:  # cues de transición de YouTube (~0.01s), sin valor
            continue
        cue_text = _clean_vtt_text(match.group(3))
        if cue_text:
            cues.append({"start": start_s, "end": end_s, "text": cue_text})

    return cues


def _merge_rolling_texts(texts: list[str]) -> str:
    """
    Reconstruye texto limpio a partir de rolling captions de YouTube.
    Cada cue repite las últimas N palabras del anterior más palabras nuevas.
    Usamos coincidencia de sufijo-prefijo para agregar solo lo nuevo.
    """
    if not texts:
        return ""
    result = texts[0].strip()
    for raw in texts[1:]:
        text = raw.strip()
        if not text or text == result:
            continue
        # Buscar el sufijo más largo de `result` que sea prefijo de `text`
        overlap = 0
        max_check = min(len(result), len(text), 120)
        for i in range(max_check, 0, -1):
            if result[-i:].lower() == text[:i].lower():
                overlap = i
                break
        new_part = text[overlap:].strip()
        if new_part:
            result += " " + new_part
    return result.strip()


def cues_to_text(cues: list[dict], block_seconds: float = 15.0) -> str:
    """
    Fusiona cues en bloques de ~block_seconds segundos usando _merge_rolling_texts.
    Produce una línea por bloque: [HH:MM:SS] texto limpio y completo.
    """
    if not cues:
        return ""

    lines       = []
    block_start = cues[0]["start"]
    block_texts: list[str] = []

    def _flush(start: float, texts: list[str]) -> None:
        merged = _merge_rolling_texts(texts)
        if merged:
            lines.append(f"[{_seconds_to_timestamp(start)}] {merged}")

    for cue in cues:
        if cue["start"] >= block_start + block_seconds:
            _flush(block_start, block_texts)
            block_start = cue["start"]
            block_texts = []
        text = cue["text"].strip()
        if text:
            block_texts.append(text)

    _flush(block_start, block_texts)
    return "\n".join(lines)


# ── Claude analysis ───────────────────────────────────────────────────────────

def identify_clips(
    cues: list[dict],
    video_title: str,
    target_clips: int | None = None,
    min_seconds: int | None = None,
    max_seconds: int | None = None,
    channel_context: str | None = None,
) -> list[dict]:
    """
    Envía el transcript a Claude y obtiene los mejores momentos para clip.

    Returns:
        [
            {
                "start": float,        # segundos
                "end": float,          # segundos
                "reason": str,         # por qué es un buen clip
                "type": str,           # insight | advice | humor | stat | story
                "title": str,          # título corto para el clip
            },
            ...
        ]
    """
    n_clips  = target_clips or config.TARGET_CLIPS
    min_secs = min_seconds  or config.MIN_CLIP_SECONDS
    max_secs = max_seconds  or config.MAX_CLIP_SECONDS

    # Pedimos un 50% extra para compensar clips que no pasen la validación de duración
    request_n = n_clips + max(3, n_clips // 2)

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    transcript_text = cues_to_text(cues)
    max_chars = 40_000
    if len(transcript_text) > max_chars:
        # Muestreo uniforme para cubrir el video completo en vez de truncar el inicio
        lines = transcript_text.split("\n")
        target = max_chars // max(1, len(transcript_text) // max(len(lines), 1))
        target = max(1, min(target, len(lines)))
        step = len(lines) / target
        sampled = [lines[int(i * step)] for i in range(target)]
        transcript_text = "\n".join(sampled) + "\n\n[Transcript muestreado — cubre el video completo]"

    ctx = channel_context or config.ZUMO_CONTEXT
    prompt = f"""{ctx}

Tenés el siguiente transcript del video "{video_title}" con timestamps en formato [HH:MM:SS.mmm].
Tu tarea es identificar los {request_n} mejores fragmentos para clips virales en TikTok/Instagram/YouTube Shorts.

REGLAS ESTRICTAS:
- Debés devolver EXACTAMENTE {request_n} clips, ni más ni menos
- Cada clip debe durar entre {min_secs} y {max_secs} segundos
- Los clips NO deben superponerse ni repetir contenido
- Distribuí los clips a lo largo de TODO el video, no solo al principio
- Priorizá: insights accionables, consejos concretos, momentos de humor genuino, estadísticas sorprendentes, historias con gancho
- El clip debe tener sentido completo por sí mismo (inicio y cierre naturales)
- Preferí momentos donde un host da un consejo claro o comparte una opinión fuerte
- Ignorá saludos, transiciones y relleno sin valor

TIMESTAMPS:
Los valores start/end DEBEN ser los segundos exactos tomados de los timestamps [HH:MM:SS.mmm] del transcript.
Ejemplo: [00:15:32.400] → start = 932.4
NO inventes ni aproximes timestamps que no aparezcan en el transcript.

TRANSCRIPT:
{transcript_text}

Respondé ÚNICAMENTE en JSON válido con esta estructura exacta:
{{
  "clips": [
    {{
      "start": 932.4,
      "end": 975.1,
      "title": "Título corto del clip (máx 60 chars)",
      "reason": "Por qué es un buen clip (1 oración)",
      "type": "insight"
    }}
  ]
}}

Tipos válidos: insight, advice, humor, stat, story"""

    # Aumentar max_tokens proporcionalmente al número de clips solicitados
    max_tokens = min(8000, 3000 + request_n * 120)

    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    response_text = message.content[0].text.strip()

    # Quitar posibles markdown fences
    if "```" in response_text:
        response_text = re.sub(r"```(?:json)?\n?", "", response_text).strip()

    data = json.loads(response_text)
    clips = data.get("clips", [])

    # Validar y sanitizar cada clip; recortar a n_clips exactos
    validated = []
    for clip in clips:
        if len(validated) >= n_clips:
            break
        start = float(clip.get("start", 0))
        end   = float(clip.get("end", 0))
        duration = end - start
        if min_secs <= duration <= max_secs:
            validated.append({
                "start":  start,
                "end":    end,
                "title":  clip.get("title", f"Clip {len(validated)+1}"),
                "reason": clip.get("reason", ""),
                "type":   clip.get("type", "insight"),
            })

    if not validated:
        raise ValueError("Claude no devolvió clips válidos dentro del rango de duración permitido")

    # Segunda pasada: títulos precisos basados en el transcript real de cada clip
    validated = _refine_titles(validated, cues, channel_context=channel_context)

    return validated


def _refine_titles(clips: list[dict], cues: list[dict], channel_context: str | None = None) -> list[dict]:
    """
    Segunda pasada de Claude: extrae el transcript exacto de cada clip
    y genera un título preciso basado en lo que realmente se dice.
    Una sola llamada a la API para todos los clips.
    """
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    sections = []
    for i, clip in enumerate(clips):
        clip_cues = [
            c for c in cues
            if c["end"] >= clip["start"] and c["start"] <= clip["end"]
        ]
        clip_text = _merge_rolling_texts([c["text"] for c in clip_cues])
        dur = clip["end"] - clip["start"]
        ts  = f"{_seconds_to_timestamp(clip['start'])} → {_seconds_to_timestamp(clip['end'])}"
        sections.append(f"CLIP {i+1} ({ts}, {dur:.0f}s):\n{clip_text or '(sin transcript)'}")

    ctx = channel_context or config.ZUMO_CONTEXT
    canal = ctx.splitlines()[0].split(" es ")[0].split("\n")[0].strip() if ctx else "este canal"
    prompt = f"""Tenés los siguientes fragmentos de transcript de clips de {canal}.
Para cada clip generá:
1. Un TÍTULO corto (máx 60 caracteres) que capture el tema central o la frase clave de ESE fragmento.
2. Una RAZÓN de una oración que explique por qué es un buen clip viral.

El título debe reflejar lo que realmente se dice en el clip, no una descripción genérica.

{chr(10).join(sections)}

Respondé ÚNICAMENTE en JSON:
{{
  "clips": [
    {{"title": "...", "reason": "..."}}
  ]
}}"""

    try:
        message = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        response = message.content[0].text.strip()
        if "```" in response:
            response = re.sub(r"```(?:json)?\n?", "", response).strip()
        data = json.loads(response)
        refined = data.get("clips", [])
        for i, clip in enumerate(clips):
            if i < len(refined):
                clip["title"]  = refined[i].get("title", clip["title"])
                clip["reason"] = refined[i].get("reason", clip["reason"])
    except Exception:
        pass  # Si falla la segunda pasada, conservamos los títulos originales

    return clips


def get_cues_for_clip(cues: list[dict], start: float, end: float) -> list[dict]:
    """Filtra los cues que caen dentro del rango del clip, ajustando los tiempos relativos."""
    result = []
    for cue in cues:
        if cue["end"] < start or cue["start"] > end:
            continue
        result.append({
            "start": max(0.0, cue["start"] - start),
            "end":   min(end - start, cue["end"] - start),
            "text":  cue["text"],
        })
    return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _timestamp_to_seconds(ts: str) -> float:
    parts = ts.split(":")
    h, m, s = int(parts[0]), int(parts[1]), float(parts[2])
    return h * 3600 + m * 60 + s


def _seconds_to_timestamp(secs: float) -> str:
    h = int(secs // 3600)
    m = int((secs % 3600) // 60)
    s = secs % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def _clean_vtt_text(raw: str) -> str:
    # Quitar tags HTML/VTT (<c>, <i>, etc.) y líneas vacías
    text = re.sub(r"<[^>]+>", "", raw)
    text = re.sub(r"\{.*?\}", "", text)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # Deduplicar líneas consecutivas idénticas (común en auto-subs)
    deduped = []
    for line in lines:
        if not deduped or line != deduped[-1]:
            deduped.append(line)
    return " ".join(deduped)
