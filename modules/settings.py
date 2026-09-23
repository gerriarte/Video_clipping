"""
Lo que el usuario configura una vez: su canal y con qué modelo trabaja.

Dos destinos distintos a propósito:

- `settings.json` — datos del canal y qué proveedor/modelo usar. Es texto común
  y se versiona el archivo de ejemplo, no el real.
- `.env` — **las API keys, y solo ahí**. Ya estaba en `.gitignore` y ya es de
  donde `config.py` las lee al arrancar. Una key nunca entra en
  `settings.json` ni en `.pipeline_state.json`, que se copian y se comparten
  sin pensarlo.
"""

import json
import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SETTINGS_FILE = Path(os.environ.get("ZUMO_SETTINGS_FILE", BASE_DIR / "settings.json"))
ENV_FILE = Path(os.environ.get("ZUMO_ENV_FILE", BASE_DIR / ".env"))

# Si algo de esto aparece en el dict de settings, `save_settings` lo rechaza: es
# la red que evita que una key termine en un archivo que se comparte. POSTIZ_API_KEY
# sigue en la lista aunque la integración se haya sacado, porque el .env de quien
# venga usando esto desde antes la tiene igual.
SECRET_KEYS = ("ANTHROPIC_API_KEY", "POSTIZ_API_KEY")

DEFAULTS = {
    "channel_name": "",
    "channel_desc": "",
    "channel_hosts": "",
    "channel_tone": "",
    # Vacío = la carpeta de descargas del proyecto (config.MATERIAL_DIR, que es
    # absoluta). Una ruta relativa acá dependería de desde dónde se lanzó la app.
    "material_dir": "",
    "llm_provider": "anthropic",
    "claude_model": "claude-sonnet-4-6",
    "ollama_model": "qwen2.5:14b",
}


def load_settings(path: Path | None = None) -> dict:
    """Lo guardado, completado con los defaults. {} nunca: siempre todas las claves."""
    path = Path(path or SETTINGS_FILE)
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}  # archivo roto: arrancamos con los defaults
    if not isinstance(data, dict):
        data = {}
    return {**DEFAULTS, **{k: v for k, v in data.items() if k in DEFAULTS}}


def save_settings(data: dict, path: Path | None = None) -> None:
    """Guarda solo las claves conocidas. Levanta si le pasan un secreto."""
    filtrado = {}
    for k, v in data.items():
        if k in SECRET_KEYS:
            raise ValueError(
                f"{k} es un secreto: va en el .env, no en settings.json."
            )
        if k in DEFAULTS:
            filtrado[k] = v
    path = Path(path or SETTINGS_FILE)
    path.write_text(
        json.dumps({**DEFAULTS, **filtrado}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def settings_exist(path: Path | None = None) -> bool:
    """Si el usuario ya pasó por la configuración alguna vez."""
    return Path(path or SETTINGS_FILE).exists()


def env_upsert(key: str, value: str, path: Path | None = None) -> None:
    """
    Escribe `key=value` en el .env sin tocar el resto.

    Reescribir el archivo entero sería más simple y perdería los comentarios y
    las otras claves que haya — o peor, las dejaría escritas de otra forma. Acá
    se reemplaza la línea si existe y se agrega al final si no.
    """
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
        raise ValueError(f"Nombre de variable inválido: {key!r}")
    # Un salto de línea partiría el archivo en dos variables.
    value = str(value).replace("\r", "").replace("\n", "")

    path = Path(path or ENV_FILE)
    lineas = path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    nueva = f"{key}={value}"
    encontrada = False
    for i, linea in enumerate(lineas):
        sin_espacios = linea.strip()
        if sin_espacios.startswith("#") or "=" not in sin_espacios:
            continue
        if sin_espacios.split("=", 1)[0].strip() == key:
            lineas[i] = nueva
            encontrada = True
            break
    if not encontrada:
        lineas.append(nueva)

    path.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def env_read(key: str, path: Path | None = None) -> str:
    """Lee una variable del .env (no de os.environ). "" si no está."""
    path = Path(path or ENV_FILE)
    if not path.exists():
        return ""
    for linea in path.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea.startswith("#") or "=" not in linea:
            continue
        k, v = linea.split("=", 1)
        if k.strip() == key:
            return v.strip()
    return ""


def mask_key(value: str) -> str:
    """
    Cómo se muestra una key en pantalla: nunca entera.

    Alcanza para reconocer *cuál* key está puesta sin dejarla legible en una
    captura de pantalla o en una grabación.
    """
    value = (value or "").strip()
    if not value:
        return ""
    if len(value) <= 12:
        return "•" * len(value)
    return f"{value[:7]}…{value[-4:]}"
