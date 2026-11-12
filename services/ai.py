from graphs.ai import ai_graph
from schemas.ai import AIChatResponse


class AIService:
    @staticmethod
    async def chat(prompt: str) -> AIChatResponse:
        result = await ai_graph.ainvoke({"prompt": prompt})
        return AIChatResponse(answer=result["answer"])
