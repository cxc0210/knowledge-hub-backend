from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from core.llm import LLMConfigurationError
from dependencies.auth import CurrentUser
from schemas.ai import AIChatRequest, AIChatResponse
from services.ai import AIService

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat", response_model=AIChatResponse)
async def chat(
    request: AIChatRequest,
    current_user: CurrentUser,
) -> AIChatResponse:
    try:
        return await AIService.chat(request.prompt)
    except LLMConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error


@router.post("/chat/stream", response_class=StreamingResponse)
async def stream_chat(
    request: AIChatRequest,
    current_user: CurrentUser,
) -> StreamingResponse:
    try:
        stream = AIService.stream_chat(request.prompt)
    except LLMConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "X-Vercel-AI-UI-Message-Stream": "v1",
        },
    )
