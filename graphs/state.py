from typing import NotRequired

from langgraph.graph import MessagesState

from enums.rag import RequestRoute
from schemas.rag import RAGFilters, RAGSource, RetrievalCandidate


class MainState(MessagesState):
    route: NotRequired[RequestRoute]
    query: NotRequired[str]
    filters: NotRequired[RAGFilters]
    keyword_candidates: NotRequired[list[RetrievalCandidate]]
    vector_candidates: NotRequired[list[RetrievalCandidate]]
    fused_candidates: NotRequired[list[RetrievalCandidate]]
    filtered_candidates: NotRequired[list[RetrievalCandidate]]
    reranked_candidates: NotRequired[list[RetrievalCandidate]]
    rag_context: NotRequired[str]
    sources: NotRequired[list[RAGSource]]
