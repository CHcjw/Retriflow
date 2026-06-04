import re
import unicodedata

from pydantic import ValidationError

from schemas.document_structure import (
    HeadingBlock,
    ImageCaptionBlock,
    PageBreakBlock,
    ParagraphBlock,
    StructuredDocument,
    TableBlock,
    TableCell,
    TableRow,
)


class RetriFlowDocumentNormalizationService:
    EMPTY_MARKERS = {"n/a", "na", "null", "--", "-", "none"}

    def normalize(self, document: StructuredDocument) -> StructuredDocument:
        normalized_blocks = []
        for block in document.blocks:
            if isinstance(block, HeadingBlock):
                normalized_blocks.append(
                    HeadingBlock(
                        block_index=block.block_index,
                        page_number=block.page_number,
                        heading_path=[self._normalize_text(item) for item in block.heading_path if self._normalize_text(item)],
                        level=block.level,
                        text=self._normalize_text(block.text),
                    )
                )
                continue

            if isinstance(block, ParagraphBlock):
                normalized_blocks.append(
                    ParagraphBlock(
                        block_index=block.block_index,
                        page_number=block.page_number,
                        heading_path=[self._normalize_text(item) for item in block.heading_path if self._normalize_text(item)],
                        text=self._normalize_text(block.text),
                    )
                )
                continue

            if isinstance(block, ImageCaptionBlock):
                normalized_blocks.append(
                    ImageCaptionBlock(
                        block_index=block.block_index,
                        page_number=block.page_number,
                        heading_path=[self._normalize_text(item) for item in block.heading_path if self._normalize_text(item)],
                        text=self._normalize_text(block.text),
                    )
                )
                continue

            if isinstance(block, TableBlock):
                headers = [self._normalize_text(header) for header in block.headers]
                rows: list[TableRow] = []
                for row in block.rows:
                    cells = [
                        TableCell(
                            row_index=cell.row_index,
                            column_index=cell.column_index,
                            text=self._normalize_cell_text(cell.text),
                            is_header=cell.is_header,
                        )
                        for cell in row.cells
                    ]
                    rows.append(TableRow(row_index=row.row_index, cells=cells))

                normalized_blocks.append(
                    TableBlock(
                        block_index=block.block_index,
                        page_number=block.page_number,
                        heading_path=[self._normalize_text(item) for item in block.heading_path if self._normalize_text(item)],
                        headers=headers,
                        rows=rows,
                        row_count=len(rows),
                        column_count=max(len(headers), max((len(row.cells) for row in rows), default=0)),
                        caption=self._normalize_optional_text(block.caption),
                    )
                )
                continue

            if isinstance(block, PageBreakBlock):
                normalized_blocks.append(
                    PageBreakBlock(
                        block_index=block.block_index,
                        page_number=block.page_number,
                        heading_path=[self._normalize_text(item) for item in block.heading_path if self._normalize_text(item)],
                    )
                )

        normalized_document = StructuredDocument(
            file_name=document.file_name,
            content_type=document.content_type,
            title=self._normalize_optional_text(document.title),
            metadata=document.metadata,
            blocks=normalized_blocks,
            text_content=self._normalize_text(document.text_content),
        )
        return self.validate_document(normalized_document)

    def validate_document(self, document: StructuredDocument) -> StructuredDocument:
        try:
            return StructuredDocument.model_validate(document.model_dump())
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

    def _normalize_optional_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = self._normalize_text(value)
        return normalized or None

    def _normalize_cell_text(self, value: str) -> str:
        normalized = self._normalize_text(value)
        if normalized.lower() in self.EMPTY_MARKERS:
            return ""
        return normalized

    @classmethod
    def _normalize_text(cls, value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value or "")
        normalized = cls._repair_common_mojibake(normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    @staticmethod
    def _repair_common_mojibake(value: str) -> str:
        repaired = value.replace("锛?", "%")
        prefix_replacements = {
            "\u037c": "图",
            "\u934f": "图",
            "\u741b": "表",
        }
        for source, target in prefix_replacements.items():
            if repaired.startswith(source):
                repaired = target + repaired[len(source) :]
        return repaired
