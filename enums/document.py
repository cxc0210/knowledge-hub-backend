from enum import IntEnum


class DocumentStatus(IntEnum):
    PENDING_UPLOAD = 0
    UPLOADED = 10

    PARSING = 20
    PARSE_FAILED = 21

    DRAFT = 30

    PENDING_REVIEW = 40
    REJECTED = 41

    INDEXING = 45
    INDEX_FAILED = 46

    PUBLISHED = 50
    UNPUBLISHED = 51

    ARCHIVED = 90
