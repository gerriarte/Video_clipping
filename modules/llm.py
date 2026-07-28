"""
Capa de abstracción de LLM.

Permite usar Anthropic (Claude, en la nube) o un modelo LOCAL vía Ollama de forma
intercambiable, sin tocar el resto del pipeline. La salida estructurada se define
con un JSON Schema (el mismo `input_schema` que ya usaban las herramientas de
Claude), así que los esquemas existentes se reutilizan tal cual.

Selección de proveedor/modelo (en config.py, sobreescribible por variable de entorno):
    LLM_PROVIDER = "anthropic" | "ollama"
    OLLAMA_MODEL = "gemma4"  (o "qwen2.5:14b", etc.)
    OLLAMA_HOST  = "http://localhost:11434"

Salida estructurada:
- Anthropic: tool use forzado (tool_choice) → siempre devuelve un objeto válido.
- Ollama: parámetro `format` = JSON Schema (decodificación restringida por
  gramática). Para modelos locales es MÁS fiable que forzar tool calls.
"""

import json

import config


class LLMError(RuntimeError):
    """Error de cualquier proveedor de LLM (sin red, JSON inválido, corte, etc.)."""


def complete_structured(
    prompt: str,
    schema: dict,
    *,
    tool_name: str,
    tool_description: str = "",
    max_tokens: int = 2000,
    num_ctx: int | None = None,
    temperature: float | None = None,
) -> dict:
    """
    Ejecuta una consulta de una sola vuelta y devuelve un dict que cumple `schema`
    (un JSON Schema de tipo object). Mismo contrato con Anthropic u Ollama.

    schema:        el `input_schema` (object) de la herramienta original.
    tool_name:     nombre de la herramienta (solo lo usa Anthropic).
    num_ctx:       ventana de contexto para Ollama (tokens). IMPORTANTE para
                   prompts largos: el default de Ollama es chico y truncaría en
                   silencio. Ignorado por Anthropic.
    """
    provider = (config.LLM_PROVIDER or "anthropic").lower()
    if provider == "anthropic":
        return _anthropic_structured(
            prompt, schema, tool_name, tool_description, max_tokens, temperature
        )
    if provider == "ollama":
        return _ollama_structured(prompt, schema, max_tokens, num_ctx, temperature)
    raise LLMError(f"LLM_PROVIDER desconocido: {provider!r} (usá 'anthropic' u 'ollama').")


def active_model_label() -> str:
    """Texto legible del proveedor/modelo activo (para logs y UI)."""
    provider = (config.LLM_PROVIDER or "anthropic").lower()
    if provider == "ollama":
        return f"Ollama · {config.OLLAMA_MODEL}"
    return f"Anthropic · {config.CLAUDE_MODEL}"


# ──────────────────────────────────────────────────────────────────────────────
# Anthropic (Claude)
# ──────────────────────────────────────────────────────────────────────────────
def _anthropic_structured(prompt, schema, tool_name, tool_description, max_tokens, temperature):
    import anthropic

    if not config.ANTHROPIC_API_KEY:
        raise LLMError("Falta ANTHROPIC_API_KEY para usar el proveedor 'anthropic'.")

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    tool = {
        "name": tool_name,
        "description": tool_description or "Registra la salida estructurada.",
        "input_schema": schema,
    }
    kwargs = dict(
        model=config.CLAUDE_MODEL,
        max_tokens=max_tokens,
        tools=[tool],
        tool_choice={"type": "tool", "name": tool_name},
        messages=[{"role": "user", "content": prompt}],
    )
    if temperature is not None:
        kwargs["temperature"] = temperature

    message = client.messages.create(**kwargs)

    if message.stop_reason == "max_tokens":
        raise LLMError(
            "La respuesta del modelo se cortó por límite de tokens "
            "(probá con menos clips o un contexto más acotado)."
        )

    tool_blocks = [b for b in message.content if getattr(b, "type", None) == "tool_use"]
    if not tool_blocks:
        raise LLMError(f"El modelo no llamó a la herramienta `{tool_name}`.")
    return tool_blocks[0].input


# ──────────────────────────────────────────────────────────────────────────────
# Ollama (modelo local)
# ──────────────────────────────────────────────────────────────────────────────
def _ollama_structured(prompt, schema, max_tokens, num_ctx, temperature):
    import requests

    # Temperatura: la del request si se pasó, si no la de config (baja por
    # defecto: gemma viene en 1.0, que aluciona timestamps).
    temp = temperature if temperature is not None else config.OLLAMA_TEMPERATURE

    options = {"num_predict": max_tokens, "temperature": temp}
    if num_ctx:
        options["num_ctx"] = num_ctx

    payload = {
        "model":    config.OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream":   False,
        "format":   schema,   # JSON Schema → salida restringida por gramática
        "options":  options,
    }

    url = f"{config.OLLAMA_HOST.rstrip('/')}/api/chat"
    try:
        r = requests.post(url, json=payload, timeout=config.OLLAMA_TIMEOUT)
        r.raise_for_status()
    except requests.RequestException as e:
        raise LLMError(
            f"No se pudo contactar Ollama en {url}: {e}. "
            f"¿Está corriendo `ollama serve` y descargado el modelo `{config.OLLAMA_MODEL}`?"
        )

    data = r.json()
    content = (data.get("message") or {}).get("content", "") or ""
    content = content.strip()
    if not content:
        raise LLMError("Ollama devolvió una respuesta vacía.")

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        # Algunos modelos 'thinking' anteponen texto; intentamos recortar al primer
        # objeto JSON balanceado como último recurso.
        salvaged = _extract_first_json_object(content)
        if salvaged is not None:
            return salvaged
        raise LLMError(f"Ollama no devolvió JSON válido ({e}). Inicio: {content[:300]}")


def _extract_first_json_object(text: str):
    """Devuelve el primer objeto JSON balanceado del texto, o None."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None
