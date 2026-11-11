from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1)
    content_id: str = Field(min_length=1)
    summary: str | None = None
    category_id: int | None = None
    team_id: int | None = None
    author_id: int | None = None
    cover_image: str | None = None
    tags: str | None = None
    status: int = 0
    remark: str | None = None
    word_count: int = Field(default=0, ge=0)
    publish_time: datetime | None = None
    is_public: bool = False
    create_by: int | None = None

    model_config = ConfigDict(str_strip_whitespace=True)


class DocumentResponse(BaseModel):
    id: int
    title: str
    content_id: str
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
