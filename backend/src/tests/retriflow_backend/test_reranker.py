import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeHttpxClient:
    def __init__(self, response_payload: dict) -> None:
        self.response_payload = response_payload
        self.last_url = ""
        self.last_json = {}
        self.last_headers = {}
        self.last_timeout = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def post(self, url: str, json: dict, headers: dict):
        self.last_url = url
        self.last_json = json
        self.last_headers = headers
        return _FakeResponse(self.response_payload)


class RetriFlowRerankServiceTests(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop("RETRIFLOW_DEFAULT_RERANK_MODEL", None)
        from core.config import get_settings

        get_settings.cache_clear()

    def test_rerank_requests_openai_compatible_rerank_endpoint_with_qwen_model(self) -> None:
        from core.config import get_settings
        from infra.llm import LLMProviderConfig
        from modules.rag.rerank import RetriFlowRerankService
        from modules.rag.retrieval.channels import RetrievedChunkRecord

        os.environ["RETRIFLOW_DEFAULT_RERANK_MODEL"] = "Qwen/Qwen3-Reranker-8B"
        get_settings.cache_clear()

        service = RetriFlowRerankService()
        fake_client = _FakeHttpxClient(
            {
                "results": [
                    {"index": 1, "relevance_score": 0.95},
                    {"index": 0, "relevance_score": 0.83},
                ]
            }
        )
        provider = LLMProviderConfig(
            name="test-provider",
            base_url="https://example.test/v1",
            api_key="test-key",
        )
        records = [
            RetrievedChunkRecord(1, "kb-demo-1", 101, "Doc A", "Alpha chunk", 0.20, "hybrid_rrf"),
            RetrievedChunkRecord(2, "kb-demo-1", 102, "Doc B", "Beta chunk", 0.10, "hybrid_rrf"),
        ]

        with (
            patch.object(service.llm_service, "_resolve_provider", return_value=provider),
            patch("modules.rag.rerank.httpx.Client", return_value=fake_client),
        ):
            reranked = service.rerank("What is RetriFlow?", records, limit=2)

        self.assertEqual(fake_client.last_url, "https://example.test/v1/rerank")
        self.assertEqual(fake_client.last_json["model"], "Qwen/Qwen3-Reranker-8B")
        self.assertEqual(fake_client.last_json["query"], "What is RetriFlow?")
        self.assertEqual(fake_client.last_json["top_n"], 2)
        self.assertEqual(
            fake_client.last_json["documents"],
            ["Doc A\nAlpha chunk", "Doc B\nBeta chunk"],
        )
        self.assertEqual(fake_client.last_headers["Authorization"], "Bearer test-key")
        self.assertEqual([item.chunk_id for item in reranked], [2, 1])
        self.assertTrue(all(item.channel == "rerank" for item in reranked))

    def test_rerank_accepts_data_field_response_shape(self) -> None:
        from core.config import get_settings
        from infra.llm import LLMProviderConfig
        from modules.rag.rerank import RetriFlowRerankService
        from modules.rag.retrieval.channels import RetrievedChunkRecord

        os.environ["RETRIFLOW_DEFAULT_RERANK_MODEL"] = "Qwen/Qwen3-Reranker-8B"
        get_settings.cache_clear()

        service = RetriFlowRerankService()
        fake_client = _FakeHttpxClient(
            {
                "data": [
                    {"index": 0, "score": 0.77},
                ]
            }
        )
        provider = LLMProviderConfig(
            name="test-provider",
            base_url="https://example.test",
            api_key="test-key",
        )
        records = [
            RetrievedChunkRecord(1, "kb-demo-1", 101, "Doc A", "Alpha chunk", 0.20, "hybrid_rrf"),
        ]

        with (
            patch.object(service.llm_service, "_resolve_provider", return_value=provider),
            patch("modules.rag.rerank.httpx.Client", return_value=fake_client),
        ):
            reranked = service.rerank("What is RetriFlow?", records, limit=1)

        self.assertEqual(len(reranked), 1)
        self.assertEqual(reranked[0].chunk_id, 1)
        self.assertEqual(reranked[0].score, 0.77)


if __name__ == "__main__":
    unittest.main()
