from pydantic import BaseModel, Field


class ChatBootstrapResponse(BaseModel):
    product: str
    capabilities: list[str]


class ChatMessageRequest(BaseModel):
    session_id: str
    message: str


class ChatMessageResponse(BaseModel):
    session_id: str
    assistant_message: str


class ChatSourceItem(BaseModel):
    chunk_id: int
    knowledge_base_id: str
    document_id: int
    document_title: str
    content: str
    score: float
    source_link: str = ""
    source_updated_at: str = ""


class ChatMcpCallItem(BaseModel):
    tool_id: str
    arguments: dict[str, object] = Field(default_factory=dict)
    content: str
    is_error: bool = False


class ChatWorkflowMetadata(BaseModel):
    name: str
    adapter: str
    intent: str = "knowledge_retrieval"
    intent_confidence: float = 0.0
    intent_reason: str = ""
    intent_source: str = "fallback"
    retrieval_channels: list[str]
    retrieval_count: int
    retrieval_stage_counts: dict[str, int] = Field(default_factory=dict)
    rewritten_queries: list[str] = Field(default_factory=list)
    rewrite_query_count: int = 0
    route_mode: str = "global"
    mcp_tool_count: int = 0


class ChatMessageWithSourcesResponse(BaseModel):
    session_id: str
    assistant_message: str
    sources: list[ChatSourceItem]
    workflow: ChatWorkflowMetadata
    mcp_calls: list[ChatMcpCallItem] = Field(default_factory=list)
