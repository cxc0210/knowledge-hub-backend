from typing import NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph

from core.llm import get_chat_model


class AIState(TypedDict):
    prompt: str
    answer: NotRequired[str]


async def call_model(state: AIState) -> dict[str, str]:
    response = await get_chat_model().ainvoke(state["prompt"])
    return {"answer": response.text}


ai_graph = (
    StateGraph(AIState)
    .add_node("call_model", call_model)
    .add_edge(START, "call_model")
    .add_edge("call_model", END)
    .compile()
)
