import os
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))


class RetriFlowModelRoutingTests(unittest.TestCase):
    def tearDown(self) -> None:
        keys = [
            "RETRIFLOW_LLM_PROVIDER",
            "RETRIFLOW_LLM_API_KEY",
            "RETRIFLOW_LLM_BASE_URL",
            "RETRIFLOW_CHAT_PROVIDER",
            "RETRIFLOW_REWRITE_PROVIDER",
            "RETRIFLOW_ROUTE_PROVIDER",
            "RETRIFLOW_MEMORY_SUMMARY_PROVIDER",
            "RETRIFLOW_EMBEDDING_PROVIDER",
            "RETRIFLOW_RERANK_PROVIDER",
            "RETRIFLOW_OLLAMA_BASE_URL",
            "RETRIFLOW_OLLAMA_CHAT_MODEL",
            "RETRIFLOW_OLLAMA_EMBEDDING_MODEL",
            "BAILIAN_API_KEY",
            "DASHSCOPE_BASE_URL",
            "SILICONFLOW_API_KEY",
            "SILICONFLOW_BASE_URL",
        ]
        for key in keys:
            os.environ.pop(key, None)

        from core.config import get_settings

        get_settings.cache_clear()

    def test_settings_expose_split_provider_defaults_and_ollama_defaults(self) -> None:
        from core.config import get_settings

        get_settings.cache_clear()
        settings = get_settings()

        self.assertEqual(settings.chat_provider, "bailian")
        self.assertEqual(settings.rewrite_provider, "ollama")
        self.assertEqual(settings.route_provider, "ollama")
        self.assertEqual(settings.memory_summary_provider, "ollama")
        self.assertEqual(settings.embedding_provider, "siliconflow")
        self.assertEqual(settings.rerank_provider, "siliconflow")
        self.assertEqual(settings.ollama_base_url, "http://127.0.0.1:11434/v1")
        self.assertEqual(settings.ollama_chat_model, "qwen3:8b")
        self.assertEqual(settings.ollama_embedding_model, "qwen3-embedding:8b")

    def test_chat_provider_uses_bailian_even_when_legacy_custom_base_url_is_present(self) -> None:
        os.environ["RETRIFLOW_LLM_PROVIDER"] = "auto"
        os.environ["RETRIFLOW_LLM_API_KEY"] = "legacy-key"
        os.environ["RETRIFLOW_LLM_BASE_URL"] = "https://legacy.example/v1"
        os.environ["RETRIFLOW_CHAT_PROVIDER"] = "bailian"
        os.environ["BAILIAN_API_KEY"] = "bailian-key"

        from core.config import get_settings
        from infra.llm import RetriFlowLLMService

        get_settings.cache_clear()
        service = RetriFlowLLMService()
        provider = service._resolve_provider(capability="chat")

        self.assertIsNotNone(provider)
        self.assertEqual(provider.name, "bailian")
        self.assertEqual(provider.base_url, "https://dashscope.aliyuncs.com/compatible-mode/v1")

    def test_embedding_provider_prefers_siliconflow_by_default(self) -> None:
        os.environ["BAILIAN_API_KEY"] = "bailian-key"
        os.environ["SILICONFLOW_API_KEY"] = "siliconflow-key"

        from core.config import get_settings
        from infra.embeddings import RetriFlowEmbeddingService

        get_settings.cache_clear()
        service = RetriFlowEmbeddingService()
        provider = service._resolve_provider()

        self.assertIsNotNone(provider)
        self.assertEqual(provider.name, "siliconflow")
        self.assertEqual(provider.base_url, "https://api.siliconflow.cn/v1")

    def test_chat_provider_can_resolve_local_ollama_with_provider_specific_model(self) -> None:
        os.environ["RETRIFLOW_CHAT_PROVIDER"] = "ollama"

        from core.config import get_settings
        from infra.llm import RetriFlowLLMService

        get_settings.cache_clear()
        service = RetriFlowLLMService()
        provider = service._resolve_provider(capability="chat")
        model = service._resolve_model(capability="chat", provider_name="ollama")

        self.assertIsNotNone(provider)
        self.assertEqual(provider.name, "ollama")
        self.assertEqual(provider.base_url, "http://127.0.0.1:11434/v1")
        self.assertEqual(model, "qwen3:8b")


if __name__ == "__main__":
    unittest.main()
