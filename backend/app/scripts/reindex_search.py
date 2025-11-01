from __future__ import annotations

import asyncio
from typing import Iterable

from sqlmodel import Session, select

from app.core.config import get_settings
from app.db.models import Message, Thread
from app.db.session import engine
from app.services.embeddings import EmbeddingService
from app.services.search_index import SearchIndexService
from app.services.vector_store import VectorStoreService


async def _reindex(batch_size: int) -> None:
    settings = get_settings()

    if not settings.search_enabled:
        raise RuntimeError("Search is disabled; enable CHAT_SEARCH_ENABLED to reindex.")

    embedding_service = EmbeddingService(
        model_name=settings.embedding_model_name,
        batch_size=settings.embedding_batch_size,
        device=settings.embedding_device,
    )
    vector_store = VectorStoreService(persist_directory=settings.chroma_persist_directory)
    vector_store.delete_all()
    index_service = SearchIndexService(embedding_service=embedding_service, vector_store=vector_store)

    with Session(engine) as session:
        query = (
            select(Message, Thread)
            .join(Thread, Message.thread_id == Thread.id)
            .where(Thread.is_deleted.is_(False))
            .order_by(Message.created_at)
        )
        results = session.exec(query)

        batch_messages: list[tuple[Message, Thread]] = []
        async for message, thread in _iterate_async(results):
            batch_messages.append((message, thread))
            if len(batch_messages) >= batch_size:
                await _index_batch(index_service, batch_messages)
                batch_messages.clear()

        if batch_messages:
            await _index_batch(index_service, batch_messages)


async def _iterate_async(iterable: Iterable[tuple[Message, Thread]]):
    for item in iterable:
        yield item
        await asyncio.sleep(0)


async def _index_batch(index_service: SearchIndexService, batch: list[tuple[Message, Thread]]) -> None:
    for message, thread in batch:
        await index_service.index_message(
            message=message,
            thread=thread,
            model_label=(thread.attributes or {}).get("model_label"),
        )


def main() -> None:
    settings = get_settings()
    batch_size = max(settings.embedding_batch_size, 8)
    asyncio.run(_reindex(batch_size=batch_size))


if __name__ == "__main__":
    main()
