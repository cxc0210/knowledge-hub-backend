from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from enums.ai_action import AIActionStatus, AIActionType
from models.ai_action import AIAction


class EmailActionResponse(BaseModel):
    id: UUID
    action_type: AIActionType
    status: AIActionStatus
    recipients: list[str]
    subject: str
    body: str
    provider_message_id: str | None
    error_message: str | None
    expires_at: datetime
    approved_at: datetime | None
    executed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_action(cls, action: AIAction) -> EmailActionResponse:
        payload = action.payload
        recipients = payload.get("recipients")
        subject = payload.get("subject")
        body = payload.get("body")
        if (
            not isinstance(recipients, list)
            or not all(isinstance(item, str) for item in recipients)
            or not isinstance(subject, str)
            or not isinstance(body, str)
        ):
            raise ValueError("email action contains an invalid payload")

        return cls(
            id=action.id,
            action_type=AIActionType(action.action_type),
            status=AIActionStatus(action.status),
            recipients=recipients,
            subject=subject,
            body=body,
            provider_message_id=action.provider_message_id,
            error_message=action.error_message,
            expires_at=action.expires_at,
            approved_at=action.approved_at,
            executed_at=action.executed_at,
            created_at=action.created_at,
            updated_at=action.updated_at,
        )
