import logging
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, Request

from core.config import settings

logger = logging.getLogger(__name__)

embedding_client = httpx.AsyncClient(
    base_url=settings.embedding_base_url.rstrip("/"),
    timeout=httpx.Timeout(settings.embedding_timeout_seconds),
)


async def init_embedding(app: FastAPI) -> None:
    response = await embedding_client.get("/api/tags")
    response.raise_for_status()

    model_names = {
        str(model.get("name")) for model in response.json().get("models", [])
    }
    if settings.embedding_model not in model_names:
        raise RuntimeError(
            f"embedding model '{settings.embedding_model}' is not installed",
        )

    app.state.embedding_client = embedding_client
    logger.info(
        "Embedding service connection successful, model=%s",
        settings.embedding_model,
    )


async def close_embedding() -> None:
    await embedding_client.aclose()
    logger.info("Embedding service connections closed")


def get_embedding_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.embedding_client


EmbeddingClient = Annotated[
    httpx.AsyncClient,
    Depends(get_embedding_client),
]
