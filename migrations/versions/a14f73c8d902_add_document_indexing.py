"""add document indexing tables

Revision ID: a14f73c8d902
Revises: e3b7d9a4f201
Create Date: 2026-11-12 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR

revision: str = "a14f73c8d902"
down_revision: str | Sequence[str] | None = "e3b7d9a4f201"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "kh_document_index_job",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False, start=100001),
            nullable=False,
        ),
        sa.Column("document_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.SmallInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "retry_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["kh_document.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_kh_document_index_job_status_created",
        "kh_document_index_job",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_kh_document_index_job_document_id",
        "kh_document_index_job",
        ["document_id"],
    )

    op.create_table(
        "kh_document_chunk",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False, start=100001),
            nullable=False,
        ),
        sa.Column("chunk_id", sa.String(length=100), nullable=False),
        sa.Column("document_id", sa.BigInteger(), nullable=False),
        sa.Column("document_version", sa.String(length=64), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("heading", sa.String(length=500), nullable=True),
        sa.Column("heading_path", sa.String(length=2000), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding_content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column("embedding", VECTOR(dim=1024), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["kh_document.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "chunk_id",
            name="uq_kh_document_chunk_chunk_id",
        ),
        sa.UniqueConstraint(
            "document_id",
            "document_version",
            "chunk_index",
            name="uq_kh_document_chunk_version_index",
        ),
    )
    op.create_index(
        "ix_kh_document_chunk_document_id",
        "kh_document_chunk",
        ["document_id"],
    )
    op.create_index(
        "ix_kh_document_chunk_embedding_hnsw",
        "kh_document_chunk",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index(
        "ix_kh_document_chunk_embedding_hnsw",
        table_name="kh_document_chunk",
    )
    op.drop_index(
        "ix_kh_document_chunk_document_id",
        table_name="kh_document_chunk",
    )
    op.drop_table("kh_document_chunk")
    op.drop_index(
        "ix_kh_document_index_job_document_id",
        table_name="kh_document_index_job",
    )
    op.drop_index(
        "ix_kh_document_index_job_status_created",
        table_name="kh_document_index_job",
    )
    op.drop_table("kh_document_index_job")
