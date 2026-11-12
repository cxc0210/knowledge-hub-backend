"""add document upload metadata

Revision ID: e3b7d9a4f201
Revises: c9d2f4a6e810
Create Date: 2026-11-11 20:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e3b7d9a4f201"
down_revision: Union[str, Sequence[str], None] = "c9d2f4a6e810"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "kh_document",
        "content_id",
        existing_type=sa.String(),
        nullable=True,
    )
    op.add_column(
        "kh_document",
        sa.Column("object_key", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "kh_document",
        sa.Column("file_name", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "kh_document",
        sa.Column("content_type", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "kh_document",
        sa.Column("file_size", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "kh_document",
        sa.Column("etag", sa.String(length=255), nullable=True),
    )

    op.execute(
        sa.text(
            """
            UPDATE kh_document
            SET object_key = 'legacy/' || id,
                file_name = title,
                content_type = 'application/octet-stream',
                file_size = 0
            """
        )
    )

    op.alter_column("kh_document", "object_key", nullable=False)
    op.alter_column("kh_document", "file_name", nullable=False)
    op.alter_column("kh_document", "content_type", nullable=False)
    op.alter_column("kh_document", "file_size", nullable=False)
    op.create_unique_constraint(
        "uq_kh_document_object_key",
        "kh_document",
        ["object_key"],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE kh_document
            SET content_id = object_key
            WHERE content_id IS NULL
            """
        )
    )
    op.drop_constraint(
        "uq_kh_document_object_key",
        "kh_document",
        type_="unique",
    )
    op.drop_column("kh_document", "etag")
    op.drop_column("kh_document", "file_size")
    op.drop_column("kh_document", "content_type")
    op.drop_column("kh_document", "file_name")
    op.drop_column("kh_document", "object_key")
    op.alter_column(
        "kh_document",
        "content_id",
        existing_type=sa.String(),
        nullable=False,
    )
