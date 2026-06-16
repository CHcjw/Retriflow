from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from api.deps.auth import CurrentUser
from modules.chat import RetriFlowChatService
from modules.chat import RetriFlowStreamingService
from schemas.chat import (
    ChatBootstrapResponse,
    ChatMessageRequest,
    ChatMessageWithSourcesResponse,
)


router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


def _chat_service() -> RetriFlowChatService:
    return RetriFlowChatService()


def _streaming_service() -> RetriFlowStreamingService:
    return RetriFlowStreamingService()


@router.get("/bootstrap", response_model=ChatBootstrapResponse)
def get_chat_bootstrap() -> ChatBootstrapResponse:
    return _chat_service().get_bootstrap()


@router.post("/messages", response_model=ChatMessageWithSourcesResponse)
def send_chat_message(request: ChatMessageRequest, user: CurrentUser) -> ChatMessageWithSourcesResponse:
    return _chat_service().send_message(request, user.id)


@router.post("/stream")
def stream_chat_message(request: ChatMessageRequest, user: CurrentUser) -> StreamingResponse:
    return StreamingResponse(
        _streaming_service().build_event_stream(request, user.id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )

