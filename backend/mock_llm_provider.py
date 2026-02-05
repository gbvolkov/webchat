from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI()


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": "mock-model",
                "object": "model",
                "owned_by": "mock",
            }
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(payload: dict):
    if payload.get("stream"):
        async def event_stream():
            response_id = "mock-resp-1"
            conversation_id = "mock-conv-1"
            chunks = [
                {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "model": "mock-model",
                    "conversation_id": conversation_id,
                    "agent_status": "streaming",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"role": "assistant", "content": "Hello"},
                            "finish_reason": None,
                        }
                    ],
                },
                {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "model": "mock-model",
                    "conversation_id": conversation_id,
                    "agent_status": "streaming",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": " world"},
                            "finish_reason": None,
                        }
                    ],
                },
                {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "model": "mock-model",
                    "conversation_id": conversation_id,
                    "agent_status": "completed",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 5,
                        "completion_tokens": 2,
                        "total_tokens": 7,
                    },
                },
            ]
            for chunk in chunks:
                yield f"data: {json.dumps(chunk)}\n\n"
                await asyncio.sleep(0.2)
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    return JSONResponse(
        {
            "id": "mock-resp-1",
            "object": "chat.completion",
            "model": "mock-model",
            "conversation_id": "mock-conv-1",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello world"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8090, log_level="info")
