from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.user import User
from schemas.user import UserCreate
from security import hash_password


class UserAlreadyExistsError(Exception):
    pass


class UserService:
    @staticmethod
    async def create(session: AsyncSession, user_create: UserCreate) -> User:
        user = User(
            username=user_create.username,
            email=str(user_create.email).lower(),
            password_hash=hash_password(user_create.password.get_secret_value()),
        )
        session.add(user)

        try:
            await session.commit()
        except IntegrityError as error:
            await session.rollback()

            constraint_name = getattr(error.orig, "constraint_name", None)
            if constraint_name is None:
                constraint_name = getattr(
                    getattr(error.orig, "__cause__", None),
                    "constraint_name",
                    None,
                )

            if constraint_name == "uq_kh_user_username_active":
                raise UserAlreadyExistsError("username already exists") from error
            if constraint_name == "uq_kh_user_email_active":
                raise UserAlreadyExistsError("email already exists") from error
            raise

        created_user = await session.scalar(
            select(User)
            .options(selectinload(User.role))
            .where(User.id == user.id)
        )
        if created_user is None:
            raise RuntimeError("created user could not be loaded")
        return created_user
