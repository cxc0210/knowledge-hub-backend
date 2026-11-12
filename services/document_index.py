from datetime import UTC, datetime

import httpx
from elasticsearch import AsyncElasticsearch
from pymongo.asynchronous.database import AsyncDatabase
from sqlalchemy import select

from core.database import session_factory
from core.mongodb import MongoDocument
from enums.document import DocumentStatus
from enums.document_index import DocumentIndexJobStatus
from models.document import Document
from models.document_index_job import DocumentIndexJob
from repositories.document_chunk import DocumentChunkRepository
from repositories.document_search import DocumentSearchRepository
from services.document_content import DocumentContentService
from services.embedding import EmbeddingService
from services.markdown_chunker import MarkdownChunker


class DocumentIndexSourceUnavailableError(RuntimeError):
    pass


class DocumentIndexService:
    @classmethod
    async def process(
        cls,
        job_id: int,
        mongo_database: AsyncDatabase[MongoDocument],
        elasticsearch: AsyncElasticsearch,
        embedding_client: httpx.AsyncClient,
    ) -> None:
        async with session_factory() as session:
            job = await session.get(DocumentIndexJob, job_id)
            if job is None:
                raise DocumentIndexSourceUnavailableError(
                    f"index job '{job_id}' does not exist",
                )
            if job.status != DocumentIndexJobStatus.PROCESSING:
                raise DocumentIndexSourceUnavailableError(
                    f"index job '{job_id}' is not processing",
                )
            document = await session.scalar(
                select(Document).where(
                    Document.id == job.document_id,
                    Document.deleted.is_(False),
                ),
            )
            if (
                document is None
                or document.content_id is None
                or document.status != DocumentStatus.INDEXING
            ):
                raise DocumentIndexSourceUnavailableError(
                    f"document for index job '{job_id}' is unavailable",
                )

        content = await DocumentContentService.get(
            mongo_database,
            document.content_id,
        )
        chunks = MarkdownChunker().split(
            document_id=document.id,
            title=document.title,
            markdown=content.content,
        )
        embeddings = await EmbeddingService.embed_documents(
            embedding_client,
            [chunk.embedding_content for chunk in chunks],
        )

        async with session_factory() as session, session.begin():
            await DocumentChunkRepository.replace(
                session,
                document.id,
                chunks,
                embeddings,
            )

        publish_time = datetime.now(UTC)
        await DocumentSearchRepository.replace(
            elasticsearch,
            document,
            chunks,
            DocumentStatus.PUBLISHED,
            publish_time,
        )

        source_disappeared = False
        async with session_factory() as session, session.begin():
            current_document = await session.scalar(
                select(Document)
                .where(
                    Document.id == document.id,
                    Document.deleted.is_(False),
                )
                .with_for_update(),
            )
            current_job = await session.get(
                DocumentIndexJob,
                job_id,
                with_for_update=True,
            )
            if current_document is None or current_job is None:
                source_disappeared = True
            else:
                current_document.status = DocumentStatus.PUBLISHED
                current_document.publish_time = publish_time
                current_document.word_count = len(
                    "".join(content.content.split()),
                )
                current_job.status = DocumentIndexJobStatus.SUCCESS
                current_job.error_message = None
                current_job.finished_at = publish_time

        if source_disappeared:
            async with session_factory() as session, session.begin():
                await DocumentChunkRepository.delete(session, document.id)
            await DocumentSearchRepository.delete(elasticsearch, document.id)
            raise DocumentIndexSourceUnavailableError(
                f"document for index job '{job_id}' disappeared",
            )
