from collections.abc import Iterable
from dataclasses import dataclass
import json

import httpx

from core.config import get_settings
from schemas.chat import ChatSourceItem


@dataclass
class LLMProviderConfig:
    name: str
    base_url: str
    api_key: str


class RetriFlowLLMService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def generate_answer(self, question: str, sources: list[ChatSourceItem]) -> str:
        provider = self._resolve_provider()
        if provider is None:
            raise RuntimeError("no llm provider is configured")

        payload = self._build_payload(question=question, sources=sources, stream=False)
        data = self._post_json(provider=provider, payload=payload)

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

        payload = self._build_payload(question=question, sources=sources, stream=True)
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

    def _post_json(self, provider: LLMProviderConfig, payload: dict) -> dict:
        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self.settings.llm_request_timeout_seconds) as client:
            response = client.post(
                f"{provider.base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    def _build_payload(self, question: str, sources: list[ChatSourceItem], stream: bool) -> dict:
        prompt = self._build_user_prompt(question, sources)
        return {
            "model": self.settings.default_chat_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are RetriFlow's RAG assistant. "
                        "Answer in Chinese when the user asks in Chinese. "
                        "Ground the answer in the provided context, cite the source titles when useful, "
                        "and clearly admit uncertainty if the retrieved context is insufficient."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
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

    @staticmethod
    def _build_user_prompt(question: str, sources: list[ChatSourceItem]) -> str:
        if sources:
            context_blocks = []
            for index, source in enumerate(sources[:4], start=1):
                context_blocks.append(
                    f"[资料{index}] 标题: {source.document_title}\n"
                    f"相关度: {source.score:.3f}\n"
                    f"内容: {source.content}"
                )
            context = "\n\n".join(context_blocks)
        else:
            context = "当前没有检索到可用知识片段。"

        return (
            f"用户问题:\n{question}\n\n"
            f"检索上下文:\n{context}\n\n"
            "请基于以上上下文回答。如果上下文不足，请明确说明，并给出下一步建议。"
        )
