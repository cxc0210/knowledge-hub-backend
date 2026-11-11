import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from config import settings
from database import engine
from mongodb import mongo_client, mongo_database
from routers.auth import router as auth_router
from routers.document import router as document_router
from routers.document_content import router as document_content_router
from routers.user import router as user_router

# log格式设置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


# 检测数据库连接是否成功
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.mongo_database = mongo_database

    try:
        # 测试 PostgreSQL
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            logger.info("PostgreSQL connection successful")

        # 测试 MongoDB
        await mongo_database.command("ping")
        logger.info("MongoDB connection successful")

        yield
    finally:
        await engine.dispose()
        await mongo_client.close()
        logger.info("Database connections closed")


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
app.include_router(document_router)
app.include_router(document_content_router)
app.include_router(user_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Knowledge Hub API is running"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
