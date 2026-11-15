from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from core.database import DatabaseSession
from dependencies.permission import require_permission
from enums.permission import PermissionCode
from models.user import User
from schemas.ai_action import EmailActionResponse
from services.ai_action import (
    AIActionExpiredError,
    AIActionInvalidStateError,
    AIActionNotFoundError,
    AIActionService,
)

router = APIRouter(prefix="/ai/actions", tags=["ai-actions"])
EmailSender = Annotated[
    User,
    Depends(require_permission(PermissionCode.AI_EMAIL_SEND)),
]


@router.post(
    "/{action_id}/approve",
    response_model=EmailActionResponse,
)
async def approve_email_action(
    action_id: UUID,
    session: DatabaseSession,
    current_user: EmailSender,
) -> EmailActionResponse:
    try:
        action = await AIActionService.approve_email_send(
            session,
            action_id=action_id,
            user_id=current_user.id,
        )
    except AIActionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except (AIActionInvalidStateError, AIActionExpiredError) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    return EmailActionResponse.from_action(action)


@router.post(
    "/{action_id}/reject",
    response_model=EmailActionResponse,
)
async def reject_email_action(
    action_id: UUID,
    session: DatabaseSession,
    current_user: EmailSender,
) -> EmailActionResponse:
    try:
        action = await AIActionService.reject_email_send(
            session,
            action_id=action_id,
            user_id=current_user.id,
        )
    except AIActionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except (AIActionInvalidStateError, AIActionExpiredError) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return EmailActionResponse.from_action(action)
