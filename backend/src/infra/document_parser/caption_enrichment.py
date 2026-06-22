import mimetypes
import re
from io import BytesIO
from zipfile import BadZipFile, ZipFile

import httpx

from infra.document_parser.tika_client import build_content_disposition


class RetriFlowImageCaptionEnrichmentService:
    CAPTION_PREFIX_PATTERN = re.compile(
        r"^(图\s*\d+|表\s*\d+|figure\s*\d+|fig\.\s*\d+|image\s*\d+)\b",
        re.IGNORECASE,
    )
    DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def __init__(
        self,
        ocr_enabled: bool = False,
        ocr_service_endpoint: str = "http://127.0.0.1:9889",
        request_timeout_seconds: int = 30,
        tika_endpoint: str = "http://127.0.0.1:9998",
        tika_request_timeout_seconds: int = 60,
    ) -> None:
        self.ocr_enabled = ocr_enabled
        self.ocr_service_endpoint = ocr_service_endpoint.rstrip("/")
        self.request_timeout_seconds = request_timeout_seconds
        self.tika_endpoint = tika_endpoint.rstrip("/")
        self.tika_request_timeout_seconds = tika_request_timeout_seconds

    def extract_page_captions(
        self,
        filename: str,
        content_bytes: bytes,
        content_type: str,
    ) -> dict[int, list[str]]:
        if not self.ocr_enabled:
            return {}

        extracted_images = self._extract_embedded_images(
            filename=filename,
            content_bytes=content_bytes,
            content_type=content_type,
        )
        if extracted_images:
            return self._ocr_extracted_images(extracted_images)

        response = self._call_ocr_service(
            filename=filename,
            payload=content_bytes,
            content_type=content_type or "application/octet-stream",
        )
        return self._normalize_ocr_payload(response.json())

    def _extract_embedded_images(
        self,
        filename: str,
        content_bytes: bytes,
        content_type: str,
    ) -> list[tuple[str, bytes, str]]:
        tika_images = self._extract_images_via_tika_unpack(
            filename=filename,
            content_bytes=content_bytes,
            content_type=content_type,
        )
        if tika_images:
            return tika_images

        return self._extract_images_via_local_docx_unzip(
            filename=filename,
            content_bytes=content_bytes,
            content_type=content_type,
        )

    def _extract_images_via_tika_unpack(
        self,
        filename: str,
        content_bytes: bytes,
        content_type: str,
    ) -> list[tuple[str, bytes, str]]:
        headers = {
            "Content-Type": content_type or "application/octet-stream",
            "Content-Disposition": build_content_disposition(filename),
        }
        try:
            response = httpx.put(
                f"{self.tika_endpoint}/unpack",
                content=content_bytes,
                headers=headers,
                timeout=self.tika_request_timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            return []

        return self._parse_unpack_zip_images(response.content)

    def _extract_images_via_local_docx_unzip(
        self,
        filename: str,
        content_bytes: bytes,
        content_type: str,
    ) -> list[tuple[str, bytes, str]]:
        if (content_type or "").lower() != self.DOCX_CONTENT_TYPE:
            return []
        if not filename.lower().endswith(".docx"):
            return []

        try:
            archive = ZipFile(BytesIO(content_bytes))
        except BadZipFile:
            return []

        images: list[tuple[str, bytes, str]] = []
        with archive:
            for name in archive.namelist():
                if not name.startswith("word/media/") or name.endswith("/"):
                    continue
                payload = archive.read(name)
                image_name = name.rsplit("/", 1)[-1]
                image_content_type = mimetypes.guess_type(image_name)[0] or "application/octet-stream"
                images.append((image_name, payload, image_content_type))
        return images

    def _parse_unpack_zip_images(self, payload: bytes) -> list[tuple[str, bytes, str]]:
        try:
            archive = ZipFile(BytesIO(payload))
        except BadZipFile:
            return []

        images: list[tuple[str, bytes, str]] = []
        with archive:
            for name in archive.namelist():
                if name.endswith("/") or name.startswith("__TEXT__/") or name.startswith("__METADATA__/"):
                    continue
                image_content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
                if not image_content_type.startswith("image/"):
                    continue
                images.append((name.rsplit("/", 1)[-1], archive.read(name), image_content_type))
        return images

    def _ocr_extracted_images(self, images: list[tuple[str, bytes, str]]) -> dict[int, list[str]]:
        results: dict[int, list[str]] = {}
        page_number = 1
        for image_name, image_bytes, image_content_type in images:
            response = self._call_ocr_service(
                filename=image_name,
                payload=image_bytes,
                content_type=image_content_type,
            )
            normalized = self._normalize_ocr_payload(response.json())
            if not normalized:
                continue
            merged_captions: list[str] = []
            for captions in normalized.values():
                merged_captions.extend(captions)
            if merged_captions:
                results.setdefault(page_number, []).extend(merged_captions)
        return results

    def _call_ocr_service(self, filename: str, payload: bytes, content_type: str) -> httpx.Response:
        response = httpx.post(
            f"{self.ocr_service_endpoint}/ocr/captions",
            files={
                "file": (
                    filename,
                    payload,
                    content_type,
                )
            },
            timeout=self.request_timeout_seconds,
        )
        response.raise_for_status()
        return response

    def _normalize_ocr_payload(self, payload: dict) -> dict[int, list[str]]:
        results: dict[int, list[str]] = {}
        for page in payload.get("pages", []):
            page_number = int(page.get("page_number", 0) or 0)
            if page_number <= 0:
                continue
            captions = [
                caption
                for caption in (
                    self._normalize_caption_text(item)
                    for item in page.get("captions", [])
                )
                if caption and self._looks_like_caption(caption)
            ]
            if captions:
                results[page_number] = captions
        return results

    def _extract_caption_candidates_from_ocr_text(self, text: str) -> list[str]:
        candidates: list[str] = []
        for raw_line in text.splitlines():
            line = self._normalize_caption_text(raw_line)
            if not line:
                continue
            if self._looks_like_caption(line):
                candidates.append(line)
        return candidates

    @classmethod
    def _looks_like_caption(cls, text: str) -> bool:
        return bool(cls.CAPTION_PREFIX_PATTERN.match(text.strip()))

    @staticmethod
    def _normalize_caption_text(text: str) -> str:
        normalized = (text or "").strip()
        replacements = {
            "\u037c": "图",
            "\u934f": "图",
            "\u741b": "表",
        }
        for source, target in replacements.items():
            if normalized.startswith(source):
                normalized = target + normalized[len(source) :]
        return normalized
