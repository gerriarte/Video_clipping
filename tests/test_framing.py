import numpy as np
from modules.framing import crop_rect, crop_from_rect

A_916 = 1080 / 1920   # 0.5625
A_11 = 1.0
S_169 = 16 / 9        # fuente 16:9


def test_9x16_from_16x9_full_height_centered():
    r = crop_rect(1920, 1080, A_916, 0.5, 1.0)
    assert r["h"] == 1.0                       # cover: altura completa
    assert abs(r["w"] - 81 / 256) < 1e-3       # frac visible = target/source
    assert abs(r["x"] - (0.5 - r["w"] / 2)) < 1e-3  # centrado


def test_square_from_16x9():
    r = crop_rect(1920, 1080, A_11, 0.5, 1.0)
    assert abs(r["w"] - 0.5625) < 1e-3 and r["h"] == 1.0


def test_zoom_tightens_both_dims_proportionally():
    r1 = crop_rect(1920, 1080, A_11, 0.5, 1.0)
    r2 = crop_rect(1920, 1080, A_11, 0.5, 2.0)
    assert r2["w"] < r1["w"] and r2["h"] < r1["h"]
    assert abs(r2["w"] - r1["w"] / 2) < 1e-3
    assert abs(r2["h"] - r1["h"] / 2) < 1e-3


def test_clamps_within_bounds_right_edge():
    r = crop_rect(1920, 1080, A_916, 0.99, 1.0)
    assert r["x"] >= 0.0
    assert r["x"] + r["w"] <= 1.0 + 1e-6


def test_clamps_within_bounds_left_edge():
    r = crop_rect(1920, 1080, A_916, 0.0, 1.0)
    assert r["x"] == 0.0


def test_vertical_center_applies_when_zoomed():
    r = crop_rect(1920, 1080, A_11, 0.5, 2.0, center_y=0.2)
    assert r["y"] < 0.2  # centrado arriba
    r2 = crop_rect(1920, 1080, A_11, 0.5, 2.0, center_y=0.8)
    assert r2["y"] > r["y"]


def test_crop_from_rect_shape_matches():
    img = np.zeros((1080, 1920, 3), dtype=np.uint8)
    r = crop_rect(1920, 1080, A_916, 0.5, 1.0)
    out = crop_from_rect(img, r)
    assert out.shape[0] == 1080
    assert 0 < out.shape[1] < 1920
    # aspecto del recorte ≈ target
    assert abs(out.shape[1] / out.shape[0] - A_916) < 0.02


# ── El recorte manual está atado al formato con el que se hizo ────────────────

import config
from pathlib import Path
from modules.renderer import _resolve_encuadre


def manual_clip(fmt=None):
    c = {"crop_manual": True, "crop_rect": {"x": 0.3, "y": 0.0, "w": 0.5625, "h": 1.0}}
    if fmt:
        c["crop_fmt"] = fmt
    return c


def encuadre(clip, fmt):
    return _resolve_encuadre(Path("no-existe.mp4"), 10.0, fmt, config.FORMAT_PRESETS[fmt], clip)


def test_el_recorte_manual_se_usa_en_su_formato():
    enc = encuadre(manual_clip("1:1"), "1:1")
    assert enc["manual_crops"] == [{"x": 0.3, "y": 0.0, "w": 0.5625, "h": 1.0}]


def test_el_recorte_manual_de_otro_formato_se_ignora():
    # Un rect cuadrado (1:1) estirado a 9:16 deformaría la imagen: mejor auto.
    enc = encuadre(manual_clip("1:1"), "9:16")
    assert enc["manual_crops"] is None


def test_los_clips_viejos_sin_crop_fmt_siguen_funcionando():
    # Guardados antes de que existiera el campo: se asumen del formato actual.
    enc = encuadre(manual_clip(), "9:16")
    assert enc["manual_crops"] is not None
