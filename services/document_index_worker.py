import asyncio
import logging
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Annotated

import httpx
from elasticsearch import AsyncElasticsearch
from fastapi import Depends, FastAPI, Request
from pymongo.asynchronous.database import AsyncDatabase
from sqlalchemy import select, update

from core.config import settings
from core.database import session_factory
from core.mongodb import MongoDocument
from enums.document import DocumentStatus
from enums.document_index import DocumentIndexJobStatus
from models.document import Document
from models.document_index_job import DocumentIndexJob
from services.document_index import DocumentIndexService

logger = logging.getLogger(__name__)


class DocumentIndexWorker:
    def __init__(
        self,
        mongo_database: AsyncDatabase[MongoDocument],
        elasticsearch: AsyncElasticsearch,
        embedding_client: httpx.AsyncClient,
    ) -> None:
        self.mongo_database = mongo_database
        self.elasticsearch = elasticsearch
        self.embedding_client = embedding_client
        self._wake_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        await self._recover_stale_jobs()
        self._task = asyncio.create_task(
            self._run(),
            name="document-index-worker",
        )
        logger.info("Document index worker started")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        logger.info("Document index worker stopped")

    def notify(self) -> None:
        self._wake_event.set()

    async def _run(self) -> None:
        event_loop = asyncio.get_running_loop()
        last_recovery = event_loop.time()

        while True:
            if (
                event_loop.time() - last_recovery
                >= settings.document_index_recovery_interval_seconds
            ):
                await self._recover_stale_jobs()
                last_recovery = event_loop.time()

            job_id = await self._claim_next_job()
            if job_id is None:
                self._wake_event.clear()
                try:
                    await asyncio.wait_for(
                        self._wake_event.wait(),
                        timeout=settings.document_index_worker_poll_seconds,
                    )
                except TimeoutError:
                    pass
                continue

            try:
                await DocumentIndexService.process(
                    job_id,
                    self.mongo_database,
                    self.elasticsearch,
                    self.embedding_client,
                )
                logger.info("Document index job succeeded, job_id=%d", job_id)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logger.exception(
                    "Document index job failed, job_id=%d",
                    job_id,
                )
                await self._mark_failed(job_id, error)

    async def _claim_next_job(self) -> int | None:
        async with session_factory() as session:
            async with session.begin():
                job = await session.scalar(
                    select(DocumentIndexJob)
                    .where(
                        DocumentIndexJob.status == DocumentIndexJobStatus.PENDING,
                    )
                    .order_by(
                        DocumentIndexJob.created_at,
                        DocumentIndexJob.id,
                    )
                    .limit(1)
                    .with_for_update(skip_locked=True),
                )
                if job is None:
                    return None

                job.status = DocumentIndexJobStatus.PROCESSING
                job.retry_count += 1
                job.error_message = None
                job.started_at = datetime.now(UTC)
                job.finished_at = None
                job_id = job.id
            return job_id

    async def _mark_failed(
        self,
        job_id: int,
        error: Exception,
    ) -> None:
        now = datetime.now(UTC)
        async with session_factory() as session, session.begin():
            job = await session.get(
                DocumentIndexJob,
                job_id,
                with_for_update=True,
            )
            if job is None:
                return

            job.status = DocumentIndexJobStatus.FAILED
            job.error_message = str(error)[:4000]
            job.finished_at = now
            document = await session.get(
                Document,
                job.document_id,
                with_for_update=True,
            )
            if (
                document is not None
                and not document.deleted
                and document.status == DocumentStatus.INDEXING
            ):
                document.status = DocumentStatus.INDEX_FAILED

    async def _recover_stale_jobs(self) -> None:
        stale_before = datetime.now(UTC) - timedelta(minutes=15)
        async with session_factory() as session, session.begin():
            await session.execute(
                update(DocumentIndexJob)
                .where(
                    DocumentIndexJob.status == DocumentIndexJobStatus.PROCESSING,
                    DocumentIndexJob.started_at < stale_before,
                )
                .values(
                    status=DocumentIndexJobStatus.PENDING,
                    error_message="recovered after worker interruption",
                    started_at=None,
                    finished_at=None,
                ),
            )


async def init_document_index_worker(app: FastAPI) -> None:
    worker = DocumentIndexWorker(
        app.state.mongo_database,
        app.state.elasticsearch_client,
        app.state.embedding_client,
    )
    await worker.start()
    app.state.document_index_worker = worker


async def close_document_index_worker(app: FastAPI) -> None:
    worker: DocumentIndexWorker | None = getattr(
        app.state,
        "document_index_worker",
        None,
    )
    if worker is not None:
        await worker.stop()


def get_document_index_worker(request: Request) -> DocumentIndexWorker:
    return request.app.state.document_index_worker


DocumentIndexWorkerDependency = Annotated[
    DocumentIndexWorker,
    Depends(get_document_index_worker),
]
