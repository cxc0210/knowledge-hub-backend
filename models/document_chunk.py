from datetime import datetime

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class DocumentChunk(Base):
    __tablename__ = "kh_document_chunk"
    __table_args__ = (
        UniqueConstraint("chunk_id", name="uq_kh_document_chunk_chunk_id"),
        UniqueConstraint(
            "document_id",
            "document_version",
            "chunk_index",
            name="uq_kh_document_chunk_version_index",
        ),
        Index("ix_kh_document_chunk_document_id", "document_id"),
        Index(
            "ix_kh_document_chunk_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(start=100001),
        primary_key=True,
    )
    chunk_id: Mapped[str] = mapped_column(String(100), nullable=False)
    document_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("kh_document.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_version: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    heading: Mapped[str | None] = mapped_column(String(500), nullable=True)
    heading_path: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(
        VECTOR(1024),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
