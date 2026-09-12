"""Capability inventory endpoints."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.api.common import get_store

router = APIRouter(tags=["capabilities"])


class LegacyUpdate(BaseModel):
    legacy: bool


@router.get("/workspaces/{ws_id}/capabilities")
def list_capabilities(ws_id: str, kind: Optional[str] = Query(None)) -> dict[str, Any]:
    store = get_store()
    if not store.workspace_exists(ws_id):
        raise HTTPException(404, f"Workspace '{ws_id}' no existe.")
    caps = store.list_capabilities(ws_id)
    if kind:
        caps = [c for c in caps if c["kind"] == kind]
    return {"capabilities": caps, "total": len(caps)}


@router.patch("/workspaces/{ws_id}/capabilities/{capability_id}")
def mark_legacy(ws_id: str, capability_id: str, body: LegacyUpdate) -> dict[str, Any]:
    store = get_store()
    if not store.set_capability_legacy(ws_id, capability_id, body.legacy):
        raise HTTPException(404, "Capacidad no encontrada en este workspace.")
    caps = {c["capability_id"]: c for c in store.list_capabilities(ws_id)}
    return caps[capability_id]
