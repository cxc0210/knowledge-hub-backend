"""add AI email actions

Revision ID: d41f8e7c9a20
Revises: a14f73c8d902
Create Date: 2026-11-15 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d41f8e7c9a20"
down_revision: str | Sequence[str] | None = "a14f73c8d902"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "kh_ai_action",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column(
            "status",
            sa.SmallInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("tool_call_id", sa.String(length=255), nullable=True),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["kh_user.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_kh_ai_action_idempotency_key",
        ),
    )
    op.create_index(
        "ix_kh_ai_action_expires_at",
        "kh_ai_action",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_kh_ai_action_user_status_created",
        "kh_ai_action",
        ["user_id", "status", "created_at"],
        unique=False,
    )

    op.execute(
        sa.text(
            """
            INSERT INTO kh_permission (code, name, description)
            VALUES (
                'ai:email:send',
                'AI 邮件发送',
                '通过 AI 创建并确认发送邮件'
            )
            ON CONFLICT (code) DO NOTHING
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO kh_role_permission (role_id, permission_id)
            SELECT role_id, permission.id
            FROM (VALUES (1), (2)) AS roles(role_id)
            CROSS JOIN kh_permission AS permission
            WHERE permission.code = 'ai:email:send'
            ON CONFLICT DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM kh_role_permission
            WHERE permission_id IN (
                SELECT id FROM kh_permission WHERE code = 'ai:email:send'
            )
            """
        )
    )
    op.execute(
        sa.text("DELETE FROM kh_permission WHERE code = 'ai:email:send'")
    )
    op.drop_index(
        "ix_kh_ai_action_user_status_created",
        table_name="kh_ai_action",
    )
    op.drop_index("ix_kh_ai_action_expires_at", table_name="kh_ai_action")
    op.drop_table("kh_ai_action")
