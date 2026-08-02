"""
Previsualización y análisis del tramo ANTES de elegir el formato.

En el Paso 3 el usuario elige 9:16 / 1:1 / 16:9 / split cuando el clip todavía no
se cortó, así que no hay nada que mirar: la decisión se toma a ciegas. Acá
sacamos fotos del tramo (una sola pasada de ffmpeg) y analizamos **cómo cambia la
toma a lo largo del clip**, no un frame suelto.

Por qué muestreo denso: con 3 fotos en 70 s, un episodio que alterna plano
general y primer plano da cualquier cosa. Con una muestra cada ~3 s se puede
decir algo objetivo: "hay dos personas en el 50% del clip".

Sobre el detector: se probó MediaPipe FaceLandmarker (el que usa
`layout_detector` sobre el clip ya cortado) y en estos planos generales devuelve
0 caras donde a ojo hay dos — su detector es de corto alcance y acá la gente está
lejos y de perfil. Haar frontal + perfil, a 480 px, es el que acierta.
"""

import glob
import json
import math
import shutil
import subprocess
from pathlib import Path

from modules.layout_detector import _cluster_by_x

# Una muestra cada ~3 s: suficiente para ver los cambios de toma sin que el
# análisis cueste más que el corte.
SAMPLE_INTERVAL = 2.8
MAX_SAMPLES = 24
MIN_SAMPLES = 4

# Ancho al que se extraen las muestras. A 720 px el clasificador empieza a ver
# caras en los peluches del set; a 480 es más limpio (y más rápido).
FRAME_WIDTH = 480

# Cara mínima considerada válida (fracción del ancho/alto del frame). Filtra
# ruido del clasificador (manchas del fondo detectadas como caras).
MIN_FACE_FRAC = 0.05

# Dos caras cuyos centros X estén más cerca que esto son la MISMA persona
# (mismo valor que usa layout_detector para el split).
CLUSTER_X_TOL = 0.12

# A partir de qué porcentaje del clip con dos caras conviene el split, y desde
# cuál avisar que la toma cambia (candidato a formato mixto).
SPLIT_RATIO = 0.45
MIXED_RATIO = 0.20

# Si casi no hay caras (pantalla compartida, plano muy abierto), no recortar.
EMPTY_RATIO = 0.60


def preview_dir(base_dir=None) -> Path:
    """Carpeta donde se cachean los frames de preview."""
    if base_dir is None:
        import config
        base_dir = config.CLIPS_DIR
    d = Path(base_dir) / "_previews"
    d.mkdir(parents=True, exist_ok=True)
    return d


def segment_key(video_id: str, start: float, end: float) -> str:
    """Nombre estable para cachear los frames de un tramo."""
    vid = "".join(ch for ch in str(video_id or "video") if ch.isalnum() or ch in "-_")
    return f"{vid}_{float(start):.2f}-{float(end):.2f}".replace(".", "p")


def sample_count(duration: float) -> int:
    """Cuántas muestras se sacan de un tramo de `duration` segundos."""
    if duration <= 0:
        return 0
    n = int(math.floor(duration / SAMPLE_INTERVAL))
    return max(MIN_SAMPLES, min(MAX_SAMPLES, n or MIN_SAMPLES))


def extract_segment_frames(
    video_path,
    start: float,
    end: float,
    video_id: str = "video",
    cache_dir=None,
    width: int = FRAME_WIDTH,
) -> list:
    """
    Muestras del tramo [start, end] del video COMPLETO (sin cortar), en UNA sola
    pasada de ffmpeg (~1 s para 24 frames de un episodio de 2 h).

    Usa seek rápido (`-ss` antes de `-i`) y cachea en disco: la segunda vez que
    se abre el preview es instantáneo. Devuelve las rutas en orden temporal.
    """
    video_path = Path(video_path)
    dur = max(0.0, float(end) - float(start))
    n = sample_count(dur)
    if not n:
        return []

    out_dir = preview_dir(cache_dir) / segment_key(video_id, start, end)
    cached = sorted(glob.glob(str(out_dir / "f_*.jpg")))
    if cached:
        return [Path(p) for p in cached]
    if not video_path.exists():
        return []

    out_dir.mkdir(parents=True, exist_ok=True)
    interval = dur / n
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{float(start):.3f}", "-t", f"{dur:.3f}",
        "-i", str(video_path),
        "-vf", f"fps=1/{interval:.4f},scale={int(width)}:-2",
        "-q:v", "3",
        "-loglevel", "error",
        str(out_dir / "f_%03d.jpg"),
    ]
    try:
        subprocess.run(cmd, capture_output=True)
    except Exception:
        return []

    frames = [Path(p) for p in sorted(glob.glob(str(out_dir / "f_*.jpg")))]
    if not frames:
        # Sin frames no hay nada que cachear; que el próximo intento reintente.
        shutil.rmtree(out_dir, ignore_errors=True)
    return frames


def sample_times(start: float, end: float, n: int) -> list:
    """Momentos (absolutos) que representan cada muestra."""
    if n <= 0:
        return []
    step = (float(end) - float(start)) / n
    return [round(float(start) + step * (i + 0.5), 2) for i in range(n)]


# ──────────────────────────────────────────────────────────────────────────────
# Detección de caras
# ──────────────────────────────────────────────────────────────────────────────

def _cascades(cv2):
    """
    Clasificadores Haar (frontal + perfil) con su `minNeighbors`.

    El de perfil evita perder a un host que mira al otro y no a cámara — justo el
    caso del split — pero con el umbral estricto del frontal (5) se le escapa; con
    3 la encuentra. Los falsos positivos que eso agrega los diluye el muestreo:
    lo que importa es en qué porcentaje del clip aparece cada persona.
    """
    base = cv2.data.haarcascades
    out = []
    for name, min_neighbors in (
        ("haarcascade_frontalface_default.xml", 5),
        ("haarcascade_profileface.xml", 3),
    ):
        c = cv2.CascadeClassifier(base + name)
        if not c.empty():
            out.append((name, c, min_neighbors))
    return out


def detect_faces(frame_path) -> list:
    """
    Caras de un frame como fracciones 0–1: [{"cx", "cy", "w", "h"}, ...].

    Corre frontal y perfil (y el perfil también sobre la imagen espejada, porque
    ese clasificador solo mira hacia un lado) y fusiona las detecciones repetidas.
    """
    try:
        import cv2
    except ImportError:
        return []

    img = cv2.imread(str(frame_path))
    if img is None:
        return []
    h, w = img.shape[:2]
    if not h or not w:
        return []

    # Sin equalizeHist a propósito: en estos sets (luces de estudio, fondos
    # oscuros) ecualizar hacía perder caras de perfil.
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    flipped = cv2.flip(gray, 1)
    min_size = (max(16, int(w * MIN_FACE_FRAC)), max(16, int(h * MIN_FACE_FRAC)))

    raw = []
    for name, cascade, min_neighbors in _cascades(cv2):
        images = [(gray, False)]
        if "profile" in name:
            # El clasificador de perfil solo mira hacia un lado: la imagen
            # espejada cubre a quien está girado para el otro.
            images.append((flipped, True))
        for image, is_flipped in images:
            try:
                found = cascade.detectMultiScale(
                    image, scaleFactor=1.1, minNeighbors=min_neighbors,
                    minSize=min_size,
                )
            except Exception:
                continue
            for (fx, fy, fw, fh) in found:
                cx = (fx + fw / 2) / w
                if is_flipped:
                    cx = 1.0 - cx
                raw.append({
                    "cx": float(cx),
                    "cy": float((fy + fh / 2) / h),
                    "w":  float(fw / w),
                    "h":  float(fh / h),
                })
    return _merge_faces(raw)


def _merge_faces(faces: list) -> list:
    """Fusiona detecciones solapadas (la misma cara vista por dos clasificadores)."""
    merged = []
    for f in sorted(faces, key=lambda d: d["w"] * d["h"], reverse=True):
        dup = False
        for m in merged:
            if (abs(f["cx"] - m["cx"]) < max(m["w"], 0.05) * 0.8 and
                    abs(f["cy"] - m["cy"]) < max(m["h"], 0.05) * 0.8):
                dup = True
                break
        if not dup:
            merged.append(f)
    return sorted(merged, key=lambda d: d["cx"])


def _nearest(x: float, centers: list) -> int:
    """Índice del cluster más cercano a `x`."""
    best, bd = 0, float("inf")
    for i, c in enumerate(centers):
        d = abs(x - c)
        if d < bd:
            bd, best = d, i
    return best


# ──────────────────────────────────────────────────────────────────────────────
# Cómo es la toma a lo largo del clip
# ──────────────────────────────────────────────────────────────────────────────

def summarize_shots(frames_faces: list, times: list | None = None) -> dict:
    """
    Resume la composición del tramo a partir de las caras de cada muestra.

    En vez de "cuántas personas hay" (que en un clip con cambios de plano no
    tiene una sola respuesta), devuelve **cuánto tiempo** hay dos, una o ninguna:

      two_shot_ratio : fracción de muestras con 2+ caras
      solo_ratio     : fracción con exactamente 1
      empty_ratio    : fracción sin caras
      people         : personas distintas vistas en el tramo (clusters por X)
      timeline       : [{"t", "n", "x": [...]}, ...] para mostrar evidencia y,
                       más adelante, cambiar de formato dentro del clip.
    """
    frames_faces = [f for f in frames_faces if f is not None]
    n = len(frames_faces)
    empty = {
        "samples": 0, "two_shot_ratio": 0.0, "solo_ratio": 0.0, "empty_ratio": 1.0,
        "people": 0, "people_max": 0, "centers_x": [], "timeline": [],
    }
    if not n:
        return empty

    all_x = [face["cx"] for faces in frames_faces for face in faces]
    centers = _cluster_by_x(all_x, CLUSTER_X_TOL) if all_x else []

    timeline, counts = [], []
    for i, faces in enumerate(frames_faces):
        groups = {_nearest(f["cx"], centers) for f in faces} if centers else set()
        counts.append(len(groups))
        timeline.append({
            "t": (times[i] if times and i < len(times) else float(i)),
            "n": len(groups),
            "x": sorted(round(f["cx"], 3) for f in faces),
        })

    two = sum(1 for c in counts if c >= 2)
    one = sum(1 for c in counts if c == 1)
    zero = sum(1 for c in counts if c == 0)

    # Una persona "existe" si aparece en al menos un cuarto de las muestras: así
    # un falso positivo suelto no suma, pero alguien que entra a mitad de clip sí.
    min_support = max(1, math.ceil(n * 0.25))
    kept = []
    for i, cx in enumerate(centers):
        support = sum(
            1 for faces in frames_faces
            if any(_nearest(f["cx"], centers) == i for f in faces)
        )
        if support >= min_support:
            kept.append(cx)

    return {
        "samples":        n,
        "two_shot_ratio": round(two / n, 3),
        "solo_ratio":     round(one / n, 3),
        "empty_ratio":    round(zero / n, 3),
        "people":         len(kept),
        "people_max":     max(counts) if counts else 0,
        "centers_x":      [round(c, 3) for c in kept],
        "timeline":       timeline,
    }


def suggest_format(summary: dict) -> str:
    """
    Formato sugerido según cómo es la toma a lo largo del clip.

    - Dos personas en buena parte del clip → "split" (se ven las dos caras).
    - Casi nunca hay caras (pantalla compartida, plano abierto) → "16:9", que no
      recorta y no se come nada.
    - El resto → "9:16" (su layout automático ya elige entre recorte al hablante
      y plano completo sobre fondo borroso).
    """
    if summary.get("two_shot_ratio", 0) >= SPLIT_RATIO:
        return "split"
    if summary.get("empty_ratio", 0) >= EMPTY_RATIO:
        return "16:9"
    return "9:16"


def is_mixed(summary: dict) -> bool:
    """
    True si la toma cambia dentro del clip (hay dos personas parte del tiempo,
    pero no las suficientes como para que el split sea claramente lo mejor).
    """
    return MIXED_RATIO <= summary.get("two_shot_ratio", 0) < SPLIT_RATIO


def analyze_segment(
    video_path,
    start: float,
    end: float,
    video_id: str = "video",
    cache_dir=None,
) -> dict:
    """
    Todo junto: muestras del tramo + cómo es la toma + formato sugerido.

    Devuelve el resumen de `summarize_shots` más {"frames", "faces_per_frame",
    "suggestion", "mixed", "thumbs"}. `thumbs` son 3 muestras elegidas para
    mostrar: la primera, la que tiene MÁS gente (ahí se ve si es un plano de dos)
    y la última.
    """
    frames = extract_segment_frames(
        video_path, start, end, video_id=video_id, cache_dir=cache_dir
    )
    times = sample_times(start, end, len(frames))

    # Detectar caras cuesta ~1 s por tramo: se cachea junto a los frames para que
    # abrir el panel en una sesión nueva sea instantáneo.
    cache_file = (frames[0].parent / "faces.json") if frames else None
    faces_per_frame = None
    if cache_file is not None and cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if len(cached) == len(frames):
                faces_per_frame = cached
        except Exception:
            faces_per_frame = None
    if faces_per_frame is None:
        faces_per_frame = [detect_faces(f) for f in frames]
        if cache_file is not None:
            try:
                cache_file.write_text(json.dumps(faces_per_frame), encoding="utf-8")
            except OSError:
                pass

    summary = summarize_shots(faces_per_frame, times)

    return {
        **summary,
        "frames":          frames,
        "faces_per_frame": faces_per_frame,
        "times":           times,
        "suggestion":      suggest_format(summary),
        "mixed":           is_mixed(summary),
        "thumbs":          pick_thumbs(frames, summary, times),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Tramos de layout: seguir la toma dentro del clip
# ──────────────────────────────────────────────────────────────────────────────

# Un tramo de layout más corto que esto se funde con el vecino: cambiar de
# recorte cada dos segundos marea y suele ser ruido del detector, no un corte.
FOLLOW_MIN_SEGMENT = 3.0


def shot_segments(timeline: list, duration: float,
                  min_segment: float = FOLLOW_MIN_SEGMENT) -> list:
    """
    Agrupa las muestras en tramos de layout: "two" (plano de dos) y "solo".

    Cada muestra manda sobre la ventana que la rodea (mitad hasta la anterior,
    mitad hasta la siguiente). Las muestras sin caras heredan el tramo anterior:
    un frame perdido no es un cambio de plano. Los tramos demasiado cortos se
    funden con el vecino.

    Devuelve [{"start", "end", "kind", "xs": [posiciones X promedio]}, ...] en
    tiempo del propio clip.
    """
    duration = float(duration)
    if not timeline or duration <= 0:
        return []

    # Cada muestra pasa a ser una franja [desde, hasta).
    ts = [float(p["t"]) for p in timeline]
    bounds = [0.0]
    for a, b in zip(ts, ts[1:]):
        bounds.append((a + b) / 2)
    bounds.append(duration)

    kinds, xs = [], []
    prev = None
    for p in timeline:
        if p["n"] >= 2:
            kind = "two"
        elif p["n"] == 1:
            kind = "solo"
        else:
            kind = prev or "solo"      # sin caras: seguimos como veníamos
        kinds.append(kind)
        xs.append(list(p.get("x") or []))
        prev = kind

    # Agrupar muestras consecutivas del mismo tipo.
    runs = []
    for i, kind in enumerate(kinds):
        if runs and runs[-1]["kind"] == kind:
            runs[-1]["end"] = bounds[i + 1]
            runs[-1]["xs"].append(xs[i])
        else:
            runs.append({"kind": kind, "start": bounds[i], "end": bounds[i + 1],
                         "xs": [xs[i]]})

    runs = _merge_short_runs(runs, min_segment)

    out = []
    for r in runs:
        out.append({
            "start": round(r["start"], 3),
            "end":   round(r["end"], 3),
            "kind":  r["kind"],
            "xs":    _representative_xs(r["xs"], 2 if r["kind"] == "two" else 1),
        })
    return out


def _merge_short_runs(runs: list, min_segment: float) -> list:
    """Funde los tramos más cortos que `min_segment` con el vecino más largo."""
    if len(runs) <= 1:
        return runs
    changed = True
    while changed and len(runs) > 1:
        changed = False
        for i, r in enumerate(runs):
            if r["end"] - r["start"] >= min_segment:
                continue
            prev_r = runs[i - 1] if i > 0 else None
            next_r = runs[i + 1] if i + 1 < len(runs) else None
            # Se funde con el vecino más largo (el que "manda" en la zona).
            target = prev_r
            if prev_r is None:
                target = next_r
            elif next_r is not None:
                dur_p = prev_r["end"] - prev_r["start"]
                dur_n = next_r["end"] - next_r["start"]
                target = prev_r if dur_p >= dur_n else next_r
            if target is None:
                continue
            target["start"] = min(target["start"], r["start"])
            target["end"]   = max(target["end"], r["end"])
            target["xs"].extend(r["xs"])
            runs.pop(i)
            changed = True
            break
    # Tras fundir pueden quedar dos vecinos del mismo tipo: se unen.
    merged = []
    for r in runs:
        if merged and merged[-1]["kind"] == r["kind"]:
            merged[-1]["end"] = r["end"]
            merged[-1]["xs"].extend(r["xs"])
        else:
            merged.append(r)
    return merged


def _representative_xs(samples_xs: list, want: int) -> list:
    """
    Posición X típica de cada persona en un tramo.

    Junta todas las caras vistas en el tramo, las agrupa por X y devuelve los
    `want` grupos con más apariciones, ordenados de izquierda a derecha (que es
    como se asignan arriba/abajo en el split).
    """
    flat = [x for xs in samples_xs for x in xs]
    if not flat:
        return [0.5] * want
    centers = _cluster_by_x(flat, CLUSTER_X_TOL)
    counts = [0] * len(centers)
    for x in flat:
        counts[_nearest(x, centers)] += 1
    top = sorted(range(len(centers)), key=lambda i: counts[i], reverse=True)[:want]
    chosen = sorted(centers[i] for i in top)
    while len(chosen) < want:                      # una sola persona en un "two"
        chosen.append(chosen[-1] if chosen else 0.5)
    return [round(c, 3) for c in chosen]


def analyze_clip_file(clip_path, duration: float, cache_dir=None) -> dict:
    """
    Analiza un archivo de clip YA CORTADO (tiempos propios, desde 0).

    Se hace sobre el clip y no sobre el tramo del original a propósito: después
    del ajuste de bordes y de los jump cuts, los tiempos del original ya no
    mapean 1 a 1 con lo que ve el render.
    """
    import hashlib
    key = hashlib.md5(str(clip_path).encode("utf-8")).hexdigest()[:10]
    return analyze_segment(clip_path, 0.0, float(duration),
                           video_id=f"clip{key}", cache_dir=cache_dir)


def pick_thumbs(frames: list, summary: dict, times: list) -> list:
    """
    Tres muestras representativas: la primera, la de más gente y la última.

    Mostrar inicio/medio/final se pierde justo el momento que importa (cuando
    entran los dos). Devuelve [(Path, etiqueta), ...].
    """
    if not frames:
        return []
    tl = summary.get("timeline") or []
    best = 0
    for i, item in enumerate(tl):
        if item["n"] > tl[best]["n"]:
            best = i

    picks = [(0, "arranque")]
    if tl and tl[best]["n"] >= 2 and best not in (0, len(frames) - 1):
        # "2+" y no el número exacto: el clasificador cuenta como caras los
        # dibujos del mural y los peluches del set, así que un "4 personas" sería
        # mentira. Para elegir formato alcanza con saber que hay más de una.
        picks.append((best, "2+ personas"))
    elif len(frames) > 2:
        picks.append((len(frames) // 2, "medio"))
    if len(frames) > 1:
        picks.append((len(frames) - 1, "final"))

    out = []
    for i, label in picks:
        if 0 <= i < len(frames):
            t = times[i] if i < len(times) else None
            stamp = f" · {int(t // 60)}:{int(t % 60):02d}" if t is not None else ""
            out.append((frames[i], label + stamp))
    return out
