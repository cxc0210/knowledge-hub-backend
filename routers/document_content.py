from fastapi import APIRouter, Depends, HTTPException, Response, status

from core.mongodb import MongoDatabase
from dependencies.permission import require_permission
from enums.permission import PermissionCode
from schemas.document_content import (
    DocumentContentCreate,
    DocumentContentResponse,
)
from services.document_content import (
    DocumentContentNotFoundError,
    DocumentContentService,
    InvalidDocumentContentIdError,
)

router = APIRouter(
    prefix="/document-contents",
    tags=["document-contents"],
    dependencies=[
        Depends(require_permission(PermissionCode.DOCUMENT_MANAGE)),
    ],
)


@router.post(
    "",
    response_model=DocumentContentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_document_content(
    document_create: DocumentContentCreate,
    database: MongoDatabase,
) -> DocumentContentResponse:
    return await DocumentContentService.create(database, document_create)


@router.get(
    "/{content_id}",
    response_model=DocumentContentResponse,
)
async def get_document_content(
    content_id: str,
    database: MongoDatabase,
) -> DocumentContentResponse:
    try:
        return await DocumentContentService.get(database, content_id)
    except InvalidDocumentContentIdError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except DocumentContentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error


@router.delete(
    "/{content_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document_content(
    content_id: str,
    database: MongoDatabase,
) -> Response:
    try:
        await DocumentContentService.delete(database, content_id)
    except InvalidDocumentContentIdError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except DocumentContentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)
