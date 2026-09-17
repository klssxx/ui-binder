"""Multi-target export API.

Extends the existing export endpoints with target selection:
  POST /api/workspaces/{ws_id}/export {"target_dir": "...", "target": "pyside6-widgets"}
  GET  /api/workspaces/{ws_id}/export-plan?target=pyside6-widgets
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.api.common import get_store
from backend.export import available_exporters, get_exporter
from backend.export.base import Exporter
from backend.logging_setup import log
from backend.persistence.store import CorruptDocumentError
from backend.schema.ui_schema import UIDocument

router = APIRouter(tags=["export"])


class ExportRequest(BaseModel):
    target_dir: str
    target: str = Field(default="react-vite-ts", description="Export target ID")


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


def _get_exporter(target: str) -> type[Exporter]:
    try:
        return get_exporter(target)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/export-targets")
def list_targets() -> dict[str, Any]:
    """List available export targets."""
    return {
        "targets": [
            {"target_id": e.target_id, "label": e.label}
            for e in available_exporters()
        ]
    }


@router.get("/workspaces/{ws_id}/export-plan")
def export_plan(ws_id: str, target: str = "react-vite-ts") -> dict[str, Any]:
    """Dry-run: what would be generated without writing."""
    store = get_store()
    document = _load_document(store, ws_id)
    exporter_cls = _get_exporter(target)
    exporter = exporter_cls()
    plan = exporter.plan(document, store.list_bindings(ws_id),
                         store.list_capabilities(ws_id), None)
    warnings = exporter.validate(document, store.list_bindings(ws_id),
                                 store.list_capabilities(ws_id), None)
    d = plan.to_dict()
    d["warnings"] = warnings
    return d


@router.post("/workspaces/{ws_id}/export")
def do_export(ws_id: str, body: ExportRequest) -> dict[str, Any]:
    """Generate export to target directory."""
    store = get_store()
    document = _load_document(store, ws_id)
    exporter_cls = _get_exporter(body.target)
    exporter = exporter_cls()

    project = store.get_project(ws_id)
    source = Path(project["path"]) if project else None

    try:
        row = store.get_ui_document(ws_id)
        tokens = row["json"].get("tokens") if row else None
    except CorruptDocumentError:
        tokens = None

    def _resolver(image_id: str):
        record = store.get_image(image_id)
        if record is None:
            return None
        p = Path(record["path"])
        return str(p) if p.is_file() else None

    try:
        plan = exporter.export(
            document, store.list_bindings(ws_id),
            store.list_capabilities(ws_id), tokens,
            Path(body.target_dir.strip().strip('"')), source,
            image_resolver=_resolver)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    log(ws_id, "INFO", "project exported", target=body.target)
    return plan
