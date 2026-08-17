"""
Corta clips del video fuente usando ffmpeg.

Además del corte crudo hace dos cosas guiadas por el audio (ver
`modules/audio_edit.py`):
  - **Ajusta los bordes** a la pausa más cercana, porque los tiempos que vienen
    del VTT traen 1–2 s de error y cortan palabras.
  - **Saca los silencios largos de adentro** (jump cuts), opcional.
Y normaliza la sonoridad a -14 LUFS, que es lo que esperan las redes.
"""

import json
import re
import subprocess
from pathlib import Path
from typing import Callable

from modules.audio_edit import (
    LOUDNORM_FILTER,
    OUTPUT_RATE,
    SNAP_WINDOW,
    SPEECH_FILTER,
    detect_silences,
    loudnorm_filter,
    measure_loudness,
    measure_loudness_complex,
    segments_duration,
    snap_bounds,
    speech_segments,
)

# Margen que agregamos al inicio y al final del clip para no cortar la primera
# ni la última palabra. Es simétrico para que el ritmo del clip se sienta natural.
# Cuando el borde se ajustó al audio no hace falta: el aire ya lo puso el snap.
PAD_LEAD = 0.25
PAD_TAIL = 0.25

# Fundido corto en cada trozo de audio: sin esto los jump cuts hacen "click".
JUMPCUT_FADE = 0.02


def clip_lead(start: float) -> float:
    """Pre-roll real aplicable al inicio (acotado si el clip arranca casi en 0)."""
    return min(PAD_LEAD, max(0.0, start))


def probe_duration(path) -> float:
    """Duración real del archivo (0.0 si ffprobe no puede leerlo)."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "json", str(path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        return float(json.loads(r.stdout)["format"]["duration"])
    except Exception:
        return 0.0


def build_audio_chain(segments: list, base: float, fade: float = JUMPCUT_FADE) -> str:
    """
    Cadena de audio sola (sin video): recorta los mismos tramos que el clip, los
    empalma con fundidos y limpia el retumbe.

    Existe aparte porque la primera pasada de `loudnorm` tiene que MEDIR
    exactamente este audio — el del clip terminado, con los jump cuts ya
    aplicados. Medir el tramo entero daría una corrección para otro material.
    """
    parts, labels = [], []
    for i, (s, e) in enumerate(segments):
        rs, re_ = max(0.0, s - base), max(0.0, e - base)
        dur = max(0.0, re_ - rs)
        f = min(fade, dur / 2) if dur else 0.0
        af = [f"atrim=start={rs:.3f}:end={re_:.3f}", "asetpts=PTS-STARTPTS"]
        if f > 0:
            af.append(f"afade=t=in:st=0:d={f:.3f}")
            af.append(f"afade=t=out:st={max(0.0, dur - f):.3f}:d={f:.3f}")
        parts.append(f"[0:a]{','.join(af)}[m{i}]")
        labels.append(f"[m{i}]")

    if len(segments) > 1:
        parts.append(f"{''.join(labels)}concat=n={len(segments)}:v=0:a=1[cat]")
        last = "[cat]"
    else:
        last = labels[0]
    parts.append(f"{last}{SPEECH_FILTER}[aout]")
    return ";".join(parts)


def build_concat_filter(segments: list, base: float, loudness: bool = True,
                        fade: float = JUMPCUT_FADE,
                        loudnorm: str | None = None) -> str:
    """
    filter_complex que pega varios tramos del mismo video en uno solo.

    `segments` son tiempos absolutos del video y `base` es el punto al que se
    hizo seek (`-ss`), porque después del seek los timestamps arrancan en 0.
    Cada trozo de audio lleva un fundido de `fade` segundos en las dos puntas
    para que el empalme no suene como un click. Salidas: `[v]` y `[a]`.
    """
    parts, vlabels, alabels = [], [], []
    for i, (s, e) in enumerate(segments):
        rs, re_ = max(0.0, s - base), max(0.0, e - base)
        dur = max(0.0, re_ - rs)
        f = min(fade, dur / 2) if dur else 0.0
        parts.append(f"[0:v]trim=start={rs:.3f}:end={re_:.3f},setpts=PTS-STARTPTS[v{i}]")
        afilters = [f"atrim=start={rs:.3f}:end={re_:.3f}", "asetpts=PTS-STARTPTS"]
        if f > 0:
            afilters.append(f"afade=t=in:st=0:d={f:.3f}")
            afilters.append(f"afade=t=out:st={max(0.0, dur - f):.3f}:d={f:.3f}")
        parts.append(f"[0:a]{','.join(afilters)}[a{i}]")
        vlabels.append(f"[v{i}]")
        alabels.append(f"[a{i}]")

    interleaved = "".join(v + a for v, a in zip(vlabels, alabels))
    if loudness:
        parts.append(f"{interleaved}concat=n={len(segments)}:v=1:a=1[v][araw]")
        # El mismo orden que en `build_audio_chain`: primero se limpia el
        # retumbe y después se normaliza, para que la medición y la corrección
        # se hagan sobre el audio ya filtrado.
        parts.append(f"[araw]{SPEECH_FILTER},{loudnorm or LOUDNORM_FILTER}[a]")
    else:
        parts.append(f"{interleaved}concat=n={len(segments)}:v=1:a=1[v][a]")
    return ";".join(parts)


def cut_clip(
    video_path: Path,
    start: float,
    end: float,
    output_path: Path,
    pad_seconds: float = PAD_LEAD,
    progress_fn: Callable[[str], None] | None = None,
    segments: list | None = None,
    pad_tail: float = PAD_TAIL,
    loudness: bool = True,
) -> Path:
    """
    Corta un fragmento del video entre start y end (segundos).

    segments: tramos absolutos a conservar (jump cuts). Si son varios se pegan
              en un solo archivo; si es None se corta [start, end] de corrido.
    loudness: normaliza a -14 LUFS (lo que esperan TikTok/IG/Shorts) en dos
              pasadas: una mide el audio final y la otra corrige. Si la medición
              falla se usa una sola pasada, como antes.
    progress_fn: callback que recibe cada línea de progreso de ffmpeg.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not segments:
        lead     = min(pad_seconds, max(0.0, start))
        segments = [(start - lead, end + pad_tail)]

    base     = max(0.0, segments[0][0])
    span     = max(0.0, segments[-1][1] - base)
    duration = segments_duration(segments)

    seek = ["-ss", f"{base:.3f}", "-t", f"{span:.3f}"]

    # ── Primera pasada: medir ─────────────────────────────────────────────────
    # Se mide el audio ya recortado y empalmado, que es el que va a salir. Es
    # solo audio, así que cuesta poco aunque el episodio dure dos horas.
    norm = LOUDNORM_FILTER
    if loudness:
        if progress_fn:
            progress_fn("Midiendo sonoridad…")
        chain = build_audio_chain(segments, base)
        # ffmpeg no acepta un filter_complex con etiquetas en -af: para el caso
        # de un solo tramo alcanza con la cadena simple.
        if len(segments) > 1:
            medido = measure_loudness_complex(video_path, chain, seek)
        else:
            medido = measure_loudness(video_path, SPEECH_FILTER, seek)
        norm = loudnorm_filter(medido)
        if progress_fn and not medido:
            progress_fn("⚠️ No se pudo medir la sonoridad; se normaliza en una pasada.")

    cmd = ["ffmpeg"] + seek + ["-i", str(video_path)]

    if len(segments) > 1:
        cmd += [
            "-filter_complex",
            build_concat_filter(segments, base, loudness=loudness, loudnorm=norm),
            "-map", "[v]", "-map", "[a]",
        ]
    elif loudness:
        cmd += ["-af", f"{SPEECH_FILTER},{norm}"]

    cmd += [
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        # Explícito además del aresample del filtro: si alguna vez se corta sin
        # normalizar, el clip igual sale a 48 kHz y no arrastra el 96 de antes.
        "-ar", str(OUTPUT_RATE),
        "-avoid_negative_ts", "make_zero",
        "-stats",             # una línea de stats por segundo
        "-loglevel", "error", # solo errores en stderr (stats van a stdout con -stats)
        "-y",
        str(output_path),
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    stderr_lines = []

    # ffmpeg -stats escribe a stderr; leemos en tiempo real
    for line in iter(proc.stderr.readline, ""):
        line = line.rstrip()
        if not line:
            continue
        stderr_lines.append(line)
        if progress_fn:
            progress_fn(_parse_ffmpeg_line(line, duration))

    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg falló al cortar clip:\n" + "\n".join(stderr_lines[-10:])
        )

    return output_path


def plan_clip(
    video_path: Path,
    start: float,
    end: float,
    snap_to_audio: bool = True,
    remove_silences: bool = False,
) -> dict:
    """
    Decide los tiempos reales del clip mirando el audio, sin cortar todavía.

    Devuelve {"start", "end", "segments", "removed", "snap_lead", "snap_tail"}.
    `segments` es None cuando no hay jump cuts que hacer. Si no se pide nada (o
    el audio no se puede analizar) devuelve los tiempos tal cual llegaron.
    """
    plan = {
        "start": float(start), "end": float(end),
        "segments": None, "removed": 0.0,
        "snap_lead": 0.0, "snap_tail": 0.0,
    }
    if not (snap_to_audio or remove_silences):
        return plan

    # Se analiza un poco más ancho que el tramo: si solo miráramos [start, end],
    # el borde únicamente podría moverse hacia adentro (perdiendo voz).
    silences = detect_silences(
        video_path, max(0.0, start - SNAP_WINDOW), end + SNAP_WINDOW
    )
    if not silences:
        return plan

    if snap_to_audio:
        new_start, new_end = snap_bounds(start, end, silences)
        plan["snap_lead"] = round(new_start - start, 2)
        plan["snap_tail"] = round(new_end - end, 2)
        plan["start"], plan["end"] = new_start, new_end

    if remove_silences:
        segs = speech_segments(plan["start"], plan["end"], silences)
        full = plan["end"] - plan["start"]
        if len(segs) > 1 and segments_duration(segs) < full:
            plan["segments"] = segs
            plan["removed"] = round(full - segments_duration(segs), 2)

    return plan


def cut_clips(
    video_path: Path,
    clips: list[dict],
    clips_dir: Path,
    video_id: str,
    progress_fn: Callable[[str], None] | None = None,
    start_index: int = 1,
    snap_to_audio: bool = True,
    remove_silences: bool = False,
) -> list[dict]:
    """Corta todos los clips y retorna la lista enriquecida con clip_path."""
    results = []
    for i, clip in enumerate(clips, start_index):
        name        = _clip_filename(clip.get("title", f"Clip {i}"), i)
        output_path = clips_dir / f"{name}.mp4"

        total_display = start_index + len(clips) - 1
        def _progress(line, idx=i, total=total_display):
            if progress_fn:
                progress_fn(f"[{idx}/{total}] {line}")

        plan = plan_clip(
            video_path, clip["start"], clip["end"],
            snap_to_audio=snap_to_audio, remove_silences=remove_silences,
        )
        if progress_fn:
            _progress(_plan_summary(plan))

        cut_clip(
            video_path, plan["start"], plan["end"], output_path,
            progress_fn=_progress,
            segments=plan["segments"],
            # El snap ya dejó el aire justo; los pads fijos son para cuando no hubo.
            pad_seconds=0.0 if plan["snap_lead"] else PAD_LEAD,
            pad_tail=0.0 if plan["snap_tail"] else PAD_TAIL,
        )

        lead = 0.0 if plan["snap_lead"] else clip_lead(plan["start"])
        # Duración real del archivo: con jump cuts ya no es end - start.
        duration = probe_duration(output_path) or (
            (plan["end"] - plan["start"]) + lead + PAD_TAIL
        )
        results.append({
            **clip,
            "start":         plan["start"],
            "end":           plan["end"],
            "clip_path":     output_path,
            "index":         i,
            "lead_pad":      lead,                    # pre-roll real del archivo
            "clip_duration": duration,
            "segments":      plan["segments"],
            "silence_removed": plan["removed"],
        })

    return results


def _plan_summary(plan: dict) -> str:
    """Línea legible de lo que el audio cambió en este clip."""
    bits = []
    if plan["snap_lead"] or plan["snap_tail"]:
        bits.append(f"bordes {plan['snap_lead']:+.2f}s / {plan['snap_tail']:+.2f}s")
    if plan["removed"]:
        n = len(plan["segments"] or [])
        bits.append(f"-{plan['removed']:.1f}s de silencio ({n} tramos)")
    return "Ajustado al audio: " + " · ".join(bits) if bits else "Sin ajustes de audio"


def _parse_ffmpeg_line(line: str, total_duration: float) -> str:
    """Convierte una línea de stats de ffmpeg en texto legible con porcentaje."""
    m = re.search(r"time=(\d+):(\d+):([\d.]+)", line)
    if m and total_duration > 0:
        elapsed = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        pct     = min(100, int(elapsed / total_duration * 100))
        speed_m = re.search(r"speed=([\d.]+)x", line)
        speed   = f" · {speed_m.group(1)}x" if speed_m else ""
        return f"Procesando… {pct}%{speed}"
    return line[:120]


def _clip_filename(title: str, index: int, max_len: int = 80) -> str:
    """Genera nombre de archivo legible a partir del título que asignó Claude."""
    # Eliminar caracteres inválidos en nombres de archivo de Windows/Mac
    clean = re.sub(r'[\\/:*?"<>|]', "", title)
    clean = re.sub(r"\s+", " ", clean).strip()
    # Truncar preservando palabras completas
    if len(clean) > max_len:
        clean = clean[:max_len].rsplit(" ", 1)[0]
    return f"{index:02d} - {clean}"
