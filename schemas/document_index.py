from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from schemas.document import DocumentResponse


@dataclass(frozen=True, slots=True)
class DocumentChunkData:
    chunk_id: str
    document_id: int
    document_version: str
    chunk_index: int
    heading: str | None
    heading_path: str | None
    content: str
    embedding_content: str
    content_hash: str
    char_count: int


class DocumentIndexJobResponse(BaseModel):
    id: int
    document_id: int
    status: int
    retry_count: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class DocumentPublishResponse(BaseModel):
    document: DocumentResponse
    index_job: DocumentIndexJobResponse
