"""
Tests de la configuración del usuario.

Lo que importa acá es que escribir la API key no rompa el `.env`: ese archivo
también tiene POSTIZ_API_KEY y la URL del servidor, y reescribirlo mal deja la
app sin publicar sin decir por qué.
"""

import json

import pytest

from modules.settings import (
    DEFAULTS,
    env_read,
    env_upsert,
    load_settings,
    mask_key,
    save_settings,
    settings_exist,
)


# ── settings.json ─────────────────────────────────────────────────────────────

def test_load_devuelve_los_defaults_si_no_hay_archivo(tmp_path):
    s = load_settings(tmp_path / "no-existe.json")
    assert s == DEFAULTS
    assert not settings_exist(tmp_path / "no-existe.json")


def test_load_completa_lo_que_falta(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"channel_name": "Zumo"}), encoding="utf-8")
    s = load_settings(p)
    assert s["channel_name"] == "Zumo"
    assert s["llm_provider"] == DEFAULTS["llm_provider"]


def test_load_sobrevive_a_un_archivo_roto(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("{esto no es json", encoding="utf-8")
    assert load_settings(p) == DEFAULTS


def test_guardar_y_releer(tmp_path):
    p = tmp_path / "settings.json"
    save_settings({"channel_name": "Zumo Streaming", "channel_tone": "Relajado"}, p)
    s = load_settings(p)
    assert s["channel_name"] == "Zumo Streaming"
    assert s["channel_tone"] == "Relajado"


def test_guardar_ignora_claves_desconocidas(tmp_path):
    p = tmp_path / "settings.json"
    save_settings({"channel_name": "Zumo", "cualquier_cosa": 1}, p)
    assert "cualquier_cosa" not in json.loads(p.read_text(encoding="utf-8"))


@pytest.mark.parametrize("secreto", ["ANTHROPIC_API_KEY", "POSTIZ_API_KEY"])
def test_guardar_rechaza_secretos(tmp_path, secreto):
    """settings.json se copia y se comparte; una key no puede terminar ahí."""
    with pytest.raises(ValueError, match="secreto"):
        save_settings({"channel_name": "Zumo", secreto: "sk-ant-loquesea"}, tmp_path / "s.json")


# ── .env ──────────────────────────────────────────────────────────────────────

_ENV_EJEMPLO = """\
# Configuración de Zumo
ANTHROPIC_API_KEY=vieja

POSTIZ_API_URL=https://redes.abralatam.com/api/public/v1
POSTIZ_API_KEY=postiz-secreta
"""


def test_upsert_reemplaza_sin_tocar_lo_demas(tmp_path):
    p = tmp_path / ".env"
    p.write_text(_ENV_EJEMPLO, encoding="utf-8")

    env_upsert("ANTHROPIC_API_KEY", "nueva", p)

    assert env_read("ANTHROPIC_API_KEY", p) == "nueva"
    assert env_read("POSTIZ_API_KEY", p) == "postiz-secreta"
    assert env_read("POSTIZ_API_URL", p) == "https://redes.abralatam.com/api/public/v1"
    assert "# Configuración de Zumo" in p.read_text(encoding="utf-8")


def test_upsert_agrega_al_final_si_no_estaba(tmp_path):
    p = tmp_path / ".env"
    p.write_text("POSTIZ_API_KEY=x\n", encoding="utf-8")
    env_upsert("ANTHROPIC_API_KEY", "nueva", p)
    assert env_read("ANTHROPIC_API_KEY", p) == "nueva"
    assert env_read("POSTIZ_API_KEY", p) == "x"


def test_upsert_crea_el_archivo_si_no_existe(tmp_path):
    p = tmp_path / ".env"
    env_upsert("ANTHROPIC_API_KEY", "nueva", p)
    assert p.exists()
    assert env_read("ANTHROPIC_API_KEY", p) == "nueva"


def test_upsert_no_confunde_una_clave_con_otra_que_la_contiene(tmp_path):
    p = tmp_path / ".env"
    p.write_text("MI_ANTHROPIC_API_KEY=otra\nANTHROPIC_API_KEY=vieja\n", encoding="utf-8")
    env_upsert("ANTHROPIC_API_KEY", "nueva", p)
    assert env_read("MI_ANTHROPIC_API_KEY", p) == "otra"
    assert env_read("ANTHROPIC_API_KEY", p) == "nueva"


def test_upsert_ignora_una_linea_comentada(tmp_path):
    p = tmp_path / ".env"
    p.write_text("# ANTHROPIC_API_KEY=ejemplo\n", encoding="utf-8")
    env_upsert("ANTHROPIC_API_KEY", "nueva", p)
    texto = p.read_text(encoding="utf-8")
    assert "# ANTHROPIC_API_KEY=ejemplo" in texto
    assert env_read("ANTHROPIC_API_KEY", p) == "nueva"


def test_upsert_no_parte_el_archivo_con_un_salto_de_linea(tmp_path):
    """Un valor pegado con un \\n de más convertiría media key en otra variable."""
    p = tmp_path / ".env"
    env_upsert("ANTHROPIC_API_KEY", "sk-ant\nPOSTIZ_API_KEY=robada", p)
    assert env_read("POSTIZ_API_KEY", p) == ""
    assert "robada" in env_read("ANTHROPIC_API_KEY", p)


def test_upsert_rechaza_un_nombre_de_variable_invalido(tmp_path):
    with pytest.raises(ValueError):
        env_upsert("NO VALE=x", "1", tmp_path / ".env")


# ── mostrar una key sin mostrarla ─────────────────────────────────────────────

def test_mask_deja_reconocerla_sin_poder_usarla():
    enmascarada = mask_key("sk-ant-api03-ABCDEFGHIJKLMNOP1234")
    assert enmascarada.startswith("sk-ant-")
    assert enmascarada.endswith("1234")
    assert "ABCDEFGHIJKLMNOP" not in enmascarada


def test_mask_de_una_key_corta_no_filtra_nada():
    assert set(mask_key("corta")) == {"•"}


def test_mask_de_vacio_es_vacio():
    assert mask_key("") == ""
    assert mask_key(None) == ""
