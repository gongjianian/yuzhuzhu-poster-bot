from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

    return app
