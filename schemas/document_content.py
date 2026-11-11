from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentContentCreate(BaseModel):
    content: str = Field(min_length=1)

    model_config = ConfigDict(str_strip_whitespace=True)


class DocumentContentResponse(BaseModel):
    content_id: str
    content: str
    created_at: datetime
    updated_at: datetime
