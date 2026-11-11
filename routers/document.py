from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from database import DatabaseSession
from dependencies.permission import require_permission
from enums.permission import PermissionCode
from models.user import User
from schemas.document import DocumentCreate, DocumentResponse
from services.document import (
    DocumentAlreadyExistsError,
    DocumentForbiddenError,
    DocumentNotFoundError,
    DocumentService,
)

router = APIRouter(prefix="/documents", tags=["documents"])
DocumentManager = Annotated[
    User,
    Depends(require_permission(PermissionCode.DOCUMENT_MANAGE)),
]


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_document(
    document_create: DocumentCreate,
    session: DatabaseSession,
    current_user: DocumentManager,
) -> DocumentResponse:
    try:
        document = await DocumentService.create(
            session,
            document_create,
            current_user,
        )
    except DocumentAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return DocumentResponse.model_validate(document)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    document_id: int,
    session: DatabaseSession,
    current_user: DocumentManager,
) -> Response:
    try:
        await DocumentService.delete(session, document_id, current_user)
    except DocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except DocumentForbiddenError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)
