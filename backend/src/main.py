import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from api.router import router
from core.config import get_settings
from core.state import get_connection, initialize_database


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

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
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
