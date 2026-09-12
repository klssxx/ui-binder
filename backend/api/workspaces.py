"""Workspace CRUD + snapshots."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.api.common import get_store
from backend.logging_setup import log
from backend.persistence.store import CorruptDocumentError

router = APIRouter(tags=["workspaces"])


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    notes: str = ""


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    notes: Optional[str] = None


class SnapshotCreate(BaseModel):
    label: str = "manual snapshot"


@router.post("/workspaces", status_code=201)
def create_workspace(body: WorkspaceCreate) -> dict[str, Any]:
    store = get_store()
    ws = store.create_workspace(body.name, body.notes)
    log(ws["id"], "INFO", "workspace created", name=ws["name"])
    return ws


@router.get("/workspaces")
def list_workspaces() -> dict[str, Any]:
    return {"workspaces": get_store().list_workspaces()}


@router.get("/workspaces/{ws_id}")
def get_workspace(ws_id: str) -> dict[str, Any]:
    ws = get_store().get_workspace(ws_id)
    if ws is None:
        raise HTTPException(404, f"Workspace '{ws_id}' no existe.")
    ui = get_store().get_ui_document(ws_id)
    return {**ws, "has_ui_document": ui is not None, "ui_version": ui["version"] if ui else 0}


@router.patch("/workspaces/{ws_id}")
def update_workspace(ws_id: str, body: WorkspaceUpdate) -> dict[str, Any]:
    if body.name is None and body.notes is None:
        raise HTTPException(422, "Nada que actualizar.")
    current = get_store().get_workspace(ws_id)
    if current is None:
        raise HTTPException(404, f"Workspace '{ws_id}' no existe.")
    ws = get_store().rename_workspace(ws_id, body.name or current["name"], body.notes)
    return ws


@router.delete("/workspaces/{ws_id}", status_code=204)
def delete_workspace(ws_id: str) -> None:
    if not get_store().delete_workspace(ws_id):
        raise HTTPException(404, f"Workspace '{ws_id}' no existe.")


@router.post("/workspaces/{ws_id}/snapshots", status_code=201)
def create_snapshot(ws_id: str, body: SnapshotCreate) -> dict[str, Any]:
    if not get_store().workspace_exists(ws_id):
        raise HTTPException(404, f"Workspace '{ws_id}' no existe.")
    try:
        snap = get_store().create_snapshot(ws_id, body.label)
    except CorruptDocumentError as exc:
        raise HTTPException(422, {
            "message": "No se puede snapshotear un documento corrupto.",
            "cause": str(exc),
            "action": "Restaura un snapshot previo o guarda un documento válido primero.",
        }) from exc
    log(ws_id, "INFO", "snapshot created", label=snap["label"])
    return {k: v for k, v in snap.items() if k != "json"}


@router.get("/workspaces/{ws_id}/snapshots")
def list_snapshots(ws_id: str) -> dict[str, Any]:
    return {"snapshots": get_store().list_snapshots(ws_id)}


@router.post("/workspaces/{ws_id}/snapshots/{snapshot_id}/restore")
def restore_snapshot(ws_id: str, snapshot_id: str) -> dict[str, Any]:
    try:
        result = get_store().restore_snapshot(ws_id, snapshot_id)
    except CorruptDocumentError as exc:
        raise HTTPException(422, {"message": "El snapshot está corrupto.", "cause": str(exc)}) from exc
    if result is None:
        raise HTTPException(404, "Snapshot no encontrado en este workspace.")
    log(ws_id, "INFO", "snapshot restored", snapshot=snapshot_id)
    return {"restored": True, "version": result["version"], "updated_at": result["updated_at"]}
