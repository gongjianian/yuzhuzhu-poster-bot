from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from dashboard.config import get_settings
from dashboard.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    from dashboard.websocket_manager import loguru_ws_sink

    sink_id = logger.add(loguru_ws_sink, level="DEBUG")
    try:
        yield
    finally:
        logger.remove(sink_id)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="浴小主海报控制面板",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url="/api/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from dashboard.routers.auth_router import router as auth_router
    from dashboard.routers.health_router import router as health_router
    from dashboard.routers.logs_router import router as logs_router
    from dashboard.routers.pipeline_router import router as pipeline_router
    from dashboard.routers.runs_router import router as runs_router
    from dashboard.routers.stats_router import router as stats_router
    from dashboard.routers.tasks_router import router as tasks_router

    app.include_router(auth_router)
    app.include_router(health_router)
    app.include_router(logs_router)
    app.include_router(pipeline_router)
    app.include_router(runs_router)
    app.include_router(stats_router)
    app.include_router(tasks_router)

    static_dir = Path(__file__).parent.parent / "static"
    static_assets_dir = static_dir / "assets"
    if static_assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(static_assets_dir)), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return JSONResponse({"detail": "Frontend not built"}, status_code=404)

    return app
