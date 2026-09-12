"""Trace mode — event recording API.

Implementation status: PARTIAL. Storage + retrieval are real; automatic browser
instrumentation (Playwright capture) is NOT_IMPLEMENTED in v0.1 (see feature
registry). No secrets are captured by policy: redaction happens in logging.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.api.common import get_store
from backend.logging_setup import log

router = APIRouter(tags=["trace"])


class TraceEvent(BaseModel):
    event: str
    component: Optional[str] = None
    capability: Optional[str] = None
    network: Optional[dict[str, Any]] = None
    result: Optional[str] = None
    error: Optional[str] = None


@router.post("/workspaces/{ws_id}/trace/events", status_code=201)
def add_event(ws_id: str, body: TraceEvent) -> dict[str, Any]:
    store = get_store()
    if not store.workspace_exists(ws_id):
        raise HTTPException(404, f"Workspace '{ws_id}' no existe.")
    store.add_trace_event(ws_id, body.model_dump(exclude_none=True))
    log(ws_id, "DEBUG", "trace event", event=body.event, component=body.component)
    return {"recorded": True}


@router.get("/workspaces/{ws_id}/trace/events")
def list_events(ws_id: str, limit: int = 200) -> dict[str, Any]:
    return {"events": get_store().list_trace_events(ws_id, limit=limit)}
