from math import ceil
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from core.config import settings
from core.database import DatabaseSession
from core.elasticsearch import ElasticsearchClient
from core.mongodb import MongoDatabase
from core.rustfs import RustFSClient
from dependencies.auth import CurrentUser
from dependencies.permission import require_permission
from enums.permission import PermissionCode
from models.user import User
from schemas.document import (
    DocumentAuthorResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadCreate,
    DocumentUploadResponse,
)
from schemas.document_index import (
    DocumentIndexJobResponse,
    DocumentPublishResponse,
)
from services.document import (
    DocumentContentUnavailableError,
    DocumentFileSizeMismatchError,
    DocumentForbiddenError,
    DocumentNotFoundError,
    DocumentObjectNotFoundError,
    DocumentService,
)
from services.document_content import (
    DocumentContentNotFoundError,
    DocumentContentService,
    InvalidDocumentContentIdError,
)
from services.document_index_job import (
    DocumentIndexAlreadyRunningError,
    DocumentIndexJobService,
    DocumentIndexNotAllowedError,
)
from services.document_index_worker import DocumentIndexWorkerDependency

router = APIRouter(prefix="/documents", tags=["documents"])
DocumentManager = Annotated[
    User,
    Depends(require_permission(PermissionCode.DOCUMENT_MANAGE)),
]


@router.post(
    "/uploads",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_document_upload(
    document_create: DocumentUploadCreate,
    session: DatabaseSession,
    rustfs: RustFSClient,
    current_user: DocumentManager,
) -> DocumentUploadResponse:
    document, upload_url = await DocumentService.create_upload(
        session,
        rustfs,
        document_create,
        current_user,
    )
    return DocumentUploadResponse(
        document=DocumentResponse.model_validate(document),
        upload_url=upload_url,
        headers={"Content-Type": document.content_type},
        expires_in=settings.rustfs_presigned_url_expire_seconds,
    )


@router.post(
    "/{document_id}/upload-complete",
    response_model=DocumentResponse,
)
async def complete_document_upload(
    document_id: int,
    session: DatabaseSession,
    rustfs: RustFSClient,
    current_user: DocumentManager,
) -> DocumentResponse:
    try:
        document = await DocumentService.complete_upload(
            session,
            rustfs,
            document_id,
            current_user,
        )
    except DocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except (DocumentObjectNotFoundError, DocumentFileSizeMismatchError) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return DocumentResponse.model_validate(document)


@router.post(
    "/{document_id}/publish",
    response_model=DocumentPublishResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def publish_document(
    document_id: int,
    session: DatabaseSession,
    worker: DocumentIndexWorkerDependency,
    current_user: DocumentManager,
) -> DocumentPublishResponse:
    try:
        document = await DocumentService.get(session, document_id)
        index_job = await DocumentIndexJobService.enqueue(
            session,
            document,
            current_user,
        )
    except DocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except DocumentIndexNotAllowedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except DocumentIndexAlreadyRunningError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    worker.notify()
    return DocumentPublishResponse(
        document=DocumentResponse.model_validate(document),
        index_job=DocumentIndexJobResponse.model_validate(index_job),
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    session: DatabaseSession,
    current_user: DocumentManager,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 10,
) -> DocumentListResponse:
    documents, total = await DocumentService.list(
        session,
        current_user,
        page,
        size,
    )
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(item) for item in documents],
        page=page,
        size=size,
        total=total,
        pages=ceil(total / size),
    )


@router.get(
    "/{document_id}/detail",
    response_model=DocumentDetailResponse,
)
async def get_document_detail(
    document_id: int,
    session: DatabaseSession,
    database: MongoDatabase,
    current_user: CurrentUser,
) -> DocumentDetailResponse:
    try:
        document = await DocumentService.get_detail(
            session,
            document_id,
            current_user,
        )
        assert document.content_id is not None
        content = await DocumentContentService.get(
            database,
            document.content_id,
        )
        author = current_user
        if document.author_id != current_user.id:
            author = (
                await session.get(User, document.author_id)
                if document.author_id is not None
                else None
            )
            if author is None:
                raise DocumentContentUnavailableError(
                    f"document '{document_id}' author is not available",
                )
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
    except DocumentContentUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except (InvalidDocumentContentIdError, DocumentContentNotFoundError) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="document content is unavailable",
        ) from error

    return DocumentDetailResponse(
        document=DocumentResponse.model_validate(document),
        author=DocumentAuthorResponse.model_validate(author),
        markdown=content.content,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    session: DatabaseSession,
    current_user: DocumentManager,
) -> DocumentResponse:
    try:
        document = await DocumentService.get(session, document_id)
    except DocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
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
    rustfs: RustFSClient,
    elasticsearch: ElasticsearchClient,
    current_user: DocumentManager,
) -> Response:
    try:
        await DocumentService.delete(
            session,
            rustfs,
            elasticsearch,
            document_id,
            current_user,
        )
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
