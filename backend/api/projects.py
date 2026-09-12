"""Project import (READ-ONLY) + analysis into the capability graph."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from adapters import adapters_for
from backend.analyzer.capability_builder import build_capabilities
from backend.analyzer.project_scanner import scan_project
from backend.api.common import get_store
from backend.logging_setup import log
from backend.security.paths import is_safe_project_path

router = APIRouter(tags=["projects"])


class ImportRequest(BaseModel):
    path: str


class AnalyzeProjectResponse(BaseModel):
    capabilities: int
    edges: int
    graph: dict[str, Any]


@router.post("/workspaces/{ws_id}/import-project")
def import_project(ws_id: str, body: ImportRequest) -> dict[str, Any]:
    store = get_store()
    if not store.workspace_exists(ws_id):
        raise HTTPException(404, f"Workspace '{ws_id}' no existe.")
    ok, why = is_safe_project_path(body.path)
    if not ok:
        raise HTTPException(422, why)
    root = Path(body.path.strip().strip('"'))
    try:
        scan = scan_project(root)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    detected = adapters_for(root)
    adapter_summaries = []
    for adapter in detected:
        try:
            adapter_summaries.append({"name": adapter.name, "inspect": adapter.inspect(root)})
        except Exception as exc:
            adapter_summaries.append({"name": adapter.name, "error": str(exc)})

    project = store.upsert_project(
        ws_id, str(scan["root"]), frameworks=scan["frameworks"],
        languages=scan["languages"], entrypoints=scan["entrypoints"],
        manifests=scan["manifests"],
        summary={"file_count": scan["file_count"], "adapters": [a.name for a in detected]},
    )
    store.set_project_files(project["id"], scan["source_files"])
    log(ws_id, "INFO", "project imported (READ-ONLY)", path=str(scan["root"]),
        files=scan["file_count"], frameworks=scan["frameworks"])
    return {
        "project": project,
        "frameworks": scan["frameworks"],
        "languages": scan["languages"],
        "entrypoints": scan["entrypoints"],
        "manifests": scan["manifests"],
        "file_count": scan["file_count"],
        "adapters": adapter_summaries,
        "read_only": True,
    }


@router.get("/workspaces/{ws_id}/project")
def get_project(ws_id: str) -> dict[str, Any]:
    store = get_store()
    project = store.get_project(ws_id)
    if project is None:
        raise HTTPException(409, "No project imported yet.")
    project["files"] = store.list_project_files(project["id"])[:500]
    return project


@router.post("/workspaces/{ws_id}/analyze-project")
def analyze_project(ws_id: str) -> AnalyzeProjectResponse:
    store = get_store()
    project = store.get_project(ws_id)
    if project is None:
        raise HTTPException(409, "Aún no hay proyecto importado: importa uno primero.")
    root = Path(project["path"])
    if not root.is_dir():
        raise HTTPException(410, f"La ruta del proyecto importado ya no existe: {root}")

    scan = {"root": str(root),
            "source_files": [{"rel_path": f["rel_path"], "language": f["language"]}
                             for f in store.list_project_files(project["id"])]}
    graph = build_capabilities(scan)

    caps = [cap.model_dump() for cap in graph.nodes]
    store.replace_capabilities(ws_id, caps)
    log(ws_id, "INFO", "project analyzed", capabilities=len(caps), edges=len(graph.edges))
    return AnalyzeProjectResponse(
        capabilities=len(caps), edges=len(graph.edges),
        graph={"nodes": caps, "edges": [e.model_dump() for e in graph.edges]},
    )
