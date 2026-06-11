import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))

from main import create_app


class RetriFlowAuthApiTests(unittest.TestCase):
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

    def test_register_login_and_me_flow(self) -> None:
        register_response = self.client.post(
            "/api/v1/auth/register",
            json={
                "username": "alice",
                "password": "Password123",
                "role": "user",
            },
        )
        self.assertEqual(register_response.status_code, 201)
        register_payload = register_response.json()
        self.assertEqual(register_payload["username"], "alice")
        self.assertEqual(register_payload["role"], "user")

        login_response = self.client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "Password123"},
        )
        self.assertEqual(login_response.status_code, 200)
        login_payload = login_response.json()
        self.assertTrue(login_payload["access_token"])
        self.assertEqual(login_payload["token_type"], "bearer")

        me_response = self.client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {login_payload['access_token']}"},
        )
        self.assertEqual(me_response.status_code, 200)
        me_payload = me_response.json()
        self.assertEqual(me_payload["username"], "alice")
        self.assertEqual(me_payload["role"], "user")

    def test_login_rejects_invalid_password(self) -> None:
        self.client.post(
            "/api/v1/auth/register",
            json={
                "username": "alice",
                "password": "Password123",
                "role": "user",
            },
        )

        response = self.client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 401)

    def test_sessions_endpoint_requires_auth(self) -> None:
        response = self.client.get("/api/v1/sessions")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
