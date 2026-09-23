"""
Tests de la traducción clips ↔ pantallas.

El caso que motiva este archivo: durante meses el Paso 5 dibujó los captions en
un `text_area` que nunca se leía de vuelta. Editar un caption no hacía nada y el
CSV salía con el texto original de Claude. Mirando la pantalla no se veía;
`test_apply_publish_guarda_los_captions_editados` sí lo ve.
"""

from pathlib import Path

import pytest

import config
from modules.ui_state import (
    apply_gallery,
    apply_publish,
    clips_to_gallery,
    clips_to_publish,
    gallery_formats,
    normalize_format,
)


def _clip(**extra) -> dict:
    base = {
        "title": "Un título",
        "start": 10.0,
        "end": 70.0,
        "type": "insight",
        "reason": "porque sí",
        "formato": "9:16",
    }
    base.update(extra)
    return base


# ── normalize_format ──────────────────────────────────────────────────────────

def test_normalize_acepta_clave_label_y_legacy():
    assert normalize_format("split") == "split"
    assert normalize_format("9:16 vertical") == "9:16"      # legacy del estado viejo
    assert normalize_format("9:16 dividido") == "split"     # label que muestra la UI
    assert normalize_format("Original 16:9") == "16:9"


def test_normalize_cae_al_default_con_basura():
    for val in (None, "", "no existe", 42):
        assert normalize_format(val) == config.DEFAULT_FORMAT


def test_gallery_formats_cubre_todos_los_presets():
    formatos = gallery_formats()
    assert {f["key"] for f in formatos} == set(config.FORMAT_PRESETS)
    for f in formatos:
        assert f["aspect"] > 0
        assert f["short"]


# ── clips_to_gallery ──────────────────────────────────────────────────────────

def test_gallery_payload_lleva_la_evidencia_del_analisis():
    clips = [_clip()]
    analyses = {0: {
        "samples": 23, "two_shot_ratio": 0.78, "solo_ratio": 0.1,
        "empty_ratio": 0.12, "mixed": False, "suggestion": "split",
        "centers_x": [0.3, 0.7],
        "thumbs": [(Path("a.jpg"), "arranque · 0:10")],
    }}
    fila = clips_to_gallery(clips, analyses, url_for=lambda p: f"http://x/{p.name}")[0]

    assert fila["id"] == 0
    assert fila["shot"]["twoShot"] == 0.78
    assert fila["shot"]["suggestion"] == "split"
    assert fila["shot"]["centersX"] == [0.3, 0.7]
    assert fila["thumbs"] == [{"url": "http://x/a.jpg", "label": "arranque · 0:10"}]


def test_gallery_payload_sin_analisis_no_inventa_evidencia():
    fila = clips_to_gallery([_clip()], {}, url_for=lambda p: "")[0]
    assert fila["shot"] is None
    assert fila["thumbs"] == []


def test_gallery_payload_marca_seleccionado_por_defecto():
    """Un clip sin la clave entra al corte: es el default histórico."""
    assert clips_to_gallery([_clip()], {}, url_for=lambda p: "")[0]["selected"] is True
    sin = clips_to_gallery([_clip(_selected=False)], {}, url_for=lambda p: "")[0]
    assert sin["selected"] is False


def test_gallery_payload_usa_el_clip_cortado_si_se_lo_dan():
    fila = clips_to_gallery(
        [_clip(clip_path="c.mp4")], {}, url_for=lambda p: "",
        clip_url=lambda c: f"http://x/{c['clip_path']}",
    )[0]
    assert fila["clipUrl"] == "http://x/c.mp4"


# ── apply_gallery ─────────────────────────────────────────────────────────────

def test_apply_gallery_vuelca_lo_editado():
    clips = [_clip()]
    cambio = apply_gallery(
        [{"id": 0, "title": "Otro", "format": "split", "selected": False,
          "start": 12.5, "end": 68.0, "type": "humor",
          "speakerFollow": False, "followShot": True}],
        clips,
    )
    assert cambio is True
    assert clips[0]["title"] == "Otro"
    assert clips[0]["formato"] == "split"
    assert clips[0]["_selected"] is False
    assert clips[0]["start"] == 12.5
    assert clips[0]["type"] == "humor"
    assert clips[0]["follow_shot"] is True


def test_apply_gallery_sin_cambios_no_toca_nada():
    """Sin esto, cada rerun escribiría el estado en disco al pedo."""
    clips = [_clip(_selected=True, speaker_follow=True, follow_shot=False)]
    fila = clips_to_gallery(clips, {}, url_for=lambda p: "")[0]
    assert apply_gallery([fila], clips) is False


def test_apply_gallery_respeta_el_encuadre_manual():
    """El encuadre se edita en los Pasos 4 y 5: la galería no debe pisarlo."""
    clips = [_clip(crop_manual=True, crop_center=0.8, crop_rect=[1, 2, 3, 4])]
    apply_gallery([{"id": 0, "format": "1:1", "title": "x"}], clips)
    assert clips[0]["crop_manual"] is True
    assert clips[0]["crop_center"] == 0.8
    assert clips[0]["crop_rect"] == [1, 2, 3, 4]


def test_apply_gallery_ignora_posiciones_que_no_existen():
    clips = [_clip()]
    assert apply_gallery([{"id": 7, "title": "x"}, {"id": -1}, {"id": "no"}], clips) is False
    assert clips[0]["title"] == "Un título"


def test_apply_gallery_normaliza_un_formato_raro():
    clips = [_clip()]
    apply_gallery([{"id": 0, "format": "inventado"}], clips)
    assert clips[0]["formato"] == config.DEFAULT_FORMAT


# ── Paso 5 ────────────────────────────────────────────────────────────────────

def test_publish_payload_usa_la_duracion_real_del_archivo():
    """Con jump cuts el clip dura menos que end - start."""
    fila = clips_to_publish([_clip(clip_duration=52.3)], url_for=lambda p: "")[0]
    assert fila["duration"] == pytest.approx(52.3)
    sin = clips_to_publish([_clip()], url_for=lambda p: "")[0]
    assert sin["duration"] == pytest.approx(60.0)


def test_publish_payload_lleva_las_tres_plataformas_aunque_falten():
    fila = clips_to_publish([_clip(captions={"tiktok": "hola"})], url_for=lambda p: "")[0]
    assert fila["captions"] == {"tiktok": "hola", "instagram": "", "youtube": ""}


def test_publish_payload_marca_el_clip_sin_render():
    fila = clips_to_publish([_clip()], url_for=lambda p: "")[0]
    assert fila["videoUrl"] == ""


def test_apply_publish_guarda_los_captions_editados():
    """El bug que este archivo existe para que no vuelva."""
    clips = [_clip(captions={"tiktok": "original", "instagram": "ig", "youtube": "yt"})]
    cambio = apply_publish(
        [{"id": 0, "format": "9:16",
          "captions": {"tiktok": "editado a mano", "instagram": "ig", "youtube": "yt"}}],
        clips,
    )
    assert cambio is True
    assert clips[0]["captions"]["tiktok"] == "editado a mano"
    assert clips[0]["captions"]["instagram"] == "ig"


def test_apply_publish_no_borra_plataformas_que_no_vinieron():
    clips = [_clip(captions={"tiktok": "tt", "instagram": "ig", "youtube": "yt"})]
    apply_publish([{"id": 0, "format": "9:16", "captions": {"tiktok": "nuevo"}}], clips)
    assert clips[0]["captions"] == {"tiktok": "nuevo", "instagram": "ig", "youtube": "yt"}


def test_apply_publish_cambia_el_formato():
    clips = [_clip(captions={})]
    assert apply_publish([{"id": 0, "format": "1:1", "captions": {}}], clips) is True
    assert clips[0]["formato"] == "1:1"


def test_apply_publish_sin_cambios_no_toca_nada():
    clips = [_clip(captions={"tiktok": "tt", "instagram": "ig", "youtube": "yt"})]
    fila = clips_to_publish(clips, url_for=lambda p: "")[0]
    assert apply_publish([fila], clips) is False


def test_ida_y_vuelta_no_deforma_el_clip():
    """Lo que sale a la pantalla y vuelve sin tocarse tiene que ser lo mismo."""
    clips = [_clip(_selected=True, speaker_follow=False, follow_shot=True,
                   captions={"tiktok": "a", "instagram": "b", "youtube": "c"})]
    antes = dict(clips[0])
    apply_gallery(clips_to_gallery(clips, {}, url_for=lambda p: ""), clips)
    apply_publish(clips_to_publish(clips, url_for=lambda p: ""), clips)
    assert clips[0] == antes
