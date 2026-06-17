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


def transcript_coverage(cues: list[dict], duration: float) -> float:
    """
    Fracción del video (0.0–1.0) que está cubierta por cues con texto real.
    Divide el video en buckets de 10s y cuenta cuántos tienen al menos un cue.
    Sirve para detectar transcripts escasos/fragmentados (VTT incompleto).

    Capea la duración considerada de cada cue: YouTube a veces inserta un cue
    "placeholder" larguísimo (decenas de minutos) que tapa un hueco sin
    subtítulos; sin el cap, ese cue falsearía la cobertura como ~100%.
    """
    if not cues or duration <= 0:
        return 0.0
    bucket    = 10.0
    max_cue   = 30.0   # un subtítulo real no dura más que esto; arriba = placeholder
    n_buckets = max(1, int(duration // bucket) + 1)
    covered   = set()
    for c in cues:
        if not c.get("text", "").strip():
            continue  # cues sin texto no aportan contenido
        end = min(c["end"], c["start"] + max_cue)
        for b in range(int(c["start"] // bucket), int(end // bucket) + 1):
            if 0 <= b < n_buckets:
                covered.add(b)
    return len(covered) / n_buckets


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

def _extract_json(response_text: str) -> dict:
    """
    Extrae un objeto JSON de la respuesta de Claude de forma robusta.
    Tolera markdown fences y texto antes/después del objeto.
    """
    text = response_text.strip()
    # Quitar fences de markdown si los hay
    if "```" in text:
        text = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fallback: tomar el substring entre el primer '{' y el último '}'
    start = text.find("{")
    end   = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start:end + 1])
    # No se pudo: error claro con un fragmento de lo que devolvió Claude
    snippet = response_text.strip()[:500]
    raise ValueError(
        "Claude no devolvió JSON válido. Respuesta recibida:\n" + (snippet or "(vacía)")
    )



def identify_clips(
    cues: list[dict],
    video_title: str,
    target_clips: int | None = None,
    min_seconds: int | None = None,
    max_seconds: int | None = None,
    channel_context: str | None = None,
    excluded_ranges: list[tuple[float, float]] | None = None,
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
    if not cues:
        raise ValueError(
            "No hay transcript para analizar. El video no tiene subtítulos VTT; "
            "transcribí el audio con Whisper antes de analizar."
        )

    n_clips  = target_clips or config.TARGET_CLIPS
    min_secs = min_seconds  or config.MIN_CLIP_SECONDS
    max_secs = max_seconds  or config.MAX_CLIP_SECONDS

    # Pedimos un 50% extra para compensar clips que no pasen la validación de duración
    request_n = n_clips + max(3, n_clips // 2)

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    transcript_text = cues_to_text(cues)
    # El modelo tiene contexto amplio; mandamos el transcript completo salvo que
    # sea enorme. Antes se salteaban líneas (1 de cada N), lo que fragmentaba el
    # contenido y dejaba a Claude "viendo" un texto entrecortado. Ahora, si hay
    # que recortar, acortamos el texto de cada bloque pero CONSERVAMOS todos los
    # timestamps, manteniendo la cobertura temporal de punta a punta del video.
    max_chars = 150_000
    if len(transcript_text) > max_chars:
        lines  = transcript_text.split("\n")
        budget = max(60, max_chars // max(1, len(lines)))
        lines  = [
            (ln[:budget].rstrip() + "…") if len(ln) > budget else ln
            for ln in lines
        ]
        transcript_text = "\n".join(lines) + "\n\n[Transcript condensado — cubre el video completo]"

    excluded_block = ""
    if excluded_ranges:
        zones = "\n".join(
            f"  - {_seconds_to_timestamp(s)} → {_seconds_to_timestamp(e)}"
            for s, e in excluded_ranges
        )
        excluded_block = f"""
ZONAS YA PROCESADAS — NO las uses ni te solapés con ellas:
{zones}
Buscá clips ÚNICAMENTE en los intervalos de tiempo que quedan fuera de estas zonas.
"""

    ctx = channel_context or config.ZUMO_CONTEXT
    prompt = f"""{ctx}

Tenés el siguiente transcript del video "{video_title}" con timestamps en formato [HH:MM:SS.mmm].
Tu tarea es identificar los {request_n} mejores fragmentos para clips virales en TikTok/Instagram/YouTube Shorts.
{excluded_block}
REGLAS ESTRICTAS:
- Devolvé hasta {request_n} clips. Buscá llegar a ese número, pero si el transcript es escaso o fragmentado devolvé los que SÍ tengan valor (aunque sean menos). Priorizá calidad sobre cantidad y devolvé al menos los que encuentres.
- Cada clip debe durar entre {min_secs} y {max_secs} segundos
- Los clips NO deben superponerse ni repetir contenido
- Distribuí los clips a lo largo de TODO el video, no solo al principio
- Priorizá: insights accionables, consejos concretos, momentos de humor genuino, estadísticas sorprendentes, historias con gancho
- El clip debe tener sentido completo por sí mismo (inicio y cierre naturales)
- Preferí momentos donde un host da un consejo claro o comparte una opinión fuerte
- Ignorá saludos, transiciones y relleno sin valor

TÍTULOS (clave para que sean usables):
- El título debe reflejar EXACTAMENTE lo que se dice en ESE fragmento: una frase, idea o afirmación concreta que aparezca en el transcript del clip.
- NO uses títulos genéricos ("Hablando de marketing"), ni inventes datos, cifras o promesas que no estén en el fragmento.
- Si en el clip se dice una frase con gancho, usala o parafraseala fielmente.

TEMAS EN VARIAS PARTES (campo `topic`):
- Asigná a cada clip una etiqueta `topic` corta que describa su tema.
- Si un mismo tema valioso es demasiado largo para un solo clip, o se retoma en otro momento del video, devolvé esos fragmentos como clips separados usando EXACTAMENTE la MISMA etiqueta `topic` en todos. Se publicarán como serie (Parte 1, Parte 2, …).
- Cada parte debe seguir teniendo sentido por sí sola.
- Si un clip es de un tema único (no tiene continuación), usá una etiqueta `topic` propia y distinta de las demás.

TIMESTAMPS:
Los valores start/end DEBEN ser los segundos exactos tomados de los timestamps [HH:MM:SS.mmm] del transcript.
Ejemplo: [00:15:32.400] → start = 932.4
NO inventes ni aproximes timestamps que no aparezcan en el transcript.

TRANSCRIPT:
{transcript_text}

Devolvé los clips llamando a la herramienta `submit_clips`.
Tipos válidos: insight, advice, humor, stat, story"""

    # Aumentar max_tokens proporcionalmente al número de clips solicitados
    max_tokens = min(8000, 3000 + request_n * 120)

    # Forzamos tool use para garantizar salida estructurada: este modelo no
    # admite prefill, y sin esto Claude a veces responde en prosa (ej. cuando
    # el transcript es escaso) y el JSON no se puede parsear.
    clips_tool = {
        "name": "submit_clips",
        "description": "Registra los clips identificados para el video.",
        "input_schema": {
            "type": "object",
            "properties": {
                "clips": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "start":  {"type": "number", "description": "Inicio en segundos"},
                            "end":    {"type": "number", "description": "Fin en segundos"},
                            "title":  {"type": "string", "description": "Título corto (máx 60 chars) basado en una frase o idea concreta del fragmento"},
                            "reason": {"type": "string", "description": "Por qué es un buen clip"},
                            "type":   {"type": "string", "enum": ["insight", "advice", "humor", "stat", "story"]},
                            "topic":  {"type": "string", "description": "Etiqueta corta del tema. Misma etiqueta EXACTA en clips que continúan el mismo tema (serie); etiqueta propia si es único."},
                        },
                        "required": ["start", "end", "title", "reason", "type", "topic"],
                    },
                },
            },
            "required": ["clips"],
        },
    }

    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=max_tokens,
        tools=[clips_tool],
        tool_choice={"type": "tool", "name": "submit_clips"},
        messages=[{"role": "user", "content": prompt}],
    )

    if message.stop_reason == "max_tokens":
        raise ValueError(
            "La respuesta de Claude se cortó por límite de tokens. "
            "Probá con menos clips o un rango de duración más acotado."
        )

    tool_blocks = [b for b in message.content if getattr(b, "type", None) == "tool_use"]
    if not tool_blocks:
        raise ValueError("Claude no llamó a la herramienta de clips en el análisis.")
    clips = tool_blocks[0].input.get("clips", [])

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
                "topic":  (clip.get("topic") or "").strip(),
            })

    if not validated:
        raise ValueError("Claude no devolvió clips válidos dentro del rango de duración permitido")

    # Detectar temas en varias partes: clips que comparten `topic` se publican
    # como serie. Asigna part/part_total ordenando por tiempo de aparición.
    _assign_parts(validated)

    # Segunda pasada: títulos precisos basados en el transcript real de cada clip
    validated = _refine_titles(validated, cues, channel_context=channel_context)

    # Sufijo "(Parte i/n)" en el título, después de refinar para no pisarlo.
    for clip in validated:
        if clip.get("part_total", 0) > 1:
            clip["title"] = f"{clip['title']} (Parte {clip['part']}/{clip['part_total']})"

    return validated


def _assign_parts(clips: list[dict]) -> None:
    """
    Agrupa clips por `topic`: si dos o más comparten la misma etiqueta, los marca
    como serie con `part` (1, 2, …) y `part_total`, ordenados por tiempo de inicio.
    Los clips de tema único quedan sin marca de parte. Muta la lista in-place.
    """
    from collections import defaultdict

    groups: dict[str, list[dict]] = defaultdict(list)
    for clip in clips:
        topic = clip.get("topic", "")
        if topic:
            groups[topic].append(clip)

    for members in groups.values():
        if len(members) < 2:
            continue
        members.sort(key=lambda c: c["start"])
        for i, clip in enumerate(members, 1):
            clip["part"]       = i
            clip["part_total"] = len(members)


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
        # Marca de serie para que Claude haga títulos coherentes entre partes.
        serie = ""
        if clip.get("part_total", 0) > 1:
            serie = f" [SERIE: parte {clip['part']} de {clip['part_total']} del mismo tema]"
        sections.append(f"CLIP {i+1} ({ts}, {dur:.0f}s){serie}:\n{clip_text or '(sin transcript)'}")

    ctx = channel_context or config.ZUMO_CONTEXT
    canal = ctx.splitlines()[0].split(" es ")[0].split("\n")[0].strip() if ctx else "este canal"
    prompt = f"""Tenés los siguientes fragmentos de transcript de clips de {canal}.
Para cada clip generá:
1. Un TÍTULO corto (máx 60 caracteres) que capture la frase o idea clave de ESE fragmento.
2. Una RAZÓN de una oración que explique por qué es un buen clip viral.

REGLAS DEL TÍTULO:
- Debe reflejar fielmente lo que REALMENTE se dice en el clip; usá palabras o ideas que aparezcan en el fragmento.
- NO inventes datos, cifras ni promesas que no estén en el texto. NO uses títulos genéricos.
- Si un clip está marcado como [SERIE], su título debe ser coherente con las otras partes del mismo tema (mismo hilo conceptual), pero NO agregues "Parte 1/2" — eso se añade después automáticamente.

{chr(10).join(sections)}

Devolvé un título y una razón por cada clip, EN EL MISMO ORDEN, llamando a `submit_titles`."""

    titles_tool = {
        "name": "submit_titles",
        "description": "Registra el título y la razón refinados de cada clip, en orden.",
        "input_schema": {
            "type": "object",
            "properties": {
                "clips": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title":  {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["title", "reason"],
                    },
                },
            },
            "required": ["clips"],
        },
    }

    try:
        message = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=2000,
            tools=[titles_tool],
            tool_choice={"type": "tool", "name": "submit_titles"},
            messages=[{"role": "user", "content": prompt}],
        )
        tool_blocks = [b for b in message.content if getattr(b, "type", None) == "tool_use"]
        refined = tool_blocks[0].input.get("clips", []) if tool_blocks else []
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
