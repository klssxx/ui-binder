"""Structured log tail per workspace."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.api.common import get_store

router = APIRouter(tags=["logs"])


@router.get("/workspaces/{ws_id}/logs")
def logs(ws_id: str, limit: int = Query(100, ge=1, le=1000),
         level: str | None = None) -> dict:
    store = get_store()
    if not store.workspace_exists(ws_id):
        raise HTTPException(404, f"Workspace '{ws_id}' no existe.")
    entries = store.list_logs(ws_id, limit=limit)
    if level:
        wanted = level.upper()
        entries = [e for e in entries if e["level"] == wanted]
    return {"logs": entries}
