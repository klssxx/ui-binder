"""Visual diff tests: synthetic images with known differences."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from backend.diff.visual import compare_images


def base_image() -> Image.Image:
    img = Image.new("RGB", (400, 300), "#101216")
    d = ImageDraw.Draw(img)
    d.rectangle([10, 10, 110, 50], fill="#4f8cff")
    d.rectangle([10, 70, 210, 100], outline="#888888", width=2)
    return img


def test_identical_images_near_perfect():
    a = base_image()
    m = compare_images(a, a.copy())
    assert m["pixel_diff"] == 0.0
    assert m["ssim"] > 0.999
    assert m["visual_fidelity_score"] > 99.0


def test_modified_image_lowers_fidelity():
    a = base_image()
    b = base_image()
    d = ImageDraw.Draw(b)
    d.rectangle([200, 200, 380, 280], fill="#ff0000")
    m = compare_images(a, b)
    assert m["pixel_diff"] > 0.02
    assert m["ssim"] < 0.99
    assert m["visual_fidelity_score"] < 99.0


def test_resizes_rendered_to_reference():
    a = base_image()
    b = base_image().resize((800, 600))
    m = compare_images(a, b)
    assert m["image_size"] == [400, 300]
    assert m["visual_fidelity_score"] > 95.0


def test_region_report_uses_ast_boxes():
    a = base_image()
    b = base_image()
    ImageDraw.Draw(b).rectangle([20, 20, 100, 45], fill="#ffffff")  # inside the button
    regions = [{"id": "comp_button", "type": "button",
                "bbox": {"x": 10, "y": 10, "width": 100, "height": 40}},
               {"id": "comp_input", "type": "input",
                "bbox": {"x": 10, "y": 70, "width": 200, "height": 30}}]
    m = compare_images(a, b, regions=regions)
    worst = {r["id"]: r["pixel_diff"] for r in m["worst_regions"]}
    assert worst.get("comp_button", 0) > worst.get("comp_input", 0)


def test_geometry_deltas_with_rendered_regions():
    a = base_image()
    b = base_image()
    ref_regions = [{"id": "c1", "type": "button",
                    "bbox": {"x": 10, "y": 10, "width": 100, "height": 40}}]
    rendered_regions = [{"id": "r1", "type": "button",
                         "bbox": {"x": 22, "y": 14, "width": 100, "height": 40}}]
    m = compare_images(a, b, regions=ref_regions, rendered_regions=rendered_regions)
    assert m["geometry"]["available"] is True
    assert m["geometry"]["matched"] == 1
    assert m["geometry"]["mean_position_delta_px"] > 0


def test_ssim_extremes():
    black = Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8))
    white = Image.fromarray(np.full((100, 100, 3), 255, dtype=np.uint8))
    m = compare_images(black, white)
    assert m["ssim"] < 0.1
    assert m["visual_fidelity_score"] < 30.0
