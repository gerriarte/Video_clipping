"""
Geometría de recorte (pura, testeable). El mismo rectángulo lo consume el preview
(OpenCV) y el render (Remotion `manualCrops`), así coinciden pixel a pixel.
"""


def crop_rect(src_w: int, src_h: int, target_aspect: float,
              center_x: float, zoom: float, center_y: float = 0.42) -> dict:
    """
    Rectángulo (fracciones 0–1 de la fuente) de aspecto `target_aspect`, centrado
    en (center_x, center_y) y acercado por `zoom` (>=1 = más cerrado).
    """
    S = (src_w / src_h) if src_h else (16 / 9)
    if target_aspect <= S:      # destino más angosto que la fuente → recorte horizontal
        rw0, rh0 = target_aspect / S, 1.0
    else:                       # destino más ancho → recorte vertical
        rw0, rh0 = 1.0, S / target_aspect
    z = max(1.0, float(zoom))
    w = rw0 / z
    h = rh0 / z
    x = min(max(center_x - w / 2, 0.0), max(0.0, 1.0 - w))
    y = min(max(center_y - h / 2, 0.0), max(0.0, 1.0 - h))
    return {"x": round(x, 5), "y": round(y, 5), "w": round(w, 5), "h": round(h, 5)}


def crop_from_rect(img, rect: dict):
    """Recorta el rectángulo (fracciones) de un frame (numpy BGR) para el preview."""
    h, w = img.shape[:2]
    x0 = max(0, int(round(rect["x"] * w)))
    y0 = max(0, int(round(rect["y"] * h)))
    x1 = min(w, int(round((rect["x"] + rect["w"]) * w)))
    y1 = min(h, int(round((rect["y"] + rect["h"]) * h)))
    if x1 <= x0 or y1 <= y0:
        return img.copy()
    return img[y0:y1, x0:x1].copy()
