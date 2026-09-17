"""Tests for multi-target export system: registry, React backward compat, PySide6, determinism, immutability."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from backend.export import available_exporters, get_exporter
from backend.export.base import Exporter, ExportPlan
from backend.export.pyside6_export import PySide6WidgetsExporter
from backend.export.react_export import ReactViteTSExporter, build_export_plan, export_react_project
from backend.schema.ui_schema import UIDocument


# Fixtures
@pytest.fixture
def sample_document():
    return UIDocument.model_validate({
        "ui_schema_version": 1,
        "screen": {"id": "screen", "width": 800, "height": 600, "background": "#101216"},
        "components": [
            {"id": "component_0001", "type": "panel", "name": "card", "parent_id": "screen",
             "children": ["component_0002", "component_0003", "component_0004"],
             "bbox": {"x": 40, "y": 40, "width": 400, "height": 300},
             "text": None, "styles": {}, "states": {}, "events": {}, "bindings": [], "metadata": {}},
            {"id": "component_0002", "type": "heading", "name": "h", "parent_id": "component_0001",
             "children": [], "bbox": {"x": 60, "y": 60, "width": 200, "height": 30},
             "text": "Idea Generator", "styles": {"color": "#ffffff"},
             "states": {}, "events": {}, "bindings": [], "metadata": {}},
            {"id": "component_0003", "type": "input", "name": "prompt", "parent_id": "component_0001",
             "children": [], "bbox": {"x": 60, "y": 110, "width": 300, "height": 36},
             "text": None, "styles": {}, "states": {}, "events": {}, "bindings": [], "metadata": {}},
            {"id": "component_0004", "type": "button", "name": "generate-button",
             "parent_id": "component_0001", "children": [],
             "bbox": {"x": 60, "y": 160, "width": 120, "height": 40},
             "text": "Generar", "styles": {"background": "#4f8cff"}, "states": {},
             "events": {}, "bindings": [], "metadata": {}},
        ],
    })


@pytest.fixture
def route_capability():
    return {"capability_id": "cap_route_gen", "kind": "route", "name": "POST /api/generate",
            "qualified_name": "backend/api.py::generate", "description": "Generate idea",
            "inputs": [{"name": "prompt", "type": "str", "required": True, "description": ""}],
            "outputs": [], "side_effects": [], "origin_file": "app.py", "origin_line": 1,
            "framework": "fastapi", "http_method": "POST", "http_path": "/api/generate",
            "dependencies": [], "legacy": False, "confidence": 0.9, "metadata": {}}


@pytest.fixture
def confirmed_binding():
    return {"binding_id": "bind_1", "component_id": "component_0004", "event": "onClick",
            "target_capability": "cap_route_gen", "status": "CONFIRMED",
            "input_mapping": [{"source": "component_0003", "target": "prompt"}],
            "output_mapping": [], "loading_mapping": "", "error_mapping": "error",
            "confidence": 0.9, "rationale": ["verb match"], "transformations": [],
            "metadata": {}}


# Registry tests
def test_registry_lists_both_exporters():
    exporters = available_exporters()
    ids = {e.target_id for e in exporters}
    assert "react-vite-ts" in ids
    assert "pyside6-widgets" in ids


def test_get_exporter_react():
    assert get_exporter("react-vite-ts") is ReactViteTSExporter


def test_get_exporter_pyside():
    assert get_exporter("pyside6-widgets") is PySide6WidgetsExporter


def test_get_exporter_unknown_raises():
    with pytest.raises(ValueError, match="Unknown export target"):
        get_exporter("nonexistent")


# React backward compatibility
def test_react_legacy_plan_compat(sample_document, confirmed_binding):
    plan = build_export_plan(sample_document, [confirmed_binding])
    assert plan["mode"] == "export-to-new-directory"
    assert plan["bindings_embedded"] == 1
    assert "target" in plan


def test_react_legacy_export_still_works(sample_document, confirmed_binding, route_capability):
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "legacy"
        plan = export_react_project(sample_document, [confirmed_binding], [route_capability], None, target)
        assert plan["bindings_embedded"] == 1
        assert (target / "src" / "App.tsx").is_file()


# PySide6 exporter
def test_pyside_plan(sample_document, confirmed_binding):
    exp = PySide6WidgetsExporter()
    plan = exp.plan(sample_document, [confirmed_binding], [], None)
    assert plan.target == "pyside6-widgets"
    assert plan.components_total == 4
    assert plan.bindings_total == 1
    assert "main.py" in plan.files_created


def test_pyside_export_creates_files(sample_document, confirmed_binding, route_capability):
    exp = PySide6WidgetsExporter()
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "pyside"
        plan = exp.export(sample_document, [confirmed_binding], [route_capability], None, target, None, None)
        assert (target / "main.py").is_file()
        assert (target / "requirements.txt").is_file()
        assert (target / "uibinder_manifest.json").is_file()
        assert (target / "ui" / "generated_ui.py").is_file()
        assert (target / "runtime" / "capability_bridge.py").is_file()
        assert plan["bindings_realizable"] == 1


def test_pyside_generated_code_compiles(sample_document, confirmed_binding, route_capability):
    import compileall
    exp = PySide6WidgetsExporter()
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "pyside"
        exp.export(sample_document, [confirmed_binding], [route_capability], None, target, None, None)
        ok = compileall.compile_dir(str(target), quiet=1, force=True)
        assert ok


def test_pyside_manifest_is_valid_json(sample_document):
    exp = PySide6WidgetsExporter()
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "pyside"
        exp.export(sample_document, [], [], None, target, None, None)
        manifest = json.loads((target / "uibinder_manifest.json").read_text(encoding="utf-8"))
        assert manifest["exporter"] == "pyside6-widgets"
        assert "components_total" in manifest
        assert "schema_version" in manifest


# Determinism
def test_export_is_deterministic(sample_document, confirmed_binding, route_capability):
    exp = PySide6WidgetsExporter()
    outputs = []
    for _ in range(2):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "det"
            exp.export(sample_document, [confirmed_binding], [route_capability], None, target, None, None)
            files = sorted(target.rglob("*.py"))
            content = "\n".join(f.read_text(encoding="utf-8") for f in files)
            outputs.append(content)
    assert outputs[0] == outputs[1]


def test_react_export_is_deterministic(sample_document, confirmed_binding, route_capability):
    outputs = []
    for _ in range(2):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "det"
            export_react_project(sample_document, [confirmed_binding], [route_capability], None, target)
            app = (target / "src" / "App.tsx").read_text(encoding="utf-8")
            outputs.append(app)
    assert outputs[0] == outputs[1]


# Input immutability
def test_pyside_does_not_mutate_document(sample_document, confirmed_binding, route_capability):
    import copy
    before = copy.deepcopy(sample_document)
    exp = PySide6WidgetsExporter()
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "immutable"
        exp.export(sample_document, [confirmed_binding], [route_capability], None, target, None, None)
    assert sample_document.model_dump() == before.model_dump()


def test_react_does_not_mutate_bindings(sample_document, confirmed_binding, route_capability):
    import copy
    before = copy.deepcopy([confirmed_binding])
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "immutable"
        export_react_project(sample_document, [confirmed_binding], [route_capability], None, target)
    assert [confirmed_binding] == before


# Security still applies
def test_pyside_refuses_system_dirs(sample_document):
    exp = PySide6WidgetsExporter()
    with pytest.raises(ValueError, match="sistema"):
        exp.export(sample_document, [], [], None, Path("C:/Windows/Temp/exp"), None, None)


def test_pyside_refuses_drive_root(sample_document):
    exp = PySide6WidgetsExporter()
    with pytest.raises(ValueError, match="raíz"):
        exp.export(sample_document, [], [], None, Path("C:/"), None, None)


# Various component types
def test_pyside_handles_all_canonical_types():
    from backend.schema.ui_schema import BBox, Component
    types = ["container", "panel", "card", "text", "heading", "button",
             "input", "textarea", "select", "checkbox", "radio", "image",
             "icon", "table", "chart", "tabs", "sidebar", "navbar", "modal", "divider", "custom"]
    comps = []
    for i, t in enumerate(types):
        comps.append(Component(
            id=f"c_{t}", type=t, name=t, parent_id="screen", children=[],
            bbox=BBox(x=0, y=i*30.0, width=100, height=25),
            text=f"Test {t}" if t not in ("image", "divider") else None,
            styles={"background": "#333", "color": "#fff", "fontSize": "12px", "radius": "4"},
            states={}, events={}, bindings=[], metadata={},
        ))
    doc = UIDocument(screen={"id": "screen", "width": 800, "height": 800}, components=comps)
    exp = PySide6WidgetsExporter()
    plan = exp.plan(doc, [], [], None)
    assert plan.components_total == len(types)
    assert plan.components_native == len(types)


# Tabs
def test_pyside_handles_tabs():
    doc = UIDocument.model_validate({
        "ui_schema_version": 1,
        "screen": {"id": "screen", "width": 800, "height": 600},
        "components": [
            {"id": "tab_widget", "type": "tabs", "name": "tabs", "parent_id": "screen",
             "children": ["tab1", "tab2"], "bbox": {"x": 0, "y": 0, "width": 800, "height": 600},
             "text": None, "styles": {}, "states": {}, "events": {}, "bindings": [], "metadata": {}},
            {"id": "tab1", "type": "panel", "name": "tab1", "parent_id": "tab_widget",
             "children": [], "bbox": {"x": 0, "y": 0, "width": 400, "height": 300},
             "text": "Tab 1", "styles": {}, "states": {}, "events": {}, "bindings": [], "metadata": {}},
            {"id": "tab2", "type": "panel", "name": "tab2", "parent_id": "tab_widget",
             "children": [], "bbox": {"x": 0, "y": 0, "width": 400, "height": 300},
             "text": "Tab 2", "styles": {}, "states": {}, "events": {}, "bindings": [], "metadata": {}},
        ],
    })
    exp = PySide6WidgetsExporter()
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "tabs"
        plan = exp.export(doc, [], [], None, target, None, None)
        assert (target / "main.py").is_file()


# Unicode
def test_pyside_handles_unicode_text():
    doc = UIDocument.model_validate({
        "ui_schema_version": 1,
        "screen": {"id": "screen", "width": 800, "height": 600},
        "components": [
            {"id": "btn_unicode", "type": "button", "name": "btn", "parent_id": "screen",
             "children": [], "bbox": {"x": 0, "y": 0, "width": 200, "height": 40},
             "text": "Ñoño café résumo 中文", "styles": {}, "states": {}, "events": {}, "bindings": [], "metadata": {}},
        ],
    })
    exp = PySide6WidgetsExporter()
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "unicode"
        exp.export(doc, [], [], None, target, None, None)
        content = (target / "ui" / "generated_ui.py").read_text(encoding="utf-8")
        assert "Ñoño" in content or "Noño" in content  # depends on escaping


# Dangerous strings
def test_pyside_handles_dangerous_strings():
    doc = UIDocument.model_validate({
        "ui_schema_version": 1,
        "screen": {"id": "screen", "width": 800, "height": 600},
        "components": [
            {"id": "btn_danger", "type": "button", "name": "btn", "parent_id": "screen",
             "children": [], "bbox": {"x": 0, "y": 0, "width": 200, "height": 40},
             "text": "Click \"here\" or <there> & 'then'", "styles": {}, "states": {},
             "events": {}, "bindings": [], "metadata": {}},
        ],
    })
    exp = PySide6WidgetsExporter()
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "danger"
        exp.export(doc, [], [], None, target, None, None)
        content = (target / "ui" / "generated_ui.py").read_text(encoding="utf-8")
        # Should compile - quotes should be escaped
        import ast
        ast.parse(content)
