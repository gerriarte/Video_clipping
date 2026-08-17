"""
Arte final: la pasada de terminación que al pipeline le faltaba.

Hasta acá el archivo salía de Remotion y se iba derecho a redes. El problema es
que el recorte 9:16 amplía la imagen 1.78x (de una franja de 607 px de ancho a
1080) y ese escalado lo hace el navegador, que entrega menos definición que
ffmpeg sobre el MISMO frame:

    recorte 9:16 hecho con ffmpeg (lanczos) ....... 25.4
    el mismo frame saliendo de Remotion ........... 18.4
    (varianza del Laplaciano del plano de luma, mayor = más detalle)

Se midió también con el clip ya pre-escalado, sin nada que ampliar, y Remotion
sigue entregando menos (21.2): el escalador del navegador es el techo mientras
Remotion componga los píxeles.

Ojo al re-medir: hay que hacerlo sobre la LUMA cruda, no sobre un PNG extraído
con ffmpeg. Esa extracción convierte YUV->RGB según las etiquetas de color del
archivo, y dos archivos pixel-idénticos (mismo md5 del YUV decodificado) llegaron
a dar 38.7 y 76.6 solo por estar etiquetados distinto.

Lo que sí se puede hacer es recuperar definición después, que es para lo que
existe un paso de arte final:

    sin realce .... 18.4     unsharp 1.0 .... 40.7
    unsharp 0.6 ... 29.5     unsharp 1.5 .... 57.4 (halo visible en el pelo)

Con 0.6 ya se supera el recorte de ffmpeg; 1.0 es el valor verificado a ojo sin
halos sobre material real. Si en algún clip se ve procesado, bajarlo es seguro.

Además esta pasada deja el archivo como lo esperan las redes: yuv420p, bt709
etiquetado, y el índice al principio para que empiece a reproducir sin bajar todo.
"""

import subprocess
from pathlib import Path
from typing import Callable

# Realce. `unsharp=lx:ly:amount` con amount 1.0 es el punto donde se recupera
# definición sin que aparezca halo (ver los números en el docstring de arriba).
SHARPEN = "unsharp=5:5:1.0:5:5:0.0"

# Destramado. Apagado por defecto: sobre este material no se notó diferencia
# (el escalado del navegador ya suaviza el ruido de compresión) y de más
# arriesga ablandar todavía más. Sirve si la fuente viene con mucho ruido.
DENOISE = "hqdn3d=1.5:1.5:6:6"

# Calidad del encode final. 18 es visualmente sin pérdida para redes, que de
# todos modos re-comprimen a 4–6 Mbps.
CRF     = 18
PRESET  = "slow"


def build_filter(sharpen: bool = True, denoise: bool = False,
                 extra: str | None = None) -> str:
    """
    Cadena de filtros de la pasada final (vacía si no hay nada que aplicar).

    El orden importa: primero se destrama y después se realza. Al revés se
    estaría afilando el ruido para después intentar borrarlo.
    """
    parts = []
    if denoise:
        parts.append(DENOISE)
    if sharpen:
        parts.append(SHARPEN)
    if extra:
        parts.append(extra)
    return ",".join(parts)


def finish(
    src: Path,
    dst: Path,
    sharpen: bool = True,
    denoise: bool = False,
    extra_filter: str | None = None,
    crf: int = CRF,
    progress_fn: Callable[[str], None] | None = None,
) -> Path:
    """
    Deja `dst` listo para publicar a partir del render crudo `src`.

    El audio se copia tal cual: ya viene normalizado a -14 LUFS desde el corte,
    y volver a codificarlo solo sumaría una generación de pérdida.

    Si ffmpeg falla se propaga la excepción: quien llama decide si publicar el
    crudo o cortar. Nunca se escribe un `dst` a medias.
    """
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    vf = build_filter(sharpen=sharpen, denoise=denoise, extra=extra_filter)

    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-loglevel", "error",
           "-i", str(src)]
    if vf:
        cmd += ["-vf", vf]
    cmd += [
        "-c:v", "libx264",
        "-crf", str(crf),
        "-preset", PRESET,
        "-pix_fmt", "yuv420p",
        # Etiquetado explícito: sin esto cada reproductor adivina la matriz y el
        # material se ve con otros colores en cada lado.
        #
        # Va por -x264-params y no por los -color_* de ffmpeg: con estos últimos
        # solo quedaba escrita la matriz, y primaries/transfer salían "unknown"
        # (verificado con ffprobe sobre la salida).
        "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709",
        "-c:a", "copy",
        "-movflags", "+faststart",
        "-y", str(dst),
    ]

    if progress_fn:
        progress_fn(f"Arte final: {vf or 'solo re-encode'}")

    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(
            "ffmpeg falló en el arte final:\n" + (r.stderr or "")[-1000:]
        )
    return dst
