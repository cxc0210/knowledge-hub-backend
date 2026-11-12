from collections.abc import Mapping
from math import ceil
from typing import Any

from elasticsearch import AsyncElasticsearch

from enums.document import DocumentStatus
from repositories.document_search import DocumentSearchRepository
from schemas.search import DocumentSearchItem, DocumentSearchResponse


class DocumentSearchService:
    @classmethod
    async def search(
        cls,
        elasticsearch: AsyncElasticsearch,
        query_text: str,
        user_id: int,
        page: int,
        size: int,
    ) -> DocumentSearchResponse:
        response = await DocumentSearchRepository.search(
            elasticsearch,
            query_text,
            user_id,
            page,
            size,
            DocumentStatus.PUBLISHED,
        )
        payload = cls._mapping(getattr(response, "body", response))
        raw_hits = cls._mapping(payload.get("hits")).get("hits", [])
        aggregations = cls._mapping(payload.get("aggregations"))
        unique_documents = cls._mapping(aggregations.get("unique_documents"))
        total = int(unique_documents.get("value", 0))

        items = [
            item
            for hit in raw_hits
            if (item := cls._build_item(cls._mapping(hit))) is not None
        ]
        return DocumentSearchResponse(
            query=query_text,
            items=items,
            page=page,
            size=size,
            total=total,
            pages=ceil(total / size),
            took_ms=int(payload.get("took", 0)),
        )

    @classmethod
    def _build_item(
        cls,
        hit: Mapping[str, Any],
    ) -> DocumentSearchItem | None:
        source = cls._mapping(hit.get("_source"))
        document_id = source.get("document_id")
        if not isinstance(document_id, int):
            return None

        highlights = cls._mapping(hit.get("highlight"))
        highlighted_titles = cls._strings(highlights.get("title"))
        snippets = cls._unique_strings(
            [
                *cls._strings(highlights.get("content")),
                *cls._strings(highlights.get("summary")),
                *cls._strings(highlights.get("heading")),
                *cls._strings(highlights.get("heading_path")),
            ],
        )
        if not snippets:
            fallback = cls._fallback_snippet(source)
            snippets = [fallback] if fallback else []

        score = hit.get("_score")
        return DocumentSearchItem(
            document_id=document_id,
            title=str(source.get("title") or "未命名文档"),
            highlighted_title=highlighted_titles[0] if highlighted_titles else None,
            heading=cls._optional_string(source.get("heading")),
            snippets=snippets,
            score=float(score) if isinstance(score, int | float) else None,
            publish_time=source.get("publish_time"),
        )

    @staticmethod
    def _mapping(value: Any) -> Mapping[str, Any]:
        return value if isinstance(value, Mapping) else {}

    @staticmethod
    def _strings(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str) and item]

    @staticmethod
    def _unique_strings(values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))

    @staticmethod
    def _optional_string(value: Any) -> str | None:
        return value if isinstance(value, str) and value else None

    @classmethod
    def _fallback_snippet(cls, source: Mapping[str, Any]) -> str | None:
        for field in ("content", "summary", "heading_path", "heading"):
            value = cls._optional_string(source.get(field))
            if value:
                return value if len(value) <= 240 else f"{value[:240]}…"
        return None
