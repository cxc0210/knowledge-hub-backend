from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from enums.role import RoleCode
from models.document import Document
from models.user import User
from schemas.document import DocumentCreate


class DocumentAlreadyExistsError(Exception):
    pass


class DocumentNotFoundError(Exception):
    pass


class DocumentForbiddenError(Exception):
    pass


class DocumentService:
    @staticmethod
    async def create(
        session: AsyncSession,
        document_create: DocumentCreate,
        current_user: User,
    ) -> Document:
        document = Document(
            **document_create.model_dump(exclude_unset=True),
            author_id=current_user.id,
            create_by=current_user.id,
        )
        session.add(document)

        try:
            await session.commit()
        except IntegrityError as error:
            await session.rollback()
            raise DocumentAlreadyExistsError(
                f"content_id '{document_create.content_id}' already exists",
            ) from error

        await session.refresh(document)
        return document

    @staticmethod
    async def delete(
        session: AsyncSession,
        document_id: int,
        current_user: User,
    ) -> None:
        result = await session.execute(
            select(Document).where(
                Document.id == document_id,
                Document.deleted.is_(False),
            ),
        )
        document = result.scalar_one_or_none()

        if document is None:
            raise DocumentNotFoundError(
                f"document '{document_id}' does not exist",
            )

        if (
            current_user.role.code != RoleCode.ADMIN
            and document.author_id != current_user.id
        ):
            raise DocumentForbiddenError(
                "you cannot delete another user's document",
            )

        document.deleted = True
        document.update_by = current_user.id
        await session.commit()
