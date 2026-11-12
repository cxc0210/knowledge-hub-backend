from fastapi import APIRouter, HTTPException, status

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
