from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from enums.document import DocumentStatus
from repositories.document_search import DocumentSearchRepository
from services.document_search import DocumentSearchService


class DocumentSearchRepositoryTests(IsolatedAsyncioTestCase):
    async def test_builds_collapsed_highlighted_document_search(self) -> None:
        client = SimpleNamespace(search=AsyncMock(return_value={}))

        with patch.object(
            DocumentSearchRepository,
            "ensure_index",
            new=AsyncMock(),
        ):
            await DocumentSearchRepository.search(
                client,  # type: ignore[arg-type]
                "知识库",
                user_id=100001,
                page=2,
                size=10,
                published_status=DocumentStatus.PUBLISHED,
            )

        request = client.search.await_args.kwargs
        self.assertEqual(request["from_"], 10)
        self.assertEqual(request["size"], 10)
        self.assertEqual(request["collapse"], {"field": "document_id"})
        self.assertEqual(
            request["aggregations"]["unique_documents"]["cardinality"]["field"],
            "document_id",
        )
        self.assertIn("content", request["highlight"]["fields"])
        filters = request["query"]["bool"]["filter"]
        self.assertEqual(filters[0], {"term": {"status": DocumentStatus.PUBLISHED}})
        self.assertIn(
            {"term": {"author_id": 100001}},
            filters[1]["bool"]["should"],
        )


class DocumentSearchServiceTests(IsolatedAsyncioTestCase):
    async def test_maps_elasticsearch_highlights_and_document_total(self) -> None:
        response = {
            "took": 8,
            "hits": {
                "hits": [
                    {
                        "_score": 4.2,
                        "_source": {
                            "document_id": 100101,
                            "title": "知识库检索说明",
                            "heading": "全文检索",
                            "content": "使用 Elasticsearch 完成全文检索。",
                            "publish_time": "2026-11-12T08:00:00+00:00",
                        },
                        "highlight": {
                            "title": ["\ue000知识库\ue001检索说明"],
                            "content": [
                                "使用 Elasticsearch 完成\ue000全文检索\ue001。",
                            ],
                        },
                    },
                ],
            },
            "aggregations": {"unique_documents": {"value": 11}},
        }

        with patch.object(
            DocumentSearchRepository,
            "search",
            new=AsyncMock(return_value=response),
        ):
            result = await DocumentSearchService.search(
                SimpleNamespace(),  # type: ignore[arg-type]
                "全文检索",
                user_id=100001,
                page=1,
                size=10,
            )

        self.assertEqual(result.total, 11)
        self.assertEqual(result.pages, 2)
        self.assertEqual(result.took_ms, 8)
        self.assertEqual(result.items[0].document_id, 100101)
        self.assertEqual(
            result.items[0].highlighted_title,
            "\ue000知识库\ue001检索说明",
        )
        self.assertEqual(
            result.items[0].snippets,
            ["使用 Elasticsearch 完成\ue000全文检索\ue001。"],
        )
