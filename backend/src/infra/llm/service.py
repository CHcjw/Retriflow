from __future__ import annotations

import concurrent.futures
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
import json
import time
from typing import Any

import httpx

from core.config import get_settings
from infra.llm.health import ModelHealthService, ModelHealthSnapshot, get_model_health_service
from modules.rag.prompt import RAGPromptService, get_prompt_template_loader
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
        self.model_health: ModelHealthService = get_model_health_service()
        self.model_health.failure_threshold = self.settings.model_health_failure_threshold
        self.model_health.open_cooldown_seconds = self.settings.model_health_open_cooldown_seconds
        self.prompt_loader = get_prompt_template_loader()

    def generate_answer(
        self,
        question: str,
        sources: list[ChatSourceItem],
        extra_context: str = "",
        memory_messages: list[dict[str, str]] | None = None,
        deep_thinking: bool = False,
    ) -> str:
        data = self._post_json_with_fallback(
            capability="chat",
            path="/chat/completions",
            payload_factory=lambda provider: self._build_chat_payload(
                question=question,
                sources=sources,
                extra_context=extra_context,
                memory_messages=memory_messages or [],
                stream=False,
                model=self._resolve_chat_model(provider.name, deep_thinking=deep_thinking),
            ),
        )
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
        data = self._post_json_with_fallback(
            capability="chat",
            path="/chat/completions",
            payload_factory=lambda candidate: {
                **payload,
                "model": self._resolve_chat_model(candidate.name, deep_thinking=deep_thinking),
            },
            initial_provider=provider,
        )
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
        initial_provider = self._resolve_provider(capability="chat")
        if initial_provider is None:
            raise RuntimeError("no chat provider is configured")

        last_error: Exception | None = None
        attempted: set[str] = set()
        for provider in self._iter_provider_candidates(
            capability="chat",
            initial_provider=initial_provider,
        ):
            if provider.name in attempted:
                continue
            attempted.add(provider.name)
            payload = self._build_chat_payload(
                question=question,
                sources=sources,
                extra_context=extra_context,
                memory_messages=memory_messages or [],
                stream=True,
                model=self._resolve_chat_model(provider.name, deep_thinking=deep_thinking),
            )
            stream = iter(self._stream_provider_answer(provider=provider, payload=payload))
            try:
                first_chunk = self._next_stream_chunk_with_timeout(
                    stream,
                    timeout_seconds=self.settings.llm_stream_first_packet_timeout_seconds,
                )
            except StopIteration as exc:
                last_error = RuntimeError("llm stream completed before first content chunk")
                continue
            except TimeoutError as exc:
                last_error = exc
                self.model_health.record_failure(
                    capability="chat",
                    provider_name=provider.name,
                    model=str(payload.get("model", "")),
                    error=str(exc),
                )
                continue
            except Exception as exc:
                last_error = exc
                continue

            yield first_chunk
            for chunk in stream:
                yield chunk
            return

        if last_error is not None:
            raise RuntimeError(f"all chat stream model candidates failed: {last_error}") from last_error
        raise RuntimeError("no chat provider is configured")

    @staticmethod
    def _next_stream_chunk_with_timeout(stream: Iterator[str], *, timeout_seconds: float) -> str:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(next, stream)
        try:
            return future.result(timeout=max(0.001, timeout_seconds))
        except concurrent.futures.TimeoutError as exc:
            future.cancel()
            raise TimeoutError(f"llm stream first packet timed out after {timeout_seconds:.3f}s") from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _stream_provider_answer(
        self,
        *,
        provider: LLMProviderConfig,
        payload: dict[str, Any],
    ) -> Iterator[str]:
        model = str(payload.get("model", ""))
        started_at = time.perf_counter()
        first_chunk_seen = False
        try:
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
                        if not first_chunk_seen:
                            first_chunk_ms = int((time.perf_counter() - started_at) * 1000)
                            self.model_health.record_first_packet(
                                capability="chat",
                                provider_name=provider.name,
                                model=model,
                                first_packet_ms=first_chunk_ms,
                            )
                            first_chunk_seen = True
                        yield chunk
            if not first_chunk_seen:
                raise RuntimeError("llm stream completed before first content chunk")
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            self.model_health.record_success(
                capability="chat",
                provider_name=provider.name,
                model=model,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            self.model_health.record_failure(
                capability="chat",
                provider_name=provider.name,
                model=model,
                error=str(exc),
            )
            raise

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
        data = self._post_json_with_fallback(
            capability="memory_summary",
            path="/chat/completions",
            payload_factory=lambda candidate: {
                **payload,
                "model": self._resolve_model(
                    capability="memory_summary",
                    provider_name=candidate.name,
                ),
            },
            initial_provider=provider,
        )
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
        data = self._post_json_with_fallback(
            capability="route",
            path="/chat/completions",
            payload_factory=lambda candidate: {
                **payload,
                "model": self._resolve_model(capability="route", provider_name=candidate.name),
            },
            initial_provider=provider,
        )
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
        data = self._post_json_with_fallback(
            capability=capability,
            path="/chat/completions",
            payload_factory=lambda candidate: {
                **payload,
                "model": model
                or self._resolve_model(capability=capability, provider_name=candidate.name),
            },
            initial_provider=provider,
        )
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("llm json response did not contain choices")

        message = choices[0].get("message", {})
        content = self._extract_content(message.get("content"))
        if not content:
            raise RuntimeError("llm json response did not contain content")
        return json.loads(content)

    def probe_model_health(
        self,
        *,
        capability: str = "chat",
        provider_name: str | None = None,
        model: str | None = None,
    ) -> ModelHealthSnapshot:
        provider = self._resolve_probe_provider(capability=capability, provider_name=provider_name)
        resolved_model = model or self._resolve_model(capability=capability, provider_name=provider.name)
        payload = {
            "model": resolved_model,
            "messages": [
                {"role": "system", "content": "You are a health probe. Reply with ok."},
                {"role": "user", "content": "ok"},
            ],
            "temperature": 0.0,
            "stream": False,
        }
        self._post_json(
            provider=provider,
            payload=payload,
            path="/chat/completions",
            capability=capability,
        )
        return self.model_health.get_snapshot(
            capability=capability,
            provider_name=provider.name,
            model=resolved_model,
        )

    def _post_json(
        self,
        provider: LLMProviderConfig,
        payload: dict[str, Any],
        path: str,
        capability: str = "chat",
    ) -> dict[str, Any]:
        model = str(payload.get("model", ""))
        started_at = time.perf_counter()
        try:
            with httpx.Client(timeout=self.settings.llm_request_timeout_seconds) as client:
                response = client.post(
                    f"{provider.base_url.rstrip('/')}{path}",
                    json=payload,
                    headers=self._build_headers(provider),
                )
                response.raise_for_status()
                data = response.json()
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            self.model_health.record_success(
                capability=capability,
                provider_name=provider.name,
                model=model,
                duration_ms=duration_ms,
            )
            return data
        except Exception as exc:
            self.model_health.record_failure(
                capability=capability,
                provider_name=provider.name,
                model=model,
                error=str(exc),
            )
            raise

    def _post_json_with_fallback(
        self,
        *,
        capability: str,
        path: str,
        payload_factory,
        initial_provider: LLMProviderConfig | None = None,
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        attempted: set[str] = set()
        for provider in self._iter_provider_candidates(
            capability=capability,
            initial_provider=initial_provider,
        ):
            if provider.name in attempted:
                continue
            attempted.add(provider.name)
            payload = payload_factory(provider)
            try:
                if capability == "chat":
                    return self._post_json(provider=provider, payload=payload, path=path)
                return self._post_json(
                    provider=provider,
                    payload=payload,
                    path=path,
                    capability=capability,
                )
            except Exception as exc:
                last_error = exc

        if last_error is not None:
            raise RuntimeError(
                f"all {capability} model candidates failed: {last_error}"
            ) from last_error
        raise RuntimeError(f"no {capability} provider is configured")

    def _iter_provider_candidates(
        self,
        *,
        capability: str,
        initial_provider: LLMProviderConfig | None = None,
    ):
        requested = self._resolve_provider_name(capability)
        if initial_provider is not None:
            yield initial_provider
            if requested in {"disabled", "custom"}:
                return

        if requested == "disabled":
            yield LLMProviderConfig(
                name="disabled",
                base_url="http://127.0.0.1:9",
                api_key="disabled",
            )
            return
        if requested == "custom":
            if self.settings.llm_api_key and self.settings.llm_base_url:
                yield LLMProviderConfig(
                    name="custom",
                    base_url=self.settings.llm_base_url,
                    api_key=self.settings.llm_api_key,
                )
            return

        providers = self._provider_registry()
        yielded: set[str] = {initial_provider.name} if initial_provider else set()

        def available_candidate(provider_name: str) -> LLMProviderConfig | None:
            if provider_name in yielded:
                return None
            provider = providers.get(provider_name)
            if provider and self._provider_is_available(provider) and self._provider_health_allows(provider, capability):
                yielded.add(provider.name)
                return provider
            return None

        if requested and requested not in {"auto", "chat"}:
            provider = available_candidate(requested)
            if provider is not None:
                yield provider
            if requested not in providers and initial_provider is None:
                return

        for provider_name in self._provider_fallback_order(capability):
            provider = available_candidate(provider_name)
            if provider is not None:
                yield provider

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
                if self._provider_health_allows(provider, capability):
                    return provider
                return self._resolve_fallback_provider(
                    providers=providers,
                    capability=capability,
                    excluded_provider_names={requested},
                )
            return None

        return self._resolve_fallback_provider(providers=providers, capability=capability)

    def _resolve_probe_provider(self, *, capability: str, provider_name: str | None) -> LLMProviderConfig:
        providers = self._provider_registry()
        normalized_provider = (provider_name or "").strip().lower()
        if normalized_provider:
            provider = providers.get(normalized_provider)
            if provider is None or not self._provider_is_available(provider):
                raise RuntimeError("probe provider is not configured or unavailable")
            return provider

        provider = self._resolve_provider(capability=capability)
        if provider is None:
            raise RuntimeError("no provider is configured for probe")
        return provider

    def _resolve_fallback_provider(
        self,
        *,
        providers: dict[str, LLMProviderConfig],
        capability: str,
        excluded_provider_names: set[str] | None = None,
    ) -> LLMProviderConfig | None:
        excluded_provider_names = excluded_provider_names or set()
        for provider_name in self._provider_fallback_order(capability):
            if provider_name in excluded_provider_names:
                continue
            provider = providers.get(provider_name)
            if provider and self._provider_is_available(provider) and self._provider_health_allows(provider, capability):
                return provider
        return None

    def _resolve_model(self, capability: str, provider_name: str) -> str:
        if provider_name == "lmstudio":
            if capability == "embedding":
                return self.settings.lmstudio_embedding_model
            return self.settings.lmstudio_chat_model
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
        if provider_name == "lmstudio":
            return self.settings.lmstudio_chat_model
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
            "lmstudio": LLMProviderConfig(
                name="lmstudio",
                base_url=self.settings.lmstudio_base_url,
                api_key="",
            ),
            "ollama": LLMProviderConfig(
                name="ollama",
                base_url=self.settings.ollama_base_url,
                api_key="",
            ),
        }

    def _provider_fallback_order(self, capability: str) -> tuple[str, ...]:
        if capability == "embedding":
            return ("siliconflow", "bailian", "aihubmix", "lmstudio", "ollama", "deepseek", "groq")
        if capability == "rerank":
            return ("bailian", "siliconflow", "aihubmix", "deepseek")
        if capability in {"intent", "rewrite", "route", "memory_summary"}:
            return ("bailian", "siliconflow", "aihubmix", "deepseek", "groq", "lmstudio", "ollama")
        return ("bailian", "siliconflow", "aihubmix", "deepseek", "groq", "lmstudio", "ollama")

    @staticmethod
    def _provider_is_available(provider: LLMProviderConfig) -> bool:
        if not provider.base_url:
            return False
        if provider.name in {"lmstudio", "ollama", "disabled"}:
            return True
        return bool(provider.api_key)

    def _provider_health_allows(self, provider: LLMProviderConfig, capability: str) -> bool:
        if provider.name == "disabled":
            return True
        model = self._resolve_model(capability=capability, provider_name=provider.name)
        return self.model_health.is_call_allowed(
            capability=capability,
            provider_name=provider.name,
            model=model,
        )

    @classmethod
    def _build_system_prompt(cls) -> str:
        return RAGPromptService(no_answer_reply=cls.NO_ANSWER_REPLY).build_system_prompt()

    @classmethod
    def _build_user_prompt(
        cls,
        question: str,
        sources: list[ChatSourceItem],
        extra_context: str = "",
    ) -> str:
        return RAGPromptService(no_answer_reply=cls.NO_ANSWER_REPLY).build_user_prompt(question, sources, extra_context)

    @staticmethod
    def _build_retrieved_context(sources: list[ChatSourceItem]) -> str:
        loader = get_prompt_template_loader()
        if not sources:
            return loader.render_section("context.md", "no-sources")

        blocks: list[str] = []
        for index, source in enumerate(sources[:5], start=1):
            updated_line = f"更新时间：{source.source_updated_at}" if source.source_updated_at else ""
            blocks.append(
                loader.render_section(
                    "context.md",
                    "single-source",
                    {
                        "index": index,
                        "document_title": source.document_title,
                        "updated_line": updated_line,
                        "knowledge_base_id": source.knowledge_base_id,
                        "content": source.content,
                    },
                )
            )
        return "\n\n".join(blocks)

    @staticmethod
    def _build_route_prompt(question: str, knowledge_base_profiles: list[dict[str, Any]]) -> str:
        profiles_json = json.dumps(knowledge_base_profiles, ensure_ascii=False, indent=2)
        return get_prompt_template_loader().render(
            "route.md",
            {"question": question, "profiles_json": profiles_json},
        )

    @staticmethod
    def _build_summary_system_prompt(max_chars: int) -> str:
        return get_prompt_template_loader().render_section(
            "memory.md",
            "summary-system",
            {"max_chars": max_chars},
        )

    @staticmethod
    def _build_summary_user_prompt(
        *,
        existing_summary: str,
        conversation_messages: list[dict[str, str]],
        max_chars: int,
    ) -> str:
        conversation_lines: list[str] = []
        for message in conversation_messages:
            role = "用户" if message["role"] == "user" else "助手"
            conversation_lines.append(f"{role}：{message['content']}")
        return get_prompt_template_loader().render_section(
            "memory.md",
            "summary-user",
            {
                "existing_summary": existing_summary.strip() or "无",
                "conversation": "\n".join(conversation_lines).strip() or "无",
                "max_chars": max_chars,
            },
        )
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
