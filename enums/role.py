from enum import IntEnum, StrEnum


class RoleId(IntEnum):
    ADMIN = 1
    USER = 2


class RoleCode(StrEnum):
    ADMIN = "admin"
    USER = "user"
