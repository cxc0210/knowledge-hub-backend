from datetime import UTC, datetime

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.asynchronous.database import AsyncDatabase

from mongodb import MongoDocument
from schemas.document_content import (
    DocumentContentCreate,
    DocumentContentResponse,
)

COLLECTION_NAME = "kh_document_content"


class InvalidDocumentContentIdError(Exception):
    pass


class DocumentContentNotFoundError(Exception):
    pass


class DocumentContentService:
    @staticmethod
    def _object_id(content_id: str) -> ObjectId:
        try:
            return ObjectId(content_id)
        except (InvalidId, TypeError) as error:
            raise InvalidDocumentContentIdError(
                f"content_id '{content_id}' is invalid",
            ) from error

    @staticmethod
    def _response(document: MongoDocument) -> DocumentContentResponse:
        return DocumentContentResponse(
            content_id=str(document["_id"]),
            content=document["content"],
            created_at=document["created_at"],
            updated_at=document["updated_at"],
        )

    @classmethod
    async def create(
        cls,
        database: AsyncDatabase[MongoDocument],
        document_create: DocumentContentCreate,
    ) -> DocumentContentResponse:
        now = datetime.now(UTC)
        document: MongoDocument = {
            "content": document_create.content,
            "created_at": now,
            "updated_at": now,
        }

        result = await database[COLLECTION_NAME].insert_one(document)
        document["_id"] = result.inserted_id
        return cls._response(document)

    @classmethod
    async def get(
        cls,
        database: AsyncDatabase[MongoDocument],
        content_id: str,
    ) -> DocumentContentResponse:
        document = await database[COLLECTION_NAME].find_one(
            {"_id": cls._object_id(content_id)},
        )

        if document is None:
            raise DocumentContentNotFoundError(
                f"document content '{content_id}' does not exist",
            )

        return cls._response(document)

    @classmethod
    async def delete(
        cls,
        database: AsyncDatabase[MongoDocument],
        content_id: str,
    ) -> None:
        result = await database[COLLECTION_NAME].delete_one(
            {"_id": cls._object_id(content_id)},
        )

        if result.deleted_count == 0:
            raise DocumentContentNotFoundError(
                f"document content '{content_id}' does not exist",
            )
