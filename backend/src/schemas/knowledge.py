from typing import Any

from pydantic import BaseModel, Field, model_validator


class KnowledgeBaseItem(BaseModel):
    id: str
    name: str
    product: str
    document_count: int
    embedding_model: str = "qwen-emb-8b"
    collection_name: str = ""
    owner: str = "admin"
    created_at: str = ""
    updated_at: str = ""


class KnowledgeBaseCreateRequest(BaseModel):
    name: str


class KnowledgeBaseListResponse(BaseModel):
    items: list[KnowledgeBaseItem]


class KnowledgeDocumentItem(BaseModel):
    id: int
    knowledge_base_id: str
    title: str
    source_type: str
    processing_mode: str = "auto"
    status: str
    enabled: bool = True
    vector_index_status: str = "pending"
    vector_chunk_count: int = 0
    document_type: str = "knowledge_base"
    size_label: str = "-"
    vector_indexed_at: str = ""
    created_at: str


class KnowledgeDocumentCreateRequest(BaseModel):
    title: str
    source_type: str = "manual"
    content: str
    document_type: str = "manual"
    chunk_strategy: str = "auto"
    chunk_size: int = 600
    chunk_overlap: int = 120
    recursive_separators: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_chunk_settings(self) -> "KnowledgeDocumentCreateRequest":
        if self.chunk_size < 1:
            raise ValueError("chunk_size must be positive")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


class KnowledgeDocumentReindexRequest(BaseModel):
    document_type: str | None = None
    chunk_strategy: str = "auto"
    chunk_size: int = 600
    chunk_overlap: int = 120
    recursive_separators: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_chunk_settings(self) -> "KnowledgeDocumentReindexRequest":
        if self.chunk_size < 1:
            raise ValueError("chunk_size must be positive")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


class KnowledgeDocumentListResponse(BaseModel):
    items: list[KnowledgeDocumentItem]


class KnowledgeSampleImportResponse(BaseModel):
    imported_count: int


class KnowledgeChunkItem(BaseModel):
    id: int
    knowledge_base_id: str
    document_id: int
    chunk_index: int
    content: str
    char_count: int
    enabled: bool = True
    strategy: str = "recursive"
    document_type: str = "manual"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class KnowledgeChunkListResponse(BaseModel):
    items: list[KnowledgeChunkItem]


class KnowledgeChunkUpdateRequest(BaseModel):
    enabled: bool


class KnowledgeChunkBatchUpdateRequest(BaseModel):
    chunk_ids: list[int] = Field(default_factory=list)
    enabled: bool


class KnowledgeChunkBatchUpdateResponse(BaseModel):
    updated_count: int


class StructuredTableCellItem(BaseModel):
    row_index: int
    column_index: int
    text: str
    is_header: bool


class StructuredTableRowItem(BaseModel):
    row_index: int
    cells: list[StructuredTableCellItem]


class KnowledgeDocumentStructuredBlockItem(BaseModel):
    id: int
    knowledge_base_id: str
    document_id: int
    block_index: int
    block_type: str
    page_number: int | None = None
    heading_path: list[str]
    level: int | None = None
    text: str | None = None
    headers: list[str]
    rows: list[StructuredTableRowItem]
    row_count: int | None = None
    column_count: int | None = None
    caption: str | None = None
    created_at: str


class KnowledgeDocumentStructuredBlockListResponse(BaseModel):
    items: list[KnowledgeDocumentStructuredBlockItem]


class IngestionTaskItem(BaseModel):
    id: int
    knowledge_base_id: str
    document_id: int
    source_type: str
    status: str
    chunk_count: int
    message: str
    created_at: str


class IngestionTaskListResponse(BaseModel):
    items: list[IngestionTaskItem]


class IngestionTaskNodeItem(BaseModel):
    id: int
    task_id: int
    node_type: str
    node_order: int
    success: bool
    message: str
    duration_ms: int
    created_at: str


class IngestionTaskNodeListResponse(BaseModel):
    items: list[IngestionTaskNodeItem]


class IngestionPipelineNodeConfig(BaseModel):
    node_id: str
    node_type: str = "fetcher"
    next_node_id: str = ""
    condition: str = ""
    config: dict[str, Any] = Field(default_factory=dict)


class IngestionPipelineItem(BaseModel):
    id: int
    name: str
    description: str
    nodes: list[IngestionPipelineNodeConfig]
    node_count: int
    owner: str
    created_at: str
    updated_at: str


class IngestionPipelineCreateRequest(BaseModel):
    name: str
    description: str = ""
    nodes: list[IngestionPipelineNodeConfig] = Field(default_factory=list)
    owner: str = "admin"

    @model_validator(mode="after")
    def validate_pipeline(self) -> "IngestionPipelineCreateRequest":
        if not self.name.strip():
            raise ValueError("pipeline name is required")
        node_ids = [node.node_id.strip() for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("node_id must be unique")
        return self


class IngestionPipelineListResponse(BaseModel):
    items: list[IngestionPipelineItem]


class KnowledgeBaseRouteProfileItem(BaseModel):
    knowledge_base_id: str
    profile_text: str
    sample_questions: list[str]
    keywords: list[str]
    updated_at: str


class KnowledgeBaseRouteProfileUpdateRequest(BaseModel):
    profile_text: str
    sample_questions: list[str]
    keywords: list[str]
