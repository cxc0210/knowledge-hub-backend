from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from core.config import settings
from services.embedding import EmbeddingResponseError, EmbeddingService


class EmbeddingServiceTests(IsolatedAsyncioTestCase):
    async def test_batches_and_returns_expected_dimension(self) -> None:
        response = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "embeddings": [
                    [0.0] * settings.embedding_dimension,
                    [1.0] * settings.embedding_dimension,
                ],
            },
        )
        client = SimpleNamespace(post=AsyncMock(return_value=response))

        embeddings = await EmbeddingService.embed_documents(
            client,  # type: ignore[arg-type]
            ["第一段", "第二段"],
        )

        self.assertEqual(len(embeddings), 2)
        self.assertEqual(len(embeddings[0]), 1024)

    async def test_rejects_unexpected_dimension(self) -> None:
        response = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"embeddings": [[0.0, 1.0]]},
        )
        client = SimpleNamespace(post=AsyncMock(return_value=response))

        with self.assertRaises(EmbeddingResponseError):
            await EmbeddingService.embed_documents(
                client,  # type: ignore[arg-type]
                ["文本"],
            )
