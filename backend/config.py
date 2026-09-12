"""Central configuration: data root resolution and tunables.

Data root precedence:
1. UIBINDER_DATA_DIR env var (dev override, e.g. repo ./data)
2. %LOCALAPPDATA%/UIBinder (production default — never next to the exe)
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Minimal .env loader (no external dependency). Never overrides real env."""
    env_file = REPO_ROOT / ".env"
    if not env_file.is_file():
        return
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass


_load_dotenv()


def get_data_root() -> Path:
    override = os.environ.get("UIBINDER_DATA_DIR", "").strip()
    if override:
        root = Path(override)
    else:
        local_app = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        root = Path(local_app) / "UIBinder"
    root.mkdir(parents=True, exist_ok=True)
    return root


def workspaces_root() -> Path:
    p = get_data_root() / "workspaces"
    p.mkdir(parents=True, exist_ok=True)
    return p


def logs_root() -> Path:
    p = get_data_root() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def db_path() -> Path:
    return get_data_root() / "uibinder.db"


HOST = os.environ.get("UIBINDER_HOST", "127.0.0.1")
PORT = int(os.environ.get("UIBINDER_PORT", "8765"))

# Vision provider selection: "heuristic" (default, local), "remote" (needs env config).
VISION_PROVIDER = os.environ.get("UIBINDER_VISION_PROVIDER", "heuristic")
VISION_BASE_URL = os.environ.get("UIBINDER_VISION_BASE_URL", "").strip()
VISION_MODEL = os.environ.get("UIBINDER_VISION_MODEL", "").strip()
VISION_API_KEY = os.environ.get("UIBINDER_VISION_API_KEY", "").strip()

# Project scan limits (protect against pathological repos).
SCAN_MAX_FILES = 5000
SCAN_MAX_FILE_BYTES = 2 * 1024 * 1024
SCAN_IGNORED_DIRS = {
    "node_modules", ".git", "dist", "build", "target", ".venv", "venv",
    "__pycache__", ".next", ".nuxt", "coverage", ".pytest_cache",
    ".mypy_cache", ".idea", ".vscode", "out", ".cache",
}

MAX_IMAGE_BYTES = 25 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {"PNG", "JPEG", "WEBP"}
