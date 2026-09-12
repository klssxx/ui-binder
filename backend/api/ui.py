"""UI AST endpoints: analyze screenshot, get/save document, DESIGN.md."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from PIL import Image
from pydantic import BaseModel

from backend.api.common import get_store
from backend.logging_setup import log
from backend.schema.ui_schema import UIDocument
from backend.vision import get_provider
from backend.vision.tokens_extract import extract_tokens, tokens_to_design_md

router = APIRouter(tags=["ui"])


class AnalyzeRequest(BaseModel):
    image_id: Optional[str] = None
    provider: str = "heuristic"


@router.post("/workspaces/{ws_id}/analyze-ui")
def analyze_ui(ws_id: str, body: AnalyzeRequest) -> dict[str, Any]:
    store = get_store()
    if not store.workspace_exists(ws_id):
        raise HTTPException(404, f"Workspace '{ws_id}' not found.")
    image = store.get_image(body.image_id) if body.image_id else store.get_reference_image(ws_id)
    if image is None:
        raise HTTPException(409, "No reference image. Import a screenshot first (POST /workspaces/{id}/images).")
    path = Path(image["path"])
    if not path.is_file():
        raise HTTPException(410, "Reference image file missing on disk. Re-import it.")

    try:
        provider = get_provider(body.provider)
        with Image.open(path) as img:
            img.load()
            document, notes = provider.analyze(img)
            tokens = extract_tokens(img, document)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:  # vision crashed on a broken image
        log(ws_id, "ERROR", "vision analysis failed", error=str(exc), provider=body.provider)
        raise HTTPException(422, f"Vision analysis failed: {exc}") from exc

    design_md = tokens_to_design_md(tokens, document.metadata)
    wrapper = {"ui": document.model_dump(), "tokens": tokens.model_dump(), "design_md": design_md}
    store.save_ui_document(ws_id, wrapper)
    log(ws_id, "INFO", "analyze-ui completed", provider=body.provider,
        components=notes.get("components"), counts=notes.get("counts"))
    return {"notes": notes, "tokens": tokens.model_dump(),
            "components": len(document.components), "version": store.get_ui_document(ws_id)["version"]}


@router.get("/workspaces/{ws_id}/ui")
def get_ui(ws_id: str) -> dict[str, Any]:
    store = get_store()
    row = store.get_ui_document(ws_id)
    if row is None:
        raise HTTPException(409, "No UI document yet. Run Analyze UI first.")
    return row["json"]


class UIDocumentPut(BaseModel):
    document: UIDocument


@router.put("/workspaces/{ws_id}/ui")
def put_ui(ws_id: str, body: UIDocumentPut) -> dict[str, Any]:
    store = get_store()
    if not store.workspace_exists(ws_id):
        raise HTTPException(404, f"Workspace '{ws_id}' not found.")
    problems = body.document.validate_structure()
    if problems:
        raise HTTPException(422, {"message": "UI document failed structural validation.",
                                  "problems": problems[:20]})
    previous = store.get_ui_document(ws_id)
    wrapper = {"ui": body.document.model_dump()}
    if previous and isinstance(previous["json"], dict):
        wrapper["tokens"] = previous["json"].get("tokens")
        wrapper["design_md"] = previous["json"].get("design_md")
    store.save_ui_document(ws_id, wrapper)
    return {"saved": True, "components": len(body.document.components),
            "version": store.get_ui_document(ws_id)["version"]}


@router.get("/workspaces/{ws_id}/design.md")
def design_md(ws_id: str) -> dict[str, str]:
    row = get_store().get_ui_document(ws_id)
    if row is None or not row["json"].get("design_md"):
        raise HTTPException(409, "No design tokens yet. Run Analyze UI first.")
    return {"markdown": row["json"]["design_md"]}
