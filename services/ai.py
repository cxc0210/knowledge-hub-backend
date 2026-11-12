import asyncio
import json
import logging
from collections.abc import AsyncIterator, Mapping
from typing import Any
from uuid import uuid4

from core.llm import get_chat_model
from graphs.ai import ai_graph
from schemas.ai import AIChatResponse

logger = logging.getLogger(__name__)


def _ui_message_chunk(data: Mapping[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"data: {payload}\n\n"


def _ui_message_done() -> str:
    return "data: [DONE]\n\n"


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
        message_id = f"msg_{uuid4().hex}"
        text_id = f"text_{uuid4().hex}"
        yield _ui_message_chunk({"type": "start", "messageId": message_id})
        yield _ui_message_chunk({"type": "text-start", "id": text_id})

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
                    yield _ui_message_chunk(
                        {
                            "type": "text-delta",
                            "id": text_id,
                            "delta": content,
                        }
                    )

            yield _ui_message_chunk({"type": "text-end", "id": text_id})
            yield _ui_message_chunk(
                {"type": "finish", "finishReason": "stop"}
            )
            yield _ui_message_done()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("AI streaming request failed")
            yield _ui_message_chunk(
                {
                    "type": "error",
                    "errorText": "模型调用失败，请稍后重试",
                }
            )
            yield _ui_message_chunk({"type": "text-end", "id": text_id})
            yield _ui_message_chunk(
                {"type": "finish", "finishReason": "error"}
            )
            yield _ui_message_done()
