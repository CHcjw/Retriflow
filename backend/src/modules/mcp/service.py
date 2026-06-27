from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
import re

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

    def route_question(self, question: str, *, memory_messages: list[dict[str, str]] | None = None) -> McpRouteDecision:
        route_question = self._resolve_route_question(question, memory_messages or [])
        matched = self._match_tools(route_question)
        matched = self._prefer_search_for_web_intent(route_question, matched)
        matched = self._prefer_remote_weather_for_realtime_question(route_question, matched)
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

        prefix = "contextual follow-up; " if route_question != question else ""
        return McpRouteDecision(
            mode="mcp",
            tool_ids=[candidate.tool_id for candidate in selected],
            confidence=selected[0].confidence,
            reason=prefix
            + "; ".join(
                f"{candidate.tool_id}: {candidate.reason}" for candidate in selected
            ),
        )

    def _prefer_search_for_web_intent(
        self,
        question: str,
        matched: list[MatchedToolCandidate],
    ) -> list[MatchedToolCandidate]:
        if not self._looks_like_web_search_question(question):
            return matched
        search_tool_id = self._find_preferred_search_tool_id()
        if not search_tool_id:
            return matched
        without_duplicate = [candidate for candidate in matched if candidate.tool_id != search_tool_id]
        return [
            MatchedToolCandidate(
                tool_id=search_tool_id,
                confidence=0.98,
                reason="explicit web search intent prefers search MCP",
            ),
            *without_duplicate,
        ]

    def _prefer_remote_weather_for_realtime_question(
        self,
        question: str,
        matched: list[MatchedToolCandidate],
    ) -> list[MatchedToolCandidate]:
        if not self._looks_like_weather_question(question):
            return matched
        remote_weather_tool_id = self._find_preferred_weather_tool_id()
        if remote_weather_tool_id:
            without_builtin_weather = [
                candidate
                for candidate in matched
                if candidate.tool_id not in {remote_weather_tool_id, "weather_query"}
            ]
            return [
                MatchedToolCandidate(
                    tool_id=remote_weather_tool_id,
                    confidence=0.98,
                    reason="weather question prefers remote weather mcp",
                ),
                *without_builtin_weather,
            ]
        search_tool_id = self._find_preferred_search_tool_id()
        if search_tool_id:
            without_builtin_weather = [
                candidate
                for candidate in matched
                if candidate.tool_id not in {search_tool_id, "weather_query"}
            ]
            return [
                MatchedToolCandidate(
                    tool_id=search_tool_id,
                    confidence=0.96,
                    reason="weather question falls back to search mcp",
                ),
                *without_builtin_weather,
            ]
        return matched

    def _find_preferred_search_tool_id(self) -> str:
        tools = self.registry.list_tools()
        for tool in tools:
            tool_id = tool.tool_id.lower()
            text = f"{tool.server_name} {tool.tool_id} {tool.description}".lower()
            if "aisearch" in tool_id or "ai_search" in tool_id or "百度ai搜索" in text:
                return tool.tool_id
        for tool in tools:
            tool_id = tool.tool_id.lower()
            text = f"{tool.server_name} {tool.tool_id} {tool.description}".lower()
            if "search_location" in tool_id:
                continue
            if "search" in tool_id or "搜索" in text or "web" in text:
                return tool.tool_id
        return ""

    def _find_preferred_weather_tool_id(self) -> str:
        for preferred in ("get_forecast", "get_current_conditions", "weather"):
            executor = self.registry.get_executor(preferred)
            if executor and executor.get_definition().server_name != "builtin":
                return preferred
        for tool in self.registry.list_tools():
            if tool.server_name == "builtin":
                continue
            tool_id = tool.tool_id.lower()
            text = f"{tool.server_name} {tool.tool_id} {tool.description}".lower()
            if "search_location" in tool_id:
                continue
            if "weather" in text or "forecast" in tool_id or "conditions" in tool_id:
                return tool.tool_id
        return ""

    def execute_question(
        self,
        question: str,
        *,
        memory_messages: list[dict[str, str]] | None = None,
        forced_tool_ids: list[str] | None = None,
        forced_tool_param_prompts: dict[str, str] | None = None,
    ) -> McpExecutionResult:
        route_question = self._resolve_route_question(question, memory_messages or [])
        if forced_tool_ids:
            route = McpRouteDecision(
                mode="mcp",
                tool_ids=list(dict.fromkeys(forced_tool_ids)),
                confidence=0.99,
                reason="intent tree selected mcp tools",
            )
        else:
            route = self.route_question(question, memory_messages=memory_messages)
        if route.mode != "mcp" or not route.tool_ids:
            return McpExecutionResult(route=route, calls=[])

        execution_question = self._with_current_date_context(route_question)
        calls = self._execute_tools(
            question=execution_question,
            tool_ids=route.tool_ids,
            tool_param_prompts=forced_tool_param_prompts or {},
        )
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

    def _execute_tools(
        self,
        question: str,
        tool_ids: list[str],
        tool_param_prompts: dict[str, str] | None = None,
    ) -> list[McpToolCallResult]:
        if self.settings.mcp_fail_fast:
            return self._execute_sequential(
                question=question,
                tool_ids=tool_ids,
                tool_param_prompts=tool_param_prompts or {},
            )
        if self._execution_mode == "parallel" and len(tool_ids) > 1:
            return self._execute_parallel(
                question=question,
                tool_ids=tool_ids,
                tool_param_prompts=tool_param_prompts or {},
            )
        return self._execute_sequential(
            question=question,
            tool_ids=tool_ids,
            tool_param_prompts=tool_param_prompts or {},
        )

    def _execute_sequential(
        self,
        question: str,
        tool_ids: list[str],
        tool_param_prompts: dict[str, str] | None = None,
    ) -> list[McpToolCallResult]:
        calls: list[McpToolCallResult] = []
        for tool_id in tool_ids:
            result = self._execute_single_tool(
                question=question,
                tool_id=tool_id,
                param_prompt_template=(tool_param_prompts or {}).get(tool_id, ""),
            )
            calls.append(result)
            if result.is_error and self.settings.mcp_fail_fast:
                break
        return calls

    def _execute_parallel(
        self,
        question: str,
        tool_ids: list[str],
        tool_param_prompts: dict[str, str] | None = None,
    ) -> list[McpToolCallResult]:
        indexed_results: dict[int, McpToolCallResult] = {}
        max_workers = min(self._parallel_max_workers, len(tool_ids))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    self._execute_single_tool,
                    question,
                    tool_id,
                    (tool_param_prompts or {}).get(tool_id, ""),
                ): (index, tool_id)
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
        param_prompt_template: str = "",
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
                "param_prompt_template": bool(param_prompt_template.strip()),
            },
        ) as span:
            try:
                arguments = self.parameter_extractor.extract(
                    question=question,
                    tool_definition=tool_definition,
                    param_prompt_template=param_prompt_template,
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

    @staticmethod
    def _looks_like_weather_question(question: str) -> bool:
        return bool(
            re.search(
                r"\u5929\u6c14|\u6c14\u6e29|\u6e29\u5ea6|\u4e0b\u96e8|\u964d\u96e8|\u9884\u62a5|\u7a7a\u6c14\u8d28\u91cf|weather|temperature|forecast|rain",
                question,
                re.I,
            )
        )

    @staticmethod
    def _looks_like_web_search_question(question: str) -> bool:
        return bool(
            re.search(
                r"\u8054\u7f51|\u641c\u7d22|\u7f51\u9875|\u6d4f\u89c8\u5668|\u67e5\u7f51\u9875|\u7f51\u4e0a\u67e5|\u4e0a\u7f51\u67e5|\u4e0a\u7f51\u641c\u7d22|\u767e\u5ea6|online|search|web",
                question,
                re.I,
            )
        )

    def _resolve_route_question(self, question: str, memory_messages: list[dict[str, str]]) -> str:
        if self._match_tools(question):
            return question
        if not self._looks_like_tool_follow_up(question):
            return question

        previous_user_question = self._latest_user_question(memory_messages)
        if not previous_user_question or not self._match_tools(previous_user_question):
            return question

        return f"{previous_user_question}\n\u8ffd\u95ee\uff1a{question}"

    @staticmethod
    def _with_current_date_context(question: str) -> str:
        if not re.search(
            r"\u4eca\u5929|\u4eca\u65e5|\u73b0\u5728|\u660e\u5929|\u540e\u5929|\u672c\u5468|\u672c\u6708|\u672c\u5b63\u5ea6|today|tomorrow|this week|this month",
            question,
            re.I,
        ):
            return question
        now = datetime.now().astimezone()
        weekday = "\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u65e5"[now.weekday()]
        context = (
            f"\u5f53\u524d\u65e5\u671f\uff1a{now.year}-{now.month:02d}-{now.day:02d}\uff0c\u661f\u671f{weekday}\u3002"
            "\u8bf7\u6309\u8fd9\u4e2a\u65e5\u671f\u89e3\u6790\u201c\u4eca\u5929\u3001\u660e\u5929\u3001\u672c\u5468\u3001\u672c\u6708\u201d\u7b49\u76f8\u5bf9\u65f6\u95f4\u8bcd\u3002"
        )
        if context in question:
            return question
        return f"{question}\n{context}"

    @staticmethod
    def _looks_like_tool_follow_up(question: str) -> bool:
        normalized = question.strip()
        if not normalized:
            return False
        return bool(
            re.search(
                r"^(\u672a\u6765|\u660e\u5929|\u540e\u5929|\u5927\u540e\u5929|\u63a5\u4e0b\u6765|\u4e4b\u540e|\u90a3|\u8fd9\u4e2a|\u90a3\u4e2a|\u518d\u67e5|\u8fd8\u6709|\u5462|.*\u5462?)",
                normalized,
            )
            or re.search(
                r"(\u672a\u6765|\u660e\u5929|\u540e\u5929|\u4e09\u5929|\u51e0\u5929|\u672c\u5468|\u672c\u6708|\u672c\u5b63\u5ea6).{0,8}(\u5462|\u600e\u4e48\u6837|\u5982\u4f55|\u60c5\u51b5)?$",
                normalized,
            )
        )

    @staticmethod
    def _latest_user_question(memory_messages: list[dict[str, str]]) -> str:
        for message in reversed(memory_messages):
            if str(message.get("role", "")).lower() != "user":
                continue
            content = str(message.get("content", "")).strip()
            if content:
                return content
        return ""
