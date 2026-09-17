"""Security regression tests: export safety, path traversal, secret redaction."""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.logging_setup import _redact
from backend.security.paths import is_safe_export_target, is_safe_project_path


# P0 — export must refuse system dirs (path traversal / data corruption)
@pytest.mark.parametrize(
    "forbidden",
    ["c:\\windows\\temp\\exp", "c:\\program files\\x", "c:\\programdata\\y"],
)
def test_export_refuses_system_dirs(tmp_path, forbidden):
    ok, _ = is_safe_export_target(Path(forbidden), None)
    assert ok is False


def test_export_refuses_drive_root():
    ok, msg = is_safe_export_target(Path("C:/"), None)
    assert ok is False
    assert "raíz" in msg


def test_export_allows_normal_target(tmp_path):
    ok, _ = is_safe_export_target(tmp_path / "fresh", None)
    assert ok is True


# Import must refuse system dirs (defense-in-depth)
@pytest.mark.parametrize(
    "forbidden",
    ["c:\\windows", "c:\\program files", "c:\\programdata"],
)
def test_import_refuses_system_dirs(forbidden):
    ok, _ = is_safe_project_path(forbidden)
    assert ok is False


def test_import_refuses_drive_root():
    ok, _ = is_safe_project_path("C:\\")
    assert ok is False


# Secret redaction must not leak API keys / bearer tokens into logs
def test_secret_redaction_dict():
    cleaned = _redact({"api_key": "sk-abcdef123456", "note": "ok"})
    assert cleaned["api_key"] == "[REDACTED]"
    assert cleaned["note"] == "ok"


def test_secret_redaction_bearer_string():
    cleaned = _redact("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.x.y")
    assert "Bearer" not in cleaned
    assert "[REDACTED]" in cleaned


def test_secret_redaction_non_string_values_pass_through():
    cleaned = _redact({"count": 3, "flag": True, "name": "uibinder"})
    assert cleaned == {"count": 3, "flag": True, "name": "uibinder"}
