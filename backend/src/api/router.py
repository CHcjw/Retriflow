from fastapi import APIRouter

from api.routes import chat, ingestion, knowledge
from api.routes import session
from core.config import get_settings


router = APIRouter()


@router.get("/healthz", tags=["system"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/v1/meta", tags=["system"])
def api_meta() -> dict[str, object]:
    settings = get_settings()
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "api_prefix": settings.api_prefix,
        "frontend_name": "RetriFlow Web",
        "primary_routes": ["home", "chat", "admin"],
    }


router.include_router(chat.router)
router.include_router(session.router)
router.include_router(knowledge.router)
router.include_router(ingestion.router)
