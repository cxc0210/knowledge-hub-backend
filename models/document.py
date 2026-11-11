from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Identity,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Document(Base):
    __tablename__ = "kh_document"
    __table_args__ = (
        UniqueConstraint("content_id", name="uq_kh_document_content_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(start=100001),
        primary_key=True,
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    content_id: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str | None] = mapped_column(String, nullable=True)
    category_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    team_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    author_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cover_image: Mapped[str | None] = mapped_column(String, nullable=True)
    tags: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        server_default=text("0"),
    )
    remark: Mapped[str | None] = mapped_column(String, nullable=True)
    view_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    like_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    comment_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    favourite_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    word_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    publish_time: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    create_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    update_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
