"""OCR local (RapidOCR/onnxruntime) + borrado del texto original (inpainting).

Política de confianza (SKILL.md): lo que dice el OCR es una inferencia con su
score; la corrección manual del usuario es un FACT. Nunca se oculta el score.
"""
from __future__ import annotations

import io
from typing import Any

import cv2
import numpy as np
from PIL import Image

_engine = None
_import_error: str | None = None


def ocr_available() -> tuple[bool, str]:
    global _engine, _import_error
    if _engine is not None:
        return True, "rapidocr"
    if _import_error is not None:
        return False, _import_error
    try:
        from rapidocr_onnxruntime import RapidOCR  # type: ignore

        _engine = RapidOCR()
        return True, "rapidocr"
    except Exception as exc:  # import o modelo roto
        _import_error = f"{exc.__class__.__name__}: {exc}"
        return False, _import_error


def read_lines(image: Image.Image, bbox: dict[str, float] | None = None) -> list[dict[str, Any]]:
    """OCR sobre la imagen (o el recorte bbox). Devuelve líneas con estilo inferido."""
    ok, provider = ocr_available()
    if not ok:
        raise RuntimeError(f"OCR no disponible ({provider}). Instala rapidocr-onnxruntime.")
    rgb = np.asarray(image.convert("RGB"))
    if bbox:
        x = max(0, int(bbox.get("x", 0)))
        y = max(0, int(bbox.get("y", 0)))
        x2 = min(rgb.shape[1], int(x + bbox.get("width", 0)))
        y2 = min(rgb.shape[0], int(y + bbox.get("height", 0)))
        if x2 <= x or y2 <= y:
            return []
        roi = rgb[y:y2, x:x2]
        ox, oy = x, y
    else:
        roi = rgb
        ox, oy = 0, 0

    result, _ = _engine(roi)
    lines: list[dict[str, Any]] = []
    if not result:
        return lines
    for box, text, score in result:
        pts = np.asarray(box, dtype=int)
        x0, y0 = int(pts[:, 0].min()), int(pts[:, 1].min())
        x1, y1 = int(pts[:, 0].max()), int(pts[:, 1].max())
        # color de tinta: el cuartil MÁS LEJANO del fondo local de la caja
        crop = roi[max(0, y0):y1, max(0, x0):x1]
        color = "#e8eaf0"
        if crop.size:
            lum = crop.mean(axis=2)
            flat = crop.reshape(-1, 3)
            bg_lum = float(np.median(lum))
            order = np.argsort(lum.reshape(-1))
            n = max(1, flat.shape[0] // 8)
            # fondo claro → tinta oscura (cuartil más oscuro); fondo oscuro → tinta clara
            quartile = flat[order[:n]] if bg_lum > 128 else flat[order[-n:]]
            color = "#{:02x}{:02x}{:02x}".format(*(int(v) for v in quartile.mean(axis=0)))
        lines.append({
            "text": str(text).strip(),
            "bbox": {"x": float(ox + x0), "y": float(oy + y0),
                     "width": float(x1 - x0), "height": float(y1 - y0)},
            "confidence": round(float(score), 3),
            "color": color,
            "fontSize": round((y1 - y0) * 0.85),
        })
    lines.sort(key=lambda l: (l["bbox"]["y"], l["bbox"]["x"]))
    return lines


def erase_regions(image: Image.Image, bboxes: list[dict[str, float]]) -> Image.Image:
    """Borra el texto de las cajas con inpainting TELEA.

    La máscara se construye por caja con tinta local (diferencia del fondo
    mediano de la propia caja, dilatada) — no borra todo el rectángulo a ciegas.
    """
    rgb = np.asarray(image.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    mask = np.zeros(gray.shape, dtype=np.uint8)
    for b in bboxes:
        x = max(0, int(b.get("x", 0)))
        y = max(0, int(b.get("y", 0)))
        x2 = min(rgb.shape[1], int(x + b.get("width", 0)))
        y2 = min(rgb.shape[0], int(y + b.get("height", 0)))
        if x2 <= x or y2 <= y:
            continue
        roi = gray[y:y2, x:x2]
        border = np.concatenate([roi[0, :], roi[-1, :], roi[:, 0], roi[:, -1]])
        bg = float(np.median(border)) if border.size else float(np.median(roi))
        ink = np.abs(roi.astype(np.int16) - int(bg)).astype(np.uint8)
        _, binm = cv2.threshold(ink, 22, 255, cv2.THRESH_BINARY)
        binm = cv2.morphologyEx(binm, cv2.MORPH_DILATE, np.ones((5, 5), np.uint8))
        mask[y:y2, x:x2] = cv2.bitwise_or(mask[y:y2, x:x2], binm)
    if mask.any():
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        cleaned = cv2.inpaint(bgr, mask, 3, cv2.INPAINT_TELEA)
        return Image.fromarray(cv2.cvtColor(cleaned, cv2.COLOR_BGR2RGB))
    return image


def to_png_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()
