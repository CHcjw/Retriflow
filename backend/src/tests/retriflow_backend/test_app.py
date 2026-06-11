import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"

import sys

sys.path.insert(0, str(SRC_PATH))


class RetriFlowAppImportTests(unittest.TestCase):
    def test_backend_app_can_be_imported(self) -> None:
        from main import create_app

        app = create_app()

        self.assertEqual(app.title, "RetriFlow API")

    def test_settings_expose_default_model_and_vector_preferences(self) -> None:
        from core.config import get_settings

        get_settings.cache_clear()
        with patch("core.config._read_env_file", return_value={}):
            settings = get_settings()

        self.assertEqual(settings.default_chat_model, "qwen3-max")
        self.assertEqual(settings.default_embedding_model, "qwen-emb-8b")
        self.assertEqual(settings.default_rerank_model, "Qwen/Qwen3-Reranker-8B")
        self.assertEqual(settings.vector_store_type, "pg")

    def test_settings_expose_default_rag_retrieval_pipeline_preferences(self) -> None:
        from core.config import get_settings

        get_settings.cache_clear()
        with patch("core.config._read_env_file", return_value={}):
            settings = get_settings()

        self.assertEqual(settings.default_rerank_model, "Qwen/Qwen3-Reranker-8B")
        self.assertEqual(settings.retrieval_bm25_top_k, 80)
        self.assertEqual(settings.retrieval_vector_top_k, 80)
        self.assertEqual(settings.retrieval_rrf_top_k, 50)
        self.assertEqual(settings.retrieval_rerank_top_k, 10)
        self.assertEqual(settings.retrieval_final_top_k, 5)

    def test_settings_expose_default_tika_and_ocr_service_endpoints(self) -> None:
        from core.config import get_settings

        settings = get_settings()

        self.assertEqual(settings.tika_endpoint, "http://127.0.0.1:9998")
        self.assertEqual(settings.tika_ocr_service_endpoint, "http://127.0.0.1:9889")
        self.assertIsInstance(settings.tika_ocr_enabled, bool)

    def test_cors_preflight_request_succeeds_for_frontend_origin(self) -> None:
        from main import create_app

        client = TestClient(create_app())

        response = client.options(
            "/api/v1/meta",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "http://127.0.0.1:5173")


if __name__ == "__main__":
    unittest.main()
