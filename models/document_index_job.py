from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    SmallInteger,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from enums.document_index import DocumentIndexJobStatus


class DocumentIndexJob(Base):
    __tablename__ = "kh_document_index_job"
    __table_args__ = (
        Index(
            "ix_kh_document_index_job_status_created",
            "status",
            "created_at",
        ),
        Index("ix_kh_document_index_job_document_id", "document_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(start=100001),
        primary_key=True,
    )
    document_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("kh_document.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=DocumentIndexJobStatus.PENDING,
        server_default=text(str(DocumentIndexJobStatus.PENDING.value)),
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
