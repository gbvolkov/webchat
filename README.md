# GWP Chat

GWP Chat is a two-part application that delivers an AI-assisted chat experience for end users and service operators. The project combines a Vue 3 + TypeScript frontend with a FastAPI backend that brokers conversations with an OpenAI-compatible provider, supports attachment uploads, and streams responses to the browser in real time.

---

## Repository Layout

```
├── README.md                # This document
├── backend/                 # FastAPI application
│   ├── README.md            # Backend-specific documentation
│   └── app/…
├── docs/                    # Product and architecture notes
├── src/                     # Frontend source (Vue 3 + TypeScript)
│   ├── api/                 # Axios instance and API clients
│   ├── domain/              # Domain-centric stores, services, and mappers
│   ├── ui/                  # Component tree (widgets, pages, shared UI)
│   └── …
└── package.json             # Frontend scripts and dependencies
```

---

## Prerequisites

| Component | Version | Notes |
| --- | --- | --- |
| Node.js | 20.19+ | Required for the Vite dev server and build pipeline |
| npm | 10+ | Ships with Node 20, used for dependency management |
| Python | 3.11+ | Required for the FastAPI backend |
| Redis (optional) | — | Only needed if you run the OpenAI proxy in queue mode |

> **Tip:** Use the `.nvmrc` and `.node-version` files to align your Node.js version.

---

## Frontend Quick Start

```bash
# Install dependencies
npm install

# Start the Vite development server (http://localhost:5173)
npm run dev

# Type-check without emitting
npm run type-check

# Lint and format helpers
npm run lint
npm run format
```

Configuration lives in `.env` (example values):

```
VITE_API_BASE_URL=http://localhost:8009/api
VITE_OPENAI_FALLBACK_MODELS=gpt-4o-mini,gpt-4o
```

The UI embeds the `deep-chat` widget with a custom skin, supports drag-and-drop attachments, and streams assistant responses as they arrive.

### Authentication

The frontend now relies on the backend's JWT endpoints. After booting the backend, you can either hit `POST /api/auth/register` manually (the endpoint remains open until the first account is created) or use the "Create account" toggle on the `/login` screen. Once signed in, tokens are persisted in `localStorage`, refreshed automatically, and attached to every API call via the `Authorization: Bearer` header. Use the "Sign out" action in the sidebar menu to clear the session.


---

## Backend Quick Start

```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate        # On PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Run FastAPI with auto-reload
uvicorn app.main:app --host 0.0.0.0 --port 8009 --reload
```

The backend exposes the REST API under `/api` and serves health checks on `/health`. Configuration is driven by environment variables prefixed with `CHAT_` (see `backend/README.md` for the full catalog). Notable features include:

- Support for streaming chat completions with status pulses (`queued → running → streaming → completed`).
- Attachment ingestion and transformation into multimodal prompts.
- Optional semantic search backed by ChromaDB + multilingual-e5 embeddings.
- Detailed HTTP tracing (requests, responses, SSE chunks) when `app.main` is in use.

Run the backend test suite with:

```bash
cd backend
pytest
```

---

## Deployment Guide

This section covers a minimal production deployment where the backend runs behind a process manager (e.g., Gunicorn or Uvicorn + systemd) and the built frontend is served as static assets (e.g., via Nginx).

### 1. Prepare Environment

1. Provision a server (Linux preferred) with Node.js 20+, Python 3.11+, and your process manager of choice.
2. Create dedicated directories, e.g. `/opt/gwp-chat` (application) and `/var/lib/gwp-chat` (data).
3. Copy the repository or configure CI/CD to push the code into `/opt/gwp-chat`.
4. Create a dedicated Python virtual environment:
   ```bash
   cd /opt/gwp-chat/backend
   python -m venv .venv
   . .venv/bin/activate
   pip install -r requirements.txt
   ```
5. Populate environment variables (for example `/etc/gwp-chat/backend.env`):
   ```ini
   CHAT_DATABASE_URL=sqlite:////var/lib/gwp-chat/app.db
   CHAT_LLM_API_BASE=https://your-openai-proxy/v1
   CHAT_LLM_API_KEY=your-secret-token
   CHAT_SEARCH_ENABLED=true
   CHAT_LOG_LEVEL=INFO
   ```

### 2. Build the Frontend

```bash
cd /opt/gwp-chat
npm install
npm run build
```

The compiled assets land in `dist/`. Copy them to your web root (e.g., `/var/www/gwp-chat`) or configure a static file server to point to this directory. When served behind Nginx, a typical location block looks like:

```nginx
location / {
    root   /var/www/gwp-chat;
    try_files $uri $uri/ /index.html;
}
```

Ensure the frontend `.env` is updated to call the production backend URL before you run `npm run build`.

### 3. Run the Backend

Below is an example systemd unit that launches Uvicorn with multiple workers and reads the environment file prepared earlier.

```
[Unit]
Description=GWP Chat API
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/gwp-chat/backend
EnvironmentFile=/etc/gwp-chat/backend.env
ExecStart=/opt/gwp-chat/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8009 --workers 4
Restart=on-failure
User=www-data
Group=www-data

[Install]
WantedBy=multi-user.target
```

Reload systemd and enable the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now gwp-chat.service
```

If you prefer Gunicorn:

```bash
/opt/gwp-chat/backend/.venv/bin/gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8009
```

Proxy traffic through Nginx (or a load balancer) to `localhost:8009`, and configure HTTPS termination at the proxy layer. Don’t forget to forward `X-Forwarded-*` headers if your provider logic depends on them.

### 4. Static Assets + Caching

- Serve `dist/` with aggressive caching for hashed assets (`/assets/*.js`, `/assets/*.css`).
- Disable caching for `index.html` so redeploys take effect immediately.
- If you expose `/docs` or other static artifacts, add separate location blocks with appropriate cache policies.

### 5. Observability & Logging

- The middleware in `app.main` logs every HTTP request/response and SSE chunk. Pipe stdout to your logging stack (journald, Loki, ELK, etc.).
- For health probes, use `/health`. For smoke tests, send a minimal `POST /api/threads/{id}/messages/stream` with a short prompt.
- Monitor database size and ChromaDB indices if semantic search is enabled.

---

## Troubleshooting

| Symptom | Potential Cause | Suggested Fix |
| --- | --- | --- |
| Attachments silently ignored | `VITE_API_BASE_URL` misconfigured | Confirm the frontend calls the correct backend URL |
| Streaming stops at `running` | LLM proxy timed out | Increase `CHAT_LLM_TIMEOUT_SECONDS` or inspect proxy logs |
| Frontend missing styles or attachment button | Props renamed or cached build | Rebuild (`npm run build`) and ensure camelCase props stay intact |
| 502 errors from backend | Upstream LLM failure | Check backend logs; the detailed error text is now propagated |

---

## Additional Resources

- `backend/README.md` — complete backend configuration reference.
- `docs/` — domain logic, chat flow diagrams, and product documentation.
- `src/ui/widget/chat/Chat.vue` — entry point for the chat widget customization.

If you plan to extend the platform (new integrations, branding updates, enhanced search), review the domain modules under `src/domain` and the API client definitions under `src/api` before making changes.

---

**Happy building!** The combination of streaming UI, fully instrumented backend, and modular domain design should make it straightforward to tailor GWP Chat to your organisation’s needs. If you have questions or spot opportunities for improvement, update the docs and open issues so the next person benefits. 


