from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.db.models import Message, Thread
from app.services.embeddings import EmbeddingService
from app.services.vector_store import VectorStoreService


@dataclass(slots=True)
class SearchMatch:
    thread_id: str
    similarity: float
    message_id: str | None = None


@dataclass(slots=True)
class SearchResultSet:
    matches: list[SearchMatch]
    best_similarity: float | None
    similarity_threshold: float | None
    best_distance: float | None
    distance_threshold: float | None
    min_similarity: float


class SearchIndexService:
    """Coordinates embedding generation and vector store operations."""

    def __init__(
        self,
        *,
        embedding_service: EmbeddingService,
        vector_store: VectorStoreService,
        min_similarity: float = 0.3,
    ) -> None:
        self._embeddings = embedding_service
        self._vector_store = vector_store
        self._min_similarity = min_similarity

    async def index_message(
        self,
        *,
        message: Message,
        thread: Thread,
        model_label: str | None = None,
    ) -> None:
        embeddings = await self._embeddings.embed_texts([message.text])
        if not embeddings:
            return

        attributes = thread.attributes or {}
        metadata = {
            "thread_id": str(thread.id),
            "model": attributes.get("model"),
            "model_label": model_label or attributes.get("model_label"),
            "sender_type": message.sender_type.value if hasattr(message.sender_type, "value") else str(message.sender_type),
            "owner_id": thread.owner_id,
            "message_id": str(message.id),
        }

        self._vector_store.upsert_messages(
            ids=[str(message.id)],
            embeddings=embeddings,
            documents=[message.text],
            metadatas=[metadata],
        )

    async def delete_thread(self, thread_id: str) -> None:
        self._vector_store.delete_thread(thread_id)

    async def search(
        self,
        *,
        user_id: str,
        phrase: str,
        model_id: str | None,
        limit: int,
    ) -> SearchResultSet:
        embeddings = await self._embeddings.embed_texts([phrase])
        if not embeddings:
            return SearchResultSet(
                matches=[],
                best_similarity=None,
                similarity_threshold=None,
                best_distance=None,
                distance_threshold=None,
                min_similarity=self._min_similarity,
            )
        result = self._vector_store.query(
            embedding=embeddings[0],
            owner_id=user_id,
            model_id=model_id,
            limit=max(limit * 4, limit),
        )

        distances = (result.get("distances") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]

        matches: list[SearchMatch] = []
        seen_threads: set[str] = set()

        for idx, metadata in enumerate(metadatas):
            thread_id = metadata.get("thread_id")
            if not thread_id or thread_id in seen_threads:
                continue
            seen_threads.add(thread_id)
            distance = float(distances[idx]) if idx < len(distances) else 1.0
            similarity = max(0.0, 1.0 - distance)
            message_id = metadata.get("message_id")
            matches.append(SearchMatch(thread_id=thread_id, similarity=similarity, message_id=message_id))
            if len(matches) >= limit:
                break

        if not matches:
            return SearchResultSet(
                matches=[],
                best_similarity=None,
                similarity_threshold=None,
                best_distance=None,
                distance_threshold=None,
                min_similarity=self._min_similarity,
            )

        matches = [match for match in matches if match.similarity >= self._min_similarity]
        if not matches:
            return SearchResultSet(
                matches=[],
                best_similarity=None,
                similarity_threshold=None,
                best_distance=None,
                distance_threshold=None,
                min_similarity=self._min_similarity,
            )

        distances_filtered = [1.0 - match.similarity for match in matches]
        best_distance = min(distances_filtered)
        distance_threshold = best_distance * 1.25
        matches = [
            match for match in matches
            if (1.0 - match.similarity) <= distance_threshold
        ]
        if not matches:
            return SearchResultSet(
                matches=[],
                best_similarity=None,
                similarity_threshold=None,
                best_distance=best_distance,
                distance_threshold=distance_threshold,
                min_similarity=self._min_similarity,
            )

        best_similarity = max(match.similarity for match in matches)
        similarity_threshold = max(0.0, 1.0 - distance_threshold)

        return SearchResultSet(
            matches=matches,
            best_similarity=best_similarity,
            similarity_threshold=similarity_threshold,
            best_distance=best_distance,
            distance_threshold=distance_threshold,
            min_similarity=self._min_similarity,
        )
