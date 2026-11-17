from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from enums.ai import AIMessageRole
from models.ai_message import AIMessage


class AIConversationCreate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class AIConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class AIConversationResponse(BaseModel):
    id: UUID
    user_id: int
    title: str
    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AIConversationListResponse(BaseModel):
    items: list[AIConversationResponse]
    page: int = Field(ge=1)
    size: int = Field(ge=1)
    total: int = Field(ge=0)
    pages: int = Field(ge=0)


class AIMessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    request_id: UUID
    role: AIMessageRole
    content: str
    metadata: dict[str, Any]
    created_at: datetime

    @classmethod
    def from_message(cls, message: AIMessage) -> AIMessageResponse:
        return cls(
            id=message.id,
            conversation_id=message.conversation_id,
            request_id=message.request_id,
            role=AIMessageRole(message.role),
            content=message.content,
            metadata=message.message_metadata,
            created_at=message.created_at,
        )


class AIMessageListResponse(BaseModel):
    items: list[AIMessageResponse]
    page: int = Field(ge=1)
    size: int = Field(ge=1)
    total: int = Field(ge=0)
    pages: int = Field(ge=0)
