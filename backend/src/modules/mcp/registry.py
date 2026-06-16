from __future__ import annotations

import json

from core.config import get_settings
from modules.mcp.client import RemoteMcpServerConfig, RetriFlowRemoteMcpClient
from modules.mcp.executors import (
    RetriFlowMcpToolExecutor,
    SalesMcpToolExecutor,
    WeatherMcpToolExecutor,
)
from modules.mcp.models import McpToolDefinition


class RemoteMcpToolExecutor(RetriFlowMcpToolExecutor):
    def __init__(self, client: RetriFlowRemoteMcpClient, definition: McpToolDefinition) -> None:
        self.client = client
        self.definition = definition

    def get_definition(self) -> McpToolDefinition:
        return self.definition

    def execute(self, arguments: dict[str, object]):
        return self.client.call_tool(self.definition.tool_id, dict(arguments))


class RetriFlowMcpRegistry:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._executors: dict[str, RetriFlowMcpToolExecutor] = {}
        self._register_builtin_tools()
        self._register_remote_tools()

    def _register_builtin_tools(self) -> None:
        for executor in (WeatherMcpToolExecutor(), SalesMcpToolExecutor()):
            self.register(executor)

    def _register_remote_tools(self) -> None:
        if not self.settings.mcp_remote_enabled:
            return

        for server in self._load_remote_servers():
            client = RetriFlowRemoteMcpClient(server)
            for tool in client.list_tools():
                self.register(RemoteMcpToolExecutor(client=client, definition=tool))

    def _load_remote_servers(self) -> list[RemoteMcpServerConfig]:
        raw = self.settings.mcp_remote_servers_json.strip()
        if not raw:
            return []

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return []

        if not isinstance(payload, list):
            return []

        servers: list[RemoteMcpServerConfig] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            url = str(item.get("url", "")).strip()
            if not name or not url:
                continue
            headers = item.get("headers", {})
            timeout_seconds = int(item.get("timeout_seconds", self.settings.mcp_remote_timeout_seconds))
            servers.append(
                RemoteMcpServerConfig(
                    name=name,
                    url=url,
                    headers=headers if isinstance(headers, dict) else {},
                    timeout_seconds=timeout_seconds,
                )
            )
        return servers

    def register(self, executor: RetriFlowMcpToolExecutor) -> None:
        definition = executor.get_definition()
        self._executors[definition.tool_id] = executor

    def get_executor(self, tool_id: str) -> RetriFlowMcpToolExecutor | None:
        return self._executors.get(tool_id)

    def list_tools(self) -> list[McpToolDefinition]:
        return [executor.get_definition() for executor in self._executors.values()]

