"""Analyzer tests: Python ast, Node Babel bridge, fallback, capability graph."""
from __future__ import annotations

from pathlib import Path

from backend.analyzer.capability_builder import build_capabilities
from backend.analyzer.node_bridge import analyze_js_files, node_available
from backend.analyzer.project_scanner import scan_project
from backend.analyzer.python_analyzer import analyze_python_file
from tests.conftest import read_json


def test_python_analyzer_finds_routes_and_functions(sample_app_dir):
    mod = analyze_python_file(sample_app_dir / "backend" / "app.py", "backend/app.py")
    routes = {(r.method, r.path) for r in mod.routes}
    assert ("POST", "/api/generate") in routes
    assert ("GET", "/api/health") in routes
    fn_names = {f.name for f in mod.functions}
    assert {"generate_idea", "evaluate_idea", "save_result", "load_history",
            "export_report", "restore_session", "api_generate"} <= fn_names
    gen = next(f for f in mod.functions if f.name == "generate_idea")
    assert {p["name"] for p in gen.params} == {"prompt", "mode"}
    save = next(f for f in mod.functions if f.name == "save_result")
    assert "fs" in save.side_effects


def test_python_analyzer_models(sample_app_dir):
    mod = analyze_python_file(sample_app_dir / "backend" / "app.py", "backend/app.py")
    assert "GenerateRequest" in mod.models
    fields = {f["name"] for f in mod.models["GenerateRequest"]}
    assert {"prompt", "mode"} == fields


def test_node_bridge_real_ast(sample_app_dir):
    if not node_available():
        import pytest
        pytest.skip("node not available in this environment")
    src = sample_app_dir / "frontend" / "src"
    files = [src / "App.tsx", src / "components" / "GenerateButton.tsx",
             src / "components" / "IdeaInput.tsx", src / "components" / "ResultPanel.tsx"]
    results = analyze_js_files(files)
    assert len(results) == 4 and not any(r.get("fallback") for r in results)

    app = next(r for r in results if r["file"].endswith("App.tsx"))
    comp_names = {c["name"] for c in app["reactComponents"]}
    assert "App" in comp_names
    fn_names = {f["name"] for f in app["functions"]}
    assert "handleGenerate" in fn_names
    fetches = [(f["method"], f["url"]) for f in app["fetchCalls"]]
    assert ("POST", "/api/generate") in fetches
    events = {e["prop"] for e in app["eventHandlers"]}
    assert "onClick" in events
    assert "onChange" in events

    button = next(r for r in results if r["file"].endswith("GenerateButton.tsx"))
    assert {c["name"] for c in button["reactComponents"]} == {"GenerateButton"}
    assert "default" in button["exports"]  # `export default function GenerateButton`


def test_fallback_scanner_flagged_low_confidence(sample_app_dir):
    from backend.analyzer.js_fallback import regex_scan
    results = regex_scan([sample_app_dir / "frontend" / "src" / "App.tsx"], reason="test")
    r = results[0]
    assert r["fallback"] is True and r["fallback_reason"] == "test"
    names = {f["name"] for f in r["functions"]}
    assert "handleGenerate" in names


def test_bridge_falls_back_on_bad_script(tmp_path, monkeypatch):
    from backend.analyzer import node_bridge
    monkeypatch.setattr(node_bridge, "_SCRIPT", tmp_path / "missing.mjs")
    out = node_bridge.analyze_js_files([tmp_path / "x.ts"])
    assert out == []


def test_scan_project_shape(sample_app_dir):
    scan = scan_project(sample_app_dir)
    assert "react" in scan["frameworks"]
    assert "vite" in scan["frameworks"]
    assert "fastapi" in scan["frameworks"]
    assert "python" in scan["languages"]
    assert "typescript" in scan["languages"]
    rels = {f["rel_path"] for f in scan["source_files"]}
    assert "backend/app.py" in rels
    assert "frontend/src/App.tsx" in rels
    assert "index.html" in scan["entrypoints"] or any("package.json" in e for e in scan["entrypoints"])


def test_capability_graph_end_to_end(sample_app_dir):
    scan = scan_project(sample_app_dir)
    graph = build_capabilities(scan)
    names = {n.name for n in graph.nodes}
    exp = read_json(sample_app_dir.parent / "golden-reference" / "expected_capabilities.json")
    for required in exp["must_include_names"]:
        assert required in names, f"missing capability {required}"
    route_nodes = [n for n in graph.nodes if n.kind == "route"]
    routes = {(n.http_method, n.http_path) for n in route_nodes}
    for r in exp["routes"]:
        assert (r["method"], r["path"]) in routes
    comp_caps = {n.name for n in graph.nodes if n.kind == "component"}
    for c in exp["react_components"]:
        assert c in comp_caps
    # graph edges: fetch (frontend) → route (backend) across the stack boundary
    fetch_edges = [e for e in graph.edges if e.relation == "fetches"]
    assert any(e.target in {n.capability_id for n in route_nodes
                            if n.http_path == "/api/generate"} for e in fetch_edges)
    # python route → handler edge
    handle_edges = [e for e in graph.edges if e.relation == "handles"]
    assert len(handle_edges) >= 1
