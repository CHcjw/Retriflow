import httpx

from core.config import get_settings
from schemas.document_structure import RawParsedDocument


class RetriFlowTikaClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    def detect_content_type(self, filename: str, content_bytes: bytes, fallback_content_type: str) -> str:
        if not self.settings.tika_enabled:
            return fallback_content_type or "application/octet-stream"

        headers = {
            "Content-Type": fallback_content_type or "application/octet-stream",
            "Content-Disposition": f'attachment; filename="{filename}"',
        }
        request_options = {"timeout": self.settings.tika_request_timeout_seconds}
        base_url = self.settings.tika_endpoint.rstrip("/")

        try:
            response = httpx.put(
                f"{base_url}/detect/stream",
                content=content_bytes,
                headers=headers,
                **request_options,
            )
        except httpx.HTTPError:
            return fallback_content_type or "application/octet-stream"

        if response.status_code >= 400:
            return fallback_content_type or "application/octet-stream"

        detected = (response.text or "").strip()
        return detected or fallback_content_type or "application/octet-stream"

    def parse_bytes(self, filename: str, content_bytes: bytes, content_type: str) -> RawParsedDocument:
        if not self.settings.tika_enabled:
            raise RuntimeError("Tika parsing is disabled. Set RETRIFLOW_TIKA_ENABLED=true to enable it.")

        headers = {
            "Content-Type": content_type or "application/octet-stream",
            "Content-Disposition": f'attachment; filename="{filename}"',
        }
        request_options = {"timeout": self.settings.tika_request_timeout_seconds}
        base_url = self.settings.tika_endpoint.rstrip("/")

        xml_response = httpx.put(
            f"{base_url}/tika/xml",
            content=content_bytes,
            headers=headers,
            **request_options,
        )
        if xml_response.status_code >= 400:
            raise ValueError(f"Tika XML parse failed with status {xml_response.status_code}.")

        meta_response = httpx.put(
            f"{base_url}/rmeta/text",
            content=content_bytes,
            headers=headers,
            **request_options,
        )
        if meta_response.status_code >= 400:
            raise ValueError(f"Tika metadata parse failed with status {meta_response.status_code}.")

        xhtml_content = self._extract_xml_payload(xml_response)
        payload = meta_response.json()
        if isinstance(payload, list):
            if not payload:
                raise ValueError("Tika rmeta response is empty.")
            metadata = dict(payload[0])
        elif isinstance(payload, dict):
            metadata = dict(payload)
        else:
            raise ValueError("Tika rmeta response has an unsupported shape.")

        text_content = str(metadata.get("X-TIKA:content", "") or "").strip()
        parsed_content_type = str(metadata.get("Content-Type", content_type or "application/octet-stream"))

        return RawParsedDocument(
            file_name=filename,
            content_type=parsed_content_type,
            metadata=metadata,
            xhtml_content=xhtml_content,
            text_content=text_content,
        )

    @staticmethod
    def _extract_xml_payload(response: httpx.Response) -> str:
        content_type = (response.headers.get("content-type") or "").lower()
        if "application/json" in content_type:
            payload = response.json()
            if isinstance(payload, dict):
                return str(payload.get("X-TIKA:content", "") or "")
            if isinstance(payload, list) and payload:
                return str(payload[0].get("X-TIKA:content", "") or "")
            raise ValueError("Tika XML response did not include structured content.")
        return response.text
