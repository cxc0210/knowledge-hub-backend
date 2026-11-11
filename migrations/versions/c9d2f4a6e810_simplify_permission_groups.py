"""simplify permission groups

Revision ID: c9d2f4a6e810
Revises: b7c4e9a1d203
Create Date: 2026-11-11 12:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql.selectable import TableClause


# revision identifiers, used by Alembic.
revision: str = "c9d2f4a6e810"
down_revision: Union[str, Sequence[str], None] = "b7c4e9a1d203"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _permission_table() -> TableClause:
    return sa.table(
        "kh_permission",
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.String()),
    )


def _clear_permissions() -> None:
    op.execute(sa.text("DELETE FROM kh_role_permission"))
    op.execute(sa.text("DELETE FROM kh_permission"))


def _assign_current_permissions() -> None:
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
            WHERE code = 'document:manage'
            """
        )
    )


def _assign_previous_permissions() -> None:
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


def upgrade() -> None:
    """Replace API-level permissions with business-level permissions."""
    _clear_permissions()
    op.bulk_insert(
        _permission_table(),
        [
            {
                "code": "document:manage",
                "name": "文档管理",
                "description": "创建、查看、修改、删除文档并提交审批",
            },
            {
                "code": "document:review",
                "name": "文档审核发布",
                "description": "审批并发布文档",
            },
            {
                "code": "user:manage",
                "name": "用户管理",
                "description": "查看、修改、禁用用户及分配角色",
            },
            {
                "code": "rbac:manage",
                "name": "角色权限管理",
                "description": "管理角色及角色拥有的权限",
            },
        ],
    )
    _assign_current_permissions()


def downgrade() -> None:
    """Restore the previous API-level permissions."""
    _clear_permissions()
    op.bulk_insert(
        _permission_table(),
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
    _assign_previous_permissions()
