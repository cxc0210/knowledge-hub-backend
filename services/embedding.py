import httpx

from core.config import settings


class EmbeddingResponseError(RuntimeError):
    pass


class EmbeddingService:
    @staticmethod
    async def embed_documents(
        client: httpx.AsyncClient,
        texts: list[str],
    ) -> list[list[float]]:
        embeddings: list[list[float]] = []
        batch_size = settings.embedding_batch_size

        for offset in range(0, len(texts), batch_size):
            batch = texts[offset : offset + batch_size]
            response = await client.post(
                "/api/embed",
                json={
                    "model": settings.embedding_model,
                    "input": batch,
                    "truncate": False,
                },
            )
            response.raise_for_status()
            batch_embeddings = response.json().get("embeddings")
            if not isinstance(batch_embeddings, list) or len(
                batch_embeddings,
            ) != len(batch):
                raise EmbeddingResponseError(
                    "embedding service returned an unexpected batch size",
                )

            for embedding in batch_embeddings:
                if (
                    not isinstance(embedding, list)
                    or len(embedding) != settings.embedding_dimension
                ):
                    raise EmbeddingResponseError(
                        "embedding service returned an unexpected dimension",
                    )
                embeddings.append([float(value) for value in embedding])

        return embeddings
