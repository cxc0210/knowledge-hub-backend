import logging
from typing import Annotated

from elasticsearch import AsyncElasticsearch
from fastapi import Depends, FastAPI, Request

from core.config import settings

logger = logging.getLogger(__name__)

elasticsearch_client = AsyncElasticsearch(
    hosts=[settings.elasticsearch_url],
    connections_per_node=20,
    request_timeout=10,
    max_retries=3,
    retry_on_timeout=True,
    http_compress=True,
)


async def init_elasticsearch(app: FastAPI) -> None:
    app.state.elasticsearch_client = elasticsearch_client

    info = await elasticsearch_client.info()
    logger.info(
        "Elasticsearch connection successful, cluster=%s, version=%s",
        info["cluster_name"],
        info["version"]["number"],
    )


async def close_elasticsearch() -> None:
    await elasticsearch_client.close()
    logger.info("Elasticsearch connections closed")


def get_elasticsearch(request: Request) -> AsyncElasticsearch:
    return request.app.state.elasticsearch_client


ElasticsearchClient = Annotated[
    AsyncElasticsearch,
    Depends(get_elasticsearch),
]
