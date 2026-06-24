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

    def delete_bucket(self, Bucket: str) -> None:
        self.buckets.discard(Bucket)


class RetriFlowStorageTests(unittest.TestCase):
    def test_s3_storage_upload_open_and_delete_uses_ragent_style_uri(self) -> None:
        from infra.storage import S3FileStorageService

        fake_client = _FakeS3Client()
        storage = S3FileStorageService(client=fake_client)
        storage.ensure_bucket("policykb")

        stored = storage.upload_bytes(
            b"hello retriflow",
            "source file.md",
            "text/markdown",
            bucket_name="policykb",
        )

        self.assertRegex(stored.uri, r"^s3://policykb/[a-f0-9]{32}-source_file\.md$")
        self.assertEqual(stored.filename, "source_file.md")
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


if __name__ == "__main__":
    unittest.main()
