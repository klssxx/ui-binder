"""Image import: file upload, clipboard paste payload, serving, metadata."""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError

from backend import config
from backend.api.common import get_store
from backend.api.workspaces import router as ws_router  # noqa: F401  (tag grouping)
from backend.logging_setup import log

router = APIRouter(tags=["images"])


def _save_image(ws_id: str, data: bytes, filename: str, role: str) -> dict[str, Any]:
    store = get_store()
    if len(data) > config.MAX_IMAGE_BYTES:
        raise HTTPException(413, f"Image too large (> {config.MAX_IMAGE_BYTES // (1024*1024)} MB).")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(422, f"Invalid or unsupported image: {exc}") from exc
    if img.format not in config.ALLOWED_IMAGE_FORMATS:
        raise HTTPException(422, f"Format '{img.format}' not supported (PNG/JPEG/WEBP).")

    ws_dir = config.workspaces_root() / ws_id / "images"
    ws_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(filename or "paste.png").name or "paste.png"
    suffix = Path(safe_name).suffix or ".png"
    dest = ws_dir / f"{hashlib.sha256(data).hexdigest()[:16]}{suffix}"
    dest.write_bytes(data)

    record = store.add_image(
        ws_id, role=role, filename=safe_name, path=str(dest),
        width=img.width, height=img.height, size_bytes=len(data),
        fmt=img.format, sha256=hashlib.sha256(data).hexdigest(),
    )
    log(ws_id, "INFO", "image imported", image_id=record["id"], size=[img.width, img.height])
    return record


@router.post("/workspaces/{ws_id}/images", status_code=201)
async def upload_image(ws_id: str, file: UploadFile = File(...), role: str = "reference") -> dict:
    if not get_store().workspace_exists(ws_id):
        raise HTTPException(404, f"Workspace '{ws_id}' not found.")
    data = await file.read()
    return _save_image(ws_id, data, file.filename or "upload.png", role)


@router.get("/images/{image_id}")
def image_meta(image_id: str) -> dict[str, Any]:
    img = get_store().get_image(image_id)
    if img is None:
        raise HTTPException(404, "Image not found.")
    return img


@router.get("/images/{image_id}/file")
def image_file(image_id: str) -> FileResponse:
    img = get_store().get_image(image_id)
    if img is None:
        raise HTTPException(404, "Image not found.")
    path = Path(img["path"])
    if not path.is_file():
        raise HTTPException(410, "Image file missing on disk.")
    return FileResponse(path, media_type=f"image/{img['format'].lower()}")
