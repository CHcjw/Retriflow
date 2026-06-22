import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))


class RetriFlowQueryTermMappingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / f"retriflow-{uuid.uuid4().hex}.db"
        os.environ["RETRIFLOW_DATABASE_BACKEND"] = "sqlite"
        os.environ["RETRIFLOW_DB_PATH"] = str(self.db_path)
        os.environ["RETRIFLOW_DATABASE_DSN"] = ""
        os.environ["RETRIFLOW_PGVECTOR_DSN"] = ""
        os.environ["RETRIFLOW_LLM_PROVIDER"] = "disabled"
        os.environ["RETRIFLOW_REWRITE_PROVIDER"] = "disabled"

        from core.config import get_settings
        from core.state import initialize_database

        get_settings.cache_clear()
        initialize_database()

    def tearDown(self) -> None:
        for key in [
            "RETRIFLOW_DATABASE_BACKEND",
            "RETRIFLOW_DB_PATH",
            "RETRIFLOW_DATABASE_DSN",
            "RETRIFLOW_PGVECTOR_DSN",
            "RETRIFLOW_LLM_PROVIDER",
            "RETRIFLOW_REWRITE_PROVIDER",
            "RETRIFLOW_QUERY_TERM_MAPPING_CACHE_ENABLED",
        ]:
            os.environ.pop(key, None)

        from core.config import get_settings

        get_settings.cache_clear()
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            pass

    def test_rewrite_normalizes_query_term_mapping_before_llm(self) -> None:
        from modules.admin import RetriFlowAdminService
        from modules.rag.rewrite import RetriFlowQueryRewriteService
        from schemas.admin import AdminKeywordMappingCreateRequest

        RetriFlowAdminService().create_keyword_mapping(
            AdminKeywordMappingCreateRequest(
                raw_keyword="退钱",
                target_keyword="退款",
                match_type="exact",
                priority=10,
                enabled=True,
            )
        )

        queries = RetriFlowQueryRewriteService().rewrite(
            history_messages=[],
            query="怎么退钱",
        )

        self.assertEqual(queries, ["怎么退款"])

    def test_keyword_mapping_mutations_clear_term_mapping_cache(self) -> None:
        from modules.admin import RetriFlowAdminService
        from schemas.admin import AdminKeywordMappingCreateRequest, AdminKeywordMappingUpdateRequest

        service = RetriFlowAdminService()
        with patch("modules.admin.service.QueryTermMappingCacheManager.clear_cache") as clear_mock:
            created = service.create_keyword_mapping(
                AdminKeywordMappingCreateRequest(
                    raw_keyword="赔钱",
                    target_keyword="理赔",
                    match_type="exact",
                    priority=1,
                    enabled=True,
                )
            )
            service.update_keyword_mapping(
                created.id,
                AdminKeywordMappingUpdateRequest(target_keyword="赔付"),
            )
            service.delete_keyword_mapping(created.id)

        self.assertEqual(clear_mock.call_count, 3)


if __name__ == "__main__":
    unittest.main()
