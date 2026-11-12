from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from models.document_chunk import DocumentChunk
from schemas.document_index import DocumentChunkData


class DocumentChunkRepository:
    @staticmethod
    async def replace(
        session: AsyncSession,
        document_id: int,
        chunks: list[DocumentChunkData],
        embeddings: list[list[float]],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")

        await session.execute(
            delete(DocumentChunk).where(
                DocumentChunk.document_id == document_id,
            ),
        )
        session.add_all(
            [
                DocumentChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    document_version=chunk.document_version,
                    chunk_index=chunk.chunk_index,
                    heading=chunk.heading,
                    heading_path=chunk.heading_path,
                    content=chunk.content,
                    embedding_content=chunk.embedding_content,
                    content_hash=chunk.content_hash,
                    char_count=chunk.char_count,
                    embedding_model=settings.embedding_model,
                    embedding=embedding,
                )
                for chunk, embedding in zip(chunks, embeddings, strict=True)
            ],
        )
        await session.flush()

    @staticmethod
    async def delete(
        session: AsyncSession,
        document_id: int,
    ) -> None:
        await session.execute(
            delete(DocumentChunk).where(
                DocumentChunk.document_id == document_id,
            ),
        )
