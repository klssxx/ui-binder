"""UI Binder desktop app — single process: FastAPI backend + built frontend + WebView2 window.

Run from source:
    python scripts/desktop_app.py            (needs apps/desktop/dist built first)

Packaged with PyInstaller (scripts/uibinder.spec) into dist/UIBinder/.

Smoke mode (no GUI interaction needed):
    set UIBINDER_SMOKE_EXIT_MS=3000 → window auto-closes, exit 0.
"""
from __future__ import annotations

import logging
import os
import socket
import sys
import threading
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

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


def _ensure_data_dir() -> Path:
    """Return the persistent data directory for WebView2 profile and logs."""
    local_app = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    data_dir = Path(local_app) / "UIBinder"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def _detect_corrupt_profile(storage: Path) -> Path | None:
    """If the WebView2 profile dir exists but has no usable session, return it for backup."""
    if not storage.is_dir():
        return None
    # Edge WebView2 uses EBWebView subfolder; check for session data
    eb = storage / "EBWebView"
    if not eb.is_dir():
        return storage
    session_files = list(eb.rglob("*.dat")) or list(eb.rglob("Session*"))
    if not session_files:
        return storage
    return None


def _backup_corrupt_profile(storage: Path) -> Path:
    """Move a corrupt/no-session profile to a timestamped backup."""
    import datetime
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = storage.parent / f"webview-profile-ROTO-{ts}"
    storage.rename(backup)
    logger.info("Corrupt profile backed up: %s -> %s", storage, backup)
    return storage


def main() -> int:
    # Windowed PyInstaller exe (console=False) launched detached:
    # stdio is None and uvicorn's logging config crashes.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115

    data_dir = _ensure_data_dir()

    # Logging
    runlog_path = data_dir / "run.log"

    def _runlog(msg: str) -> None:
        try:
            with open(runlog_path, "a", encoding="utf-8") as fh:
                fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
        except OSError:
            pass

    # Determine WebView2 storage path
    storage = data_dir / "webview-profile"

    # Detect corrupt profile and back up if needed
    corrupt = _detect_corrupt_profile(storage)
    if corrupt:
        _backup_corrupt_profile(corrupt)

    # Set env for subprocess
    os.environ["UIBINDER_DATA_DIR"] = str(data_dir)

    # Start FastAPI backend
    logger.info("Starting FastAPI backend...")
    import uvicorn
    from fastapi.staticfiles import StaticFiles

    from backend.api.app import create_app

    app = create_app()
    dist = _frontend_dist()
    app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")

    port = int(os.environ.get("UIBINDER_PORT", "0") or 0) or _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    # Wait for backend to accept connections (max 15 s)
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.1)
    else:
        logger.error("Backend failed to start on port %s", port)
        return 1

    _runlog(f"backend ok port={port}")

    # Start WebView2
    logger.info("Starting WebView2...")
    import webview

    url = f"http://127.0.0.1:{port}/"

    def _on_loaded() -> None:
        _runlog("webview_loaded")
        logger.info("WebView2 loaded: %s", url)
        # Verify DOM contains UIEDITION
        try:
            title = window.evaluate_js("document.title")
            body_text = window.evaluate_js("document.body.innerText.slice(0, 200)")
            _runlog(f"dom_check title={title!r} body={body_text!r}")
            logger.info("DOM check: title=%r body=%r", title, body_text)
        except Exception as e:
            _runlog(f"dom_check_failed: {e}")
            logger.warning("DOM check failed: %s", e)

    def _on_error(error: str) -> None:
        _runlog(f"webview_error: {error}")
        logger.error("WebView2 error: %s", error)

    def _on_closed() -> None:
        _runlog("webview_closed")
        logger.info("WebView2 closed")
        server.should_exit = True

    window = webview.create_window(
        "UIEDITION", url, width=1440, height=900, min_size=(1024, 640),
        maximized=True,
    )

    # Attach event callbacks AFTER window creation (pywebview API)
    window.events.loaded += _on_loaded
    window.events.closed += _on_closed

    _runlog(f"webview_created pid={os.getpid()} url={url}")
    logger.info("WebView2 window created: %s", url)

    # Smoke mode: auto-close after timeout
    smoke_ms = os.environ.get("UIBINDER_SMOKE_EXIT_MS", "").strip()
    if smoke_ms.isdigit():

        def _auto_close() -> None:
            time.sleep(int(smoke_ms) / 1000)
            try:
                window.destroy()
            except Exception:
                pass
        threading.Thread(target=_auto_close, daemon=True).start()

    # Start webview event loop (blocking in main thread for windowed EXE)
    try:
        webview.start(private_mode=True, storage_path=str(storage))
    except Exception as exc:
        _runlog(f"webview_start_failed: {exc}")
        logger.exception("webview.start() failed")
        server.should_exit = True
        return 1

    _runlog("webview.start returned normally")
    logger.info("WebView2 event loop exited normally")
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
