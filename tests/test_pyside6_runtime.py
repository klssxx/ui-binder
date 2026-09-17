"""PySide6 runtime test with explicit binding invocation assertions."""
from __future__ import annotations

import os
import sys
import importlib.util
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _clean_everything():
    """Remove ALL cached ui/runtime modules and clean sys.path."""
    to_remove = [k for k in sys.modules.keys() if k.startswith("ui") or k.startswith("runtime")]
    for k in to_remove:
        del sys.modules[k]
    sys.path = [p for p in sys.path if ".pytest_tmp" not in p and "exported" not in p]
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_from_file(target, module_path, module_name):
    """Load a Python module from a specific file path."""
    full_path = target / module_path
    if not full_path.exists():
        raise FileNotFoundError(f"Module not found: {full_path}")
    spec = importlib.util.spec_from_file_location(module_name, full_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _create_window_for_test(target: Path):
    """Create a MainWindow from a specific target export."""
    _clean_everything()
    
    # Load capability bridge
    bridge_mod = _load_from_file(target, Path("runtime/capability_bridge.py"), "runtime.capability_bridge")
    CapabilityBridge = bridge_mod.CapabilityBridge
    
    # Load binding runtime (dependency of generated_ui)
    _load_from_file(target, Path("runtime/binding_runtime.py"), "runtime.binding_runtime")
    
    # Load generated_ui which contains build_ui
    generated_mod = _load_from_file(target, Path("ui/generated_ui.py"), "ui.generated_ui")
    
    # Load main_window
    mw_mod = _load_from_file(target, Path("ui/main_window.py"), "ui.main_window")
    MainWindow = mw_mod.MainWindow
    
    return MainWindow


def _export(target: Path, components: list, bindings: list, capabilities: list):
    """Create a PySide6 export."""
    sys.path.insert(0, str(PROJECT_ROOT))
    from backend.export.pyside6_export import PySide6WidgetsExporter
    from backend.schema.ui_schema import UIDocument

    doc = UIDocument.model_validate({
        "ui_schema_version": 1,
        "screen": {"id": "screen", "width": 800, "height": 600},
        "components": components,
    })
    exp = PySide6WidgetsExporter()
    exp.export(doc, bindings, capabilities, None, target)


@pytest.fixture(scope="module")
def qt_app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(sys.argv)


def test_binding_click_invokes_callback(qt_app, tmp_path):
    """Clicking button must invoke callback exactly once with correct payload."""
    from PySide6.QtWidgets import QWidget

    target = tmp_path / "t1"
    _export(target, [
        {"id": "input_field", "type": "input", "name": "input_field", "parent_id": "screen",
         "children": [], "bbox": {"x": 0, "y": 0, "width": 200, "height": 30},
         "text": None, "styles": {}, "states": {}, "events": {}, "bindings": [], "metadata": {}},
        {"id": "page_title", "type": "heading", "name": "page_title", "parent_id": "screen",
         "children": [], "bbox": {"x": 0, "y": 40, "width": 200, "height": 30},
         "text": "Initial", "styles": {}, "states": {}, "events": {}, "bindings": [], "metadata": {}},
        {"id": "generate_btn", "type": "button", "name": "generate_btn", "parent_id": "screen",
         "children": [], "bbox": {"x": 0, "y": 80, "width": 150, "height": 40},
         "text": "Generar", "styles": {}, "states": {}, "events": {}, "bindings": [], "metadata": {}},
    ], [{
        "binding_id": "bind_1", "component_id": "generate_btn", "event": "onClick",
        "target_capability": "cap_generate", "status": "CONFIRMED",
        "input_mapping": [{"source": "input_field", "target": "prompt"}],
        "output_mapping": [{"source": "result", "target": "page_title"}],
        "loading_mapping": "", "error_mapping": "error",
        "confidence": 0.9, "rationale": [], "transformations": [], "metadata": {},
    }], [{
        "capability_id": "cap_generate", "kind": "route", "name": "Generate",
        "qualified_name": "backend/api.py::generate", "description": "",
        "inputs": [{"name": "prompt", "type": "str", "required": True, "description": ""}],
        "outputs": [], "side_effects": [], "origin_file": "app.py", "origin_line": 1,
        "framework": "fastapi", "http_method": "POST", "http_path": "/api/generate",
        "dependencies": [], "legacy": False, "confidence": 0.9, "metadata": {},
    }])

    MainWindow = _create_window_for_test(target)
    window = MainWindow()

    callback_data = {"call_count": 0, "received_payload": None, "result": None}

    def fake_generate(data):
        callback_data["call_count"] += 1
        callback_data["received_payload"] = data
        result = {"result": data.get("prompt", "").upper()}
        callback_data["result"] = result
        return result

    window.bridge.register("cap_generate", fake_generate)

    btn = window.findChild(QWidget, "generate_btn")
    inp = window.findChild(QWidget, "input_field")

    assert btn is not None
    assert inp is not None

    inp.setText("hola")
    btn.click()

    assert callback_data["call_count"] == 1
    assert callback_data["received_payload"] == {"prompt": "hola"}
    assert callback_data["result"] == {"result": "HOLA"}

    page_title = window.findChild(QWidget, "page_title")
    assert page_title.text() == "HOLA"

    window.close()


def test_binding_output_mapping_updates_widget(qt_app, tmp_path):
    """Output mapping should update target widget text after click."""
    from PySide6.QtWidgets import QWidget

    target = tmp_path / "t2"
    _export(target, [
        {"id": "input_field", "type": "input", "name": "input_field", "parent_id": "screen",
         "children": [], "bbox": {"x": 0, "y": 0, "width": 200, "height": 30},
         "text": None, "styles": {}, "states": {}, "events": {}, "bindings": [], "metadata": {}},
        {"id": "page_title", "type": "heading", "name": "page_title", "parent_id": "screen",
         "children": [], "bbox": {"x": 0, "y": 40, "width": 200, "height": 30},
         "text": "Initial", "styles": {}, "states": {}, "events": {}, "bindings": [], "metadata": {}},
        {"id": "generate_btn", "type": "button", "name": "generate_btn", "parent_id": "screen",
         "children": [], "bbox": {"x": 0, "y": 80, "width": 150, "height": 40},
         "text": "Generar", "styles": {}, "states": {}, "events": {}, "bindings": [], "metadata": {}},
    ], [{
        "binding_id": "bind_1", "component_id": "generate_btn", "event": "onClick",
        "target_capability": "cap_generate", "status": "CONFIRMED",
        "input_mapping": [{"source": "input_field", "target": "prompt"}],
        "output_mapping": [{"source": "result", "target": "page_title"}],
        "loading_mapping": "", "error_mapping": "error",
        "confidence": 0.9, "rationale": [], "transformations": [], "metadata": {},
    }], [{
        "capability_id": "cap_generate", "kind": "route", "name": "Generate",
        "qualified_name": "backend/api.py::generate", "description": "",
        "inputs": [{"name": "prompt", "type": "str", "required": True, "description": ""}],
        "outputs": [], "side_effects": [], "origin_file": "app.py", "origin_line": 1,
        "framework": "fastapi", "http_method": "POST", "http_path": "/api/generate",
        "dependencies": [], "legacy": False, "confidence": 0.9, "metadata": {},
    }])

    MainWindow = _create_window_for_test(target)
    window = MainWindow()
    window.bridge.register("cap_generate", lambda d: {"result": d.get("prompt", "").upper()})

    btn = window.findChild(QWidget, "generate_btn")
    inp = window.findChild(QWidget, "input_field")
    page_title = window.findChild(QWidget, "page_title")

    inp.setText("test")
    btn.click()

    assert page_title.text() == "TEST"
    window.close()


def test_binding_missing_capability_no_crash(qt_app, tmp_path):
    """Binding with missing target capability must not crash."""
    from PySide6.QtWidgets import QWidget

    target = tmp_path / "t3"
    _export(target, [
        {"id": "btn", "type": "button", "name": "btn", "parent_id": "screen",
         "children": [], "bbox": {"x": 0, "y": 0, "width": 100, "height": 40},
         "text": "Click", "styles": {}, "states": {}, "events": {}, "bindings": [], "metadata": {}},
    ], [{
        "binding_id": "bind_1", "component_id": "btn", "event": "onClick",
        "target_capability": "nonexistent_cap", "status": "CONFIRMED",
        "input_mapping": [], "output_mapping": [],
        "loading_mapping": "", "error_mapping": "",
        "confidence": 0.9, "rationale": [], "transformations": [], "metadata": {},
    }], [])

    MainWindow = _create_window_for_test(target)
    window = MainWindow()
    btn = window.findChild(QWidget, "btn")
    assert btn is not None

    btn.click()
    assert not window.bridge.has_handler("nonexistent_cap")
    window.close()
