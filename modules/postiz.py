"""
Cliente de la API pública de Postiz para programar publicaciones.

Flujo por clip:
  1. Subir el video (POST /upload) → devuelve {id, path}
  2. Crear el post (POST /posts) con una entrada por canal, cada una con su
     caption y el video, y una fecha programada.

Postiz limita a ~30 requests/hora. Cada clip consume 1 upload + 1 post = 2 req,
así que ~15 clips por hora es el techo práctico.
"""

import time
import mimetypes
from pathlib import Path
from datetime import datetime, timezone

import requests
from requests.exceptions import (
    ConnectionError as ReqConnectionError,
    Timeout,
    ChunkedEncodingError,
)

import config


# Errores transitorios: NO son culpa del payload, conviene reintentar.
#   - ConnectionReset 10054 ("conexión forzada por el host remoto"), timeouts,
#     cortes a mitad de subida → red/proxy/servidor saturado.
#   - Status 429 (rate limit) y 5xx (error del servidor).
# Los 4xx (400 settings inválidos, 401 auth) NO se reintentan: fallarían igual.
_RETRY_EXCEPTIONS = (ReqConnectionError, Timeout, ChunkedEncodingError)
_RETRY_STATUS     = {429, 500, 502, 503, 504}


# Mapeo plataforma lógica → cómo viene el `identifier` del canal en Postiz y
# qué columna de caption del CSV usar.
PLATFORM_CAPTION_FIELD = {
    "tiktok":    "caption_tiktok",
    "instagram": "caption_instagram",
    "youtube":   "caption_youtube",
}


def to_utc_iso(local_dt: datetime) -> str:
    """Hora local → ISO 8601 UTC con milisegundos (formato que pide Postiz)."""
    if local_dt.tzinfo is None:
        local_dt = local_dt.astimezone()  # asume zona local del sistema
    return local_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _platform_of(identifier: str) -> str | None:
    """Normaliza el identifier de Postiz a nuestra plataforma lógica."""
    ident = (identifier or "").lower()
    if ident.startswith("tiktok"):
        return "tiktok"
    if ident.startswith("instagram"):   # instagram, instagram-standalone
        return "instagram"
    if ident.startswith("youtube"):
        return "youtube"
    return None


class PostizClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key  = api_key  or config.POSTIZ_API_KEY
        self.base_url = (base_url or config.POSTIZ_API_URL).rstrip("/")
        if not self.api_key:
            raise EnvironmentError(
                "Falta POSTIZ_API_KEY. Agregala al .env (Settings → Public API en Postiz)."
            )
        self._session = requests.Session()
        self._session.headers.update({"Authorization": self.api_key})

    # ── Núcleo con reintentos ─────────────────────────────────────────────────

    def _send(self, make_request, *, what: str, attempts: int = 4, backoff: float = 3.0):
        """
        Ejecuta `make_request()` (que devuelve un Response) reintentando ante
        errores transitorios de red (ConnectionReset/Timeout) y status 429/5xx.

        `make_request` es un callable, no un Response, para poder REHACER la
        request en cada intento (clave en /upload: el archivo se reabre cada vez).
        Devuelve el Response final; deja que el caller decida sobre 4xx.
        """
        for attempt in range(1, attempts + 1):
            try:
                r = make_request()
            except _RETRY_EXCEPTIONS as e:
                if attempt == attempts:
                    raise RuntimeError(
                        f"Postiz {what}: error de red tras {attempts} intentos "
                        f"(red/proxy inestable, p.ej. ConnectionReset 10054): {e}"
                    ) from e
                wait = backoff * attempt
                print(f"    ⏳ {what}: error de red ({e.__class__.__name__}), "
                      f"reintento {attempt + 1}/{attempts} en {wait:g}s…")
                time.sleep(wait)
                continue

            if r.status_code in _RETRY_STATUS and attempt < attempts:
                wait = backoff * attempt
                print(f"    ⏳ {what}: HTTP {r.status_code}, "
                      f"reintento {attempt + 1}/{attempts} en {wait:g}s…")
                time.sleep(wait)
                continue
            return r

    # ── Endpoints crudos ──────────────────────────────────────────────────────

    def list_integrations(self) -> list[dict]:
        """GET /integrations → [{id, name, identifier, profile, disabled, ...}]"""
        r = self._send(
            lambda: self._session.get(f"{self.base_url}/integrations", timeout=30),
            what="GET /integrations",
        )
        r.raise_for_status()
        return r.json()

    def upload(self, file_path: Path) -> dict:
        """POST /upload (multipart 'file') → {id, path, ...}"""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"No existe el video a subir: {file_path}")
        mime = mimetypes.guess_type(str(file_path))[0] or "video/mp4"

        def _do():
            # Reabrimos el archivo en cada intento: tras un corte el handle
            # quedó a mitad de lectura y no sirve para reintentar.
            with open(file_path, "rb") as fh:
                files = {"file": (file_path.name, fh, mime)}
                return self._session.post(f"{self.base_url}/upload", files=files, timeout=300)

        r = self._send(_do, what=f"upload {file_path.name}")
        r.raise_for_status()
        return r.json()

    def create_post(
        self,
        posts: list[dict],
        date_iso: str,
        post_type: str = "schedule",
        short_link: bool = False,
        tags: list | None = None,
    ) -> dict:
        """POST /posts. `posts` ya viene armado (una entrada por canal)."""
        payload = {
            "type":      post_type,         # schedule | draft | now
            "date":      date_iso,          # ISO 8601 UTC, ej. 2026-06-20T13:00:00.000Z
            "shortLink": short_link,
            "tags":      tags or [],
            "posts":     posts,
        }
        r = self._send(
            lambda: self._session.post(f"{self.base_url}/posts", json=payload, timeout=120),
            what="POST /posts",
        )
        if r.status_code >= 400:
            # Mensaje claro con el cuerpo de la respuesta (suele explicar qué setting falta)
            raise RuntimeError(f"Postiz POST /posts {r.status_code}: {r.text[:1000]}")
        return r.json()

    # ── Helpers de alto nivel ─────────────────────────────────────────────────

    def channel_map(self) -> dict[str, dict]:
        """{plataforma_lógica: integración} para los canales habilitados."""
        result = {}
        for integ in self.list_integrations():
            if integ.get("disabled"):
                continue
            plat = _platform_of(integ.get("identifier", ""))
            if plat and plat not in result:
                result[plat] = integ
        return result


def _settings_for(platform: str, clip: dict, cover_media: dict | None = None) -> dict:
    """
    Settings por plataforma. Postiz valida campos obligatorios distintos según el
    canal (confirmado contra la API self-hosted: un POST sin estos da 400). Ajustá
    si la API rechaza algún post (el error 400 dice exactamente qué setting falta).

    cover_media: media {id, path} de la portada subida. Solo YouTube acepta
    thumbnail custom vía API pública (Instagram/TikTok no lo exponen).
    """
    if platform == "youtube":
        title = (clip.get("clip_title") or clip.get("title") or "Short")[:95]
        s = {"title": title, "type": "public"}
        if cover_media and cover_media.get("id"):
            s["thumbnail"] = {"id": cover_media["id"], "path": cover_media.get("path", "")}
        return s
    if platform == "tiktok":
        return {
            "privacy_level":          "PUBLIC_TO_EVERYONE",  # o SELF_ONLY / MUTUAL_FOLLOW_FRIENDS / FOLLOWER_OF_CREATOR
            "duet":                   False,
            "stitch":                 False,
            "comment":                True,
            "autoAddMusic":           "no",                  # "yes" | "no"
            "brand_content_toggle":   False,
            "brand_organic_toggle":   False,
            "content_posting_method": "DIRECT_POST",         # DIRECT_POST | UPLOAD
        }
    if platform == "instagram":
        return {"post_type": "post"}  # post | story
    return {}


def _caption_of(clip: dict, platform: str) -> str:
    """
    Lee el caption de una plataforma soportando ambos formatos de clip:
    - fila de CSV:    {"caption_tiktok": "..."}
    - clip en memoria: {"captions": {"tiktok": "..."}}
    """
    flat = clip.get(PLATFORM_CAPTION_FIELD[platform])
    if flat:
        return flat.strip()
    caps = clip.get("captions") or {}
    return (caps.get(platform) or "").strip()


def maybe_upload_cover(client: "PostizClient", clip: dict, platforms: list[str]) -> dict | None:
    """
    Sube la portada SOLO si YouTube está entre las plataformas y existe el archivo.
    Devuelve el media {id, path} o None. Es best-effort: si la subida falla, devuelve
    None y el post se programa igual (sin thumbnail custom) en vez de tumbar todo.

    YouTube es el único canal cuya API pública acepta thumbnail custom; Instagram
    y TikTok no lo exponen (su cover se elige dentro de la app).
    """
    if "youtube" not in platforms:
        return None
    raw = (clip.get("cover_path") or "").strip()
    if not raw:
        return None
    cover = Path(raw)
    if not cover.exists():
        return None
    try:
        return client.upload(cover)
    except Exception as e:
        print(f"    ⚠️  No se pudo subir la portada ({cover.name}): {e}. Sigo sin thumbnail.")
        return None


def build_posts_for_clip(
    clip: dict,
    channels: dict[str, dict],
    media: dict,
    platforms: list[str],
    cover_media: dict | None = None,
) -> list[dict]:
    """
    Arma el array `posts` (una entrada por plataforma) para un clip.

    clip:        fila del CSV o clip en memoria (ver _caption_of).
    channels:    {plataforma: integración} de PostizClient.channel_map().
    media:       dict devuelto por upload() ({id, path}).
    cover_media: media de la portada (ver maybe_upload_cover); se usa solo en YouTube.
    """
    image = [{"id": media["id"], "path": media.get("path", "")}]
    group = str(clip.get("clip_index") or clip.get("index")
                or clip.get("clip_title") or clip.get("title") or media["id"])

    posts = []
    for plat in platforms:
        integ = channels.get(plat)
        if not integ:
            continue
        content = _caption_of(clip, plat)
        if not content:
            continue
        posts.append({
            "integration": {"id": integ["id"]},
            "value":       [{"content": content, "image": image}],
            "group":       group,
            "settings":    _settings_for(plat, clip, cover_media),
        })
    return posts
