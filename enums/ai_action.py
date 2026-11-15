from enum import IntEnum, StrEnum


class AIActionType(StrEnum):
    EMAIL_SEND = "email_send"


class AIActionStatus(IntEnum):
    PENDING = 0
    EXECUTING = 10
    SUCCEEDED = 20
    FAILED = 30
    REJECTED = 40
    EXPIRED = 50
