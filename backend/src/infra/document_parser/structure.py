import re
from xml.etree import ElementTree as ET

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


class RetriFlowStructuredExtractionService:
    IMAGE_RESOURCE_NAME_PATTERN = re.compile(r"^image\d+\.(png|jpe?g|gif|bmp|webp|tiff?)$", re.IGNORECASE)

    def extract_from_xhtml(
        self,
        file_name: str,
        content_type: str,
        metadata: dict,
        xhtml_content: str,
        text_content: str,
        ocr_captions_by_page: dict[int, list[str]] | None = None,
    ) -> StructuredDocument:
        title = str(metadata.get("dc:title") or metadata.get("title") or "").strip() or None
        root = ET.fromstring(xhtml_content)
        blocks: list = []
        block_index = 0
        normalized_ocr_captions = ocr_captions_by_page or {}

        body = self._find_first(root, "body")
        if body is None:
            return StructuredDocument(
                file_name=file_name,
                content_type=content_type,
                title=title,
                metadata=metadata,
                blocks=[],
                text_content=text_content,
            )

        page_wrappers = [child for child in list(body) if self._is_page_wrapper(child)]
        page_nodes = page_wrappers if page_wrappers else [body]

        for page_number, page_node in enumerate(page_nodes, start=1):
            page_has_caption = False
            if page_number > 1:
                blocks.append(PageBreakBlock(block_index=block_index, page_number=page_number))
                block_index += 1

            for element in self._iter_content_elements(page_node):
                tag_name = self._local_name(element.tag)
                if tag_name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                    text = self._text_content(element)
                    if text and not self._looks_like_embedded_resource_name(text):
                        blocks.append(
                            HeadingBlock(
                                block_index=block_index,
                                page_number=page_number,
                                level=int(tag_name[1]),
                                text=text,
                            )
                        )
                        block_index += 1
                    continue

                if tag_name == "p":
                    text = self._repair_mojibake_caption_prefix(self._text_content(element))
                    if not text:
                        continue
                    if self._looks_like_image_caption(text):
                        blocks.append(
                            ImageCaptionBlock(
                                block_index=block_index,
                                page_number=page_number,
                                text=text,
                            )
                        )
                        page_has_caption = True
                    else:
                        blocks.append(
                            ParagraphBlock(
                                block_index=block_index,
                                page_number=page_number,
                                text=text,
                            )
                        )
                    block_index += 1
                    continue

                if tag_name == "table":
                    blocks.append(self._build_table_block(element, block_index, page_number))
                    block_index += 1

            if not page_has_caption:
                for caption in normalized_ocr_captions.get(page_number, []):
                    repaired_caption = self._repair_mojibake_caption_prefix(caption)
                    if not repaired_caption or not self._looks_like_image_caption(repaired_caption):
                        continue
                    blocks.append(
                        ImageCaptionBlock(
                            block_index=block_index,
                            page_number=page_number,
                            text=repaired_caption,
                        )
                    )
                    block_index += 1
                    break

        self._apply_heading_paths(blocks)

        return StructuredDocument(
            file_name=file_name,
            content_type=content_type,
            title=title,
            metadata=metadata,
            blocks=blocks,
            text_content=text_content,
        )

    def _build_table_block(self, element: ET.Element, block_index: int, page_number: int) -> TableBlock:
        headers: list[str] = []
        rows: list[TableRow] = []
        inferred_header_from_first_row = False

        header_row = self._find_first(element, "thead")
        if header_row is not None:
            first_row = self._find_first(header_row, "tr")
            if first_row is not None:
                headers = [self._text_content(cell) for cell in self._find_children(first_row, {"th", "td"})]

        body_rows_parent = self._find_first(element, "tbody")
        row_parent = body_rows_parent if body_rows_parent is not None else element
        row_elements = self._find_children(row_parent, {"tr"})

        if not headers and row_elements:
            headers = [self._text_content(cell) for cell in self._find_children(row_elements[0], {"th", "td"})]
            inferred_header_from_first_row = any(headers)

        for row_index, row_element in enumerate(row_elements):
            if headers and row_index == 0 and self._is_header_row(row_element):
                continue
            if inferred_header_from_first_row and row_index == 0:
                continue
            cells: list[TableCell] = []
            for column_index, cell_element in enumerate(self._find_children(row_element, {"th", "td"})):
                cells.append(
                    TableCell(
                        row_index=row_index - 1 if inferred_header_from_first_row else row_index,
                        column_index=column_index,
                        text=self._text_content(cell_element),
                        is_header=self._local_name(cell_element.tag) == "th",
                    )
                )
            if cells:
                normalized_row_index = row_index - 1 if inferred_header_from_first_row else row_index
                rows.append(TableRow(row_index=normalized_row_index, cells=cells))

        column_count = max(
            len(headers),
            max((len(row.cells) for row in rows), default=0),
        )

        return TableBlock(
            block_index=block_index,
            page_number=page_number,
            headers=headers,
            rows=rows,
            row_count=len(rows),
            column_count=column_count,
        )

    @staticmethod
    def _is_header_row(row_element: ET.Element) -> bool:
        return all(RetriFlowStructuredExtractionService._local_name(cell.tag) == "th" for cell in list(row_element))

    @staticmethod
    def _apply_heading_paths(blocks: list) -> None:
        heading_stack: list[tuple[int, str]] = []
        for block in blocks:
            if isinstance(block, HeadingBlock):
                while heading_stack and heading_stack[-1][0] >= block.level:
                    heading_stack.pop()
                heading_stack.append((block.level, block.text))
                block.heading_path = [item[1] for item in heading_stack[:-1]]
                continue

            if isinstance(block, (ParagraphBlock, TableBlock, ImageCaptionBlock)):
                block.heading_path = [item[1] for item in heading_stack]

    @staticmethod
    def _is_page_wrapper(element: ET.Element) -> bool:
        class_name = (element.attrib.get("class") or "").lower()
        return RetriFlowStructuredExtractionService._local_name(element.tag) == "div" and "page" in class_name

    @staticmethod
    def _looks_like_image_caption(text: str) -> bool:
        lowered = text.strip().lower()
        return (
            lowered.startswith("图")
            or lowered.startswith("表")
            or lowered.startswith("figure")
            or lowered.startswith("fig.")
            or lowered.startswith("image")
        )

    @classmethod
    def _looks_like_embedded_resource_name(cls, text: str) -> bool:
        return bool(cls.IMAGE_RESOURCE_NAME_PATTERN.match(text.strip()))

    @staticmethod
    def _repair_mojibake_caption_prefix(text: str) -> str:
        repaired = (text or "").strip()
        replacements = {
            "\u037c": "图",
            "\u934f": "图",
            "\u741b": "表",
        }
        for source, target in replacements.items():
            if repaired.startswith(source):
                repaired = target + repaired[len(source) :]
        return repaired

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.split("}", 1)[-1]

    @staticmethod
    def _text_content(element: ET.Element) -> str:
        return " ".join(part.strip() for part in element.itertext() if part and part.strip()).strip()

    def _find_first(self, element: ET.Element, tag_name: str) -> ET.Element | None:
        for child in element.iter():
            if self._local_name(child.tag) == tag_name:
                return child
        return None

    def _find_children(self, element: ET.Element | None, tag_names: set[str]) -> list[ET.Element]:
        if element is None:
            return []
        return [child for child in list(element) if self._local_name(child.tag) in tag_names]

    def _iter_content_elements(self, element: ET.Element):
        for child in list(element):
            tag_name = self._local_name(child.tag)
            if tag_name in {"h1", "h2", "h3", "h4", "h5", "h6", "p", "table"}:
                yield child
                continue
            yield from self._iter_content_elements(child)
