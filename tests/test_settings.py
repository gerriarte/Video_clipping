"""
Tests de la configuración del usuario.

Lo que importa acá es que escribir la API key no rompa el `.env`: ese archivo
puede tener otras variables, y reescribirlo mal se las lleva puestas sin decir
por qué.
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
    p.write_text(json.dumps({"channel_name": "Canal"}), encoding="utf-8")
    s = load_settings(p)
    assert s["channel_name"] == "Canal"
    assert s["llm_provider"] == DEFAULTS["llm_provider"]


def test_load_sobrevive_a_un_archivo_roto(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("{esto no es json", encoding="utf-8")
    assert load_settings(p) == DEFAULTS


def test_guardar_y_releer(tmp_path):
    p = tmp_path / "settings.json"
    save_settings({"channel_name": "Canal de ejemplo", "channel_tone": "Relajado"}, p)
    s = load_settings(p)
    assert s["channel_name"] == "Canal de ejemplo"
    assert s["channel_tone"] == "Relajado"


def test_guardar_ignora_claves_desconocidas(tmp_path):
    p = tmp_path / "settings.json"
    save_settings({"channel_name": "Canal", "cualquier_cosa": 1}, p)
    assert "cualquier_cosa" not in json.loads(p.read_text(encoding="utf-8"))


def test_guardar_rechaza_secretos(tmp_path):
    """settings.json se copia y se comparte; una key no puede terminar ahí."""
    with pytest.raises(ValueError, match="secreto"):
        save_settings({"channel_name": "Canal", "ANTHROPIC_API_KEY": "sk-ant-loquesea"},
                      tmp_path / "s.json")


# ── .env ──────────────────────────────────────────────────────────────────────

_ENV_EJEMPLO = """\
# Configuración
ANTHROPIC_API_KEY=vieja

LLM_PROVIDER=anthropic
OTRA_VARIABLE=no-me-toques
"""


def test_upsert_reemplaza_sin_tocar_lo_demas(tmp_path):
    p = tmp_path / ".env"
    p.write_text(_ENV_EJEMPLO, encoding="utf-8")

    env_upsert("ANTHROPIC_API_KEY", "nueva", p)

    assert env_read("ANTHROPIC_API_KEY", p) == "nueva"
    assert env_read("OTRA_VARIABLE", p) == "no-me-toques"
    assert env_read("LLM_PROVIDER", p) == "anthropic"
    assert "# Configuración" in p.read_text(encoding="utf-8")


def test_upsert_agrega_al_final_si_no_estaba(tmp_path):
    p = tmp_path / ".env"
    p.write_text("OTRA_VARIABLE=x\n", encoding="utf-8")
    env_upsert("ANTHROPIC_API_KEY", "nueva", p)
    assert env_read("ANTHROPIC_API_KEY", p) == "nueva"
    assert env_read("OTRA_VARIABLE", p) == "x"


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
    env_upsert("ANTHROPIC_API_KEY", "sk-ant\nOTRA_VARIABLE=colada", p)
    assert env_read("OTRA_VARIABLE", p) == ""
    assert "colada" in env_read("ANTHROPIC_API_KEY", p)


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


# ── Carpetas de trabajo ───────────────────────────────────────────────────────

def test_las_carpetas_se_guardan_y_se_releen(tmp_path):
    p = tmp_path / "settings.json"
    save_settings({"material_dir": "E:/Material", "output_dir": "E:/Salida"}, p)
    s = load_settings(p)
    assert s["material_dir"] == "E:/Material"
    assert s["output_dir"] == "E:/Salida"


def test_las_carpetas_vacias_dejan_mandar_al_default():
    """Vacío = las carpetas del proyecto, que son rutas absolutas."""
    assert DEFAULTS["material_dir"] == ""
    assert DEFAULTS["output_dir"] == ""
