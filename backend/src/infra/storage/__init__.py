"""File storage adapters used by upload ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Protocol
from uuid import uuid4
import re

from core.config import get_settings


@dataclass(frozen=True)
class StoredFile:
    uri: str
    filename: str
    content_type: str
    size: int


class FileStorageService(Protocol):
    def upload_bytes(
        self,
        content: bytes,
        original_filename: str,
        content_type: str | None = None,
        bucket_name: str | None = None,
    ) -> StoredFile:
        ...

    def open_stream(self, uri: str) -> BinaryIO:
        ...

    def delete_by_uri(self, uri: str) -> None:
        ...

    def ensure_bucket(self, bucket_name: str) -> None:
        ...

    def delete_bucket(self, bucket_name: str) -> None:
        ...


class LocalFileStorageService:
    scheme = "local://"

    def __init__(self, base_dir: str | Path | None = None) -> None:
        settings = get_settings()
        configured_dir = base_dir or settings.storage_local_dir
        self.base_dir = Path(configured_dir).expanduser().resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def upload_bytes(
        self,
        content: bytes,
        original_filename: str,
        content_type: str | None = None,
        bucket_name: str | None = None,
    ) -> StoredFile:
        filename = self._safe_filename(original_filename)
        object_name = f"{uuid4().hex}-{filename}"
        target_path = (self.base_dir / object_name).resolve()
        self._ensure_inside_base(target_path)
        target_path.write_bytes(content)
        return StoredFile(
            uri=f"{self.scheme}{object_name}",
            filename=filename,
            content_type=content_type or "application/octet-stream",
            size=len(content),
        )

    def open_stream(self, uri: str) -> BinaryIO:
        return self._path_from_uri(uri).open("rb")

    def delete_by_uri(self, uri: str) -> None:
        path = self._path_from_uri(uri)
        if path.exists():
            path.unlink()

    def ensure_bucket(self, bucket_name: str) -> None:
        return None

    def delete_bucket(self, bucket_name: str) -> None:
        return None

    def _path_from_uri(self, uri: str) -> Path:
        if not uri.startswith(self.scheme):
            raise ValueError("Unsupported storage URI")
        object_name = uri[len(self.scheme) :]
        if not object_name or "/" in object_name or "\\" in object_name:
            raise ValueError("Invalid local storage URI")
        path = (self.base_dir / object_name).resolve()
        self._ensure_inside_base(path)
        return path

    def _ensure_inside_base(self, path: Path) -> None:
        if path != self.base_dir and self.base_dir not in path.parents:
            raise ValueError("Storage path escapes the configured local directory")

    @staticmethod
    def _safe_filename(filename: str) -> str:
        name = Path(filename or "upload.bin").name.strip() or "upload.bin"
        return re.sub(r"[^A-Za-z0-9._-]+", "_", name)


class S3FileStorageService:
    scheme = "s3://"

    def __init__(
        self,
        endpoint: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        region: str | None = None,
        client=None,
    ) -> None:
        settings = get_settings()
        self.endpoint = endpoint or settings.s3_endpoint
        self.access_key_id = access_key_id or settings.s3_access_key_id
        self.secret_access_key = secret_access_key or settings.s3_secret_access_key
        self.region = region or settings.s3_region
        self._client = client

    @property
    def client(self):
        if self._client is None:
            try:
                import boto3
                from botocore.config import Config
            except ImportError as exc:
                raise RuntimeError("S3 storage requires boto3. Install backend dependencies first.") from exc
            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name=self.region,
                config=Config(s3={"addressing_style": "path"}),
            )
        return self._client

    def upload_bytes(
        self,
        content: bytes,
        original_filename: str,
        content_type: str | None = None,
        bucket_name: str | None = None,
    ) -> StoredFile:
        bucket = self._validate_bucket_name(bucket_name)
        filename = LocalFileStorageService._safe_filename(original_filename)
        object_key = self._generate_object_key(filename)
        resolved_content_type = content_type or "application/octet-stream"
        self.client.put_object(
            Bucket=bucket,
            Key=object_key,
            Body=content,
            ContentType=resolved_content_type,
        )
        return StoredFile(
            uri=f"{self.scheme}{bucket}/{object_key}",
            filename=filename,
            content_type=resolved_content_type,
            size=len(content),
        )

    def open_stream(self, uri: str) -> BinaryIO:
        bucket, key = self._parse_s3_uri(uri)
        response = self.client.get_object(Bucket=bucket, Key=key)
        body = response["Body"]
        data = body.read()
        close = getattr(body, "close", None)
        if callable(close):
            close()
        return BytesIO(data)

    def delete_by_uri(self, uri: str) -> None:
        bucket, key = self._parse_s3_uri(uri)
        self.client.delete_object(Bucket=bucket, Key=key)

    def ensure_bucket(self, bucket_name: str) -> None:
        bucket = self._validate_bucket_name(bucket_name)
        try:
            self.client.create_bucket(Bucket=bucket)
        except Exception as exc:
            if self._is_bucket_exists_error(exc):
                raise ValueError(f"Storage bucket already exists: {bucket}") from exc
            raise

    def delete_bucket(self, bucket_name: str) -> None:
        bucket = self._validate_bucket_name(bucket_name)
        try:
            self.client.delete_bucket(Bucket=bucket)
        except Exception:
            return None

    @staticmethod
    def _generate_object_key(filename: str) -> str:
        return f"{uuid4().hex}-{filename}"

    @staticmethod
    def _validate_bucket_name(bucket_name: str | None) -> str:
        bucket = (bucket_name or "").strip()
        if not bucket:
            raise ValueError("S3 bucket name is required")
        return bucket

    def _parse_s3_uri(self, uri: str) -> tuple[str, str]:
        if not uri.startswith(self.scheme):
            raise ValueError("Unsupported storage URI")
        path = uri[len(self.scheme) :]
        bucket, sep, key = path.partition("/")
        if not bucket or not sep or not key:
            raise ValueError("Invalid S3 storage URI")
        return bucket, key

    @staticmethod
    def _is_bucket_exists_error(exc: Exception) -> bool:
        response = getattr(exc, "response", None)
        code = ""
        if isinstance(response, dict):
            code = str(response.get("Error", {}).get("Code", ""))
        return code in {"BucketAlreadyExists", "BucketAlreadyOwnedByYou"} or "BucketAlready" in exc.__class__.__name__


def resolve_file_storage() -> FileStorageService:
    settings = get_settings()
    backend = settings.storage_backend.strip().lower()
    if backend == "local":
        return LocalFileStorageService(settings.storage_local_dir)
    if backend in {"s3", "rustfs"}:
        return S3FileStorageService()
    raise ValueError(f"Unsupported storage backend: {settings.storage_backend}")
