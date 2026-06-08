from pydantic import BaseModel


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


class ChatWorkflowMetadata(BaseModel):
    name: str
    adapter: str
    retrieval_channels: list[str]
    retrieval_count: int


class ChatMessageWithSourcesResponse(BaseModel):
    session_id: str
    assistant_message: str
    sources: list[ChatSourceItem]
    workflow: ChatWorkflowMetadata
