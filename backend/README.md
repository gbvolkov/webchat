# GWP Chat Backend

FastAPI implementation of the chat REST API described in `docs/???-???_??????_???????.pdf`.

## Quick start

```bash
cd backend
python -m venv .venv
.venv\Scriptsctivate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8009 --reload
```

The service exposes a health check at `GET /health` and the chat API under the `/api` prefix (default URL: `http://localhost:8009/api`).

### Frontend preview

To exercise the API with the bundled Vue frontend:

```bash
cd ..
npm install
npm run dev
```

This boots Vite on `http://localhost:5173` and proxies API calls to the backend URL configured in `.env` (`VITE_API_BASE_URL`).

## Configuration

Environment variables use the `CHAT_` prefix:

| Variable | Default | Description |
| --- | --- | --- |
| `CHAT_DATABASE_URL` | `sqlite:///./app.db` | SQLAlchemy connection string. |
| `CHAT_API_PREFIX` | `/api` | API router prefix. |
| `CHAT_LLM_ENABLED` | `true` | Toggle OpenAI-compatible integration. Set to `false` to accept messages without calling the provider. |
| `CHAT_LLM_API_BASE` | `None` | Optional override for the OpenAI-compatible API base URL. |
| `CHAT_LLM_API_SCHEME` | `http` | URL scheme when composing the base URL from host/port. |
| `CHAT_LLM_API_HOST` | `127.0.0.1` | Host used to reach the OpenAI-compatible API. |
| `CHAT_LLM_API_PORT` | `8080` | Port used to reach the OpenAI-compatible API. |
| `CHAT_LLM_API_PATH_PREFIX` | `/v1` | Path prefix added to provider requests (keeps compatibility with OpenAI endpoints). |
| `CHAT_LLM_API_KEY` | `None` | Optional bearer token passed as `Authorization` header. |
| `CHAT_LLM_TIMEOUT_SECONDS` | `30.0` | HTTP timeout used for chat-completion requests. |
| `CHAT_SEARCH_ENABLED` | `true` | Toggle embedding-based search and indexing. |
| `CHAT_EMBEDDING_MODEL_NAME` | `intfloat/multilingual-e5-large` | Hugging Face model used for embeddings. |
| `CHAT_EMBEDDING_BATCH_SIZE` | `8` | Batch size for embedding generation. |
| `CHAT_EMBEDDING_DEVICE` | `None` | Optional device override passed to SentenceTransformer (e.g. `cuda`). |
| `CHAT_CHROMA_PERSIST_DIRECTORY` | `./.chroma` | Directory for ChromaDB persistence. |
| `CHAT_SEARCH_MIN_SIMILARITY` | `0.3` | Minimum cosine similarity for semantic search results. |
| `CHAT_JWT_SECRET_KEY` | `change-me` | HMAC secret used to sign access and refresh tokens. |
| `CHAT_JWT_ALGORITHM` | `HS256` | JWT signing algorithm. |
| `CHAT_ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access token lifetime (minutes). |
| `CHAT_REFRESH_TOKEN_EXPIRE_MINUTES` | `10080` | Refresh token lifetime (minutes). |
| `CHAT_JWT_ISSUER` | `gwp-chat` | Issuer claim asserted in generated tokens. |
| `CHAT_JWT_AUDIENCE` | `None` | Optional audience claim validated on inbound tokens. |

The frontend retrieves model options from `GET /api/models`, backed by the same OpenAI-compatible service (defaults to `http://127.0.0.1:8080`). You can provide a comma-separated fallback list through `VITE_OPENAI_FALLBACK_MODELS`; its first entry is used when the provider is unavailable or returns an empty set. Supplying `CHAT_LLM_API_BASE` overrides the host/port settings for all provider calls.

Values can be stored in `backend/.env` (ignored by git).

## REST endpoints

Every protected endpoint expects an `Authorization: Bearer <access_token>` header issued by the auth service described below.

### Authentication

- `POST /api/auth/register` – create the first user (open while the table is empty, then restricted to `admin` users).
- `POST /api/auth/login` – exchange username/password for an access/refresh token pair.
- `POST /api/auth/refresh` – mint a new pair from a valid refresh token.
- `POST /api/auth/logout` – rotate the caller’s token version and revoke outstanding tokens.
- `GET /api/auth/me` – fetch the current user profile and permissions.

### Threads & messaging

- `POST /api/threads` – create a thread for the authenticated user.
- `GET /api/threads` – list threads (pagination: `page`, `limit`; excludes deleted by default).
- `GET /api/threads/{thread_id}` – fetch thread details with the latest messages.
- `PATCH /api/threads/{thread_id}` – update title/summary/metadata or soft-delete flag.
- `DELETE /api/threads/{thread_id}` – soft delete a thread.
- `GET /api/threads/{thread_id}/messages` – paginated messages ordered by `created_at` desc.
- `POST /api/threads/{thread_id}/messages` – enqueue a new message (accepts both `sender_id` and `user_id`; the backend enforces the caller’s identity).
- `POST /api/threads/{thread_id}/messages/stream` – stream assistant output over Server-Sent Events (SSE).
- `PATCH /api/threads/{thread_id}/messages/{message_id}` – update status or text.

### Providers, models, and search

- `GET /api/models` – fetch the list of models exposed by the OpenAI-compatible provider.
- `GET /api/provider-threads/{thread_id}` – retrieve persisted provider state (e.g., conversation id) for a thread.
- `PUT /api/provider-threads/{thread_id}` – upsert provider state for a given thread.
- `POST /api/search/threads` – semantic/regex hybrid search across chats, optionally filtered by model id.

### Vector search index

Semantic search relies on [ChromaDB](https://www.trychroma.com/) and Hugging Face's `intfloat/multilingual-e5-large` model to embed messages. Indexing happens automatically when messages are created or threads are soft-deleted. To rebuild the index from scratch:

```bash
cd backend
python -m app.scripts.reindex_search
```

Ensure the model weights are available (the command downloads them from Hugging Face on first run).

### Bootstrapping users

When the `users` table is empty you can create the first account by calling `POST /api/auth/register`. Subsequent registrations require an authenticated user with the `admin` role. Tokens are signed JWTs (`CHAT_JWT_SECRET_KEY` + `CHAT_JWT_ALGORITHM`); send the access token with every request using the `Authorization: Bearer <token>` header.

User records carry per-product and per-agent allow lists. When thread metadata contains `product_id` or `agent_id`, the backend enforces that the caller is allowed to interact with those resources.

### Streaming responses (SSE)

`POST /api/threads/{thread_id}/messages/stream` returns `text/event-stream`. Each event is a `data: <json>\n\n` line, and the stream ends with `data: [DONE]\n\n`.

Behavior:
- The backend sends an initial `queued` chunk, followed by a `running` chunk.
- While the provider is running, it emits a `running` heartbeat every ~10 seconds.
- Provider chunks are forwarded as-is (OpenAI-compatible `chat.completion.chunk` payloads).
- If the provider does not end with `agent_status="completed"` or `"interrupted"`, the backend emits a final `completed` chunk.
- On errors, it emits a `failed` chunk and a JSON error payload, then `[DONE]`.

Full example stream (including a typical provider chunk with assistant content):

```
data: {"id":"<thread_id>","object":"chat.completion.chunk","agent_status":"queued","choices":[{"delta":{},"finish_reason":null}]}

data: {"id":"<thread_id>","object":"chat.completion.chunk","agent_status":"running","choices":[{"delta":{},"finish_reason":null}]}

data: {"id":"resp-1","object":"chat.completion.chunk","model":"theodor_agent","conversation_id":"conv-123","agent_status":"streaming","choices":[{"index":0,"delta":{"role":"assistant","content":"Hello"},"finish_reason":null}]}

data: {"id":"resp-1","object":"chat.completion.chunk","model":"theodor_agent","conversation_id":"conv-123","agent_status":"streaming","choices":[{"index":0,"delta":{"content":" world"},"finish_reason":null}]}

data: {"id":"resp-1","object":"chat.completion.chunk","model":"theodor_agent","conversation_id":"conv-123","agent_status":"completed","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":12,"completion_tokens":5,"total_tokens":17}}

data: [DONE]
```

Failure example (error event after `failed` status):

```
data: {"id":"<thread_id>","object":"chat.completion.chunk","agent_status":"failed","choices":[{"delta":{},"finish_reason":"error"}]}

data: {"error":{"message":"LLM provider error","type":"agent_error"}}

data: [DONE]
```

## Running tests

```bash
cd backend
pytest
```

Tests run against a temporary SQLite database (`backend/app/tests/test_app.db`).
