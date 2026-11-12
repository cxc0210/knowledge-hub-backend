from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from sqlalchemy.ext.asyncio import AsyncSession

from enums.document import DocumentStatus
from services.document import (
    DocumentContentUnavailableError,
    DocumentForbiddenError,
    DocumentService,
)


class DocumentServiceTests(IsolatedAsyncioTestCase):
    async def test_gets_available_detail_for_document_owner(self) -> None:
        session = AsyncMock(spec=AsyncSession)
        current_user = SimpleNamespace(id=1001)
        document = SimpleNamespace(
            author_id=1001,
            content_id="6912abcdef1234567890abcd",
            status=DocumentStatus.DRAFT,
            is_public=False,
        )
        session.scalar.return_value = document

        result = await DocumentService.get_detail(
            session,
            document_id=100001,
            current_user=current_user,  # type: ignore[arg-type]
        )

        self.assertIs(result, document)

    async def test_rejects_detail_for_another_user(self) -> None:
        session = AsyncMock(spec=AsyncSession)
        current_user = SimpleNamespace(id=1002)
        document = SimpleNamespace(
            author_id=1001,
            content_id="6912abcdef1234567890abcd",
            status=DocumentStatus.DRAFT,
            is_public=False,
        )
        session.scalar.return_value = document

        with self.assertRaises(DocumentForbiddenError):
            await DocumentService.get_detail(
                session,
                document_id=100001,
                current_user=current_user,  # type: ignore[arg-type]
            )

    async def test_rejects_detail_before_draft_status(self) -> None:
        session = AsyncMock(spec=AsyncSession)
        current_user = SimpleNamespace(id=1001)
        document = SimpleNamespace(
            author_id=1001,
            content_id=None,
            status=DocumentStatus.PARSING,
            is_public=False,
        )
        session.scalar.return_value = document

        with self.assertRaises(DocumentContentUnavailableError):
            await DocumentService.get_detail(
                session,
                document_id=100001,
                current_user=current_user,  # type: ignore[arg-type]
            )

    async def test_allows_published_public_document_for_another_user(self) -> None:
        session = AsyncMock(spec=AsyncSession)
        current_user = SimpleNamespace(id=1002)
        document = SimpleNamespace(
            author_id=1001,
            content_id="6912abcdef1234567890abcd",
            status=DocumentStatus.PUBLISHED,
            is_public=True,
        )
        session.scalar.return_value = document

        result = await DocumentService.get_detail(
            session,
            document_id=100001,
            current_user=current_user,  # type: ignore[arg-type]
        )

        self.assertIs(result, document)
