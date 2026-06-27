from __future__ import annotations

from dataclasses import dataclass
import json
import os

from core.config import _read_env_file, get_settings
from modules.mcp.client import RemoteMcpServerConfig, RetriFlowRemoteMcpClient
from modules.mcp.executors import (
    RetriFlowMcpToolExecutor,
    SalesMcpToolExecutor,
    TicketMcpToolExecutor,
    WeatherMcpToolExecutor,
)
from modules.mcp.models import McpToolDefinition


@dataclass(frozen=True)
class RemoteMcpServerStatus:
    name: str
    url: str
    healthy: bool
    tool_count: int
    error: str = ""


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
        self._remote_server_statuses: list[RemoteMcpServerStatus] = []
        self._register_builtin_tools()
        self._register_remote_tools()

    def _register_builtin_tools(self) -> None:
        executors: list[RetriFlowMcpToolExecutor] = [WeatherMcpToolExecutor(), SalesMcpToolExecutor(), TicketMcpToolExecutor()]
        for executor in executors:
            self.register(executor)

    def _register_remote_tools(self) -> None:
        if not self.settings.mcp_remote_enabled:
            return

        for server in self._load_remote_servers():
            client = RetriFlowRemoteMcpClient(server)
            try:
                tools = client.list_tools()
            except Exception as exc:
                self._remote_server_statuses.append(
                    RemoteMcpServerStatus(
                        name=server.name,
                        url=server.url,
                        healthy=False,
                        tool_count=0,
                        error=str(exc),
                    )
                )
                continue

            for tool in tools:
                tool.keywords = self._augment_remote_keywords(server.name, tool)
                self.register(RemoteMcpToolExecutor(client=client, definition=tool))
            self._remote_server_statuses.append(
                RemoteMcpServerStatus(
                    name=server.name,
                    url=server.url,
                    healthy=True,
                    tool_count=len(tools),
                )
            )

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
            command = str(item.get("command", "")).strip()
            args = item.get("args", [])
            if not name or (not url and not command):
                continue
            headers = item.get("headers", {})
            env = item.get("env", {})
            stdio_framing = str(item.get("stdio_framing", "json_lines")).strip() or "json_lines"
            timeout_seconds = int(item.get("timeout_seconds", self.settings.mcp_remote_timeout_seconds))
            servers.append(
                RemoteMcpServerConfig(
                    name=name,
                    url=url,
                    command=command,
                    args=[str(arg) for arg in args] if isinstance(args, list) else [],
                    headers=self._resolve_headers(headers if isinstance(headers, dict) else {}),
                    env=self._resolve_env(env if isinstance(env, dict) else {}),
                    timeout_seconds=timeout_seconds,
                    stdio_framing=stdio_framing,
                )
            )
        return servers

    @staticmethod
    def _resolve_headers(headers: dict) -> dict[str, str]:
        resolved: dict[str, str] = {}
        for key, value in headers.items():
            header_name = str(key)
            header_value = str(value)
            if header_value.startswith("env:"):
                header_value = RetriFlowMcpRegistry._lookup_env(header_value.removeprefix("env:"))
            elif header_value.startswith("Bearer env:"):
                env_name = header_value.removeprefix("Bearer env:")
                env_value = RetriFlowMcpRegistry._lookup_env(env_name)
                header_value = f"Bearer {env_value}" if env_value else ""
            if header_value:
                resolved[header_name] = header_value
        return resolved

    @staticmethod
    def _resolve_env(env: dict) -> dict[str, str]:
        resolved: dict[str, str] = {}
        for key, value in env.items():
            env_name = str(key)
            env_value = str(value)
            if env_value.startswith("env:"):
                env_value = RetriFlowMcpRegistry._lookup_env(env_value.removeprefix("env:"))
            if env_value:
                resolved[env_name] = env_value
        return resolved

    @staticmethod
    def _lookup_env(name: str) -> str:
        return os.getenv(name, _read_env_file().get(name, ""))

    @staticmethod
    def _augment_remote_keywords(server_name: str, tool: McpToolDefinition) -> list[str]:
        server = server_name.lower()
        tool_id = tool.tool_id.lower()
        text = f"{server_name} {tool.tool_id} {tool.description}".lower()
        keywords = set(tool.keywords)

        if "aisearch" in tool_id or "ai_search" in tool_id or "百度ai搜索" in text or "智能搜索" in text:
            keywords.update(
                [
                    "联网",
                    "搜索",
                    "网页",
                    "查网页",
                    "网上查",
                    "上网查",
                    "上网搜索",
                    "百度",
                    "百度搜索",
                    "AI搜索",
                    "智能搜索",
                    "实时信息",
                    "online",
                    "search",
                    "web",
                ]
            )

        if "weather" in text or "天气" in text or "forecast" in tool_id or "conditions" in tool_id:
            keywords.update(
                [
                    "天气",
                    "气温",
                    "温度",
                    "预报",
                    "下雨",
                    "降雨",
                    "空气质量",
                    "weather",
                    "forecast",
                    "temperature",
                    "rain",
                ]
            )

        return sorted(keyword for keyword in keywords if keyword.strip())

    def register(self, executor: RetriFlowMcpToolExecutor) -> None:
        definition = executor.get_definition()
        self._executors[definition.tool_id] = executor

    def get_executor(self, tool_id: str) -> RetriFlowMcpToolExecutor | None:
        return self._executors.get(tool_id)

    def list_tools(self) -> list[McpToolDefinition]:
        return [executor.get_definition() for executor in self._executors.values()]

    def remote_server_statuses(self) -> list[RemoteMcpServerStatus]:
        return list(self._remote_server_statuses)

    def list_executors(self) -> list[RetriFlowMcpToolExecutor]:
        return list(self._executors.values())

    def unregister(self, tool_id: str) -> None:
        self._executors.pop(tool_id, None)

    def contains(self, tool_id: str) -> bool:
        return tool_id in self._executors

    def size(self) -> int:
        return len(self._executors)

