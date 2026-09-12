"""Export tests: safe target rules, plan, generated project sanity."""
from __future__ import annotations

import json
from pathlib import Path

from backend.export import build_export_plan, export_react_project
from backend.schema.ui_schema import BBox, Component, UIDocument


def doc() -> UIDocument:
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
             "text": "Idea Generator", "styles": {}, "states": {}, "events": {},
             "bindings": [], "metadata": {}},
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


def route_cap():
    return {"capability_id": "cap_route_gen", "kind": "route", "name": "POST /api/generate",
            "qualified_name": "backend/app.py::api_generate",
            "http_method": "POST", "http_path": "/api/generate",
            "inputs": [{"name": "prompt", "type": "str", "required": True, "description": ""}],
            "outputs": [], "side_effects": [], "confidence": 0.95}


def confirmed_binding():
    return {"binding_id": "bind_1", "component_id": "component_0004", "event": "onClick",
            "target_capability": "cap_route_gen", "status": "CONFIRMED",
            "input_mapping": [{"source": "component_0003", "target": "prompt"}],
            "output_mapping": [], "loading_mapping": "", "error_mapping": "error",
            "confidence": 0.9, "rationale": [], "transformations": []}


def test_plan_is_dry_run():
    plan = build_export_plan(doc(), [])
    assert "files_created" in plan and plan["files_modified"] == []
    assert plan["mode"] == "export-to-new-directory"


def test_export_writes_functional_project(tmp_path):
    target = tmp_path / "exported"
    plan = export_react_project(doc(), [confirmed_binding()], [route_cap()], None, target)
    assert plan["bindings_embedded"] == 1
    for f in ["package.json", "vite.config.ts", "tsconfig.json", "index.html",
              "src/main.tsx", "src/App.tsx", "src/api.ts", "src/bindings.json"]:
        assert (target / f).is_file(), f"missing {f}"
    pkg = json.loads((target / "package.json").read_text(encoding="utf-8"))
    assert pkg["dependencies"]["react"]
    api = (target / "src/api.ts").read_text(encoding="utf-8")
    assert "/api/generate" in api and "POST" in api
    app = (target / "src/App.tsx").read_text(encoding="utf-8")
    assert "Generar" in app  # button text preserved
    assert "component_0003" in app  # input read from mapped source
    bindings = json.loads((target / "src/bindings.json").read_text(encoding="utf-8"))
    assert bindings[0]["binding_id"] == "bind_1"


def test_export_refuses_non_empty_target(tmp_path):
    target = tmp_path / "occupied"
    target.mkdir()
    (target / "junk.txt").write_text("x", encoding="utf-8")
    try:
        export_react_project(doc(), [], [], None, target)
        raise AssertionError("should have refused")
    except ValueError as e:
        assert "not empty" in str(e)


def test_export_refuses_inside_source_project(tmp_path):
    source = tmp_path / "source"
    (source / "frontend").mkdir(parents=True)
    target = source / "frontend" / "new"
    try:
        export_react_project(doc(), [], [], None, target, source_project=source)
        raise AssertionError("should have refused")
    except ValueError as e:
        assert "overlap" in str(e)
