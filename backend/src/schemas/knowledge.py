from typing import Any

import re

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


COLLECTION_NAME_PATTERN = re.compile(r"^[a-z0-9]+$")


class KnowledgeBaseCreateRequest(BaseModel):
    name: str
    embedding_model: str = "Qwen/Qwen3-Embedding-8B"
    collection_name: str = ""

    @model_validator(mode="after")
    def validate_knowledge_base(self) -> "KnowledgeBaseCreateRequest":
        if not self.name.strip():
            raise ValueError("name is required")
        if self.collection_name and not COLLECTION_NAME_PATTERN.fullmatch(self.collection_name):
            raise ValueError("collection_name can only contain lowercase letters and numbers")
        return self


class KnowledgeBaseUpdateRequest(BaseModel):
    name: str | None = None
    embedding_model: str | None = None
    collection_name: str | None = None

    @model_validator(mode="after")
    def validate_knowledge_base_update(self) -> "KnowledgeBaseUpdateRequest":
        if self.name is not None and not self.name.strip():
            raise ValueError("name is required")
        if self.collection_name is not None and not COLLECTION_NAME_PATTERN.fullmatch(self.collection_name):
            raise ValueError("collection_name can only contain lowercase letters and numbers")
        return self


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
    source_uri: str = ""
    processing_config: dict[str, Any] = Field(default_factory=dict)
    vector_indexed_at: str = ""
    created_at: str


class KnowledgeDocumentCreateRequest(BaseModel):
    title: str
    source_type: str = "manual"
    content: str
    document_type: str = "manual"
    process_mode: str = "chunk_strategy"
    pipeline_id: int | None = None
    chunk_strategy: str = "auto"
    chunk_size: int = 600
    chunk_overlap: int = 120
    recursive_separators: list[str] = Field(default_factory=list)
    chunk_config: dict[str, Any] = Field(default_factory=dict)

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
    process_mode: str = "chunk_strategy"
    pipeline_id: int | None = None
    chunk_strategy: str = "auto"
    chunk_size: int = 600
    chunk_overlap: int = 120
    recursive_separators: list[str] = Field(default_factory=list)
    chunk_config: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_chunk_settings(self) -> "KnowledgeDocumentReindexRequest":
        if self.chunk_size < 1:
            raise ValueError("chunk_size must be positive")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


class KnowledgeDocumentUpdateRequest(BaseModel):
    title: str | None = None
    enabled: bool | None = None

    @model_validator(mode="after")
    def validate_document_update(self) -> "KnowledgeDocumentUpdateRequest":
        if self.title is not None and not self.title.strip():
            raise ValueError("title is required")
        return self


class KnowledgeDocumentListResponse(BaseModel):
    items: list[KnowledgeDocumentItem]


class KnowledgeDocumentPreviewResponse(BaseModel):
    id: int
    knowledge_base_id: str
    title: str
    source_type: str
    content: str
    source_uri: str = ""
    created_at: str


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
    enabled: bool | None = None
    content: str | None = None

    @model_validator(mode="after")
    def validate_chunk_update(self) -> "KnowledgeChunkUpdateRequest":
        if self.enabled is None and self.content is None:
            raise ValueError("enabled or content is required")
        if self.content is not None and not self.content.strip():
            raise ValueError("content is required")
        return self


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
    node_id: str = ""
    node_type: str
    node_order: int
    success: bool
    status: str = "success"
    message: str
    error_message: str = ""
    output: dict[str, Any] = Field(default_factory=dict)
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


class IngestionPipelineUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    nodes: list[IngestionPipelineNodeConfig] | None = None
    owner: str | None = None

    @model_validator(mode="after")
    def validate_pipeline(self) -> "IngestionPipelineUpdateRequest":
        if self.name is not None and not self.name.strip():
            raise ValueError("pipeline name is required")
        if self.nodes is not None:
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
