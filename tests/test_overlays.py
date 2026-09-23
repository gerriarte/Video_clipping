"""
Tests de las capas que van encima del clip.

Lo que se cuida acá es que un parámetro mal puesto no se descubra recién
mirando un render: un gancho que arranca después de que el clip terminó no se
ve nunca, y cada verificación cuesta un render entero.
"""

import pytest

from modules.overlays import (
    DEFAULT_CARD,
    DEFAULT_HOOK,
    describe,
    for_render,
    normalize,
    parse_hosts,
)


def _clip(**extra):
    base = {"title": "Un título", "start": 10.0, "end": 70.0}
    base.update(extra)
    return base


# ── parse_hosts ───────────────────────────────────────────────────────────────

def test_parse_hosts_lee_nombre_y_rol():
    hosts = parse_hosts("David Guerrero: Diseñador de Marca\nGer: Marketing e IA")
    assert hosts == [
        {"name": "David Guerrero", "role": "Diseñador de Marca"},
        {"name": "Ger", "role": "Marketing e IA"},
    ]


def test_parse_hosts_acepta_una_linea_sin_rol():
    assert parse_hosts("Camila") == [{"name": "Camila", "role": ""}]


def test_parse_hosts_ignora_lineas_vacias():
    assert len(parse_hosts("Ana: Conductora\n\n  \nJuan: Editor")) == 2


def test_parse_hosts_de_vacio():
    assert parse_hosts("") == []
    assert parse_hosts(None) == []


def test_parse_hosts_conserva_los_dos_puntos_del_rol():
    """Un rol puede tener dos puntos; solo el primero separa."""
    hosts = parse_hosts("Ana: Conductora: mañanas")
    assert hosts[0]["role"] == "Conductora: mañanas"


# ── normalize ─────────────────────────────────────────────────────────────────

def test_normalize_completa_lo_que_falta():
    capas = normalize({"hook": {"on": True}})
    assert capas["hook"]["style"] == DEFAULT_HOOK["style"]
    assert capas["lower"]["on"] is False


def test_normalize_sobrevive_a_basura():
    for basura in (None, [], "texto", 7):
        capas = normalize(basura)
        assert capas["hook"]["on"] is False


def test_normalize_descarta_un_estilo_inventado():
    assert normalize({"hook": {"style": "explotar"}})["hook"]["style"] == "pop"
    assert normalize({"hook": {"position": "diagonal"}})["hook"]["position"] == "top"
    assert normalize({"lower": {"side": "arriba"}})["lower"]["side"] == "left"


@pytest.mark.parametrize("valor", [None, "", "abc", float("nan"), float("inf")])
def test_normalize_descarta_tiempos_que_no_son_numeros(valor):
    capas = normalize({"hook": {"start": valor, "dur": valor}})
    assert capas["hook"]["start"] == DEFAULT_HOOK["start"]
    assert capas["hook"]["dur"] == DEFAULT_HOOK["dur"]


def test_normalize_no_deja_tiempos_negativos():
    capas = normalize({"hook": {"start": -5, "dur": -2}})
    assert capas["hook"]["start"] == 0.0
    assert capas["hook"]["dur"] >= 0.3


def test_una_capa_no_puede_arrancar_despues_de_que_el_clip_termino():
    """Es el error que solo se descubre mirando un render que salió sin nada."""
    capas = normalize({"hook": {"on": True, "start": 80, "dur": 10}}, clip_duration=60)
    assert capas["hook"]["start"] <= 60
    assert capas["hook"]["start"] + capas["hook"]["dur"] <= 60 + 1e-6


def test_una_capa_no_se_pasa_del_final():
    capas = normalize({"lower": {"on": True, "start": 55, "dur": 30}}, clip_duration=60)
    assert capas["lower"]["start"] + capas["lower"]["dur"] <= 60 + 1e-6


# ── for_render ────────────────────────────────────────────────────────────────

def test_sin_capas_no_manda_nada():
    """Un clip sin capas tiene que renderizar exactamente como antes."""
    assert for_render(_clip()) is None


def test_el_gancho_cae_al_titulo_del_clip():
    capas = for_render(_clip(overlays={"hook": {"on": True}}))
    assert "hook" in capas
    assert capas["hook"]["text"] == ""      # el texto lo pone la composición


def test_un_gancho_sin_texto_ni_titulo_no_se_dibuja():
    assert for_render(_clip(title="", overlays={"hook": {"on": True}})) is None


def test_una_placa_sin_nombre_no_se_dibuja():
    """A diferencia del gancho, no tiene de dónde sacar el texto."""
    assert for_render(_clip(overlays={"lower": {"on": True, "role": "Editor"}})) is None


def test_una_placa_con_nombre_si():
    capas = for_render(_clip(overlays={"lower": {"on": True, "name": "Ger"}}))
    assert capas["lower"]["name"] == "Ger"
    assert "hook" not in capas          # el gancho apagado no viaja


def test_usa_la_duracion_real_del_archivo():
    """Con jump cuts el clip dura menos que end - start."""
    capas = for_render(_clip(clip_duration=12.0,
                             overlays={"hook": {"on": True, "start": 30, "dur": 5}}))
    assert capas["hook"]["start"] <= 12.0


def test_describe_resume_lo_prendido():
    assert describe(_clip()) == ""
    texto = describe(_clip(overlays={"hook": {"on": True},
                                     "lower": {"on": True, "name": "Ger"}}))
    assert "gancho" in texto and "Ger" in texto


# ── Dos capas en el mismo lugar ───────────────────────────────────────────────

def test_avisa_si_el_gancho_abajo_se_pisa_con_la_placa():
    from modules.overlays import collision
    aviso = collision(_clip(overlays={
        "hook":  {"on": True, "position": "bottom", "start": 1.0, "dur": 5.0},
        "lower": {"on": True, "name": "Ger", "start": 3.0, "dur": 4.0},
    }))
    assert aviso and "3.0" in aviso and "6.0" in aviso


def test_no_avisa_si_no_coinciden_en_el_tiempo():
    from modules.overlays import collision
    assert collision(_clip(overlays={
        "hook":  {"on": True, "position": "bottom", "start": 0.0, "dur": 2.0},
        "lower": {"on": True, "name": "Ger", "start": 3.0, "dur": 4.0},
    })) is None


def test_no_avisa_con_el_gancho_arriba():
    from modules.overlays import collision
    assert collision(_clip(overlays={
        "hook":  {"on": True, "position": "top", "start": 1.0, "dur": 9.0},
        "lower": {"on": True, "name": "Ger", "start": 3.0, "dur": 4.0},
    })) is None


def test_no_avisa_con_una_sola_capa():
    from modules.overlays import collision
    assert collision(_clip(overlays={"hook": {"on": True, "position": "bottom"}})) is None
    assert collision(_clip()) is None


# ── Placas de apertura y cierre ───────────────────────────────────────────────

def test_una_placa_sin_titulo_no_se_dibuja():
    assert for_render(_clip(overlays={"intro": {"on": True, "subtitle": "solo bajada"}})) is None


def test_la_placa_de_apertura_viaja_con_su_titulo():
    capas = for_render(_clip(overlays={"intro": {"on": True, "title": "Canal de ejemplo"}}))
    assert capas["intro"]["title"] == "Canal de ejemplo"
    assert "outro" not in capas          # la apagada no viaja


def test_las_dos_placas_a_la_vez():
    capas = for_render(_clip(overlays={
        "intro": {"on": True, "title": "Canal"},
        "outro": {"on": True, "title": "Seguinos"},
    }))
    assert set(capas) == {"intro", "outro"}


def test_una_placa_no_puede_durar_mas_que_el_clip():
    """Duraría todo el clip: sería un video de una placa, no un clip."""
    capas = normalize({"intro": {"on": True, "title": "x", "dur": 90}}, clip_duration=12)
    assert capas["intro"]["dur"] <= 12


def test_el_oscurecido_se_mantiene_entre_0_y_1():
    assert normalize({"intro": {"dim": 5}})["intro"]["dim"] == 1.0
    assert normalize({"intro": {"dim": -3}})["intro"]["dim"] == 0.0
    assert normalize({"intro": {"dim": "mucho"}})["intro"]["dim"] == DEFAULT_CARD["dim"]


def test_por_default_la_placa_deja_ver_el_video():
    """El movimiento de atrás es lo que sostiene la atención mientras se lee."""
    assert 0 < DEFAULT_CARD["dim"] < 1


def test_avisa_si_la_placa_de_apertura_se_come_al_gancho():
    from modules.overlays import collision
    aviso = collision(_clip(overlays={
        "hook":  {"on": True, "start": 0.5, "dur": 3.0},
        "intro": {"on": True, "title": "Canal", "dur": 2.0},
    }))
    assert aviso and "apertura" in aviso


def test_no_avisa_si_el_gancho_entra_despues_de_la_placa():
    from modules.overlays import collision
    assert collision(_clip(overlays={
        "hook":  {"on": True, "start": 2.5, "dur": 3.0},
        "intro": {"on": True, "title": "Canal", "dur": 2.0},
    })) is None
