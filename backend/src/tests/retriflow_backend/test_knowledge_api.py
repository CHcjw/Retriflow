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
        os.environ["RETRIFLOW_STORAGE_BACKEND"] = "local"
        os.environ["RETRIFLOW_STORAGE_LOCAL_DIR"] = str(Path(self.temp_dir.name) / "uploads")
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
        os.environ.pop("RETRIFLOW_STORAGE_BACKEND", None)
        os.environ.pop("RETRIFLOW_STORAGE_LOCAL_DIR", None)
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

    def test_create_knowledge_base_rejects_duplicate_name(self) -> None:
        first_response = self.client.post(
            "/api/v1/knowledge-bases",
            json={"name": "重复知识库", "collection_name": "duplicatekb"},
        )
        self.assertEqual(first_response.status_code, 201)

        duplicate_response = self.client.post(
            "/api/v1/knowledge-bases",
            json={"name": "重复知识库", "collection_name": "duplicatekb2"},
        )

        self.assertEqual(duplicate_response.status_code, 409)
        self.assertIn("知识库已存在", duplicate_response.json()["detail"])

    def test_delete_knowledge_base_deletes_storage_bucket(self) -> None:
        from modules.knowledge.service import RetriFlowKnowledgeService
        from schemas.knowledge import KnowledgeBaseCreateRequest

        service = RetriFlowKnowledgeService()
        deleted_buckets: list[str] = []
        service.file_storage.ensure_bucket = lambda bucket: None
        service.file_storage.delete_bucket = deleted_buckets.append
        created = service.create_knowledge_base(
            KnowledgeBaseCreateRequest(name="Bucket Delete KB", collection_name="bucketdeletekb")
        )

        service.delete_knowledge_base(created.id)

        self.assertEqual(deleted_buckets, ["bucketdeletekb"])

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
        self.assertEqual(refreshed_kb["indexed_document_count"], 0)
        self.assertEqual(refreshed_kb["chunk_count"], 0)

    def test_knowledge_base_list_returns_global_chunk_statistics(self) -> None:
        first = self.client.post(
            "/api/v1/knowledge-bases",
            json={"name": "Stats KB A", "collection_name": "statskba"},
        ).json()
        second = self.client.post(
            "/api/v1/knowledge-bases",
            json={"name": "Stats KB B", "collection_name": "statskbb"},
        ).json()

        first_doc = self.client.post(
            f"/api/v1/knowledge-bases/{first['id']}/documents",
            json={
                "title": "Stats Document A",
                "content": "Chunk stats document A. " * 60,
                "document_type": "manual",
                "chunk_strategy": "fixed",
                "chunk_size": 120,
                "chunk_overlap": 0,
            },
        ).json()
        second_doc = self.client.post(
            f"/api/v1/knowledge-bases/{second['id']}/documents",
            json={
                "title": "Stats Document B",
                "content": "Chunk stats document B. " * 80,
                "document_type": "manual",
                "chunk_strategy": "fixed",
                "chunk_size": 160,
                "chunk_overlap": 0,
            },
        ).json()

        payload = self.client.get("/api/v1/knowledge-bases").json()
        by_id = {item["id"]: item for item in payload["items"]}

        self.assertEqual(by_id[first["id"]]["document_count"], 1)
        self.assertEqual(by_id[first["id"]]["indexed_document_count"], 1)
        self.assertEqual(by_id[first["id"]]["chunk_count"], first_doc["vector_chunk_count"])
        self.assertEqual(by_id[second["id"]]["document_count"], 1)
        self.assertEqual(by_id[second["id"]]["indexed_document_count"], 1)
        self.assertEqual(by_id[second["id"]]["chunk_count"], second_doc["vector_chunk_count"])
        self.assertGreater(sum(item["chunk_count"] for item in payload["items"]), 1)

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

    def test_document_changes_do_not_overwrite_route_profile_sample_questions(self) -> None:
        created = self.client.post(
            "/api/v1/knowledge-bases",
            json={"name": "Insurance System", "collection_name": "insurance"},
        ).json()
        kb_id = created["id"]
        saved_questions = ["保险系统登录失败怎么办？", "保险系统保单查询入口在哪里？"]

        update_resp = self.client.put(
            f"/api/v1/knowledge-bases/{kb_id}/route-profile",
            json={
                "profile_text": "保险系统示例问题由用户维护",
                "sample_questions": saved_questions,
                "keywords": ["insurance"],
            },
        )
        self.assertEqual(update_resp.status_code, 200)

        create_doc_resp = self.client.post(
            f"/api/v1/knowledge-bases/{kb_id}/documents",
            json={
                "title": "互联网保险系统数据安全规范",
                "source_type": "manual",
                "content": "pii 相关流程与数据安全说明。",
            },
        )
        self.assertEqual(create_doc_resp.status_code, 201)

        profile = self.client.get(f"/api/v1/knowledge-bases/{kb_id}/route-profile").json()
        self.assertEqual(profile["sample_questions"], saved_questions)
        self.assertIn("互联网保险系统数据安全规范", profile["profile_text"])


if __name__ == "__main__":
    unittest.main()
