import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from enums.ai_action import AIActionStatus, AIActionType
from models.ai_action import AIAction
from services.email import EmailService

logger = logging.getLogger(__name__)


class AIActionNotFoundError(Exception):
    pass


class AIActionInvalidStateError(Exception):
    pass


class AIActionExpiredError(Exception):
    pass


class AIActionService:
    @staticmethod
    async def create_email_send(
        session: AsyncSession,
        *,
        user_id: int,
        recipients: list[str],
        subject: str,
        body: str,
        tool_call_id: str | None,
    ) -> AIAction:
        normalized_recipients = sorted(
            {recipient.strip().lower() for recipient in recipients}
        )
        payload = {
            "recipients": normalized_recipients,
            "subject": subject.strip(),
            "body": body.strip(),
        }
        idempotency_key = _idempotency_key(
            user_id=user_id,
            tool_call_id=tool_call_id,
            payload=payload,
        )

        existing = await session.scalar(
            select(AIAction).where(
                AIAction.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return existing

        action = AIAction(
            user_id=user_id,
            action_type=AIActionType.EMAIL_SEND,
            status=AIActionStatus.PENDING,
            payload=payload,
            tool_call_id=tool_call_id,
            idempotency_key=idempotency_key,
            expires_at=datetime.now(UTC)
            + timedelta(minutes=settings.ai_action_expire_minutes),
        )
        session.add(action)

        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            existing = await session.scalar(
                select(AIAction).where(
                    AIAction.idempotency_key == idempotency_key,
                )
            )
            if existing is None:
                raise
            return existing

        await session.refresh(action)
        return action

    @staticmethod
    async def approve_email_send(
        session: AsyncSession,
        *,
        action_id: UUID,
        user_id: int,
    ) -> AIAction:
        action = await _get_owned_action_for_update(session, action_id, user_id)
        if action.status == AIActionStatus.SUCCEEDED:
            return action
        await _ensure_pending(session, action)

        action.status = AIActionStatus.EXECUTING
        action.approved_at = datetime.now(UTC)
        action.error_message = None
        await session.commit()

        payload = action.payload
        try:
            message_id = await EmailService.send(
                recipients=list(payload["recipients"]),
                subject=str(payload["subject"]),
                body=str(payload["body"]),
            )
        except Exception:
            logger.exception(
                "Email action execution failed",
                extra={"action_id": str(action.id)},
            )
            action.status = AIActionStatus.FAILED
            action.error_message = "邮件发送失败，请检查 SMTP 配置后重试"
            action.executed_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(action)
            return action

        action.status = AIActionStatus.SUCCEEDED
        action.provider_message_id = message_id
        action.executed_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(action)
        return action

    @staticmethod
    async def reject_email_send(
        session: AsyncSession,
        *,
        action_id: UUID,
        user_id: int,
    ) -> AIAction:
        action = await _get_owned_action_for_update(session, action_id, user_id)
        await _ensure_pending(session, action)
        action.status = AIActionStatus.REJECTED
        action.executed_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(action)
        return action


async def _get_owned_action_for_update(
    session: AsyncSession,
    action_id: UUID,
    user_id: int,
) -> AIAction:
    action = await session.scalar(
        select(AIAction)
        .where(
            AIAction.id == action_id,
            AIAction.user_id == user_id,
            AIAction.action_type == AIActionType.EMAIL_SEND,
        )
        .with_for_update()
    )
    if action is None:
        raise AIActionNotFoundError("email action was not found")
    return action


async def _ensure_pending(session: AsyncSession, action: AIAction) -> None:
    if action.status != AIActionStatus.PENDING:
        raise AIActionInvalidStateError(
            f"email action status '{action.status}' cannot be changed",
        )
    if action.expires_at <= datetime.now(UTC):
        action.status = AIActionStatus.EXPIRED
        action.executed_at = datetime.now(UTC)
        await session.commit()
        raise AIActionExpiredError("email action has expired")


def _idempotency_key(
    *,
    user_id: int,
    tool_call_id: str | None,
    payload: dict[str, object],
) -> str:
    source = json.dumps(
        {
            "user_id": user_id,
            "tool_call_id": tool_call_id or uuid4().hex,
            "payload": payload,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(source.encode()).hexdigest()
