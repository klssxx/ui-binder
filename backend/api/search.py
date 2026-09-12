"""Global search across components, capabilities, bindings, files and routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from backend.api.common import get_store

router = APIRouter(tags=["search"])


@router.get("/workspaces/{ws_id}/search")
def search(ws_id: str, q: str = Query(..., min_length=1)) -> dict[str, Any]:
    store = get_store()
    if not store.workspace_exists(ws_id):
        raise HTTPException(404, f"Workspace '{ws_id}' not found.")
    needle = q.strip().lower()

    components = []
    row = store.get_ui_document(ws_id)
    if row:
        for c in (row["json"].get("ui") or {}).get("components", []):
            hay = f"{c.get('name','')} {c.get('text') or ''} {c['type']}".lower()
            if needle in hay:
                components.append({"id": c["id"], "type": c["type"], "name": c.get("name"),
                                   "text": c.get("text")})

    caps, routes = [], []
    for c in store.list_capabilities(ws_id):
        hay = f"{c['name']} {c['qualified_name']} {c.get('description','')}".lower()
        if needle in hay:
            entry = {"capability_id": c["capability_id"], "kind": c["kind"],
                     "name": c["name"], "qualified_name": c["qualified_name"]}
            (routes if c["kind"] == "route" else caps).append(entry)

    bindings = []
    for b in store.list_bindings(ws_id):
        hay = f"{b['component_id']} {b['target_capability']} {b['event']} {b['status']}".lower()
        if needle in hay:
            bindings.append({"binding_id": b["binding_id"], "component_id": b["component_id"],
                             "target_capability": b["target_capability"], "status": b["status"]})

    files = []
    project = store.get_project(ws_id)
    if project:
        for f in store.list_project_files(project["id"]):
            if needle in f["rel_path"].lower():
                files.append({"rel_path": f["rel_path"], "language": f["language"]})

    return {"query": q, "components": components, "capabilities": caps,
            "routes": routes, "bindings": bindings, "files": files}
