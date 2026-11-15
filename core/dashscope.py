import logging
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, Request

from core.config import settings

logger = logging.getLogger(__name__)

dashscope_client = httpx.AsyncClient(
    base_url=settings.dashscope_base_url.rstrip("/"),
    timeout=httpx.Timeout(settings.dashscope_asr_timeout_seconds),
    limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
)


async def init_dashscope(app: FastAPI) -> None:
    app.state.dashscope_client = dashscope_client
    if settings.dashscope_api_key.get_secret_value().strip():
        logger.info(
            "DashScope client initialized, ASR model=%s",
            settings.dashscope_asr_model,
        )
    else:
        logger.info(
            "DashScope client initialized without API key; ASR is disabled",
        )


async def close_dashscope() -> None:
    await dashscope_client.aclose()
    logger.info("DashScope connections closed")


def get_dashscope_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.dashscope_client


DashScopeClient = Annotated[
    httpx.AsyncClient,
    Depends(get_dashscope_client),
]
