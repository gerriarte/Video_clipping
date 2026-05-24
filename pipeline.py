#!/usr/bin/env python3
"""
Zumo Streaming — Pipeline principal
Descarga video de YouTube → identifica clips → corta → renderiza 9:16 → genera captions
"""

import csv
import sys
import argparse
from pathlib import Path
from datetime import datetime

import config
from modules.downloader  import download_video
from modules.analyzer    import parse_vtt, identify_clips, get_cues_for_clip
from modules.clipper     import cut_clips
from modules.renderer    import render_clips
from modules.caption_gen import generate_all_captions


def run_pipeline(url: str, skip_render: bool = False) -> Path:
    """
    Ejecuta el pipeline completo para una URL de YouTube.

    Returns: Path al directorio de output del video.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"\n{'═'*55}")
    print(f"  ZUMO STREAMING — PIPELINE")
    print(f"  {timestamp}")
    print(f"{'═'*55}\n")

    # ── PASO 1: Descargar ────────────────────────────────────────────────────
    print("▶ PASO 1/5 — Descargando video...")
    video_info = download_video(url, config.DOWNLOADS_DIR)
    video_id    = video_info["video_id"]
    video_title = video_info["title"]
    video_path  = video_info["video_path"]
    vtt_path    = video_info["vtt_path"]
    print(f"  ✅ Video: {video_title} ({video_info['duration']}s)\n")

    # ── PASO 2: Analizar transcript ──────────────────────────────────────────
    print("▶ PASO 2/5 — Analizando transcript con Claude...")
    if not vtt_path:
        print("  ⚠️  Sin transcript VTT — Claude analizará sin timestamps precisos")
        print("  💡 Tip: usá un video con subtítulos automáticos habilitados\n")
        cues = []
    else:
        cues = parse_vtt(vtt_path)
        print(f"  ✅ {len(cues)} cues de transcript parseados")

    clips = identify_clips(cues, video_title)
    print(f"  ✅ {len(clips)} clips identificados:")
    for clip in clips:
        dur = clip['end'] - clip['start']
        print(f"     [{clip['type']:8s}] {clip['title']} ({dur:.0f}s) — {clip['reason']}")
    print()

    # ── PASO 3: Cortar clips ─────────────────────────────────────────────────
    print("▶ PASO 3/5 — Cortando clips con ffmpeg...")
    clips_with_path = cut_clips(video_path, clips, config.CLIPS_DIR, video_id)
    print(f"  ✅ {len(clips_with_path)} clips cortados\n")

    # Añadir subtítulos relativos a cada clip
    for clip in clips_with_path:
        clip["subtitles"] = get_cues_for_clip(cues, clip["start"], clip["end"])

    # ── PASO 4: Renderizar en 9:16 ───────────────────────────────────────────
    output_dir = config.OUTPUT_DIR / video_id
    output_dir.mkdir(parents=True, exist_ok=True)

    if skip_render:
        print("▶ PASO 4/5 — Renderizado Remotion OMITIDO (--skip-render)\n")
        for clip in clips_with_path:
            clip["output_path"] = clip["clip_path"]  # usar clip sin procesar
        rendered_clips = clips_with_path
    else:
        print("▶ PASO 4/5 — Renderizando en vertical 9:16 con Remotion...")
        rendered_clips = render_clips(clips_with_path, output_dir, video_id)
        print(f"  ✅ {len(rendered_clips)} clips renderizados\n")

    # ── PASO 5: Generar captions ─────────────────────────────────────────────
    print("▶ PASO 5/5 — Generando captions con Claude...")
    final_clips = generate_all_captions(rendered_clips, video_title)
    print(f"  ✅ Captions generados para {len(final_clips)} clips\n")

    # ── OUTPUT: CSV ───────────────────────────────────────────────────────────
    csv_path = output_dir / "captions.csv"
    _export_csv(final_clips, csv_path, video_title, video_id)

    print(f"{'═'*55}")
    print(f"  PIPELINE COMPLETADO")
    print(f"  📁 Output: {output_dir}")
    print(f"  📄 CSV:    {csv_path}")
    print(f"  🎬 Clips:  {len(final_clips)}")
    print(f"{'═'*55}\n")

    return output_dir


def _export_csv(clips: list[dict], csv_path: Path, video_title: str, video_id: str) -> None:
    fieldnames = [
        "video_id", "video_title", "clip_index", "clip_title",
        "start", "end", "duration", "type", "reason",
        "clip_path", "output_path",
        "caption_tiktok", "caption_instagram", "caption_youtube",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for clip in clips:
            captions = clip.get("captions", {})
            writer.writerow({
                "video_id":          video_id,
                "video_title":       video_title,
                "clip_index":        clip.get("index", ""),
                "clip_title":        clip.get("title", ""),
                "start":             clip.get("start", ""),
                "end":               clip.get("end", ""),
                "duration":          f"{clip.get('end', 0) - clip.get('start', 0):.1f}",
                "type":              clip.get("type", ""),
                "reason":            clip.get("reason", ""),
                "clip_path":         str(clip.get("clip_path", "")),
                "output_path":       str(clip.get("output_path", "")),
                "caption_tiktok":    captions.get("tiktok", ""),
                "caption_instagram": captions.get("instagram", ""),
                "caption_youtube":   captions.get("youtube", ""),
            })


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Zumo Streaming — Pipeline de clips virales desde YouTube"
    )
    parser.add_argument("url", help="URL del video de YouTube")
    parser.add_argument(
        "--skip-render",
        action="store_true",
        help="Omitir el renderizado con Remotion (útil para testear sin Node.js)"
    )

    args = parser.parse_args()

    try:
        output_dir = run_pipeline(args.url, skip_render=args.skip_render)
        print(f"✅ Listo. Revisá: {output_dir}")
    except KeyboardInterrupt:
        print("\n⚠️  Pipeline interrumpido por el usuario.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error en pipeline: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
