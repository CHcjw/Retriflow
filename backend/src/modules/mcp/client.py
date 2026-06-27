from __future__ import annotations

from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
from typing import Any

import httpx

from modules.mcp.models import McpToolCallResult, McpToolDefinition


@dataclass
class RemoteMcpServerConfig:
    name: str
    url: str = ""
    command: str = ""
    args: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 15
    stdio_framing: str = "json_lines"

    @property
    def transport(self) -> str:
        return "stdio" if self.command else "remote_http"


class RetriFlowRemoteMcpClient:
    _request_counter = itertools.count(1)

    def __init__(self, server_config: RemoteMcpServerConfig) -> None:
        self.server_config = server_config
        self._http_initialized = False
        self._http_session_id = ""

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
                    parameter_schema=self._normalize_parameter_schema(tool),
                    keywords=self._extract_keywords(tool),
                    server_name=self.server_config.name,
                    transport=self.server_config.transport,
                )
            )
        return [definition for definition in definitions if definition.tool_id]

    @classmethod
    def _normalize_parameter_schema(cls, tool: dict[str, Any]) -> dict[str, Any]:
        raw_schema = tool.get("inputSchema")
        if not isinstance(raw_schema, dict):
            raw_schema = tool.get("input_schema")
        if not isinstance(raw_schema, dict):
            raw_schema = tool.get("parameters")
        if not isinstance(raw_schema, dict):
            function = tool.get("function")
            raw_schema = function.get("parameters") if isinstance(function, dict) else {}
        if not isinstance(raw_schema, dict):
            return {"type": "object", "properties": {}, "required": []}

        schema = dict(raw_schema)
        if "properties" not in schema:
            schema = {"type": "object", "properties": schema}
        schema.setdefault("type", "object")
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            schema["properties"] = {}
        required = schema.get("required")
        if not isinstance(required, list):
            schema["required"] = []
        return schema

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
        sources = self._extract_sources(content_items, content)
        is_error = bool(result.get("isError", False))
        return McpToolCallResult(
            tool_id=tool_id,
            arguments=arguments,
            content=content or ("\u8fdc\u7a0b MCP \u5de5\u5177 " + tool_id + " \u672a\u8fd4\u56de\u6587\u672c\u5185\u5bb9\u3002"),
            is_error=is_error,
            sources=sources,
        )

    def _post_jsonrpc(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if self.server_config.command:
            return self._post_stdio_jsonrpc(method, params=params)

        if method not in {"initialize", "notifications/initialized"}:
            self._ensure_http_initialized()

        return self._post_http_jsonrpc(method, params=params, extra_headers=extra_headers)

    def _post_http_jsonrpc(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:

        request_id = next(self._request_counter)
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if method != "notifications/initialized":
            payload["id"] = request_id
        if params is not None:
            payload["params"] = params

        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            **self.server_config.headers,
        }
        if self._http_session_id:
            headers["mcp-session-id"] = self._http_session_id
        if extra_headers:
            headers.update(extra_headers)

        endpoint = self.server_config.url.rstrip("/")
        if not endpoint.endswith("/mcp"):
            endpoint = f"{endpoint}/mcp"

        with httpx.Client(timeout=self.server_config.timeout_seconds) as client:
            response = client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            session_id = response.headers.get("mcp-session-id")
            if session_id:
                self._http_session_id = session_id
            if method == "notifications/initialized" and not response.content:
                return {}
            body = response.json()

        if "error" in body:
            raise RuntimeError(str(body["error"]))

        result = body.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("remote mcp server returned invalid result")
        return result

    def _ensure_http_initialized(self) -> None:
        if self._http_initialized:
            return
        self._post_http_jsonrpc(
            "initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "retriflow", "version": "0.1.0"},
            },
        )
        self._post_http_jsonrpc("notifications/initialized", params={})
        self._http_initialized = True

    def _post_stdio_jsonrpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        command = self._resolve_stdio_command(self.server_config.command)
        process = subprocess.Popen(
            [command, *self.server_config.args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, **self.server_config.env} if self.server_config.env else None,
            text=False,
        )
        try:
            init_result = self._stdio_request(
                process,
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "retriflow", "version": "0.1.0"},
                },
            )
            if not isinstance(init_result, dict):
                raise RuntimeError("stdio mcp initialize returned invalid result")
            self._stdio_notification(process, "notifications/initialized", {})
            return self._stdio_request(process, method, params or {})
        finally:
            self._terminate_stdio_process(process)

    def _stdio_request(
        self,
        process: subprocess.Popen,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        request_id = next(self._request_counter)
        self._write_stdio_message(
            process,
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            },
        )
        while True:
            message = self._read_stdio_message_with_timeout(process)
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise RuntimeError(str(message["error"]))
            result = message.get("result")
            if not isinstance(result, dict):
                raise RuntimeError("stdio mcp response has invalid result")
            return result

    def _stdio_notification(self, process: subprocess.Popen, method: str, params: dict[str, Any]) -> None:
        self._write_stdio_message(
            process,
            {
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
            },
        )

    def _write_stdio_message(self, process: subprocess.Popen, payload: dict[str, Any]) -> None:
        if process.stdin is None:
            raise RuntimeError("stdio mcp stdin is not available")
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if self.server_config.stdio_framing == "content_length":
            process.stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
        else:
            process.stdin.write(body + b"\n")
        process.stdin.flush()

    def _read_stdio_message(self, process: subprocess.Popen) -> dict[str, Any]:
        if process.stdout is None:
            raise RuntimeError("stdio mcp stdout is not available")
        headers: dict[str, str] = {}
        while True:
            line = process.stdout.readline()
            if not line:
                stderr = self._read_process_stderr(process)
                raise RuntimeError(f"stdio mcp server closed stdout: {stderr}".strip())
            stripped = line.strip()
            if stripped.startswith(b"{"):
                return json.loads(stripped.decode("utf-8"))
            if line in {b"\r\n", b"\n"}:
                if "content-length" not in headers:
                    headers = {}
                    continue
                break
            decoded = line.decode("ascii", errors="ignore").strip()
            if ":" in decoded:
                key, value = decoded.split(":", 1)
                key = key.lower()
                if key == "content-length":
                    headers[key] = value.strip()
        content_length = int(headers.get("content-length", "0"))
        if content_length <= 0:
            raise RuntimeError("stdio mcp response missing content length")
        body = process.stdout.read(content_length)
        return json.loads(body.decode("utf-8"))

    def _read_stdio_message_with_timeout(self, process: subprocess.Popen) -> dict[str, Any]:
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(self._read_stdio_message, process)
        try:
            return future.result(timeout=self.server_config.timeout_seconds)
        except TimeoutError as exc:
            self._terminate_stdio_process(process)
            future.cancel()
            raise RuntimeError("stdio mcp server response timed out") from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    @staticmethod
    def _read_process_stderr(process: subprocess.Popen) -> str:
        if process.stderr is None:
            return ""
        try:
            return process.stderr.read().decode("utf-8", errors="replace").strip()
        except Exception:
            return ""

    @staticmethod
    def _terminate_stdio_process(process: subprocess.Popen) -> None:
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()

    @staticmethod
    def _resolve_stdio_command(command: str) -> str:
        if sys.platform == "win32" and command.lower() == "npx":
            resolved = shutil.which("npx.cmd") or shutil.which("npx.ps1") or shutil.which(command)
            if resolved:
                return resolved
        return command

    @staticmethod
    def _extract_keywords(tool: dict[str, Any]) -> list[str]:
        keywords = tool.get("keywords")
        if isinstance(keywords, list):
            return [str(item) for item in keywords if str(item).strip()]

        text_parts = [str(tool.get("name", "")), str(tool.get("description", ""))]
        merged = " ".join(text_parts).lower()
        inferred: list[str] = []
        for token in (
            "\u5929\u6c14",
            "\u6c14\u6e29",
            "\u6e29\u5ea6",
            "\u9884\u62a5",
            "\u641c\u7d22",
            "\u8054\u7f51",
            "\u7f51\u9875",
            "\u6d4f\u89c8\u5668",
            "\u667a\u80fd\u641c\u7d22",
            "AI\u641c\u7d22",
            "\u9500\u552e",
            "\u8425\u6536",
            "\u80a1\u7968",
            "\u80a1\u4ef7",
            "\u6c47\u7387",
            "\u822a\u73ed",
            "weather",
            "forecast",
            "temperature",
            "search",
            "web",
            "date",
        ):
            if token.lower() in merged:
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

    @classmethod
    def _extract_sources(cls, content_items: object, content_text: str) -> list[dict[str, str]]:
        candidates: list[dict[str, str]] = []
        cls._collect_sources(content_items, candidates)
        for parsed in cls._parse_json_candidates(content_text):
            cls._collect_sources(parsed, candidates)

        for url in re.findall(r"https?://[^\s\])}>\"]+", content_text or ""):
            candidates.append({"title": url, "url": url, "snippet": ""})

        deduped: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in candidates:
            url = str(item.get("url", "")).strip()
            if not url or url in seen:
                continue
            seen.add(url)
            title = str(item.get("title", "")).strip() or url
            snippet = str(item.get("snippet", "")).strip()
            deduped.append({"title": title[:160], "url": url, "snippet": snippet[:300]})
        return deduped[:10]

    @classmethod
    def _collect_sources(cls, value: object, candidates: list[dict[str, str]]) -> None:
        if isinstance(value, list):
            for item in value:
                cls._collect_sources(item, candidates)
            return
        if not isinstance(value, dict):
            return

        url = cls._first_string(value, ("url", "link", "href", "source_url", "sourceUrl", "web_url", "webUrl"))
        if url and url.startswith(("http://", "https://")):
            candidates.append(
                {
                    "title": cls._first_string(value, ("title", "name", "site_name", "siteName")) or url,
                    "url": url,
                    "snippet": cls._first_string(value, ("snippet", "summary", "content", "text", "description")) or "",
                }
            )

        for key in ("metadata", "meta", "source", "sources", "references", "results", "items", "data"):
            if key in value:
                cls._collect_sources(value[key], candidates)

    @staticmethod
    def _first_string(value: dict[str, Any], keys: tuple[str, ...]) -> str:
        for key in keys:
            item = value.get(key)
            if isinstance(item, str) and item.strip():
                return item.strip()
        return ""

    @staticmethod
    def _parse_json_candidates(content_text: str) -> list[object]:
        text = (content_text or "").strip()
        if not text:
            return []
        candidates: list[object] = []
        for raw in (text, *re.findall(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)):
            raw = raw.strip()
            if not raw or raw[0] not in "[{":
                continue
            try:
                candidates.append(json.loads(raw))
            except Exception:
                continue
        return candidates
