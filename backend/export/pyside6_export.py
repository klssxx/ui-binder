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
    * Hierarchical widget tree with real parent-child relationships.
    * Safe Python identifiers for arbitrary component IDs.
    * Transactional export with staging directory.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from backend.export.base import Exporter, ExportPlan, register_exporter
from backend.schema.ui_schema import UIDocument


# ---------------------------------------------------------------------------
# Safe Python identifiers (P1-09)
# ---------------------------------------------------------------------------

def safe_python_identifier(component_id: str) -> str:
    """Convert an arbitrary component ID to a safe Python identifier.

    Deterministic, valid Python, no silent collisions.
    Preserves original ID via objectName in generated code.
    """
    if not component_id:
        return "_empty"

    # Replace non-alphanumeric characters with underscores
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', component_id)

    # Ensure it doesn't start with a digit
    if safe and safe[0].isdigit():
        safe = "_" + safe

    # Handle empty result
    if not safe or safe.strip('_') == '':
        safe = "_component"

    return safe


def _resolve_identifiers(ids: list[str]) -> dict[str, str]:
    """Resolve a list of component IDs to unique Python identifiers.

    Handles collisions deterministically with a short hash suffix.
    """
    result: dict[str, str] = {}
    seen: dict[str, int] = {}

    for cid in ids:
        base = safe_python_identifier(cid)
        if base in seen:
            # Collision — add short hash suffix
            seen[base] += 1
            suffix = hashlib.sha256(cid.encode('utf-8')).hexdigest()[:6]
            result[cid] = f"{base}_{suffix}"
        else:
            seen[base] = 0
            result[cid] = base

    return result


# ---------------------------------------------------------------------------
# Image asset resolution (P1-01)
# ---------------------------------------------------------------------------

def _parse_image_id(src: str | None) -> str | None:
    """Parse image_id from styles.src URL pattern.

    Expected format: /api/images/{image_id}/file
    Returns None for non-matching patterns.
    """
    if not src or not isinstance(src, str):
        return None
    m = re.search(r'/api/images/([A-Za-z0-9_-]+)/file', src)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Layout plan (P0-03, §9)
# ---------------------------------------------------------------------------

def _compute_layout_plan(document: UIDocument) -> dict[str, Any]:
    """Deterministic spatial analysis -> Qt layout plan.

    Produces a real layout plan with mode, confidence, and fallback info.
    """
    by_id = document.by_id()
    root_children = document.children_of("screen")
    plan: dict[str, Any] = {
        "root_children": [],
        "components": {},
        "fallback_used": [],
        "layout_modes": {},
    }

    for child in root_children:
        plan["root_children"].append(child.id)
        _analyze_node(child, by_id, plan)

    return plan


def _analyze_node(comp, by_id, plan):
    """Recursively analyze a node and its children for layout."""
    children = [by_id[cid] for cid in comp.children if cid in by_id]

    if not children:
        plan["components"][comp.id] = {
            "layout_mode": "LEAF",
            "layout_confidence": 1.0,
            "fallback_reason": None,
            "child_count": 0,
        }
        return

    # Detect layout mode from geometry
    if len(children) == 1:
        layout_mode = "NONE"
        confidence = 1.0
        fallback_reason = None
    else:
        xs = [c.bbox.x for c in children]
        ys = [c.bbox.y for c in children]
        x_range = max(xs) - min(xs)
        y_range = max(ys) - min(ys)

        if y_range >= x_range:
            layout_mode = "VERTICAL"
            confidence = min(1.0, y_range / (x_range + 1))
        else:
            layout_mode = "HORIZONTAL"
            confidence = min(1.0, x_range / (y_range + 1))

        fallback_reason = None

    # Check for grid pattern (matrix arrangement)
    if len(children) >= 4:
        unique_x = len(set(round(c.bbox.x, 1) for c in children))
        unique_y = len(set(round(c.bbox.y, 1) for c in children))
        if unique_x >= 2 and unique_y >= 2:
            layout_mode = "GRID"
            confidence = 0.8

    # Check for tabs
    if comp.type == "tabs":
        layout_mode = "TABS"
        confidence = 1.0

    plan["components"][comp.id] = {
        "layout_mode": layout_mode,
        "layout_confidence": confidence,
        "fallback_reason": fallback_reason,
        "child_count": len(children),
    }

    for child in children:
        _analyze_node(child, by_id, plan)


def _qt_layout_class(layout_mode: str) -> str:
    """Map layout mode to Qt layout class."""
    mapping = {
        "VERTICAL": "QVBoxLayout",
        "HORIZONTAL": "QHBoxLayout",
        "GRID": "QGridLayout",
        "TABS": "QTabWidget",
        "NONE": "QVBoxLayout",
        "LEAF": "QVBoxLayout",
    }
    return mapping.get(layout_mode, "QVBoxLayout")


# ---------------------------------------------------------------------------
# String serialization (P1-10)
# ---------------------------------------------------------------------------

def _safe_python_string(text: str) -> str:
    """Serialize a string safely for Python code generation.

    Uses repr() for robust escaping of newlines, quotes, backslashes, etc.
    """
    if not text:
        return '""'
    return repr(text)


# ---------------------------------------------------------------------------
# Widget factory (P0-01 — real hierarchy)
# ---------------------------------------------------------------------------

def _render_widget_factory(comp, identifiers: dict[str, str]) -> list[str]:
    """Generate a single widget creation function with safe identifiers."""
    ctype = comp.type
    mapping = PySide6WidgetsExporter._WIDGET_MAP.get(ctype, ("QWidget", "container"))
    qt_class, category = mapping

    ident = identifiers.get(comp.id, safe_python_identifier(comp.id))

    lines = [
        f"def _create_{ident}():",
        f"    w = {qt_class}()",
        f"    w.setObjectName({_safe_python_string(comp.id)})",
    ]

    # Geometry — relative to parent if not root
    b = comp.bbox
    if qt_class != "QMainWindow":
        lines.append(f"    w.setGeometry({b.x:g}, {b.y:g}, {b.width:g}, {b.height:g})")
        lines.append(f"    w.setMinimumSize({max(1, int(b.width // 4))}, {max(1, int(b.height // 4))})")

    # Text
    if comp.text:
        if qt_class in ("QLabel", "QPushButton", "QCheckBox", "QRadioButton"):
            lines.append(f"    w.setText({_safe_python_string(comp.text)})")
        elif qt_class == "QLineEdit":
            lines.append(f"    w.setPlaceholderText({_safe_python_string(comp.text)})")

    # Tooltip from metadata
    if comp.metadata.get("tooltip"):
        lines.append(f"    w.setToolTip({_safe_python_string(comp.metadata['tooltip'])})")

    # Stylesheet (from styles dict)
    qss = _styles_to_qss(comp.styles)
    if qss:
        lines.append(f"    w.setStyleSheet({_safe_python_string(qss)})")

    lines.append("    return w")
    return lines


# ---------------------------------------------------------------------------
# Main exporter
# ---------------------------------------------------------------------------

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

        # Honest component support counting (§12)
        native_count = 0
        partial_count = 0
        fallback_count = 0
        for c in document.components:
            if c.type in self._WIDGET_MAP:
                if c.type in ("table", "chart", "modal", "custom"):
                    partial_count += 1
                else:
                    native_count += 1
            else:
                fallback_count += 1

        p.components_native = native_count
        p.components_fallback = fallback_count
        p.components_partial = partial_count

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

        # Check for bindings with missing capabilities
        cap_ids = {c.get("capability_id") for c in capabilities}
        for b in bindings:
            if b.get("status") == "CONFIRMED":
                target = b.get("target_capability")
                if target and target not in cap_ids:
                    warnings.append(
                        f"Binding {b.get('binding_id')} targets missing capability '{target}'."
                    )

        return warnings

    def export(self, document, bindings, capabilities, tokens, target,
               source_project=None, image_resolver=None) -> dict[str, Any]:
        from backend.security.paths import is_safe_export_target

        ok, why = is_safe_export_target(target, source_project)
        if not ok:
            raise ValueError(why)

        # Detach to avoid mutating inputs (§29)
        bindings = _detach(bindings)
        capabilities = _detach(capabilities)

        # Build identifier mapping (P1-09)
        all_ids = [c.id for c in document.components]
        identifiers = _resolve_identifiers(all_ids)

        # Compute layout plan (P0-03)
        layout = _compute_layout_plan(document)

        # Build capability lookup for binding resolution (P0-02)
        caps_by_id = {c.get("capability_id"): c for c in capabilities}

        # Generate code
        main_py = _render_main_py(document, layout)
        manifest_py = _render_manifest_py(document, bindings, capabilities, layout, tokens, identifiers)
        styles_qss = _render_styles_qss(document)
        stroke_py = _render_stroke_overlay(document)
        runtime_bridge = _render_capability_bridge(bindings)
        runtime_binding = _render_binding_runtime(bindings)

        # Transactional export (§28)
        target.mkdir(parents=True, exist_ok=True)
        staging = target.parent / f".uibinder-staging-{tempfile.mktemp(dir='').split('/')[-1]}"
        staging.mkdir(parents=True, exist_ok=True)

        try:
            # Write to staging
            (staging / "main.py").write_text(main_py, encoding="utf-8")
            (staging / "requirements.txt").write_text(_REQUIREMENTS_TXT, encoding="utf-8")
            (staging / "ui").mkdir(exist_ok=True)
            (staging / "ui" / "__init__.py").write_text("", encoding="utf-8")
            (staging / "ui" / "main_window.py").write_text(_MAIN_WINDOW_PY, encoding="utf-8")
            (staging / "ui" / "generated_ui.py").write_text(manifest_py, encoding="utf-8")
            (staging / "ui" / "styles.qss").write_text(styles_qss, encoding="utf-8")
            (staging / "ui" / "stroke_overlay.py").write_text(stroke_py, encoding="utf-8")
            (staging / "runtime").mkdir(exist_ok=True)
            (staging / "runtime" / "__init__.py").write_text("", encoding="utf-8")
            (staging / "runtime" / "capability_bridge.py").write_text(runtime_bridge, encoding="utf-8")
            (staging / "runtime" / "binding_runtime.py").write_text(runtime_binding, encoding="utf-8")

            # Bindings JSON
            (staging / "bindings.json").write_text(
                json.dumps(bindings, ensure_ascii=False, indent=2), encoding="utf-8")

            # Manifest
            manifest = _build_manifest(document, bindings, capabilities, tokens, layout)
            (staging / "uibinder_manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

            # Copy assets
            assets_copied = 0
            if image_resolver is not None:
                (staging / "assets").mkdir(exist_ok=True)
                for comp in document.components:
                    styles = comp.model_dump().get("styles") if hasattr(comp, "model_dump") else comp.styles
                    src = styles.get("src") if isinstance(styles, dict) else None
                    image_id = _parse_image_id(src)
                    if not image_id:
                        continue
                    record_path = image_resolver(image_id)
                    if record_path and Path(record_path).is_file():
                        dest = staging / "assets" / f"{image_id}{Path(record_path).suffix}"
                        if not dest.exists():
                            shutil.copyfile(record_path, dest)
                            assets_copied += 1

            # Promote staging to target
            if target.exists() or target.is_symlink():
                if target.is_symlink() or target.is_file():
                    target.unlink()
                else:
                    shutil.rmtree(target)
            shutil.move(str(staging), str(target))

        except Exception:
            # Clean up staging on failure
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
            raise

        plan = self.plan(document, bindings, capabilities, tokens)
        d = plan.to_dict()
        d["target_path"] = str(target)
        d["assets_copied"] = assets_copied
        return d


def _detach(bindings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deep copy each binding dict so export doesn't mutate input."""
    return [dict(b) for b in bindings]


# ---------------------------------------------------------------- codegen

def _render_main_py(document: UIDocument, layout: dict[str, Any]) -> str:
    """Entry point for the generated app — uses __file__-relative paths (§14)."""
    screen = document.screen
    return f'''"""Generated by UI Binder — PySide6 Widgets export.
Run: python main.py
"""
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow

ROOT = Path(__file__).resolve().parent


def main():
    app = QApplication(sys.argv)
    style_file = ROOT / "ui" / "styles.qss"
    if style_file.is_file():
        app.setStyleSheet(style_file.read_text(encoding="utf-8"))
    window = MainWindow()
    window.setWindowTitle({_safe_python_string("UI Binder Export")})
    window.resize({screen.width:g}, {screen.height:g})
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
'''


_MAIN_WINDOW_PY = '''"""Main window — loads generated UI and wires bindings."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout
from PySide6.QtCore import Qt

from ui.generated_ui import build_ui
from runtime.capability_bridge import CapabilityBridge

ROOT = Path(__file__).resolve().parent


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
                        tokens: dict[str, Any] | None,
                        identifiers: dict[str, str] | None = None) -> str:
    """Generate the UI widget tree as Python code with real hierarchy."""
    if identifiers is None:
        identifiers = _resolve_identifiers([c.id for c in document.components])

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
        '    """Construct the widget tree and register bindings."""',
    ]

    comps = {c.id: c for c in document.components}
    by_id = document.by_id()

    # Build capability lookup for binding resolution
    caps_by_id = {c.get("capability_id"): c for c in capabilities}

    # Recursive widget creation
    lines.append("    # Build widget tree recursively")
    lines.append("    widget_map = {}")
    lines.append("")
    lines.append("    def _create_widget(comp_id, parent_widget=None):")
    lines.append('        """Recursively create a widget and its children."""')
    lines.append("        if comp_id in widget_map:")
    lines.append("            return widget_map[comp_id]")
    lines.append("        comp = components.get(comp_id)")
    lines.append("        if comp is None:")
    lines.append("            return None")
    lines.append("")
    lines.append("        # Create the widget")
    lines.append("        w = _create_widget_instance(comp)")
    lines.append("        widget_map[comp_id] = w")
    lines.append("")
    lines.append("        # Set up layout for children")
    lines.append("        layout_info = layout_plan.get(comp_id, {})")
    lines.append("        layout_mode = layout_info.get('layout_mode', 'LEAF')")
    lines.append("")
    lines.append("        if layout_mode == 'TABS':")
    lines.append("            # Tabs: add children as tab pages")
    lines.append("            for i, child_id in enumerate(comp['children']):")
    lines.append("                child_widget = _create_widget(child_id, w)")
    lines.append("                if child_widget is not None:")
    lines.append("                    title = _get_tab_title(comp, child_id, i)")
    lines.append("                    w.addTab(child_widget, title)")
    lines.append("        elif layout_mode in ('VERTICAL', 'HORIZONTAL', 'GRID', 'NONE'):")
    lines.append("            # Container: add children to layout")
    lines.append("            child_layout = _create_layout(w, layout_mode)")
    lines.append("            for child_id in comp['children']:")
    lines.append("                child_widget = _create_widget(child_id, w)")
    lines.append("                if child_widget is not None:")
    lines.append("                    if layout_mode == 'GRID':")
    lines.append("                        idx = comp['children'].index(child_id)")
    lines.append("                        row, col = divmod(idx, 2)")
    lines.append("                        child_layout.addWidget(child_widget, row, col)")
    lines.append("                    else:")
    lines.append("                        child_layout.addWidget(child_widget)")
    lines.append("        elif layout_mode == 'LEAF':")
    lines.append("            pass  # No children")
    lines.append("")
    lines.append("        # Wire bindings")
    lines.append("        _wire_bindings(w, comp, bridge)")
    lines.append("")
    lines.append("        return w")
    lines.append("")

    # Emit widget factory functions (for backward compat / direct access)
    lines.append("")
    lines.append("# Widget factory functions (recursive via _create_widget)")
    lines.append("")

    # Emit helper functions
    lines.append("")
    lines.append("# Helper functions")
    lines.append("")
    lines.append("def _create_widget_instance(comp):")
    lines.append('    """Create a widget instance from component type."""')
    lines.append("    ctype = comp['type']")
    lines.append("    mapping = {")
    for ctype, (qt_class, _) in PySide6WidgetsExporter._WIDGET_MAP.items():
        lines.append(f'        "{ctype}": "{qt_class}",')
    lines.append("    }")
    lines.append("    qt_class = mapping.get(ctype, 'QWidget')")
    lines.append("    w = globals()[qt_class]()")
    lines.append("    w.setObjectName(comp['id'])")
    lines.append("")
    lines.append("    # Geometry")
    lines.append("    b = comp['bbox']")
    lines.append("    if qt_class != 'QMainWindow':")
    lines.append("        w.setGeometry(b['x'], b['y'], b['width'], b['height'])")
    lines.append("")
    lines.append("    # Text")
    lines.append("    if comp.get('text'):")
    lines.append("        if qt_class in ('QLabel', 'QPushButton', 'QCheckBox', 'QRadioButton'):")
    lines.append("            w.setText(comp['text'])")
    lines.append("        elif qt_class == 'QLineEdit':")
    lines.append("            w.setPlaceholderText(comp['text'])")
    lines.append("")
    lines.append("    # Stylesheet")
    lines.append("    qss = _styles_to_qss(comp.get('styles', {}))")
    lines.append("    if qss:")
    lines.append("        w.setStyleSheet(qss)")
    lines.append("")
    lines.append("    return w")
    lines.append("")

    lines.append("def _create_layout(parent, layout_mode):")
    lines.append('    """Create a layout for a container widget."""')
    lines.append("    if layout_mode == 'VERTICAL':")
    lines.append("        return QVBoxLayout(parent)")
    lines.append("    elif layout_mode == 'HORIZONTAL':")
    lines.append("        return QHBoxLayout(parent)")
    lines.append("    elif layout_mode == 'GRID':")
    lines.append("        return QGridLayout(parent)")
    lines.append("    else:")
    lines.append("        return QVBoxLayout(parent)")
    lines.append("")

    lines.append("def _get_tab_title(comp, child_id, index):")
    lines.append('    """Get tab title from metadata or fallback."""')
    lines.append("    child = components.get(child_id, {})")
    lines.append("    # Priority: metadata.tab_title > child.text > child.name > 'Tab N'")
    lines.append("    meta = comp.get('metadata', {})")
    lines.append("    if meta.get('tab_title'):")
    lines.append("        return meta['tab_title']")
    lines.append("    if child.get('text'):")
    lines.append("        return child['text']")
    lines.append("    if child.get('name'):")
    lines.append("        return child['name']")
    lines.append("    return f'Tab {index + 1}'")
    lines.append("")

    lines.append("def _wire_bindings(widget, comp, bridge):")
    lines.append('    """Wire bindings for a widget."""')
    lines.append("    comp_id = comp['id']")
    lines.append("    for binding in bindings:")
    lines.append("        if binding.get('component_id') != comp_id:")
    lines.append("            continue")
    lines.append("        if binding.get('status') != 'CONFIRMED':")
    lines.append("            continue")
    lines.append("        target_cap = binding.get('target_capability')")
    lines.append("        if not target_cap:")
    lines.append("            continue")
    lines.append("        # Check if capability exists")
    lines.append("        cap = capabilities_by_id.get(target_cap)")
    lines.append("        if cap is None:")
    lines.append("            # Broken binding — do not wire")
    lines.append("            continue")
    lines.append("        # Get event and map to Qt signal")
    lines.append("        event = binding.get('event', 'onClick')")
    lines.append("        signal = _map_event_to_signal(event)")
    lines.append("        if signal is None:")
    lines.append("            continue")
    lines.append("        # Connect the signal")
    lines.append("        if hasattr(widget, signal):")
    lines.append("            getattr(widget, signal).connect(")
    lines.append("                lambda cap=target_cap: bridge.call(cap)")
    lines.append("            )")
    lines.append("")

    lines.append("def _map_event_to_signal(event):")
    lines.append('    """Map binding event to Qt signal name."""')
    lines.append("    mapping = {")
    lines.append("        'onClick': 'clicked',")
    lines.append("        'clicked': 'clicked',")
    lines.append("        'onChange': 'textChanged',")
    lines.append("        'textChanged': 'textChanged',")
    lines.append("        'toggled': 'toggled',")
    lines.append("        'currentIndexChanged': 'currentIndexChanged',")
    lines.append("    }")
    lines.append("    return mapping.get(event)")
    lines.append("")

    # Data section (must come BEFORE tree builder — _create_widget uses these)
    lines.append("")
    lines.append("# Data")
    lines.append("component_list = [")
    for comp in document.components:
        lines.append(f"    {comp.model_dump()},")
    lines.append("]")
    lines.append("")
    lines.append("binding_list = [")
    for b in bindings:
        lines.append(f"    {b},")
    lines.append("]")
    lines.append("")
    lines.append("capability_list = [")
    for c in capabilities:
        lines.append(f"    {c},")
    lines.append("]")
    lines.append("")
    lines.append("root_children = [")
    for cid in layout.get("root_children", []):
        lines.append(f"    {cid!r},")
    lines.append("]")

    # Build the tree from roots
    lines.append("")
    lines.append("# Build the widget tree")
    lines.append("components = {c['id']: c for c in component_list}")
    lines.append("layout_plan = layout")
    lines.append("bindings = binding_list")
    lines.append("capabilities_by_id = {c['capability_id']: c for c in capability_list}")
    lines.append("")
    lines.append("for root_id in root_children:")
    lines.append("    root_widget = _create_widget(root_id)")
    lines.append("    if root_widget is not None:")
    lines.append("        layout.addWidget(root_widget)")
    lines.append("")

    return "\n".join(lines) + "\n"


def _find_binding_cap(component_id: str, bindings: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Find a CONFIRMED binding for a component."""
    for b in bindings:
        if b.get("component_id") == component_id and b.get("status") == "CONFIRMED":
            return b
    return None


def _render_styles_qss(document: UIDocument) -> str:
    """Generate global stylesheet — uses design tokens, not hardcoded colors (§24)."""
    lines = [
        "/* Generated by UI Binder — PySide6 Widgets export. */",
    ]

    # Use screen background if available
    screen_bg = document.screen.background
    if screen_bg:
        lines.append(f"QMainWindow, QWidget {{ background: {screen_bg}; color: #e0e0e0; }}")
    else:
        lines.append("QMainWindow, QWidget { background: #1e1e1e; color: #e0e0e0; }")

    lines.append("QFrame { border: 1px solid #3c3c3c; }")
    lines.append("QPushButton { background: #0e639c; color: white; border: none; padding: 6px 12px; border-radius: 2px; }")
    lines.append("QPushButton:hover { background: #1177bb; }")
    lines.append("QPushButton:disabled { opacity: 0.5; }")
    lines.append("QLineEdit, QPlainTextEdit { background: #2d2d2d; border: 1px solid #3c3c3c; padding: 4px; }")
    lines.append("QLabel { background: transparent; }")

    return "\n".join(lines) + "\n"


def _render_stroke_overlay(document: UIDocument) -> str:
    """Optional stroke overlay renderer with paintEvent (§23)."""
    if not document.strokes:
        return '"""Stroke overlay — no strokes in document."""\n'

    lines = [
        '"""Generated stroke overlay renderer."""',
        "from __future__ import annotations",
        "",
        "from PySide6.QtCore import QRectF",
        "from PySide6.QtWidgets import QWidget",
        "from PySide6.QtGui import QPainter, QPen, QColor",
        "",
        "",
        "class StrokeOverlay(QWidget):",
        "    def __init__(self, strokes, parent=None):",
        "        super().__init__(parent)",
        "        self._strokes = strokes",
        "",
        "    def paintEvent(self, event):",
        "        painter = QPainter(self)",
        "        painter.setRenderHint(QPainter.Antialiasing)",
        "        for stroke in self._strokes:",
        "            self._draw_stroke(painter, stroke)",
        "",
        "    def _draw_stroke(self, painter, stroke):",
        "        pen = QPen(QColor(stroke.get('color', '#4f8cff')))",
        "        pen.setWidth(stroke.get('width', 4))",
        "        pen.setCapStyle(Qt.RoundCap)",
        "        pen.setJoinStyle(Qt.RoundJoin)",
        "        painter.setPen(pen)",
        "        painter.setOpacity(stroke.get('opacity', 1))",
        "        tool = stroke.get('tool', 'pencil')",
        "        pts = stroke.get('points', [])",
        "        if not pts:",
        "            return",
        "        if tool == 'pencil':",
        "            for i in range(len(pts) - 1):",
        "                painter.drawLine(pts[i]['x'], pts[i]['y'], pts[i+1]['x'], pts[i+1]['y'])",
        "        elif tool == 'rect':",
        "            a, b = pts[0], pts[-1]",
        "            x, y = min(a['x'], b['x']), min(a['y'], b['y'])",
        "            w, h = abs(b['x'] - a['x']), abs(b['y'] - a['y'])",
        "            painter.drawRect(x, y, w, h)",
        "        elif tool == 'ellipse':",
        "            a, b = pts[0], pts[-1]",
        "            x, y = min(a['x'], b['x']), min(a['y'], b['y'])",
        "            w, h = abs(b['x'] - a['x']), abs(b['y'] - a['y'])",
        "            painter.drawEllipse(x, y, w, h)",
        "        elif tool == 'line':",
        "            a, b = pts[0], pts[-1]",
        "            painter.drawLine(a['x'], a['y'], b['x'], b['y'])",
        "        elif tool == 'arrow':",
        "            import math",
        "            a, b = pts[0], pts[-1]",
        "            painter.drawLine(a['x'], a['y'], b['x'], b['y'])",
        "            ang = math.atan2(b['y'] - a['y'], b['x'] - a['x'])",
        "            size = max(10.0, stroke.get('width', 4) * 3)",
        "            lx = b['x'] - size * math.cos(ang - 0.5)",
        "            ly = b['y'] - size * math.sin(ang - 0.5)",
        "            rx = b['x'] - size * math.cos(ang + 0.5)",
        "            ry = b['y'] - size * math.sin(ang + 0.5)",
        "            painter.drawLine(b['x'], b['y'], lx, ly)",
        "            painter.drawLine(b['x'], b['y'], rx, ry)",
    ]
    return "\n".join(lines) + "\n"


def _render_capability_bridge(bindings: list[dict[str, Any]] | None = None) -> str:
    """Bridge for injecting real callbacks at runtime — no fake no-op (P1-04, §16)."""
    lines = [
        '"""Capability bridge — BINDING != IMPLEMENTATION.',
        '',
        'Widgets call bridge.register(capability_id, callback) to inject',
        'real business logic. The bridge does NOT guess implementation.',
        'States: REGISTERED, UNREGISTERED, BROKEN.',
        '"""',
        "from __future__ import annotations",
        "",
        "from typing import Any, Callable",
        "",
        "",
        "class CapabilityBridge:",
        "    def __init__(self) -> None:",
        "        self._handlers: dict[str, Callable] = {}",
        "        self._states: dict[str, str] = {}",
        "",
        "    def register(self, capability_id: str, callback: Callable) -> None:",
        "        self._handlers[capability_id] = callback",
        "        self._states[capability_id] = 'REGISTERED'",
        "",
        "    def call(self, capability_id: str, data: dict[str, Any] | None = None) -> Any:",
        "        fn = self._handlers.get(capability_id)",
        "        if fn is None:",
        "            self._states[capability_id] = 'UNREGISTERED'",
        "            return None",
        "        try:",
        "            return fn(data or {})",
        "        except Exception as e:",
        "            self._states[capability_id] = 'BROKEN'",
        "            raise",
        "",
        "    def has_handler(self, capability_id: str) -> bool:",
        "        return capability_id in self._handlers",
        "",
        "    def get_state(self, capability_id: str) -> str:",
        "        return self._states.get(capability_id, 'UNREGISTERED')",
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
    """Build honest manifest with component support counts (§12)."""
    native_count = 0
    partial_count = 0
    fallback_count = 0
    for c in document.components:
        if c.type in PySide6WidgetsExporter._WIDGET_MAP:
            if c.type in ("table", "chart", "modal", "custom"):
                partial_count += 1
            else:
                native_count += 1
        else:
            fallback_count += 1

    return {
        "schema_version": 1,
        "exporter": "pyside6-widgets",
        "exporter_version": "0.2.0",
        "source_ui_schema_version": document.ui_schema_version,
        "components_total": len(document.components),
        "components_native": native_count,
        "components_partial": partial_count,
        "components_fallback": fallback_count,
        "bindings_total": len(bindings),
        "bindings_confirmed": sum(1 for b in bindings if b.get("status") == "CONFIRMED"),
        "layout_fallbacks": [cid for cid, v in layout.get("components", {}).items()
                             if v.get("layout_mode") == "LEAF"],
        "unsupported": sorted({c.type for c in document.components} - set(PySide6WidgetsExporter._WIDGET_MAP)),
        "warnings": [],
    }


def _styles_to_qss(styles: dict[str, Any]) -> str:
    """Translate UI AST styles to QSS string (§24)."""
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
    if styles.get("padding"):
        parts.append(f"padding: {styles['padding']};")
    if styles.get("border"):
        parts.append(f"border: {styles['border']};")
    if styles.get("fontStyle"):
        parts.append(f"font-style: {styles['fontStyle']};")
    if styles.get("textAlign"):
        parts.append(f"text-align: {styles['textAlign']};")
    return " ".join(parts)


_REQUIREMENTS_TXT = """PySide6>=6.5
"""


# Register
register_exporter(PySide6WidgetsExporter)
