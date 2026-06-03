from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Citation(BaseModel):
    source_file: str | None = None
    heading: str | None = None
    chunk_index: int | None = None
    text: str
    score: float | None = None
    kind: str = "document"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    session_id: UUID | None = None
    user_id: UUID | None = None
    language: str | None = Field(default=None, pattern="^(auto|zh|en)$")


class ChatResponse(BaseModel):
    session_id: UUID
    message_id: UUID
    answer: str
    language: str
    citations: list[Citation] = []


class ChatMessageRead(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    language: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSessionRead(BaseModel):
    id: UUID
    user_id: UUID | None
    title: str
    language: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

