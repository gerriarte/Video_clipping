"""Bordes guiados por audio, jump cuts y armado del filtro de concatenación."""

from modules.audio_edit import (
    SNAP_PAD_LEAD,
    SNAP_PAD_TAIL,
    parse_silencedetect,
    segments_duration,
    snap_bounds,
    speech_segments,
)
from modules.clipper import build_concat_filter


# ── parse_silencedetect ───────────────────────────────────────────────────────

STDERR = """
[silencedetect @ 0000] silence_start: 1.234
[silencedetect @ 0000] silence_end: 2.500 | silence_duration: 1.266
[silencedetect @ 0000] silence_start: 8.000
[silencedetect @ 0000] silence_end: 8.750 | silence_duration: 0.750
"""


def test_parsea_pares_de_silencio():
    assert parse_silencedetect(STDERR) == [(1.234, 2.5), (8.0, 8.75)]


def test_suma_el_offset_del_tramo_analizado():
    # ffmpeg reporta relativo al tramo; los tiempos tienen que volver a absolutos.
    assert parse_silencedetect(STDERR, offset=100.0)[0] == (101.234, 102.5)


def test_silencio_abierto_al_final_se_cierra_en_el_borde():
    out = parse_silencedetect("silence_start: 5.0\n", offset=0.0, segment_end=9.0)
    assert out == [(5.0, 9.0)]


def test_silencio_abierto_sin_borde_conocido_se_descarta():
    assert parse_silencedetect("silence_start: 5.0\n") == []


def test_sin_silencios():
    assert parse_silencedetect("nada que ver aquí") == []


# ── snap_bounds ───────────────────────────────────────────────────────────────

def test_inicio_se_pega_al_final_del_silencio():
    # Silencio 9.0–10.0: el clip debería arrancar cuando vuelve la voz.
    s, e = snap_bounds(10.4, 40.0, [(9.0, 10.0), (39.0, 40.5)])
    assert abs(s - (10.0 - SNAP_PAD_LEAD)) < 1e-6


def test_fin_se_pega_al_comienzo_del_silencio():
    s, e = snap_bounds(10.4, 40.0, [(9.0, 10.0), (39.0, 40.5)])
    assert abs(e - (39.0 + SNAP_PAD_TAIL)) < 1e-6


def test_no_se_mueve_si_la_pausa_esta_lejos():
    # Única pausa a 10 s de distancia: fuera de la ventana, no se toca nada.
    assert snap_bounds(100.0, 130.0, [(50.0, 51.0)]) == (100.0, 130.0)


def test_sin_silencios_devuelve_los_originales():
    assert snap_bounds(5.0, 20.0, []) == (5.0, 20.0)


def test_prefiere_alargar_ante_distancias_parecidas():
    # Dos pausas casi igual de cerca del inicio: gana la anterior, que no
    # arriesga comerse el arranque de la frase.
    s, _e = snap_bounds(20.0, 60.0, [(18.6, 19.0), (20.9, 21.4)])
    assert s < 20.0


def test_no_deja_un_clip_mas_corto_que_el_minimo():
    # Pegar los dos bordes dejaría ~2 s de clip: se descarta el ajuste entero.
    silences = [(10.5, 11.4), (13.0, 14.0)]
    assert snap_bounds(10.0, 15.0, silences, min_duration=5.0) == (10.0, 15.0)


# ── speech_segments ───────────────────────────────────────────────────────────

def test_saca_el_silencio_largo_del_medio():
    segs = speech_segments(0.0, 30.0, [(10.0, 13.0)])
    assert len(segs) == 2
    assert segs[0][0] == 0.0 and segs[-1][1] == 30.0
    assert segments_duration(segs) < 30.0


def test_respeta_las_pausas_cortas():
    # 0.4 s es ritmo, no relleno: el tramo queda entero.
    assert speech_segments(0.0, 30.0, [(10.0, 10.4)]) == [(0.0, 30.0)]


def test_deja_aire_a_los_costados_del_corte():
    segs = speech_segments(0.0, 30.0, [(10.0, 13.0)])
    # El corte no arranca exactamente donde empieza el silencio.
    assert segs[0][1] > 10.0
    assert segs[1][0] < 13.0


def test_silencio_al_borde_no_genera_tramos_vacios():
    segs = speech_segments(0.0, 30.0, [(0.0, 3.0), (28.0, 30.0)])
    assert all(e > s for s, e in segs)
    assert segments_duration(segs) < 30.0


def test_ignora_silencios_fuera_del_tramo():
    assert speech_segments(10.0, 20.0, [(0.0, 5.0), (50.0, 60.0)]) == [(10.0, 20.0)]


def test_tramo_invalido_no_devuelve_nada():
    assert speech_segments(20.0, 20.0, []) == []


# ── build_concat_filter ───────────────────────────────────────────────────────

def test_filtro_usa_tiempos_relativos_al_seek():
    f = build_concat_filter([(100.0, 105.0), (110.0, 115.0)], base=100.0, loudness=False)
    assert "trim=start=0.000:end=5.000" in f
    assert "trim=start=10.000:end=15.000" in f


def test_filtro_concatena_todos_los_tramos():
    f = build_concat_filter([(0.0, 1.0), (2.0, 3.0), (4.0, 5.0)], base=0.0, loudness=False)
    assert "concat=n=3:v=1:a=1[v][a]" in f


def test_filtro_agrega_loudnorm_al_final():
    f = build_concat_filter([(0.0, 1.0), (2.0, 3.0)], base=0.0, loudness=True)
    assert "concat=n=2:v=1:a=1[v][araw]" in f
    assert "loudnorm" in f.split("[araw]")[-1]


def test_cada_trozo_de_audio_lleva_fundido():
    # Sin fundido los empalmes hacen click.
    f = build_concat_filter([(0.0, 2.0), (3.0, 5.0)], base=0.0)
    assert f.count("afade=t=in") == 2
    assert f.count("afade=t=out") == 2
