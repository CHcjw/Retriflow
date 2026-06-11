from __future__ import annotations

from dataclasses import dataclass, field
import itertools
from typing import Any

import httpx

from domain.mcp.models import McpToolCallResult, McpToolDefinition


@dataclass
class RemoteMcpServerConfig:
    name: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 15


class RetriFlowRemoteMcpClient:
    _request_counter = itertools.count(1)

    def __init__(self, server_config: RemoteMcpServerConfig) -> None:
        self.server_config = server_config

    def list_tools(self) -> list[McpToolDefinition]:
        result = self._post_jsonrpc("tools/list")
        tools = result.get("tools", [])
        definitions: list[McpToolDefinition] = []
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            definitions.append(
                McpToolDefinition(
                    tool_id=str(tool.get("name", "")).strip(),
                    description=str(tool.get("description", "")).strip(),
                    parameter_schema=(
                        tool.get("inputSchema", {})
                        if isinstance(tool.get("inputSchema"), dict)
                        else {}
                    ),
                    keywords=self._extract_keywords(tool),
                    server_name=self.server_config.name,
                    transport="remote_http",
                )
            )
        return [definition for definition in definitions if definition.tool_id]

    def call_tool(self, tool_id: str, arguments: dict[str, Any]) -> McpToolCallResult:
        result = self._post_jsonrpc(
            "tools/call",
            params={"name": tool_id, "arguments": arguments},
            extra_headers={
                "Mcp-Method": "tools/call",
                "Mcp-Name": tool_id,
            },
        )
        content_items = result.get("content", [])
        content = self._extract_text_content(content_items)
        is_error = bool(result.get("isError", False))
        return McpToolCallResult(
            tool_id=tool_id,
            arguments=arguments,
            content=content or f"远端 MCP 工具 {tool_id} 未返回文本内容。",
            is_error=is_error,
        )

    def _post_jsonrpc(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        request_id = next(self._request_counter)
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        headers = {"Content-Type": "application/json", **self.server_config.headers}
        if extra_headers:
            headers.update(extra_headers)

        endpoint = self.server_config.url.rstrip("/")
        if not endpoint.endswith("/mcp"):
            endpoint = f"{endpoint}/mcp"

        with httpx.Client(timeout=self.server_config.timeout_seconds) as client:
            response = client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            body = response.json()

        if "error" in body:
            raise RuntimeError(str(body["error"]))

        result = body.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("remote mcp server returned invalid result")
        return result

    @staticmethod
    def _extract_keywords(tool: dict[str, Any]) -> list[str]:
        keywords = tool.get("keywords")
        if isinstance(keywords, list):
            return [str(item) for item in keywords if str(item).strip()]

        text_parts = [str(tool.get("name", "")), str(tool.get("description", ""))]
        merged = " ".join(text_parts)
        inferred: list[str] = []
        for token in ("天气", "气温", "销售", "营收", "股票", "股价", "汇率", "航班"):
            if token in merged:
                inferred.append(token)
        return inferred

    @staticmethod
    def _extract_text_content(content_items: object) -> str:
        if not isinstance(content_items, list):
            return ""
        texts: list[str] = []
        for item in content_items:
            if isinstance(item, dict) and item.get("type") == "text":
                text = str(item.get("text", "")).strip()
                if text:
                    texts.append(text)
        return "\n".join(texts).strip()
