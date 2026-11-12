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
