from collections.abc import Mapping
from datetime import datetime
from typing import Any

from elasticsearch import AsyncElasticsearch
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from enums.document import DocumentStatus
from models.document import Document
from models.document_chunk import DocumentChunk
from repositories.document_search import DocumentSearchRepository
from schemas.rag import RAGFilters, RetrievalCandidate


class RAGElasticsearchRepository:
    @classmethod
    async def search(
        cls,
        client: AsyncElasticsearch,
        *,
        query: str,
        filters: RAGFilters,
        limit: int,
    ) -> list[RetrievalCandidate]:
        await DocumentSearchRepository.ensure_index(client)
        filter_clauses: list[dict[str, Any]] = [
            {"term": {"status": DocumentStatus.PUBLISHED.value}},
            {
                "bool": {
                    "should": [
                        {"term": {"author_id": filters.user_id}},
                        {"term": {"is_public": True}},
                    ],
                    "minimum_should_match": 1,
                },
            },
        ]
        if filters.category_id is not None:
            filter_clauses.append(
                {"term": {"category_id": filters.category_id}},
            )
        if filters.team_id is not None:
            filter_clauses.append({"term": {"team_id": filters.team_id}})
        if filters.tags:
            filter_clauses.extend(
                {"term": {"tags": tag}} for tag in filters.tags
            )
        if filters.document_ids:
            filter_clauses.append(
                {"terms": {"document_id": list(filters.document_ids)}},
            )

        response = await client.search(
            index=settings.elasticsearch_document_alias,
            size=limit,
            source_includes=[
                "chunk_id",
                "document_id",
                "chunk_index",
                "title",
                "heading",
                "heading_path",
                "content",
                "publish_time",
            ],
            query={
                "bool": {
                    "must": {
                        "multi_match": {
                            "query": query,
                            "fields": [
                                "title^5",
                                "summary^3",
                                "heading^3",
                                "heading_path^2",
                                "content",
                            ],
                            "type": "best_fields",
                        },
                    },
                    "filter": filter_clauses,
                },
            },
            track_total_hits=False,
        )
        payload = cls._mapping(getattr(response, "body", response))
        hits = cls._mapping(payload.get("hits")).get("hits", [])
        if not isinstance(hits, list):
            return []

        candidates: list[RetrievalCandidate] = []
        for rank, raw_hit in enumerate(hits, start=1):
            hit = cls._mapping(raw_hit)
            source = cls._mapping(hit.get("_source"))
            candidate = cls._candidate(source, rank)
            if candidate is not None:
                candidates.append(candidate)
        return candidates

    @classmethod
    def _candidate(
        cls,
        source: Mapping[str, Any],
        rank: int,
    ) -> RetrievalCandidate | None:
        chunk_id = source.get("chunk_id")
        document_id = source.get("document_id")
        chunk_index = source.get("chunk_index")
        content = source.get("content")
        if (
            not isinstance(chunk_id, str)
            or not isinstance(document_id, int)
            or not isinstance(chunk_index, int)
            or not isinstance(content, str)
        ):
            return None

        return RetrievalCandidate(
            chunk_id=chunk_id,
            document_id=document_id,
            chunk_index=chunk_index,
            title=str(source.get("title") or "未命名文档"),
            heading=cls._optional_string(source.get("heading")),
            heading_path=cls._optional_string(source.get("heading_path")),
            content=content,
            publish_time=cls._datetime(source.get("publish_time")),
            keyword_rank=rank,
        )

    @staticmethod
    def _mapping(value: Any) -> Mapping[str, Any]:
        return value if isinstance(value, Mapping) else {}

    @staticmethod
    def _optional_string(value: Any) -> str | None:
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None


class RAGPgvectorRepository:
    @staticmethod
    async def search(
        session: AsyncSession,
        *,
        embedding: list[float],
        filters: RAGFilters,
        limit: int,
    ) -> list[RetrievalCandidate]:
        distance = DocumentChunk.embedding.cosine_distance(embedding).label(
            "distance",
        )
        statement = (
            select(
                DocumentChunk,
                Document.title,
                Document.publish_time,
                distance,
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                Document.status == DocumentStatus.PUBLISHED,
                Document.deleted.is_(False),
                DocumentChunk.embedding_model == settings.embedding_model,
                or_(
                    Document.author_id == filters.user_id,
                    Document.is_public.is_(True),
                ),
            )
            .order_by(distance)
            .limit(limit)
        )
        if filters.category_id is not None:
            statement = statement.where(
                Document.category_id == filters.category_id,
            )
        if filters.team_id is not None:
            statement = statement.where(Document.team_id == filters.team_id)
        if filters.document_ids:
            statement = statement.where(Document.id.in_(filters.document_ids))
        for tag in filters.tags:
            statement = statement.where(Document.tags.ilike(f"%{tag}%"))

        result = await session.execute(statement)
        candidates: list[RetrievalCandidate] = []
        for rank, row in enumerate(result.all(), start=1):
            chunk, title, publish_time, _ = row
            candidates.append(
                RetrievalCandidate(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    chunk_index=chunk.chunk_index,
                    title=title,
                    heading=chunk.heading,
                    heading_path=chunk.heading_path,
                    content=chunk.content,
                    publish_time=publish_time,
                    vector_rank=rank,
                )
            )
        return candidates


class RAGDocumentAccessRepository:
    @staticmethod
    async def allowed_document_ids(
        session: AsyncSession,
        *,
        document_ids: set[int],
        filters: RAGFilters,
    ) -> set[int]:
        if not document_ids:
            return set()

        statement = select(Document.id).where(
            Document.id.in_(document_ids),
            Document.status == DocumentStatus.PUBLISHED,
            Document.deleted.is_(False),
            or_(
                Document.author_id == filters.user_id,
                Document.is_public.is_(True),
            ),
        )
        if filters.category_id is not None:
            statement = statement.where(
                Document.category_id == filters.category_id,
            )
        if filters.team_id is not None:
            statement = statement.where(Document.team_id == filters.team_id)
        if filters.document_ids:
            statement = statement.where(Document.id.in_(filters.document_ids))
        for tag in filters.tags:
            statement = statement.where(Document.tags.ilike(f"%{tag}%"))

        result = await session.scalars(statement)
        return set(result.all())
