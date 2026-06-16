from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import json
from typing import Any

import httpx

from core.config import get_settings
from schemas.chat import ChatSourceItem


@dataclass
class LLMProviderConfig:
    name: str
    base_url: str
    api_key: str


class RetriFlowLLMService:
    NO_ANSWER_REPLY = (
        "根据现有资料，暂时无法回答该问题。"
        "建议您联系人工客服获取更多帮助。"
    )

    def __init__(self) -> None:
        self.settings = get_settings()

    def generate_answer(
        self,
        question: str,
        sources: list[ChatSourceItem],
        extra_context: str = "",
        memory_messages: list[dict[str, str]] | None = None,
        deep_thinking: bool = False,
    ) -> str:
        provider = self._resolve_provider(capability="chat")
        if provider is None:
            raise RuntimeError("no chat provider is configured")

        payload = self._build_chat_payload(
            question=question,
            sources=sources,
            extra_context=extra_context,
            memory_messages=memory_messages or [],
            stream=False,
            model=self._resolve_chat_model(provider.name, deep_thinking=deep_thinking),
        )
        data = self._post_json(provider=provider, payload=payload, path="/chat/completions")
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("llm response did not contain choices")

        message = choices[0].get("message", {})
        content = self._extract_content(message.get("content"))
        if not content:
            raise RuntimeError("llm response did not contain text content")
        return content

    def generate_general_answer(
        self,
        question: str,
        memory_messages: list[dict[str, str]] | None = None,
        deep_thinking: bool = False,
    ) -> str:
        provider = self._resolve_provider(capability="chat")
        if provider is None:
            raise RuntimeError("no chat provider is configured")

        payload = {
            "model": self._resolve_chat_model(provider.name, deep_thinking=deep_thinking),
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是 RetriFlow 的对话助手。"
                        "当用户在闲聊、寒暄或咨询系统能力时，请直接自然回答。"
                        "如果问题更适合知识库检索或工具调用，不要编造外部事实，"
                        "可以简短说明你可以继续帮助检索或调用工具。"
                    ),
                },
                *self._sanitize_memory_messages(memory_messages or []),
                {"role": "user", "content": question},
            ],
            "temperature": 0.4,
            "stream": False,
        }
        data = self._post_json(provider=provider, payload=payload, path="/chat/completions")
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("llm response did not contain choices")

        message = choices[0].get("message", {})
        content = self._extract_content(message.get("content"))
        if not content:
            raise RuntimeError("llm response did not contain text content")
        return content

    def stream_answer(
        self,
        question: str,
        sources: list[ChatSourceItem],
        extra_context: str = "",
        memory_messages: list[dict[str, str]] | None = None,
        deep_thinking: bool = False,
    ) -> Iterable[str]:
        provider = self._resolve_provider(capability="chat")
        if provider is None:
            raise RuntimeError("no chat provider is configured")

        payload = self._build_chat_payload(
            question=question,
            sources=sources,
            extra_context=extra_context,
            memory_messages=memory_messages or [],
            stream=True,
            model=self._resolve_chat_model(provider.name, deep_thinking=deep_thinking),
        )

        with httpx.stream(
            "POST",
            f"{provider.base_url.rstrip('/')}/chat/completions",
            json=payload,
            headers=self._build_headers(provider),
            timeout=self.settings.llm_request_timeout_seconds,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                decoded = line.decode("utf-8") if isinstance(line, bytes) else line
                if not decoded.startswith("data:"):
                    continue
                data = decoded[5:].strip()
                if data == "[DONE]":
                    break
                chunk = self._parse_stream_chunk(data)
                if chunk:
                    yield chunk

    def summarize_conversation(
        self,
        *,
        existing_summary: str,
        conversation_messages: list[dict[str, str]],
        max_chars: int,
    ) -> str:
        provider = self._resolve_provider(capability="memory_summary")
        if provider is None:
            raise RuntimeError("no memory summary provider is configured")

        normalized_messages = self._sanitize_memory_messages(conversation_messages)
        if not normalized_messages:
            return existing_summary.strip()

        payload = {
            "model": self._resolve_model(
                capability="memory_summary",
                provider_name=provider.name,
            ),
            "messages": [
                {
                    "role": "system",
                    "content": self._build_summary_system_prompt(max_chars=max_chars),
                },
                {
                    "role": "user",
                    "content": self._build_summary_user_prompt(
                        existing_summary=existing_summary,
                        conversation_messages=normalized_messages,
                        max_chars=max_chars,
                    ),
                },
            ],
            "temperature": 0.1,
            "stream": False,
        }
        data = self._post_json(provider=provider, payload=payload, path="/chat/completions")
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("llm summary response did not contain choices")

        message = choices[0].get("message", {})
        content = self._extract_content(message.get("content"))
        if not content:
            raise RuntimeError("llm summary response did not contain content")
        return content[:max_chars].strip()

    def route_knowledge_bases(
        self,
        question: str,
        knowledge_base_profiles: list[dict[str, Any]],
    ) -> dict[str, Any]:
        provider = self._resolve_provider(capability="route")
        if provider is None:
            raise RuntimeError("no route provider is configured")

        payload = {
            "model": self._resolve_model(capability="route", provider_name=provider.name),
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是 RetriFlow 的知识库路由器。"
                        "请从候选知识库中选择与用户问题最相关的 knowledge_base_ids。"
                        "只返回严格 JSON，必须包含 mode、knowledge_base_ids、confidence、reason。"
                        "如果没有明显匹配，请返回 mode=global 且 knowledge_base_ids=[]."
                    ),
                },
                {
                    "role": "user",
                    "content": self._build_route_prompt(
                        question=question,
                        knowledge_base_profiles=knowledge_base_profiles,
                    ),
                },
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        data = self._post_json(provider=provider, payload=payload, path="/chat/completions")
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("llm route response did not contain choices")

        message = choices[0].get("message", {})
        content = self._extract_content(message.get("content"))
        if not content:
            raise RuntimeError("llm route response did not contain content")
        return json.loads(content)

    def extract_json_object(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        capability: str = "chat",
    ) -> dict[str, Any]:
        provider = self._resolve_provider(capability=capability)
        if provider is None:
            raise RuntimeError("no llm provider is configured")

        payload = {
            "model": model or self._resolve_model(capability=capability, provider_name=provider.name),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        data = self._post_json(provider=provider, payload=payload, path="/chat/completions")
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("llm json response did not contain choices")

        message = choices[0].get("message", {})
        content = self._extract_content(message.get("content"))
        if not content:
            raise RuntimeError("llm json response did not contain content")
        return json.loads(content)

    def _post_json(
        self,
        provider: LLMProviderConfig,
        payload: dict[str, Any],
        path: str,
    ) -> dict[str, Any]:
        with httpx.Client(timeout=self.settings.llm_request_timeout_seconds) as client:
            response = client.post(
                f"{provider.base_url.rstrip('/')}{path}",
                json=payload,
                headers=self._build_headers(provider),
            )
            response.raise_for_status()
            return response.json()

    def _build_headers(self, provider: LLMProviderConfig) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if provider.api_key:
            headers["Authorization"] = f"Bearer {provider.api_key}"
        return headers

    def _build_chat_payload(
        self,
        question: str,
        sources: list[ChatSourceItem],
        extra_context: str,
        memory_messages: list[dict[str, str]],
        stream: bool,
        model: str,
    ) -> dict[str, Any]:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": self._build_system_prompt()},
        ]
        messages.extend(self._sanitize_memory_messages(memory_messages))
        messages.append(
            {
                "role": "user",
                "content": self._build_user_prompt(
                    question=question,
                    sources=sources,
                    extra_context=extra_context,
                ),
            }
        )
        return {
            "model": model,
            "messages": messages,
            "temperature": 0.1,
            "stream": stream,
        }

    def _resolve_provider(self, capability: str = "chat") -> LLMProviderConfig | None:
        requested = self._resolve_provider_name(capability)
        if requested == "disabled":
            return LLMProviderConfig(
                name="disabled",
                base_url="http://127.0.0.1:9",
                api_key="disabled",
            )
        if requested == "custom":
            if self.settings.llm_api_key and self.settings.llm_base_url:
                return LLMProviderConfig(
                    name="custom",
                    base_url=self.settings.llm_base_url,
                    api_key=self.settings.llm_api_key,
                )
            return None

        providers = self._provider_registry()
        if requested and requested not in {"auto", "chat"}:
            provider = providers.get(requested)
            if provider and self._provider_is_available(provider):
                return provider
            return None

        for provider_name in self._provider_fallback_order(capability):
            provider = providers.get(provider_name)
            if provider and self._provider_is_available(provider):
                return provider
        return None

    def _resolve_model(self, capability: str, provider_name: str) -> str:
        if provider_name == "ollama":
            if capability == "embedding":
                return self.settings.ollama_embedding_model
            return self.settings.ollama_chat_model

        if capability == "route":
            return self.settings.default_route_model
        if capability == "rerank":
            return self.settings.default_rerank_model
        if capability == "embedding":
            return self.settings.default_embedding_model
        return self.settings.default_chat_model

    def _resolve_chat_model(self, provider_name: str, *, deep_thinking: bool) -> str:
        if provider_name == "ollama":
            return self.settings.ollama_chat_model
        if deep_thinking:
            return self.settings.deep_thinking_model or self.settings.default_chat_model
        return self.settings.default_chat_model

    def _resolve_provider_name(self, capability: str) -> str:
        capability_map = {
            "chat": self.settings.chat_provider,
            "intent": self.settings.intent_provider,
            "rewrite": self.settings.rewrite_provider,
            "route": self.settings.route_provider,
            "memory_summary": self.settings.memory_summary_provider,
            "embedding": self.settings.embedding_provider,
            "rerank": self.settings.rerank_provider,
        }
        requested = capability_map.get(capability, "auto").strip().lower()
        legacy = self.settings.llm_provider.strip().lower()
        if legacy == "disabled":
            return "disabled"
        if requested == "chat" and capability != "chat":
            return self._resolve_provider_name("chat")
        if requested in {"", "auto"}:
            if legacy and legacy not in {"auto", "disabled"}:
                return legacy
            return "auto"
        return requested

    def _provider_registry(self) -> dict[str, LLMProviderConfig]:
        return {
            "bailian": LLMProviderConfig(
                name="bailian",
                base_url=self.settings.dashscope_base_url,
                api_key=self.settings.bailian_api_key,
            ),
            "aihubmix": LLMProviderConfig(
                name="aihubmix",
                base_url=self.settings.aihubmix_base_url,
                api_key=self.settings.aihubmix_api_key,
            ),
            "siliconflow": LLMProviderConfig(
                name="siliconflow",
                base_url=self.settings.siliconflow_base_url,
                api_key=self.settings.siliconflow_api_key,
            ),
            "deepseek": LLMProviderConfig(
                name="deepseek",
                base_url=self.settings.deepseek_base_url,
                api_key=self.settings.deepseek_api_key,
            ),
            "groq": LLMProviderConfig(
                name="groq",
                base_url=self.settings.groq_base_url,
                api_key=self.settings.groq_api_key,
            ),
            "ollama": LLMProviderConfig(
                name="ollama",
                base_url=self.settings.ollama_base_url,
                api_key="",
            ),
        }

    def _provider_fallback_order(self, capability: str) -> tuple[str, ...]:
        if capability == "embedding":
            return ("siliconflow", "bailian", "aihubmix", "deepseek", "ollama", "groq")
        if capability == "rerank":
            return ("siliconflow", "bailian", "aihubmix", "deepseek")
        if capability in {"intent", "rewrite", "route", "memory_summary"}:
            return ("ollama", "bailian", "siliconflow", "aihubmix", "deepseek", "groq")
        return ("bailian", "siliconflow", "aihubmix", "deepseek", "groq", "ollama")

    @staticmethod
    def _provider_is_available(provider: LLMProviderConfig) -> bool:
        if not provider.base_url:
            return False
        if provider.name in {"ollama", "disabled"}:
            return True
        return bool(provider.api_key)

    @classmethod
    def _build_system_prompt(cls) -> str:
        return (
            "【System】\n"
            "你是一名专业的知识库问答助手。你的任务是根据【参考资料】中的信息，准确回答用户的问题。\n\n"
            "请严格遵守以下规则：\n"
            "1. 只基于【参考资料】中的内容回答问题，不要使用你自己的知识。\n"
            f"2. 如果【参考资料】中没有足够的信息来回答用户的问题，请明确回答：\"{cls.NO_ANSWER_REPLY}\"\n"
            "3. 不要编造任何【参考资料】中没有提到的信息，包括数字、日期、金额等具体细节。\n"
            "4. 回答时请引用参考资料的编号，格式为 [1]、[2] 等，标注在相关句子的末尾。\n"
            "5. 如果多条参考资料的信息存在冲突，请指出冲突，并提醒用户优先参考更新时间更晚、内容更具体的资料。\n"
            "6. 用简洁、友好的语气回答，输出 Markdown。\n"
        )

    @classmethod
    def _build_user_prompt(
        cls,
        question: str,
        sources: list[ChatSourceItem],
        extra_context: str = "",
    ) -> str:
        sections = ["【参考资料】", cls._build_retrieved_context(sources)]
        if extra_context.strip():
            sections.extend(["", "【工具结果】", extra_context.strip()])
        sections.extend(["", "【用户问题】", question])
        return "\n".join(sections).strip()

    @staticmethod
    def _build_retrieved_context(sources: list[ChatSourceItem]) -> str:
        if not sources:
            return "暂无可用参考资料。"

        blocks: list[str] = []
        for index, source in enumerate(sources[:5], start=1):
            lines = [f"[{index}] 来源：{source.document_title}"]
            if source.source_updated_at:
                lines.append(f"更新时间：{source.source_updated_at}")
            lines.append(f"知识库：{source.knowledge_base_id}")
            lines.append(source.content)
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

    @staticmethod
    def _build_route_prompt(question: str, knowledge_base_profiles: list[dict[str, Any]]) -> str:
        profiles_json = json.dumps(knowledge_base_profiles, ensure_ascii=False, indent=2)
        return (
            f"用户问题：\n{question}\n\n"
            f"候选知识库画像：\n{profiles_json}\n\n"
            "请选择最相关的 knowledge_base_ids。"
            "如果没有明显匹配，请返回 mode=global 且 knowledge_base_ids=[]."
        )

    @staticmethod
    def _build_summary_system_prompt(max_chars: int) -> str:
        return (
            "你是 RetriFlow 的对话记忆摘要器。"
            "请把对话中已经完成的讨论内容压缩成面向后续问答的短期记忆摘要。"
            "重点保留用户目标、关键约束、已确认结论、待确认事项。"
            f"输出纯文本，不要分点，不要使用 Markdown，总长度不要超过 {max_chars} 个字符。"
        )

    @staticmethod
    def _build_summary_user_prompt(
        *,
        existing_summary: str,
        conversation_messages: list[dict[str, str]],
        max_chars: int,
    ) -> str:
        lines = [
            "【已有摘要】",
            existing_summary.strip() or "无",
            "",
            "【新增对话】",
        ]
        for message in conversation_messages:
            role = "用户" if message["role"] == "user" else "助手"
            lines.append(f"{role}：{message['content']}")
        lines.extend(
            [
                "",
                "【要求】",
                "请将已有摘要与新增对话整合为新的摘要。",
                "只保留后续问答真正需要的上下文。",
                f"最终摘要不要超过 {max_chars} 个字符。",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _sanitize_memory_messages(memory_messages: list[dict[str, str]]) -> list[dict[str, str]]:
        sanitized: list[dict[str, str]] = []
        for message in memory_messages:
            role = str(message.get("role", "")).strip()
            content = str(message.get("content", "")).strip()
            if role not in {"system", "user", "assistant"}:
                continue
            if not content:
                continue
            sanitized.append({"role": role, "content": content})
        return sanitized

    @staticmethod
    def _extract_content(content: object) -> str:
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = [item.get("text", "") for item in content if isinstance(item, dict)]
            return "".join(parts).strip()
        return ""

    @classmethod
    def _parse_stream_chunk(cls, data: str) -> str:
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            return ""

        choices = payload.get("choices", [])
        if not choices:
            return ""

        delta = choices[0].get("delta", {})
        if "content" in delta:
            return cls._extract_content(delta.get("content"))

        message = choices[0].get("message", {})
        return cls._extract_content(message.get("content"))
