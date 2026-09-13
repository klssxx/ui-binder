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
    # Windowed PyInstaller exe (console=False) launched detached (e.g. `start`):
    # stdio is None and uvicorn's logging config crashes with
    # "Unable to configure formatter 'default'". Point them at devnull first.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115

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
        "UIEDITION", url, width=1440, height=900, min_size=(1024, 640))

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

    # Perfil persistente del WebView2: sin esto pywebview usa modo privado
    # (localStorage volátil) y una carpeta temporal por arranque.
    data_dir = Path(os.environ.get("UIBINDER_DATA_DIR",
                                   str(Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "UIBinder")))
    storage = data_dir / "webview-profile"
    storage.mkdir(parents=True, exist_ok=True)
    runlog = data_dir / "run.log"

    def _runlog(msg: str) -> None:
        try:
            with open(runlog, "a", encoding="utf-8") as fh:
                fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
        except OSError:
            pass

    _runlog(f"webview.start pid={os.getpid()} port={port}")
    webview.start(private_mode=False, storage_path=str(storage))
    _runlog("webview.start devolvió (ventana cerrada o GUI terminada)")
    server.should_exit = True
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        # Windowed exe: no console for the traceback — persist it for diagnosis.
        import traceback
        crash_dir = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "UIBinder"
        crash_dir.mkdir(parents=True, exist_ok=True)
        (crash_dir / "crash.log").write_text(traceback.format_exc(), encoding="utf-8")
        raise
