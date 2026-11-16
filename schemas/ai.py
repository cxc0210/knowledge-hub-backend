from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from schemas.rag import RAGSource

Prompt = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=20_000),
]


class AIChatRequest(BaseModel):
    prompt: Prompt
    request_id: UUID | None = None
    tts_enabled: bool = False

    model_config = ConfigDict(extra="forbid")


class AIChatResponse(BaseModel):
    answer: str
    sources: list[RAGSource] = Field(default_factory=list)
