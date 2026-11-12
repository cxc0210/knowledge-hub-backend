from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from graphs.ai import ai_graph
from services.ai import AIService


class AIGraphTests(IsolatedAsyncioTestCase):
    async def test_sends_prompt_to_model_and_returns_answer(self) -> None:
        model = SimpleNamespace(
            ainvoke=AsyncMock(return_value=SimpleNamespace(text="模型答案")),
        )

        with patch("graphs.ai.get_chat_model", return_value=model):
            result = await ai_graph.ainvoke({"prompt": "用户问题"})

        model.ainvoke.assert_awaited_once_with("用户问题")
        self.assertEqual(result["answer"], "模型答案")


class AIServiceTests(IsolatedAsyncioTestCase):
    async def test_returns_api_response(self) -> None:
        with patch.object(
            ai_graph,
            "ainvoke",
            new=AsyncMock(return_value={"prompt": "问题", "answer": "答案"}),
        ):
            result = await AIService.chat("问题")

        self.assertEqual(result.answer, "答案")

    async def test_streams_model_tokens_as_sse_events(self) -> None:
        async def fake_stream(*args, **kwargs):
            self.assertEqual(args, ({"prompt": "问题"},))
            self.assertEqual(kwargs["stream_mode"], "messages")
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
            patch.object(ai_graph, "astream", new=fake_stream),
        ):
            events = [event async for event in AIService.stream_chat("问题")]

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
            patch.object(ai_graph, "astream", new=failing_stream),
            self.assertLogs("services.ai", level="ERROR"),
        ):
            events = [event async for event in AIService.stream_chat("问题")]

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
