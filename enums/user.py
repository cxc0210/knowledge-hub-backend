from enum import IntEnum


class UserStatus(IntEnum):
    PENDING_VERIFICATION = 0
    ACTIVE = 1
    DISABLED = 2
