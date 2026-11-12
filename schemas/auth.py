from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    StringConstraints,
)

LoginIdentifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=320),
]


class LoginRequest(BaseModel):
    username_or_email: LoginIdentifier
    password: SecretStr = Field(min_length=1, max_length=128)

    model_config = ConfigDict(extra="forbid")
