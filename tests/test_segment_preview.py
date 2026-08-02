"""Análisis de la toma del tramo: composición en el tiempo y formato sugerido."""

from modules.segment_preview import (
    is_mixed,
    pick_thumbs,
    sample_count,
    sample_times,
    segment_key,
    shot_segments,
    suggest_format,
    summarize_shots,
)


def face(cx, cy=0.4, w=0.12, h=0.2):
    return {"cx": cx, "cy": cy, "w": w, "h": h}


def frames(pattern):
    """'2' → frame con dos caras, '1' → una, '0' → ninguna."""
    out = []
    for ch in pattern:
        if ch == "2":
            out.append([face(0.3), face(0.75)])
        elif ch == "1":
            out.append([face(0.3)])
        else:
            out.append([])
    return out


# ── summarize_shots ───────────────────────────────────────────────────────────

def test_mide_la_proporcion_de_tiempo_con_dos_personas():
    # La mitad del clip es plano de dos; la otra mitad, primer plano de uno.
    s = summarize_shots(frames("2222111122221111"))
    assert s["two_shot_ratio"] == 0.5
    assert s["solo_ratio"] == 0.5
    assert s["samples"] == 16


def test_cuenta_las_personas_distintas_del_tramo():
    s = summarize_shots(frames("2222111122221111"))
    assert s["people"] == 2
    assert len(s["centers_x"]) == 2


def test_una_aparicion_suelta_no_cuenta_como_persona():
    # La segunda cara sale en 1 de 16 muestras: es ruido del clasificador.
    s = summarize_shots(frames("2111111111111111"))
    assert s["people"] == 1
    assert s["two_shot_ratio"] < 0.1


def test_alguien_que_entra_a_mitad_de_clip_si_cuenta():
    s = summarize_shots(frames("1111222222221111"))
    assert s["people"] == 2


def test_tramo_sin_caras():
    s = summarize_shots(frames("0000"))
    assert s["empty_ratio"] == 1.0
    assert s["people"] == 0
    assert s["two_shot_ratio"] == 0.0


def test_sin_muestras():
    assert summarize_shots([])["samples"] == 0


def test_timeline_trae_un_punto_por_muestra_con_su_tiempo():
    s = summarize_shots(frames("121"), times=[10.0, 20.0, 30.0])
    assert [p["t"] for p in s["timeline"]] == [10.0, 20.0, 30.0]
    assert [p["n"] for p in s["timeline"]] == [1, 2, 1]


def test_caras_muy_juntas_son_la_misma_persona():
    juntas = [[face(0.50), face(0.54)]] * 8
    s = summarize_shots(juntas)
    assert s["people"] == 1
    assert s["two_shot_ratio"] == 0.0


# ── suggest_format / is_mixed ─────────────────────────────────────────────────

def test_sugiere_split_cuando_predomina_el_plano_de_dos():
    assert suggest_format(summarize_shots(frames("2222222211"))) == "split"


def test_sugiere_vertical_cuando_predomina_una_persona():
    assert suggest_format(summarize_shots(frames("1111111122"))) == "9:16"


def test_sugiere_no_recortar_si_casi_no_hay_caras():
    assert suggest_format(summarize_shots(frames("0000000011"))) == "16:9"


def test_marca_mixto_cuando_la_toma_cambia():
    # 30% del clip con dos personas: ni split claro ni una sola persona.
    s = summarize_shots(frames("2221111111"))
    assert is_mixed(s)
    assert suggest_format(s) == "9:16"


def test_no_marca_mixto_cuando_el_plano_es_estable():
    assert not is_mixed(summarize_shots(frames("1111111111")))
    assert not is_mixed(summarize_shots(frames("2222222222")))


# ── muestreo ──────────────────────────────────────────────────────────────────

def test_mas_duracion_mas_muestras_hasta_el_tope():
    assert sample_count(30) < sample_count(60)
    assert sample_count(600) == sample_count(3000)  # tope


def test_tramo_corto_igual_saca_algunas_muestras():
    assert sample_count(4) >= 4


def test_tramo_vacio_no_saca_muestras():
    assert sample_count(0) == 0


def test_los_tiempos_caen_dentro_del_tramo_y_en_orden():
    ts = sample_times(100.0, 200.0, 5)
    assert len(ts) == 5
    assert all(100.0 <= t <= 200.0 for t in ts)
    assert ts == sorted(ts)


# ── thumbs ────────────────────────────────────────────────────────────────────

def test_elige_la_muestra_con_mas_gente_para_el_medio():
    fr = [f"f{i}" for i in range(5)]
    s = summarize_shots(frames("11211"), times=[1.0, 2.0, 3.0, 4.0, 5.0])
    thumbs = pick_thumbs(fr, s, s and [p["t"] for p in s["timeline"]])
    # arranque, el frame con 2 personas, final
    assert [t[0] for t in thumbs] == ["f0", "f2", "f4"]
    assert "2+ personas" in thumbs[1][1]


def test_sin_frames_no_hay_thumbs():
    assert pick_thumbs([], {"timeline": []}, []) == []


# ── segment_key ───────────────────────────────────────────────────────────────

def test_segment_key_es_estable_y_sin_puntos():
    k = segment_key("abc123", 12.345, 40.0)
    assert k == segment_key("abc123", 12.345, 40.0)
    assert "." not in k


def test_segment_key_distingue_tramos():
    assert segment_key("v", 0, 10) != segment_key("v", 0, 11)


def test_segment_key_limpia_caracteres_de_ruta():
    assert "/" not in segment_key("a/b\\c", 0, 1)


# ── shot_segments (seguir la toma) ────────────────────────────────────────────

def timeline(pattern, step=3.0):
    """'2'/'1'/'0' por muestra, espaciadas `step` segundos."""
    out = []
    for i, ch in enumerate(pattern):
        n = int(ch)
        xs = {2: [0.3, 0.75], 1: [0.3], 0: []}[n]
        out.append({"t": step * (i + 0.5), "n": n, "x": xs})
    return out


def test_un_clip_de_un_solo_plano_da_un_tramo():
    segs = shot_segments(timeline("2222222222"), duration=30.0)
    assert len(segs) == 1
    assert segs[0]["kind"] == "two"
    assert segs[0]["start"] == 0.0 and segs[0]["end"] == 30.0


def test_detecta_el_cambio_de_plano():
    segs = shot_segments(timeline("2222211111"), duration=30.0)
    assert [s["kind"] for s in segs] == ["two", "solo"]
    # Los tramos son contiguos y cubren todo el clip.
    assert segs[0]["end"] == segs[1]["start"]
    assert segs[-1]["end"] == 30.0


def test_un_parpadeo_no_genera_un_tramo():
    # Una sola muestra distinta (3 s) no llega al mínimo: se funde.
    segs = shot_segments(timeline("2222122222"), duration=30.0, min_segment=5.0)
    assert len(segs) == 1
    assert segs[0]["kind"] == "two"


def test_las_muestras_sin_caras_heredan_el_plano_anterior():
    segs = shot_segments(timeline("2222002222"), duration=30.0)
    assert len(segs) == 1
    assert segs[0]["kind"] == "two"


def test_el_tramo_de_dos_trae_dos_posiciones_ordenadas():
    segs = shot_segments(timeline("2222222222"), duration=30.0)
    xs = segs[0]["xs"]
    assert len(xs) == 2
    assert xs[0] < xs[1]


def test_el_tramo_solo_trae_una_posicion():
    segs = shot_segments(timeline("1111111111"), duration=30.0)
    assert len(segs[0]["xs"]) == 1


def test_sin_timeline_no_hay_tramos():
    assert shot_segments([], duration=30.0) == []
    assert shot_segments(timeline("111"), duration=0) == []
