from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    StringConstraints,
)


Username = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=3,
        max_length=50,
        pattern=r"^[A-Za-z0-9_.-]+$",
    ),
]


class UserCreate(BaseModel):
    username: Username
    email: EmailStr
    password: SecretStr = Field(min_length=8, max_length=128)

    model_config = ConfigDict(extra="forbid")


class UserRoleResponse(BaseModel):
    code: str
    name: str

    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    avatar_url: str | None
    role: UserRoleResponse
    status: int
    email_verified_at: datetime | None
    last_login_at: datetime | None
    password_changed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
