import asyncio
import json
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any
from uuid import uuid4

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import WebSocketException

from core.config import settings

TextQueue = asyncio.Queue[str | None]
SendAudio = Callable[[bytes], Awaitable[None]]
SendEvent = Callable[[dict[str, Any]], Awaitable[None]]


class TTSConfigurationError(Exception):
    pass


class TTSProviderError(Exception):
    pass


class TTSService:
    @staticmethod
    async def synthesize(
        text_queue: TextQueue,
        *,
        send_audio: SendAudio,
        send_event: SendEvent,
    ) -> None:
        api_key = settings.dashscope_api_key.get_secret_value().strip()
        websocket_url = settings.dashscope_tts_websocket_url.strip()
        if not api_key or not websocket_url:
            raise TTSConfigurationError("语音合成服务尚未配置")

        task_id = str(uuid4())
        connection: ClientConnection | None = None
        task_started = False

        try:
            async with connect(
                websocket_url,
                additional_headers={
                    "Authorization": f"Bearer {api_key}",
                },
                open_timeout=settings.dashscope_tts_connect_timeout_seconds,
                close_timeout=5,
                ping_interval=20,
                ping_timeout=20,
                max_size=None,
            ) as provider_connection:
                connection = provider_connection
                await connection.send(_run_task_message(task_id))
                await _wait_until_task_started(connection)
                task_started = True
                await send_event({"type": "started"})

                sender = asyncio.create_task(
                    _send_text(connection, task_id, text_queue)
                )
                try:
                    await _receive_audio(connection, send_audio)
                    await sender
                finally:
                    if not sender.done():
                        sender.cancel()
                    await asyncio.gather(sender, return_exceptions=True)
        except asyncio.CancelledError:
            if connection is not None and task_started:
                with suppress(Exception):
                    await asyncio.shield(connection.send(_cancel_task_message(task_id)))
            raise
        except TTSProviderError:
            raise
        except (TimeoutError, OSError, WebSocketException) as error:
            raise TTSProviderError("语音合成服务连接失败") from error
        except Exception as error:
            raise TTSProviderError("语音合成服务调用失败") from error


async def _wait_until_task_started(connection: ClientConnection) -> None:
    while True:
        message = await connection.recv()
        if isinstance(message, bytes):
            continue

        event = _parse_event(message)
        event_type = event.get("header", {}).get("event")
        if event_type == "task-started":
            return
        if event_type == "task-failed":
            raise _provider_event_error(event)


async def _send_text(
    connection: ClientConnection,
    task_id: str,
    text_queue: TextQueue,
) -> None:
    while True:
        text = await text_queue.get()
        if text is None:
            await connection.send(_finish_task_message(task_id))
            return
        await connection.send(_continue_task_message(task_id, text))


async def _receive_audio(
    connection: ClientConnection,
    send_audio: SendAudio,
) -> None:
    while True:
        message = await connection.recv()
        if isinstance(message, bytes):
            await send_audio(message)
            continue

        event = _parse_event(message)
        event_type = event.get("header", {}).get("event")
        if event_type == "task-finished":
            return
        if event_type == "task-failed":
            raise _provider_event_error(event)


def _parse_event(message: str) -> dict[str, Any]:
    try:
        event = json.loads(message)
    except json.JSONDecodeError as error:
        raise TTSProviderError("语音合成服务返回了无效响应") from error

    if not isinstance(event, dict):
        raise TTSProviderError("语音合成服务返回了无效响应")
    return event


def _provider_event_error(event: dict[str, Any]) -> TTSProviderError:
    header = event.get("header")
    if not isinstance(header, dict):
        return TTSProviderError("语音合成失败")

    message = header.get("error_message")
    if not isinstance(message, str) or not message.strip():
        message = "语音合成失败"
    return TTSProviderError(message)


def _run_task_message(task_id: str) -> str:
    return _json_message(
        {
            "header": {
                "action": "run-task",
                "task_id": task_id,
                "streaming": "duplex",
            },
            "payload": {
                "task_group": "audio",
                "task": "tts",
                "function": "SpeechSynthesizer",
                "model": settings.dashscope_tts_model,
                "parameters": {
                    "text_type": "PlainText",
                    "voice": settings.dashscope_tts_voice,
                    "format": "pcm",
                    "sample_rate": settings.dashscope_tts_sample_rate,
                    "volume": settings.dashscope_tts_volume,
                    "rate": settings.dashscope_tts_rate,
                    "pitch": settings.dashscope_tts_pitch,
                    "language_hints": ["zh"],
                    "enable_ssml": False,
                },
                "input": {},
            },
        }
    )


def _continue_task_message(task_id: str, text: str) -> str:
    return _json_message(
        {
            "header": {
                "action": "continue-task",
                "task_id": task_id,
                "streaming": "duplex",
            },
            "payload": {"input": {"text": text}},
        }
    )


def _finish_task_message(task_id: str) -> str:
    return _json_message(
        {
            "header": {
                "action": "finish-task",
                "task_id": task_id,
                "streaming": "duplex",
            },
            "payload": {"input": {}},
        }
    )


def _cancel_task_message(task_id: str) -> str:
    return _json_message(
        {
            "header": {
                "action": "finish-task",
                "task_id": task_id,
                "streaming": "duplex",
            },
            "payload": {"input": {"directive": "cancel"}},
        }
    )


def _json_message(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
