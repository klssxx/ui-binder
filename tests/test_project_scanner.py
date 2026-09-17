"""Regression tests for P1 project scanner bug (break → continue) and project analysis pipeline."""
from __future__ import annotations

from pathlib import Path

from backend.analyzer.project_scanner import scan_project


def test_scanner_does_not_break_on_ignored_dir(tmp_path):
    """node_modules in root shouldn't abort the whole scan."""
    root = tmp_node_modules = tmp_path / "proj"
    root.mkdir()
    (root / "node_modules").mkdir()
    (root / "node_modules" / "dep.js").write_text("var x;", encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("def hello(): pass", encoding="utf-8")
    (root / "package.json").write_text('{"name":"p","dependencies":{"react":"18"}}', encoding="utf-8")

    result = scan_project(root)
    rels = {f["rel_path"] for f in result["source_files"]}
    assert "src/app.py" in rels, f"src/app.py missing; got {rels}"
    assert "package.json" in {m["path"] for m in result["manifests"]}
    # node_modules excluded by parts filter
    assert not any("node_modules" in r for r in rels)


def test_scanner_detects_requirements(tmp_path):
    root = tmp_path / "pyproj"
    root.mkdir()
    (root / "requirements.txt").write_text("fastapi>=0.115\npytest>=8\n", encoding="utf-8")
    (root / "app.py").write_text("from fastapi import FastAPI\napp = FastAPI()", encoding="utf-8")

    result = scan_project(root)
    assert "fastapi" in result["frameworks"]
    manifests = {m["type"]: m for m in result["manifests"]}
    assert "requirements" in manifests
    assert any("fastapi" in d.lower() for d in manifests["requirements"]["dependencies"])


def test_scanner_ignores_dot_dirs(tmp_path):
    root = tmp_path / "proj2"
    root.mkdir()
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("x", encoding="utf-8")
    (root / "main.py").write_text("print('hi')", encoding="utf-8")

    result = scan_project(root)
    rels = {f["rel_path"] for f in result["source_files"]}
    assert "main.py" in rels
    assert not any(".git" in r for r in rels)
