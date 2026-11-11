from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import HTTPException, status

from dependencies.auth import CurrentUser
from enums.permission import PermissionCode
from models.user import User


PermissionChecker = Callable[..., Coroutine[Any, Any, User]]


def require_permission(required_permission: PermissionCode) -> PermissionChecker:
    async def checker(current_user: CurrentUser) -> User:
        permission_codes = {
            permission.code for permission in current_user.role.permissions
        }
        if required_permission.value not in permission_codes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"missing permission: {required_permission.value}",
            )

        return current_user

    return checker
