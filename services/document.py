from pathlib import PurePath
from uuid import uuid4

from botocore.exceptions import ClientError
from elasticsearch import AsyncElasticsearch
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from types_aiobotocore_s3.client import S3Client

from core.config import settings
from enums.document import DocumentStatus
from enums.role import RoleCode
from models.document import Document
from models.user import User
from repositories.document_chunk import DocumentChunkRepository
from repositories.document_search import DocumentSearchRepository
from schemas.document import DocumentUploadCreate


class DocumentNotFoundError(Exception):
    pass


class DocumentObjectNotFoundError(Exception):
    pass


class DocumentFileSizeMismatchError(Exception):
    pass


class DocumentForbiddenError(Exception):
    pass


class DocumentContentUnavailableError(Exception):
    pass


class DocumentService:
    @staticmethod
    async def _get_active(
        session: AsyncSession,
        document_id: int,
        *,
        for_update: bool = False,
    ) -> Document:
        statement = select(Document).where(
            Document.id == document_id,
            Document.deleted.is_(False),
        )
        if for_update:
            statement = statement.with_for_update()
        document = await session.scalar(statement)
        if document is None:
            raise DocumentNotFoundError(
                f"document '{document_id}' does not exist",
            )
        return document

    @staticmethod
    async def create_upload(
        session: AsyncSession,
        rustfs: S3Client,
        document_create: DocumentUploadCreate,
        current_user: User,
    ) -> tuple[Document, str]:
        file_name = document_create.file_name
        suffix = PurePath(file_name).suffix.lower()
        object_key = f"documents/{current_user.id}/{uuid4().hex}{suffix}"

        document = Document(
            title=document_create.title,
            content_id=None,
            object_key=object_key,
            file_name=file_name,
            content_type=document_create.content_type,
            file_size=document_create.file_size,
            summary=document_create.summary,
            category_id=document_create.category_id,
            team_id=document_create.team_id,
            cover_image=document_create.cover_image,
            tags=document_create.tags,
            remark=document_create.remark,
            status=DocumentStatus.PENDING_UPLOAD,
            author_id=current_user.id,
            create_by=current_user.id,
        )
        upload_url = await rustfs.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.rustfs_bucket,
                "Key": object_key,
                "ContentType": document.content_type,
            },
            ExpiresIn=settings.rustfs_presigned_url_expire_seconds,
        )

        session.add(document)
        await session.commit()
        await session.refresh(document)
        return document, upload_url

    @staticmethod
    async def list(
        session: AsyncSession,
        current_user: User,
        page: int,
        size: int,
    ) -> tuple[list[Document], int]:
        filters = (
            Document.author_id == current_user.id,
            Document.deleted.is_(False),
        )
        total = await session.scalar(
            select(func.count(Document.id)).where(*filters),
        )
        result = await session.scalars(
            select(Document)
            .where(*filters)
            .order_by(Document.created_at.desc(), Document.id.desc())
            .offset((page - 1) * size)
            .limit(size),
        )
        return list(result.all()), total or 0

    @classmethod
    async def get(
        cls,
        session: AsyncSession,
        document_id: int,
    ) -> Document:
        return await cls._get_active(session, document_id)

    @classmethod
    async def get_detail(
        cls,
        session: AsyncSession,
        document_id: int,
        current_user: User,
    ) -> Document:
        document = await cls._get_active(session, document_id)

        can_view_published_document = (
            document.status == DocumentStatus.PUBLISHED and document.is_public
        )
        if document.author_id != current_user.id and not can_view_published_document:
            raise DocumentForbiddenError(
                "you cannot view another user's document",
            )

        if document.status < DocumentStatus.DRAFT or document.content_id is None:
            raise DocumentContentUnavailableError(
                f"document '{document_id}' content is not available",
            )

        return document

    @classmethod
    async def complete_upload(
        cls,
        session: AsyncSession,
        rustfs: S3Client,
        document_id: int,
        current_user: User,
    ) -> Document:
        document = await cls._get_active(session, document_id)

        try:
            object_metadata = await rustfs.head_object(
                Bucket=settings.rustfs_bucket,
                Key=document.object_key,
            )
        except ClientError as error:
            error_code = str(error.response.get("Error", {}).get("Code", ""))
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                raise DocumentObjectNotFoundError(
                    f"uploaded file for document '{document_id}' does not exist",
                ) from error
            raise

        actual_file_size = int(object_metadata["ContentLength"])
        if actual_file_size != document.file_size:
            raise DocumentFileSizeMismatchError(
                f"expected {document.file_size} bytes, got {actual_file_size} bytes",
            )

        document.status = DocumentStatus.UPLOADED
        document.etag = str(object_metadata.get("ETag", "")).strip('"') or None
        document.update_by = current_user.id
        await session.commit()
        await session.refresh(document)
        return document

    @classmethod
    async def delete(
        cls,
        session: AsyncSession,
        rustfs: S3Client,
        elasticsearch: AsyncElasticsearch,
        document_id: int,
        current_user: User,
    ) -> None:
        document = await cls._get_active(
            session,
            document_id,
            for_update=True,
        )

        if (
            current_user.role.code != RoleCode.ADMIN
            and document.author_id != current_user.id
        ):
            raise DocumentForbiddenError(
                "you cannot delete another user's document",
            )

        await rustfs.delete_object(
            Bucket=settings.rustfs_bucket,
            Key=document.object_key,
        )
        await DocumentChunkRepository.delete(session, document.id)
        await DocumentSearchRepository.delete(elasticsearch, document.id)
        document.deleted = True
        document.update_by = current_user.id
        await session.commit()
