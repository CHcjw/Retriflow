import os
import sys

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from api.router import router
from core.config import get_settings
from core.state import get_connection, initialize_database
from infra.llm.monitor import get_model_health_probe_scheduler


def configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


configure_utf8_stdio()


def create_app() -> FastAPI:
    settings = get_settings()
    initialize_database()
    runtime_backend = "unknown"
    try:
        with get_connection() as connection:
            runtime_backend = connection.backend
    except Exception as exc:
        print(f"[RetriFlow] database probe failed: {exc}")

    print(
        "[RetriFlow] app bootstrapped"
        f" | configured_backend={settings.database_backend}"
        f" | runtime_backend={runtime_backend}"
        f" | db_path={settings.db_path}"
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        scheduler = get_model_health_probe_scheduler()
        scheduler.start()
        try:
            yield
        finally:
            await scheduler.stop()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


if __name__ == "__main__":
    uvicorn.run("main:create_app", host="127.0.0.1", port=8000, reload=False, factory=True)
elif os.getenv("RETRIFLOW_EAGER_APP", "false").lower() == "true":
    app = create_app()
