from typing import Annotated, Any

from fastapi import Depends, Request
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from config import settings

MongoDocument = dict[str, Any]


def get_mongodb(
    request: Request,
) -> AsyncDatabase[MongoDocument]:
    return request.app.state.mongo_database


mongo_client = AsyncMongoClient[MongoDocument](
    settings.mongodb_url,
    maxPoolSize=20,
    minPoolSize=1,
    maxIdleTimeMS=60_000,
    waitQueueTimeoutMS=5_000,
    serverSelectionTimeoutMS=5_000,
    tz_aware=True,
)

mongo_database = mongo_client[settings.mongodb_database]


MongoDatabase = Annotated[
    AsyncDatabase[MongoDocument],
    Depends(get_mongodb),
]
