from fastapi import APIRouter, status

from domain.session import RetriFlowSessionService
from schemas.session import (
    ConversationMessageListResponse,
    SessionCreateRequest,
    SessionItem,
    SessionListResponse,
)


router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])
service = RetriFlowSessionService()


@router.get("", response_model=SessionListResponse)
def list_sessions() -> SessionListResponse:
    return service.list_sessions()


@router.post("", response_model=SessionItem, status_code=status.HTTP_201_CREATED)
def create_session(request: SessionCreateRequest) -> SessionItem:
    return service.create_session(request)


@router.get("/{session_id}/messages", response_model=ConversationMessageListResponse)
def list_messages(session_id: str) -> ConversationMessageListResponse:
    return service.list_messages(session_id)
