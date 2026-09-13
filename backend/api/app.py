"""FastAPI application factory."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import APP_NAME, VERSION, config
from backend.logging_setup import log
from backend.persistence.db import init_db
from backend.persistence.store import WorkspaceStore
from backend.vision import list_providers


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    log("", "INFO", "backend started", version=VERSION, data_root=str(config.get_data_root()))
    yield
    log("", "INFO", "backend stopped")


def create_app() -> FastAPI:
    app = FastAPI(title=APP_NAME, version=VERSION, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                       "tauri://localhost", "http://tauri.localhost"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from .workspaces import router as workspaces_router
    from .images import router as images_router
    from .ui import router as ui_router
    from .projects import router as projects_router
    from .capabilities import router as capabilities_router
    from .bindings import router as bindings_router
    from .verification import router as verification_router
    from .export import router as export_router
    from .search import router as search_router
    from .trace import router as trace_router
    from .logs import router as logs_router
    from .spec import router as spec_router
    from .ocr_api import router as ocr_router
    from .fonts_api import router as fonts_router
    from .imagegen_api import router as imagegen_router

    @app.get("/health")
    @app.get("/api/health")
    def health() -> dict:
        init_db()
        store = WorkspaceStore()
        configured = "remote" if (config.VISION_BASE_URL and config.VISION_MODEL and config.VISION_API_KEY) else "heuristic"
        try:
            db_state = "ok"
            workspaces = len(store.list_workspaces())
        except Exception as exc:  # pragma: no cover - degraded health still reports
            db_state = f"error: {exc.__class__.__name__}"
            workspaces = -1
        return {
            "status": "ok" if db_state == "ok" else "degraded",
            "app": APP_NAME,
            "version": VERSION,
            "database": {"state": db_state, "path": str(config.db_path())},
            "vision_provider": {"available": list_providers(), "configured": configured,
                                "remote_configured": bool(config.VISION_BASE_URL and config.VISION_MODEL and config.VISION_API_KEY)},
            "workspaces": {"count": workspaces},
        }

    app.include_router(workspaces_router, prefix="/api")
    app.include_router(images_router, prefix="/api")
    app.include_router(ui_router, prefix="/api")
    app.include_router(projects_router, prefix="/api")
    app.include_router(capabilities_router, prefix="/api")
    app.include_router(bindings_router, prefix="/api")
    app.include_router(verification_router, prefix="/api")
    app.include_router(export_router, prefix="/api")
    app.include_router(search_router, prefix="/api")
    app.include_router(trace_router, prefix="/api")
    app.include_router(logs_router, prefix="/api")
    app.include_router(spec_router, prefix="/api")
    app.include_router(ocr_router, prefix="/api")
    app.include_router(fonts_router, prefix="/api")
    app.include_router(imagegen_router, prefix="/api")
    return app


app = create_app()
