import sys
import os
import tempfile
import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))

from main import create_app


class RetriFlowKnowledgeApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / f"retriflow-{uuid.uuid4().hex}.db"
        os.environ["RETRIFLOW_DATABASE_BACKEND"] = "sqlite"
        os.environ["RETRIFLOW_DB_PATH"] = str(self.db_path)
        os.environ["RETRIFLOW_DATABASE_DSN"] = ""
        os.environ["RETRIFLOW_PGVECTOR_DSN"] = ""
        os.environ["RETRIFLOW_VECTOR_STORE_TYPE"] = "memory"
        from core.config import get_settings

        get_settings.cache_clear()
        self.client = TestClient(create_app())
        login_response = self.client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        self.assertEqual(login_response.status_code, 200)
        self.client.headers.update({"Authorization": f"Bearer {login_response.json()['access_token']}"})

    def tearDown(self) -> None:
        self.client.close()
        os.environ.pop("RETRIFLOW_DATABASE_BACKEND", None)
        os.environ.pop("RETRIFLOW_DB_PATH", None)
        os.environ.pop("RETRIFLOW_DATABASE_DSN", None)
        os.environ.pop("RETRIFLOW_PGVECTOR_DSN", None)
        os.environ.pop("RETRIFLOW_VECTOR_STORE_TYPE", None)
        from core.config import get_settings

        get_settings.cache_clear()
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            pass

    def test_knowledge_endpoint_starts_empty_without_demo_seed(self) -> None:
        response = self.client.get("/api/v1/knowledge-bases")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["items"], [])

    def test_knowledge_endpoint_requires_auth(self) -> None:
        unauthenticated_client = TestClient(create_app())

        response = unauthenticated_client.get("/api/v1/knowledge-bases")

        self.assertEqual(response.status_code, 401)

    def test_delete_knowledge_base_removes_created_item(self) -> None:
        created = self.client.post(
            "/api/v1/knowledge-bases",
            json={"name": "Delete KB"},
        ).json()

        response = self.client.delete(f"/api/v1/knowledge-bases/{created['id']}")

        self.assertEqual(response.status_code, 204)
        listed = self.client.get("/api/v1/knowledge-bases").json()
        self.assertEqual(listed["items"], [])


if __name__ == "__main__":
    unittest.main()
