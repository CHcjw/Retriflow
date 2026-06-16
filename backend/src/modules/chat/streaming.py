from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterable
import re
import time

from modules.chat.service import RetriFlowChatService
from modules.rag.postprocess import RetriFlowAnswerPostprocessor
from modules.rag.workflow import WorkflowStreamResult
from schemas.chat import ChatMessageRequest


class RetriFlowStreamingService:
    def __init__(self) -> None:
        self.chat_service = RetriFlowChatService()
        self.answer_postprocessor = RetriFlowAnswerPostprocessor()

    def build_event_stream(self, request: ChatMessageRequest, user_id: str) -> AsyncIterable[str]:
        workflow_result = self.chat_service.prepare_stream(request, user_id)
        return self._stream_events(
            request=request,
            user_id=user_id,
            workflow_result=workflow_result,
        )

    async def _stream_events(
        self,
        request: ChatMessageRequest,
        user_id: str,
        workflow_result: WorkflowStreamResult,
    ) -> AsyncIterable[str]:
        assistant_parts: list[str] = []
        started_at = time.perf_counter()

        yield self._format_event("workflow", workflow_result.workflow.model_dump_json())
        await asyncio.sleep(0)
        yield self._format_event(
            "sources",
            json.dumps([source.model_dump() for source in workflow_result.sources], ensure_ascii=False),
        )
        await asyncio.sleep(0)

        if workflow_result.mcp_calls:
            yield self._format_event(
                "mcp_calls",
                json.dumps([call.model_dump() for call in workflow_result.mcp_calls], ensure_ascii=False),
            )
            await asyncio.sleep(0)

        for delta in workflow_result.deltas:
            for display_chunk in self._split_display_chunks(delta):
                assistant_parts.append(display_chunk)
                yield self._format_event("delta", json.dumps({"content": display_chunk}, ensure_ascii=False))
                await asyncio.sleep(0.02)

        raw_message = "".join(assistant_parts)
        assistant_message = self.answer_postprocessor.finalize(raw_message, workflow_result.sources)
        self.chat_service.persist_stream_result(
            request=request,
            assistant_message=assistant_message,
            user_id=user_id,
            assistant_duration_ms=max(1, int((time.perf_counter() - started_at) * 1000)),
        )
        yield self._format_event(
            "final",
            json.dumps(self._build_final_payload(raw_message, assistant_message), ensure_ascii=False),
        )
        await asyncio.sleep(0)
        yield self._format_event("done", json.dumps({"session_id": request.session_id}, ensure_ascii=False))

    @staticmethod
    def _format_event(event: str, data: str) -> str:
        return f"event: {event}\ndata: {data}\n\n"

    @staticmethod
    def _split_display_chunks(delta: str) -> list[str]:
        text = delta or ""
        if len(text) <= 24:
            return [text] if text else []

        chunks: list[str] = []
        sentence_parts = re.split(r"(?<=[。！？；.!?])", text)
        for part in sentence_parts:
            if not part:
                continue
            if len(part) <= 24:
                chunks.append(part)
                continue

            for index in range(0, len(part), 24):
                chunks.append(part[index:index + 24])

        return chunks or [text]

    @staticmethod
    def _build_final_payload(raw_message: str, assistant_message: str) -> dict[str, str]:
        if assistant_message == raw_message:
            return {"status": "complete"}

        if assistant_message.startswith(raw_message):
            return {
                "status": "complete",
                "mode": "append",
                "content_delta": assistant_message[len(raw_message):],
            }

        return {
            "status": "complete",
            "mode": "replace",
            "content": assistant_message,
        }
