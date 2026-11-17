from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from enums.ai import AIMessageRole
from models.ai_conversation import AIConversation
from services.ai_conversation import (
    AIConversationNotFoundError,
    AIConversationService,
)


class AIConversationServiceTests(IsolatedAsyncioTestCase):
    async def test_lists_only_active_conversations_owned_by_user(self) -> None:
        session = AsyncMock(spec=AsyncSession)
        conversations = [MagicMock(), MagicMock()]
        scalar_result = MagicMock()
        scalar_result.all.return_value = conversations
        session.scalar.return_value = 12
        session.scalars.return_value = scalar_result

        result, total = await AIConversationService.list(
            session,
            user_id=1001,
            page=2,
            size=10,
        )

        self.assertEqual(result, conversations)
        self.assertEqual(total, 12)
        count_sql = " ".join(str(session.scalar.await_args.args[0]).split())
        list_sql = " ".join(str(session.scalars.await_args.args[0]).split())
        self.assertIn("kh_ai_conversation.user_id = :user_id_1", count_sql)
        self.assertIn("kh_ai_conversation.deleted IS false", count_sql)
        self.assertIn("last_message_at DESC NULLS LAST", list_sql)
        self.assertIn("LIMIT :param_1 OFFSET :param_2", list_sql)

    async def test_rejects_conversation_not_owned_by_user(self) -> None:
        session = AsyncMock(spec=AsyncSession)
        session.scalar.return_value = None

        with self.assertRaises(AIConversationNotFoundError):
            await AIConversationService.get_owned(
                session,
                conversation_id=uuid4(),
                user_id=1001,
            )

    async def test_first_user_message_sets_title_and_updates_activity(self) -> None:
        session = AsyncMock(spec=AsyncSession)
        conversation_id = uuid4()
        request_id = uuid4()
        conversation = AIConversation(
            id=conversation_id,
            user_id=1001,
            title="新对话",
        )
        session.scalar.return_value = conversation

        message = await AIConversationService.add_message(
            session,
            conversation_id=conversation_id,
            user_id=1001,
            request_id=request_id,
            role=AIMessageRole.USER,
            content="  请帮我介绍一下   PostgreSQL 事务  ",
        )

        self.assertEqual(conversation.title, "请帮我介绍一下 PostgreSQL 事务")
        self.assertIsNotNone(conversation.last_message_at)
        self.assertEqual(message.conversation_id, conversation_id)
        self.assertEqual(message.request_id, request_id)
        self.assertEqual(message.role, AIMessageRole.USER.value)
        session.add.assert_called_once_with(message)
        session.commit.assert_awaited_once()
        session.refresh.assert_awaited_once_with(message)

    async def test_assistant_message_does_not_replace_custom_title(self) -> None:
        session = AsyncMock(spec=AsyncSession)
        conversation_id = uuid4()
        conversation = AIConversation(
            id=conversation_id,
            user_id=1001,
            title="数据库学习",
        )
        session.scalar.return_value = conversation

        await AIConversationService.add_message(
            session,
            conversation_id=conversation_id,
            user_id=1001,
            request_id=uuid4(),
            role=AIMessageRole.ASSISTANT,
            content="这是回答",
        )

        self.assertEqual(conversation.title, "数据库学习")
