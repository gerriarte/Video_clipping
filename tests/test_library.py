"""
Tests del listado de material.

Lo que más importa: que no ofrezca como fuente un archivo que generó la propia
app. Elegir un `proxy480` significaría cortar y renderizar el episodio entero a
partir de una copia de 480p sin que nada lo avise.
"""

import os

from modules.library import find_videos, is_source_video, label_for


def _video(dir_path, nombre, mb=1, edad=0):
    p = dir_path / nombre
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"0" * int(mb * 1024 * 1024))
    if edad:
        t = p.stat().st_mtime - edad
        os.utime(p, (t, t))
    return p


def test_encuentra_videos_en_subcarpetas(tmp_path):
    _video(tmp_path, "uno.mp4")
    _video(tmp_path / "Episodio 3", "dos.mkv")
    nombres = {v["name"] for v in find_videos(tmp_path)}
    assert nombres == {"uno.mp4", "dos.mkv"}


def test_ignora_lo_que_no_es_video(tmp_path):
    _video(tmp_path, "video.mp4")
    (tmp_path / "notas.txt").write_text("x", encoding="utf-8")
    (tmp_path / "subs.vtt").write_text("x", encoding="utf-8")
    assert [v["name"] for v in find_videos(tmp_path)] == ["video.mp4"]


def test_no_ofrece_el_proxy_que_genera_la_app(tmp_path):
    """El proxy es 480p: cortar desde ahí arruinaría el render sin avisar."""
    _video(tmp_path, "episodio.mp4")
    _video(tmp_path, "episodio.proxy480.mp4")
    assert [v["name"] for v in find_videos(tmp_path)] == ["episodio.mp4"]


def test_no_entra_a_las_carpetas_de_trabajo(tmp_path):
    _video(tmp_path, "bueno.mp4")
    _video(tmp_path / "_previews", "frame.mp4")
    _video(tmp_path / "node_modules" / "algo", "ruido.mp4")
    assert [v["name"] for v in find_videos(tmp_path)] == ["bueno.mp4"]


def test_ordena_del_mas_nuevo_al_mas_viejo(tmp_path):
    _video(tmp_path, "viejo.mp4", edad=10_000)
    _video(tmp_path, "nuevo.mp4", edad=10)
    _video(tmp_path, "medio.mp4", edad=5_000)
    assert [v["name"] for v in find_videos(tmp_path)] == ["nuevo.mp4", "medio.mp4", "viejo.mp4"]


def test_respeta_el_limite(tmp_path):
    for i in range(8):
        _video(tmp_path, f"v{i}.mp4", edad=i * 100)
    assert len(find_videos(tmp_path, limit=3)) == 3


def test_una_carpeta_que_no_existe_no_rompe(tmp_path):
    """La ruta la escribe el usuario: equivocarse no puede tirar la pantalla."""
    assert find_videos(tmp_path / "no-existe") == []
    assert find_videos("") == []


def test_un_archivo_en_vez_de_una_carpeta_no_rompe(tmp_path):
    p = _video(tmp_path, "suelto.mp4")
    assert find_videos(p) == []


def test_la_etiqueta_dice_nombre_origen_y_peso(tmp_path):
    _video(tmp_path / "Episodio 3", "charla.mp4", mb=2)
    texto = label_for(find_videos(tmp_path)[0])
    assert "charla.mp4" in texto
    assert "Episodio 3" in texto
    assert "MB" in texto


def test_is_source_video_por_extension():
    from pathlib import Path
    assert is_source_video(Path("a/b.MP4"))
    assert is_source_video(Path("a/b.mkv"))
    assert not is_source_video(Path("a/b.jpg"))
    assert not is_source_video(Path("a/b.mp4.vtt"))
