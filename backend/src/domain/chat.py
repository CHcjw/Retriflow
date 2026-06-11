from __future__ import annotations

from fastapi import HTTPException, status

from core.state import get_connection
from domain.memory import RetriFlowConversationMemoryService
from domain.session import RetriFlowSessionService
from domain.workflow import RetriFlowChatWorkflow, WorkflowResult, WorkflowStreamResult
from schemas.chat import (
    ChatBootstrapResponse,
    ChatMessageRequest,
    ChatMessageWithSourcesResponse,
)


class RetriFlowChatService:
    def __init__(self) -> None:
        self.workflow = RetriFlowChatWorkflow()
        self.memory_service = RetriFlowConversationMemoryService()
        self.session_service = RetriFlowSessionService()

    def get_bootstrap(self) -> ChatBootstrapResponse:
        return ChatBootstrapResponse(
            product="RetriFlow",
            capabilities=[
                "stream_chat",
                "conversation_memory",
                "knowledge_retrieval",
                "mcp_tools",
                "trace_observability",
            ],
        )

    def send_message(self, request: ChatMessageRequest, user_id: str) -> ChatMessageWithSourcesResponse:
        self._ensure_session_access(request.session_id, user_id, claim_unowned=True)
        workflow_result = self.workflow.run(
            request.message,
            session_id=request.session_id,
        )
        self._persist_message_exchange(
            session_id=request.session_id,
            user_message=request.message,
            assistant_message=workflow_result.assistant_message,
        )
        self.memory_service.update_short_term_memory(request.session_id)
        self.memory_service.update_mid_term_memory(request.session_id)
        self.memory_service.update_long_term_memory(request.session_id)
        return self._build_response(request=request, workflow_result=workflow_result)

    def prepare_stream(self, request: ChatMessageRequest, user_id: str) -> WorkflowStreamResult:
        self._ensure_session_access(request.session_id, user_id, claim_unowned=True)
        return self.workflow.stream(
            request.message,
            session_id=request.session_id,
        )

    def persist_stream_result(self, request: ChatMessageRequest, assistant_message: str, user_id: str) -> None:
        self._ensure_session_access(request.session_id, user_id, claim_unowned=True)
        self._persist_message_exchange(
            session_id=request.session_id,
            user_message=request.message,
            assistant_message=assistant_message,
        )
        self.memory_service.update_short_term_memory(request.session_id)
        self.memory_service.update_mid_term_memory(request.session_id)
        self.memory_service.update_long_term_memory(request.session_id)

    @staticmethod
    def _build_response(
        request: ChatMessageRequest,
        workflow_result: WorkflowResult,
    ) -> ChatMessageWithSourcesResponse:
        return ChatMessageWithSourcesResponse(
            session_id=request.session_id,
            assistant_message=workflow_result.assistant_message,
            sources=workflow_result.sources,
            workflow=workflow_result.workflow,
            mcp_calls=workflow_result.mcp_calls,
        )

    @staticmethod
    def _persist_message_exchange(session_id: str, user_message: str, assistant_message: str) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                insert into conversation_messages (session_id, role, content)
                values (?, ?, ?)
                """,
                (session_id, "user", user_message),
            )
            connection.execute(
                """
                insert into conversation_messages (session_id, role, content)
                values (?, ?, ?)
                """,
                (session_id, "assistant", assistant_message),
            )
            connection.execute(
                """
                update sessions
                set message_count = message_count + 2
                where id = ?
                """,
                (session_id,),
            )
            connection.commit()

    def _ensure_session_access(self, session_id: str, user_id: str, *, claim_unowned: bool) -> None:
        try:
            self.session_service.ensure_session_access(session_id, user_id, claim_unowned=claim_unowned)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
