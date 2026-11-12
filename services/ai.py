import asyncio
import json
import logging
from collections.abc import AsyncIterator, Mapping
from typing import Any

from core.llm import get_chat_model
from graphs.ai import ai_graph
from schemas.ai import AIChatResponse

logger = logging.getLogger(__name__)


def _sse_event(event: str, data: Mapping[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


class AIService:
    @staticmethod
    async def chat(prompt: str) -> AIChatResponse:
        result = await ai_graph.ainvoke({"prompt": prompt})
        return AIChatResponse(answer=result["answer"])

    @staticmethod
    def stream_chat(prompt: str) -> AsyncIterator[str]:
        get_chat_model()
        return AIService._stream_chat(prompt)

    @staticmethod
    async def _stream_chat(prompt: str) -> AsyncIterator[str]:
        try:
            async for part in ai_graph.astream(
                {"prompt": prompt},
                stream_mode="messages",
                version="v2",
            ):
                if part["type"] != "messages":
                    continue

                message, metadata = part["data"]
                if metadata.get("langgraph_node") != "call_model":
                    continue

                content = message.text
                if content:
                    yield _sse_event("token", {"content": content})

            yield _sse_event("done", {})
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("AI streaming request failed")
            yield _sse_event(
                "error",
                {"message": "模型调用失败，请稍后重试"},
            )
