from __future__ import annotations

import os

import uvicorn

os.environ.setdefault("CHAT_DATABASE_URL", "sqlite:///./app_stream_check.db")
os.environ.setdefault("CHAT_LLM_API_BASE", "http://127.0.0.1:8090/v1")
os.environ.setdefault("CHAT_SEARCH_ENABLED", "false")
os.environ.setdefault("CHAT_LOG_LEVEL", "INFO")

uvicorn.run("app.main:app", host="127.0.0.1", port=8011, log_level="info")
