"""
Cliente de la API pública de Postiz para programar publicaciones.

Flujo por clip:
  1. Subir el video (POST /upload) → devuelve {id, path}
  2. Crear el post (POST /posts) con una entrada por canal, cada una con su
     caption y el video, y una fecha programada.

Postiz limita a ~30 requests/hora. Cada clip consume 1 upload + 1 post = 2 req,
así que ~15 clips por hora es el techo práctico.
"""

import mimetypes
from pathlib import Path
from datetime import datetime, timezone

import requests

import config


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

    # ── Endpoints crudos ──────────────────────────────────────────────────────

    def list_integrations(self) -> list[dict]:
        """GET /integrations → [{id, name, identifier, profile, disabled, ...}]"""
        r = self._session.get(f"{self.base_url}/integrations", timeout=30)
        r.raise_for_status()
        return r.json()

    def upload(self, file_path: Path) -> dict:
        """POST /upload (multipart 'file') → {id, path, ...}"""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"No existe el video a subir: {file_path}")
        mime = mimetypes.guess_type(str(file_path))[0] or "video/mp4"
        with open(file_path, "rb") as fh:
            files = {"file": (file_path.name, fh, mime)}
            r = self._session.post(f"{self.base_url}/upload", files=files, timeout=300)
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
        r = self._session.post(f"{self.base_url}/posts", json=payload, timeout=120)
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


def _settings_for(platform: str, clip: dict) -> dict:
    """
    Settings por plataforma. Postiz valida campos obligatorios distintos según el
    canal (confirmado contra la API self-hosted: un POST sin estos da 400). Ajustá
    si la API rechaza algún post (el error 400 dice exactamente qué setting falta).
    """
    if platform == "youtube":
        title = (clip.get("clip_title") or clip.get("title") or "Short")[:95]
        return {"title": title, "type": "public"}
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


def build_posts_for_clip(
    clip: dict,
    channels: dict[str, dict],
    media: dict,
    platforms: list[str],
) -> list[dict]:
    """
    Arma el array `posts` (una entrada por plataforma) para un clip.

    clip:     fila del CSV o clip en memoria (ver _caption_of).
    channels: {plataforma: integración} de PostizClient.channel_map().
    media:    dict devuelto por upload() ({id, path}).
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
            "settings":    _settings_for(plat, clip),
        })
    return posts
