from dataclasses import dataclass
from pathlib import Path

import httpx

from domain.document_caption_enrichment import RetriFlowImageCaptionEnrichmentService
from domain.document_normalizer import RetriFlowDocumentNormalizationService
from domain.document_structure import RetriFlowStructuredExtractionService
from domain.ingestion import IngestionPipelineNodeResult
from domain.tika_client import RetriFlowTikaClient
from schemas.document_structure import ParagraphBlock, StructuredDocument


@dataclass
class ParsedUploadDocumentResult:
    title: str
    structured_document: StructuredDocument
    ingestion_text: str
    node_results: list[IngestionPipelineNodeResult]


class RetriFlowDocumentParserService:
    def __init__(self) -> None:
        from core.config import get_settings

        self.settings = get_settings()
        self.tika_client = RetriFlowTikaClient()
        self.extraction_service = RetriFlowStructuredExtractionService()
        self.normalization_service = RetriFlowDocumentNormalizationService()
        self.caption_enrichment_service = RetriFlowImageCaptionEnrichmentService(
            ocr_enabled=self.settings.tika_ocr_enabled,
            ocr_service_endpoint=self.settings.tika_ocr_service_endpoint,
            request_timeout_seconds=self.settings.tika_ocr_request_timeout_seconds,
        )

    def parse_upload(self, filename: str, content_bytes: bytes, content_type: str | None) -> ParsedUploadDocumentResult:
        title = Path(filename).stem or "uploaded-document"
        effective_content_type = content_type or "application/octet-stream"
        tika_enabled = self.settings.tika_enabled
        if tika_enabled:
            try:
                effective_content_type = self.tika_client.detect_content_type(
                    filename=filename,
                    content_bytes=content_bytes,
                    fallback_content_type=effective_content_type,
                )
            except httpx.HTTPError:
                if self._supports_text_fallback(filename=filename, content_type=effective_content_type):
                    tika_enabled = False
                else:
                    raise

        try:
            if tika_enabled:
                raw_document = self.tika_client.parse_bytes(filename, content_bytes, effective_content_type)
                ocr_captions_by_page = self.caption_enrichment_service.extract_page_captions(
                    filename=filename,
                    content_bytes=content_bytes,
                    content_type=effective_content_type,
                )
                extracted_document = self.extraction_service.extract_from_xhtml(
                    file_name=raw_document.file_name,
                    content_type=raw_document.content_type,
                    metadata=raw_document.metadata,
                    xhtml_content=raw_document.xhtml_content,
                    text_content=raw_document.text_content,
                    ocr_captions_by_page=ocr_captions_by_page,
                )
                parse_message = "Parsed uploaded document through Apache Tika."
            else:
                extracted_document = self._build_text_fallback_document(filename, content_bytes, effective_content_type)
                parse_message = "Decoded UTF-8 text upload without Apache Tika."
        except UnicodeDecodeError as exc:
            raise ValueError("Only UTF-8 text uploads are supported when Tika parsing is disabled.") from exc
        except ValueError as exc:
            if tika_enabled and self._supports_text_fallback(filename=filename, content_type=effective_content_type):
                extracted_document = self._build_text_fallback_document(filename, content_bytes, effective_content_type)
                parse_message = "Apache Tika parse failed, so RetriFlow fell back to UTF-8 text decoding."
            else:
                raise
        except httpx.HTTPError as exc:
            if self._supports_text_fallback(filename=filename, content_type=effective_content_type):
                extracted_document = self._build_text_fallback_document(filename, content_bytes, effective_content_type)
                parse_message = "Apache Tika was unavailable, so RetriFlow fell back to UTF-8 text decoding."
            else:
                raise RuntimeError("Apache Tika request failed. Check the Tika server endpoint and runtime.") from exc

        normalized_document = self.normalization_service.normalize(extracted_document)
        ingestion_text = self._build_ingestion_text(normalized_document)

        node_results = [
            IngestionPipelineNodeResult("parse", 1, True, parse_message, 1),
            IngestionPipelineNodeResult("extract", 2, True, f"Extracted {len(extracted_document.blocks)} structured blocks.", 1),
            IngestionPipelineNodeResult("clean", 3, True, "Normalized structured content and field values.", 1),
            IngestionPipelineNodeResult("validate", 4, True, "Validated structured document schema.", 1),
        ]

        normalized_title = normalized_document.title or title
        return ParsedUploadDocumentResult(
            title=normalized_title,
            structured_document=normalized_document,
            ingestion_text=ingestion_text,
            node_results=node_results,
        )

    def _build_text_fallback_document(
        self,
        filename: str,
        content_bytes: bytes,
        content_type: str,
    ) -> StructuredDocument:
        decoded = content_bytes.decode("utf-8")
        paragraphs = [item.strip() for item in decoded.replace("\r\n", "\n").replace("\r", "\n").split("\n\n") if item.strip()]
        blocks = [
            ParagraphBlock(
                block_index=index,
                page_number=1,
                text=paragraph,
            )
            for index, paragraph in enumerate(paragraphs or [decoded.strip()])
        ]
        return StructuredDocument(
            file_name=filename,
            content_type=content_type,
            title=Path(filename).stem or "uploaded-document",
            metadata={},
            blocks=blocks,
            text_content=decoded,
        )

    @staticmethod
    def _supports_text_fallback(filename: str, content_type: str) -> bool:
        normalized_content_type = (content_type or "").lower()
        normalized_suffix = Path(filename).suffix.lower()
        return normalized_content_type.startswith("text/") or normalized_suffix in {".txt", ".md", ".markdown", ".csv", ".html", ".htm"}

    @staticmethod
    def _build_ingestion_text(document: StructuredDocument) -> str:
        segments: list[str] = []
        for block in document.blocks:
            if block.block_type == "heading":
                segments.append(f"{'#' * block.level} {block.text}".strip())
                continue
            if block.block_type == "paragraph":
                segments.append(block.text)
                continue
            if block.block_type == "image_caption":
                segments.append(f"Image caption: {block.text}")
                continue
            if block.block_type == "table":
                if block.headers:
                    segments.append("Table headers: " + " | ".join(block.headers))
                for row in block.rows:
                    values = []
                    for cell in row.cells:
                        header = block.headers[cell.column_index] if cell.column_index < len(block.headers) else f"column_{cell.column_index + 1}"
                        values.append(f"{header}={cell.text}")
                    segments.append(f"Row {row.row_index + 1}: " + " | ".join(values))
                continue
            if block.block_type == "page_break":
                segments.append(f"[Page {block.page_number}]")

        return "\n\n".join(segment for segment in segments if segment.strip()).strip()
