from dataclasses import dataclass
import hashlib
import math

import httpx
from langchain_core.embeddings import Embeddings

from core.config import get_settings


@dataclass
class EmbeddingProviderConfig:
    name: str
    base_url: str
    api_key: str


class DeterministicHashEmbeddings(Embeddings):
    def __init__(self, dimensions: int = 32) -> None:
        self.dimensions = dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_text(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_text(text)

    def _embed_text(self, text: str) -> list[float]:
        if not text.strip():
            return [0.0] * self.dimensions

        vector = [0.0] * self.dimensions
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for index in range(self.dimensions):
                byte = digest[index % len(digest)]
                vector[index] += (byte / 255.0) - 0.5

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class RetriFlowEmbeddingService(Embeddings):
    def __init__(self) -> None:
        self.settings = get_settings()
        self.fallback_embeddings = DeterministicHashEmbeddings()
        from infra.llm import RetriFlowLLMService

        self.llm_service = RetriFlowLLMService()
        self.default_provider_name: str | None = None
        self.default_model_name: str | None = None

    def embed_texts(
        self,
        texts: list[str],
        *,
        provider_name: str | None = None,
        model_name: str | None = None,
    ) -> list[list[float]]:
        return self._embed_documents(
            texts,
            provider_name=provider_name or self.default_provider_name,
            model_name=model_name or self.default_model_name,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed_documents(
            texts,
            provider_name=self.default_provider_name,
            model_name=self.default_model_name,
        )

    def _embed_documents(
        self,
        texts: list[str],
        *,
        provider_name: str | None = None,
        model_name: str | None = None,
    ) -> list[list[float]]:
        if not texts:
            return []

        provider = self._resolve_provider(provider_name=provider_name)
        if provider is None:
            return self.fallback_embeddings.embed_documents(texts)

        try:
            return self._request_embeddings(provider=provider, inputs=texts, model_name=model_name)
        except Exception:
            return self.fallback_embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        provider = self._resolve_provider(provider_name=self.default_provider_name)
        if provider is None:
            return self.fallback_embeddings.embed_query(text)

        try:
            result = self._request_embeddings(
                provider=provider,
                inputs=[text],
                model_name=self.default_model_name,
            )
        except Exception:
            return self.fallback_embeddings.embed_query(text)

        return result[0] if result else self.fallback_embeddings.embed_query(text)

    def _request_embeddings(
        self,
        provider: EmbeddingProviderConfig,
        inputs: list[str],
        model_name: str | None = None,
    ) -> list[list[float]]:
        headers = {"Content-Type": "application/json"}
        if provider.api_key:
            headers["Authorization"] = f"Bearer {provider.api_key}"
        payload = {
            "model": model_name or self.llm_service._resolve_model(
                capability="embedding",
                provider_name=provider.name,
            ),
            "input": inputs,
        }

        with httpx.Client(timeout=self.settings.llm_request_timeout_seconds) as client:
            response = client.post(
                f"{provider.base_url.rstrip('/')}/embeddings",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        raw_items = data.get("data", [])
        if not raw_items:
            raise RuntimeError("embedding response did not contain vectors")

        ordered_items = sorted(raw_items, key=lambda item: int(item.get("index", 0)))
        embeddings = [item.get("embedding", []) for item in ordered_items]
        if not all(isinstance(item, list) and item for item in embeddings):
            raise RuntimeError("embedding response contained invalid vectors")
        return embeddings

    def _resolve_provider(self, provider_name: str | None = None) -> EmbeddingProviderConfig | None:
        provider = (
            self.llm_service._provider_registry().get(provider_name)
            if provider_name
            else self.llm_service._resolve_provider(capability="embedding")
        )
        if provider is None or provider.name == "disabled":
            return None
        return EmbeddingProviderConfig(
            name=provider.name,
            base_url=provider.base_url,
            api_key=provider.api_key,
        )

    def with_runtime_defaults(
        self,
        *,
        provider_name: str | None = None,
        model_name: str | None = None,
    ) -> "RetriFlowEmbeddingService":
        clone = RetriFlowEmbeddingService()
        clone.settings = self.settings
        clone.fallback_embeddings = self.fallback_embeddings
        clone.llm_service = self.llm_service
        clone.default_provider_name = provider_name
        clone.default_model_name = model_name
        return clone
