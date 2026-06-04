from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, model_validator


class RawParsedDocument(BaseModel):
    file_name: str
    content_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    xhtml_content: str = ""
    text_content: str = ""


class StructuredBlockBase(BaseModel):
    block_type: str
    block_index: int
    page_number: int | None = None
    heading_path: list[str] = Field(default_factory=list)


class HeadingBlock(StructuredBlockBase):
    block_type: Literal["heading"] = "heading"
    level: int
    text: str

    @model_validator(mode="after")
    def validate_level(self) -> "HeadingBlock":
        if self.level < 1 or self.level > 6:
            raise ValueError("Heading level must be between 1 and 6.")
        return self


class ParagraphBlock(StructuredBlockBase):
    block_type: Literal["paragraph"] = "paragraph"
    text: str


class TableCell(BaseModel):
    row_index: int
    column_index: int
    text: str
    is_header: bool = False


class TableRow(BaseModel):
    row_index: int
    cells: list[TableCell]


class TableBlock(StructuredBlockBase):
    block_type: Literal["table"] = "table"
    headers: list[str] = Field(default_factory=list)
    rows: list[TableRow] = Field(default_factory=list)
    row_count: int
    column_count: int
    caption: str | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> "TableBlock":
        if self.row_count != len(self.rows):
            raise ValueError("Table row_count does not match row list length.")
        if self.column_count < 0:
            raise ValueError("Table column_count must be non-negative.")
        return self


class ImageCaptionBlock(StructuredBlockBase):
    block_type: Literal["image_caption"] = "image_caption"
    text: str


class PageBreakBlock(StructuredBlockBase):
    block_type: Literal["page_break"] = "page_break"


StructuredBlock = Annotated[
    HeadingBlock | ParagraphBlock | TableBlock | ImageCaptionBlock | PageBreakBlock,
    Field(discriminator="block_type"),
]


class StructuredDocument(BaseModel):
    file_name: str
    content_type: str
    title: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    blocks: list[StructuredBlock] = Field(default_factory=list)
    text_content: str = ""
