from __future__ import annotations

import inspect
import json
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal, Sequence

import httpx


class LLMServiceError(RuntimeError):
    """Raised when the LLM provider cannot fulfil a request."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
        error_type: str | None = None,
        request_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.error_type = error_type
        self.request_id = request_id
        self.extra = dict(extra) if extra else {}


ChatRole = Literal["system", "user", "assistant"]


@dataclass(slots=True)
class ChatPromptMessage:
    role: ChatRole
    parts: list[dict[str, Any]]


@dataclass(slots=True)
class ChatCompletionResult:
    response_id: str
    content: str
    role: ChatRole
    model: str
    conversation_id: str | None
    usage: dict[str, int | None]


@dataclass(slots=True)
class ProviderModelCard:
    id: str
    name: str | None = None


logger = logging.getLogger(__name__)


class OpenAIChatService:
    """Thin wrapper around an OpenAI-compatible chat completions endpoint."""

    StatusCallback = Callable[[str], Awaitable[None] | None]
    ChunkCallback = Callable[[dict[str, Any]], Awaitable[None] | None]

    def __init__(
        self,
        *,
        api_base: str,
        api_key: str | None,
        timeout_seconds: float,
        trace_enabled: bool = True,
    ) -> None:
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._request_timeout = httpx.Timeout(
            connect=timeout_seconds,
            read=timeout_seconds,
            write=timeout_seconds,
            pool=timeout_seconds,
        )
        self._stream_timeout = httpx.Timeout(
            connect=timeout_seconds,
            read=None,
            write=timeout_seconds,
            pool=timeout_seconds,
        )
        self._client = httpx.AsyncClient(
            base_url=api_base.rstrip("/"),
            headers=headers,
            timeout=self._request_timeout,
        )
        self._trace_enabled = trace_enabled
        self._trace_level = logging.INFO
        self._trace("Trace logging enabled for OpenAIChatService base_url=%s", self._client.base_url)

    async def create_completion(
        self,
        *,
        model: str,
        messages: Sequence[ChatPromptMessage],
        user: str | None = None,
        conversation_id: str | None = None,
        stream: bool = False,
        on_status: StatusCallback | None = None,
        on_chunk: ChunkCallback | None = None,
    ) -> ChatCompletionResult:
        payload = {
            "model": model,
            "messages": [
                {"role": message.role, "content": message.parts}
                for message in messages
            ],
        }
        if user:
            payload["user"] = user
        if conversation_id:
            payload["conversation_id"] = conversation_id
        if stream:
            payload["stream"] = True

        self._trace(
            "create_completion called: model=%s stream=%s user=%s conversation_id=%s message_count=%s",
            model,
            stream,
            user,
            conversation_id,
            len(messages),
        )
        self._log_request("chat.completions", payload)
        safe_headers = dict(self._client.headers)
        if "Authorization" in safe_headers:
            safe_headers["Authorization"] = "***redacted***"
        
        ##logging without file data
        redacted_payload = {
            **payload,
            "messages": [
                {
                    **message,
                    "content": [
                        (
                            {k: v for k, v in part.items() if k != "data"}
                            if isinstance(part, dict)
                            else part
                        )
                        for part in message.get("content", [])
                    ],
                }
                for message in payload.get("messages", [])
            ],
        }
        logger.info(
            "OpenAI request dispatched: method=POST url=%s headers=%s payload=%s",
            str(self._client.base_url.join("chat/completions")),
            safe_headers,
            json.dumps(redacted_payload, ensure_ascii=False),
        )

        try:
            if stream:
                self._trace("Opening streaming request to chat/completions")
                async with self._client.stream(
                    "POST",
                    "chat/completions",
                    json=payload,
                    headers={"Accept": "text/event-stream"},
                    timeout=self._stream_timeout,
                ) as response:
                    self._trace(
                        "Streaming response opened: status=%s headers=%s",
                        response.status_code,
                        dict(response.headers),
                    )
                    logger.info(
                        "OpenAI streaming response opened: status=%s headers=%s",
                        response.status_code,
                        dict(response.headers),
                    )
                    if response.status_code >= 400:
                        await response.aread()
                        error_info = self._extract_error_info(response)
                        detail = error_info["message"]
                        self._trace_json("Streaming error info", error_info)
                        logger.warning(
                            "OpenAI-compatible API returned error status=%s detail=%s error_code=%s error_type=%s request_id=%s",
                            response.status_code,
                            detail,
                            error_info.get("error_code"),
                            error_info.get("error_type"),
                            error_info.get("request_id"),
                        )
                        logger.warning(
                            "OpenAI error response payload: %s",
                            json.dumps(error_info, ensure_ascii=False),
                        )
                        raise LLMServiceError(
                            detail,
                            status_code=response.status_code,
                            error_code=error_info.get("error_code"),
                            error_type=error_info.get("error_type"),
                            request_id=error_info.get("request_id"),
                            extra=error_info.get("extra"),
                        )

                    parser = _StreamingCompletionParser(
                        default_model=model,
                        status_callback=on_status,
                        trace_callback=self._trace if self._trace_enabled else None,
                    )
                    async for line in response.aiter_lines():
                        self._trace("Streaming raw line: %s", self._truncate_text(line, 500))
                        if not line or line.startswith(":"):
                            continue
                        if not line.startswith("data:"):
                            continue
                        payload_line = line[5:].strip()
                        logger.info("OpenAI streaming chunk received: %s", payload_line)
                        self._trace("Streaming payload line: %s", self._truncate_text(payload_line, 500))
                        if not payload_line:
                            continue
                        if payload_line == "[DONE]":
                            logger.info("OpenAI streaming completed with [DONE] sentinel")
                            self._trace("Received [DONE] sentinel from provider")
                            break
                        payload_obj = parser.parse_json(payload_line)
                        if payload_obj is None:
                            self._trace("Discarded streaming payload after failed JSON parse")
                            continue
                        self._trace_json("Streaming payload object", payload_obj)
                        if on_chunk is not None:
                            self._trace("Forwarding streaming chunk to caller callback")
                            chunk_result = on_chunk(payload_obj)
                            if inspect.isawaitable(chunk_result):
                                await chunk_result
                                self._trace("Caller chunk callback awaited successfully")
                        await parser.process_chunk(payload_obj)
                        self._trace("Streaming chunk processed successfully")
                result = parser.finalise()
                self._trace_json("Streaming final result", {
                    "response_id": result.response_id,
                    "role": result.role,
                    "model": result.model,
                    "conversation_id": result.conversation_id,
                    "usage": result.usage,
                })
                logger.info(
                    "Received OpenAI-compatible streaming response: model=%s response_id=%s role=%s conversation_id=%s status=%s",
                    result.model,
                    result.response_id,
                    result.role,
                    result.conversation_id,
                    parser.last_status,
                )
                if any(result.usage.values()):
                    logger.debug(
                        "OpenAI-compatible streaming usage metrics: prompt_tokens=%s completion_tokens=%s total_tokens=%s",
                        result.usage.get("prompt_tokens"),
                        result.usage.get("completion_tokens"),
                        result.usage.get("total_tokens"),
                    )
                return result

            response = await self._client.post("chat/completions", json=payload)
            self._trace(
                "Received non-streaming response metadata: status=%s headers=%s",
                response.status_code,
                dict(response.headers),
            )
            logger.info(
                "OpenAI response received: status=%s headers=%s body=%s",
                response.status_code,
                dict(response.headers),
                response.text,
            )
            if response.content:
                self._trace(
                    "Received non-streaming raw body size=%s bytes",
                    len(response.content),
                )
                if response.headers.get("content-type", "").startswith("application/json"):
                    try:
                        response_payload = response.json()
                    except ValueError:
                        response_payload = None
                else:
                    response_payload = None
                if response_payload is not None:
                    self._trace_json("Non-streaming response JSON", response_payload)
                else:
                    text_preview = self._truncate_text(response.text or "", 1000)
                    if text_preview:
                        self._trace("Non-streaming response text preview: %s", text_preview)
        except httpx.ReadTimeout as exc:
            logger.warning("LLM provider timed out while streaming model=%s", model)
            raise LLMServiceError(
                "LLM provider timed out while streaming response",
                error_type="timeout",
            ) from exc
        except httpx.HTTPError as exc:
            status_code = None
            request_id = None
            extra: dict[str, Any] | None = None
            response = getattr(exc, "response", None)
            if isinstance(response, httpx.Response):
                status_code = response.status_code
                request_id = OpenAIChatService._get_request_id(response)
                text_excerpt = OpenAIChatService._truncate_text(response.text or "", 400)
                if text_excerpt:
                    extra = {"response_text_excerpt": text_excerpt}
            logger.exception("Failed to reach OpenAI-compatible API for model %s", model)
            raise LLMServiceError(
                "Failed to reach LLM provider",
                status_code=status_code,
                error_type="transport_error",
                request_id=request_id,
                extra=extra,
            ) from exc

        if response.status_code >= 400:
            error_info = self._extract_error_info(response)
            self._trace_json("Non-streaming error info", error_info)
            detail = error_info["message"]
            logger.warning(
                "OpenAI-compatible API returned error status=%s detail=%s error_code=%s error_type=%s request_id=%s",
                response.status_code,
                detail,
                error_info.get("error_code"),
                error_info.get("error_type"),
                error_info.get("request_id"),
            )
            raise LLMServiceError(
                detail,
                status_code=response.status_code,
                error_code=error_info.get("error_code"),
                error_type=error_info.get("error_type"),
                request_id=error_info.get("request_id"),
                extra=error_info.get("extra"),
            )

        data = response.json()

        try:
            choice = data["choices"][0]
            message = choice["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMServiceError(
                "Malformed response from LLM provider",
                error_type="protocol_error",
            ) from exc

        content = message.get("content", "")
        role: ChatRole = message.get("role", "assistant")

        logger.info(
            "Received OpenAI-compatible response: model=%s response_id=%s role=%s conversation_id=%s",
            data.get("model", model),
            data.get("id"),
            role,
            data.get("conversation_id"),
        )

        usage_raw = data.get("usage") or {}
        usage: dict[str, int | None] = {
            "prompt_tokens": usage_raw.get("prompt_tokens"),
            "completion_tokens": usage_raw.get("completion_tokens"),
            "total_tokens": usage_raw.get("total_tokens"),
        }

        if usage_raw:
            logger.debug(
                "OpenAI-compatible usage metrics: prompt_tokens=%s completion_tokens=%s total_tokens=%s",
                usage.get("prompt_tokens"),
                usage.get("completion_tokens"),
                usage.get("total_tokens"),
            )

        result = ChatCompletionResult(
            response_id=data.get("id", ""),
            content=content,
            role=role,
            model=data.get("model", model),
            conversation_id=data.get("conversation_id"),
            usage=usage,
        )
        self._trace_json(
            "Non-streaming final result",
            {
                "response_id": result.response_id,
                "role": result.role,
                "model": result.model,
                "conversation_id": result.conversation_id,
                "usage": result.usage,
                "content_preview": self._truncate_text(result.content, 200),
            },
        )
        return result

    async def list_models(self) -> list[ProviderModelCard]:
        logger.info("Requesting OpenAI-compatible models catalog")
        try:
            response = await self._client.get("models")
        except httpx.HTTPError as exc:
            status_code = None
            request_id = None
            extra: dict[str, Any] | None = None
            response = getattr(exc, "response", None)
            if isinstance(response, httpx.Response):
                status_code = response.status_code
                request_id = OpenAIChatService._get_request_id(response)
                text_excerpt = OpenAIChatService._truncate_text(response.text or "", 400)
                if text_excerpt:
                    extra = {"response_text_excerpt": text_excerpt}
            logger.exception("Failed to reach OpenAI-compatible API while listing models")
            raise LLMServiceError(
                "Failed to reach LLM provider",
                status_code=status_code,
                error_type="transport_error",
                request_id=request_id,
                extra=extra,
            ) from exc

        if response.status_code >= 400:
            error_info = self._extract_error_info(response)
            detail = error_info["message"]
            logger.warning(
                "OpenAI-compatible API returned error during list_models status=%s detail=%s error_code=%s error_type=%s request_id=%s",
                response.status_code,
                detail,
                error_info.get("error_code"),
                error_info.get("error_type"),
                error_info.get("request_id"),
            )
            raise LLMServiceError(
                detail,
                status_code=response.status_code,
                error_code=error_info.get("error_code"),
                error_type=error_info.get("error_type"),
                request_id=error_info.get("request_id"),
                extra=error_info.get("extra"),
            )

        data = response.json()
        cards: list[ProviderModelCard] = []

        if isinstance(data, dict):
            items = data.get("data") or data.get("models")
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        model_id = item.get("id")
                        if isinstance(model_id, str):
                            cards.append(
                                ProviderModelCard(
                                    id=model_id,
                                    name=item.get("name") if isinstance(item.get("name"), str) else None,
                                )
                            )
                    elif isinstance(item, str):
                        cards.append(ProviderModelCard(id=item))
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    model_id = item.get("id")
                    if isinstance(model_id, str):
                        cards.append(
                            ProviderModelCard(
                                id=model_id,
                                name=item.get("name") if isinstance(item.get("name"), str) else None,
                            )
                        )
                elif isinstance(item, str):
                    cards.append(ProviderModelCard(id=item))
        elif isinstance(data, str):
            cards.append(ProviderModelCard(id=data))

        if not cards and isinstance(data, dict):
            legacy_models = data.get("models")
            if isinstance(legacy_models, list):
                for item in legacy_models:
                    if isinstance(item, str):
                        cards.append(ProviderModelCard(id=item))

        if not cards:
            raise LLMServiceError("LLM provider returned no models", error_type="empty_result")

        logger.info("Fetched %s OpenAI-compatible models", len(cards))

        return cards

    async def aclose(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _get_request_id(response: httpx.Response) -> str | None:
        request_id = response.headers.get("x-request-id")
        if isinstance(request_id, str):
            request_id = request_id.strip()
            if request_id:
                return request_id
        return None

    @staticmethod
    def _extract_error_info(response: httpx.Response) -> dict[str, Any]:
        status_code = response.status_code
        request_id = OpenAIChatService._get_request_id(response)
        default_message = f"LLM provider returned HTTP {status_code}"
        error_code: str | None = None
        error_type: str | None = None
        detail: str | None = None
        extra: dict[str, Any] = {}

        try:
            data = response.json()
        except ValueError:
            text_excerpt = OpenAIChatService._truncate_text(response.text or "", 400)
            if text_excerpt:
                detail = text_excerpt
                extra["response_text_excerpt"] = text_excerpt
            return {
                "message": detail or default_message,
                "error_code": error_code,
                "error_type": error_type,
                "request_id": request_id,
                "extra": extra or None,
            }

        if isinstance(data, dict):
            error_block = data.get("error")
            if isinstance(error_block, dict):
                message = error_block.get("message")
                if isinstance(message, str) and message.strip():
                    detail = message.strip()
                code = error_block.get("code")
                if isinstance(code, str) and code.strip():
                    error_code = code.strip()
                err_type = error_block.get("type")
                if isinstance(err_type, str) and err_type.strip():
                    error_type = err_type.strip()
                request_hint = error_block.get("request_id") or error_block.get("requestId")
                if isinstance(request_hint, str) and request_hint.strip():
                    request_id = request_hint.strip()
                remaining = {
                    key: value
                    for key, value in error_block.items()
                    if key not in {"message", "code", "type", "request_id", "requestId"}
                }
                if remaining:
                    extra["provider_error_context"] = remaining
            if detail is None:
                for key in ("detail", "message", "error_description", "error"):
                    candidate = data.get(key)
                    if isinstance(candidate, str) and candidate.strip():
                        detail = candidate.strip()
                        break

            excerpt_source = data
            try:
                excerpt_text = json.dumps(excerpt_source) if excerpt_source else ""
            except (TypeError, ValueError):
                excerpt_text = str(excerpt_source)
            excerpt_text = OpenAIChatService._truncate_text(excerpt_text, 400)
            if excerpt_text:
                extra["provider_response_excerpt"] = excerpt_text
        else:
            extra["provider_response_preview"] = OpenAIChatService._truncate_text(str(data), 200)

        if detail is None:
            detail = default_message

        return {
            "message": detail,
            "error_code": error_code,
            "error_type": error_type,
            "request_id": request_id,
            "extra": extra or None,
        }

    def _trace(self, message: str, *args: Any) -> None:
        if not self._trace_enabled:
            return
        logger.log(self._trace_level, "[TRACE] " + message, *args)

    def _trace_json(self, label: str, data: Any, *, max_length: int = 2000) -> None:
        if not self._trace_enabled:
            return
        serialised = self._serialise_for_log(data, max_length=max_length)
        logger.log(self._trace_level, "[TRACE] %s: %s", label, serialised)

    @staticmethod
    def _serialise_for_log(data: Any, *, max_length: int = 2000) -> str:
        if isinstance(data, bytes):
            text = data[: max_length].decode("utf-8", "replace")
        else:
            try:
                text = json.dumps(data, default=str, ensure_ascii=True)
            except (TypeError, ValueError):
                text = str(data)
        return OpenAIChatService._truncate_text(text, max_length)

    def _log_request(self, endpoint: str, payload: dict[str, Any]) -> None:
        self._trace("Preparing request to endpoint=%s", endpoint)
        self._trace_json("HTTP request payload", payload)
        messages = payload.get("messages") or []
        attachment_count = sum(
            1
            for message in messages
            for part in message.get("content", [])
            if isinstance(part, dict) and part.get("type") != "text"
        )
        logger.info(
            "Calling OpenAI-compatible API: endpoint=%s model=%s messages=%s attachments=%s user=%s conversation_id=%s",
            endpoint,
            payload.get("model"),
            len(messages),
            attachment_count,
            payload.get("user"),
            payload.get("conversation_id"),
        )
        if logger.isEnabledFor(logging.DEBUG):
            summaries: list[dict[str, Any]] = []
            for idx, message in enumerate(messages):
                parts = message.get("content") or []
                text_part = next(
                    (
                        part.get("text")
                        for part in parts
                        if isinstance(part, dict) and part.get("type") == "text"
                    ),
                    "",
                )
                text_preview = self._truncate_text(text_part)
                attachment_types = [
                    part.get("type")
                    for part in parts
                    if isinstance(part, dict) and part.get("type") != "text"
                ]
                summaries.append(
                    {
                        "idx": idx,
                        "role": message.get("role"),
                        "text_preview": text_preview,
                        "attachments": attachment_types,
                    }
                )
            logger.debug("OpenAI-compatible payload summary: %s", summaries)
            logger.debug("OpenAI-compatible payload raw: %s", payload)

    @staticmethod
    def _truncate_text(text: str, length: int = 120) -> str:
        if not isinstance(text, str):
            return ""
        sanitized = " ".join(text.split())
        if len(sanitized) <= length:
            return sanitized
        return f"{sanitized[: length - 3]}..."


class _StreamingCompletionParser:
    """Accumulate Server-Sent Event chunks into a completion result."""

    def __init__(
        self,
        *,
        default_model: str,
        status_callback: OpenAIChatService.StatusCallback | None,
        trace_callback: Callable[..., None] | None = None,
    ) -> None:
        self._default_model = default_model
        self._status_callback = status_callback
        self._trace_callback = trace_callback
        self._content_parts: list[str] = []
        self._role: ChatRole = "assistant"
        self._model: str | None = None
        self._response_id: str | None = None
        self._conversation_id: str | None = None
        self._usage: dict[str, int | None] = {
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
        }
        self._finish_reason: str | None = None
        self.last_status: str | None = None
        self._trace("Initialised streaming parser for model=%s", default_model)

    def parse_json(self, payload_line: str) -> dict[str, Any] | None:
        try:
            return json.loads(payload_line)
        except json.JSONDecodeError:
            logger.warning("Discarding malformed streaming payload: %s", payload_line)
        return None

    async def process_chunk(self, payload: dict[str, Any]) -> None:
        self._trace(
            "Processing streaming chunk keys=%s",
            list(payload.keys()),
        )
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str):
                message = message.strip() or None
            raw_code = error.get("code")
            error_code = raw_code.strip() if isinstance(raw_code, str) and raw_code.strip() else None
            raw_type = error.get("type")
            error_type = raw_type.strip() if isinstance(raw_type, str) and raw_type.strip() else None
            raw_request = error.get("request_id") or error.get("requestId")
            request_id = raw_request.strip() if isinstance(raw_request, str) and raw_request.strip() else None
            status_code = payload.get("status_code")
            if not isinstance(status_code, int):
                status_candidate = error.get("status")
                status_code = status_candidate if isinstance(status_candidate, int) else None
            remaining = {
                key: value
                for key, value in error.items()
                if key not in {"message", "code", "type", "request_id", "requestId", "status"}
            }
            raise LLMServiceError(
                message or "LLM provider streaming error",
                status_code=status_code,
                error_code=error_code,
                error_type=error_type,
                request_id=request_id,
                extra={"provider_error_context": remaining} if remaining else None,
            )

        status = payload.get("agent_status")
        if isinstance(status, str):
            self._trace("Emitting agent status from streaming chunk: %s", status)
            await self._emit_status(status)

        if isinstance(payload.get("id"), str):
            self._response_id = payload["id"]
            self._trace("Updated streaming response_id=%s", self._response_id)
        if isinstance(payload.get("model"), str):
            self._model = payload["model"]
            self._trace("Updated streaming model=%s", self._model)
        if isinstance(payload.get("conversation_id"), str):
            self._conversation_id = payload["conversation_id"]
            self._trace("Updated streaming conversation_id=%s", self._conversation_id)

        usage = payload.get("usage")
        if isinstance(usage, dict):
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                value = usage.get(key)
                if isinstance(value, int):
                    self._usage[key] = value
                    self._trace("Updated streaming usage %s=%s", key, value)

        choices = payload.get("choices")
        if isinstance(choices, list):
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                delta = choice.get("delta")
                if isinstance(delta, dict):
                    role = delta.get("role")
                    if isinstance(role, str):
                        self._role = role
                        self._trace("Updated streaming role via delta=%s", self._role)
                    self._ingest_content(delta.get("content"))
                message = choice.get("message")
                if isinstance(message, dict):
                    role = message.get("role")
                    if isinstance(role, str):
                        self._role = role
                        self._trace("Updated streaming role via message=%s", self._role)
                    self._ingest_content(message.get("content"))
                finish_reason = choice.get("finish_reason")
                if isinstance(finish_reason, str):
                    self._finish_reason = finish_reason
                    self._trace("Received finish_reason=%s", self._finish_reason)

    async def _emit_status(self, status: str) -> None:
        normalised = status.lower()
        if self.last_status == normalised:
            return
        self.last_status = normalised
        self._trace("Emitting status callback with status=%s", normalised)
        if self._status_callback is None:
            return
        result = self._status_callback(normalised)
        if inspect.isawaitable(result):
            await result

    def _ingest_content(self, content: Any) -> None:
        if isinstance(content, str):
            self._content_parts.append(content)
            self._trace("Appended streaming text content length=%s", len(content))
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    text = part.get("text")
                    if isinstance(text, str):
                        self._content_parts.append(text)
                        self._trace("Appended streaming text part length=%s", len(text))

    def finalise(self) -> ChatCompletionResult:
        if self._finish_reason and self._finish_reason not in {"stop", "length"}:
            logger.warning("LLM completion finished with reason=%s", self._finish_reason)
        return ChatCompletionResult(
            response_id=self._response_id or "",
            content="".join(self._content_parts),
            role=self._role,
            model=self._model or self._default_model,
            conversation_id=self._conversation_id,
            usage=self._usage,
        )

    def _trace(self, message: str, *args: Any) -> None:
        if self._trace_callback is None:
            return
        self._trace_callback(message, *args)
