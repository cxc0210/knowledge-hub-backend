from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from enums.document import DocumentStatus
from enums.document_index import DocumentIndexJobStatus
from models.document import Document
from models.document_index_job import DocumentIndexJob
from models.user import User


class DocumentIndexNotAllowedError(Exception):
    pass


class DocumentIndexAlreadyRunningError(Exception):
    pass


class DocumentIndexJobService:
    @staticmethod
    async def enqueue(
        session: AsyncSession,
        document: Document,
        current_user: User,
    ) -> DocumentIndexJob:
        # 串行化同一文档的发布请求，避免并发创建多个索引任务。
        await session.refresh(document, with_for_update=True)

        if document.author_id != current_user.id:
            raise DocumentIndexNotAllowedError(
                "you cannot publish another user's document",
            )
        if document.content_id is None:
            raise DocumentIndexNotAllowedError(
                "document content is not available",
            )
        if document.status not in {
            DocumentStatus.DRAFT,
            DocumentStatus.INDEX_FAILED,
        }:
            raise DocumentIndexNotAllowedError(
                f"document status '{document.status}' cannot be published",
            )

        running_job = await session.scalar(
            select(DocumentIndexJob.id).where(
                DocumentIndexJob.document_id == document.id,
                DocumentIndexJob.status.in_(
                    [
                        DocumentIndexJobStatus.PENDING,
                        DocumentIndexJobStatus.PROCESSING,
                    ],
                ),
            ),
        )
        if running_job is not None:
            raise DocumentIndexAlreadyRunningError(
                f"document '{document.id}' is already being indexed",
            )

        document.status = DocumentStatus.INDEXING
        document.update_by = current_user.id
        job = DocumentIndexJob(
            document_id=document.id,
            status=DocumentIndexJobStatus.PENDING,
        )
        session.add(job)
        await session.commit()
        await session.refresh(document)
        await session.refresh(job)
        return job
