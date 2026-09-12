"""Verification: orphan detector, functional coverage, visual diff + fidelity."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from backend.api.common import get_store
from backend.bindings import verify_bindings
from backend.diff.visual import compare_images
from backend.logging_setup import log
from backend.persistence.store import CorruptDocumentError
from backend.verification import functional_coverage, orphan_report
from backend.vision.heuristic import LocalHeuristicVisionProvider

router = APIRouter(tags=["verification"])


def _document_or_none(store, ws_id: str):
    try:
        return store.get_ui_document(ws_id)
    except CorruptDocumentError as exc:
        raise HTTPException(422, {
            "message": "El documento UI persistido está corrupto; verificación incompleta.",
            "cause": str(exc),
            "action": "Restaura un snapshot o guarda un documento válido (PUT /ui).",
        }) from exc


@router.post("/workspaces/{ws_id}/verify")
def verify(ws_id: str) -> dict[str, Any]:
    store = get_store()
    if not store.workspace_exists(ws_id):
        raise HTTPException(404, f"Workspace '{ws_id}' no existe.")
    caps = store.list_capabilities(ws_id)
    bindings = store.list_bindings(ws_id)
    row = _document_or_none(store, ws_id)
    components = (row["json"].get("ui") or {}).get("components", []) if row else []

    binding_results = verify_bindings(bindings, caps, components)
    for r in binding_results:
        if r["status"] == "BROKEN":
            store.update_binding(ws_id, r["binding_id"], {"status": "BROKEN"})
    bindings = store.list_bindings(ws_id)

    orphan = orphan_report(caps, bindings)
    coverage = functional_coverage(caps, bindings)
    diffs = store.list_visual_diffs(ws_id)
    visual_fidelity = diffs[0]["fidelity"] if diffs else None

    report = {
        "visual_fidelity": visual_fidelity,
        "functional_coverage": coverage,
        "broken_bindings": orphan["broken"],
        "unbound_capabilities": orphan["unbound"],
        "orphan": orphan,
        "binding_checks": binding_results,
        "scores": {
            "visual_fidelity": visual_fidelity,
            "functional_coverage": coverage,
            "note": "Visual fidelity and functional coverage are independent; "
                    "a visually perfect UI with lost functionality is a FAILURE.",
        },
    }
    store.save_verification_run(ws_id, report)
    log(ws_id, "INFO", "verification run", coverage=coverage, broken=orphan["broken"],
        visual=visual_fidelity)
    return report


@router.post("/workspaces/{ws_id}/visual-diff")
async def visual_diff(ws_id: str, rendered: UploadFile = File(...),
                      reference_id: Optional[str] = None) -> dict[str, Any]:
    store = get_store()
    if not store.workspace_exists(ws_id):
        raise HTTPException(404, f"Workspace '{ws_id}' no existe.")
    ref = store.get_image(reference_id) if reference_id else store.get_reference_image(ws_id)
    if ref is None:
        raise HTTPException(409, "Este workspace no tiene imagen de referencia.")

    data = await rendered.read()
    try:
        rendered_img = Image.open(io.BytesIO(data))
        rendered_img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(422, f"Imagen renderizada inválida: {exc}") from exc
    ref_path = Path(ref["path"])
    if not ref_path.is_file():
        raise HTTPException(410, "La imagen de referencia no está en disco; vuelve a importarla.")
    with Image.open(ref_path) as rimg:
        rimg.load()

        row = _document_or_none(store, ws_id)
        regions = []
        if row:
            for c in (row["json"].get("ui") or {}).get("components", []):
                regions.append({"id": c["id"], "type": c["type"], "bbox": c["bbox"]})
        # geometry deltas: heuristic detection on the rendered image
        rendered_regions = []
        try:
            heuristic_doc, _ = LocalHeuristicVisionProvider().analyze(rendered_img)
            rendered_regions = [{"id": c.id, "type": c.type, "bbox": c.model_dump()["bbox"]}
                                for c in heuristic_doc.components]
        except Exception:
            pass
        metrics = compare_images(rimg, rendered_img, regions=regions,
                                 rendered_regions=rendered_regions)

    record = store.save_visual_diff(ws_id, ref["id"], rendered.filename or "rendered.png",
                                    metrics, metrics["visual_fidelity_score"])
    log(ws_id, "INFO", "visual diff computed", fidelity=metrics["visual_fidelity_score"])
    return {"diff_id": record["id"], "metrics": metrics}


@router.get("/workspaces/{ws_id}/diffs")
def list_diffs(ws_id: str) -> dict[str, Any]:
    return {"diffs": get_store().list_visual_diffs(ws_id)}
