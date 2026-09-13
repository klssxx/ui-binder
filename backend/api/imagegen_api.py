"""F6 endpoints: estado de IA, generación de héroes y herramientas locales de fondo."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend import config
from backend.api.common import get_store
from backend.logging_setup import log
from backend.vision import imagegen

router = APIRouter(tags=["imagegen"])


def _save_variant(ws_id: str, data: bytes, role: str, name: str, w: int, h: int) -> dict[str, Any]:
    store = get_store()
    ws_dir = config.workspaces_root() / ws_id / "images"
    ws_dir.mkdir(parents=True, exist_ok=True)
    dest = ws_dir / f"{role}_{hashlib.sha256(data).hexdigest()[:16]}.png"
    dest.write_bytes(data)
    return store.add_image(ws_id, role=role, filename=name, path=str(dest),
                           width=w, height=h, size_bytes=len(data), fmt="PNG",
                           sha256=hashlib.sha256(data).hexdigest())


@router.get("/imagegen/status")
def imagegen_status() -> dict[str, Any]:
    return imagegen.status()


class HeroRequest(BaseModel):
    prompt: str
    width: int = 1024
    height: int = 576


@router.post("/workspaces/{ws_id}/imagegen/hero")
def generate_hero(ws_id: str, body: HeroRequest) -> dict[str, Any]:
    if not get_store().workspace_exists(ws_id):
        raise HTTPException(404, f"Workspace '{ws_id}' no existe.")
    if not body.prompt.strip():
        raise HTTPException(422, "Describe qué quieres generar (prompt vacío).")
    if not imagegen.status()["configured"]:
        raise HTTPException(409, "La generación con IA no está configurada. Define "
                                 "UIBINDER_IMAGEGEN_BASE_URL, UIBINDER_IMAGEGEN_MODEL y "
                                 "UIBINDER_IMAGEGEN_API_KEY (ver .env.example), o usa las "
                                 "herramientas de fondo locales.")
    try:
        png = imagegen.generate_hero(body.prompt.strip(), body.width, body.height)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        log(ws_id, "ERROR", "imagegen failed", error=str(exc))
        raise HTTPException(502, f"El proveedor de imágenes falló: {exc}") from exc
    from PIL import Image
    import io as _io

    with Image.open(_io.BytesIO(png)) as im:
        w, h = im.size
    record = _save_variant(ws_id, png, "hero", "hero_ia.png", w, h)
    log(ws_id, "INFO", "hero generado con IA (prompt enviado al proveedor externo)")
    return {"image": record, "privacy": "el prompt se envió al proveedor externo configurado"}


class BackgroundRequest(BaseModel):
    op: Literal["blur", "darken", "lighten", "color", "gradient"]
    params: dict[str, Any] = {}
    image_id: Optional[str] = None


@router.post("/workspaces/{ws_id}/background")
def background_op(ws_id: str, body: BackgroundRequest) -> dict[str, Any]:
    store = get_store()
    if not store.workspace_exists(ws_id):
        raise HTTPException(404, f"Workspace '{ws_id}' no existe.")
    source = store.get_image(body.image_id) if body.image_id else store.get_reference_image(ws_id)
    if source is None:
        raise HTTPException(409, "No hay imagen de referencia sobre la que aplicar el fondo.")
    path = Path(source["path"])
    if not path.is_file():
        raise HTTPException(410, "La imagen no está en disco; vuelve a importarla.")
    try:
        data = imagegen.apply_background_op(path.read_bytes(), body.op, body.params)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        log(ws_id, "ERROR", "background op failed", error=str(exc), op=body.op)
        raise HTTPException(422, f"La operación de fondo falló: {exc}") from exc
    from PIL import Image
    import io as _io

    with Image.open(_io.BytesIO(data)) as im:
        w, h = im.size
    record = _save_variant(ws_id, data, "variant", f"{body.op}_{source['filename']}", w, h)
    log(ws_id, "INFO", "fondo alterado (local, sin nube)", op=body.op)
    return {"image": record, "op": body.op}
