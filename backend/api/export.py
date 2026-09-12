"""Export endpoints: dry-run CHANGE PLAN + safe apply to a new directory."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.api.common import get_store
from backend.export import build_export_plan, export_react_project
from backend.logging_setup import log
from backend.persistence.store import CorruptDocumentError
from backend.schema.ui_schema import UIDocument

router = APIRouter(tags=["export"])


class ExportRequest(BaseModel):
    target_dir: str


def _load_document(store, ws_id: str) -> UIDocument:
    try:
        row = store.get_ui_document(ws_id)
    except CorruptDocumentError as exc:
        raise HTTPException(422, {
            "message": "El documento UI persistido está corrupto; no se puede exportar.",
            "cause": str(exc),
            "action": "Restaura un snapshot o vuelve a ejecutar Analyze UI.",
        }) from exc
    if row is None:
        raise HTTPException(409, "Aún no hay documento UI: ejecuta antes ANALYZE UI.")
    try:
        return UIDocument.model_validate(row["json"]["ui"])
    except Exception as exc:
        raise HTTPException(422, f"El documento UI persistido no es válido: {exc}") from exc


@router.get("/workspaces/{ws_id}/export-plan")
def export_plan(ws_id: str) -> dict[str, Any]:
    store = get_store()
    document = _load_document(store, ws_id)
    return build_export_plan(document, store.list_bindings(ws_id))


@router.post("/workspaces/{ws_id}/export")
def do_export(ws_id: str, body: ExportRequest) -> dict[str, Any]:
    store = get_store()
    document = _load_document(store, ws_id)
    project = store.get_project(ws_id)
    source = Path(project["path"]) if project else None
    try:
        row = store.get_ui_document(ws_id)
        tokens = row["json"].get("tokens") if row else None
    except CorruptDocumentError:  # unreachable if _load_document passed, kept defensive
        tokens = None
    try:
        plan = export_react_project(document, store.list_bindings(ws_id),
                                    store.list_capabilities(ws_id), tokens,
                                    Path(body.target_dir.strip().strip('"')), source)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    log(ws_id, "INFO", "project exported", target=body.target_dir,
        bindings=plan["bindings_embedded"])
    return plan
