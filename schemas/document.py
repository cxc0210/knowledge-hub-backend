from datetime import datetime
from pathlib import PurePath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DocumentUploadCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    file_name: str = Field(min_length=1, max_length=512)
    content_type: str = Field(min_length=1, max_length=255)
    file_size: int = Field(gt=0, le=5 * 1024 * 1024 * 1024)
    summary: str | None = None
    category_id: int | None = None
    team_id: int | None = None
    cover_image: str | None = None
    tags: str | None = None
    remark: str | None = None

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    @field_validator("file_name")
    @classmethod
    def normalize_file_name(cls, value: str) -> str:
        file_name = PurePath(value.replace("\\", "/")).name
        if not file_name or file_name in {".", ".."}:
            raise ValueError("file_name must contain a valid file name")
        return file_name


class DocumentResponse(BaseModel):
    id: int
    title: str
    content_id: str | None
    object_key: str
    file_name: str
    content_type: str
    file_size: int
    etag: str | None
    summary: str | None
    category_id: int | None
    team_id: int | None
    author_id: int | None
    cover_image: str | None
    tags: str | None
    status: int
    remark: str | None
    view_count: int
    like_count: int
    comment_count: int
    favourite_count: int
    word_count: int
    publish_time: datetime | None
    is_public: bool
    created_at: datetime
    updated_at: datetime
    create_by: int | None
    update_by: int | None
    deleted: bool

    model_config = ConfigDict(from_attributes=True)


class DocumentUploadResponse(BaseModel):
    document: DocumentResponse
    upload_url: str
    method: Literal["PUT"] = "PUT"
    headers: dict[str, str]
    expires_in: int


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    page: int
    size: int
    total: int
    pages: int


class DocumentAuthorResponse(BaseModel):
    id: int
    username: str
    avatar_url: str | None

    model_config = ConfigDict(from_attributes=True)


class DocumentDetailResponse(BaseModel):
    document: DocumentResponse
    author: DocumentAuthorResponse
    markdown: str
