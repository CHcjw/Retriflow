from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class McpToolDefinition:
    tool_id: str
    description: str
    parameter_schema: dict[str, Any]
    keywords: list[str] = field(default_factory=list)
    server_name: str = "builtin"
    transport: str = "builtin"
    schema_version: str = "json_schema"


@dataclass
class McpToolCallResult:
    tool_id: str
    arguments: dict[str, Any]
    content: str
    is_error: bool = False
    sources: list[dict[str, str]] = field(default_factory=list)


@dataclass
class McpRouteDecision:
    mode: str
    tool_ids: list[str]
    confidence: float
    reason: str


@dataclass
class McpExecutionResult:
    route: McpRouteDecision
    calls: list[McpToolCallResult]

    @property
    def context(self) -> str:
        if not self.calls:
            return ""

        sections: list[str] = []
        for index, call in enumerate(self.calls, start=1):
            status = "error" if call.is_error else "ok"
            lines = [
                f"[M{index}] Tool: {call.tool_id}",
                f"Status: {status}",
                f"Arguments: {call.arguments}",
                f"Result: {call.content}",
            ]
            if call.sources:
                lines.append(f"Sources: {call.sources}")
            sections.append("\n".join(lines))
        return "\n\n".join(sections)

