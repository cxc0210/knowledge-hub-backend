from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

Prompt = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=20_000),
]


class AIChatRequest(BaseModel):
    prompt: Prompt

    model_config = ConfigDict(extra="forbid")


class AIChatResponse(BaseModel):
    answer: str
