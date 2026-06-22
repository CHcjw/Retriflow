from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import AsyncIterable
import re
import time

from core.config import get_settings
from modules.chat.rate_limit import ChatQueueTicket, get_chat_queue_limiter
from modules.chat.service import RetriFlowChatService
from modules.chat.stream_tasks import get_stream_task_manager
from modules.rag.postprocess import RetriFlowAnswerPostprocessor
from modules.rag.trace import RetriFlowTraceService
from schemas.chat import ChatMessageRequest


class RetriFlowStreamingService:
    def __init__(self) -> None:
        self.chat_service = RetriFlowChatService()
        self.answer_postprocessor = RetriFlowAnswerPostprocessor()
        self.trace_service = RetriFlowTraceService()
        self.settings = get_settings()
        self.stream_task_manager = get_stream_task_manager()

    def build_event_stream(self, request: ChatMessageRequest, user_id: str) -> AsyncIterable[str]:
        return self._stream_with_queue(request=request, user_id=user_id)

    async def _stream_with_queue(self, request: ChatMessageRequest, user_id: str) -> AsyncIterable[str]:
        ticket: ChatQueueTicket | None = None
        cancel_event: threading.Event | None = None
        task_id = self.stream_task_manager.create_task_id()
        if self.settings.chat_queue_enabled:
            limiter = get_chat_queue_limiter()
            queue_snapshot = limiter.snapshot()
            yield self._format_event(
                "queue",
                json.dumps(
                    {
                        "status": "waiting",
                        **queue_snapshot,
                        "max_wait_seconds": self.settings.chat_queue_max_wait_seconds,
                    },
                    ensure_ascii=False,
                ),
            )
            await asyncio.sleep(0)
            cancel_event = threading.Event()
            try:
                ticket = await asyncio.to_thread(
                    limiter.acquire,
                    max_wait_seconds=self.settings.chat_queue_max_wait_seconds,
                    cancel_event=cancel_event,
                )
            except (GeneratorExit, asyncio.CancelledError):
                cancel_event.set()
                raise
            if not ticket.acquired:
                reject_message = self.chat_service.QUEUE_REJECT_MESSAGE
                self.chat_service.persist_rejected_stream_result(request=request, user_id=user_id)
                yield self._format_event(
                    "reject",
                    json.dumps({"message": reject_message, "reason": ticket.reason}, ensure_ascii=False),
                )
                await asyncio.sleep(0)
                yield self._format_event(
                    "final",
                    json.dumps({"status": "rejected", "mode": "replace", "content": reject_message}, ensure_ascii=False),
                )
                await asyncio.sleep(0)
                yield self._format_event("done", json.dumps({"session_id": request.session_id}, ensure_ascii=False))
                return

        try:
            async for event in self._stream_events(
                request=request,
                user_id=user_id,
                task_id=task_id,
            ):
                yield event
        except (GeneratorExit, asyncio.CancelledError):
            if cancel_event is not None:
                cancel_event.set()
            raise
        finally:
            if ticket is not None:
                ticket.release()
            self.stream_task_manager.unregister(task_id)

    async def _stream_events(
        self,
        request: ChatMessageRequest,
        user_id: str,
        task_id: str,
    ) -> AsyncIterable[str]:
        trace_root = self.trace_service.start_root(
            session_id=request.session_id,
            task_id=task_id,
            name="chat.stream",
        )
        trace_root.__enter__()
        terminal_event = False
        first_packet_recorded = False
        assistant_parts: list[str] = []
        workflow_result = None
        started_at = time.perf_counter()

        try:
            workflow_result = self.chat_service.prepare_stream(request, user_id)
            yield self._format_event("workflow", workflow_result.workflow.model_dump_json())
            await asyncio.sleep(0)
            yield self._format_event("task", json.dumps({"task_id": task_id}, ensure_ascii=False))
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
                if self.stream_task_manager.is_cancelled(task_id):
                    terminal_event = True
                    trace_root.finish_cancelled()
                    yield self._format_event("cancel", json.dumps({"task_id": task_id}, ensure_ascii=False))
                    await asyncio.sleep(0)
                    yield self._format_event("done", json.dumps({"session_id": request.session_id}, ensure_ascii=False))
                    return
                for display_chunk in self._split_display_chunks(delta):
                    if self.stream_task_manager.is_cancelled(task_id):
                        terminal_event = True
                        trace_root.finish_cancelled()
                        yield self._format_event("cancel", json.dumps({"task_id": task_id}, ensure_ascii=False))
                        await asyncio.sleep(0)
                        yield self._format_event("done", json.dumps({"session_id": request.session_id}, ensure_ascii=False))
                        return
                    if not first_packet_recorded:
                        self._record_user_first_packet(started_at)
                        first_packet_recorded = True
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
            terminal_event = True
            trace_root.finish_success(
                output_summary=f"events=done; chars={len(raw_message)}; sources={len(workflow_result.sources)}"
            )
        except (GeneratorExit, asyncio.CancelledError):
            if not terminal_event:
                trace_root.finish_cancelled()
            raise
        except BaseException as exc:
            if not terminal_event:
                trace_root.finish_error(exc)
            raise
        finally:
            if not terminal_event and workflow_result is not None:
                close_deltas = getattr(workflow_result.deltas, "close", None)
                if callable(close_deltas):
                    close_deltas()
            if not terminal_event and not trace_root._finished:
                trace_root.finish_cancelled()
            trace_root.__exit__(None, None, None)

    def _record_user_first_packet(self, started_at: float) -> None:
        span = self.trace_service.span(
            name="user-first-packet",
            node_type="USER_TTFT",
            input_summary="first streamed delta",
        )
        span.__enter__()
        try:
            duration_ms = max(0, int((time.perf_counter() - started_at) * 1000))
            self.trace_service.finish_node(
                node_id=span.id,
                status="success",
                output_summary="first_delta",
                duration_ms=duration_ms,
            )
            span._finished = True
        finally:
            span.__exit__(None, None, None)

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
