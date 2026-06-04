from core.state import get_connection
from schemas.chat import (
    ChatBootstrapResponse,
    ChatMessageRequest,
    ChatMessageWithSourcesResponse,
)

from domain.workflow import RetriFlowChatWorkflow, WorkflowResult, WorkflowStreamResult


class RetriFlowChatService:
    def __init__(self) -> None:
        self.workflow = RetriFlowChatWorkflow()

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

    def send_message(self, request: ChatMessageRequest) -> ChatMessageWithSourcesResponse:
        workflow_result = self.workflow.run(request.message)
        self._persist_message_exchange(
            session_id=request.session_id,
            user_message=request.message,
            assistant_message=workflow_result.assistant_message,
        )
        return self._build_response(request=request, workflow_result=workflow_result)

    def prepare_stream(self, request: ChatMessageRequest) -> WorkflowStreamResult:
        return self.workflow.stream(request.message)

    def persist_stream_result(self, request: ChatMessageRequest, assistant_message: str) -> None:
        self._persist_message_exchange(
            session_id=request.session_id,
            user_message=request.message,
            assistant_message=assistant_message,
        )

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
