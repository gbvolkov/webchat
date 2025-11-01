from __future__ import annotations

import asyncio
from typing import Iterable

from sentence_transformers import SentenceTransformer


class EmbeddingService:
    """Wrapper around a SentenceTransformer model to produce text embeddings."""

    def __init__(
        self,
        *,
        model_name: str,
        batch_size: int = 8,
        device: str | None = None,
        normalize_embeddings: bool = True,
    ) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self.normalize_embeddings = normalize_embeddings
        self._model = SentenceTransformer(model_name, device=device)

    async def embed_texts(self, texts: Iterable[str]) -> list[list[float]]:
        items = list(texts)
        if not items:
            return []

        loop = asyncio.get_running_loop()
        embeddings = await loop.run_in_executor(
            None,
            self._encode,
            items,
        )
        return embeddings

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=self.normalize_embeddings,
            convert_to_numpy=True,
        )
        return vectors.tolist()
