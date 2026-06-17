#!/usr/bin/env python3
"""
Programa en Postiz las publicaciones de los clips a partir del CSV que genera
el pipeline (zumo_<id>_captions.csv / captions.csv).

Por cada clip: sube el video una vez y crea UN post programado que publica en
las plataformas elegidas (cada una con su caption). Los clips se escalonan en
el tiempo (por defecto 1 cada 24 h).

Ejemplos:
  # Ver el plan sin tocar nada (recomendado primero):
  python schedule_postiz.py output/abc123/captions.csv --dry-run

  # Probar con 1 solo clip, real, dentro de 1 hora:
  python schedule_postiz.py output/abc123/captions.csv --limit 1 --start "2026-06-16 10:00"

  # Programar todo: 1 clip por día a las 9:00, solo TikTok e Instagram
  python schedule_postiz.py output/abc123/captions.csv --start "2026-06-17 09:00" \
      --interval-hours 24 --platforms tiktok,instagram
"""

import sys
import csv
import argparse
from pathlib import Path
from datetime import datetime, timedelta

import config
from modules.postiz import PostizClient, build_posts_for_clip, PLATFORM_CAPTION_FIELD, to_utc_iso


def _parse_start(s: str | None) -> datetime:
    """Parsea --start (hora local). Si no se da, mañana a las 09:00 local."""
    if not s:
        base = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        return base + timedelta(days=1)
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise SystemExit(f"❌ Formato de --start inválido: {s!r}. Usá 'YYYY-MM-DD HH:MM'.")


def _video_path(row: dict) -> Path:
    raw = (row.get("output_path") or row.get("clip_path") or "").strip()
    return Path(raw)


def main():
    # La consola de Windows usa cp1252 y revienta con emojis; forzamos UTF-8.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Programa publicaciones en Postiz desde el CSV de captions.")
    ap.add_argument("csv_path", help="Ruta al CSV de captions generado por el pipeline")
    ap.add_argument("--start", help="Fecha/hora local del 1er post (YYYY-MM-DD HH:MM). Default: mañana 09:00")
    ap.add_argument("--interval-hours", type=float, default=24.0, help="Horas entre clips (default 24)")
    ap.add_argument("--platforms", default="tiktok,instagram,youtube",
                    help="Plataformas separadas por coma (default todas)")
    ap.add_argument("--type", default="schedule", choices=["schedule", "draft", "now"],
                    help="schedule (programado), draft (borrador) o now (publicar ya)")
    ap.add_argument("--limit", type=int, default=0, help="Procesar solo los primeros N clips (0 = todos)")
    ap.add_argument("--dry-run", action="store_true", help="No llama a la API; solo muestra el plan")
    args = ap.parse_args()

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        raise SystemExit(f"❌ No existe el CSV: {csv_path}")

    platforms = [p.strip().lower() for p in args.platforms.split(",") if p.strip()]
    bad = [p for p in platforms if p not in PLATFORM_CAPTION_FIELD]
    if bad:
        raise SystemExit(f"❌ Plataformas no soportadas: {bad}. Válidas: {list(PLATFORM_CAPTION_FIELD)}")

    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if args.limit:
        rows = rows[:args.limit]
    if not rows:
        raise SystemExit("❌ El CSV no tiene filas.")

    start = _parse_start(args.start)

    # Cliente + descubrimiento de canales (salvo dry-run sin key)
    client   = None
    channels = {}
    if not args.dry_run:
        client   = PostizClient()
        channels = client.channel_map()
        faltan = [p for p in platforms if p not in channels]
        if faltan:
            print(f"⚠️  Sin canal conectado en Postiz para: {faltan} (se omiten).")
        platforms = [p for p in platforms if p in channels]
        if not platforms:
            raise SystemExit("❌ Ninguna de las plataformas pedidas tiene canal conectado en Postiz.")

    n_req = len(rows) * 2  # 1 upload + 1 post por clip
    print(f"\n📋 {len(rows)} clips × {len(platforms)} plataformas — modo: "
          f"{'DRY-RUN' if args.dry_run else args.type.upper()}")
    print(f"   1er post: {start:%Y-%m-%d %H:%M} (local) · cada {args.interval_hours:g} h")
    if not args.dry_run and n_req > 30:
        print(f"   ⚠️  Son ~{n_req} requests; Postiz limita a 30/hora. Considerá --limit o correrlo por tandas.\n")

    ok, fail = 0, 0
    for i, row in enumerate(rows):
        when     = start + timedelta(hours=args.interval_hours * i)
        date_iso = to_utc_iso(when)
        title    = row.get("clip_title", f"clip {i+1}")
        vid      = _video_path(row)
        serie    = f" [serie {row.get('serie')} {row.get('parte')}]" if row.get("parte") else ""

        print(f"\n[{i+1}/{len(rows)}] {when:%Y-%m-%d %H:%M} · {title}{serie}")
        print(f"    🎬 {vid.name}")

        if args.dry_run:
            for p in platforms:
                cap = (row.get(PLATFORM_CAPTION_FIELD[p]) or "").strip().replace("\n", " ")
                print(f"    └ {p:9s}: {cap[:80]}{'…' if len(cap) > 80 else ''}")
            continue

        if not vid.exists():
            print(f"    ❌ Video no encontrado, se omite: {vid}")
            fail += 1
            continue

        try:
            media = client.upload(vid)
            posts = build_posts_for_clip(row, channels, media, platforms)
            if not posts:
                print("    ⚠️  Sin captions para las plataformas elegidas, se omite.")
                continue
            res = client.create_post(posts, date_iso, post_type=args.type)
            pid = res[0].get("id") if isinstance(res, list) and res else res
            print(f"    ✅ Programado ({len(posts)} canales) · id={pid}")
            ok += 1
        except Exception as e:
            print(f"    ❌ Error: {e}")
            fail += 1

    print(f"\n{'═'*50}")
    if args.dry_run:
        print("DRY-RUN completo (no se creó nada). Quitá --dry-run para programar.")
    else:
        print(f"Listo: {ok} programados, {fail} con error.")


if __name__ == "__main__":
    main()
