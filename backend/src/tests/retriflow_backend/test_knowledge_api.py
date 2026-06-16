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

    def test_delete_document_removes_document_and_chunks(self) -> None:
        created = self.client.post(
            "/api/v1/knowledge-bases",
            json={"name": "Document Delete KB"},
        ).json()
        kb_id = created["id"]
        document = self.client.post(
            f"/api/v1/knowledge-bases/{kb_id}/documents",
            json={
                "title": "Delete Me",
                "content": "RetriFlow document deletion test. " * 40,
                "document_type": "manual",
                "chunk_strategy": "fixed",
                "chunk_size": 200,
                "chunk_overlap": 20,
            },
        ).json()

        chunk_response = self.client.get(
            f"/api/v1/knowledge-bases/{kb_id}/documents/{document['id']}/chunks"
        )
        self.assertEqual(chunk_response.status_code, 200)
        self.assertGreater(len(chunk_response.json()["items"]), 0)

        response = self.client.delete(
            f"/api/v1/knowledge-bases/{kb_id}/documents/{document['id']}"
        )

        self.assertEqual(response.status_code, 204)
        listed = self.client.get(f"/api/v1/knowledge-bases/{kb_id}/documents").json()
        self.assertEqual(listed["items"], [])
        refreshed_kb = self.client.get("/api/v1/knowledge-bases").json()["items"][0]
        self.assertEqual(refreshed_kb["document_count"], 0)

    def test_update_and_delete_document_chunks(self) -> None:
        created = self.client.post(
            "/api/v1/knowledge-bases",
            json={"name": "Chunk Manage KB"},
        ).json()
        kb_id = created["id"]
        document = self.client.post(
            f"/api/v1/knowledge-bases/{kb_id}/documents",
            json={
                "title": "Chunk Manage Document",
                "content": "Chunk management test content. " * 60,
                "document_type": "manual",
                "chunk_strategy": "fixed",
                "chunk_size": 200,
                "chunk_overlap": 20,
            },
        ).json()

        chunks = self.client.get(
            f"/api/v1/knowledge-bases/{kb_id}/documents/{document['id']}/chunks"
        ).json()["items"]
        self.assertGreater(len(chunks), 0)
        first_chunk = chunks[0]
        self.assertTrue(first_chunk["enabled"])

        disabled_response = self.client.patch(
            f"/api/v1/knowledge-bases/{kb_id}/documents/{document['id']}/chunks/{first_chunk['id']}",
            json={"enabled": False},
        )
        self.assertEqual(disabled_response.status_code, 200)
        self.assertFalse(disabled_response.json()["enabled"])

        batch_response = self.client.patch(
            f"/api/v1/knowledge-bases/{kb_id}/documents/{document['id']}/chunks",
            json={"chunk_ids": [first_chunk["id"]], "enabled": True},
        )
        self.assertEqual(batch_response.status_code, 200)
        self.assertEqual(batch_response.json()["updated_count"], 1)

        delete_response = self.client.delete(
            f"/api/v1/knowledge-bases/{kb_id}/documents/{document['id']}/chunks/{first_chunk['id']}"
        )
        self.assertEqual(delete_response.status_code, 204)
        remaining_chunks = self.client.get(
            f"/api/v1/knowledge-bases/{kb_id}/documents/{document['id']}/chunks"
        ).json()["items"]
        self.assertNotIn(first_chunk["id"], [chunk["id"] for chunk in remaining_chunks])

    def test_get_and_update_route_profile(self) -> None:
        created = self.client.post(
            "/api/v1/knowledge-bases",
            json={"name": "Test Route KB"},
        ).json()
        kb_id = created["id"]

        # Get default route profile
        get_resp = self.client.get(f"/api/v1/knowledge-bases/{kb_id}/route-profile")
        self.assertEqual(get_resp.status_code, 200)
        profile = get_resp.json()
        self.assertEqual(profile["knowledge_base_id"], kb_id)
        self.assertIn("Test Route KB", profile["profile_text"])
        self.assertIsInstance(profile["sample_questions"], list)
        self.assertIsInstance(profile["keywords"], list)

        # Update route profile
        update_data = {
            "profile_text": "Updated profile text description",
            "sample_questions": ["What is updated?", "How to update route profile?"],
            "keywords": ["update", "route", "profile"]
        }
        put_resp = self.client.put(
            f"/api/v1/knowledge-bases/{kb_id}/route-profile",
            json=update_data,
        )
        self.assertEqual(put_resp.status_code, 200)
        updated_profile = put_resp.json()
        self.assertEqual(updated_profile["profile_text"], "Updated profile text description")
        self.assertEqual(updated_profile["sample_questions"], ["What is updated?", "How to update route profile?"])
        self.assertEqual(updated_profile["keywords"], ["update", "route", "profile"])

        # Fetch again to verify persistence
        get_resp2 = self.client.get(f"/api/v1/knowledge-bases/{kb_id}/route-profile")
        self.assertEqual(get_resp2.status_code, 200)
        profile2 = get_resp2.json()
        self.assertEqual(profile2["profile_text"], "Updated profile text description")
        self.assertEqual(profile2["sample_questions"], ["What is updated?", "How to update route profile?"])
        self.assertEqual(profile2["keywords"], ["update", "route", "profile"])


if __name__ == "__main__":
    unittest.main()
