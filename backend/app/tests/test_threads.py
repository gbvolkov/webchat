import inspect
import os
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

# Configure isolated database before importing the app modules.
TEST_DB_PATH = Path("app/tests/test_app.db")
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

os.environ["CHAT_DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ.setdefault("CHAT_SEARCH_ENABLED", "false")

from app.main import app  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.api.deps import get_chat_service, get_optional_search_index_service, get_search_index_service  # noqa: E402
from app.services.llm import ChatCompletionResult, LLMServiceError, ProviderModelCard  # noqa: E402
from app.services.search_index import SearchMatch, SearchResultSet  # noqa: E402
from sqlmodel import Session, select  # noqa: E402
from app.db.models import User  # noqa: E402
from app.services.auth import AuthService  # noqa: E402
from app.core.config import get_settings  # noqa: E402


class SuccessfulStubLLM:
    def __init__(self):
        self.calls = 0
        self.chunk_attachments: list[dict[str, object]] | None = None

    async def create_completion(
        self,
        *,
        model: str,
        messages,
        user=None,
        conversation_id=None,
        stream=False,
        on_status=None,
        on_chunk=None,
    ):
        self.calls += 1
        if on_status:
            for status in ("queued", "running", "streaming", "completed"):
                result = on_status(status)
                if inspect.isawaitable(result):
                    await result
        if on_chunk:
            chunk_payload = {
                "agent_status": "streaming",
                "choices": [
                    {
                        "delta": {
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "Hello from ass"}],
                        }
                    },
                    {
                        "delta": {
                            "content": [{"type": "output_text", "text": "istant"}],
                        }
                    },
                ],
            }
            if self.chunk_attachments:
                chunk_payload["message_metadata"] = {"attachments": self.chunk_attachments}
            result = on_chunk(chunk_payload)
            if inspect.isawaitable(result):
                await result
        conversation = conversation_id or "conv-1"
        return ChatCompletionResult(
            response_id="resp-1",
            content="Hello from assistant",
            role="assistant",
            model=model,
            conversation_id=conversation,
            usage={
                "prompt_tokens": 4,
                "completion_tokens": 6,
                "total_tokens": 10,
            },
        )

    async def list_models(self):
        return [
            ProviderModelCard(id="stub-model", name="Stub Model"),
            ProviderModelCard(id="stub-model-2", name="Stub Model 2"),
        ]


class FailingStubLLM:
    async def create_completion(
        self,
        *,
        model: str,
        messages,
        user=None,
        conversation_id=None,
        stream=False,
        on_status=None,
        on_chunk=None,
    ):  # pragma: no cover - keeps signature explicit
        raise LLMServiceError("LLM failure")

    async def list_models(self):  # pragma: no cover
        raise LLMServiceError("LLM failure")


class InterruptStubLLM:
    async def create_completion(
        self,
        *,
        model: str,
        messages,
        user=None,
        conversation_id=None,
        stream=False,
        on_status=None,
        on_chunk=None,
    ):
        return ChatCompletionResult(
            response_id="resp-int",
            content="Can you clarify?",
            role="assistant",
            model=model,
            conversation_id=conversation_id or "conv-int",
            usage={
                "prompt_tokens": 5,
                "completion_tokens": 3,
                "total_tokens": 8,
            },
            metadata={
                "interrupt_id": "int-1",
                "interrupt_payload": {
                    "interrupt_id": "int-1",
                    "question": "Can you clarify?",
                    "content": "Detailed interrupt content",
                },
            },
            agent_status="interrupted",
        )

    async def list_models(self):
        return [ProviderModelCard(id="stub-model", name="Stub Model")]


class StubSearchIndex:
    def __init__(self):
        self.messages: dict[str, dict[str, str | None]] = {}

    async def index_message(self, *, message, thread, model_label=None):
        attributes = thread.attributes or {}
        self.messages[str(message.id)] = {
            "thread_id": str(thread.id),
            "text": message.text,
            "model": attributes.get("model"),
        }

    async def delete_thread(self, thread_id: str) -> None:
        self.messages = {mid: data for mid, data in self.messages.items() if data.get("thread_id") != thread_id}

    async def search(self, *, user_id: str, phrase: str, model_id: str | None, limit: int) -> SearchResultSet:
        phrase_lower = phrase.lower()
        results: list[SearchMatch] = []
        seen_threads: set[str] = set()
        for data in self.messages.values():
            model = data.get("model")
            if model_id and model != model_id:
                continue
            text = data.get("text") or ""
            if phrase_lower in text.lower():
                thread_id = data.get("thread_id")
                if thread_id and thread_id not in seen_threads:
                    seen_threads.add(thread_id)
                    results.append(SearchMatch(thread_id=thread_id, similarity=1.0))
                    if len(results) >= limit:
                        break
        return SearchResultSet(
            matches=results,
            best_similarity=1.0 if results else None,
            similarity_threshold=1.0 if results else None,
            best_distance=0.0 if results else None,
            distance_threshold=0.0 if results else None,
            min_similarity=0.3,
        )


@pytest.fixture(autouse=True)
def cleanup_db():
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink(missing_ok=True)
    yield
    engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink(missing_ok=True)


TEST_USERNAME = "test-user"
TEST_PASSWORD = "test-pass"
TEST_EMAIL = "test@example.com"


def authenticate_client(
    client: TestClient,
    *,
    roles: list[str] | None = None,
    allowed_products: list[str] | None = None,
    allowed_agents: list[str] | None = None,
) -> User:
    auth_service = AuthService()
    with Session(engine) as db:
        user = User(
            username=TEST_USERNAME,
            email=TEST_EMAIL,
            password_hash=auth_service.hash_password(TEST_PASSWORD),
            roles=roles or ["admin"],
            allowed_products=allowed_products or [],
            allowed_agents=allowed_agents or [],
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    login_resp = client.post(
        "/api/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert login_resp.status_code == 200, login_resp.text
    access_token = login_resp.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {access_token}"})
    return user


def test_thread_crud_flow():
    stub = SuccessfulStubLLM()
    search_stub = StubSearchIndex()
    app.dependency_overrides[get_chat_service] = lambda: stub
    app.dependency_overrides[get_search_index_service] = lambda: search_stub
    app.dependency_overrides[get_optional_search_index_service] = lambda: search_stub
    try:
        with TestClient(app) as client:
            user = authenticate_client(client)
            create_payload = {"title": "My first thread", "metadata": {"topic": "demo"}}
            create_resp = client.post("/api/threads", json=create_payload)
            assert create_resp.status_code == 201, create_resp.text
            thread = create_resp.json()
            assert thread["title"] == "My first thread"
            assert thread["metadata"]["topic"] == "demo"
            thread_id = thread["id"]
            UUID(thread_id)  # validate UUID format

            list_resp = client.get("/api/threads")
            assert list_resp.status_code == 200
            data = list_resp.json()
            assert data["pagination"]["total"] == 0
            assert len(data["items"]) == 0

            patch_resp = client.patch(f"/api/threads/{thread_id}", json={"summary": "Updated"})
            assert patch_resp.status_code == 200
            assert patch_resp.json()["summary"] == "Updated"

            message_payload = {
                "text": "Hello!",
                "user_id": str(user.id),
                "model": "stub-model",
                "model_label": "Stub Model",
            }
            message_resp = client.post(f"/api/threads/{thread_id}/messages", json=message_payload)
            assert message_resp.status_code == 201, message_resp.text
            message_data = message_resp.json()
            assert message_data["status"] == "ready"
            assert message_data["tokens_count"] == 4
            assert message_data["attachments"] == []

            list_resp_after_message = client.get("/api/threads")
            assert list_resp_after_message.json()["pagination"]["total"] == 1
            assert len(list_resp_after_message.json()["items"]) == 1

            messages_resp = client.get(f"/api/threads/{thread_id}/messages")
            assert messages_resp.status_code == 200
            messages = messages_resp.json()
            assert messages["pagination"]["total"] == 2
            assistant_message = messages["items"][0]
            user_message = messages["items"][1]
            assert assistant_message["sender_type"] == "assistant"
            assert assistant_message["status"] == "ready"
            assert assistant_message["text"] == "Hello from assistant"
            assert assistant_message["attachments"] == []
            assert user_message["status"] == "ready"
            assert user_message["text"] == "Hello!"
            assert user_message["attachments"] == []

            thread_detail = client.get(f"/api/threads/{thread_id}")
            assert thread_detail.status_code == 200
            detail_json = thread_detail.json()
            assert detail_json["metadata"]["model"] == "stub-model"
            assert detail_json["metadata"]["model_label"] == "Stub Model"
            assert detail_json["title"] == "Stub Model: Hello!"

            provider_state_resp = client.get(f"/api/provider-threads/{thread_id}")
            assert provider_state_resp.status_code == 200
            provider_state = provider_state_resp.json()
            assert provider_state["conversation_id"] == "conv-1"
            assert provider_state["provider"] == "openai-compatible"

            delete_resp = client.delete(f"/api/threads/{thread_id}")
            assert delete_resp.status_code == 204

            list_resp_after = client.get("/api/threads")
            assert list_resp_after.json()["pagination"]["total"] == 0
    finally:
        app.dependency_overrides.pop(get_search_index_service, None)
        app.dependency_overrides.pop(get_optional_search_index_service, None)
        app.dependency_overrides.pop(get_chat_service, None)
        engine.dispose()


def test_create_message_llm_failure_returns_502():
    app.dependency_overrides[get_chat_service] = lambda: FailingStubLLM()
    search_stub = StubSearchIndex()
    app.dependency_overrides[get_search_index_service] = lambda: search_stub
    app.dependency_overrides[get_optional_search_index_service] = lambda: search_stub
    try:
        with TestClient(app) as client:
            user = authenticate_client(client)
            create_resp = client.post("/api/threads", json={"title": "Broken"})
            assert create_resp.status_code == 201, create_resp.text
            thread_id = create_resp.json()["id"]

            message_payload = {"text": "Ping", "user_id": str(user.id), "model": "stub-model"}
            message_resp = client.post(f"/api/threads/{thread_id}/messages", json=message_payload)
            assert message_resp.status_code == 502

            messages_resp = client.get(f"/api/threads/{thread_id}/messages")
            assert messages_resp.status_code == 200
            messages = messages_resp.json()["items"]
            assert len(messages) == 1
            stored_message = messages[0]
            assert stored_message["status"] == "error"
            assert stored_message["error_code"] == "LLM failure"
    finally:
        app.dependency_overrides.pop(get_search_index_service, None)
        app.dependency_overrides.pop(get_optional_search_index_service, None)
        app.dependency_overrides.pop(get_chat_service, None)
        engine.dispose()


def test_list_models_success():
    app.dependency_overrides[get_chat_service] = lambda: SuccessfulStubLLM()
    search_stub = StubSearchIndex()
    app.dependency_overrides[get_search_index_service] = lambda: search_stub
    app.dependency_overrides[get_optional_search_index_service] = lambda: search_stub
    try:
        with TestClient(app) as client:
            authenticate_client(client)
            response = client.get("/api/models")
            assert response.status_code == 200
            data = response.json()
            assert data["models"] == ["stub-model", "stub-model-2"]
            assert data["cards"][0]["name"] == "Stub Model"
    finally:
        app.dependency_overrides.pop(get_search_index_service, None)
        app.dependency_overrides.pop(get_optional_search_index_service, None)
        app.dependency_overrides.pop(get_chat_service, None)
        engine.dispose()


def test_list_models_failure_returns_502():
    app.dependency_overrides[get_chat_service] = lambda: FailingStubLLM()
    search_stub = StubSearchIndex()
    app.dependency_overrides[get_search_index_service] = lambda: search_stub
    app.dependency_overrides[get_optional_search_index_service] = lambda: search_stub
    try:
        with TestClient(app) as client:
            authenticate_client(client)
            response = client.get("/api/models")
            assert response.status_code == 502
            assert response.json()["detail"] == "LLM failure"
    finally:
        app.dependency_overrides.pop(get_search_index_service, None)
        app.dependency_overrides.pop(get_optional_search_index_service, None)
        app.dependency_overrides.pop(get_chat_service, None)
        engine.dispose()


def test_first_message_sets_default_title():
    stub = SuccessfulStubLLM()
    app.dependency_overrides[get_chat_service] = lambda: stub
    try:
        with TestClient(app) as client:
            user = authenticate_client(client)
            create_resp = client.post("/api/threads", json={})
            assert create_resp.status_code == 201
            thread_id = create_resp.json()["id"]

            question = "How do I configure integration settings for deployment?"
            message_payload = {
                "text": question,
                "user_id": str(user.id),
                "model": "stub-model",
                "model_label": "Stub Model",
            }
            post_resp = client.post(f"/api/threads/{thread_id}/messages", json=message_payload)
            assert post_resp.status_code == 201

            detail_resp = client.get(f"/api/threads/{thread_id}")
            assert detail_resp.status_code == 200
            preview = question[:32].rstrip()
            expected_title = f"Stub Model: {preview}"
            assert detail_resp.json()["title"] == expected_title
    finally:
        app.dependency_overrides.pop(get_chat_service, None)
        engine.dispose()


def test_provider_thread_state_upsert_route():
    stub = SuccessfulStubLLM()
    app.dependency_overrides[get_chat_service] = lambda: stub
    try:
        with TestClient(app) as client:
            authenticate_client(client)
            create_resp = client.post("/api/threads", json={"title": "Stateful"})
            thread_id = create_resp.json()["id"]

            put_payload = {
                "provider": "test-provider",
                "conversation_id": "abc-123",
                "payload": {"foo": "bar"},
            }
            put_resp = client.put(f"/api/provider-threads/{thread_id}", json=put_payload)
            assert put_resp.status_code == 200
            data = put_resp.json()
            assert data["conversation_id"] == "abc-123"
            assert data["payload"] == {"foo": "bar"}

            get_resp = client.get(f"/api/provider-threads/{thread_id}", params={"provider": "test-provider"})
            assert get_resp.status_code == 200
            assert get_resp.json()["conversation_id"] == "abc-123"
    finally:
        app.dependency_overrides.pop(get_chat_service, None)
        engine.dispose()


def test_provider_attachments_persisted_and_returned():
    stub = SuccessfulStubLLM()
    stub.chunk_attachments = [
        {
            "type": "file",
            "filename": "report.xlsx",
            "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "bytes": 2048,
            "storage_filename": "report_storage.xlsx",
            "download_url": "/api/attachments/report_storage.xlsx",
        }
    ]
    search_stub = StubSearchIndex()
    app.dependency_overrides[get_chat_service] = lambda: stub
    app.dependency_overrides[get_search_index_service] = lambda: search_stub
    app.dependency_overrides[get_optional_search_index_service] = lambda: search_stub
    try:
        with TestClient(app) as client:
            user = authenticate_client(client)
            thread_resp = client.post("/api/threads", json={"title": "Attachments"})
            thread_id = thread_resp.json()["id"]
            message_payload = {
                "text": "Please attach report",
                "user_id": str(user.id),
                "model": "stub-model",
            }
            message_resp = client.post(f"/api/threads/{thread_id}/messages", json=message_payload)
            assert message_resp.status_code == 201

            history_resp = client.get(f"/api/threads/{thread_id}/messages")
            assert history_resp.status_code == 200
            messages = history_resp.json()["items"]
            assistant_message = messages[0]
            assert assistant_message["attachments"], "Expected assistant attachments in history response"
            attachment = assistant_message["attachments"][0]
            assert attachment["filename"] == "report.xlsx"
            assert attachment["download_url"] == "/api/attachments/report_storage.xlsx"
            assert attachment["size_bytes"] == 2048
            assert attachment["data_base64"] is None
    finally:
        app.dependency_overrides.pop(get_search_index_service, None)
        app.dependency_overrides.pop(get_optional_search_index_service, None)
        app.dependency_overrides.pop(get_chat_service, None)
        engine.dispose()


def test_conversation_id_reused_between_messages():
    stub = SuccessfulStubLLM()
    recorded_conversation_ids: list[str | None] = []

    original_create_completion = stub.create_completion

    async def tracking_completion(**kwargs):
        recorded_conversation_ids.append(kwargs.get("conversation_id"))
        return await original_create_completion(**kwargs)

    stub.create_completion = tracking_completion  # type: ignore[assignment]
    search_stub = StubSearchIndex()
    app.dependency_overrides[get_chat_service] = lambda: stub
    app.dependency_overrides[get_search_index_service] = lambda: search_stub
    app.dependency_overrides[get_optional_search_index_service] = lambda: search_stub

    try:
        with TestClient(app) as client:
            user = authenticate_client(client)
            create_resp = client.post("/api/threads", json={"title": "Conv"})
            thread_id = create_resp.json()["id"]

            message_payload = {"text": "Hi", "user_id": str(user.id), "model": "stub-model"}
            client.post(f"/api/threads/{thread_id}/messages", json=message_payload)
            client.post(f"/api/threads/{thread_id}/messages", json=message_payload)

            assert recorded_conversation_ids[0] is None
            assert recorded_conversation_ids[1] == "conv-1"
    finally:
        app.dependency_overrides.pop(get_search_index_service, None)
        app.dependency_overrides.pop(get_optional_search_index_service, None)
        app.dependency_overrides.pop(get_chat_service, None)
        engine.dispose()


def test_interrupt_metadata_persisted_and_exposed():
    stub = InterruptStubLLM()
    search_stub = StubSearchIndex()
    app.dependency_overrides[get_chat_service] = lambda: stub
    app.dependency_overrides[get_search_index_service] = lambda: search_stub
    app.dependency_overrides[get_optional_search_index_service] = lambda: search_stub

    try:
        with TestClient(app) as client:
            user = authenticate_client(client)
            create_resp = client.post("/api/threads", json={"title": "Interrupt"})
            thread_id = create_resp.json()["id"]

            message_payload = {"text": "Please clarify", "user_id": str(user.id), "model": "stub-model"}
            post_resp = client.post(f"/api/threads/{thread_id}/messages", json=message_payload)
            assert post_resp.status_code == 201

            history_resp = client.get(f"/api/threads/{thread_id}/messages")
            assert history_resp.status_code == 200
            items = history_resp.json()["items"]
            assert len(items) == 2
            assistant_message = items[0]
            user_message = items[1]
            assert assistant_message["sender_type"] == "assistant"
            assert assistant_message["metadata"]["interrupt_id"] == "int-1"
            assert assistant_message["text"] == "Detailed interrupt content"
            assert user_message["metadata"] == {}
    finally:
        app.dependency_overrides.pop(get_search_index_service, None)
        app.dependency_overrides.pop(get_optional_search_index_service, None)
        app.dependency_overrides.pop(get_chat_service, None)
        engine.dispose()


def test_search_threads_filters_by_phrase_and_model():
    stub = SuccessfulStubLLM()
    search_stub = StubSearchIndex()
    app.dependency_overrides[get_chat_service] = lambda: stub
    app.dependency_overrides[get_search_index_service] = lambda: search_stub
    app.dependency_overrides[get_optional_search_index_service] = lambda: search_stub
    try:
        with TestClient(app) as client:
            user = authenticate_client(client)
            # create first thread and message containing target phrase
            create_resp = client.post("/api/threads", json={})
            thread_id = create_resp.json()["id"]
            message_payload = {
                "text": "Integration settings deployment guide",
                "user_id": str(user.id),
                "model": "stub-model",
                "model_label": "Stub Model",
            }
            client.post(f"/api/threads/{thread_id}/messages", json=message_payload)

            # create another thread with different model and different text
            other_resp = client.post("/api/threads", json={})
            other_thread_id = other_resp.json()["id"]
            other_payload = {
                "text": "General question",
                "user_id": str(user.id),
                "model": "stub-model-2",
                "model_label": "Stub Model 2",
            }
            client.post(f"/api/threads/{other_thread_id}/messages", json=other_payload)

            search_payload = {"phrase": "integration", "model_id": "stub-model"}
            search_resp = client.post("/api/search/threads", json=search_payload)
            assert search_resp.status_code == 200
            results = search_resp.json()
            assert results["pagination"]["total"] == 1
            assert results["items"][0]["thread"]["id"] == thread_id
            assert results["items"][0]["similarity"] == pytest.approx(1.0)
            assert results["best_similarity"] == pytest.approx(1.0)
            assert results["similarity_threshold"] == pytest.approx(1.0)
            assert results["best_distance"] == pytest.approx(0.0)
            assert results["distance_threshold"] == pytest.approx(0.0)
            assert results["min_similarity"] == pytest.approx(0.3)

            search_all_resp = client.post("/api/search/threads", json={"phrase": "integration"})
            assert search_all_resp.status_code == 200
            results_all = search_all_resp.json()
            assert results_all["pagination"]["total"] == 1
            assert results_all["items"][0]["thread"]["id"] == thread_id

            # invalid regex should return 400
            invalid_resp = client.post("/api/search/threads", json={"phrase": "["})
            assert invalid_resp.status_code == 400
    finally:
        app.dependency_overrides.pop(get_search_index_service, None)
        app.dependency_overrides.pop(get_optional_search_index_service, None)
        app.dependency_overrides.pop(get_chat_service, None)
        engine.dispose()


def test_delete_thread_marks_as_deleted():
    stub = SuccessfulStubLLM()
    search_stub = StubSearchIndex()
    app.dependency_overrides[get_chat_service] = lambda: stub
    app.dependency_overrides[get_search_index_service] = lambda: search_stub
    app.dependency_overrides[get_optional_search_index_service] = lambda: search_stub
    try:
        with TestClient(app) as client:
            authenticate_client(client)
            create_resp = client.post("/api/threads", json={"title": "To delete"})
            assert create_resp.status_code == 201
            thread_id = create_resp.json()["id"]

            delete_resp = client.delete(f"/api/threads/{thread_id}")
            assert delete_resp.status_code == 204

            list_resp = client.get("/api/threads")
            assert list_resp.status_code == 200
            assert list_resp.json()["pagination"]["total"] == 0

            detail_resp = client.get(f"/api/threads/{thread_id}")
            assert detail_resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_search_index_service, None)
        app.dependency_overrides.pop(get_optional_search_index_service, None)
        app.dependency_overrides.pop(get_chat_service, None)
        engine.dispose()


def test_download_attachment_endpoint_serves_files():
    settings = get_settings()
    storage_dir = Path(settings.attachments_storage_dir).expanduser()
    storage_dir.mkdir(parents=True, exist_ok=True)
    filename = "stored_report_123.txt"
    file_path = storage_dir / filename
    file_contents = b"example attachment payload"
    file_path.write_bytes(file_contents)
    try:
        with TestClient(app) as client:
            authenticate_client(client)
            response = client.get(f"/api/attachments/{filename}")
            assert response.status_code == 200
            assert response.content == file_contents
            disposition = response.headers.get("content-disposition", "")
            assert filename in disposition
    finally:
        file_path.unlink(missing_ok=True)
