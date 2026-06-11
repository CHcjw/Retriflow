from pydantic import BaseModel


class SessionItem(BaseModel):
    id: str
    title: str
    message_count: int
    owner_id: str = ""


class SessionCreateRequest(BaseModel):
    title: str
    owner_id: str = ""


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
