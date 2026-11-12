from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.security import hash_password, verify_password
from enums.user import UserStatus
from models.role import Role
from models.user import User
from schemas.auth import LoginRequest

_DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-timing-protection")


class InvalidCredentialsError(Exception):
    pass


class UserDisabledError(Exception):
    pass


class AuthService:
    @staticmethod
    async def authenticate(
        session: AsyncSession,
        login_request: LoginRequest,
    ) -> User:
        identifier = login_request.username_or_email.strip().lower()
        user = await session.scalar(
            select(User)
            .options(
                selectinload(User.role).selectinload(Role.permissions),
            )
            .where(
                User.deleted.is_(False),
                or_(
                    func.lower(User.username) == identifier,
                    func.lower(User.email) == identifier,
                ),
            ),
        )

        password = login_request.password.get_secret_value()
        stored_password_hash = user.password_hash if user else _DUMMY_PASSWORD_HASH
        password_matches = verify_password(password, stored_password_hash)

        if user is None or not password_matches:
            raise InvalidCredentialsError("invalid username, email, or password")

        if user.status == UserStatus.DISABLED:
            raise UserDisabledError("user account is disabled")

        user.last_login_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(user, attribute_names=["updated_at"])
        return user
