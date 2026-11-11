"""create rbac

Revision ID: b7c4e9a1d203
Revises: 4f0e41e1c973
Create Date: 2026-11-11 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7c4e9a1d203"
down_revision: Union[str, Sequence[str], None] = "4f0e41e1c973"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create RBAC tables and assign the default user role."""
    op.create_table(
        "kh_role",
        sa.Column("id", sa.SmallInteger(), autoincrement=False, nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_kh_role_code"),
    )
    op.create_table(
        "kh_permission",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False, start=1001),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_kh_permission_code"),
    )
    op.create_table(
        "kh_role_permission",
        sa.Column("role_id", sa.SmallInteger(), nullable=False),
        sa.Column("permission_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["kh_permission.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["kh_role.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
    )

    role_table = sa.table(
        "kh_role",
        sa.column("id", sa.SmallInteger()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.String()),
    )
    op.bulk_insert(
        role_table,
        [
            {
                "id": 1,
                "code": "admin",
                "name": "管理员",
                "description": "拥有系统全部管理权限",
            },
            {
                "id": 2,
                "code": "user",
                "name": "普通用户",
                "description": "拥有普通文档操作权限",
            },
        ],
    )

    permission_table = sa.table(
        "kh_permission",
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.String()),
    )
    op.bulk_insert(
        permission_table,
        [
            {
                "code": "document:create",
                "name": "创建文档",
                "description": "创建新的文档记录",
            },
            {
                "code": "document:read",
                "name": "查看文档",
                "description": "查看有权访问的文档",
            },
            {
                "code": "document:update:own",
                "name": "修改自己的文档",
                "description": "修改本人创建的文档",
            },
            {
                "code": "document:delete:own",
                "name": "删除自己的文档",
                "description": "删除本人创建的文档",
            },
            {
                "code": "document:submit_review",
                "name": "提交文档审批",
                "description": "将文档提交至发布审批流程",
            },
            {
                "code": "document:approve",
                "name": "审批文档",
                "description": "通过或拒绝文档发布申请",
            },
            {
                "code": "document:publish",
                "name": "发布文档",
                "description": "发布审批通过的文档",
            },
            {
                "code": "user:read",
                "name": "查看用户",
                "description": "查看用户信息和用户列表",
            },
            {
                "code": "user:update",
                "name": "修改用户",
                "description": "修改用户资料和状态",
            },
            {
                "code": "user:disable",
                "name": "禁用用户",
                "description": "禁用或恢复用户账号",
            },
            {
                "code": "user:assign_role",
                "name": "分配角色",
                "description": "修改用户所属角色",
            },
            {
                "code": "rbac:manage",
                "name": "管理权限",
                "description": "管理角色及其权限",
            },
        ],
    )

    op.execute(
        sa.text(
            """
            INSERT INTO kh_role_permission (role_id, permission_id)
            SELECT 1, id FROM kh_permission
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO kh_role_permission (role_id, permission_id)
            SELECT 2, id
            FROM kh_permission
            WHERE code IN (
                'document:create',
                'document:read',
                'document:update:own',
                'document:delete:own',
                'document:submit_review'
            )
            """
        )
    )

    op.add_column(
        "kh_user",
        sa.Column(
            "role_id",
            sa.SmallInteger(),
            server_default=sa.text("2"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_kh_user_role_id_kh_role",
        "kh_user",
        "kh_role",
        ["role_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    """Remove RBAC tables and the user role reference."""
    op.drop_constraint(
        "fk_kh_user_role_id_kh_role",
        "kh_user",
        type_="foreignkey",
    )
    op.drop_column("kh_user", "role_id")
    op.drop_table("kh_role_permission")
    op.drop_table("kh_permission")
    op.drop_table("kh_role")
