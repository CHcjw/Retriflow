import json
from collections.abc import Iterable

from schemas.chat import ChatMessageRequest

from domain.chat import RetriFlowChatService


class RetriFlowStreamingService:
    def __init__(self) -> None:
        self.chat_service = RetriFlowChatService()

    def stream_events(self, request: ChatMessageRequest) -> Iterable[str]:
        workflow_result = self.chat_service.prepare_stream(request)
        assistant_parts: list[str] = []

        yield self._format_event("workflow", workflow_result.workflow.model_dump_json())
        yield self._format_event(
            "sources",
            json.dumps([source.model_dump() for source in workflow_result.sources], ensure_ascii=False),
        )

        for delta in workflow_result.deltas:
            assistant_parts.append(delta)
            yield self._format_event("delta", json.dumps({"content": delta}, ensure_ascii=False))

        assistant_message = "".join(assistant_parts)
        self.chat_service.persist_stream_result(request=request, assistant_message=assistant_message)

        yield self._format_event(
            "done",
            json.dumps({"session_id": request.session_id}, ensure_ascii=False),
        )

    @staticmethod
    def _format_event(event: str, data: str) -> str:
        return f"event: {event}\ndata: {data}\n\n"
