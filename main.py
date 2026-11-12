import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from core.config import settings
from core.database import engine
from core.elasticsearch import close_elasticsearch, init_elasticsearch
from core.embedding import close_embedding, init_embedding
from core.mongodb import close_mongodb, init_mongodb
from core.rustfs import close_rustfs, init_rustfs
from routers.ai import router as ai_router
from routers.auth import router as auth_router
from routers.document import router as document_router
from routers.document_content import router as document_content_router
from routers.search import router as search_router
from routers.user import router as user_router
from services.document_index_worker import (
    close_document_index_worker,
    init_document_index_worker,
)

# log格式设置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


# 检测数据库连接是否成功
@asynccontextmanager
async def lifespan(app: FastAPI):

    try:
        # 测试 PostgreSQL
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            logger.info("PostgreSQL connection successful")

        # 测试 MongoDB
        await init_mongodb(app)

        # 测试 RustFS
        await init_rustfs(app)

        # 测试 Elasticsearch
        await init_elasticsearch(app)

        # 测试 Embedding 服务
        await init_embedding(app)

        # 启动文档索引后台任务
        await init_document_index_worker(app)

        yield
    finally:
        await close_document_index_worker(app)
        await close_embedding()
        await close_elasticsearch()
        await close_rustfs()
        await engine.dispose()
        await close_mongodb()


app = FastAPI(lifespan=lifespan)
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(auth_router)
app.include_router(ai_router)
app.include_router(document_router)
app.include_router(document_content_router)
app.include_router(search_router)
app.include_router(user_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Knowledge Hub API is running"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
