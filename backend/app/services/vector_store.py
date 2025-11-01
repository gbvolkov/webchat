from __future__ import annotations

from typing import Any, Sequence

try:
    import chromadb  # type: ignore[import]
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
    chromadb = None  # type: ignore[assignment]
    _CHROMADB_IMPORT_ERROR = exc
else:  # pragma: no branch
    _CHROMADB_IMPORT_ERROR = None

if chromadb is not None:  # pragma: no branch - satisfied when dependency installed
    from chromadb.api import ClientAPI
    from chromadb.api.models.Collection import Collection
else:
    ClientAPI = Collection = Any  # type: ignore[assignment]


class VectorStoreService:
    """ChromaDB wrapper to store and query chat message embeddings."""

    def __init__(
        self,
        *,
        persist_directory: str,
        collection_name: str = "chat_messages",
    ) -> None:
        if chromadb is None:  # pragma: no cover - exercised when dependency missing
            raise RuntimeError(
                "ChromaDB is required for search features. Install the 'chromadb' package "
                "or disable search by setting CHAT_SEARCH_ENABLED=false."
            ) from _CHROMADB_IMPORT_ERROR
        self._persist_directory = persist_directory
        self._collection_name = collection_name
        self._client: ClientAPI = chromadb.PersistentClient(path=persist_directory)
        self._collection: Collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert_messages(
        self,
        *,
        ids: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        documents: Sequence[str],
        metadatas: Sequence[dict[str, Any]],
    ) -> None:
        if not ids:
            return
        self._collection.upsert(
            ids=list(ids),
            embeddings=list(embeddings),
            documents=list(documents),
            metadatas=list(metadatas),
        )

    def delete_thread(self, thread_id: str) -> None:
        self._collection.delete(where={"thread_id": thread_id})

    def delete_all(self) -> None:
        self._client.delete_collection(name=self._collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def query(
        self,
        *,
        embedding: Sequence[float],
        owner_id: str,
        model_id: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        where: dict[str, Any]
        owner_clause: dict[str, Any] = {"owner_id": {"$eq": owner_id}}
        if model_id:
            model_clause: dict[str, Any] = {"model": {"$eq": model_id}}
            where = {"$and": [owner_clause, model_clause]}
        else:
            where = owner_clause

        return self._collection.query(
            query_embeddings=[list(embedding)],
            n_results=max(limit, 1),
            where=where,
            include=["metadatas", "distances"],
        )
