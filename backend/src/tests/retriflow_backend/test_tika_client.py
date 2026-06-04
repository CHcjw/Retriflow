import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))


class RetriFlowTikaClientTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["RETRIFLOW_TIKA_ENABLED"] = "true"
        os.environ["RETRIFLOW_TIKA_ENDPOINT"] = "http://127.0.0.1:9998"

        from core.config import get_settings

        get_settings.cache_clear()

    def tearDown(self) -> None:
        os.environ.pop("RETRIFLOW_TIKA_ENABLED", None)
        os.environ.pop("RETRIFLOW_TIKA_ENDPOINT", None)

        from core.config import get_settings

        get_settings.cache_clear()

    def test_parse_bytes_returns_valid_raw_parsed_document(self) -> None:
        from domain.tika_client import RetriFlowTikaClient

        xml_response = httpx.Response(
            200,
            text=(
                "<html xmlns='http://www.w3.org/1999/xhtml'>"
                "<body><div class='page'><h1>RetriFlow</h1><p>Structured parsing</p></div></body></html>"
            ),
        )
        meta_response = httpx.Response(
            200,
            json=[
                {
                    "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "dc:title": "RetriFlow Spec",
                    "X-TIKA:content": "RetriFlow Structured parsing",
                }
            ],
        )

        with patch("domain.tika_client.httpx.put", side_effect=[xml_response, meta_response]):
            parsed = RetriFlowTikaClient().parse_bytes(
                filename="retriflow-spec.docx",
                content_bytes=b"fake-docx",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

        self.assertEqual(parsed.file_name, "retriflow-spec.docx")
        self.assertEqual(parsed.content_type, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        self.assertIn("<h1>RetriFlow</h1>", parsed.xhtml_content)
        self.assertEqual(parsed.text_content, "RetriFlow Structured parsing")
        self.assertEqual(parsed.metadata["dc:title"], "RetriFlow Spec")

    def test_parse_bytes_rejects_empty_rmeta_payload(self) -> None:
        from domain.tika_client import RetriFlowTikaClient

        xml_response = httpx.Response(
            200,
            text="<html xmlns='http://www.w3.org/1999/xhtml'><body></body></html>",
        )
        meta_response = httpx.Response(200, json=[])

        with patch("domain.tika_client.httpx.put", side_effect=[xml_response, meta_response]):
            with self.assertRaises(ValueError):
                RetriFlowTikaClient().parse_bytes(
                    filename="broken.docx",
                    content_bytes=b"broken",
                    content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )

    def test_detect_content_type_returns_tika_detected_mime(self) -> None:
        from domain.tika_client import RetriFlowTikaClient

        detect_response = httpx.Response(200, text="application/pdf")

        with patch("domain.tika_client.httpx.put", return_value=detect_response) as detect_mock:
            detected = RetriFlowTikaClient().detect_content_type(
                filename="unknown.bin",
                content_bytes=b"%PDF-1.4 fake",
                fallback_content_type="application/octet-stream",
            )

        self.assertEqual(detected, "application/pdf")
        detect_mock.assert_called_once()

    def test_detect_content_type_falls_back_when_tika_detect_fails(self) -> None:
        from domain.tika_client import RetriFlowTikaClient

        detect_response = httpx.Response(500, text="boom")

        with patch("domain.tika_client.httpx.put", return_value=detect_response):
            detected = RetriFlowTikaClient().detect_content_type(
                filename="unknown.bin",
                content_bytes=b"fake",
                fallback_content_type="text/plain",
            )

        self.assertEqual(detected, "text/plain")


if __name__ == "__main__":
    unittest.main()
