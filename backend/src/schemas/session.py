from pydantic import BaseModel


class SessionItem(BaseModel):
    id: str
    title: str
    message_count: int


class SessionCreateRequest(BaseModel):
    title: str


class SessionListResponse(BaseModel):
    items: list[SessionItem]


class ConversationMessageItem(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    created_at: str


class ConversationMessageListResponse(BaseModel):
    items: list[ConversationMessageItem]
