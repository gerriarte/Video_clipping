"""
Leer imágenes sin que el nombre del archivo decida si funciona.

`cv2.imread` en Windows abre el archivo con la *code page* ANSI del sistema, no
con UTF-8. Con una `ó` en la ruta no encuentra nada y devuelve `None` — sin
excepción, sin aviso. Y como el `video_id` de esta app sale del título del
episodio, "Automatización con IA" alcanzaba para que la detección de caras
midiera **cero caras en todos los frames** y la app concluyera "sin caras el
100% del clip", con las caras a la vista en la miniatura de al lado.

La vuelta conocida es leer los bytes desde Python (que sí entiende la ruta) y
dejar que OpenCV decodifique el buffer.
"""

from pathlib import Path


def imread(path, flags=None):
    """
    Como `cv2.imread`, pero sirve con acentos en la ruta.

    Devuelve None igual que el original si el archivo no existe o no se puede
    decodificar, así reemplazarlo no cambia el manejo de errores de nadie.
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None

    if flags is None:
        flags = cv2.IMREAD_COLOR

    try:
        data = Path(path).read_bytes()
    except OSError:
        return None
    if not data:
        return None

    try:
        return cv2.imdecode(np.frombuffer(data, np.uint8), flags)
    except Exception:
        return None
