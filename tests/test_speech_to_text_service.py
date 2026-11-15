import base64
from io import BytesIO
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import UploadFile
from pydantic import SecretStr
from starlette.datastructures import Headers

from core.config import settings
from services.speech_to_text import (
    AudioFileTooLargeError,
    SpeechRecognitionProviderError,
    SpeechToTextService,
    UnsupportedAudioFormatError,
)


def upload_file(
    content: bytes,
    content_type: str = "audio/webm;codecs=opus",
) -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename="recording.webm",
        headers=Headers({"content-type": content_type}),
    )


class SpeechToTextServiceTests(IsolatedAsyncioTestCase):
    async def test_transcribes_browser_webm_audio(self) -> None:
        audio = b"browser-audio"
        request = httpx.Request("POST", "https://example.test/asr")
        response = httpx.Response(
            200,
            request=request,
            json={
                "output": {"text": " 查询知识库 "},
                "usage": {"duration": 4},
                "request_id": "request-123",
            },
        )
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.return_value = response

        with patch.object(
            settings,
            "dashscope_api_key",
            SecretStr("test-key"),
        ):
            result = await SpeechToTextService.transcribe(
                client,
                upload_file(audio),
            )

        self.assertEqual(result.text, "查询知识库")
        self.assertEqual(result.duration_seconds, 4.0)
        self.assertEqual(result.request_id, "request-123")

        call = client.post.await_args
        self.assertIsNotNone(call)
        payload = call.kwargs["json"]
        self.assertEqual(payload["model"], "qwen-audio-3.1-asr-flash")
        self.assertEqual(payload["parameters"]["format"], "webm")
        data_uri = payload["input"]["messages"][0]["content"][0]["input_audio"]["data"]
        self.assertEqual(
            data_uri,
            "data:audio/webm;base64," + base64.b64encode(audio).decode("ascii"),
        )

    async def test_rejects_unsupported_audio_type(self) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)

        with (
            patch.object(
                settings,
                "dashscope_api_key",
                SecretStr("test-key"),
            ),
            self.assertRaises(UnsupportedAudioFormatError),
        ):
            await SpeechToTextService.transcribe(
                client,
                upload_file(b"audio", "application/octet-stream"),
            )

        client.post.assert_not_awaited()

    async def test_rejects_audio_above_application_limit(self) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)

        with (
            patch.object(
                settings,
                "dashscope_api_key",
                SecretStr("test-key"),
            ),
            patch.object(settings, "dashscope_asr_max_file_size_bytes", 3),
            self.assertRaises(AudioFileTooLargeError),
        ):
            await SpeechToTextService.transcribe(
                client,
                upload_file(b"four"),
            )

        client.post.assert_not_awaited()

    async def test_rejects_provider_response_without_text(self) -> None:
        request = httpx.Request("POST", "https://example.test/asr")
        response = httpx.Response(
            200,
            request=request,
            json={"output": {}, "request_id": "request-123"},
        )
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.return_value = response

        with (
            patch.object(
                settings,
                "dashscope_api_key",
                SecretStr("test-key"),
            ),
            self.assertRaises(SpeechRecognitionProviderError),
        ):
            await SpeechToTextService.transcribe(
                client,
                upload_file(b"audio"),
            )
