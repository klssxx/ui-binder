"""Dev orchestrator: backend (uvicorn) + frontend (vite) in one command.

Usage:
    python scripts/dev.py                # backend + frontend
    python scripts/dev.py --backend-only # just the API
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    backend_only = "--backend-only" in sys.argv
    venv_python = ROOT / ".venv" / "Scripts" / "python.exe"
    py = str(venv_python) if venv_python.exists() else sys.executable

    procs: list[subprocess.Popen] = []
    env = os.environ.copy()
    env.setdefault("UIBINDER_DATA_DIR", str(ROOT / "data"))

    procs.append(subprocess.Popen([
        py, "-m", "uvicorn", "backend.api.app:app",
        "--host", env.get("UIBINDER_HOST", "127.0.0.1"),
        "--port", env.get("UIBINDER_PORT", "8765"),
        "--reload", "--app-dir", str(ROOT),
    ], cwd=str(ROOT), env=env))
    print("[dev] backend  → http://127.0.0.1:8765 (health: /health)")

    if not backend_only:
        npm = "npm.cmd" if os.name == "nt" else "npm"
        procs.append(subprocess.Popen([npm, "run", "dev"], cwd=str(ROOT / "apps" / "desktop")))
        print("[dev] frontend → http://localhost:5173")

    def shutdown(*_a: object) -> None:
        for p in procs:
            if p.poll() is None:
                p.terminate()

    signal.signal(signal.SIGINT, signal.SIG_IGN)  # handled via KeyboardInterrupt below
    try:
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
