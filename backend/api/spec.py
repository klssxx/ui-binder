"""SPEC mode: describe buttons in plain language, get capability matches.

The description text feeds the same deterministic matcher used by the editor
(docs/BINDING_MODEL.md) — no new scoring path, full auditability.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.api.common import get_store
from backend.bindings import suggest_bindings

router = APIRouter(tags=["spec"])


class SpecSuggestRequest(BaseModel):
    name: str
    description: str = ""
    type: str = "button"
    limit: int = 6


@router.post("/workspaces/{ws_id}/spec/suggest")
def spec_suggest(ws_id: str, body: SpecSuggestRequest) -> dict[str, Any]:
    store = get_store()
    if not store.workspace_exists(ws_id):
        raise HTTPException(404, f"Workspace '{ws_id}' no existe.")
    caps = store.list_capabilities(ws_id)
    if not caps:
        raise HTTPException(409, "Aún no hay capacidades: importa y analiza un proyecto primero.")
    synthetic = {
        "id": "spec_item",
        "type": body.type,
        "name": body.name,
        "text": f"{body.name} {body.description}".strip(),
        "bbox": {"x": 0, "y": 0, "width": 10, "height": 10},
    }
    suggestions = suggest_bindings(synthetic, caps, limit=body.limit)
    return {
        "item": {"name": body.name, "description": body.description, "type": body.type},
        "suggestions": [s.model_dump() for s in suggestions],
    }
