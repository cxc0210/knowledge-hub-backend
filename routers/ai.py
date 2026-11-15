from uuid import UUID

from fastapi import (
    APIRouter,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from core.config import settings
from core.database import session_factory
from core.llm import LLMConfigurationError
from core.security import InvalidAccessTokenError, decode_access_token
from dependencies.auth import CurrentUser
from enums.user import UserStatus
from graphs.context import AgentContext
from models.user import User
from schemas.ai import AIChatRequest, AIChatResponse
from services.ai import AIService
from services.tts_session import (
    SpeechStreamSession,
    speech_session_manager,
)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat", response_model=AIChatResponse)
async def chat(
    request: AIChatRequest,
    current_user: CurrentUser,
) -> AIChatResponse:
    try:
        return await AIService.chat(
            request.prompt,
            _agent_context(current_user),
        )
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
    speech_session = None
    if request.tts_enabled and request.request_id is not None:
        speech_session = await speech_session_manager.get(
            current_user.id,
            str(request.request_id),
        )

    try:
        stream = AIService.stream_chat(
            request.prompt,
            _agent_context(current_user),
            speech_session,
        )
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


@router.websocket("/speech/{request_id}")
async def stream_speech(websocket: WebSocket, request_id: UUID) -> None:
    if not _websocket_origin_allowed(websocket):
        await websocket.close(code=4403, reason="origin is not allowed")
        return

    user_id = await _authenticate_websocket(websocket)
    if user_id is None:
        await websocket.close(code=4401, reason="not authenticated")
        return

    await websocket.accept()
    session = SpeechStreamSession(
        websocket,
        user_id=user_id,
        request_id=str(request_id),
    )
    await speech_session_manager.register(session)

    try:
        await session.send_ready()
        while True:
            message = await websocket.receive_json()
            if isinstance(message, dict) and message.get("type") == "stop":
                await session.stop()
    except RuntimeError, WebSocketDisconnect:
        pass
    finally:
        await speech_session_manager.unregister(session)
        await session.disconnect()


def _websocket_origin_allowed(websocket: WebSocket) -> bool:
    allowed_origins = set(settings.cors_origins)
    origin = websocket.headers.get("origin")
    return not allowed_origins or origin is None or origin in allowed_origins


def _agent_context(current_user: User) -> AgentContext:
    return AgentContext(
        user_id=current_user.id,
        permission_codes=frozenset(
            permission.code for permission in current_user.role.permissions
        ),
    )


async def _authenticate_websocket(websocket: WebSocket) -> int | None:
    token = websocket.cookies.get(settings.auth_cookie_name)
    if token is None:
        return None

    try:
        user_id, token_version = decode_access_token(token)
    except InvalidAccessTokenError:
        return None

    async with session_factory() as database_session:
        user = await database_session.scalar(
            select(User).where(
                User.id == user_id,
                User.deleted.is_(False),
            )
        )

    if (
        user is None
        or user.token_version != token_version
        or user.status == UserStatus.DISABLED
    ):
        return None
    return user.id
