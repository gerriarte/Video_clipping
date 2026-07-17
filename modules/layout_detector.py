"""
Decide el layout de cada clip y, cuando hay un "talking head", sigue dinámicamente
a la persona que habla para mantenerla centrada en el recorte.

Dos niveles:

1. Layout (fill / fit)
   - "fill": hay una cara grande → conviene RECORTAR para llenar la pantalla.
   - "fit": la cara es chica o no hay (pantalla compartida, slides) → recortar
     perdería contenido → mostramos el plano completo 16:9 sobre fondo borroso.

2. Foco dinámico (solo en "fill")
   Si hay varias personas (p. ej. dos hosts), trackeamos cada cara a lo largo del
   clip con MediaPipe Face Mesh y medimos el movimiento de sus labios. La persona
   con más actividad de boca en cada momento es "la que habla", y el recorte se
   centra en ella. Cuando el que habla cambia, la "cámara" viaja suave hacia la
   otra persona (keyframes interpolados en Remotion).

Además `detect_split()` devuelve el foco de las dos mitades para el formato de dos
recortes apilados (un host arriba, otro abajo).

El centrado del recorte depende del ASPECTO de destino: la fracción de ancho de la
fuente que queda visible al hacer cover-crop cambia según el formato (9:16, 1:1, o
media pantalla del split). Por eso el mapeo cara→object-position recibe esa fracción.

Detección preferida: MediaPipe Face Landmarker (Tasks API, landmarks de boca,
multi-cara). Fallback: OpenCV Haar (cara más grande, foco estático). Si no hay ni
OpenCV, layout "fit" seguro.
"""

import subprocess
import tempfile
from pathlib import Path

# ── Umbrales de layout ────────────────────────────────────────────────────────
# Alto de la cara más grande respecto al alto del frame para considerar "fill".
# Primer plano: 25-45%; webcam PiP sobre pantalla compartida: ~8-15%. 0.16 separa
# bien ambos casos (capta también planos a dos personas, donde cada cara es algo
# más chica pero igual vale recortar al que habla).
_FACE_FILL_RATIO = 0.16

# ── Muestreo temporal (para el tracking de hablante con MediaPipe) ─────────────
_SAMPLE_FPS    = 4.0    # frames analizados por segundo de clip
_MAX_SAMPLES   = 240    # tope duro de frames a procesar (acota el costo por clip)

# ── Selección del hablante / suavizado de la cámara ───────────────────────────
_ACTIVITY_WIN_S = 0.6   # ventana para medir "cuánto se mueve la boca" (std)
_SMOOTH_WIN_S   = 0.7   # media móvil sobre la señal de foco (cámara suave)
_MIN_DWELL_S    = 0.7   # tiempo mínimo en una persona antes de poder saltar
_SWITCH_MARGIN  = 1.25  # el nuevo hablante debe superar al actual por este factor
_CLUSTER_X_TOL  = 0.14  # tolerancia en X para agrupar caras como "la misma persona"
_KEYFRAME_TOL   = 0.012 # simplificación de keyframes (RDP) sobre objectPosition

# Fracciones del clip donde muestrea el fallback Haar (evita intro/outro).
_SAMPLE_FRACTIONS = (0.25, 0.5, 0.75)

# Aspecto de destino por defecto (9:16), usado si detect_* no recibe uno explícito.
_DEFAULT_TARGET_ASPECT = 1080.0 / 1920.0


def _log(msg: str) -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "ignore").decode())


def _visible_frac(target_aspect: float, source_aspect: float) -> float:
    """
    Fracción del ANCHO de la fuente que queda visible al hacer cover-crop hacia
    `target_aspect` (ambos = width/height). Si el destino es más ANGOSTO que la
    fuente (típico: 9:16 desde 16:9), se recorta a lo ancho y la fracción es
    target/source. Si es más ancho, no hay recorte horizontal → 1.
    """
    if source_aspect <= 0:
        source_aspect = 16.0 / 9.0
    return max(0.01, min(1.0, target_aspect / source_aspect))


def _face_x_to_object_position(face_x: float, visible_frac: float) -> float:
    """
    Mapea el centro horizontal de la cara (0–1 en el frame fuente) al valor de
    CSS `object-position` (0–1) que centra a esa persona en el recorte.

    Deducción (cover, alto llena el alto; ancho desborda):
        p = (f - 0.5·r) / (1 - r),  con r = fracción de ancho visible.
    f=0.5 → 0.5; los extremos se mapean más lejos para llevar al hablante al centro.
    Si r≈1 no hay recorte horizontal → la posición X es irrelevante (0.5). Se acota a [0,1].
    """
    r = visible_frac
    if r >= 0.999:
        return 0.5
    p = (face_x - 0.5 * r) / (1.0 - r)
    return min(1.0, max(0.0, p))


# ──────────────────────────────────────────────────────────────────────────────
# API pública
# ──────────────────────────────────────────────────────────────────────────────
def detect_layout(
    clip_path: Path,
    clip_duration: float | None = None,
    target_aspect: float | None = None,
) -> dict:
    """
    Devuelve:
        {
          "layout": "fill"|"fit",
          "focus_x": float,                 # objectPosition X fijo (fallback)
          "focus_keyframes": [{"t": float, "x": float}, ...],  # cámara dinámica
          "cover_time": float,              # mejor frame para la portada (seg)
        }

    target_aspect: ancho/alto del formato de salida (p. ej. 1080/1920 para 9:16,
    1080/1080 para 1:1). Ajusta el centrado del recorte. Si es None, usa 9:16.
    """
    if target_aspect is None:
        target_aspect = _DEFAULT_TARGET_ASPECT

    midpoint = (clip_duration / 2) if (clip_duration and clip_duration > 0) else 1.0
    safe_default = {
        "layout": "fit", "focus_x": 0.5, "focus_keyframes": [], "cover_time": midpoint,
    }

    clip_path = Path(clip_path)
    if not clip_path.exists():
        return safe_default

    # Intento principal: tracking de hablante con MediaPipe.
    try:
        result = _detect_with_mediapipe(clip_path, clip_duration, target_aspect)
        if result is not None:
            return result
    except Exception as e:  # cualquier fallo del path nuevo → caemos al clásico
        _log(f"  ⚠️  Tracking de hablante falló ({e}); uso layout estático.")

    # Fallback: método clásico Haar (cara más grande, foco fijo).
    return _detect_with_haar(clip_path, clip_duration, midpoint, target_aspect)


def detect_split(
    clip_path: Path,
    clip_duration: float | None = None,
    target_aspect: float | None = None,
) -> dict:
    """
    Foco horizontal de las dos mitades del formato "split" (dos recortes apilados).

    Devuelve {"focus_top": float, "focus_bottom": float, "cover_time": float}.
    Agrupa las caras por posición X, elige las dos "personas" más presentes y las
    asigna izquierda→arriba, derecha→abajo. Si detecta menos de dos, ambas mitades
    quedan centradas en lo que haya (o al centro).

    target_aspect: ancho/alto de UNA mitad (p. ej. 1080/960), no del frame entero.
    """
    if target_aspect is None:
        target_aspect = 1080.0 / 960.0  # media pantalla de un 1080×1920

    midpoint = (clip_duration / 2) if (clip_duration and clip_duration > 0) else 1.0
    default = {"focus_top": 0.5, "focus_bottom": 0.5, "cover_time": midpoint}

    clip_path = Path(clip_path)
    if not clip_path.exists():
        return default

    try:
        sampled = _sample_faces(clip_path, clip_duration)
    except Exception as e:
        _log(f"  ⚠️  Muestreo de caras para split falló ({e}); foco centrado.")
        return default

    if sampled is None:
        return default
    samples, _max_face_ratio, source_aspect = sampled

    r = _visible_frac(target_aspect, source_aspect)
    cover_time = _best_cover_time(samples)

    xs = [x for _t, faces in samples for (x, _h, _m) in faces]
    if not xs:
        return {**default, "cover_time": round(cover_time, 3)}

    clusters = _cluster_by_x(xs, _CLUSTER_X_TOL)  # centros ordenados por X
    counts = [0] * len(clusters)
    for x in xs:
        counts[_nearest_cluster(x, clusters)] += 1

    # Los 2 clusters más presentes, re-ordenados por X (izquierda→arriba).
    order = sorted(range(len(clusters)), key=lambda c: counts[c], reverse=True)
    top2 = sorted(order[:2], key=lambda c: clusters[c])
    if len(top2) >= 2:
        left_x, right_x = clusters[top2[0]], clusters[top2[1]]
    else:
        left_x = right_x = clusters[top2[0]]

    return {
        "focus_top":    round(_face_x_to_object_position(left_x, r), 3),
        "focus_bottom": round(_face_x_to_object_position(right_x, r), 3),
        "cover_time":   round(cover_time, 3),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Muestreo de caras (compartido por detect_layout y detect_split)
# ──────────────────────────────────────────────────────────────────────────────
def _ensure_model() -> "Path | None":
    """Ruta al modelo face_landmarker.task; lo descarga si falta. None si no se puede."""
    try:
        import config
        model_path = Path(config.FACE_LANDMARKER_MODEL)
        url = config.FACE_LANDMARKER_URL
    except Exception:
        return None

    if model_path.exists() and model_path.stat().st_size > 0:
        return model_path

    try:
        import urllib.request
        model_path.parent.mkdir(parents=True, exist_ok=True)
        _log("  ⬇️  Descargando modelo face_landmarker.task (una sola vez)…")
        urllib.request.urlretrieve(url, str(model_path))
        if model_path.exists() and model_path.stat().st_size > 0:
            return model_path
    except Exception as e:
        _log(f"  ⚠️  No se pudo descargar el modelo de caras ({e}).")
    return None


def _sample_faces(clip_path: Path, clip_duration: float | None):
    """
    Muestrea caras del clip con MediaPipe Face Landmarker.

    Devuelve (samples, max_face_ratio, source_aspect) o None para delegar al
    fallback (faltan deps, no hay modelo, o el video no abre).
      samples: [(t_seg, [(x, h_ratio, mouth_open), ...]), ...]
      source_aspect: ancho/alto real del video fuente.
    """
    try:
        import cv2
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision
    except ImportError:
        return None  # delega al fallback Haar/seguro

    model_path = _ensure_model()
    if model_path is None:
        return None

    cap = cv2.VideoCapture(str(clip_path))
    if not cap.isOpened():
        return None

    video_fps   = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if frame_count <= 0 and clip_duration:
        frame_count = int(clip_duration * video_fps)
    src_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0.0
    src_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0.0
    source_aspect = (src_w / src_h) if (src_w > 0 and src_h > 0) else (16.0 / 9.0)

    step = max(1, int(round(video_fps / _SAMPLE_FPS)))
    if frame_count > 0:
        n_samples = frame_count // step
        if n_samples > _MAX_SAMPLES:
            step = max(1, frame_count // _MAX_SAMPLES)

    # Índices de boca/cara en la malla de 478 puntos (topología Face Mesh).
    LIP_TOP, LIP_BOT = 13, 14        # labio superior/inferior (interior)
    FACE_TOP, FACE_CHIN = 10, 152    # frente / mentón → alto de la cara
    NOSE = 1                         # centro horizontal estable

    samples = []        # (t, [face, ...]); face = (x, h_ratio, mouth_open)
    max_face_ratio = 0.0

    options = mp_vision.FaceLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
        running_mode=mp_vision.RunningMode.IMAGE,
        num_faces=4,
        min_face_detection_confidence=0.5,
        output_face_blendshapes=False,
    )
    try:
        landmarker = mp_vision.FaceLandmarker.create_from_options(options)
    except Exception as e:
        cap.release()
        _log(f"  ⚠️  No se pudo crear FaceLandmarker ({e}); uso layout estático.")
        return None

    try:
        idx = 0
        while True:
            if frame_count > 0 and idx >= frame_count:
                break
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok or frame is None:
                break

            t = idx / video_fps
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            res = landmarker.detect(mp_img)

            faces = []
            if res.face_landmarks:
                for lm in res.face_landmarks:   # lm: lista de NormalizedLandmark
                    face_h = abs(lm[FACE_CHIN].y - lm[FACE_TOP].y)  # frac del alto
                    if face_h <= 1e-4:
                        continue
                    mouth = abs(lm[LIP_BOT].y - lm[LIP_TOP].y) / face_h
                    x = min(1.0, max(0.0, lm[NOSE].x))
                    faces.append((x, face_h, mouth))
                    if face_h > max_face_ratio:
                        max_face_ratio = face_h

            samples.append((t, faces))
            idx += step
    finally:
        cap.release()
        try:
            landmarker.close()
        except Exception:
            pass

    if not samples:
        return None
    return samples, max_face_ratio, source_aspect


# ──────────────────────────────────────────────────────────────────────────────
# Camino principal: MediaPipe + actividad de labios (foco dinámico)
# ──────────────────────────────────────────────────────────────────────────────
def _detect_with_mediapipe(
    clip_path: Path, clip_duration: float | None, target_aspect: float
) -> dict | None:
    """
    Dict de layout con foco dinámico, o None para delegar al fallback.
    """
    try:
        import numpy as np
    except ImportError:
        return None

    sampled = _sample_faces(clip_path, clip_duration)
    if sampled is None:
        return None
    samples, max_face_ratio, source_aspect = sampled

    if max_face_ratio <= 0.0:
        return None  # no se vio ninguna cara → fallback decide fit

    r = _visible_frac(target_aspect, source_aspect)
    cover_time = _best_cover_time(samples)

    # ¿"fill" o "fit"? Si la cara más grande no llega al umbral, no recortamos.
    if max_face_ratio < _FACE_FILL_RATIO:
        return {
            "layout": "fit", "focus_x": 0.5,
            "focus_keyframes": [], "cover_time": round(cover_time, 3),
        }

    focus_signal = _build_focus_signal(samples, np)  # lista de (t, face_x 0–1)
    if not focus_signal:
        return {
            "layout": "fill", "focus_x": 0.5,
            "focus_keyframes": [], "cover_time": round(cover_time, 3),
        }

    times = [t for t, _ in focus_signal]
    xs    = _moving_average([x for _, x in focus_signal], times, _SMOOTH_WIN_S)
    pos   = [_face_x_to_object_position(x, r) for x in xs]

    keyframes = _simplify_keyframes(times, pos, _KEYFRAME_TOL)
    focus_x = float(np.median(pos)) if pos else 0.5

    return {
        "layout": "fill",
        "focus_x": round(focus_x, 3),
        "focus_keyframes": keyframes,
        "cover_time": round(cover_time, 3),
    }


def _best_cover_time(samples: list) -> float:
    """Tiempo del frame con la cara más grande (mejor para portada)."""
    best_t, best_h = None, 0.0
    for t, faces in samples:
        for (_x, h, _m) in faces:
            if h > best_h:
                best_h, best_t = h, t
    if best_t is not None:
        return best_t
    # Sin caras: punto medio del rango muestreado.
    return samples[len(samples) // 2][0] if samples else 1.0


def _build_focus_signal(samples: list, np) -> list:
    """
    A partir de las muestras (t, faces), agrupa caras por posición X en "personas"
    estables, mide la actividad de labios de cada una y devuelve, por cada tiempo,
    el centro X (0–1) de la persona que habla, con histéresis para no saltar.
    """
    obs = []  # (t_index, x, mouth)
    for i, (t, faces) in enumerate(samples):
        for (x, _h, mouth) in faces:
            obs.append((i, x, mouth))
    if not obs:
        return []

    clusters = _cluster_by_x([o[1] for o in obs], _CLUSTER_X_TOL)  # centros X
    n = len(samples)
    k = len(clusters)

    mouth = np.full((k, n), np.nan)
    xpos  = np.full((k, n), np.nan)
    for (i, x, m) in obs:
        c = _nearest_cluster(x, clusters)
        if np.isnan(mouth[c, i]) or m > mouth[c, i]:
            mouth[c, i] = m
            xpos[c, i]  = x

    dt = (samples[1][0] - samples[0][0]) if n > 1 else 0.25
    half = max(1, int(round((_ACTIVITY_WIN_S / 2) / max(dt, 1e-3))))
    activity = np.zeros((k, n))
    for c in range(k):
        for i in range(n):
            lo, hi = max(0, i - half), min(n, i + half + 1)
            window = mouth[c, lo:hi]
            window = window[~np.isnan(window)]
            activity[c, i] = float(np.std(window)) if window.size >= 2 else 0.0

    min_dwell = max(1, int(round(_MIN_DWELL_S / max(dt, 1e-3))))
    current = None
    dwell = min_dwell
    last_x = 0.5
    signal = []
    for i in range(n):
        present = [c for c in range(k) if not np.isnan(xpos[c, i])]
        if not present:
            signal.append((samples[i][0], last_x))
            dwell += 1
            continue

        best = max(present, key=lambda c: activity[c, i])
        if current is None or current not in present:
            current = best
            dwell = 0
        elif best != current and dwell >= min_dwell and \
                activity[best, i] > activity[current, i] * _SWITCH_MARGIN:
            current = best
            dwell = 0

        cx = xpos[current, i]
        if np.isnan(cx):
            cx = last_x
        last_x = float(cx)
        signal.append((samples[i][0], last_x))
        dwell += 1

    return signal


def _cluster_by_x(values: list, tol: float) -> list:
    """Agrupa posiciones X 1D en centros de cluster (greedy sobre ordenado)."""
    if not values:
        return []
    vals = sorted(values)
    centers = []
    group = [vals[0]]
    for v in vals[1:]:
        if v - group[0] <= tol:
            group.append(v)
        else:
            centers.append(sum(group) / len(group))
            group = [v]
    centers.append(sum(group) / len(group))
    return centers


def _nearest_cluster(x: float, centers: list) -> int:
    best, bd = 0, float("inf")
    for c, cx in enumerate(centers):
        d = abs(x - cx)
        if d < bd:
            bd, best = d, c
    return best


def _moving_average(values: list, times: list, window_s: float) -> list:
    """Media móvil temporal (suaviza la trayectoria de la cámara)."""
    n = len(values)
    if n == 0:
        return []
    out = []
    for i in range(n):
        t0 = times[i]
        acc, cnt = 0.0, 0
        for j in range(n):
            if abs(times[j] - t0) <= window_s / 2:
                acc += values[j]
                cnt += 1
        out.append(acc / cnt if cnt else values[i])
    return out


def _simplify_keyframes(times: list, values: list, tol: float) -> list:
    """
    Reduce la señal (t, x) a pocos keyframes con Ramer–Douglas–Peucker, manteniendo
    la forma dentro de `tol`. Devuelve [{"t": ..., "x": ...}] con t estrictamente
    creciente (requisito de interpolate() en Remotion).
    """
    n = len(times)
    if n == 0:
        return []
    if n <= 2:
        return _dedup_times([{"t": round(times[i], 3), "x": round(values[i], 4)}
                             for i in range(n)])

    keep = [False] * n
    keep[0] = keep[-1] = True

    def rdp(lo: int, hi: int) -> None:
        x0, y0 = times[lo], values[lo]
        x1, y1 = times[hi], values[hi]
        dx = x1 - x0
        dmax, idx = 0.0, -1
        for i in range(lo + 1, hi):
            if abs(dx) < 1e-9:
                d = abs(values[i] - y0)
            else:
                yhat = y0 + (times[i] - x0) * (y1 - y0) / dx
                d = abs(values[i] - yhat)
            if d > dmax:
                dmax, idx = d, i
        if idx != -1 and dmax > tol:
            keep[idx] = True
            rdp(lo, idx)
            rdp(idx, hi)

    rdp(0, n - 1)
    kf = [{"t": round(times[i], 3), "x": round(values[i], 4)}
          for i in range(n) if keep[i]]
    return _dedup_times(kf)


def _dedup_times(keyframes: list) -> list:
    """Garantiza t estrictamente creciente (descarta duplicados de tiempo)."""
    out = []
    last_t = None
    for kf in keyframes:
        if last_t is None or kf["t"] > last_t:
            out.append(kf)
            last_t = kf["t"]
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Fallback clásico: OpenCV Haar (cara más grande, foco estático)
# ──────────────────────────────────────────────────────────────────────────────
def _extract_frame(clip_path: Path, at_seconds: float, out_path: Path) -> bool:
    cmd = [
        "ffmpeg",
        "-ss", f"{at_seconds:.3f}",
        "-i", str(clip_path),
        "-frames:v", "1",
        "-q:v", "2",
        "-loglevel", "error",
        "-y",
        str(out_path),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True)
        return r.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0
    except Exception:
        return False


def _detect_with_haar(
    clip_path: Path, clip_duration: float | None, midpoint: float, target_aspect: float
) -> dict:
    """Método original: muestrea pocos frames, elige la cara más grande, foco fijo."""
    safe_default = {
        "layout": "fit", "focus_x": 0.5, "focus_keyframes": [], "cover_time": midpoint,
    }

    try:
        import cv2
    except ImportError:
        _log("  ⚠️  OpenCV no instalado — layout por defecto 'fit' (pantalla completa).")
        return safe_default

    if clip_duration and clip_duration > 0:
        sample_times = [clip_duration * f for f in _SAMPLE_FRACTIONS]
    else:
        sample_times = [0.5, 1.5, 3.0]

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)
    if face_cascade.empty():
        _log("  ⚠️  No se pudo cargar el clasificador de caras — layout 'fit'.")
        return safe_default

    best_ratio, best_focus_x, best_time = 0.0, 0.5, None
    source_aspect = 16.0 / 9.0
    tmp_dir = Path(tempfile.mkdtemp(prefix="zumo_layout_"))
    try:
        for i, t in enumerate(sample_times):
            frame_png = tmp_dir / f"f{i}.png"
            if not _extract_frame(clip_path, t, frame_png):
                continue
            img = cv2.imread(str(frame_png))
            if img is None:
                continue
            h, w = img.shape[:2]
            if h:
                source_aspect = w / h
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5,
                minSize=(int(w * 0.05), int(h * 0.05)),
            )
            for (fx, fy, fw, fh) in faces:
                ratio = fh / h if h else 0.0
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_focus_x = (fx + fw / 2) / w if w else 0.5
                    best_time = t
    finally:
        for p in tmp_dir.glob("*"):
            try:
                p.unlink()
            except OSError:
                pass
        try:
            tmp_dir.rmdir()
        except OSError:
            pass

    cover_time = best_time if best_time is not None else midpoint

    if best_ratio >= _FACE_FILL_RATIO:
        r = _visible_frac(target_aspect, source_aspect)
        focus_x = _face_x_to_object_position(best_focus_x, r)
        return {
            "layout": "fill", "focus_x": round(focus_x, 3),
            "focus_keyframes": [], "cover_time": round(cover_time, 3),
        }

    return {
        "layout": "fit", "focus_x": 0.5,
        "focus_keyframes": [], "cover_time": round(cover_time, 3),
    }
