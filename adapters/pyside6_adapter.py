"""PySide6 project adapter — read-only detection of Qt Widgets projects."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from adapters.base import Adapter
from backend import config


class PySide6Adapter(Adapter):
    name = "pyside6"

    _WIDGET_RE = re.compile(r"\b(QMainWindow|QWidget|QDialog|QFrame|QLabel|QPushButton|QLineEdit|QTextEdit|QPlainTextEdit|QComboBox|QCheckBox|QRadioButton|QTableView|QTableWidget|QTabWidget|QScrollArea|QSplitter)\s*\(")
    _SIGNAL_RE = re.compile(r"\.(\w+)\.connect\(")
    _CONNECT_TARGET_RE = re.compile(r"\.connect\(([^)]+)\)")

    def detect(self, path: Path) -> bool:
        if not path.is_dir():
            return False
        for marker in ("requirements.txt", "pyproject.toml", "setup.py", "setup.cfg"):
            f = path / marker
            if f.is_file():
                try:
                    text = f.read_text(encoding="utf-8", errors="replace").lower()
                    if any(pkg in text for pkg in ("pyside6", "pyqt6", "pyside2", "pyqt5")):
                        return True
                except OSError:
                    continue
        count = 0
        for p in path.rglob("*.py"):
            if count > 100:
                break
            if any(ignored in p.parts for ignored in config.SCAN_IGNORED_DIRS):
                continue
            try:
                head = p.read_text(encoding="utf-8", errors="replace")[:3000]
            except OSError:
                continue
            if "from PySide6" in head or "import PySide6" in head:
                return True
            if "from PyQt6" in head or "import PyQt6" in head:
                return True
            count += 1
        return False

    def inspect(self, path: Path) -> dict[str, Any]:
        widgets = self._find_widgets(path)
        return {
            "adapter": self.name,
            "window_types": sorted({w["type"] for w in widgets}),
            "components": len(widgets),
        }

    def capabilities(self, path: Path) -> list[dict[str, Any]]:
        caps = []
        for p in sorted(path.rglob("*.py"))[:200]:
            if any(ignored in p.parts for ignored in config.SCAN_IGNORED_DIRS):
                continue
            try:
                source = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = p.relative_to(path).as_posix()
            for line_no, line in enumerate(source.splitlines(), 1):
                stripped = line.strip()
                if ".connect(" in stripped:
                    signal = self._extract_signal(stripped)
                    handler = self._extract_connect_target(stripped)
                    if signal and handler:
                        caps.append({
                            "capability_id": f"cap_signal_{rel}_{line_no}",
                            "kind": "handler",
                            "name": handler,
                            "qualified_name": f"{rel}::{handler}",
                            "description": f"{signal} -> {handler}",
                            "inputs": [], "outputs": [], "side_effects": [],
                            "origin_file": rel, "origin_line": line_no,
                            "framework": "pyside6",
                            "http_method": "", "http_path": "",
                            "dependencies": [], "legacy": False,
                            "confidence": 0.7,
                            "metadata": {"signal": signal},
                        })
        return caps

    def bindings_compat(self, path: Path) -> dict[str, Any]:
        return {
            "adapter": self.name,
            "events": ["clicked", "toggled", "textChanged", "currentIndexChanged",
                       "editingFinished", "returnPressed", "selectionChanged",
                       "valueChanged", "activated"],
            "state": ["property", "settings"],
            "call_style": "Qt signal/slot connection",
        }

    def validate(self, path: Path) -> list[str]:
        problems = []
        has_main = False
        for p in path.rglob("*.py"):
            if any(ignored in p.parts for ignored in config.SCAN_IGNORED_DIRS):
                continue
            try:
                source = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "QApplication" in source and ("app.exec()" in source or "app.exec_()" in source):
                has_main = True
                break
        if not has_main:
            problems.append("No QApplication entry point found.")
        return problems

    def _find_widgets(self, path: Path) -> list[dict[str, Any]]:
        widgets = []
        for p in sorted(path.rglob("*.py"))[:100]:
            if any(ignored in p.parts for ignored in config.SCAN_IGNORED_DIRS):
                continue
            try:
                source = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = p.relative_to(path).as_posix()
            for match in self._WIDGET_RE.finditer(source):
                wtype = match.group(1)
                line_no = source[:match.start()].count("\n") + 1
                widgets.append({"type": wtype, "file": rel, "line": line_no})
        return widgets

    def _extract_signal(self, line: str) -> str | None:
        m = self._SIGNAL_RE.search(line)
        return m.group(1) if m else None

    def _extract_connect_target(self, line: str) -> str | None:
        m = self._CONNECT_TARGET_RE.search(line)
        if not m:
            return None
        target = m.group(1).strip()
        if target.startswith("self."):
            target = target[5:]
        if "lambda" in target:
            return "<lambda>"
        return target.split(",")[0].strip().strip("'\"")
