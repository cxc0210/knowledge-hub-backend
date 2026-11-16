from langchain_core.messages import SystemMessage
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from core.llm import get_chat_model
from graphs.context import AgentContext
from tools import request_email_send

TOOLS = [request_email_send]

SYSTEM_PROMPT = """
你是 Knowledge Hub 的 AI 助手，可以回答问题并使用系统提供的工具。

工具使用规则：
1. 当用户明确要求发送邮件时，使用 request_email_send 创建待确认邮件。
2. 收件人、标题或正文不完整时，先向用户询问，不要猜测。
3. request_email_send 只会创建待确认操作。工具返回 pending_approval 后，提醒用户在邮件卡片中确认或取消。
4. 除非工具明确返回发送成功，否则不得声称邮件已经发送。
5. 工具失败时如实说明，不得伪造执行结果。
""".strip()


async def call_model(state: MessagesState) -> dict[str, list[object]]:
    model = get_chat_model().bind_tools(TOOLS)
    response = await model.ainvoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            *state["messages"],
        ]
    )
    return {"messages": [response]}


agent_graph = (
    StateGraph(MessagesState, context_schema=AgentContext)
    .add_node("call_model", call_model)
    .add_node(
        "tools",
        ToolNode(
            TOOLS,
            handle_tool_errors="工具执行失败，请检查参数后重试",
        ),
    )
    .add_edge(START, "call_model")
    .add_conditional_edges("call_model", tools_condition)
    .add_edge("tools", "call_model")
    .compile(name="agent_graph")
)

# 保留旧名称，避免现有调用方和测试在迁移期间失效。
ai_graph = agent_graph
