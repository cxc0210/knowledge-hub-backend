from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

from langchain_core.messages import AIMessage, HumanMessage

from enums.rag import RequestRoute
from graphs.context import AgentContext
from graphs.main import main_graph
from schemas.rag import (
    RAGFilters,
    RAGSource,
    RetrievalCandidate,
    RetrievalResults,
    RouteDecision,
)

TEST_CONTEXT = AgentContext(
    user_id=1001,
    permission_codes=frozenset({"ai:email:send"}),
)


class MainGraphTests(IsolatedAsyncioTestCase):
    async def test_routes_action_request_to_agent_graph(self) -> None:
        router = SimpleNamespace(
            ainvoke=AsyncMock(
                return_value=RouteDecision(route=RequestRoute.AGENT),
            )
        )
        router_model = SimpleNamespace(
            with_structured_output=Mock(return_value=router),
        )
        bound_model = SimpleNamespace(
            ainvoke=AsyncMock(return_value=AIMessage(content="请确认邮件。")),
        )
        agent_model = SimpleNamespace(
            bind_tools=Mock(return_value=bound_model),
        )

        with (
            patch("graphs.main.get_chat_model", return_value=router_model),
            patch("graphs.ai.get_chat_model", return_value=agent_model),
        ):
            result = await main_graph.ainvoke(
                {"messages": [HumanMessage(content="帮我发送邮件")]},
                context=TEST_CONTEXT,
            )

        self.assertEqual(result["route"], RequestRoute.AGENT)
        self.assertEqual(result["messages"][-1].text, "请确认邮件。")

    async def test_routes_knowledge_request_through_rag_graph(self) -> None:
        router = SimpleNamespace(
            ainvoke=AsyncMock(
                return_value=RouteDecision(route=RequestRoute.KNOWLEDGE),
            )
        )
        router_model = SimpleNamespace(
            with_structured_output=Mock(return_value=router),
        )
        candidate = RetrievalCandidate(
            chunk_id="100001:v1:0",
            document_id=100001,
            chunk_index=0,
            title="事务指南",
            heading="事务管理",
            heading_path="数据库 > 事务管理",
            content="事务由 SQLAlchemy AsyncSession 管理。",
            publish_time=None,
        )
        retrieve = AsyncMock(
            return_value=RetrievalResults(
                keyword=[candidate],
                vector=[candidate],
            )
        )
        access_filter = AsyncMock(return_value=[candidate])
        rerank = AsyncMock(return_value=[candidate])
        answer_model = SimpleNamespace(
            ainvoke=AsyncMock(
                return_value=AIMessage(content="事务由 AsyncSession 管理。[来源 1]"),
            )
        )

        with (
            patch("graphs.main.get_chat_model", return_value=router_model),
            patch(
                "graphs.rag.HybridRetrievalService.retrieve",
                new=retrieve,
            ),
            patch(
                "graphs.rag.RAGAccessFilterService.filter",
                new=access_filter,
            ),
            patch(
                "graphs.rag.RAGRerankerService.rerank",
                new=rerank,
            ),
            patch("graphs.rag.get_chat_model", return_value=answer_model),
        ):
            result = await main_graph.ainvoke(
                {"messages": [HumanMessage(content="FastAPI 怎么管理事务？")]},
                context=TEST_CONTEXT,
            )

        self.assertEqual(result["route"], RequestRoute.KNOWLEDGE)
        self.assertEqual(
            result["messages"][-1].text,
            "事务由 AsyncSession 管理。[来源 1]",
        )
        self.assertEqual(
            result["sources"],
            [
                RAGSource(
                    document_id=100001,
                    chunk_id="100001:v1:0",
                    title="事务指南",
                    heading="数据库 > 事务管理",
                )
            ],
        )
        await_args = retrieve.await_args
        assert await_args is not None
        called_filters = await_args.args[1]
        self.assertIsInstance(called_filters, RAGFilters)
        self.assertEqual(called_filters.user_id, TEST_CONTEXT.user_id)
