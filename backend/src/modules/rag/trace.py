from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import secrets
import time
import uuid
from typing import Any

from core.state import get_connection


_TRACE_ID: ContextVar[str] = ContextVar("retriflow_trace_id", default="")
_TASK_ID: ContextVar[str] = ContextVar("retriflow_task_id", default="")
_SESSION_ID: ContextVar[str] = ContextVar("retriflow_session_id", default="")
_NODE_STACK: ContextVar[tuple[str, ...]] = ContextVar("retriflow_node_stack", default=())


@dataclass
class RetriFlowTraceSpan:
    service: "RetriFlowTraceService"
    id: str
    session_id: str
    task_id: str
    name: str
    node_type: str
    started_at: float
    _finished: bool = False
    _context_tokens: tuple[Any, ...] = ()

    def __enter__(self) -> "RetriFlowTraceSpan":
        if self.id:
            self.service._push_node(self.id)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if exc is not None:
                self.finish_error(exc)
            elif not self._finished:
                self.finish_success()
        finally:
            if self.id:
                self.service._pop_node(self.id)
            if self._context_tokens:
                self.service._reset_context(self._context_tokens)

    def finish_success(self, output_summary: str = "") -> None:
        self._finish(status="success", output_summary=output_summary)

    def finish_error(self, error: BaseException) -> None:
        self._finish(status="error", error_message=str(error))

    def finish_cancelled(self) -> None:
        self._finish(status="cancelled")

    def _finish(self, *, status: str, output_summary: str = "", error_message: str = "") -> None:
        if self._finished:
            return
        self._finished = True
        if not self.id:
            return
        self.service.finish_node(
            node_id=self.id,
            status=status,
            output_summary=output_summary,
            error_message=error_message,
            duration_ms=max(0, int((time.perf_counter() - self.started_at) * 1000)),
        )


@dataclass
class RetriFlowStreamTraceSpan:
    service: "RetriFlowTraceService"
    span: RetriFlowTraceSpan
    _detached: bool = False
    _finished: bool = False

    @property
    def id(self) -> str:
        return self.span.id

    def detach(self) -> None:
        if self._detached:
            return
        self._detached = True
        self.service._pop_node(self.span.id)

    def finish_success(self, output_summary: str = "") -> None:
        self._finish(status="success", output_summary=output_summary)

    def finish_error(self, error: BaseException) -> None:
        self._finish(status="error", error_message=f"{type(error).__name__}: {error}")

    def finish_cancelled_if_running(self) -> None:
        self._finish(status="cancelled")

    def _finish(self, *, status: str, output_summary: str = "", error_message: str = "") -> None:
        if self._finished:
            return
        self._finished = True
        self.service.finish_node(
            node_id=self.span.id,
            status=status,
            output_summary=output_summary,
            error_message=error_message,
            duration_ms=max(0, int((time.perf_counter() - self.span.started_at) * 1000)),
        )


class RetriFlowTraceService:
    def start_root(self, *, session_id: str, task_id: str = "", name: str = "rag") -> RetriFlowTraceSpan:
        trace_id = self._generate_trace_id()
        context_tokens = (
            _TRACE_ID.set(trace_id),
            _TASK_ID.set(task_id),
            _SESSION_ID.set(session_id),
            _NODE_STACK.set(()),
        )
        span = self._create_span(
            session_id=session_id,
            task_id=task_id,
            parent_id="",
            name=name,
            node_type="ROOT",
            node_id=trace_id,
        )
        span._context_tokens = context_tokens
        return span

    def span(
        self,
        *,
        name: str,
        node_type: str = "METHOD",
        input_summary: str = "",
        metadata: dict[str, Any] | None = None,
        session_id: str = "",
    ) -> RetriFlowTraceSpan:
        effective_session_id = session_id or _SESSION_ID.get()
        if not _TRACE_ID.get() or not effective_session_id:
            return self._noop_span(
                session_id=effective_session_id,
                task_id=_TASK_ID.get(),
                name=name,
                node_type=node_type,
            )
        parent_id = self.current_node_id()
        return self._create_span(
            session_id=effective_session_id,
            task_id=_TASK_ID.get(),
            parent_id=parent_id or "",
            name=name,
            node_type=node_type,
            input_summary=input_summary,
            metadata=metadata or {},
        )

    def has_active_trace(self) -> bool:
        return bool(_TRACE_ID.get())

    def begin_stream_span(
        self,
        *,
        name: str,
        node_type: str = "STREAM",
        input_summary: str = "",
        metadata: dict[str, Any] | None = None,
        session_id: str = "",
    ) -> RetriFlowStreamTraceSpan:
        effective_session_id = session_id or _SESSION_ID.get()
        trace_id = _TRACE_ID.get()
        if not trace_id or not effective_session_id:
            noop = RetriFlowTraceSpan(
                service=self,
                id="",
                session_id=effective_session_id,
                task_id=_TASK_ID.get(),
                name=name,
                node_type=node_type,
                started_at=time.perf_counter(),
                _finished=True,
            )
            return RetriFlowStreamTraceSpan(service=self, span=noop, _detached=True, _finished=True)
        span = self._create_span(
            session_id=effective_session_id,
            task_id=_TASK_ID.get(),
            parent_id=self.current_node_id() or "",
            name=name,
            node_type=node_type,
            input_summary=input_summary,
            metadata=metadata or {},
        )
        self._push_node(span.id)
        return RetriFlowStreamTraceSpan(service=self, span=span)

    def list_nodes(self, session_id: str) -> list[dict[str, Any]]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                select *
                from rag_trace_nodes
                where session_id = ?
                order by started_at asc, id asc
                """,
                (session_id,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def finish_node(
        self,
        *,
        node_id: str,
        status: str,
        output_summary: str = "",
        error_message: str = "",
        duration_ms: int = 0,
    ) -> None:
        finished_at = datetime.now(timezone.utc).isoformat()
        with get_connection() as connection:
            connection.execute(
                """
                update rag_trace_nodes
                set status = ?,
                    output_summary = ?,
                    error_message = ?,
                    finished_at = ?,
                    duration_ms = ?
                where id = ?
                """,
                (status, output_summary, error_message, finished_at, duration_ms, node_id),
            )
            connection.commit()

    def current_node_id(self) -> str:
        stack = _NODE_STACK.get()
        return stack[-1] if stack else ""

    def _create_span(
        self,
        *,
        session_id: str,
        task_id: str,
        parent_id: str,
        name: str,
        node_type: str,
        node_id: str | None = None,
        input_summary: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> RetriFlowTraceSpan:
        resolved_node_id = node_id or uuid.uuid4().hex
        started_at = datetime.now(timezone.utc).isoformat()
        with get_connection() as connection:
            connection.execute(
                """
                insert into rag_trace_nodes (
                    id, session_id, task_id, parent_id, name, node_type, status,
                    input_summary, metadata_json, started_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resolved_node_id,
                    session_id,
                    task_id,
                    parent_id,
                    name,
                    node_type,
                    "running",
                    input_summary,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    started_at,
                ),
            )
            connection.commit()
        return RetriFlowTraceSpan(
            service=self,
            id=resolved_node_id,
            session_id=session_id,
            task_id=task_id,
            name=name,
            node_type=node_type,
            started_at=time.perf_counter(),
        )

    @staticmethod
    def _generate_trace_id() -> str:
        epoch_ms = int(time.time() * 1000)
        return f"{epoch_ms:013d}{secrets.randbelow(10_000_000):07d}"

    def _noop_span(self, *, session_id: str, task_id: str, name: str, node_type: str) -> RetriFlowTraceSpan:
        return RetriFlowTraceSpan(
            service=self,
            id="",
            session_id=session_id,
            task_id=task_id,
            name=name,
            node_type=node_type,
            started_at=time.perf_counter(),
        )

    @staticmethod
    def _push_node(node_id: str) -> None:
        _NODE_STACK.set((*_NODE_STACK.get(), node_id))

    @staticmethod
    def _pop_node(node_id: str) -> None:
        stack = _NODE_STACK.get()
        if not stack:
            return
        if stack[-1] == node_id:
            _NODE_STACK.set(stack[:-1])
            return
        _NODE_STACK.set(tuple(item for item in stack if item != node_id))

    @staticmethod
    def _reset_context(tokens: tuple[Any, ...]) -> None:
        for context_var, token in zip(
            (_NODE_STACK, _SESSION_ID, _TASK_ID, _TRACE_ID),
            reversed(tokens),
            strict=True,
        ):
            try:
                context_var.reset(token)
            except ValueError:
                continue

    @staticmethod
    def _row_to_dict(row) -> dict[str, Any]:
        metadata_raw = row.get("metadata_json", "{}")
        try:
            metadata = json.loads(str(metadata_raw or "{}"))
        except json.JSONDecodeError:
            metadata = {}
        return {
            "id": str(row["id"]),
            "session_id": str(row["session_id"]),
            "task_id": str(row["task_id"] or ""),
            "parent_id": str(row["parent_id"] or ""),
            "name": str(row["name"]),
            "node_type": str(row["node_type"]),
            "status": str(row["status"]),
            "input_summary": str(row["input_summary"] or ""),
            "output_summary": str(row["output_summary"] or ""),
            "error_message": str(row["error_message"] or ""),
            "metadata": metadata,
            "started_at": str(row["started_at"] or ""),
            "finished_at": str(row["finished_at"] or ""),
            "duration_ms": int(row["duration_ms"] or 0),
        }
