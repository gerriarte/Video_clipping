"""
Tests de la lectura de imágenes.

El caso real: `clips/_previews/Automatización_con_IA…/f_001.jpg`. `cv2.imread`
devolvía `None` por la `ó`, la detección de caras medía cero en todos los frames
y la app informaba "sin caras el 100% del clip" con las caras a la vista en la
miniatura de al lado. Sin excepción y sin aviso: el peor tipo de bug.
"""

import pytest

from modules.imaging import imread

cv2 = pytest.importorskip("cv2", reason="OpenCV es opcional en este proyecto")
np = pytest.importorskip("numpy")


def _jpg(path):
    """Un JPEG chico escrito sin pasar por cv2 (que es justo lo que falla)."""
    img = np.full((20, 30, 3), 128, dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buf.tobytes())
    return path


def test_lee_una_ruta_normal(tmp_path):
    img = imread(_jpg(tmp_path / "frame.jpg"))
    assert img is not None
    assert img.shape[:2] == (20, 30)


def test_lee_una_ruta_con_acentos(tmp_path):
    """El caso que rompía: el video_id sale del título del episodio."""
    p = _jpg(tmp_path / "Automatización_con_IA" / "f_001.jpg")
    assert imread(p) is not None


@pytest.mark.parametrize("nombre", ["ñandú", "Español", "café ☕", "日本語"])
def test_lee_rutas_con_cualquier_cosa(tmp_path, nombre):
    assert imread(_jpg(tmp_path / nombre / "f.jpg")) is not None


def test_un_archivo_que_no_existe_devuelve_none(tmp_path):
    """Mismo contrato que cv2.imread: None, no excepción."""
    assert imread(tmp_path / "no-existe.jpg") is None


def test_un_archivo_vacio_devuelve_none(tmp_path):
    p = tmp_path / "vacio.jpg"
    p.write_bytes(b"")
    assert imread(p) is None


def test_un_archivo_que_no_es_imagen_devuelve_none(tmp_path):
    p = tmp_path / "texto.jpg"
    p.write_text("esto no es un jpeg", encoding="utf-8")
    assert imread(p) is None


def test_una_carpeta_devuelve_none(tmp_path):
    assert imread(tmp_path) is None


def test_es_el_reemplazo_de_cv2_imread_en_ascii(tmp_path):
    """Donde cv2.imread funciona, los dos tienen que dar lo mismo."""
    p = _jpg(tmp_path / "ascii.jpg")
    original = cv2.imread(str(p))
    assert original is not None  # si esto falla, el entorno es raro
    assert np.array_equal(imread(p), original)
