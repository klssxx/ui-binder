"""Vision pipeline tests against the golden reference (synthetic, deterministic)."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from backend.vision.heuristic import LocalHeuristicVisionProvider
from backend.vision.tokens_extract import extract_tokens
from tests.conftest import read_json

EXPECTED = None


def expected(repo_root: Path) -> dict:
    return read_json(repo_root / "samples" / "golden-reference" / "expected_ui_schema.json")


def analyze(golden_png: Path):
    with Image.open(golden_png) as img:
        img.load()
        return LocalHeuristicVisionProvider().analyze(img)


def test_golden_min_counts(golden_png, repo_root):
    _, notes = analyze(golden_png)
    exp = expected(repo_root)
    assert notes["components"] >= exp["components_total_min"]
    for type_, minimum in exp["min_counts"].items():
        assert notes["counts"].get(type_, 0) >= minimum, f"{type_}: {notes['counts'].get(type_, 0)} < {minimum}"


def test_golden_screen_size(golden_png, repo_root):
    doc, _ = analyze(golden_png)
    exp = expected(repo_root)
    assert doc.screen.width == exp["screen"]["width"]
    assert doc.screen.height == exp["screen"]["height"]


def test_golden_must_contain_bboxes(golden_png, repo_root):
    doc, _ = analyze(golden_png)
    exp = expected(repo_root)
    for want in exp["must_contain_bbox"]:
        hit = any(
            c.type == want["type"]
            and abs(c.bbox.x - want["x"]) <= want["tolerance"]
            and abs(c.bbox.y - want["y"]) <= want["tolerance"]
            and abs(c.bbox.width - want["w"]) <= want["tolerance"]
            and abs(c.bbox.height - want["h"]) <= want["tolerance"]
            for c in doc.components
        )
        assert hit, f"no {want['type']} near {want}"


def test_hierarchy_and_confidence(golden_png):
    doc, _ = analyze(golden_png)
    ids = {c.id for c in doc.components}
    for c in doc.components:
        assert c.parent_id is None or c.parent_id == "screen" or c.parent_id in ids
        assert 0.0 <= float(c.metadata["confidence"]) <= 1.0
        assert c.metadata["source"] == "heuristic"


def test_document_validates(golden_png):
    doc, _ = analyze(golden_png)
    assert doc.validate_structure() == []
    assert doc.model_dump()["ui_schema_version"] == 1


def test_tokens_extracted(golden_png):
    with Image.open(golden_png) as img:
        img.load()
        doc, _ = LocalHeuristicVisionProvider().analyze(img)
        tokens = extract_tokens(img, doc)
    assert len(tokens.colors) >= 3
    assert any(c.name == "background" for c in tokens.colors)
    assert len(tokens.fonts) >= 1
    css = tokens.to_css_variables()
    assert any(k.startswith("--color-") for k in css)


def test_manual_provider_empty(sample_app_dir, golden_png):
    from backend.vision.manual import ManualVisionProvider
    with Image.open(golden_png) as img:
        doc, notes = ManualVisionProvider().analyze(img)
    assert doc.components == []
    assert notes["provider"] == "manual"


def test_synthetic_flat_image_produces_screen_only():
    import numpy as np
    img = Image.fromarray(np.zeros((200, 300, 3), dtype=np.uint8))
    doc, notes = LocalHeuristicVisionProvider().analyze(img)
    assert notes["components"] <= 2  # at most a stray container, no hallucinated controls
