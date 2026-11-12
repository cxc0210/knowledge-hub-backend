import asyncio
import logging
from uuid import uuid4

from sqlalchemy import delete, select

from core.config import settings
from core.database import engine, session_factory
from core.elasticsearch import elasticsearch_client
from core.embedding import embedding_client
from core.mongodb import mongo_client, mongo_database
from enums.document import DocumentStatus
from enums.document_index import DocumentIndexJobStatus
from models.document import Document
from models.document_chunk import DocumentChunk
from models.document_index_job import DocumentIndexJob
from repositories.document_search import DocumentSearchRepository
from schemas.document_content import DocumentContentCreate
from services.document_content import DocumentContentService
from services.document_index import DocumentIndexService

logger = logging.getLogger(__name__)

MARKDOWN = """# 知识库索引验证

这是一次中文全文索引与向量检索链路的集成测试。系统会按字符和 Markdown 结构切分内容，保留标题层级，并为每个分片生成稳定的 chunk_id。

## 为什么采用异步索引

向量生成和搜索索引写入都属于耗时操作，不应阻塞上传接口。文档会先进入 INDEXING 状态，只有 pgvector 与 Elasticsearch 都写入成功后才会变为 PUBLISHED。

## 幂等设计

每个分片标识由文档 ID、正文版本哈希和分片序号组成。重复执行同一版本时使用相同标识，并先替换该文档之前的索引数据，因此不会不断产生重复分片。

| 存储 | 用途 |
| --- | --- |
| PostgreSQL + pgvector | 语义相似度检索 |
| Elasticsearch + IK | 中文关键字全文检索 |
| MongoDB | 保存完整 Markdown 正文 |
"""


async def _assert_indexed(document_id: int) -> int:
    async with session_factory() as session:
        document = await session.get(Document, document_id)
        if document is None or document.status != DocumentStatus.PUBLISHED:
            raise AssertionError("document was not published")

        chunks = list(
            await session.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == document_id)
                .order_by(DocumentChunk.chunk_index),
            ),
        )
        if not chunks:
            raise AssertionError("pgvector contains no document chunks")
        if any(len(chunk.embedding) != 1024 for chunk in chunks):
            raise AssertionError("pgvector embedding dimension is not 1024")

    es_count = await elasticsearch_client.count(
        index=settings.elasticsearch_document_alias,
        query={"term": {"document_id": document_id}},
    )
    if es_count["count"] != len(chunks):
        raise AssertionError("Elasticsearch and pgvector chunk counts differ")

    search = await elasticsearch_client.search(
        index=settings.elasticsearch_document_alias,
        query={"match": {"content": "中文全文索引"}},
    )
    if not search["hits"]["hits"]:
        raise AssertionError("IK full-text search returned no result")

    return len(chunks)


async def main() -> None:
    marker = uuid4().hex
    document_id: int | None = None
    content_id: str | None = None

    try:
        await mongo_database.command("ping")
        await elasticsearch_client.info()
        tags = await embedding_client.get("/api/tags")
        tags.raise_for_status()

        content = await DocumentContentService.create(
            mongo_database,
            DocumentContentCreate(content=MARKDOWN),
        )
        content_id = content.content_id

        async with session_factory() as session, session.begin():
            document = Document(
                title=f"索引集成测试-{marker}",
                content_id=content_id,
                object_key=f"integration-test/{marker}.md",
                file_name="document-index-integration.md",
                content_type="text/markdown",
                file_size=len(MARKDOWN.encode("utf-8")),
                status=DocumentStatus.INDEXING,
                tags="集成测试,中文检索",
                is_public=True,
            )
            session.add(document)
            await session.flush()
            document_id = document.id

            job = DocumentIndexJob(
                document_id=document_id,
                status=DocumentIndexJobStatus.PROCESSING,
                retry_count=1,
            )
            session.add(job)
            await session.flush()
            job_id = job.id

        await DocumentIndexService.process(
            job_id,
            mongo_database,
            elasticsearch_client,
            embedding_client,
        )
        first_count = await _assert_indexed(document_id)

        # 重复执行同一版本，验证稳定 chunk_id 不会产生重复数据。
        async with session_factory() as session, session.begin():
            document = await session.get(Document, document_id)
            job = await session.get(DocumentIndexJob, job_id)
            if document is None or job is None:
                raise AssertionError("integration test records disappeared")
            document.status = DocumentStatus.INDEXING
            job.status = DocumentIndexJobStatus.PROCESSING
            job.finished_at = None

        await DocumentIndexService.process(
            job_id,
            mongo_database,
            elasticsearch_client,
            embedding_client,
        )
        second_count = await _assert_indexed(document_id)
        if first_count != second_count:
            raise AssertionError("idempotent reindex changed the chunk count")

        print(
            "document indexing integration check passed: "
            f"document_id={document_id}, chunks={second_count}, "
            "embedding_dimension=1024, idempotent=true",
        )
    finally:
        if document_id is not None:
            try:
                await DocumentSearchRepository.delete(
                    elasticsearch_client,
                    document_id,
                )
            except Exception as error:  # noqa: BLE001
                logger.warning("Elasticsearch cleanup failed: %s", error)
            async with session_factory() as session, session.begin():
                await session.execute(
                    delete(Document).where(Document.id == document_id),
                )
        if content_id is not None:
            try:
                await DocumentContentService.delete(
                    mongo_database,
                    content_id,
                )
            except Exception as error:  # noqa: BLE001
                logger.warning("MongoDB cleanup failed: %s", error)

        await embedding_client.aclose()
        await elasticsearch_client.close()
        await mongo_client.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
