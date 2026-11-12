from typing import Annotated

from fastapi import APIRouter, Query

from core.elasticsearch import ElasticsearchClient
from dependencies.auth import CurrentUser
from schemas.search import DocumentSearchResponse
from services.document_search import DocumentSearchService

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=DocumentSearchResponse)
async def search_documents(
    elasticsearch: ElasticsearchClient,
    current_user: CurrentUser,
    q: Annotated[
        str,
        Query(min_length=1, max_length=200, pattern=r".*\S.*"),
    ],
    page: Annotated[int, Query(ge=1, le=100)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 10,
) -> DocumentSearchResponse:
    return await DocumentSearchService.search(
        elasticsearch,
        q.strip(),
        current_user.id,
        page,
        size,
    )
