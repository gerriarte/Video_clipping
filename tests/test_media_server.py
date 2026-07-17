import tempfile
import urllib.request
from pathlib import Path

from modules.media_server import MediaServer


def _make_file(nbytes=25600):
    d = Path(tempfile.mkdtemp())
    f = d / "sub dir" / "a.bin"   # subcarpeta con espacio (caso real)
    f.parent.mkdir(parents=True, exist_ok=True)
    data = bytes(range(256)) * (nbytes // 256)
    f.write_bytes(data)
    return d, f, data


def test_range_request_returns_206_and_correct_bytes():
    d, f, data = _make_file()
    srv = MediaServer(d)
    srv.start()
    try:
        url = srv.url_for(f)
        req = urllib.request.Request(url, headers={"Range": "bytes=10-19"})
        resp = urllib.request.urlopen(req, timeout=5)
        assert resp.getcode() == 206
        assert resp.read() == data[10:20]
        assert resp.headers.get("Content-Range") == f"bytes 10-19/{len(data)}"
        assert resp.headers.get("Accept-Ranges") == "bytes"
    finally:
        srv.stop()


def test_full_request_returns_200_full_length():
    d, f, data = _make_file()
    srv = MediaServer(d)
    srv.start()
    try:
        resp = urllib.request.urlopen(srv.url_for(f), timeout=5)
        assert resp.getcode() == 200
        assert len(resp.read()) == len(data)
    finally:
        srv.stop()


def test_open_range_to_end():
    d, f, data = _make_file()
    srv = MediaServer(d)
    srv.start()
    try:
        req = urllib.request.Request(srv.url_for(f), headers={"Range": "bytes=25590-"})
        resp = urllib.request.urlopen(req, timeout=5)
        assert resp.getcode() == 206
        assert resp.read() == data[25590:]
    finally:
        srv.stop()


def test_ephemeral_port_is_assigned():
    d, _, _ = _make_file()
    srv = MediaServer(d)
    try:
        assert srv.port > 0
    finally:
        srv._server.server_close()
