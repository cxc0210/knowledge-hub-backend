from dataclasses import dataclass, field
from datetime import datetime

from pydantic import BaseModel, Field

from enums.rag import RequestRoute


@dataclass(frozen=True, slots=True)
class RAGFilters:
    user_id: int
    category_id: int | None = None
    team_id: int | None = None
    tags: tuple[str, ...] = ()
    document_ids: tuple[int, ...] = ()


@dataclass(slots=True)
class RetrievalCandidate:
    chunk_id: str
    document_id: int
    chunk_index: int
    title: str
    heading: str | None
    heading_path: str | None
    content: str
    publish_time: datetime | None
    keyword_rank: int | None = None
    vector_rank: int | None = None
    fused_score: float = 0
    rerank_score: float | None = None


class RAGSource(BaseModel):
    document_id: int
    chunk_id: str
    title: str
    heading: str | None


class RouteDecision(BaseModel):
    route: RequestRoute


class RerankDecision(BaseModel):
    ranked_chunk_ids: list[str] = Field(default_factory=list, max_length=50)


@dataclass(slots=True)
class RetrievalResults:
    keyword: list[RetrievalCandidate] = field(default_factory=list)
    vector: list[RetrievalCandidate] = field(default_factory=list)
