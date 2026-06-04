import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))


class RetriFlowDocumentStructureTests(unittest.TestCase):
    def test_extracts_headings_paragraphs_tables_and_captions_from_xhtml(self) -> None:
        from domain.document_structure import RetriFlowStructuredExtractionService

        xhtml = """
        <html xmlns="http://www.w3.org/1999/xhtml">
          <body>
            <div class="page">
              <h1>RetriFlow Overview</h1>
              <p>RetriFlow ingests knowledge documents.</p>
              <table>
                <thead>
                  <tr><th>Metric</th><th>Value</th></tr>
                </thead>
                <tbody>
                  <tr><td>Latency</td><td>20%</td></tr>
                </tbody>
              </table>
              <p>图1 系统架构图</p>
            </div>
          </body>
        </html>
        """

        document = RetriFlowStructuredExtractionService().extract_from_xhtml(
            file_name="retriflow-spec.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            metadata={"dc:title": "RetriFlow Spec"},
            xhtml_content=xhtml,
            text_content="RetriFlow Overview RetriFlow ingests knowledge documents.",
        )

        self.assertEqual(document.file_name, "retriflow-spec.docx")
        self.assertEqual(document.title, "RetriFlow Spec")
        self.assertEqual(document.blocks[0].block_type, "heading")
        self.assertEqual(document.blocks[0].level, 1)
        self.assertEqual(document.blocks[0].text, "RetriFlow Overview")
        self.assertEqual(document.blocks[0].page_number, 1)

        self.assertEqual(document.blocks[1].block_type, "paragraph")
        self.assertEqual(document.blocks[1].text, "RetriFlow ingests knowledge documents.")
        self.assertEqual(document.blocks[1].heading_path, ["RetriFlow Overview"])

        table_block = next(block for block in document.blocks if block.block_type == "table")
        self.assertEqual(table_block.headers, ["Metric", "Value"])
        self.assertEqual(table_block.row_count, 1)
        self.assertEqual(table_block.column_count, 2)
        self.assertEqual(table_block.rows[0].cells[0].text, "Latency")
        self.assertEqual(table_block.rows[0].cells[0].row_index, 0)
        self.assertEqual(table_block.rows[0].cells[1].column_index, 1)
        self.assertEqual(table_block.page_number, 1)

        caption_block = next(block for block in document.blocks if block.block_type == "image_caption")
        self.assertEqual(caption_block.text, "图1 系统架构图")
        self.assertEqual(caption_block.page_number, 1)

    def test_extracts_multiple_pages_from_page_wrappers(self) -> None:
        from domain.document_structure import RetriFlowStructuredExtractionService

        xhtml = """
        <html xmlns="http://www.w3.org/1999/xhtml">
          <body>
            <div class="page"><p>Page one paragraph.</p></div>
            <div class="page"><p>Page two paragraph.</p></div>
          </body>
        </html>
        """

        document = RetriFlowStructuredExtractionService().extract_from_xhtml(
            file_name="pages.pdf",
            content_type="application/pdf",
            metadata={},
            xhtml_content=xhtml,
            text_content="Page one paragraph. Page two paragraph.",
        )

        paragraphs = [block for block in document.blocks if block.block_type == "paragraph"]
        self.assertEqual([block.page_number for block in paragraphs], [1, 2])

    def test_infers_table_headers_from_first_row_when_thead_is_missing(self) -> None:
        from domain.document_structure import RetriFlowStructuredExtractionService

        xhtml = """
        <html xmlns="http://www.w3.org/1999/xhtml">
          <body>
            <div class="page">
              <table>
                <tbody>
                  <tr><td>Metric</td><td>Value</td></tr>
                  <tr><td>Latency</td><td>20%</td></tr>
                </tbody>
              </table>
            </div>
          </body>
        </html>
        """

        document = RetriFlowStructuredExtractionService().extract_from_xhtml(
            file_name="tbody-only.xlsx",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            metadata={},
            xhtml_content=xhtml,
            text_content="Metric Value Latency 20%",
        )

        table_block = next(block for block in document.blocks if block.block_type == "table")
        self.assertEqual(table_block.headers, ["Metric", "Value"])
        self.assertEqual(table_block.row_count, 1)
        self.assertEqual(table_block.rows[0].cells[0].text, "Latency")
        self.assertEqual(table_block.rows[0].cells[1].text, "20%")

    def test_repairs_mojibake_image_caption_prefix(self) -> None:
        from domain.document_structure import RetriFlowStructuredExtractionService

        xhtml = """
        <html xmlns="http://www.w3.org/1999/xhtml">
          <body>
            <div class="page">
              <p>ͼ1 RetriFlow document parsing overview</p>
            </div>
          </body>
        </html>
        """

        document = RetriFlowStructuredExtractionService().extract_from_xhtml(
            file_name="caption.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            metadata={},
            xhtml_content=xhtml,
            text_content="ͼ1 RetriFlow document parsing overview",
        )

        caption_block = next(block for block in document.blocks if block.block_type == "image_caption")
        self.assertEqual(caption_block.text, "图1 RetriFlow document parsing overview")

    def test_promotes_ocr_caption_when_existing_caption_is_missing(self) -> None:
        from domain.document_structure import RetriFlowStructuredExtractionService

        xhtml = """
        <html xmlns="http://www.w3.org/1999/xhtml">
          <body>
            <div class="page">
              <p>System diagram follows below.</p>
            </div>
          </body>
        </html>
        """

        document = RetriFlowStructuredExtractionService().extract_from_xhtml(
            file_name="ocr-caption.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            metadata={},
            xhtml_content=xhtml,
            text_content="System diagram follows below.",
            ocr_captions_by_page={1: ["图1 OCR extracted architecture overview"]},
        )

        caption_block = next(block for block in document.blocks if block.block_type == "image_caption")
        self.assertEqual(caption_block.text, "图1 OCR extracted architecture overview")
        self.assertEqual(caption_block.page_number, 1)

    def test_ignores_tika_unpack_artifact_headings_for_embedded_images(self) -> None:
        from domain.document_structure import RetriFlowStructuredExtractionService

        xhtml = """
        <html xmlns="http://www.w3.org/1999/xhtml">
          <body>
            <div class="page">
              <h1>image1.png</h1>
              <p>Figure 1 RetriFlow Parsing Workflow</p>
            </div>
          </body>
        </html>
        """

        document = RetriFlowStructuredExtractionService().extract_from_xhtml(
            file_name="artifact.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            metadata={},
            xhtml_content=xhtml,
            text_content="Figure 1 RetriFlow Parsing Workflow",
        )

        self.assertEqual([block.block_type for block in document.blocks], ["image_caption"])

    def test_repairs_greek_pi_style_mojibake_caption_prefix(self) -> None:
        from domain.document_structure import RetriFlowStructuredExtractionService

        repaired = RetriFlowStructuredExtractionService._repair_mojibake_caption_prefix(
            "ͼ1 RetriFlow document parsing overview"
        )

        self.assertEqual(repaired, "图1 RetriFlow document parsing overview")


if __name__ == "__main__":
    unittest.main()
