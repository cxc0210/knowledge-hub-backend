import logging
from contextlib import AsyncExitStack
from typing import Annotated

from aiobotocore.config import AioConfig
from aiobotocore.session import get_session
from fastapi import Depends, FastAPI, Request
from types_aiobotocore_s3.client import S3Client

from core.config import settings

logger = logging.getLogger(__name__)

rustfs_session = get_session()
rustfs_exit_stack = AsyncExitStack()


async def init_rustfs(app: FastAPI) -> None:
    rustfs_client = await rustfs_exit_stack.enter_async_context(
        rustfs_session.create_client(
            "s3",
            endpoint_url=settings.rustfs_endpoint,
            aws_access_key_id=settings.rustfs_access_key.get_secret_value(),
            aws_secret_access_key=settings.rustfs_secret_key.get_secret_value(),
            region_name="us-east-1",
            config=AioConfig(
                signature_version="s3v4",
                max_pool_connections=20,
                connect_timeout=5,
                read_timeout=30,
                retries={"max_attempts": 3, "mode": "standard"},
                s3={"addressing_style": "path"},
            ),
        )
    )
    app.state.rustfs_client = rustfs_client

    response = await rustfs_client.list_buckets()
    logger.info(
        "RustFS connection successful, buckets=%d",
        len(response.get("Buckets", [])),
    )


async def close_rustfs() -> None:
    await rustfs_exit_stack.aclose()
    logger.info("RustFS connections closed")


def get_rustfs(request: Request) -> S3Client:
    return request.app.state.rustfs_client


RustFSClient = Annotated[
    S3Client,
    Depends(get_rustfs),
]
