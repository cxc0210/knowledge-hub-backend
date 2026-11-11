from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyCookie
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from config import settings
from database import DatabaseSession
from enums.user import UserStatus
from models.role import Role
from models.user import User
from security import InvalidAccessTokenError, decode_access_token


access_token_cookie = APIKeyCookie(
    name=settings.auth_cookie_name,
    auto_error=False,
)


def _unauthorized(detail: str = "not authenticated") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
    )


async def get_current_user(
    token: Annotated[str | None, Security(access_token_cookie)],
    session: DatabaseSession,
) -> User:
    if token is None:
        raise _unauthorized()

    try:
        user_id, token_version = decode_access_token(token)
    except InvalidAccessTokenError as error:
        raise _unauthorized("access token is invalid or expired") from error

    user = await session.scalar(
        select(User)
        .options(
            selectinload(User.role).selectinload(Role.permissions),
        )
        .where(
            User.id == user_id,
            User.deleted.is_(False),
        ),
    )
    if user is None or user.token_version != token_version:
        raise _unauthorized("access token is no longer valid")

    if user.status == UserStatus.DISABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user account is disabled",
        )

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
