from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from core.dashscope import DashScopeClient
from dependencies.auth import CurrentUser
from schemas.speech import SpeechTranscriptionResponse
from services.speech_to_text import (
    AudioFileTooLargeError,
    EmptyAudioFileError,
    SpeechRecognitionConfigurationError,
    SpeechRecognitionProviderError,
    SpeechRecognitionTimeoutError,
    SpeechToTextService,
    UnsupportedAudioFormatError,
)

router = APIRouter(prefix="/speech", tags=["speech"])


@router.post(
    "/transcriptions",
    response_model=SpeechTranscriptionResponse,
)
async def transcribe_audio(
    file: Annotated[UploadFile, File(description="Audio to transcribe")],
    client: DashScopeClient,
    current_user: CurrentUser,
) -> SpeechTranscriptionResponse:
    try:
        return await SpeechToTextService.transcribe(client, file)
    except EmptyAudioFileError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except AudioFileTooLargeError as error:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(error),
        ) from error
    except UnsupportedAudioFormatError as error:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(error),
        ) from error
    except SpeechRecognitionConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except SpeechRecognitionTimeoutError as error:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(error),
        ) from error
    except SpeechRecognitionProviderError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error
