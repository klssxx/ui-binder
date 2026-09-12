"""UI Binder desktop app — single process: FastAPI backend + built frontend + WebView2 window.

Run from source:
    python scripts/desktop_app.py            (needs apps/desktop/dist built first)

Packaged with PyInstaller (scripts/uibinder.spec) into dist/UIBinder/.

Smoke mode (no GUI interaction needed):
    set UIBINDER_SMOKE_EXIT_MS=3000 → window auto-closes, exit 0.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SOURCE_ROOT))


def _frontend_dist() -> Path:
    if getattr(sys, "frozen", False):  # PyInstaller
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        candidate = base / "webdist"
        if candidate.is_dir():
            return candidate
        return Path(sys.executable).parent / "webdist"
    dist = SOURCE_ROOT / "apps" / "desktop" / "dist"
    if not dist.is_dir():
        raise SystemExit(
            "Frontend not built. Run: npm run build   (in apps/desktop), then retry.")
    return dist


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def main() -> int:
    os.environ.setdefault("UIBINDER_DATA_DIR",
                          os.environ.get("UIBINDER_DATA_DIR") or "")
    if not os.environ.get("UIBINDER_DATA_DIR"):
        local_app = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        os.environ["UIBINDER_DATA_DIR"] = str(Path(local_app) / "UIBinder")

    import uvicorn
    from fastapi.staticfiles import StaticFiles

    from backend.api.app import create_app

    app = create_app()
    dist = _frontend_dist()
    app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")

    port = int(os.environ.get("UIBINDER_PORT", "0") or 0) or _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # wait for the server to accept connections (max 15 s)
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.1)
    else:
        print("backend failed to start", file=sys.stderr)
        return 1

    import webview

    url = f"http://127.0.0.1:{port}/"
    window = webview.create_window(
        "UI Binder", url, width=1440, height=900, min_size=(1024, 640))

    smoke_ms = os.environ.get("UIBINDER_SMOKE_EXIT_MS", "").strip()
    if smoke_ms.isdigit():
        import webview as _wv

        def _auto_close() -> None:
            time.sleep(int(smoke_ms) / 1000)
            try:
                window.destroy()
            except Exception:
                pass
        threading.Thread(target=_auto_close, daemon=True).start()

    webview.start()
    server.should_exit = True
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
