import sys
import unittest
from io import BytesIO
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))


class _FakeS3Body:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.closed = False

    def read(self) -> bytes:
        return self.data

    def close(self) -> None:
        self.closed = True


class _FakeS3Client:
    def __init__(self) -> None:
        self.buckets: set[str] = set()
        self.objects: dict[tuple[str, str], tuple[bytes, str]] = {}

    def create_bucket(self, Bucket: str) -> None:
        if Bucket in self.buckets:
            error = RuntimeError("already exists")
            error.response = {"Error": {"Code": "BucketAlreadyOwnedByYou"}}
            raise error
        self.buckets.add(Bucket)

    def put_object(self, Bucket: str, Key: str, Body: bytes, ContentType: str) -> None:
        self.objects[(Bucket, Key)] = (Body, ContentType)

    def get_object(self, Bucket: str, Key: str) -> dict:
        return {"Body": _FakeS3Body(self.objects[(Bucket, Key)][0])}

    def delete_object(self, Bucket: str, Key: str) -> None:
        self.objects.pop((Bucket, Key), None)

    def list_objects_v2(self, Bucket: str, **kwargs) -> dict:
        contents = [{"Key": key} for bucket, key in self.objects if bucket == Bucket]
        return {"Contents": contents, "IsTruncated": False}

    def delete_objects(self, Bucket: str, Delete: dict) -> None:
        for item in Delete.get("Objects", []):
            self.objects.pop((Bucket, item.get("Key")), None)

    def delete_bucket(self, Bucket: str) -> None:
        if any(bucket == Bucket for bucket, _key in self.objects):
            error = RuntimeError("bucket is not empty")
            error.response = {"Error": {"Code": "BucketNotEmpty"}}
            raise error
        self.buckets.discard(Bucket)


class RetriFlowStorageTests(unittest.TestCase):
    def test_s3_storage_upload_open_and_delete_uses_stable_content_hash_uri(self) -> None:
        from infra.storage import S3FileStorageService

        fake_client = _FakeS3Client()
        storage = S3FileStorageService(client=fake_client)
        storage.ensure_bucket("policykb")

        stored = storage.upload_bytes(
            b"hello retriflow",
            "互联网保险系统数据安全规范.md",
            "text/markdown",
            bucket_name="policykb",
        )

        self.assertRegex(stored.uri, r"^s3://policykb/[a-f0-9]{16}-互联网保险系统数据安全规范\.md$")
        self.assertEqual(stored.filename, "互联网保险系统数据安全规范.md")
        self.assertEqual(stored.content_type, "text/markdown")
        with storage.open_stream(stored.uri) as stream:
            self.assertEqual(stream.read(), b"hello retriflow")

        storage.delete_by_uri(stored.uri)
        self.assertEqual(fake_client.objects, {})

    def test_s3_storage_reports_existing_bucket(self) -> None:
        from infra.storage import S3FileStorageService

        fake_client = _FakeS3Client()
        storage = S3FileStorageService(client=fake_client)
        storage.ensure_bucket("policykb")

        with self.assertRaises(ValueError):
            storage.ensure_bucket("policykb")

    def test_s3_storage_deletes_objects_before_bucket(self) -> None:
        from infra.storage import S3FileStorageService

        fake_client = _FakeS3Client()
        storage = S3FileStorageService(client=fake_client)
        storage.ensure_bucket("policykb")
        storage.upload_bytes(b"one", "one.md", "text/markdown", bucket_name="policykb")
        storage.upload_bytes(b"two", "two.md", "text/markdown", bucket_name="policykb")

        storage.delete_bucket("policykb")

        self.assertNotIn("policykb", fake_client.buckets)
        self.assertEqual(fake_client.objects, {})


if __name__ == "__main__":
    unittest.main()
