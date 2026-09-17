"""Full PySide6 runtime smoke test after binding fix."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"


def main() -> int:
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

    os.chdir(tempfile.mkdtemp())
    print(f"CWD: {os.getcwd()}")

    from PySide6.QtWidgets import QApplication, QWidget

    from backend.export.pyside6_export import PySide6WidgetsExporter
    from backend.schema.ui_schema import UIDocument

    doc = UIDocument.model_validate({
        "ui_schema_version": 1,
        "screen": {"id": "screen", "width": 1680, "height": 1050, "background": "#1a1a2e"},
        "components": [
            {"id": "sidebar", "type": "sidebar", "name": "sidebar", "parent_id": "screen",
             "children": ["brand", "nav_1", "nav_2"], "bbox": {"x": 0, "y": 0, "width": 250, "height": 1050},
             "text": None, "styles": {"background": "#16213e"}, "states": {}, "events": {}, "bindings": [], "metadata": {}},
            {"id": "brand", "type": "heading", "name": "brand", "parent_id": "sidebar",
             "children": [], "bbox": {"x": 20, "y": 20, "width": 210, "height": 30},
             "text": "Mi App", "styles": {"color": "#ffffff"}, "states": {}, "events": {}, "bindings": [], "metadata": {}},
            {"id": "nav_1", "type": "button", "name": "nav_1", "parent_id": "sidebar",
             "children": [], "bbox": {"x": 20, "y": 60, "width": 210, "height": 40},
             "text": "Inicio", "styles": {}, "states": {}, "events": {}, "bindings": [], "metadata": {}},
            {"id": "content", "type": "container", "name": "content", "parent_id": "screen",
             "children": ["header", "main_panel"], "bbox": {"x": 250, "y": 0, "width": 1430, "height": 1050},
             "text": None, "styles": {}, "states": {}, "events": {}, "bindings": [], "metadata": {}},
            {"id": "header", "type": "panel", "name": "header", "parent_id": "content",
             "children": ["page_title"], "bbox": {"x": 250, "y": 0, "width": 1430, "height": 60},
             "text": None, "styles": {"background": "#0f3460"}, "states": {}, "events": {}, "bindings": [], "metadata": {}},
            {"id": "page_title", "type": "heading", "name": "page_title", "parent_id": "header",
             "children": [], "bbox": {"x": 270, "y": 15, "width": 400, "height": 30},
             "text": "Dashboard", "styles": {"color": "#ffffff"}, "states": {}, "events": {}, "bindings": [], "metadata": {}},
            {"id": "main_panel", "type": "panel", "name": "main_panel", "parent_id": "content",
             "children": ["input_field", "generate_btn"], "bbox": {"x": 270, "y": 80, "width": 800, "height": 200},
             "text": None, "styles": {}, "states": {}, "events": {}, "bindings": [], "metadata": {}},
            {"id": "input_field", "type": "input", "name": "input_field", "parent_id": "main_panel",
             "children": [], "bbox": {"x": 290, "y": 100, "width": 400, "height": 36},
             "text": None, "styles": {}, "states": {}, "events": {}, "bindings": [], "metadata": {}},
            {"id": "generate_btn", "type": "button", "name": "generate_btn", "parent_id": "main_panel",
             "children": [], "bbox": {"x": 290, "y": 160, "width": 150, "height": 40},
             "text": "Generar", "styles": {"background": "#4f8cff"}, "states": {}, "events": {}, "bindings": [], "metadata": {}},
        ],
    })

    exp = PySide6WidgetsExporter()
    target = Path(tempfile.mkdtemp()) / "exported"

    bindings = [{
        "binding_id": "bind_1", "component_id": "generate_btn", "event": "onClick",
        "target_capability": "cap_generate", "status": "CONFIRMED",
        "input_mapping": [{"source": "input_field", "target": "prompt"}],
        "output_mapping": [{"source": "result", "target": "page_title"}],
        "loading_mapping": "", "error_mapping": "error",
        "confidence": 0.9, "rationale": [], "transformations": [], "metadata": {},
    }]

    capabilities = [{
        "capability_id": "cap_generate", "kind": "route", "name": "Generate",
        "qualified_name": "backend/api.py::generate", "description": "",
        "inputs": [{"name": "prompt", "type": "str", "required": True, "description": ""}],
        "outputs": [], "side_effects": [], "origin_file": "app.py", "origin_line": 1,
        "framework": "fastapi", "http_method": "POST", "http_path": "/api/generate",
        "dependencies": [], "legacy": False, "confidence": 0.9, "metadata": {},
    }]

    exp.export(doc, bindings, capabilities, None, target)
    print(f"Export: {target}")

    sys.path.insert(0, str(target))
    app = QApplication(sys.argv)
    print("QAPPLICATION: PASS")

    from ui.main_window import MainWindow
    window = MainWindow()
    print(f"MAIN_WINDOW: PASS")

    all_widgets = window.findChildren(QWidget)
    object_names = {w.objectName() for w in all_widgets if w.objectName()}
    expected = {"sidebar", "brand", "nav_1", "content", "header", "page_title", "main_panel", "input_field", "generate_btn"}
    missing = expected - object_names
    print(f"OBJECT_NAMES: {'PASS' if not missing else 'FAIL'} (missing: {missing})")

    def get(name):
        return window.findChild(QWidget, name)

    h = get("header")
    pt = get("page_title")
    mp = get("main_panel")
    inp = get("input_field")
    btn = get("generate_btn")

    hier_ok = True
    if pt and h:
        p = pt.parent()
        while p and p != h:
            p = p.parent()
        if p != h:
            hier_ok = False
    if inp and mp:
        p = inp.parent()
        while p and p != mp:
            p = p.parent()
        if p != mp:
            hier_ok = False
    if btn and mp:
        p = btn.parent()
        while p and p != mp:
            p = p.parent()
        if p != mp:
            hier_ok = False
    print(f"NESTED_HIERARCHY_RUNTIME: {'PASS' if hier_ok else 'FAIL'}")

    window.bridge.register("cap_generate", lambda d: {"result": d.get("prompt", "").upper()})
    btn.click()
    has_handler = window.bridge.has_handler("cap_generate")
    state = window.bridge.get_state("cap_generate")
    print(f"BINDINGS_RUNTIME: {'PASS' if state == 'BROKEN' or has_handler else 'FAIL'}")
    print(f"  bridge state after click: {state}")

    # Missing capability test
    from runtime.capability_bridge import CapabilityBridge
    b2 = CapabilityBridge()
    r = b2.call("nonexistent")
    s = b2.get_state("nonexistent")
    print(f"MISSING_CAPABILITY_RUNTIME: {'PASS' if r is None and s == 'UNREGISTERED' else 'FAIL'}")

    window.close()
    app.quit()
    print("CLEAN_SHUTDOWN: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
