"""add AI conversations and messages

Revision ID: f6a1c2d3e4b5
Revises: d41f8e7c9a20
Create Date: 2026-11-17 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f6a1c2d3e4b5"
down_revision: str | Sequence[str] | None = "d41f8e7c9a20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "kh_ai_conversation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "title",
            sa.String(length=200),
            server_default=sa.text("'新对话'"),
            nullable=False,
        ),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "deleted",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["kh_user.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_kh_ai_conversation_user_active_recent",
        "kh_ai_conversation",
        ["user_id", "last_message_at", "created_at"],
        unique=False,
        postgresql_where=sa.text("deleted = false"),
    )

    op.create_table(
        "kh_ai_message",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_kh_ai_message_role",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["kh_ai_conversation.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_kh_ai_message_conversation_created",
        "kh_ai_message",
        ["conversation_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_kh_ai_message_conversation_request",
        "kh_ai_message",
        ["conversation_id", "request_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_kh_ai_message_conversation_request",
        table_name="kh_ai_message",
    )
    op.drop_index(
        "ix_kh_ai_message_conversation_created",
        table_name="kh_ai_message",
    )
    op.drop_table("kh_ai_message")
    op.drop_index(
        "ix_kh_ai_conversation_user_active_recent",
        table_name="kh_ai_conversation",
    )
    op.drop_table("kh_ai_conversation")
