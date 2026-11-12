from datetime import datetime

from pydantic import BaseModel


class DocumentSearchItem(BaseModel):
    document_id: int
    title: str
    highlighted_title: str | None
    heading: str | None
    snippets: list[str]
    score: float | None
    publish_time: datetime | None


class DocumentSearchResponse(BaseModel):
    query: str
    items: list[DocumentSearchItem]
    page: int
    size: int
    total: int
    pages: int
    took_ms: int
