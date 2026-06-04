import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))


class RetriFlowDocumentNormalizerTests(unittest.TestCase):
    def test_normalizes_whitespace_units_and_empty_values(self) -> None:
        from domain.document_normalizer import RetriFlowDocumentNormalizationService
        from schemas.document_structure import ParagraphBlock, StructuredDocument, TableBlock, TableCell, TableRow

        document = StructuredDocument(
            file_name="metrics.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            title=" Metrics ",
            blocks=[
                ParagraphBlock(
                    block_index=0,
                    page_number=1,
                    text="  Revenue   growth   20％  ",
                ),
                TableBlock(
                    block_index=1,
                    page_number=1,
                    headers=[" Metric ", " Value "],
                    rows=[
                        TableRow(
                            row_index=0,
                            cells=[
                                TableCell(row_index=0, column_index=0, text="Latency"),
                                TableCell(row_index=0, column_index=1, text=" N/A "),
                            ],
                        )
                    ],
                    row_count=1,
                    column_count=2,
                ),
            ],
            text_content=" Revenue growth 20％ ",
        )

        normalized = RetriFlowDocumentNormalizationService().normalize(document)

        self.assertEqual(normalized.title, "Metrics")
        self.assertEqual(normalized.blocks[0].text, "Revenue growth 20%")
        self.assertEqual(normalized.blocks[1].headers, ["Metric", "Value"])
        self.assertEqual(normalized.blocks[1].rows[0].cells[1].text, "")
        self.assertEqual(normalized.text_content, "Revenue growth 20%")

    def test_validate_document_rejects_invalid_heading_level(self) -> None:
        from domain.document_normalizer import RetriFlowDocumentNormalizationService
        from schemas.document_structure import HeadingBlock, StructuredDocument

        document = StructuredDocument.model_construct(
            file_name="broken.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            title="Broken",
            blocks=[
                HeadingBlock.model_construct(
                    block_type="heading",
                    block_index=0,
                    page_number=1,
                    heading_path=[],
                    level=7,
                    text="Bad heading",
                )
            ],
            metadata={},
            text_content="Bad heading",
        )

        with self.assertRaises(ValueError):
            RetriFlowDocumentNormalizationService().validate_document(document)

    def test_normalize_repairs_mojibake_caption_prefixes(self) -> None:
        from domain.document_normalizer import RetriFlowDocumentNormalizationService
        from schemas.document_structure import ImageCaptionBlock, StructuredDocument

        document = StructuredDocument(
            file_name="caption.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            title=" Caption ",
            blocks=[
                ImageCaptionBlock(
                    block_index=0,
                    page_number=1,
                    text="ͼ1 RetriFlow document parsing overview",
                )
            ],
            metadata={},
            text_content="ͼ1 RetriFlow document parsing overview",
        )

        normalized = RetriFlowDocumentNormalizationService().normalize(document)

        self.assertEqual(normalized.blocks[0].text, "图1 RetriFlow document parsing overview")
        self.assertEqual(normalized.text_content, "图1 RetriFlow document parsing overview")


if __name__ == "__main__":
    unittest.main()
