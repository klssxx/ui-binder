"""Tests for PySide6 project adapter — read-only detection without execution."""
from __future__ import annotations

import tempfile
from pathlib import Path

from adapters.pyside6_adapter import PySide6Adapter


def test_detects_pyside6_import():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "main.py").write_text(
            "from PySide6.QtWidgets import QApplication, QMainWindow\n"
            "from PySide6.QtCore import Signal\n"
            "app = QApplication([])\n"
            "win = QMainWindow()\n"
            "win.show()\n"
            "sys.exit(app.exec())\n",
            encoding="utf-8",
        )
        adapter = PySide6Adapter()
        assert adapter.detect(root) is True


def test_detects_pyside6_in_requirements():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "requirements.txt").write_text("PySide6>=6.5\npytest>=8\n", encoding="utf-8")
        adapter = PySide6Adapter()
        assert adapter.detect(root) is True


def test_detects_pyside6_in_pyproject():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "pyproject.toml").write_text(
            '[project]\nname = "test"\ndependencies = ["PySide6>=6.5"]\n',
            encoding="utf-8",
        )
        adapter = PySide6Adapter()
        assert adapter.detect(root) is True


def test_non_qt_project_not_detected():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "app.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")
        adapter = PySide6Adapter()
        assert adapter.detect(root) is False


def test_inspect_finds_widgets():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "main.py").write_text(
            "from PySide6.QtWidgets import QMainWindow, QPushButton, QLineEdit\n"
            "win = QMainWindow()\n"
            "btn = QPushButton()\n"
            "field = QLineEdit()\n",
            encoding="utf-8",
        )
        adapter = PySide6Adapter()
        info = adapter.inspect(root)
        assert info["components"] == 3
        assert "QMainWindow" in info["window_types"]


def test_capabilities_detect_signal_connections():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "main.py").write_text(
            "from PySide6.QtWidgets import QMainWindow, QPushButton\n"
            "win = QMainWindow()\n"
            "btn = QPushButton()\n"
            "btn.clicked.connect(self.on_click)\n",
            encoding="utf-8",
        )
        adapter = PySide6Adapter()
        caps = adapter.capabilities(root)
        assert len(caps) >= 1
        assert caps[0]["kind"] == "handler"
        assert "clicked" in caps[0].get("metadata", {}).get("signal", "")


def test_bindings_compat_lists_qt_events():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "main.py").write_text("import PySide6\n", encoding="utf-8")
        adapter = PySide6Adapter()
        compat = adapter.bindings_compat(root)
        assert "clicked" in compat["events"]
        assert "textChanged" in compat["events"]


def test_validate_flags_missing_app_entry():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "main.py").write_text(
            "from PySide6.QtWidgets import QMainWindow\n"
            "win = QMainWindow()\n",
            encoding="utf-8",
        )
        adapter = PySide6Adapter()
        problems = adapter.validate(root)
        assert any("entry point" in p.lower() or "QApplication" in p for p in problems)


def test_validate_passes_with_full_entry():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "main.py").write_text(
            "import sys\n"
            "from PySide6.QtWidgets import QApplication, QMainWindow\n"
            "app = QApplication(sys.argv)\n"
            "win = QMainWindow()\n"
            "sys.exit(app.exec())\n",
            encoding="utf-8",
        )
        adapter = PySide6Adapter()
        problems = adapter.validate(root)
        assert problems == []


def test_does_not_execute_project():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # File with dangerous code that would crash if executed
        (root / "main.py").write_text(
            "from PySide6.QtWidgets import QMainWindow\n"
            "import os; os.system('echo EXPLOITED')\n"  # Would be bad if executed
            "win = QMainWindow()\n",
            encoding="utf-8",
        )
        adapter = PySide6Adapter()
        # All operations must succeed without side-effects
        assert adapter.detect(root) is True
        adapter.capabilities(root)
        adapter.inspect(root)
        adapter.validate(root)
