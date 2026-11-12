from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from sqlalchemy.ext.asyncio import AsyncSession

from enums.document import DocumentStatus
from services.document_index_job import (
    DocumentIndexJobService,
    DocumentIndexNotAllowedError,
)


class DocumentIndexJobServiceTests(IsolatedAsyncioTestCase):
    async def test_enqueues_draft_document_and_sets_indexing(self) -> None:
        session = AsyncMock(spec=AsyncSession)
        session.scalar.return_value = None
        document = SimpleNamespace(
            id=100001,
            author_id=1001,
            content_id="6912abcdef1234567890abcd",
            status=DocumentStatus.DRAFT,
            update_by=None,
        )
        user = SimpleNamespace(id=1001)

        job = await DocumentIndexJobService.enqueue(
            session,
            document,  # type: ignore[arg-type]
            user,  # type: ignore[arg-type]
        )

        self.assertEqual(document.status, DocumentStatus.INDEXING)
        self.assertEqual(document.update_by, 1001)
        self.assertEqual(job.document_id, 100001)
        session.commit.assert_awaited_once()

    async def test_rejects_document_without_content(self) -> None:
        session = AsyncMock(spec=AsyncSession)
        document = SimpleNamespace(
            id=100001,
            author_id=1001,
            content_id=None,
            status=DocumentStatus.DRAFT,
        )
        user = SimpleNamespace(id=1001)

        with self.assertRaises(DocumentIndexNotAllowedError):
            await DocumentIndexJobService.enqueue(
                session,
                document,  # type: ignore[arg-type]
                user,  # type: ignore[arg-type]
            )
