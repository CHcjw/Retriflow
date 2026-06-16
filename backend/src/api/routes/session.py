from fastapi import APIRouter, HTTPException, status

from api.deps.auth import CurrentUser
from modules.session import RetriFlowSessionService
from schemas.session import (
    ConversationMessageListResponse,
    SessionCreateRequest,
    SessionItem,
    SessionListResponse,
    SessionUpdateRequest,
)

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


def _service() -> RetriFlowSessionService:
    return RetriFlowSessionService()


@router.get("", response_model=SessionListResponse)
def list_sessions(user: CurrentUser) -> SessionListResponse:
    return _service().list_sessions(user.id)


@router.post("", response_model=SessionItem, status_code=status.HTTP_201_CREATED)
def create_session(request: SessionCreateRequest, user: CurrentUser) -> SessionItem:
    return _service().create_session(request, user.id)


@router.patch("/{session_id}", response_model=SessionItem)
def update_session(session_id: str, request: SessionUpdateRequest, user: CurrentUser) -> SessionItem:
    try:
        return _service().update_session_title(session_id, request.title, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("/{session_id}/messages", response_model=ConversationMessageListResponse)
def list_messages(session_id: str, user: CurrentUser) -> ConversationMessageListResponse:
    try:
        return _service().list_messages(session_id, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str, user: CurrentUser) -> None:
    try:
        _service().delete_session(session_id, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
