"""PySide6 Widgets exporter — generates a standalone Qt desktop app from the UI AST.

Target output:
    target/
      main.py
      requirements.txt
      uibinder_manifest.json
      bindings.json
      ui/
        __init__.py
        main_window.py
        generated_ui.py
        styles.qss
        stroke_overlay.py
      runtime/
        __init__.py
        binding_runtime.py
        capability_bridge.py
      assets/

Design:
    * UIDocument is treated as immutable input.
    * Bindings/capabilities are detached before processing.
    * Layout inference is deterministic (same UIDocument = same layout plan).
    * Styles translated to QSS with proper escaping.
    * Bindings expose injectable callbacks via CapabilityBridge.
    * NO business logic from the imported project is copied.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.export.base import Exporter, ExportPlan, register_exporter
from backend.schema.ui_schema import UIDocument


class PySide6WidgetsExporter(Exporter):
    target_id = "pyside6-widgets"
    label = "PySide6 / Widgets"

    # Mapping UI AST type -> (Qt class, category)
    _WIDGET_MAP: dict[str, tuple[str, str]] = {
        "screen": ("QMainWindow", "window"),
        "container": ("QWidget", "container"),
        "panel": ("QFrame", "container"),
        "card": ("QFrame", "container"),
        "text": ("QLabel", "display"),
        "heading": ("QLabel", "display"),
        "button": ("QPushButton", "input"),
        "input": ("QLineEdit", "input"),
        "textarea": ("QPlainTextEdit", "input"),
        "select": ("QComboBox", "input"),
        "checkbox": ("QCheckBox", "input"),
        "radio": ("QRadioButton", "input"),
        "image": ("QLabel", "display"),
        "table": ("QTableView", "display"),
        "tabs": ("QTabWidget", "container"),
        "sidebar": ("QFrame", "container"),
        "navbar": ("QFrame", "container"),
        "modal": ("QDialog", "window"),
        "divider": ("QFrame", "display"),
        "icon": ("QLabel", "display"),
        "chart": ("QWidget", "display"),
        "custom": ("QWidget", "container"),
    }

    def plan(self, document, bindings, capabilities, tokens) -> ExportPlan:
        p = ExportPlan()
        p.target = self.target_id
        p.target_label = self.label
        p.files_created = [
            "main.py", "requirements.txt", "uibinder_manifest.json", "bindings.json",
            "ui/__init__.py", "ui/main_window.py", "ui/generated_ui.py",
            "ui/styles.qss", "ui/stroke_overlay.py",
            "runtime/__init__.py", "runtime/binding_runtime.py", "runtime/capability_bridge.py",
        ]
        p.components_total = len(document.components)
        p.components_native = sum(
            1 for c in document.components if c.type in self._WIDGET_MAP
        )
        p.components_fallback = p.components_total - p.components_native
        confirmed = [b for b in bindings if b.get("status") == "CONFIRMED"]
        p.bindings_total = len(bindings)
        p.bindings_realizable = len(confirmed)
        p.bindings_unresolved = len(bindings) - len(confirmed)
        # Unsupported types
        for c in document.components:
            if c.type not in self._WIDGET_MAP:
                p.unsupported.append(c.type)
        return p

    def validate(self, document, bindings, capabilities, tokens) -> list[str]:
        warnings = []
        if not document.components:
            warnings.append("No components in UI document — export will be empty.")
        unsupported = {c.type for c in document.components} - set(self._WIDGET_MAP)
        for u in sorted(unsupported):
            warnings.append(f"Component type '{u}' has no native mapping — using fallback.")
        return warnings

    def export(self, document, bindings, capabilities, tokens, target,
               source_project=None, image_resolver=None) -> dict[str, Any]:
        from backend.security.paths import is_safe_export_target

        ok, why = is_safe_export_target(target, source_project)
        if not ok:
            raise ValueError(why)

        # Detach to avoid mutating inputs
        bindings = _detach(bindings)

        # Build directory structure
        target.mkdir(parents=True, exist_ok=True)
        (target / "ui").mkdir(exist_ok=True)
        (target / "runtime").mkdir(exist_ok=True)
        (target / "assets").mkdir(exist_ok=True)

        # Layout plan (deterministic)
        layout = _compute_layout_plan(document)

        # Generate code
        main_py = _render_main_py(document, layout)
        manifest_py = _render_manifest_py(document, bindings, capabilities, layout, tokens)
        styles_qss = _render_styles_qss(document)
        stroke_py = _render_stroke_overlay(document)
        runtime_bridge = _render_capability_bridge(bindings)
        runtime_binding = _render_binding_runtime(bindings)

        (target / "main.py").write_text(main_py, encoding="utf-8")
        (target / "requirements.txt").write_text(_REQUIREMENTS_TXT, encoding="utf-8")
        (target / "ui/__init__.py").write_text("", encoding="utf-8")
        (target / "ui/main_window.py").write_text(_MAIN_WINDOW_PY, encoding="utf-8")
        (target / "ui/generated_ui.py").write_text(manifest_py, encoding="utf-8")
        (target / "ui/styles.qss").write_text(styles_qss, encoding="utf-8")
        (target / "ui/stroke_overlay.py").write_text(stroke_py, encoding="utf-8")
        (target / "runtime/__init__.py").write_text("", encoding="utf-8")
        (target / "runtime/capability_bridge.py").write_text(runtime_bridge, encoding="utf-8")
        (target / "runtime/binding_runtime.py").write_text(runtime_binding, encoding="utf-8")

        # Bindings JSON
        (target / "bindings.json").write_text(
            json.dumps(bindings, ensure_ascii=False, indent=2), encoding="utf-8")

        # Manifest
        manifest = _build_manifest(document, bindings, capabilities, tokens, layout)
        (target / "uibinder_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        # Copy assets
        assets_copied = 0
        if image_resolver is not None:
            import shutil
            for comp in document.components:
                styles = comp.model_dump().get("styles") if hasattr(comp, "model_dump") else comp.styles
                src = styles.get("src") if isinstance(styles, dict) else None
                if not isinstance(src, str):
                    continue
                record_path = image_resolver(comp.id)
                if record_path and Path(record_path).is_file():
                    shutil.copyfile(record_path, target / "assets" / f"{comp.id}{Path(record_path).suffix}")
                    assets_copied += 1

        plan = self.plan(document, bindings, capabilities, tokens)
        d = plan.to_dict()
        d["target_path"] = str(target)
        d["assets_copied"] = assets_copied
        return d


def _detach(bindings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Shallow copy each binding dict so export doesn't mutate input."""
    return [{**b} for b in bindings]


# ---------------------------------------------------------------- layout

def _compute_layout_plan(document: UIDocument) -> dict[str, Any]:
    """Deterministic spatial analysis -> Qt layout plan.

    For now, uses geometric nesting + fallback absolute positioning.
    Confidence is recorded per component.
    """
    by_id = document.by_id()
    root_children = document.children_of("screen")
    plan = {"root_children": [], "components": {}, "fallback_used": []}

    for child in root_children:
        plan["root_children"].append(child.id)
        _analyze_node(child, by_id, plan)

    return plan


def _analyze_node(comp, by_id, plan):
    children = [by_id[cid] for cid in comp.children if cid in by_id]
    if not children:
        plan["components"][comp.id] = {"layout": "leaf"}
        return

    # Try to detect stack/row
    if len(children) <= 1:
        direction = "none"
    else:
        xs = [c.bbox.x for c in children]
        ys = [c.bbox.y for c in children]
        x_range = max(xs) - min(xs)
        y_range = max(ys) - min(ys)
        direction = "vertical" if y_range >= x_range else "horizontal"

    for child in children:
        _analyze_node(child, by_id, plan)

    plan["components"][comp.id] = {
        "layout": direction,
        "child_count": len(children),
    }


# ---------------------------------------------------------------- codegen

def _render_main_py(document: UIDocument, layout: dict[str, Any]) -> str:
    """Entry point for the generated app."""
    return f'''"""Generated by UI Binder — PySide6 Widgets export.
Run: python main.py
"""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(open("ui/styles.qss", encoding="utf-8").read())
    window = MainWindow()
    window.setWindowTitle("UI Binder Export")
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
'''


_MAIN_WINDOW_PY = '''"""Main window — loads generated UI and wires bindings."""
from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout
from PySide6.QtCore import Qt

from ui.generated_ui import build_ui
from runtime.capability_bridge import CapabilityBridge


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.bridge = CapabilityBridge()
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        build_ui(self, layout, self.bridge)
'''


def _render_manifest_py(document: UIDocument, bindings: list[dict[str, Any]],
                        capabilities: list[dict[str, Any]],
                        layout: dict[str, Any],
                        tokens: dict[str, Any] | None) -> str:
    """Generate the UI widget tree as Python code."""
    lines = [
        '"""Generated by UI Binder — do not edit manually if you plan to re-export."""',
        "from __future__ import annotations",
        "",
        "from PySide6.QtWidgets import (",
        "    QWidget, QFrame, QLabel, QPushButton, QLineEdit, QPlainTextEdit,",
        "    QComboBox, QCheckBox, QRadioButton, QTableView, QTabWidget, QDialog,",
        "    QVBoxLayout, QHBoxLayout, QGridLayout, QSplitter, QScrollArea,",
        "    QSizePolicy, QApplication",
        ")",
        "from PySide6.QtCore import Qt, QSize",
        "from PySide6.QtGui import QPixmap",
        "",
        "from runtime.binding_runtime import BindingRuntime",
        "",
        "",
        "def build_ui(window, layout, bridge):",
        "    \"\"\"Construct the widget tree and register bindings.\"\"\"",
    ]

    comps = {c.id: c for c in document.components}
    root_children = [cid for cid in layout.get("root_children", [])]
    for cid in sorted(root_children):
        comp = comps.get(cid)
        if comp is None:
            continue
        lines.append(f"    # Component: {comp.id} ({comp.type})")
        lines.append(f"    widget_{comp.id} = _create_{comp.id}()")
        lines.append(f"    layout.addWidget(widget_{comp.id})")
        if comp.type == "button":
            cap = _find_binding_cap(comp.id, bindings)
            if cap:
                method = cap.get("http_method", "POST").upper()
                path = cap.get("http_path", "")
                bridge_reg = f'bridge.register("{cap["capability_id"]}", lambda *a, **k: None)'
                lines.append(f"    {bridge_reg}")
                if method == "GET":
                    lines.append(f'    widget_{comp.id}.clicked.connect(lambda: bridge.call("{cap["capability_id"]}"))')
                else:
                    lines.append(f'    widget_{comp.id}.clicked.connect(lambda: bridge.call("{cap["capability_id"]}", {{}}))')
        lines.append("")

    # Emit widget factory functions
    lines.append("")
    lines.append("")
    for comp in document.components:
        lines.extend(_render_widget_factory(comp))

    return "\n".join(lines) + "\n"


def _render_widget_factory(comp) -> list[str]:
    """Generate a single widget creation function."""
    ctype = comp.type
    mapping = PySide6WidgetsExporter._WIDGET_MAP.get(ctype, ("QWidget", "container"))
    qt_class, category = mapping

    lines = [
        f"def _create_{comp.id}():",
        f"    w = {qt_class}()",
        f"    w.setObjectName({json.dumps(comp.id, ensure_ascii=False)})",
    ]

    # Geometry
    b = comp.bbox
    if qt_class != "QMainWindow":  # top-level uses layout
        lines.append(f"    w.setGeometry({b.x:g}, {b.y:g}, {b.width:g}, {b.height:g})")
        lines.append(f"    w.setMinimumSize({max(1, int(b.width // 4))}, {max(1, int(b.height // 4))})")

    # Text
    if comp.text:
        if qt_class in ("QLabel", "QPushButton", "QCheckBox", "QRadioButton"):
            safe_text = comp.text.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'    w.setText("{safe_text}")')
        elif qt_class in ("QLineEdit",):
            safe_text = comp.text.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'    w.setPlaceholderText("{safe_text}")')

    # Tooltip from metadata
    if comp.metadata.get("tooltip"):
        safe_tt = comp.metadata["tooltip"].replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'    w.setToolTip("{safe_tt}")')

    # Stylesheet (from styles dict)
    qss = _styles_to_qss(comp.styles)
    if qss:
        safe_qss = qss.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'    w.setStyleSheet("{safe_qss}")')

    lines.append("    return w")
    return lines


def _find_binding_cap(component_id: str, bindings: list[dict[str, Any]]) -> dict[str, Any] | None:
    for b in bindings:
        if b.get("component_id") == component_id and b.get("status") == "CONFIRMED":
            return b
    return None


def _render_styles_qss(document: UIDocument) -> str:
    """Generate global stylesheet."""
    lines = [
        "/* Generated by UI Binder — PySide6 Widgets export. */",
        "QMainWindow, QWidget { background: #1e1e1e; color: #e0e0e0; }",
        "QFrame { border: 1px solid #3c3c3c; }",
        "QPushButton { background: #0e639c; color: white; border: none; padding: 6px 12px; border-radius: 2px; }",
        "QPushButton:hover { background: #1177bb; }",
        "QPushButton:disabled { opacity: 0.5; }",
        "QLineEdit, QPlainTextEdit { background: #2d2d2d; border: 1px solid #3c3c3c; padding: 4px; }",
        "QLabel { background: transparent; }",
    ]
    return "\n".join(lines) + "\n"


def _render_stroke_overlay(document: UIDocument) -> str:
    """Optional stroke overlay renderer."""
    if not document.strokes:
        return '"""Stroke overlay — no strokes in document."""\n'

    lines = [
        '"""Generated stroke overlay renderer."""',
        "from __future__ import annotations",
        "",
        "from PySide6.QtCore import QRectF",
        "from PySide6.QtWidgets import QWidget",
        "",
        "",
        "class StrokeOverlay(QWidget):",
        "    def __init__(self, strokes, parent=None):",
        "        super().__init__(parent)",
        "        self._strokes = strokes",
        "",
    ]
    return "\n".join(lines) + "\n"


def _render_capability_bridge(bindings: list[dict[str, Any]]) -> str:
    """Bridge for injecting real callbacks at runtime."""
    lines = [
        '"""Capability bridge — BINDING != IMPLEMENTATION.',
        '',
        'Widgets call bridge.register(capability_id, callback) to inject',
        'real business logic. The bridge does NOT guess implementation.',
        '"""',
        "from __future__ import annotations",
        "",
        "from typing import Any, Callable",
        "",
        "",
        "class CapabilityBridge:",
        "    def __init__(self) -> None:",
        "        self._handlers: dict[str, Callable] = {}",
        "",
        "    def register(self, capability_id: str, callback: Callable) -> None:",
        "        self._handlers[capability_id] = callback",
        "",
        "    def call(self, capability_id: str, data: dict[str, Any] | None = None) -> Any:",
        "        fn = self._handlers.get(capability_id)",
        "        if fn is None:",
        "            return None",
        "        return fn(data or {})",
        "",
        "    def has_handler(self, capability_id: str) -> bool:",
        "        return capability_id in self._handlers",
    ]
    return "\n".join(lines) + "\n"


def _render_binding_runtime(bindings: list[dict[str, Any]]) -> str:
    """Runtime binding mapper — maps UI events to bridge calls."""
    lines = [
        '"""Binding runtime — maps UI events to capability bridge calls."""',
        "from __future__ import annotations",
        "",
        "",
        "class BindingRuntime:",
        "    def __init__(self, bridge):",
        "        self.bridge = bridge",
        "",
        "    def wire(self, widget, capability_id, method='POST'):",
        "        from PySide6.QtWidgets import QPushButton",
        "        if isinstance(widget, QPushButton):",
        "            widget.clicked.connect(lambda: self.bridge.call(capability_id))",
    ]
    return "\n".join(lines) + "\n"


def _build_manifest(document: UIDocument, bindings: list[dict[str, Any]],
                    capabilities: list[dict[str, Any]],
                    tokens: dict[str, Any] | None,
                    layout: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "exporter": "pyside6-widgets",
        "exporter_version": "0.1.0",
        "source_ui_schema_version": document.ui_schema_version,
        "components_total": len(document.components),
        "components_native": sum(
            1 for c in document.components
            if c.type in PySide6WidgetsExporter._WIDGET_MAP
        ),
        "bindings_total": len(bindings),
        "bindings_confirmed": sum(1 for b in bindings if b.get("status") == "CONFIRMED"),
        "layout_fallbacks": [cid for cid, v in layout.get("components", {}).items()
                             if v.get("layout") == "leaf"],
        "unsupported": sorted({c.type for c in document.components} - set(PySide6WidgetsExporter._WIDGET_MAP)),
        "warnings": [],
    }


def _styles_to_qss(styles: dict[str, Any]) -> str:
    """Translate UI AST styles to QSS string."""
    parts = []
    if styles.get("background"):
        parts.append(f"background: {styles['background']};")
    if styles.get("color"):
        parts.append(f"color: {styles['color']};")
    if styles.get("fontSize"):
        parts.append(f"font-size: {styles['fontSize']};")
    if styles.get("fontWeight"):
        parts.append(f"font-weight: {styles['fontWeight']};")
    if styles.get("fontFamily"):
        parts.append(f"font-family: {styles['fontFamily']};")
    if styles.get("opacity") is not None:
        parts.append(f"opacity: {styles['opacity']};")
    if styles.get("radius"):
        parts.append(f"border-radius: {styles['radius']}px;")
    return " ".join(parts)


_REQUIREMENTS_TXT = """PySide6>=6.5
"""


# Register
register_exporter(PySide6WidgetsExporter)
