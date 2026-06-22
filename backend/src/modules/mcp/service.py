from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from core.config import get_settings
from modules.mcp.models import McpExecutionResult, McpRouteDecision, McpToolCallResult
from modules.mcp.parameter_extractor import RetriFlowMcpParameterExtractor
from modules.mcp.registry import RetriFlowMcpRegistry
from modules.rag.trace import RetriFlowTraceService


@dataclass(frozen=True)
class MatchedToolCandidate:
    tool_id: str
    confidence: float
    reason: str


class RetriFlowMcpService:
    MIN_TOOL_CONFIDENCE = 0.55
    DEFAULT_MAX_TOOL_CANDIDATES = 3
    DEFAULT_PARALLEL_MAX_WORKERS = 3

    def __init__(self) -> None:
        self.settings = get_settings()
        self.registry = RetriFlowMcpRegistry()
        self.parameter_extractor = RetriFlowMcpParameterExtractor()
        self.trace_service = RetriFlowTraceService()

    def route_question(self, question: str) -> McpRouteDecision:
        matched = self._match_tools(question)
        if not matched:
            return McpRouteDecision(
                mode="none",
                tool_ids=[],
                confidence=0.0,
                reason="no matched mcp tool",
            )

        selected = [
            candidate
            for candidate in matched
            if candidate.confidence >= self.MIN_TOOL_CONFIDENCE
        ][: self._max_tool_candidates]

        if not selected:
            return McpRouteDecision(
                mode="none",
                tool_ids=[],
                confidence=0.0,
                reason="matched tools did not pass confidence threshold",
            )

        return McpRouteDecision(
            mode="mcp",
            tool_ids=[candidate.tool_id for candidate in selected],
            confidence=selected[0].confidence,
            reason="; ".join(
                f"{candidate.tool_id}: {candidate.reason}" for candidate in selected
            ),
        )

    def execute_question(self, question: str) -> McpExecutionResult:
        route = self.route_question(question)
        if route.mode != "mcp" or not route.tool_ids:
            return McpExecutionResult(route=route, calls=[])

        calls = self._execute_tools(question=question, tool_ids=route.tool_ids)
        return McpExecutionResult(route=route, calls=calls)

    @property
    def _execution_mode(self) -> str:
        mode = self.settings.mcp_execution_mode.strip().lower()
        if mode in {"parallel", "sequential"}:
            return mode
        return "sequential"

    @property
    def _max_tool_candidates(self) -> int:
        return max(1, self.settings.mcp_max_tool_candidates or self.DEFAULT_MAX_TOOL_CANDIDATES)

    @property
    def _parallel_max_workers(self) -> int:
        return max(
            1,
            self.settings.mcp_parallel_max_workers or self.DEFAULT_PARALLEL_MAX_WORKERS,
        )

    def _execute_tools(self, question: str, tool_ids: list[str]) -> list[McpToolCallResult]:
        if self.settings.mcp_fail_fast:
            return self._execute_sequential(question=question, tool_ids=tool_ids)
        if self._execution_mode == "parallel" and len(tool_ids) > 1:
            return self._execute_parallel(question=question, tool_ids=tool_ids)
        return self._execute_sequential(question=question, tool_ids=tool_ids)

    def _execute_sequential(
        self,
        question: str,
        tool_ids: list[str],
    ) -> list[McpToolCallResult]:
        calls: list[McpToolCallResult] = []
        for tool_id in tool_ids:
            result = self._execute_single_tool(question=question, tool_id=tool_id)
            calls.append(result)
            if result.is_error and self.settings.mcp_fail_fast:
                break
        return calls

    def _execute_parallel(
        self,
        question: str,
        tool_ids: list[str],
    ) -> list[McpToolCallResult]:
        indexed_results: dict[int, McpToolCallResult] = {}
        max_workers = min(self._parallel_max_workers, len(tool_ids))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._execute_single_tool, question, tool_id): (index, tool_id)
                for index, tool_id in enumerate(tool_ids)
            }
            first_error_index: int | None = None

            for future in as_completed(futures):
                index, tool_id = futures[future]
                try:
                    indexed_results[index] = future.result()
                except Exception as exc:
                    indexed_results[index] = self._build_error_result(
                        tool_id=tool_id,
                        arguments={},
                        exc=exc,
                    )

                if indexed_results[index].is_error and self.settings.mcp_fail_fast:
                    if first_error_index is None or index < first_error_index:
                        first_error_index = index
                    for pending in futures:
                        if pending is not future:
                            pending.cancel()

        ordered_indices = sorted(indexed_results)
        if self.settings.mcp_fail_fast:
            error_index = next(
                (
                    index
                    for index in ordered_indices
                    if indexed_results[index].is_error
                ),
                None,
            )
            if error_index is not None:
                ordered_indices = [
                    index for index in ordered_indices if index <= error_index
                ]

        return [indexed_results[index] for index in ordered_indices]

    def _execute_single_tool(
        self,
        question: str,
        tool_id: str,
    ) -> McpToolCallResult:
        executor = self.registry.get_executor(tool_id)
        if executor is None:
            return McpToolCallResult(
                tool_id=tool_id,
                arguments={},
                content=f"MCP tool '{tool_id}' is not registered.",
                is_error=True,
            )

        arguments: dict[str, object] = {}
        tool_definition = executor.get_definition()
        with self.trace_service.span(
            name=f"mcp.tool.{tool_id}",
            node_type="MCP_TOOL",
            input_summary=question[:120],
            metadata={
                "tool_id": tool_definition.tool_id,
                "server_name": tool_definition.server_name,
                "transport": tool_definition.transport,
                "schema_version": tool_definition.schema_version,
            },
        ) as span:
            try:
                arguments = self.parameter_extractor.extract(
                    question=question,
                    tool_definition=tool_definition,
                )
                result = executor.execute(arguments)
                if not isinstance(result, McpToolCallResult):
                    raise TypeError("executor returned an invalid MCP result")
                span.finish_success(
                    output_summary=f"is_error={result.is_error}; chars={len(result.content or '')}"
                )
                return result
            except Exception as exc:
                span.finish_error(exc)
                return self._build_error_result(
                    tool_id=tool_id,
                    arguments=arguments,
                    exc=exc,
                )

    def _build_error_result(
        self,
        tool_id: str,
        arguments: dict[str, object],
        exc: Exception,
    ) -> McpToolCallResult:
        return McpToolCallResult(
            tool_id=tool_id,
            arguments=dict(arguments),
            content=f"Tool execution failed: {exc}",
            is_error=True,
        )

    def _match_tools(self, question: str) -> list[MatchedToolCandidate]:
        lowered = question.lower()
        matched: list[MatchedToolCandidate] = []

        for tool in self.registry.list_tools():
            matched_keywords = [
                keyword
                for keyword in tool.keywords
                if keyword.lower() in lowered or keyword in question
            ]
            if not matched_keywords:
                continue

            confidence = min(0.4 + 0.15 * len(matched_keywords), 0.95)
            matched.append(
                MatchedToolCandidate(
                    tool_id=tool.tool_id,
                    confidence=confidence,
                    reason="matched keywords: " + ",".join(matched_keywords[:3]),
                )
            )

        matched.sort(key=lambda item: (-item.confidence, item.tool_id))
        return matched

