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
    NO_ANSWER_REPLY = "根据现有资料，暂时无法回答该问题。建议您联系人工客服获取更多帮助。"

    def __init__(self) -> None:
        self.settings = get_settings()

    def generate_answer(self, question: str, sources: list[ChatSourceItem]) -> str:
        provider = self._resolve_provider()
        if provider is None:
            raise RuntimeError("no llm provider is configured")

        payload = self._build_chat_payload(question=question, sources=sources, stream=False)
        data = self._post_json(provider=provider, payload=payload, path="/chat/completions")

        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("llm response did not contain choices")

        message = choices[0].get("message", {})
        content = self._extract_content(message.get("content"))
        if not content:
            raise RuntimeError("llm response did not contain text content")

        return content

    def stream_answer(self, question: str, sources: list[ChatSourceItem]) -> Iterable[str]:
        provider = self._resolve_provider()
        if provider is None:
            raise RuntimeError("no llm provider is configured")

        payload = self._build_chat_payload(question=question, sources=sources, stream=True)
        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }

        with httpx.stream(
            "POST",
            f"{provider.base_url.rstrip('/')}/chat/completions",
            json=payload,
            headers=headers,
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

    def route_knowledge_bases(
        self,
        question: str,
        knowledge_base_profiles: list[dict[str, Any]],
    ) -> dict[str, Any]:
        provider = self._resolve_provider()
        if provider is None:
            raise RuntimeError("no llm provider is configured")

        payload = {
            "model": self.settings.default_route_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是 RetriFlow 的知识库路由器。"
                        "请从候选知识库中选择最相关的 knowledge_base_ids。"
                        "只返回严格 JSON，字段必须包含 mode、knowledge_base_ids、confidence、reason。"
                        "如果没有明显匹配，请返回 mode='global' 且 knowledge_base_ids=[]。"
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

    def _post_json(
        self,
        provider: LLMProviderConfig,
        payload: dict[str, Any],
        path: str,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self.settings.llm_request_timeout_seconds) as client:
            response = client.post(
                f"{provider.base_url.rstrip('/')}{path}",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    def _build_chat_payload(
        self,
        question: str,
        sources: list[ChatSourceItem],
        stream: bool,
    ) -> dict[str, Any]:
        return {
            "model": self.settings.default_chat_model,
            "messages": [
                {
                    "role": "system",
                    "content": self._build_system_prompt(),
                },
                {
                    "role": "user",
                    "content": self._build_user_prompt(question=question, sources=sources),
                },
            ],
            "temperature": 0.1,
            "stream": stream,
        }

    def _resolve_provider(self) -> LLMProviderConfig | None:
        if self.settings.llm_api_key and self.settings.llm_base_url:
            return LLMProviderConfig(
                name=self.settings.llm_provider,
                base_url=self.settings.llm_base_url,
                api_key=self.settings.llm_api_key,
            )

        requested = self.settings.llm_provider.lower().strip()
        providers = {
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
        }

        if requested and requested not in {"auto", "disabled"}:
            provider = providers.get(requested)
            if provider and provider.api_key and provider.base_url:
                return provider
            return None

        for provider_name in ("bailian", "siliconflow", "aihubmix", "deepseek", "groq"):
            provider = providers[provider_name]
            if provider.api_key and provider.base_url:
                return provider

        return None

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
            "5. 如果多条参考资料的信息存在冲突，请指出冲突，并提醒用户优先参考更新更晚、内容更具体的资料。\n"
            "6. 回答时使用简洁、友好的语气，输出 Markdown。\n"
        )

    @staticmethod
    def _extract_content(content: object) -> str:
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            text_parts = [item.get("text", "") for item in content if isinstance(item, dict)]
            return "".join(text_parts).strip()
        return ""

    @staticmethod
    def _parse_stream_chunk(data: str) -> str:
        payload = json.loads(data)
        choices = payload.get("choices", [])
        if not choices:
            return ""

        delta = choices[0].get("delta", {})
        if "content" in delta:
            return RetriFlowLLMService._extract_content(delta.get("content"))

        message = choices[0].get("message", {})
        return RetriFlowLLMService._extract_content(message.get("content"))

    @classmethod
    def _build_user_prompt(cls, question: str, sources: list[ChatSourceItem]) -> str:
        return (
            "【参考资料】\n\n"
            f"{cls._build_retrieved_context(sources)}\n\n"
            "【用户问题】\n"
            f"{question}"
        )

    @staticmethod
    def _build_retrieved_context(sources: list[ChatSourceItem]) -> str:
        if not sources:
            return "暂无可用参考资料。"

        blocks: list[str] = []
        for index, source in enumerate(sources[:5], start=1):
            meta_lines = [f"[{index}] 来源：{source.document_title}"]
            if source.source_updated_at:
                meta_lines.append(f"更新时间：{source.source_updated_at}")
            meta_lines.append(f"知识库：{source.knowledge_base_id}")
            block = "\n".join(meta_lines + [source.content])
            blocks.append(block)
        return "\n\n".join(blocks)

    @staticmethod
    def _build_route_prompt(question: str, knowledge_base_profiles: list[dict[str, Any]]) -> str:
        serialized_profiles = json.dumps(knowledge_base_profiles, ensure_ascii=False, indent=2)
        return (
            f"用户问题：\n{question}\n\n"
            f"候选知识库画像：\n{serialized_profiles}\n\n"
            "请选择最相关的 knowledge_base_ids。"
            "如果没有明显匹配，请返回 mode=global 和空 knowledge_base_ids。"
        )
