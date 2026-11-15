import asyncio
import json
import logging
from collections.abc import AsyncIterator, Mapping
from contextlib import suppress
from typing import Any
from uuid import uuid4

from langchain_core.messages import HumanMessage

from core.llm import get_chat_model
from graphs.ai import ai_graph
from graphs.context import AgentContext
from schemas.ai import AIChatResponse
from services.tts_session import SpeechStreamSession

logger = logging.getLogger(__name__)


def _ui_message_chunk(data: Mapping[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"data: {payload}\n\n"


def _ui_message_done() -> str:
    return "data: [DONE]\n\n"


class AIService:
    @staticmethod
    async def chat(prompt: str, agent_context: AgentContext) -> AIChatResponse:
        result = await ai_graph.ainvoke(
            {"messages": [HumanMessage(content=prompt)]},
            context=agent_context,
        )
        return AIChatResponse(answer=result["messages"][-1].text)

    @staticmethod
    def stream_chat(
        prompt: str,
        agent_context: AgentContext,
        speech_session: SpeechStreamSession | None = None,
    ) -> AsyncIterator[str]:
        get_chat_model()
        return AIService._stream_chat(prompt, agent_context, speech_session)

    @staticmethod
    async def _stream_chat(
        prompt: str,
        agent_context: AgentContext,
        speech_session: SpeechStreamSession | None,
    ) -> AsyncIterator[str]:
        active_speech_session = speech_session
        message_id = f"msg_{uuid4().hex}"
        text_id = f"text_{uuid4().hex}"
        yield _ui_message_chunk({"type": "start", "messageId": message_id})
        yield _ui_message_chunk({"type": "text-start", "id": text_id})

        try:
            async for part in ai_graph.astream(
                {"messages": [HumanMessage(content=prompt)]},
                context=agent_context,
                stream_mode=["messages", "custom"],
                version="v2",
            ):
                if part["type"] == "custom":
                    custom_event = part["data"]
                    if (
                        isinstance(custom_event, dict)
                        and custom_event.get("type") == "email-approval"
                        and isinstance(custom_event.get("data"), dict)
                    ):
                        action_data = custom_event["data"]
                        yield _ui_message_chunk(
                            {
                                "type": "data-email-approval",
                                "id": action_data.get("id"),
                                "data": action_data,
                            }
                        )
                    continue

                if part["type"] != "messages":
                    continue

                message, metadata = part["data"]
                if metadata.get("langgraph_node") != "call_model":
                    continue

                content = message.text
                if content:
                    if active_speech_session is not None:
                        try:
                            await active_speech_session.feed_text(content)
                        except Exception:
                            logger.exception(
                                "TTS text forwarding failed; text stream continues"
                            )
                            active_speech_session = None
                    yield _ui_message_chunk(
                        {
                            "type": "text-delta",
                            "id": text_id,
                            "delta": content,
                        }
                    )

            if active_speech_session is not None:
                try:
                    await active_speech_session.finish()
                except Exception:
                    logger.exception("TTS finalization failed; text stream continues")

            yield _ui_message_chunk({"type": "text-end", "id": text_id})
            yield _ui_message_chunk({"type": "finish", "finishReason": "stop"})
            yield _ui_message_done()
        except asyncio.CancelledError:
            if active_speech_session is not None:
                with suppress(Exception):
                    await active_speech_session.stop()
            raise
        except Exception:
            logger.exception("AI streaming request failed")
            if active_speech_session is not None:
                with suppress(Exception):
                    await active_speech_session.stop()
            yield _ui_message_chunk(
                {
                    "type": "error",
                    "errorText": "模型调用失败，请稍后重试",
                }
            )
            yield _ui_message_chunk({"type": "text-end", "id": text_id})
            yield _ui_message_chunk({"type": "finish", "finishReason": "error"})
            yield _ui_message_done()
