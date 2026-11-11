from fastapi import APIRouter, HTTPException, Response, status

from database import DatabaseSession
from schemas.document import DocumentCreate, DocumentResponse
from services.document import (
    DocumentAlreadyExistsError,
    DocumentNotFoundError,
    DocumentService,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_document(
    document_create: DocumentCreate,
    session: DatabaseSession,
) -> DocumentResponse:
    try:
        document = await DocumentService.create(session, document_create)
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
) -> Response:
    try:
        await DocumentService.delete(session, document_id)
    except DocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)
