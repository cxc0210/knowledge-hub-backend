from enum import IntEnum


class DocumentStatus(IntEnum):
    UPLOADED = 10

    PARSING = 20
    PARSE_FAILED = 21

    DRAFT = 30

    PENDING_REVIEW = 40
    REJECTED = 41

    PUBLISHED = 50
    UNPUBLISHED = 51

    ARCHIVED = 90