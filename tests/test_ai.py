from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage

from enums.ai_action import AIActionStatus, AIActionType
from graphs.ai import ai_graph
from graphs.context import AgentContext
from graphs.main import main_graph
from schemas.ai_action import EmailActionResponse
from services.ai import AIService

TEST_CONTEXT = AgentContext(
    user_id=1001,
    permission_codes=frozenset({"ai:email:send"}),
)


class AIGraphTests(IsolatedAsyncioTestCase):
    async def test_sends_messages_to_tool_bound_model_and_returns_answer(
        self,
    ) -> None:
        bound_model = SimpleNamespace(
            ainvoke=AsyncMock(return_value=AIMessage(content="模型答案")),
        )
        model = SimpleNamespace(
            bind_tools=Mock(return_value=bound_model),
        )

        with patch("graphs.ai.get_chat_model", return_value=model):
            result = await ai_graph.ainvoke(
                {"messages": [HumanMessage(content="用户问题")]},
                context=TEST_CONTEXT,
            )

        model.bind_tools.assert_called_once()
        invoked_messages = bound_model.ainvoke.await_args.args[0]
        self.assertEqual(invoked_messages[-1].text, "用户问题")
        self.assertEqual(result["messages"][-1].text, "模型答案")

    async def test_executes_email_tool_and_loops_back_to_model(self) -> None:
        action_id = uuid4()
        now = datetime.now(UTC)
        action_response = EmailActionResponse(
            id=action_id,
            action_type=AIActionType.EMAIL_SEND,
            status=AIActionStatus.PENDING,
            recipients=["user@example.com"],
            subject="测试邮件",
            body="你好",
            provider_message_id=None,
            error_message=None,
            expires_at=now + timedelta(minutes=30),
            approved_at=None,
            executed_at=None,
            created_at=now,
            updated_at=now,
        )
        bound_model = SimpleNamespace(
            ainvoke=AsyncMock(
                side_effect=[
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "request_email_send",
                                "args": {
                                    "recipients": ["user@example.com"],
                                    "subject": "测试邮件",
                                    "body": "你好",
                                },
                                "id": "tool-call-1",
                                "type": "tool_call",
                            }
                        ],
                    ),
                    AIMessage(content="邮件已生成，请确认发送。"),
                ]
            )
        )
        model = SimpleNamespace(bind_tools=Mock(return_value=bound_model))
        create_action = AsyncMock(return_value=object())

        @asynccontextmanager
        async def fake_session_factory():
            yield object()

        with (
            patch("graphs.ai.get_chat_model", return_value=model),
            patch("tools.email.session_factory", new=fake_session_factory),
            patch(
                "tools.email.AIActionService.create_email_send",
                new=create_action,
            ),
            patch(
                "tools.email.EmailActionResponse.from_action",
                return_value=action_response,
            ),
        ):
            events = [
                cast(dict[str, Any], event)
                async for event in ai_graph.astream(
                    {"messages": [HumanMessage(content="帮我发送邮件")]},
                    context=TEST_CONTEXT,
                    stream_mode="custom",
                    version="v2",
                )
            ]

        self.assertEqual(bound_model.ainvoke.await_count, 2)
        create_action.assert_awaited_once()
        self.assertEqual(events[0]["type"], "custom")
        self.assertEqual(events[0]["data"]["data"]["id"], str(action_id))


class AIServiceTests(IsolatedAsyncioTestCase):
    async def test_returns_api_response(self) -> None:
        with patch.object(
            main_graph,
            "ainvoke",
            new=AsyncMock(return_value={"messages": [AIMessage(content="答案")]}),
        ) as invoke:
            result = await AIService.chat("问题", TEST_CONTEXT)

        self.assertEqual(result.answer, "答案")
        await_args = invoke.await_args
        assert await_args is not None
        self.assertEqual(await_args.kwargs["context"], TEST_CONTEXT)

    async def test_streams_model_tokens_as_sse_events(self) -> None:
        async def fake_stream(*args, **kwargs):
            messages = args[0]["messages"]
            self.assertEqual(messages[-1].text, "问题")
            self.assertEqual(kwargs["context"], TEST_CONTEXT)
            self.assertEqual(kwargs["stream_mode"], ["messages", "custom"])
            self.assertTrue(kwargs["subgraphs"])
            self.assertEqual(kwargs["version"], "v2")
            yield {
                "type": "messages",
                "data": (
                    SimpleNamespace(text="你"),
                    {"langgraph_node": "call_model"},
                ),
            }
            yield {
                "type": "messages",
                "data": (
                    SimpleNamespace(text="好"),
                    {"langgraph_node": "call_model"},
                ),
            }

        with (
            patch("services.ai.get_chat_model"),
            patch(
                "services.ai.uuid4",
                side_effect=[
                    SimpleNamespace(hex="message-id"),
                    SimpleNamespace(hex="text-id"),
                ],
            ),
            patch.object(main_graph, "astream", new=fake_stream),
        ):
            events = [
                event
                async for event in AIService.stream_chat(
                    "问题",
                    TEST_CONTEXT,
                )
            ]

        self.assertEqual(
            events,
            [
                'data: {"type":"start","messageId":"msg_message-id"}\n\n',
                'data: {"type":"text-start","id":"text_text-id"}\n\n',
                'data: {"type":"text-delta","id":"text_text-id","delta":"你"}\n\n',
                'data: {"type":"text-delta","id":"text_text-id","delta":"好"}\n\n',
                'data: {"type":"text-end","id":"text_text-id"}\n\n',
                'data: {"type":"finish","finishReason":"stop"}\n\n',
                "data: [DONE]\n\n",
            ],
        )

    async def test_reports_complete_streamed_answer_and_sources(self) -> None:
        sources = [{"document_id": 100001, "chunk_id": "chunk-1"}]

        async def fake_stream(*args, **kwargs):
            yield {
                "type": "custom",
                "data": {
                    "type": "rag-sources",
                    "data": sources,
                },
            }
            yield {
                "type": "messages",
                "data": (
                    SimpleNamespace(text="完整"),
                    {"langgraph_node": "generate_answer"},
                ),
            }
            yield {
                "type": "messages",
                "data": (
                    SimpleNamespace(text="答案"),
                    {"langgraph_node": "generate_answer"},
                ),
            }

        on_complete = AsyncMock()
        with (
            patch("services.ai.get_chat_model"),
            patch.object(main_graph, "astream", new=fake_stream),
        ):
            events = [
                event
                async for event in AIService.stream_chat(
                    "问题",
                    TEST_CONTEXT,
                    on_complete=on_complete,
                )
            ]

        on_complete.assert_awaited_once_with("完整答案", sources)
        self.assertIn('"delta":"完整"', "".join(events))
        self.assertIn('"delta":"答案"', "".join(events))

    async def test_streams_email_approval_as_data_part(self) -> None:
        action_data = {
            "id": "450b66ad-8a8f-4387-94d1-4e787934e601",
            "status": 0,
            "recipients": ["user@example.com"],
            "subject": "测试邮件",
            "body": "你好",
        }

        async def fake_stream(*args, **kwargs):
            yield {
                "type": "custom",
                "data": {
                    "type": "email-approval",
                    "data": action_data,
                },
            }

        with (
            patch("services.ai.get_chat_model"),
            patch.object(main_graph, "astream", new=fake_stream),
        ):
            events = [
                event
                async for event in AIService.stream_chat(
                    "发送邮件",
                    TEST_CONTEXT,
                )
            ]

        self.assertIn(
            '"type":"data-email-approval"',
            "".join(events),
        )
        self.assertIn(action_data["id"], "".join(events))

    async def test_streams_rag_sources_and_answer_text(self) -> None:
        sources = [
            {
                "document_id": 100001,
                "chunk_id": "100001:v1:0",
                "title": "事务指南",
                "heading": "事务管理",
            }
        ]

        async def fake_stream(*args, **kwargs):
            yield {
                "type": "custom",
                "data": {
                    "type": "rag-sources",
                    "data": sources,
                },
            }
            yield {
                "type": "messages",
                "data": (
                    SimpleNamespace(text="知识库答案"),
                    {"langgraph_node": "generate_answer"},
                ),
            }

        with (
            patch("services.ai.get_chat_model"),
            patch.object(main_graph, "astream", new=fake_stream),
        ):
            events = [
                event
                async for event in AIService.stream_chat(
                    "事务怎么管理？",
                    TEST_CONTEXT,
                )
            ]

        payload = "".join(events)
        self.assertIn('"type":"data-rag-sources"', payload)
        self.assertIn('"delta":"知识库答案"', payload)

    async def test_forwards_only_model_text_to_speech_session(self) -> None:
        async def fake_stream(*args, **kwargs):
            yield {
                "type": "custom",
                "data": {
                    "type": "email-approval",
                    "data": {"id": "action-id"},
                },
            }
            yield {
                "type": "messages",
                "data": (
                    SimpleNamespace(text="语音内容。"),
                    {"langgraph_node": "call_model"},
                ),
            }

        speech_session = SimpleNamespace(
            feed_text=AsyncMock(),
            finish=AsyncMock(),
            stop=AsyncMock(),
        )

        with (
            patch("services.ai.get_chat_model"),
            patch.object(main_graph, "astream", new=fake_stream),
        ):
            events = [
                event
                async for event in AIService.stream_chat(
                    "问题",
                    TEST_CONTEXT,
                    speech_session,  # type: ignore[arg-type]
                )
            ]

        speech_session.feed_text.assert_awaited_once_with("语音内容。")
        speech_session.finish.assert_awaited_once_with()
        speech_session.stop.assert_not_awaited()
        self.assertIn('"delta":"语音内容。"', "".join(events))

    async def test_streams_safe_error_event_when_model_fails(self) -> None:
        async def failing_stream(*args, **kwargs):
            if False:
                yield None
            raise RuntimeError("provider secret error")

        with (
            patch("services.ai.get_chat_model"),
            patch(
                "services.ai.uuid4",
                side_effect=[
                    SimpleNamespace(hex="message-id"),
                    SimpleNamespace(hex="text-id"),
                ],
            ),
            patch.object(main_graph, "astream", new=failing_stream),
            self.assertLogs("services.ai", level="ERROR"),
        ):
            events = [
                event
                async for event in AIService.stream_chat(
                    "问题",
                    TEST_CONTEXT,
                )
            ]

        self.assertEqual(
            events,
            [
                'data: {"type":"start","messageId":"msg_message-id"}\n\n',
                'data: {"type":"text-start","id":"text_text-id"}\n\n',
                'data: {"type":"error","errorText":"模型调用失败，请稍后重试"}\n\n',
                'data: {"type":"text-end","id":"text_text-id"}\n\n',
                'data: {"type":"finish","finishReason":"error"}\n\n',
                "data: [DONE]\n\n",
            ],
        )
