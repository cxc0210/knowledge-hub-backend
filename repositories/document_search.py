from datetime import datetime
from typing import Any

from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk

from core.config import settings
from models.document import Document
from schemas.document_index import DocumentChunkData


class DocumentSearchRepository:
    HIGHLIGHT_START = "\ue000"
    HIGHLIGHT_END = "\ue001"

    @staticmethod
    async def ensure_index(client: AsyncElasticsearch) -> None:
        index_name = settings.elasticsearch_document_index
        if not await client.indices.exists(index=index_name):
            await client.options(ignore_status=400).indices.create(
                index=index_name,
                settings={
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                },
                mappings={
                    "dynamic": "strict",
                    "properties": {
                        "chunk_id": {"type": "keyword"},
                        "document_id": {"type": "long"},
                        "document_version": {"type": "keyword"},
                        "chunk_index": {"type": "integer"},
                        "title": {
                            "type": "text",
                            "analyzer": "ik_max_word",
                            "search_analyzer": "ik_smart",
                            "fields": {"keyword": {"type": "keyword"}},
                        },
                        "summary": {
                            "type": "text",
                            "analyzer": "ik_max_word",
                            "search_analyzer": "ik_smart",
                        },
                        "heading": {
                            "type": "text",
                            "analyzer": "ik_max_word",
                            "search_analyzer": "ik_smart",
                        },
                        "heading_path": {
                            "type": "text",
                            "analyzer": "ik_max_word",
                            "search_analyzer": "ik_smart",
                        },
                        "content": {
                            "type": "text",
                            "analyzer": "ik_max_word",
                            "search_analyzer": "ik_smart",
                        },
                        "content_hash": {"type": "keyword"},
                        "char_count": {"type": "integer"},
                        "author_id": {"type": "long"},
                        "category_id": {"type": "long"},
                        "team_id": {"type": "long"},
                        "tags": {"type": "keyword"},
                        "status": {"type": "short"},
                        "is_public": {"type": "boolean"},
                        "created_at": {"type": "date"},
                        "publish_time": {"type": "date"},
                    },
                },
                aliases={settings.elasticsearch_document_alias: {}},
            )

        if not await client.indices.exists_alias(
            name=settings.elasticsearch_document_alias,
        ):
            await client.indices.put_alias(
                index=index_name,
                name=settings.elasticsearch_document_alias,
            )

    @classmethod
    async def replace(
        cls,
        client: AsyncElasticsearch,
        document: Document,
        chunks: list[DocumentChunkData],
        published_status: int,
        publish_time: datetime,
    ) -> None:
        await cls.ensure_index(client)
        index_name = settings.elasticsearch_document_index
        await client.delete_by_query(
            index=index_name,
            query={"term": {"document_id": document.id}},
            conflicts="proceed",
            refresh=True,
        )

        actions: list[dict[str, Any]] = [
            {
                "_op_type": "index",
                "_index": index_name,
                "_id": chunk.chunk_id,
                "_source": {
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "document_version": chunk.document_version,
                    "chunk_index": chunk.chunk_index,
                    "title": document.title,
                    "summary": document.summary,
                    "heading": chunk.heading,
                    "heading_path": chunk.heading_path,
                    "content": chunk.content,
                    "content_hash": chunk.content_hash,
                    "char_count": chunk.char_count,
                    "author_id": document.author_id,
                    "category_id": document.category_id,
                    "team_id": document.team_id,
                    "tags": cls._tags(document.tags),
                    "status": published_status,
                    "is_public": document.is_public,
                    "created_at": document.created_at.isoformat(),
                    "publish_time": publish_time.isoformat(),
                },
            }
            for chunk in chunks
        ]
        await async_bulk(
            client,
            actions,
            refresh="wait_for",
            raise_on_error=True,
        )

    @classmethod
    async def delete(
        cls,
        client: AsyncElasticsearch,
        document_id: int,
    ) -> None:
        index_name = settings.elasticsearch_document_index
        if not await client.indices.exists(index=index_name):
            return
        await client.delete_by_query(
            index=index_name,
            query={"term": {"document_id": document_id}},
            conflicts="proceed",
            refresh=True,
        )

    @classmethod
    async def search(
        cls,
        client: AsyncElasticsearch,
        query_text: str,
        user_id: int,
        page: int,
        size: int,
        published_status: int,
    ) -> Any:
        await cls.ensure_index(client)
        return await client.search(
            index=settings.elasticsearch_document_alias,
            from_=(page - 1) * size,
            size=size,
            source_includes=[
                "document_id",
                "title",
                "summary",
                "heading",
                "heading_path",
                "content",
                "publish_time",
            ],
            query={
                "bool": {
                    "must": {
                        "multi_match": {
                            "query": query_text,
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
                    "filter": [
                        {"term": {"status": published_status}},
                        {
                            "bool": {
                                "should": [
                                    {"term": {"author_id": user_id}},
                                    {"term": {"is_public": True}},
                                ],
                                "minimum_should_match": 1,
                            },
                        },
                    ],
                },
            },
            collapse={"field": "document_id"},
            aggregations={
                "unique_documents": {
                    "cardinality": {
                        "field": "document_id",
                        "precision_threshold": 40000,
                    },
                },
            },
            highlight={
                "pre_tags": [cls.HIGHLIGHT_START],
                "post_tags": [cls.HIGHLIGHT_END],
                "order": "score",
                "fields": {
                    "title": {"number_of_fragments": 0},
                    "summary": {"fragment_size": 180, "number_of_fragments": 1},
                    "heading": {"number_of_fragments": 0},
                    "heading_path": {
                        "fragment_size": 180,
                        "number_of_fragments": 1,
                    },
                    "content": {"fragment_size": 220, "number_of_fragments": 3},
                },
            },
            track_total_hits=False,
        )

    @staticmethod
    def _tags(tags: str | None) -> list[str]:
        if not tags:
            return []
        return [
            tag.strip() for tag in tags.replace("，", ",").split(",") if tag.strip()
        ]
