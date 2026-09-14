"""Central configuration: data root resolution and tunables.

Data root precedence:
1. UIBINDER_DATA_DIR env var (dev override, e.g. repo ./data)
2. %LOCALAPPDATA%/UIBinder (production default — never next to the exe)
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def user_env_file() -> Path:
    """Archivo .env del usuario (persistente, editable, nunca dentro del repo)."""
    local_app = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local_app) / "UIBinder" / ".env"


def _load_dotenv() -> None:
    """Minimal .env loader (no external dependency). Never overrides real env.

    Orden (el primero que exista gana): LOCALAPPDATA/UIBinder/.env,
    .env junto al exe (frozen), .env del repo (dev).
    """
    candidates = [user_env_file()]
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).parent / ".env")
    candidates.append(REPO_ROOT / ".env")
    for env_file in candidates:
        if not env_file.is_file():
            continue
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
        break


import sys  # noqa: E402  (usado arriba solo en frozen)

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

# Generación de imágenes opcional (F6): proveedor compatible OpenAI.
IMAGEGEN_BASE_URL = os.environ.get("UIBINDER_IMAGEGEN_BASE_URL", "").strip()
IMAGEGEN_MODEL = os.environ.get("UIBINDER_IMAGEGEN_MODEL", "").strip()
IMAGEGEN_API_KEY = os.environ.get("UIBINDER_IMAGEGEN_API_KEY", "").strip()

MAX_IMAGE_BYTES = 25 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {"PNG", "JPEG", "WEBP"}
