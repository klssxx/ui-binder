"""OCR endpoints: leer texto de la referencia y borrarlo (inpainting)."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from PIL import Image
from pydantic import BaseModel

from backend import config
from backend.api.common import get_store
from backend.logging_setup import log
from backend.vision import ocr

router = APIRouter(tags=["ocr"])


def _load_image(ws_id: str, image_id: Optional[str]) -> Image.Image:
    store = get_store()
    img = store.get_image(image_id) if image_id else store.get_reference_image(ws_id)
    if img is None:
        raise HTTPException(409, "No hay imagen de referencia: importa un screenshot primero.")
    path = Path(img["path"])
    if not path.is_file():
        raise HTTPException(410, "La imagen no está en disco; vuelve a importarla.")
    with Image.open(path) as im:
        im.load()
        return im


class OcrRequest(BaseModel):
    bbox: Optional[dict[str, float]] = None
    image_id: Optional[str] = None


class EraseRequest(BaseModel):
    bboxes: list[dict[str, float]]
    image_id: Optional[str] = None


@router.get("/ocr/status")
def ocr_status() -> dict[str, Any]:
    ok, provider = ocr.ocr_available()
    return {"available": ok, "provider": "rapidocr" if ok else None, "detail": provider if not ok else ""}


@router.post("/workspaces/{ws_id}/ocr")
def read_text(ws_id: str, body: OcrRequest) -> dict[str, Any]:
    if not get_store().workspace_exists(ws_id):
        raise HTTPException(404, f"Workspace '{ws_id}' no existe.")
    try:
        image = _load_image(ws_id, body.image_id)
        lines = ocr.read_lines(image, body.bbox)
    except HTTPException:
        raise  # los 409/410 de _load_image deben llegar tal cual al cliente
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        log(ws_id, "ERROR", "ocr failed", error=str(exc))
        raise HTTPException(422, f"El OCR falló sobre la imagen: {exc}") from exc
    return {"lines": lines, "count": len(lines),
            "note": "El texto del OCR es una inferencia (mira la confidence); "
                    "corregirlo a mano lo convierte en hecho."}


@router.post("/workspaces/{ws_id}/ocr/erase")
def erase_text(ws_id: str, body: EraseRequest) -> dict[str, Any]:
    store = get_store()
    if not store.workspace_exists(ws_id):
        raise HTTPException(404, f"Workspace '{ws_id}' no existe.")
    if not body.bboxes:
        raise HTTPException(422, "Sin cajas que borrar.")
    source = store.get_image(body.image_id) if body.image_id else store.get_reference_image(ws_id)
    if source is None:
        raise HTTPException(409, "No hay imagen de referencia que limpiar.")
    path = Path(source["path"])
    if not path.is_file():
        raise HTTPException(410, "La imagen no está en disco; vuelve a importarla.")
    with Image.open(path) as im:
        im.load()
        cleaned = ocr.erase_regions(im, body.bboxes)
    data = ocr.to_png_bytes(cleaned)

    ws_dir = config.workspaces_root() / ws_id / "images"
    ws_dir.mkdir(parents=True, exist_ok=True)
    dest = ws_dir / f"cleaned_{hashlib.sha256(data).hexdigest()[:16]}.png"
    dest.write_bytes(data)
    record = store.add_image(
        ws_id, role="cleaned", filename=f"cleaned_{source['filename']}", path=str(dest),
        width=cleaned.width, height=cleaned.height, size_bytes=len(data),
        fmt="PNG", sha256=hashlib.sha256(data).hexdigest(),
    )
    log(ws_id, "INFO", "ocr erase (inpaint)", boxes=len(body.bboxes), new_image=record["id"])
    return {"image": record, "erased_boxes": len(body.bboxes)}
