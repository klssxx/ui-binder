"""Shared fixtures: isolated data dir per test, API client, sample paths."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from backend.api.app import create_app  # noqa: E402
from backend import config  # noqa: E402


@pytest.fixture()
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated UIBINDER_DATA_DIR per test; resets persistence init flags."""
    import backend.persistence.db as db_module
    import backend.api.common as common

    target = tmp_path / "uibinder-data"
    monkeypatch.setenv("UIBINDER_DATA_DIR", str(target))
    monkeypatch.setattr(db_module, "_initialized", False)
    common._store = None  # noqa: SLF001 — test isolation
    return target


@pytest.fixture()
def client(data_dir: Path) -> TestClient:
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def golden_png() -> Path:
    path = ROOT / "samples" / "golden-reference" / "reference.png"
    if not path.is_file():
        raise FileNotFoundError("Run scripts/make_golden.py first")
    return path


@pytest.fixture(scope="session")
def sample_app_dir() -> Path:
    path = ROOT / "samples" / "sample_app"
    assert (path / "backend" / "app.py").is_file()
    return path


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return ROOT


def read_json(path: Path):
    import json
    return json.loads(path.read_text(encoding="utf-8"))
