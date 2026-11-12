from datetime import UTC, datetime, timedelta

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from core.config import settings

password_hash = PasswordHash.recommended()
JWT_ALGORITHM = "HS256"


class InvalidAccessTokenError(Exception):
    pass


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(user_id: int, token_version: int) -> str:
    now = datetime.now(UTC)
    expires_at = now + timedelta(
        minutes=settings.jwt_access_token_expire_minutes,
    )
    return jwt.encode(
        {
            "sub": str(user_id),
            "token_version": token_version,
            "iat": now,
            "exp": expires_at,
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> tuple[int, int]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[JWT_ALGORITHM],
            options={
                "require": ["sub", "token_version", "iat", "exp"],
            },
        )
        user_id = int(payload["sub"])
        token_version = int(payload["token_version"])
    except (InvalidTokenError, KeyError, TypeError, ValueError) as error:
        raise InvalidAccessTokenError("invalid access token") from error

    if user_id <= 0 or token_version < 0:
        raise InvalidAccessTokenError("invalid access token")

    return user_id, token_version
