import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from enums.ai import AIMessageRole
from models.ai_conversation import AIConversation
from models.ai_message import AIMessage

DEFAULT_CONVERSATION_TITLE = "新对话"
TITLE_MAX_DISPLAY_LENGTH = 60


class AIConversationNotFoundError(Exception):
    pass


class AIConversationService:
    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        user_id: int,
        title: str | None,
    ) -> AIConversation:
        conversation = AIConversation(
            user_id=user_id,
            title=title or DEFAULT_CONVERSATION_TITLE,
        )
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
        return conversation

    @staticmethod
    async def list(
        session: AsyncSession,
        *,
        user_id: int,
        page: int,
        size: int,
    ) -> tuple[list[AIConversation], int]:
        filters = (
            AIConversation.user_id == user_id,
            AIConversation.deleted.is_(False),
        )
        total = await session.scalar(
            select(func.count(AIConversation.id)).where(*filters),
        )
        result = await session.scalars(
            select(AIConversation)
            .where(*filters)
            .order_by(
                AIConversation.last_message_at.desc().nullslast(),
                AIConversation.created_at.desc(),
                AIConversation.id.desc(),
            )
            .offset((page - 1) * size)
            .limit(size),
        )
        return list(result.all()), total or 0

    @classmethod
    async def get_owned(
        cls,
        session: AsyncSession,
        *,
        conversation_id: UUID,
        user_id: int,
        for_update: bool = False,
    ) -> AIConversation:
        statement = select(AIConversation).where(
            AIConversation.id == conversation_id,
            AIConversation.user_id == user_id,
            AIConversation.deleted.is_(False),
        )
        if for_update:
            statement = statement.with_for_update()
        conversation = await session.scalar(statement)
        if conversation is None:
            raise AIConversationNotFoundError(
                f"conversation '{conversation_id}' does not exist",
            )
        return conversation

    @classmethod
    async def update_title(
        cls,
        session: AsyncSession,
        *,
        conversation_id: UUID,
        user_id: int,
        title: str,
    ) -> AIConversation:
        conversation = await cls.get_owned(
            session,
            conversation_id=conversation_id,
            user_id=user_id,
            for_update=True,
        )
        conversation.title = title
        await session.commit()
        await session.refresh(conversation)
        return conversation

    @classmethod
    async def delete(
        cls,
        session: AsyncSession,
        *,
        conversation_id: UUID,
        user_id: int,
    ) -> None:
        conversation = await cls.get_owned(
            session,
            conversation_id=conversation_id,
            user_id=user_id,
            for_update=True,
        )
        conversation.deleted = True
        await session.commit()

    @classmethod
    async def list_messages(
        cls,
        session: AsyncSession,
        *,
        conversation_id: UUID,
        user_id: int,
        page: int,
        size: int,
    ) -> tuple[list[AIMessage], int]:
        await cls.get_owned(
            session,
            conversation_id=conversation_id,
            user_id=user_id,
        )
        total = await session.scalar(
            select(func.count(AIMessage.id)).where(
                AIMessage.conversation_id == conversation_id,
            )
        )
        result = await session.scalars(
            select(AIMessage)
            .where(AIMessage.conversation_id == conversation_id)
            .order_by(AIMessage.created_at.asc(), AIMessage.id.asc())
            .offset((page - 1) * size)
            .limit(size),
        )
        return list(result.all()), total or 0

    @classmethod
    async def add_message(
        cls,
        session: AsyncSession,
        *,
        conversation_id: UUID,
        user_id: int,
        request_id: UUID,
        role: AIMessageRole,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> AIMessage:
        conversation = await cls.get_owned(
            session,
            conversation_id=conversation_id,
            user_id=user_id,
            for_update=True,
        )
        message = AIMessage(
            conversation_id=conversation.id,
            request_id=request_id,
            role=role.value,
            content=content,
            message_metadata=metadata or {},
        )
        session.add(message)

        now = datetime.now(UTC)
        conversation.last_message_at = now
        if (
            role == AIMessageRole.USER
            and conversation.title == DEFAULT_CONVERSATION_TITLE
        ):
            conversation.title = _title_from_message(content)

        await session.commit()
        await session.refresh(message)
        return message


def _title_from_message(content: str) -> str:
    normalized = re.sub(r"\s+", " ", content).strip()
    if len(normalized) <= TITLE_MAX_DISPLAY_LENGTH:
        return normalized
    return f"{normalized[: TITLE_MAX_DISPLAY_LENGTH - 1]}…"
