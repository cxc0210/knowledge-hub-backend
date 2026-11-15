import base64
import logging
from typing import Any

import httpx
from fastapi import UploadFile

from core.config import settings
from schemas.speech import SpeechTranscriptionResponse

logger = logging.getLogger(__name__)

GENERATION_PATH = "/services/aigc/multimodal-generation/generation"

AUDIO_FORMATS = {
    "audio/aac": "aac",
    "audio/amr": "amr",
    "audio/flac": "flac",
    "audio/m4a": "m4a",
    "audio/mp4": "mp4",
    "audio/mpeg": "mp3",
    "audio/ogg": "ogg",
    "audio/opus": "opus",
    "audio/wav": "wav",
    "audio/webm": "webm",
    "audio/x-m4a": "m4a",
    "audio/x-wav": "wav",
}


class SpeechRecognitionError(Exception):
    pass


class SpeechRecognitionConfigurationError(SpeechRecognitionError):
    pass


class EmptyAudioFileError(SpeechRecognitionError):
    pass


class AudioFileTooLargeError(SpeechRecognitionError):
    pass


class UnsupportedAudioFormatError(SpeechRecognitionError):
    pass


class SpeechRecognitionProviderError(SpeechRecognitionError):
    pass


class SpeechRecognitionTimeoutError(SpeechRecognitionProviderError):
    pass


class SpeechToTextService:
    @staticmethod
    def _audio_format(content_type: str | None) -> tuple[str, str]:
        normalized_type = (content_type or "").split(";", 1)[0].strip().lower()
        audio_format = AUDIO_FORMATS.get(normalized_type)
        if audio_format is None:
            raise UnsupportedAudioFormatError(
                f"audio type '{normalized_type or 'unknown'}' is not supported",
            )
        return normalized_type, audio_format

    @staticmethod
    def _response(payload: Any) -> SpeechTranscriptionResponse:
        if not isinstance(payload, dict):
            raise SpeechRecognitionProviderError(
                "speech recognition returned an invalid response",
            )

        output = payload.get("output")
        if not isinstance(output, dict):
            raise SpeechRecognitionProviderError(
                "speech recognition response has no output",
            )

        text = output.get("text")
        if not isinstance(text, str) or not text.strip():
            raise SpeechRecognitionProviderError(
                "speech recognition returned no text",
            )

        usage = payload.get("usage")
        duration_seconds: float | None = None
        if isinstance(usage, dict):
            duration = usage.get("duration")
            if isinstance(duration, int | float) and not isinstance(
                duration,
                bool,
            ):
                duration_seconds = float(duration)

        request_id = payload.get("request_id")
        return SpeechTranscriptionResponse(
            text=text.strip(),
            duration_seconds=duration_seconds,
            request_id=request_id if isinstance(request_id, str) else None,
        )

    @classmethod
    async def transcribe(
        cls,
        client: httpx.AsyncClient,
        file: UploadFile,
    ) -> SpeechTranscriptionResponse:
        api_key = settings.dashscope_api_key.get_secret_value().strip()
        if not api_key:
            raise SpeechRecognitionConfigurationError(
                "DASHSCOPE_API_KEY is not configured",
            )

        media_type, audio_format = cls._audio_format(file.content_type)
        max_size = settings.dashscope_asr_max_file_size_bytes
        audio = await file.read(max_size + 1)
        if not audio:
            raise EmptyAudioFileError("audio file is empty")
        if len(audio) > max_size:
            raise AudioFileTooLargeError(
                f"audio file exceeds the {max_size}-byte limit",
            )

        encoded_audio = base64.b64encode(audio).decode("ascii")
        data_uri = f"data:{media_type};base64,{encoded_audio}"
        payload = {
            "model": settings.dashscope_asr_model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_audio",
                                "input_audio": {"data": data_uri},
                            },
                        ],
                    },
                ],
            },
            "parameters": {
                "format": audio_format,
                "language_hints": ["zh"],
                "keep_dialect": False,
                "speaker_diarization_enabled": False,
            },
        }

        try:
            response = await client.post(
                GENERATION_PATH,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "X-DashScope-SSE": "disable",
                },
                json=payload,
            )
            response.raise_for_status()
        except httpx.TimeoutException as error:
            raise SpeechRecognitionTimeoutError(
                "speech recognition request timed out",
            ) from error
        except httpx.HTTPStatusError as error:
            logger.warning(
                "DashScope ASR request failed, status=%d",
                error.response.status_code,
            )
            raise SpeechRecognitionProviderError(
                "speech recognition provider rejected the request",
            ) from error
        except httpx.RequestError as error:
            raise SpeechRecognitionProviderError(
                "speech recognition provider is unavailable",
            ) from error

        try:
            response_payload = response.json()
        except ValueError as error:
            raise SpeechRecognitionProviderError(
                "speech recognition returned invalid JSON",
            ) from error
        return cls._response(response_payload)
