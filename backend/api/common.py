"""Shared API dependencies and small helpers."""
from __future__ import annotations

from fastapi import HTTPException, Request

from backend.persistence.store import WorkspaceStore

_store: WorkspaceStore | None = None


def get_store() -> WorkspaceStore:
    global _store
    if _store is None:
        _store = WorkspaceStore()
    return _store


def require_workspace(request: Request, ws_id: str) -> dict:
    store = get_store()
    ws = store.get_workspace(ws_id)
    if ws is None:
        raise HTTPException(status_code=404, detail=f"Workspace '{ws_id}' not found.")
    return ws


def get_document(store: WorkspaceStore, ws_id: str) -> dict:
    """Current persisted wrapper {ui, tokens, design_md} — empty if never analyzed."""
    row = store.get_ui_document(ws_id)
    if row is None:
        raise HTTPException(
            status_code=409,
            detail="No UI document yet. Import a screenshot and run Analyze UI first.",
        )
    return row["json"]


def save_document(store: WorkspaceStore, ws_id: str, wrapper: dict) -> None:
    store.save_ui_document(ws_id, wrapper)
