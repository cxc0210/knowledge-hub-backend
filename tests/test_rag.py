from datetime import UTC, datetime
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, Mock, patch

from schemas.rag import (
    RAGFilters,
    RerankDecision,
    RetrievalCandidate,
)
from services.rag import (
    HybridRetrievalService,
    RAGAccessFilterService,
    RAGContextBuilder,
    RAGRerankerService,
    RAGRetrievalError,
    RRFFusionService,
)


def candidate(
    chunk_id: str,
    *,
    document_id: int = 100001,
    chunk_index: int = 0,
    content: str = "文档正文",
) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=chunk_id,
        document_id=document_id,
        chunk_index=chunk_index,
        title="测试文档",
        heading="测试章节",
        heading_path="第一章 > 测试章节",
        content=content,
        publish_time=datetime.now(UTC),
    )


class RRFFusionTests(TestCase):
    def test_fuses_and_deduplicates_candidates_by_chunk_id(self) -> None:
        keyword = [candidate("shared"), candidate("keyword-only")]
        vector = [candidate("shared"), candidate("vector-only")]

        result = RRFFusionService.fuse(keyword, vector)

        self.assertEqual(result[0].chunk_id, "shared")
        self.assertEqual(result[0].keyword_rank, 1)
        self.assertEqual(result[0].vector_rank, 1)
        self.assertEqual(
            {item.chunk_id for item in result},
            {"shared", "keyword-only", "vector-only"},
        )


class RAGContextBuilderTests(TestCase):
    def test_builds_numbered_sources_and_removes_duplicate_content(self) -> None:
        candidates = [
            candidate("chunk-1", content="相同正文"),
            candidate("chunk-2", content="相同正文"),
            candidate(
                "chunk-3",
                document_id=100002,
                content="另一段正文",
            ),
        ]

        context, sources = RAGContextBuilder.build(candidates)

        self.assertEqual(len(sources), 2)
        self.assertIn("[来源 1]", context)
        self.assertIn("[来源 2]", context)
        self.assertEqual([source.chunk_id for source in sources], ["chunk-1", "chunk-3"])


class RAGServiceTests(IsolatedAsyncioTestCase):
    async def test_hybrid_retrieval_degrades_to_vector_results(self) -> None:
        vector = [candidate("vector")]
        with (
            patch.object(
                HybridRetrievalService,
                "_keyword_search",
                new=AsyncMock(side_effect=RuntimeError("ES unavailable")),
            ),
            patch.object(
                HybridRetrievalService,
                "_vector_search",
                new=AsyncMock(return_value=vector),
            ),
            self.assertLogs("services.rag", level="ERROR"),
        ):
            result = await HybridRetrievalService.retrieve(
                "问题",
                RAGFilters(user_id=1001),
            )

        self.assertEqual(result.keyword, [])
        self.assertEqual(result.vector, vector)

    async def test_hybrid_retrieval_fails_when_both_sources_fail(self) -> None:
        with (
            patch.object(
                HybridRetrievalService,
                "_keyword_search",
                new=AsyncMock(side_effect=RuntimeError("ES unavailable")),
            ),
            patch.object(
                HybridRetrievalService,
                "_vector_search",
                new=AsyncMock(side_effect=RuntimeError("vector unavailable")),
            ),
            self.assertLogs("services.rag", level="ERROR"),
            self.assertRaises(RAGRetrievalError),
        ):
            await HybridRetrievalService.retrieve(
                "问题",
                RAGFilters(user_id=1001),
            )

    async def test_access_filter_keeps_only_authorized_documents(self) -> None:
        candidates = [
            candidate("allowed", document_id=100001),
            candidate("denied", document_id=100002),
        ]

        with patch(
            "services.rag.RAGDocumentAccessRepository.allowed_document_ids",
            new=AsyncMock(return_value={100001}),
        ):
            result = await RAGAccessFilterService.filter(
                candidates,
                RAGFilters(user_id=1001),
            )

        self.assertEqual([item.chunk_id for item in result], ["allowed"])

    async def test_reranker_uses_model_ranked_chunk_ids(self) -> None:
        candidates = [candidate("chunk-1"), candidate("chunk-2")]
        structured_model = SimpleNamespace(
            ainvoke=AsyncMock(
                return_value=RerankDecision(
                    ranked_chunk_ids=["chunk-2", "chunk-1"],
                )
            )
        )
        model = SimpleNamespace(
            with_structured_output=Mock(return_value=structured_model),
        )

        with patch("services.rag.get_chat_model", return_value=model):
            result = await RAGRerankerService.rerank("问题", candidates)

        self.assertEqual(
            [item.chunk_id for item in result],
            ["chunk-2", "chunk-1"],
        )
