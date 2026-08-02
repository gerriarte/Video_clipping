"""
Edición guiada por el audio: dónde empieza y termina de verdad un clip, y qué
partes son silencio.

Los tiempos que elige Claude salen del VTT de YouTube, que es "rolling" y trae
uno o dos segundos de error: por eso hay clips que arrancan con media palabra o
cortan la última sílaba. Acá detectamos las pausas reales con ffmpeg y las usamos
para dos cosas:

  1. `snap_bounds`     — pegar inicio/fin a la pausa más cercana (respiración).
  2. `speech_segments` — sacar los silencios largos de adentro (jump cuts).

Las funciones que deciden son puras (reciben la lista de silencios): la única que
toca el disco es `detect_silences`.
"""

import re
import subprocess

# Umbral de "silencio". -32 dB deja pasar la respiración y el ruido de sala pero
# marca las pausas reales entre frases.
NOISE_DB = -32.0
MIN_SILENCE = 0.30

# Cuánto nos permitimos mover un borde buscando la pausa. Más de ~1.5 s ya cambia
# el contenido del clip, no lo acomoda.
SNAP_WINDOW = 1.5

# Aire que dejamos al pegar: un pelito antes de la primera palabra y un poco más
# al final para que la última no quede seca.
SNAP_PAD_LEAD = 0.10
SNAP_PAD_TAIL = 0.20

# Jump cuts: solo se saca el silencio si es largo (una pausa corta es ritmo, no
# relleno), y se deja `KEEP_PAD` de aire a cada lado para que no suene cortado.
JUMPCUT_MIN_SILENCE = 0.70
JUMPCUT_KEEP_PAD = 0.15
JUMPCUT_MIN_PIECE = 0.40

# Normalización de sonoridad al estándar de las redes (TikTok/IG/YouTube rondan
# los -14 LUFS). Sin esto cada episodio sale con un volumen distinto.
LOUDNORM_FILTER = "loudnorm=I=-14:TP=-1.5:LRA=11"


def detect_silences(
    video_path,
    start: float,
    end: float,
    noise_db: float = NOISE_DB,
    min_silence: float = MIN_SILENCE,
) -> list:
    """
    Silencios del tramo [start, end] como intervalos absolutos [(s, e), ...].

    Analiza solo ese tramo (seek + `-t`), así no cuesta nada aunque el episodio
    dure dos horas. Si ffmpeg falla devuelve [] y todo el pipeline sigue igual
    que antes (sin snap, sin jump cuts).
    """
    dur = max(0.0, float(end) - float(start))
    if dur <= 0:
        return []

    cmd = [
        "ffmpeg", "-hide_banner", "-nostats",
        "-ss", f"{float(start):.3f}", "-t", f"{dur:.3f}",
        "-i", str(video_path),
        "-map", "0:a:0",
        "-af", f"silencedetect=noise={noise_db}dB:d={min_silence}",
        "-f", "null", "-",
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    except Exception:
        return []

    return parse_silencedetect(r.stderr or "", offset=float(start), segment_end=float(end))


def parse_silencedetect(stderr: str, offset: float = 0.0, segment_end=None) -> list:
    """
    Convierte la salida de `silencedetect` en intervalos absolutos.

    ffmpeg imprime los tiempos relativos al tramo analizado, así que les sumamos
    `offset`. Un silencio que llega hasta el final del tramo no trae `silence_end`:
    lo cerramos en `segment_end`.
    """
    silences = []
    open_start = None
    for m in re.finditer(r"silence_(start|end):\s*(-?[\d.]+)", stderr):
        kind, value = m.group(1), float(m.group(2))
        if kind == "start":
            open_start = value
        elif open_start is not None:
            silences.append((open_start + offset, value + offset))
            open_start = None
    if open_start is not None and segment_end is not None:
        if segment_end > open_start + offset:
            silences.append((open_start + offset, float(segment_end)))
    return silences


def snap_bounds(
    start: float,
    end: float,
    silences: list,
    window: float = SNAP_WINDOW,
    min_duration: float = 3.0,
) -> tuple:
    """
    Corre inicio y fin hasta la pausa más cercana, si hay alguna a mano.

    - El inicio busca el FINAL de un silencio (arrancar justo cuando empieza a
      hablar) y se queda un pelín antes, para no comerse la primera consonante.
    - El fin busca el COMIENZO de un silencio (cerrar cuando terminó la frase) y
      se estira un poco, para que la última palabra no quede seca.

    Solo se mueve dentro de `window` segundos: más que eso ya sería cambiar el
    contenido del clip. Devuelve (start, end) — iguales a los de entrada si no
    hay una pausa razonable cerca.
    """
    # `prefer_earlier`/`prefer_later` sesgan hacia el lado que ALARGA el clip:
    # sumar un poco de aire es barato, comerse palabras no tiene arreglo.
    new_start = _closest([e for _s, e in silences], start, window, prefer="earlier")
    new_end   = _closest([s for s, _e in silences], end,   window, prefer="later")

    s = start if new_start is None else max(0.0, new_start - SNAP_PAD_LEAD)
    e = end if new_end is None else new_end + SNAP_PAD_TAIL

    # Nunca invertir ni dejar un clip inservible: ante la duda, los originales.
    if e - s < min_duration:
        return float(start), float(end)
    return float(s), float(e)


# Cuánto "descuento" tiene el lado que alarga el clip al comparar distancias:
# a igualdad de cercanía gana, y solo pierde si el otro está bastante más cerca.
_PREFER_FACTOR = 0.7


def _closest(candidates: list, target: float, window: float, prefer: str = ""):
    """
    Candidato más cercano a `target` dentro de ±window (None si no hay).

    `prefer` ("earlier" | "later") no filtra: solo pondera. El lado preferido
    compite con la distancia reducida, así que ante dos pausas parecidas se
    queda con la que no arriesga cortar voz.
    """
    best, best_score = None, None
    for c in candidates:
        d = abs(c - target)
        if d > window:
            continue
        score = d
        if (prefer == "earlier" and c <= target) or (prefer == "later" and c >= target):
            score = d * _PREFER_FACTOR
        if best_score is None or score < best_score:
            best, best_score = c, score
    return best


def speech_segments(
    start: float,
    end: float,
    silences: list,
    min_silence: float = JUMPCUT_MIN_SILENCE,
    keep_pad: float = JUMPCUT_KEEP_PAD,
    min_piece: float = JUMPCUT_MIN_PIECE,
) -> list:
    """
    Trozos con voz de [start, end], sacando los silencios largos de adentro.

    Solo se eliminan las pausas de más de `min_silence` (una pausa corta es
    ritmo, no relleno) y se les deja `keep_pad` de aire a cada lado para que el
    corte no suene abrupto. Los pedacitos más cortos que `min_piece` se descartan
    (serían un parpadeo).

    Devuelve [(s, e), ...] en orden. Si no hay nada que sacar, devuelve el tramo
    entero: quien llame puede comparar y no hacer nada.
    """
    start, end = float(start), float(end)
    if end <= start:
        return []

    cuts = []
    for s, e in sorted(silences):
        s, e = max(s, start), min(e, end)
        if e - s <= min_silence:
            continue
        # Dejamos aire a los costados del silencio.
        cs, ce = s + keep_pad, e - keep_pad
        if ce > cs:
            cuts.append((cs, ce))

    if not cuts:
        return [(start, end)]

    segments = []
    cursor = start
    for cs, ce in cuts:
        if cs > cursor:
            segments.append((cursor, cs))
        cursor = max(cursor, ce)
    if cursor < end:
        segments.append((cursor, end))

    segments = [(s, e) for s, e in segments if e - s >= min_piece]
    return segments or [(start, end)]


def segments_duration(segments: list) -> float:
    """Duración total de una lista de tramos."""
    return sum(max(0.0, e - s) for s, e in segments)
