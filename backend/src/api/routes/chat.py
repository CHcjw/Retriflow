from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from api.deps.auth import CurrentUser
from modules.chat import RetriFlowChatService
from modules.chat import RetriFlowStreamingService
from modules.chat.feedback import RetriFlowMessageFeedbackService
from modules.chat.stream_tasks import get_stream_task_manager
from schemas.chat import (
    ChatBootstrapResponse,
    ChatMessageRequest,
    ChatMessageWithSourcesResponse,
    MessageFeedbackRequest,
    MessageFeedbackResponse,
)


router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


def _chat_service() -> RetriFlowChatService:
    return RetriFlowChatService()


def _streaming_service() -> RetriFlowStreamingService:
    return RetriFlowStreamingService()


def _feedback_service() -> RetriFlowMessageFeedbackService:
    return RetriFlowMessageFeedbackService()


@router.get("/bootstrap", response_model=ChatBootstrapResponse)
def get_chat_bootstrap() -> ChatBootstrapResponse:
    return _chat_service().get_bootstrap()


@router.post("/messages", response_model=ChatMessageWithSourcesResponse)
def send_chat_message(request: ChatMessageRequest, user: CurrentUser) -> ChatMessageWithSourcesResponse:
    return _chat_service().send_message(request, user.id)


@router.post("/messages/{message_id}/feedback", response_model=MessageFeedbackResponse)
def submit_message_feedback(
    message_id: int,
    request: MessageFeedbackRequest,
    user: CurrentUser,
) -> MessageFeedbackResponse:
    return _feedback_service().submit_feedback(message_id=message_id, user_id=user.id, request=request)


@router.post("/stream")
def stream_chat_message(request: ChatMessageRequest, user: CurrentUser) -> StreamingResponse:
    return StreamingResponse(
        _streaming_service().build_event_stream(request, user.id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/stream/{task_id}/cancel")
def cancel_stream_task(task_id: str, user: CurrentUser) -> dict[str, str]:
    get_stream_task_manager().cancel(task_id)
    return {"task_id": task_id, "status": "cancelled"}

