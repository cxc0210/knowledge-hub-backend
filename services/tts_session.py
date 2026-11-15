import asyncio
import logging
from contextlib import suppress
from typing import Any

from fastapi import WebSocket

from core.config import settings
from services.streaming_text_chunker import StreamingTextChunker
from services.tts import TTSConfigurationError, TTSProviderError, TTSService

logger = logging.getLogger(__name__)


class SpeechStreamSession:
    def __init__(
        self,
        websocket: WebSocket,
        *,
        user_id: int,
        request_id: str,
    ) -> None:
        self.user_id = user_id
        self.request_id = request_id
        self._websocket = websocket
        self._chunker = StreamingTextChunker()
        self._text_queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=64)
        self._send_lock = asyncio.Lock()
        self._tts_task: asyncio.Task[None] | None = None
        self._input_finished = False
        self._terminal_event_sent = False
        self._closed = False

    async def send_ready(self) -> None:
        await self._send_control(
            {
                "type": "ready",
                "request_id": self.request_id,
                "encoding": "pcm_s16le",
                "sample_rate": settings.dashscope_tts_sample_rate,
                "channels": 1,
            }
        )

    async def feed_text(self, delta: str) -> None:
        if self._closed or self._input_finished:
            return

        for text in self._chunker.feed(delta):
            await self._enqueue_text(text)

    async def finish(self) -> None:
        if self._closed or self._input_finished:
            return

        self._input_finished = True
        for text in self._chunker.finish():
            await self._enqueue_text(text)

        if self._tts_task is None:
            await self._send_terminal_control({"type": "finished"})
            return
        if self._tts_task.done():
            return

        await self._text_queue.put(None)

    async def stop(self, *, notify: bool = True) -> None:
        if self._closed:
            return

        self._input_finished = True
        task = self._tts_task
        self._tts_task = None
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        if notify:
            await self._send_terminal_control({"type": "stopped"})

    async def disconnect(self) -> None:
        if self._closed:
            return
        await self.stop(notify=False)
        self._closed = True

    async def _enqueue_text(self, text: str) -> None:
        if self._tts_task is not None and self._tts_task.done():
            return
        if self._tts_task is None:
            self._tts_task = asyncio.create_task(self._run_tts())
        await self._text_queue.put(text)

    async def _run_tts(self) -> None:
        try:
            await TTSService.synthesize(
                self._text_queue,
                send_audio=self._send_audio,
                send_event=self._send_control,
            )
        except asyncio.CancelledError:
            raise
        except TTSConfigurationError as error:
            await self._send_terminal_control({"type": "error", "message": str(error)})
        except TTSProviderError:
            logger.exception(
                "TTS provider failed, user_id=%s request_id=%s",
                self.user_id,
                self.request_id,
            )
            await self._send_terminal_control(
                {"type": "error", "message": "语音合成失败，请稍后重试"}
            )
        except Exception:
            logger.exception(
                "TTS streaming failed, user_id=%s request_id=%s",
                self.user_id,
                self.request_id,
            )
            await self._send_terminal_control(
                {"type": "error", "message": "语音播放出现错误"}
            )
        else:
            await self._send_terminal_control({"type": "finished"})

    async def _send_audio(self, audio: bytes) -> None:
        if self._closed:
            return
        async with self._send_lock:
            await self._websocket.send_bytes(audio)

    async def _send_control(self, message: dict[str, Any]) -> None:
        if self._closed:
            return
        async with self._send_lock:
            await self._websocket.send_json(message)

    async def _send_terminal_control(self, message: dict[str, Any]) -> None:
        if self._terminal_event_sent:
            return
        self._terminal_event_sent = True
        await self._send_control(message)


class SpeechSessionManager:
    def __init__(self) -> None:
        self._sessions: dict[tuple[int, str], SpeechStreamSession] = {}
        self._lock = asyncio.Lock()

    async def register(self, session: SpeechStreamSession) -> None:
        key = (session.user_id, session.request_id)
        async with self._lock:
            previous = self._sessions.get(key)
            self._sessions[key] = session

        if previous is not None:
            with suppress(Exception):
                await previous.stop()

    async def get(
        self,
        user_id: int,
        request_id: str,
    ) -> SpeechStreamSession | None:
        async with self._lock:
            return self._sessions.get((user_id, request_id))

    async def unregister(self, session: SpeechStreamSession) -> None:
        key = (session.user_id, session.request_id)
        async with self._lock:
            if self._sessions.get(key) is session:
                self._sessions.pop(key, None)


speech_session_manager = SpeechSessionManager()
