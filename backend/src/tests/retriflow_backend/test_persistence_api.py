import os
import sqlite3
import sys
import tempfile
import uuid
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))


class RetriFlowPersistenceApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / f"retriflow-{uuid.uuid4().hex}.db"
        os.environ["RETRIFLOW_DATABASE_BACKEND"] = "sqlite"
        os.environ["RETRIFLOW_DB_PATH"] = str(self.db_path)
        os.environ["RETRIFLOW_LLM_PROVIDER"] = "disabled"

        from core.config import get_settings

        get_settings.cache_clear()
        from main import create_app

        self.client = TestClient(create_app())
        login_response = self.client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        self.token = login_response.json()["access_token"]
        self.client.headers.update({"Authorization": f"Bearer {self.token}"})

    def tearDown(self) -> None:
        self.client.close()
        os.environ.pop("RETRIFLOW_DATABASE_BACKEND", None)
        os.environ.pop("RETRIFLOW_DB_PATH", None)
        os.environ.pop("RETRIFLOW_LLM_PROVIDER", None)
        from core.config import get_settings

        get_settings.cache_clear()
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            pass

    def test_database_file_is_created_with_core_schema_and_default_admin(self) -> None:
        self.assertTrue(self.db_path.exists())

        connection = sqlite3.connect(self.db_path)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                select name
                from sqlite_master
                where type = 'table'
                  and name in ('users', 'sessions', 'knowledge_bases')
                """
            )
            table_names = {row[0] for row in cursor.fetchall()}
            cursor.execute("select count(*) from users where username = 'admin'")
            admin_count = cursor.fetchone()[0]
        finally:
            connection.close()

        self.assertEqual(table_names, {"users", "sessions", "knowledge_bases"})
        self.assertEqual(admin_count, 1)

    def test_created_session_persists_in_database(self) -> None:
        create_response = self.client.post("/api/v1/sessions", json={"title": "数据库持久化会话"})
        self.assertEqual(create_response.status_code, 201)

        list_response = self.client.get("/api/v1/sessions")
        payload = list_response.json()

        self.assertTrue(any(item["title"] == "数据库持久化会话" for item in payload["items"]))

    def test_created_knowledge_base_persists_in_database(self) -> None:
        create_response = self.client.post("/api/v1/knowledge-bases", json={"name": "数据库知识库"})
        self.assertEqual(create_response.status_code, 201)

        list_response = self.client.get("/api/v1/knowledge-bases")
        payload = list_response.json()

        self.assertTrue(any(item["name"] == "数据库知识库" for item in payload["items"]))


if __name__ == "__main__":
    unittest.main()
