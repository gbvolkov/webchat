from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.api.routes.models import router as models_router
from app.api.routes.provider_threads import router as provider_threads_router
from app.api.routes.search import router as search_router
from app.api.routes.threads import router as threads_router
from app.core.config import get_settings
from app.db.session import init_db
from app.services.embeddings import EmbeddingService
from app.services.llm import OpenAIChatService
from app.services.search_index import SearchIndexService
from app.services.vector_store import VectorStoreService

settings = get_settings()


def configure_logging(level: str) -> None:
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    if not root_logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s"
        )
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(logger_name).setLevel(numeric_level)


configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    llm_service: OpenAIChatService | None = None
    embedding_service: EmbeddingService | None = None
    vector_store_service: VectorStoreService | None = None
    search_index_service: SearchIndexService | None = None
    if settings.llm_enabled:
        llm_service = OpenAIChatService(
            api_base=settings.llm_effective_base_url,
            api_key=settings.llm_api_key,
            timeout_seconds=settings.llm_timeout_seconds,
            trace_enabled=settings.llm_trace_enabled,
        )
        app.state.llm_service = llm_service
    else:
        app.state.llm_service = None

    if settings.search_enabled:
        embedding_service = EmbeddingService(
            model_name=settings.embedding_model_name,
            batch_size=settings.embedding_batch_size,
            device=settings.embedding_device,
        )
        vector_store_service = VectorStoreService(
            persist_directory=settings.chroma_persist_directory,
        )
        search_index_service = SearchIndexService(
            embedding_service=embedding_service,
            vector_store=vector_store_service,
            min_similarity=settings.search_min_similarity,
        )
        app.state.embedding_service = embedding_service
        app.state.vector_store_service = vector_store_service
        app.state.search_index_service = search_index_service
    else:
        app.state.embedding_service = None
        app.state.vector_store_service = None
        app.state.search_index_service = None

    try:
        yield
    finally:
        if llm_service is not None:
            await llm_service.aclose()
            app.state.llm_service = None
        if search_index_service is not None:
            app.state.search_index_service = None
        if vector_store_service is not None:
            app.state.vector_store_service = None
        if embedding_service is not None:
            app.state.embedding_service = None


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


http_logger = logging.getLogger("app.http")


@app.middleware("http")
async def log_http_traffic(request: Request, call_next):
    """
    Log incoming HTTP requests and outgoing responses, including streaming responses.
    """
    body_bytes = await request.body()
    body_text = body_bytes.decode("utf-8", errors="ignore")
    headers_in = dict(request.headers)
    http_logger.info(
        "Incoming request: method=%s url=%s headers=%s body=%s",
        request.method,
        str(request.url),
        headers_in,
        body_text,
    )

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": body_bytes, "more_body": False}

    wrapped_request = Request(request.scope, receive)
    response = await call_next(wrapped_request)
    headers_out = dict(response.headers)

    is_streaming = hasattr(response, "body_iterator") and not hasattr(response, "body")

    if isinstance(response, StreamingResponse) or is_streaming:
        original_iterator = response.body_iterator

        async def logging_iterator():
            async for chunk in original_iterator:
                chunk_text = (
                    chunk.decode("utf-8", errors="ignore")
                    if isinstance(chunk, (bytes, bytearray))
                    else str(chunk)
                )
                http_logger.info(
                    "Outgoing streaming response chunk: status=%s chunk=%s",
                    response.status_code,
                    chunk_text,
                )
                yield chunk

        response.body_iterator = logging_iterator()
        http_logger.info(
            "Outgoing streaming response: status=%s headers=%s",
            response.status_code,
            headers_out,
        )
        return response

    body_out = getattr(response, "body", b"") or b""
    if not isinstance(body_out, (bytes, bytearray)):
        body_out = str(body_out).encode("utf-8")
    body_out_text = body_out.decode("utf-8", errors="ignore")
    http_logger.info(
        "Outgoing response: status=%s headers=%s body=%s",
        response.status_code,
        headers_out,
        body_out_text,
    )
    return response


@app.get("/health", tags=["health"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(models_router, prefix=settings.api_prefix)
app.include_router(provider_threads_router, prefix=settings.api_prefix)
app.include_router(search_router, prefix=settings.api_prefix)
app.include_router(threads_router, prefix=settings.api_prefix)
