from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from domain.chat import RetriFlowChatService
from domain.streaming import RetriFlowStreamingService
from schemas.chat import (
    ChatBootstrapResponse,
    ChatMessageRequest,
    ChatMessageWithSourcesResponse,
)


router = APIRouter(prefix="/api/v1/chat", tags=["chat"])
service = RetriFlowChatService()
streaming_service = RetriFlowStreamingService()


@router.get("/bootstrap", response_model=ChatBootstrapResponse)
def get_chat_bootstrap() -> ChatBootstrapResponse:
    return service.get_bootstrap()


@router.post("/messages", response_model=ChatMessageWithSourcesResponse)
def send_chat_message(request: ChatMessageRequest) -> ChatMessageWithSourcesResponse:
    return service.send_message(request)


@router.post("/stream")
def stream_chat_message(request: ChatMessageRequest) -> StreamingResponse:
    return StreamingResponse(
        streaming_service.stream_events(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
