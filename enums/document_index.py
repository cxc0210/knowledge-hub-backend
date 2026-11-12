from enum import IntEnum


class DocumentIndexJobStatus(IntEnum):
    PENDING = 0
    PROCESSING = 10
    SUCCESS = 20
    FAILED = 30
