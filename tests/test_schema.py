"""UI AST schema tests: invariants, versioning, structural validation."""
from __future__ import annotations

import pytest

from backend.schema.ui_schema import (
    COMPONENT_TYPES, BBox, Component, UIDocument, empty_document,
)
from backend.schema.capability import confidence_band
from backend.schema.tokens import ColorToken, DesignTokens
from backend.schema.binding import Binding


def make_doc() -> UIDocument:
    doc = empty_document(1280, 800)
    doc.components = [
        Component(id="component_0001", type="panel", name="card", parent_id="screen",
                  children=["component_0002"], bbox=BBox(x=10, y=10, width=500, height=400)),
        Component(id="component_0002", type="button", name="go", parent_id="component_0001",
                  children=[], bbox=BBox(x=30, y=30, width=100, height=40), text="Generar"),
    ]
    return doc


def test_schema_version_is_pinned():
    assert UIDocument.model_validate(make_doc().model_dump()).ui_schema_version == 1


def test_valid_document_passes_structure():
    assert make_doc().validate_structure() == []


def test_unknown_parent_detected():
    doc = make_doc()
    doc.components[1].parent_id = "ghost"
    problems = doc.validate_structure()
    assert any("unknown parent" in p for p in problems)


def test_duplicate_ids_detected():
    doc = make_doc()
    doc.components[1].id = "component_0001"
    assert any("Duplicate" in p for p in doc.validate_structure())


def test_children_reciprocity_enforced():
    doc = make_doc()
    doc.components[0].children = []
    assert any("not listed in parent" in p for p in doc.validate_structure())


def test_component_type_universe():
    assert "custom" in COMPONENT_TYPES
    assert len(COMPONENT_TYPES) == 22  # incl. 'screen'


def test_confidence_bands_never_promote_unknown_to_fact():
    assert confidence_band(0.0) == "UNKNOWN"
    assert confidence_band(0.5) == "MEDIUM CONFIDENCE"
    assert confidence_band(0.99) == "HIGH CONFIDENCE"
    assert confidence_band(0.1, source="manual") == "FACT"


def test_design_tokens_css_variables():
    tokens = DesignTokens(colors=[ColorToken(name="primary", hex="#4f8cff")])
    css = tokens.to_css_variables()
    assert css["--color-primary"] == "#4f8cff"


def test_binding_defaults():
    b = Binding(binding_id="b1", component_id="c1", target_capability="cap1")
    assert b.status == "SUGGESTED"
    assert b.event == "onClick"


def test_bbox_validation_rejects_zero_size():
    with pytest.raises(Exception):
        BBox(x=0, y=0, width=0, height=10)
