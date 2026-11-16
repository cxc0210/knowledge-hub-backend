import logging
from typing import cast

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from core.llm import get_chat_model
from enums.rag import RequestRoute
from graphs.ai import agent_graph
from graphs.context import AgentContext
from graphs.rag import rag_graph
from graphs.state import MainState
from schemas.rag import RouteDecision

logger = logging.getLogger(__name__)

ROUTER_SYSTEM_PROMPT = """
你是 Knowledge Hub 的请求路由器，只负责选择处理流程，不回答用户问题。

选择 knowledge：
- 用户询问信息、概念、制度、流程或文档内容；
- 用户要求查找、搜索、总结、比较 Knowledge Hub 中的资料；
- 回答应当依赖知识库文档。

选择 agent：
- 用户要求执行会改变外部状态的操作，例如发送邮件、发布、删除或修改；
- 用户只是寒暄，或请求不需要查询知识库；
- 一个请求同时包含知识查询和外部操作时，也选择 agent。
""".strip()

ACTION_MARKERS = (
    "发送",
    "发邮件",
    "删除",
    "发布",
    "创建",
    "修改",
    "更新",
    "审批",
    "确认",
    "取消",
)
GREETING_MARKERS = ("你好", "您好", "嗨", "谢谢", "再见")


def _latest_question(state: MainState) -> str:
    for message in reversed(state["messages"]):
        if isinstance(message, HumanMessage) and message.text.strip():
            return message.text.strip()
    raise ValueError("main graph requires a user question")


async def classify_request(state: MainState) -> dict:
    question = _latest_question(state)
    try:
        router_model = get_chat_model().with_structured_output(RouteDecision)
        decision = cast(
            RouteDecision,
            await router_model.ainvoke(
                [
                    SystemMessage(content=ROUTER_SYSTEM_PROMPT),
                    HumanMessage(content=question),
                ]
            ),
        )
        route = decision.route
    except Exception:
        logger.exception("AI request routing failed; using deterministic fallback")
        route = _fallback_route(question)

    return {"route": route}


def _fallback_route(question: str) -> RequestRoute:
    if any(marker in question for marker in ACTION_MARKERS):
        return RequestRoute.AGENT
    if any(question.startswith(marker) for marker in GREETING_MARKERS):
        return RequestRoute.AGENT
    return RequestRoute.KNOWLEDGE


def choose_route(state: MainState) -> str:
    route = state.get("route")
    if route is None:
        raise ValueError("request route was not classified")
    return route.value


main_graph = (
    StateGraph(MainState, context_schema=AgentContext)
    .add_node("classify_request", classify_request)
    .add_node("agent", agent_graph)
    .add_node("rag", rag_graph)
    .add_edge(START, "classify_request")
    .add_conditional_edges(
        "classify_request",
        choose_route,
        {
            RequestRoute.KNOWLEDGE.value: "rag",
            RequestRoute.AGENT.value: "agent",
        },
    )
    .add_edge("rag", END)
    .add_edge("agent", END)
    .compile(name="main_graph")
)
