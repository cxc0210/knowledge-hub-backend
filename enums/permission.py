from enum import StrEnum


class PermissionCode(StrEnum):
    DOCUMENT_MANAGE = "document:manage"
    DOCUMENT_REVIEW = "document:review"
    USER_MANAGE = "user:manage"
    RBAC_MANAGE = "rbac:manage"
