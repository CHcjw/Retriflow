import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))


class RetriFlowDocumentParserTests(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop("RETRIFLOW_TIKA_ENABLED", None)
        os.environ.pop("RETRIFLOW_TIKA_OCR_ENABLED", None)
        from core.config import get_settings

        get_settings.cache_clear()

    def test_parse_upload_passes_ocr_captions_to_structured_extractor(self) -> None:
        os.environ["RETRIFLOW_TIKA_ENABLED"] = "true"
        os.environ["RETRIFLOW_TIKA_OCR_ENABLED"] = "true"

        from core.config import get_settings
        from infra.document_parser import RetriFlowDocumentParserService
        from schemas.document_structure import ParagraphBlock, RawParsedDocument, StructuredDocument

        get_settings.cache_clear()

        extractor_result = StructuredDocument(
            file_name="sample.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            title="Sample",
            metadata={},
            blocks=[
                ParagraphBlock(
                    block_index=0,
                    page_number=1,
                    text="RetriFlow parser output",
                )
            ],
            text_content="RetriFlow parser output",
        )

        with (
            patch("infra.document_parser.service.RetriFlowTikaClient.detect_content_type", return_value="application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            patch("infra.document_parser.service.RetriFlowTikaClient.parse_bytes") as parse_bytes_mock,
            patch("infra.document_parser.service.RetriFlowImageCaptionEnrichmentService.extract_page_captions") as caption_mock,
            patch("infra.document_parser.service.RetriFlowStructuredExtractionService.extract_from_xhtml") as extract_mock,
        ):
            parse_bytes_mock.return_value = RawParsedDocument(
                file_name="sample.docx",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                metadata={"dc:title": "Sample"},
                xhtml_content="<html><body><div class='page'><p>content</p></div></body></html>",
                text_content="content",
            )
            caption_mock.return_value = {1: ["图1 OCR caption"]}
            extract_mock.return_value = extractor_result

            service = RetriFlowDocumentParserService()
            result = service.parse_upload(
                filename="sample.docx",
                content_bytes=b"fake-binary",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

        self.assertEqual(result.title, "Sample")
        extract_mock.assert_called_once()
        self.assertEqual(extract_mock.call_args.kwargs["ocr_captions_by_page"], {1: ["图1 OCR caption"]})

    def test_parse_upload_prefers_tika_detected_content_type_over_uploaded_header(self) -> None:
        os.environ["RETRIFLOW_TIKA_ENABLED"] = "true"

        from core.config import get_settings
        from infra.document_parser import RetriFlowDocumentParserService
        from schemas.document_structure import ParagraphBlock, RawParsedDocument, StructuredDocument

        get_settings.cache_clear()

        extractor_result = StructuredDocument(
            file_name="sample.pdf",
            content_type="application/pdf",
            title="Sample PDF",
            metadata={},
            blocks=[
                ParagraphBlock(
                    block_index=0,
                    page_number=1,
                    text="RetriFlow parser output",
                )
            ],
            text_content="RetriFlow parser output",
        )

        with (
            patch("infra.document_parser.service.RetriFlowTikaClient.detect_content_type", return_value="application/pdf") as detect_mock,
            patch("infra.document_parser.service.RetriFlowTikaClient.parse_bytes") as parse_bytes_mock,
            patch("infra.document_parser.service.RetriFlowImageCaptionEnrichmentService.extract_page_captions", return_value={}) as caption_mock,
            patch("infra.document_parser.service.RetriFlowStructuredExtractionService.extract_from_xhtml", return_value=extractor_result),
        ):
            parse_bytes_mock.return_value = RawParsedDocument(
                file_name="sample.pdf",
                content_type="application/pdf",
                metadata={"dc:title": "Sample PDF"},
                xhtml_content="<html><body><div class='page'><p>content</p></div></body></html>",
                text_content="content",
            )

            service = RetriFlowDocumentParserService()
            result = service.parse_upload(
                filename="sample.pdf",
                content_bytes=b"%PDF-1.4 fake-binary",
                content_type="application/octet-stream",
            )

        self.assertEqual(result.title, "Sample PDF")
        detect_mock.assert_called_once()
        self.assertEqual(parse_bytes_mock.call_args.args[2], "application/pdf")
        self.assertEqual(caption_mock.call_args.kwargs["content_type"], "application/pdf")


if __name__ == "__main__":
    unittest.main()
