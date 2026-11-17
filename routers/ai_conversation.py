import logging
from collections.abc import Iterable
from math import ceil
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import DatabaseSession, session_factory
from core.llm import LLMConfigurationError
from dependencies.auth import CurrentUser
from enums.ai import AIMessageRole
from graphs.context import AgentContext
from models.ai_conversation import AIConversation
from models.role import Permission
from schemas.ai import AIChatRequest, AIChatResponse
from schemas.ai_conversation import (
    AIConversationCreate,
    AIConversationListResponse,
    AIConversationResponse,
    AIConversationUpdate,
    AIMessageListResponse,
    AIMessageResponse,
)
from services.ai import AIService
from services.ai_conversation import (
    AIConversationNotFoundError,
    AIConversationService,
)
from services.tts_session import speech_session_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai/conversations", tags=["ai-conversations"])


@router.post(
    "",
    response_model=AIConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    conversation_create: AIConversationCreate,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> AIConversationResponse:
    conversation = await AIConversationService.create(
        session,
        user_id=current_user.id,
        title=conversation_create.title,
    )
    return AIConversationResponse.model_validate(conversation)


@router.get("", response_model=AIConversationListResponse)
async def list_conversations(
    session: DatabaseSession,
    current_user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AIConversationListResponse:
    conversations, total = await AIConversationService.list(
        session,
        user_id=current_user.id,
        page=page,
        size=size,
    )
    return AIConversationListResponse(
        items=[
            AIConversationResponse.model_validate(conversation)
            for conversation in conversations
        ],
        page=page,
        size=size,
        total=total,
        pages=ceil(total / size),
    )


@router.get("/{conversation_id}", response_model=AIConversationResponse)
async def get_conversation(
    conversation_id: UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> AIConversationResponse:
    conversation = await _get_owned_conversation(
        session,
        conversation_id,
        current_user.id,
    )
    return AIConversationResponse.model_validate(conversation)


@router.patch("/{conversation_id}", response_model=AIConversationResponse)
async def update_conversation(
    conversation_id: UUID,
    conversation_update: AIConversationUpdate,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> AIConversationResponse:
    try:
        conversation = await AIConversationService.update_title(
            session,
            conversation_id=conversation_id,
            user_id=current_user.id,
            title=conversation_update.title,
        )
    except AIConversationNotFoundError as error:
        raise _not_found(error) from error
    return AIConversationResponse.model_validate(conversation)


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_conversation(
    conversation_id: UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> Response:
    try:
        await AIConversationService.delete(
            session,
            conversation_id=conversation_id,
            user_id=current_user.id,
        )
    except AIConversationNotFoundError as error:
        raise _not_found(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{conversation_id}/messages",
    response_model=AIMessageListResponse,
)
async def list_conversation_messages(
    conversation_id: UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AIMessageListResponse:
    try:
        messages, total = await AIConversationService.list_messages(
            session,
            conversation_id=conversation_id,
            user_id=current_user.id,
            page=page,
            size=size,
        )
    except AIConversationNotFoundError as error:
        raise _not_found(error) from error
    return AIMessageListResponse(
        items=[AIMessageResponse.from_message(message) for message in messages],
        page=page,
        size=size,
        total=total,
        pages=ceil(total / size),
    )


@router.post(
    "/{conversation_id}/chat",
    response_model=AIChatResponse,
)
async def chat_in_conversation(
    conversation_id: UUID,
    request: AIChatRequest,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> AIChatResponse:
    await _get_owned_conversation(session, conversation_id, current_user.id)
    request_id = request.request_id or uuid4()
    await AIConversationService.add_message(
        session,
        conversation_id=conversation_id,
        user_id=current_user.id,
        request_id=request_id,
        role=AIMessageRole.USER,
        content=request.prompt,
    )

    try:
        response = await AIService.chat(
            request.prompt,
            _agent_context(current_user.id, current_user.role.permissions),
        )
    except LLMConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    await AIConversationService.add_message(
        session,
        conversation_id=conversation_id,
        user_id=current_user.id,
        request_id=request_id,
        role=AIMessageRole.ASSISTANT,
        content=response.answer,
        metadata={
            "sources": [source.model_dump(mode="json") for source in response.sources]
        },
    )
    return response


@router.post(
    "/{conversation_id}/chat/stream",
    response_class=StreamingResponse,
)
async def stream_chat_in_conversation(
    conversation_id: UUID,
    request: AIChatRequest,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> StreamingResponse:
    await _get_owned_conversation(session, conversation_id, current_user.id)
    request_id = request.request_id or uuid4()
    await AIConversationService.add_message(
        session,
        conversation_id=conversation_id,
        user_id=current_user.id,
        request_id=request_id,
        role=AIMessageRole.USER,
        content=request.prompt,
    )

    speech_session = None
    if request.tts_enabled and request.request_id is not None:
        speech_session = await speech_session_manager.get(
            current_user.id,
            str(request.request_id),
        )

    async def persist_answer(
        answer: str,
        sources: list[dict[str, Any]],
    ) -> None:
        async with session_factory() as callback_session:
            try:
                await AIConversationService.add_message(
                    callback_session,
                    conversation_id=conversation_id,
                    user_id=current_user.id,
                    request_id=request_id,
                    role=AIMessageRole.ASSISTANT,
                    content=answer,
                    metadata={"sources": sources},
                )
            except AIConversationNotFoundError:
                logger.warning(
                    "Conversation was deleted before streamed answer persisted",
                    extra={"conversation_id": str(conversation_id)},
                )

    try:
        stream = AIService.stream_chat(
            request.prompt,
            _agent_context(current_user.id, current_user.role.permissions),
            speech_session,
            on_complete=persist_answer,
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


async def _get_owned_conversation(
    session: AsyncSession,
    conversation_id: UUID,
    user_id: int,
) -> AIConversation:
    try:
        return await AIConversationService.get_owned(
            session,
            conversation_id=conversation_id,
            user_id=user_id,
        )
    except AIConversationNotFoundError as error:
        raise _not_found(error) from error


def _not_found(error: AIConversationNotFoundError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=str(error),
    )


def _agent_context(
    user_id: int,
    permissions: Iterable[Permission],
) -> AgentContext:
    return AgentContext(
        user_id=user_id,
        permission_codes=frozenset(permission.code for permission in permissions),
    )
