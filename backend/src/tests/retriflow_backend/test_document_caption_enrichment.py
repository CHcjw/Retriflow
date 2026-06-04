import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))


class RetriFlowDocumentCaptionEnrichmentTests(unittest.TestCase):
    def test_returns_empty_result_when_ocr_is_disabled(self) -> None:
        from domain.document_caption_enrichment import RetriFlowImageCaptionEnrichmentService

        service = RetriFlowImageCaptionEnrichmentService(ocr_enabled=False)

        result = service.extract_page_captions(
            filename="sample.docx",
            content_bytes=b"fake",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        self.assertEqual(result, {})

    def test_prefers_only_caption_like_ocr_lines(self) -> None:
        from domain.document_caption_enrichment import RetriFlowImageCaptionEnrichmentService

        service = RetriFlowImageCaptionEnrichmentService(ocr_enabled=True)

        result = service._extract_caption_candidates_from_ocr_text(
            "Random paragraph\n图1 系统架构总览\nAnother text\nFigure 2 Retrieval flow"
        )

        self.assertEqual(result, ["图1 系统架构总览", "Figure 2 Retrieval flow"])

    def test_returns_remote_ocr_page_captions_when_service_enabled(self) -> None:
        from domain.document_caption_enrichment import RetriFlowImageCaptionEnrichmentService

        service = RetriFlowImageCaptionEnrichmentService(
            ocr_enabled=True,
            ocr_service_endpoint="http://127.0.0.1:9889",
        )

        class FakeResponse:
            status_code = 200

            @staticmethod
            def json() -> dict:
                return {
                    "pages": [
                        {"page_number": 1, "captions": ["Figure 1 OCR caption"]},
                        {"page_number": 2, "captions": ["图2 检索流程"]},
                    ]
                }

            @staticmethod
            def raise_for_status() -> None:
                return None

        with patch("domain.document_caption_enrichment.httpx.post", return_value=FakeResponse()) as post_mock:
            result = service.extract_page_captions(
                filename="sample.docx",
                content_bytes=b"fake",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

        self.assertEqual(result, {1: ["Figure 1 OCR caption"], 2: ["图2 检索流程"]})
        post_mock.assert_called_once()

    def test_extracts_docx_embedded_images_and_calls_ocr_service(self) -> None:
        from domain.document_caption_enrichment import RetriFlowImageCaptionEnrichmentService

        service = RetriFlowImageCaptionEnrichmentService(
            ocr_enabled=True,
            ocr_service_endpoint="http://127.0.0.1:9889",
        )

        docx_bytes = self._build_minimal_docx_with_image()

        class FakeResponse:
            status_code = 200

            @staticmethod
            def json() -> dict:
                return {"pages": [{"page_number": 1, "captions": ["图1 OCR image caption"]}]}

            @staticmethod
            def raise_for_status() -> None:
                return None

        with patch("domain.document_caption_enrichment.httpx.post", return_value=FakeResponse()) as post_mock:
            result = service.extract_page_captions(
                filename="sample.docx",
                content_bytes=docx_bytes,
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

        self.assertEqual(result, {1: ["图1 OCR image caption"]})
        self.assertGreaterEqual(post_mock.call_count, 1)
        sent_file = post_mock.call_args.kwargs["files"]["file"]
        self.assertEqual(sent_file[0], "image1.png")
        self.assertEqual(sent_file[2], "image/png")

    def test_prefers_tika_unpack_images_before_local_docx_unzip(self) -> None:
        from domain.document_caption_enrichment import RetriFlowImageCaptionEnrichmentService

        service = RetriFlowImageCaptionEnrichmentService(
            ocr_enabled=True,
            ocr_service_endpoint="http://127.0.0.1:9889",
            tika_endpoint="http://127.0.0.1:9998",
        )

        docx_bytes = self._build_minimal_docx_with_image()
        unpack_zip_bytes = self._build_unpack_zip_with_image()

        class FakeUnpackResponse:
            status_code = 200
            content = unpack_zip_bytes

            @staticmethod
            def raise_for_status() -> None:
                return None

        class FakeOcrResponse:
            status_code = 200

            @staticmethod
            def json() -> dict:
                return {"pages": [{"page_number": 1, "captions": ["图1 OCR image caption"]}]}

            @staticmethod
            def raise_for_status() -> None:
                return None

        with (
            patch("domain.document_caption_enrichment.httpx.put", return_value=FakeUnpackResponse()) as unpack_mock,
            patch("domain.document_caption_enrichment.httpx.post", return_value=FakeOcrResponse()) as post_mock,
        ):
            result = service.extract_page_captions(
                filename="sample.docx",
                content_bytes=docx_bytes,
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

        self.assertEqual(result, {1: ["图1 OCR image caption"]})
        unpack_mock.assert_called_once()
        sent_file = post_mock.call_args.kwargs["files"]["file"]
        self.assertEqual(sent_file[0], "tika-image.png")
        self.assertEqual(sent_file[2], "image/png")

    def test_extracts_pdf_images_via_tika_unpack_and_calls_ocr_service(self) -> None:
        from domain.document_caption_enrichment import RetriFlowImageCaptionEnrichmentService

        service = RetriFlowImageCaptionEnrichmentService(
            ocr_enabled=True,
            ocr_service_endpoint="http://127.0.0.1:9889",
            tika_endpoint="http://127.0.0.1:9998",
        )

        unpack_zip_bytes = self._build_unpack_zip_with_image()

        class FakeUnpackResponse:
            status_code = 200
            content = unpack_zip_bytes

            @staticmethod
            def raise_for_status() -> None:
                return None

        class FakeOcrResponse:
            status_code = 200

            @staticmethod
            def json() -> dict:
                return {"pages": [{"page_number": 1, "captions": ["Figure 1 OCR from pdf image"]}]}

            @staticmethod
            def raise_for_status() -> None:
                return None

        with (
            patch("domain.document_caption_enrichment.httpx.put", return_value=FakeUnpackResponse()) as unpack_mock,
            patch("domain.document_caption_enrichment.httpx.post", return_value=FakeOcrResponse()) as post_mock,
        ):
            result = service.extract_page_captions(
                filename="sample.pdf",
                content_bytes=b"%PDF-fake",
                content_type="application/pdf",
            )

        self.assertEqual(result, {1: ["Figure 1 OCR from pdf image"]})
        unpack_mock.assert_called_once()
        sent_file = post_mock.call_args.kwargs["files"]["file"]
        self.assertEqual(sent_file[0], "tika-image.png")
        self.assertEqual(sent_file[2], "image/png")

    @staticmethod
    def _build_minimal_docx_with_image() -> bytes:
        buffer = io.BytesIO()
        with ZipFile(buffer, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types></Types>")
            archive.writestr("word/document.xml", "<w:document></w:document>")
            archive.writestr("word/media/image1.png", b"\x89PNG\r\n\x1a\nfakepng")
        return buffer.getvalue()

    @staticmethod
    def _build_unpack_zip_with_image() -> bytes:
        buffer = io.BytesIO()
        with ZipFile(buffer, "w") as archive:
            archive.writestr("tika-image.png", b"\x89PNG\r\n\x1a\nfrom-tika")
            archive.writestr("__TEXT__/tika-image.png.txt", "ignored")
            archive.writestr("__METADATA__/tika-image.png.metadata.json", "{}")
        return buffer.getvalue()


if __name__ == "__main__":
    unittest.main()
