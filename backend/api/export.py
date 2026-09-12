"""Export endpoints: dry-run CHANGE PLAN + safe apply to a new directory."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.api.common import get_store
from backend.export import build_export_plan, export_react_project
from backend.logging_setup import log
from backend.schema.ui_schema import UIDocument

router = APIRouter(tags=["export"])


class ExportRequest(BaseModel):
    target_dir: str


def _load_document(store, ws_id: str) -> UIDocument:
    row = store.get_ui_document(ws_id)
    if row is None:
        raise HTTPException(409, "No UI document. Run Analyze UI first.")
    try:
        return UIDocument.model_validate(row["json"]["ui"])
    except Exception as exc:
        raise HTTPException(500, f"Persisted UI document is invalid: {exc}") from exc


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
    tokens = None
    row = store.get_ui_document(ws_id)
    if row:
        tokens = row["json"].get("tokens")
    try:
        plan = export_react_project(document, store.list_bindings(ws_id),
                                    store.list_capabilities(ws_id), tokens,
                                    Path(body.target_dir.strip().strip('"')), source)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    log(ws_id, "INFO", "project exported", target=body.target_dir,
        bindings=plan["bindings_embedded"])
    return plan
