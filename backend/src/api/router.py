from fastapi import APIRouter

from api.routes import admin, auth, chat, ingestion, knowledge
from api.routes import session
from core.config import get_settings
from core.state import get_connection


router = APIRouter()


@router.get("/healthz", tags=["system"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/v1/meta", tags=["system"])
def api_meta() -> dict[str, object]:
    settings = get_settings()
    runtime_backend = "unknown"
    try:
        with get_connection() as connection:
            runtime_backend = connection.backend
    except Exception:
        runtime_backend = "unavailable"

    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "api_prefix": settings.api_prefix,
        "frontend_name": "RetriFlow Web",
        "primary_routes": ["home", "chat", "admin"],
        "database_backend": settings.database_backend,
        "runtime_database_backend": runtime_backend,
        "database_schema": settings.database_schema,
    }


router.include_router(chat.router)
router.include_router(admin.router)
router.include_router(auth.router)
router.include_router(session.router)
router.include_router(knowledge.router)
router.include_router(ingestion.router)
