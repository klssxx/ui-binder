"""Pixel Match Engine — reference screenshot vs rendered UI.

Metrics:
  - global pixel difference (grayscale, threshold-based)
  - mean SSIM (custom implementation, 11x11 gaussian window)
  - structural/edge SSIM (Canny edge maps) — layout alignment proxy
  - per-region difference over AST component bboxes (worst regions listed)
  - component geometry deltas when a rendered-side AST is provided

Visual Fidelity Score = 100 * (0.5*ssim + 0.3*(1-pixdiff) + 0.2*edge_ssim)

Visual fidelity is NEVER mixed with functional coverage (directive §28).
"""
from __future__ import annotations

from typing import Any

import cv2
import numpy as np
from PIL import Image


def _to_gray(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2GRAY)


def _ssim(a: np.ndarray, b: np.ndarray) -> float:
    """SSIM with gaussian weights; images must share shape and dtype float64."""
    C1, C2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    a = a.astype(np.float64)
    b = b.astype(np.float64)
    kernel = cv2.getGaussianKernel(11, 1.5)
    window = np.outer(kernel, kernel.transpose())

    mu_a = cv2.filter2D(a, -1, window, borderType=cv2.BORDER_REFLECT)
    mu_b = cv2.filter2D(b, -1, window, borderType=cv2.BORDER_REFLECT)
    mu_a2, mu_b2, mu_ab = mu_a * mu_a, mu_b * mu_b, mu_a * mu_b
    sigma_a2 = cv2.filter2D(a * a, -1, window, borderType=cv2.BORDER_REFLECT) - mu_a2
    sigma_b2 = cv2.filter2D(b * b, -1, window, borderType=cv2.BORDER_REFLECT) - mu_b2
    sigma_ab = cv2.filter2D(a * b, -1, window, borderType=cv2.BORDER_REFLECT) - mu_ab

    ssim_map = ((2 * mu_ab + C1) * (2 * sigma_ab + C2)) / \
               ((mu_a2 + mu_b2 + C1) * (sigma_a2 + sigma_b2 + C2))
    return float(ssim_map.mean())


def compare_images(reference: Image.Image, rendered: Image.Image,
                   regions: list[dict[str, Any]] | None = None,
                   rendered_regions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Compare rendered vs reference. ``regions`` are AST bboxes {id,type,bbox:{x,y,width,height}}."""
    ref_gray = _to_gray(reference)
    h, w = ref_gray.shape
    rendered_resized = rendered.convert("RGB").resize((w, h), Image.LANCZOS)
    rend_gray = _to_gray(rendered_resized)

    diff = cv2.absdiff(ref_gray, rend_gray)
    _, binmask = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
    pixel_diff = float((binmask > 0).mean())

    ssim = _ssim(ref_gray, rend_gray)

    ref_edges = cv2.Canny(ref_gray, 50, 150)
    rend_edges = cv2.Canny(rend_gray, 50, 150)
    edge_ssim = _ssim(ref_edges, rend_edges)

    region_results: list[dict[str, Any]] = []
    for r in (regions or [])[:200]:
        b = r.get("bbox", {})
        x, y = int(max(0, b.get("x", 0))), int(max(0, b.get("y", 0)))
        x2 = int(min(w, x + b.get("width", 0)))
        y2 = int(min(h, y + b.get("height", 0)))
        if x2 <= x or y2 <= y:
            continue
        roi_diff = float((binmask[y:y2, x:x2] > 0).mean())
        region_results.append({
            "id": r.get("id"), "type": r.get("type"),
            "bbox": b, "pixel_diff": round(roi_diff, 4),
        })
    region_results.sort(key=lambda rr: -rr["pixel_diff"])

    geometry: dict[str, Any] = {"available": False}
    if rendered_regions:
        matches = _match_regions(regions or [], rendered_regions)
        if matches:
            pos_deltas, dim_deltas = [], []
            for m in matches:
                a, b = m["ref"]["bbox"], m["rendered"]["bbox"]
                pos_deltas.append(abs(a["x"] - b["x"]) + abs(a["y"] - b["y"]))
                dim_deltas.append(abs(a["width"] - b["width"]) + abs(a["height"] - b["height"]))
            geometry = {
                "available": True,
                "matched": len(matches),
                "mean_position_delta_px": round(float(np.mean(pos_deltas)), 1),
                "mean_dimension_delta_px": round(float(np.mean(dim_deltas)), 1),
            }

    fidelity = 100.0 * (0.5 * max(0.0, ssim) + 0.3 * (1.0 - min(1.0, pixel_diff))
                        + 0.2 * max(0.0, edge_ssim))

    return {
        "image_size": [w, h],
        "rendered_resized_to": [w, h],
        "pixel_diff": round(pixel_diff, 4),
        "ssim": round(ssim, 4),
        "edge_ssim": round(edge_ssim, 4),
        "visual_fidelity_score": round(max(0.0, min(100.0, fidelity)), 1),
        "worst_regions": region_results[:10],
        "region_count": len(region_results),
        "geometry": geometry,
        "formula": "100 * (0.5*ssim + 0.3*(1-pixel_diff) + 0.2*edge_ssim)",
    }


def _match_regions(ref: list[dict[str, Any]], rendered: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Greedy nearest-bbox matching by center distance under a tolerance."""
    def center(b: dict[str, float]) -> tuple[float, float]:
        return (b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)

    used: set[int] = set()
    out = []
    for r in ref:
        rc = center(r["bbox"])
        best_i, best_d = -1, 1e12
        for i, cand in enumerate(rendered):
            if i in used or cand.get("type") != r.get("type"):
                continue
            cc = center(cand["bbox"])
            d = (rc[0] - cc[0]) ** 2 + (rc[1] - cc[1]) ** 2
            if d < best_d:
                best_d, best_i = d, i
        if best_i >= 0 and best_d ** 0.5 <= 60:
            used.add(best_i)
            out.append({"ref": r, "rendered": rendered[best_i]})
    return out
