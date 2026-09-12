"""Smart Binder endpoints: suggestions, binding CRUD, verification of targets."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.api.common import get_store
from backend.bindings import suggest_bindings, verify_bindings
from backend.logging_setup import log
from backend.persistence.store import CorruptDocumentError
from backend.schema.binding import Mapping

router = APIRouter(tags=["bindings"])


class SuggestRequest(BaseModel):
    component_id: str
    limit: int = 5


class BindingCreate(BaseModel):
    component_id: str
    event: str = "onClick"
    target_capability: str
    input_mapping: list[Mapping] = []
    output_mapping: list[Mapping] = []
    loading_mapping: str = ""
    error_mapping: str = ""
    transformations: list[str] = []
    confidence: float = 0.0
    status: str = "SUGGESTED"
    rationale: list[str] = []


class BindingUpdate(BaseModel):
    event: Optional[str] = None
    target_capability: Optional[str] = None
    input_mapping: Optional[list[Mapping]] = None
    output_mapping: Optional[list[Mapping]] = None
    loading_mapping: Optional[str] = None
    error_mapping: Optional[str] = None
    confidence: Optional[float] = None
    status: Optional[str] = None
    rationale: Optional[list[str]] = None


def _current_document(store, ws_id: str) -> dict:
    try:
        row = store.get_ui_document(ws_id)
    except CorruptDocumentError as exc:
        raise HTTPException(422, {
            "message": "El documento UI persistido está corrupto; no se pueden validar bindings.",
            "cause": str(exc),
            "action": "Restaura un snapshot o guarda un documento válido (PUT /ui).",
        }) from exc
    if row is None:
        raise HTTPException(409, "No UI document. Run Analyze UI first.")
    return row["json"].get("ui") or {}


@router.post("/workspaces/{ws_id}/suggest-bindings")
def suggest(ws_id: str, body: SuggestRequest) -> dict[str, Any]:
    store = get_store()
    if not store.workspace_exists(ws_id):
        raise HTTPException(404, f"Workspace '{ws_id}' not found.")
    ui = _current_document(store, ws_id)
    component = next((c for c in ui.get("components", []) if c["id"] == body.component_id), None)
    if component is None:
        raise HTTPException(404, f"Component '{body.component_id}' not in current AST.")
    caps = store.list_capabilities(ws_id)
    if not caps:
        raise HTTPException(409, "No capabilities. Import and analyze a project first.")
    suggestions = suggest_bindings(component, caps, limit=body.limit)
    log(ws_id, "DEBUG", "suggestions computed", component=body.component_id,
        count=len(suggestions))
    return {"component_id": body.component_id,
            "suggestions": [s.model_dump() for s in suggestions]}


@router.get("/workspaces/{ws_id}/bindings")
def list_bindings(ws_id: str) -> dict[str, Any]:
    store = get_store()
    caps = {c["capability_id"]: c for c in store.list_capabilities(ws_id)}
    bindings = store.list_bindings(ws_id)
    for b in bindings:
        cap = caps.get(b["target_capability"])
        b["target_name"] = cap["name"] if cap else None
        b["target_broken"] = cap is None
    return {"bindings": bindings, "total": len(bindings)}


@router.post("/workspaces/{ws_id}/bindings", status_code=201)
def create_binding(ws_id: str, body: BindingCreate) -> dict[str, Any]:
    store = get_store()
    if not store.workspace_exists(ws_id):
        raise HTTPException(404, f"Workspace '{ws_id}' not found.")
    caps = {c["capability_id"] for c in store.list_capabilities(ws_id)}
    if body.target_capability not in caps:
        raise HTTPException(422, f"Unknown target capability '{body.target_capability}'.")
    ui = _current_document(store, ws_id)
    comp_ids = {c["id"] for c in ui.get("components", [])}
    if body.component_id not in comp_ids:
        raise HTTPException(422, f"Component '{body.component_id}' not in current AST.")
    if body.status not in ("SUGGESTED", "CONFIRMED", "BROKEN", "UNKNOWN"):
        raise HTTPException(422, f"Invalid status '{body.status}'.")
    # prevent silent duplicates of the exact same edge
    for existing in store.list_bindings(ws_id):
        if (existing["component_id"] == body.component_id
                and existing["event"] == body.event
                and existing["target_capability"] == body.target_capability):
            raise HTTPException(409, {
                "message": "An identical binding already exists.",
                "binding_id": existing["binding_id"]})
    binding = store.create_binding(ws_id, body.model_dump())
    # keep AST events in sync
    _sync_ast_events(store, ws_id)
    log(ws_id, "INFO", "binding created", binding_id=binding["binding_id"],
        component=body.component_id, target=body.target_capability, status=binding["status"])
    return binding


@router.patch("/workspaces/{ws_id}/bindings/{binding_id}")
def update_binding(ws_id: str, binding_id: str, body: BindingUpdate) -> dict[str, Any]:
    store = get_store()
    changes = body.model_dump(exclude_none=True)
    if "status" in changes and changes["status"] not in ("SUGGESTED", "CONFIRMED", "BROKEN", "UNKNOWN"):
        raise HTTPException(422, f"Invalid status '{changes['status']}'.")
    updated = store.update_binding(ws_id, binding_id, changes)
    if updated is None:
        raise HTTPException(404, "Binding not found in this workspace.")
    _sync_ast_events(store, ws_id)
    return updated


@router.delete("/workspaces/{ws_id}/bindings/{binding_id}", status_code=204)
def delete_binding(ws_id: str, binding_id: str) -> None:
    store = get_store()
    if not store.delete_binding(ws_id, binding_id):
        raise HTTPException(404, "Binding not found in this workspace.")
    _sync_ast_events(store, ws_id)


@router.post("/workspaces/{ws_id}/bindings/verify")
def verify_all(ws_id: str) -> dict[str, Any]:
    store = get_store()
    bindings = store.list_bindings(ws_id)
    caps = store.list_capabilities(ws_id)
    ui = store.get_ui_document(ws_id)
    components = (ui["json"].get("ui") or {}).get("components", []) if ui else []
    results = verify_bindings(bindings, caps, components)
    patched = 0
    for r in results:
        if r["status"] and r["status"] != "BROKEN":
            continue
        store.update_binding(ws_id, r["binding_id"], {"status": r["status"] or "UNKNOWN"})
        patched += 1
    _sync_ast_events(store, ws_id)
    return {"results": results, "patched": patched}


def _sync_ast_events(store, ws_id: str) -> None:
    """Mirror CONFIRMED bindings into component.events so the editor sees them."""
    try:
        row = store.get_ui_document(ws_id)
    except CorruptDocumentError as exc:
        log(ws_id, "WARNING", "binding sync skipped: corrupt UI document", cause=str(exc))
        return
    if row is None:
        return
    wrapper = row["json"]
    ui = wrapper.get("ui") or {}
    bindings = store.list_bindings(ws_id)
    confirmed: dict[str, list[str]] = {}
    for b in bindings:
        if b["status"] == "CONFIRMED":
            confirmed.setdefault(b["component_id"], []).append(b["binding_id"])
    changed = False
    for comp in ui.get("components", []):
        want = confirmed.get(comp["id"], [])
        events = {k: v for k, v in (comp.get("events") or {}).items()}
        if want:
            new_events = {**events, "onClick": want[0]}
        else:
            new_events = {k: v for k, v in events.items() if k != "onClick"}
        if new_events != events:
            comp["events"] = new_events
            changed = True
        comp["bindings"] = [b["binding_id"] for b in bindings if b["component_id"] == comp["id"]]
        changed = True
    if changed:
        store.save_ui_document(ws_id, wrapper)
