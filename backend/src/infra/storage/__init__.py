"""File storage adapters used by upload ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4
import re

from core.config import get_settings


@dataclass(frozen=True)
class StoredFile:
    uri: str
    filename: str
    content_type: str
    size: int


class LocalFileStorageService:
    scheme = "local://"

    def __init__(self, base_dir: str | Path | None = None) -> None:
        settings = get_settings()
        configured_dir = base_dir or settings.storage_local_dir
        self.base_dir = Path(configured_dir).expanduser().resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def upload_bytes(self, content: bytes, original_filename: str, content_type: str | None = None) -> StoredFile:
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


def resolve_file_storage() -> LocalFileStorageService:
    settings = get_settings()
    if settings.storage_backend != "local":
        raise ValueError(f"Unsupported storage backend: {settings.storage_backend}")
    return LocalFileStorageService(settings.storage_local_dir)
