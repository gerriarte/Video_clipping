"""
Qué material hay para trabajar.

Existe para que cargar un video local deje de ser escribir a mano
`C:\\Videos\\mi_video.mp4`. La app corre en el navegador pero el archivo está en
el disco del servidor (la misma máquina), así que un `file_uploader` obligaría a
subir varios GB por HTTP para terminar donde ya estaban: lo correcto es
mostrarle al usuario lo que hay y que elija.
"""

from pathlib import Path

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".webm", ".m4v", ".avi"}

# Archivos que genera la propia app a partir del material. Si aparecieran en la
# lista, elegirlos sería trabajar sobre una copia degradada sin enterarse.
DERIVED_STEMS = (".proxy480",)

# Carpetas de trabajo de la app: lo que hay adentro son resultados, no fuentes.
SKIP_DIRS = {"_previews", "_archivo", "node_modules", "__pycache__", ".git"}


def is_source_video(path: Path) -> bool:
    """Si el archivo es material de origen y no algo que generamos nosotros."""
    if path.suffix.lower() not in VIDEO_EXTS:
        return False
    if any(parte in SKIP_DIRS for parte in path.parts):
        return False
    return not any(path.stem.endswith(s) for s in DERIVED_STEMS)


def find_videos(root, limit: int = 60) -> list[dict]:
    """
    Los videos que hay bajo `root`, del más nuevo al más viejo.

    Devuelve [{path, name, parent, size_mb, mtime}]. Si la carpeta no existe
    devuelve [] en vez de levantar: la ruta la escribe el usuario en Ajustes y
    equivocarse no tiene que romper la pantalla de inicio.
    """
    # Ojo: Path("") es Path("."), o sea el proyecto entero. Sin este corte, una
    # carpeta vacía en Ajustes listaría los renders de `output/` como si fueran
    # material de origen.
    if not str(root or "").strip():
        return []
    root = Path(root)
    if not root.is_dir():
        return []

    encontrados = []
    for p in root.rglob("*"):
        try:
            if not p.is_file() or not is_source_video(p):
                continue
            st = p.stat()
        except OSError:
            continue  # permisos, enlaces rotos, archivos que se movieron
        encontrados.append({
            "path":    str(p),
            "name":    p.name,
            "parent":  p.parent.name if p.parent != root else "",
            "size_mb": st.st_size / (1024 * 1024),
            "mtime":   st.st_mtime,
        })

    encontrados.sort(key=lambda d: d["mtime"], reverse=True)
    return encontrados[:limit]


def label_for(video: dict) -> str:
    """Cómo se lee en la lista: nombre, de dónde salió y cuánto pesa."""
    partes = [video["name"]]
    if video.get("parent"):
        partes.append(f"· {video['parent']}")
    partes.append(f"· {video['size_mb']:.0f} MB")
    return " ".join(partes)
