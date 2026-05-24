"""
Renderiza clips en formato vertical 9:16 con subtítulos usando Remotion.
"""

import json
import math
import platform
import socketserver
import subprocess
import tempfile
import threading
import http.server
from pathlib import Path

import config

# En Windows, subprocess no puede ejecutar npx.ps1; usa npx.cmd
_NPX = "npx.cmd" if platform.system() == "Windows" else "npx"

_CLIP_SERVER_PORT = 19876


class _ClipServer:
    """
    Servidor HTTP local que expone la carpeta de clips para que
    Chromium (Puppeteer de Remotion) pueda cargar los videos.
    Chromium bloquea file:// pero permite http://127.0.0.1.
    """

    def __init__(self, directory: Path, port: int = _CLIP_SERVER_PORT):
        self._port = port
        dir_str = str(directory)

        class _Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *a, **kw):
                super().__init__(*a, directory=dir_str, **kw)
            def log_message(self, *_):
                pass

        class _Server(socketserver.TCPServer):
            allow_reuse_address = True  # debe ser atributo de clase para aplicar antes del bind

        self._server = _Server(("127.0.0.1", port), _Handler)

    def start(self):
        t = threading.Thread(target=self._server.serve_forever, daemon=True)
        t.start()

    def stop(self):
        self._server.shutdown()

    def url_for(self, file_path: Path) -> str:
        return f"http://127.0.0.1:{self._port}/{file_path.name}"


def render_clip(
    clip_path: Path,
    subtitles: list[dict],
    output_path: Path,
    clip_title: str = "",
    clip_url: str | None = None,
    duration_frames: int | None = None,
) -> Path:
    """
    Llama a Remotion para renderizar el clip en 9:16 con subtítulos superpuestos.

    clip_url: URL HTTP del clip (si se sirve via _ClipServer).
              Si None, usa clip_path como string (puede fallar en Chromium).
    duration_frames: frames totales del clip; si se pasa, evita que calculateMetadata
                     intente cargar el video antes de renderizar.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    props = {
        "clipPath":  clip_url or str(clip_path).replace("\\", "/"),
        "subtitles": subtitles,
        "title":     clip_title,
        "width":     config.OUTPUT_WIDTH,
        "height":    config.OUTPUT_HEIGHT,
        "fps":       config.OUTPUT_FPS,
    }
    if duration_frames is not None:
        props["durationInFrames"] = duration_frames

    # Escribir props en archivo JSON sin BOM (Remotion en Windows lo requiere)
    props_file = Path(tempfile.mktemp(suffix=".json"))
    props_file.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")

    try:
        cmd = [
            _NPX, "remotion", "render",
            "src/index.ts",
            "ClipComposition",
            str(output_path).replace("\\", "/"),
            f"--props={props_file}",
            "--width",  str(config.OUTPUT_WIDTH),
            "--height", str(config.OUTPUT_HEIGHT),
            "--fps",    str(config.OUTPUT_FPS),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(config.REMOTION_DIR),
        )
    finally:
        props_file.unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(f"Remotion falló:\n{result.stderr[-2000:]}")

    return output_path


def render_clips(
    clips_with_subs: list[dict],
    output_dir: Path,
    video_id: str,
    progress_fn: "Callable[[int, int, str], None] | None" = None,
) -> list[dict]:
    """
    Renderiza todos los clips y retorna la lista con output_path añadido.
    progress_fn(done, total, titulo) se llama antes de cada clip y al finalizar.
    """
    server = _ClipServer(config.CLIPS_DIR)
    server.start()

    total   = len(clips_with_subs)
    results = []
    try:
        for done, clip in enumerate(clips_with_subs):
            idx   = clip["index"]
            title = clip.get("title", f"Clip {idx}")
            name  = _clip_filename(title, idx)
            output_path = output_dir / f"{name} - vertical.mp4"

            if progress_fn:
                progress_fn(done, total, title)

            clip_url        = server.url_for(clip["clip_path"])
            duration_frames = math.ceil(
                (clip["end"] - clip["start"]) * config.OUTPUT_FPS
            )

            print(f"  🎬 [{done+1}/{total}] {title}")

            render_clip(
                clip_path=clip["clip_path"],
                subtitles=clip.get("subtitles", []),
                output_path=output_path,
                clip_title=title,
                clip_url=clip_url,
                duration_frames=duration_frames,
            )

            results.append({**clip, "output_path": output_path})

        if progress_fn:
            progress_fn(total, total, "")
    finally:
        server.stop()

    return results


def _clip_filename(title: str, index: int, max_len: int = 80) -> str:
    import re
    clean = re.sub(r'[\\/:*?"<>|]', "", title)
    clean = re.sub(r"\s+", " ", clean).strip()
    if len(clean) > max_len:
        clean = clean[:max_len].rsplit(" ", 1)[0]
    return f"{index:02d} - {clean}"
