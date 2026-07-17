"""
Server HTTP local con soporte de Range requests, para servir el video al iframe
del editor de timeline. El SimpleHTTPRequestHandler por defecto no responde 206,
y sin Range el navegador no puede hacer seek en videos grandes.
"""

import os
import re
import http.server
import socketserver
import threading
from pathlib import Path
from urllib.parse import quote


class _RangeHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_):  # silencio
        pass

    def _send_file(self, head_only: bool = False):
        path = self.translate_path(self.path)
        if not os.path.isfile(path):
            self.send_error(404, "File not found")
            return

        fs = os.path.getsize(path)
        ctype = self.guess_type(path)
        rng = self.headers.get("Range")

        start, end = 0, fs - 1
        partial = False
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng.strip())
            if m:
                if m.group(1):
                    start = int(m.group(1))
                if m.group(2):
                    end = int(m.group(2))
                end = min(end, fs - 1)
                if start > end or start >= fs:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{fs}")
                    self.end_headers()
                    return
                partial = True

        length = end - start + 1
        self.send_response(206 if partial else 200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{fs}")
        self.send_header("Content-Length", str(length))
        self.end_headers()

        if head_only:
            return

        with open(path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(65536, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    break
                remaining -= len(chunk)

    def do_GET(self):
        self._send_file(head_only=False)

    def do_HEAD(self):
        self._send_file(head_only=True)


class _ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class MediaServer:
    """Sirve `directory` en 127.0.0.1:port con soporte de Range."""

    def __init__(self, directory: Path, port: int):
        self._port = port
        dir_str = str(directory)

        class _Handler(_RangeHandler):
            def __init__(self, *a, **kw):
                super().__init__(*a, directory=dir_str, **kw)

        _Handler.protocol_version = "HTTP/1.1"
        self._server = _ThreadingServer(("127.0.0.1", port), _Handler)
        self._dir = Path(directory)

    def start(self):
        t = threading.Thread(target=self._server.serve_forever, daemon=True)
        t.start()

    def stop(self):
        self._server.shutdown()

    def url_for(self, file_path: Path) -> str:
        """URL respetando subcarpetas de la raíz servida."""
        vp = Path(file_path)
        try:
            rel = vp.relative_to(self._dir).as_posix()
        except ValueError:
            rel = vp.name
        return f"http://127.0.0.1:{self._port}/{quote(rel)}"
