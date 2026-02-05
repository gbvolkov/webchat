from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional

import httpx

DEFAULT_BASE_URL = os.environ.get("OPENAI_PROXY_BASE_URL", "http://127.0.0.1:8084")
DEFAULT_MODEL = os.environ.get("OPENAI_PROXY_MODEL", "simple_agent")
DEFAULT_USER = os.environ.get("OPENAI_PROXY_USER", "cli-user")

EXIT_COMMANDS = {"exit", "/exit", "/quit", "quit"}
RESET_COMMANDS = {"/reset", "reset"}
MULTILINE_START_COMMANDS = {"/multi", "/multiline", "<<<"}
MULTILINE_END_COMMANDS = {"/send", "/end", ">>>"}
MULTILINE_CANCEL_COMMANDS = {"/cancel", "/abort"}


def _stream_chat(
    *,
    base_url: str,
    payload: dict,
    show_status: bool,
) -> tuple[Optional[str], str]:
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    headers = {"Accept": "text/event-stream", "Content-Type": "application/json"}
    timeout = httpx.Timeout(connect=10.0, read=None, write=30.0, pool=None)
    assistant_chunks: list[str] = []
    conversation_id: Optional[str] = None

    with httpx.stream("POST", url, headers=headers, json=payload, timeout=timeout) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line:
                continue
            if isinstance(line, bytes):
                line = line.decode("utf-8", errors="ignore")
            if line.startswith(":"):
                if show_status:
                    sys.stdout.write(".")
                    sys.stdout.flush()
                continue
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue
            if "error" in event:
                err = event["error"]
                message = err.get("message") if isinstance(err, dict) else str(err)
                sys.stderr.write(f"\n[error] {message}\n")
                sys.stderr.flush()
                continue
            if conversation_id is None:
                conversation_id = event.get("conversation_id")
            choices = event.get("choices") or []
            delta_content = None
            if choices:
                delta = choices[0].get("delta") or {}
                delta_content = delta.get("content")
                if delta_content:
                    sys.stdout.write(delta_content)
                    sys.stdout.flush()
                    assistant_chunks.append(delta_content)
            if show_status and not delta_content:
                agent_status = event.get("agent_status")
                if agent_status:
                    sys.stdout.write(f"\n[{agent_status}]\n")
                    sys.stdout.flush()

    assistant_text = "".join(assistant_chunks).strip()
    return conversation_id, assistant_text


def _send_message(
    *,
    base_url: str,
    model: str,
    user: Optional[str],
    conversation_id: Optional[str],
    messages: list[dict],
    show_status: bool,
) -> tuple[Optional[str], str]:
    payload: dict = {"model": model, "messages": messages, "stream": True}
    if user:
        payload["user"] = user
    if conversation_id:
        payload["conversation_id"] = conversation_id

    try:
        new_conversation_id, assistant_text = _stream_chat(
            base_url=base_url,
            payload=payload,
            show_status=show_status,
        )
    except httpx.HTTPStatusError as exc:
        body = exc.response.text.strip()
        sys.stderr.write(f"\nRequest failed ({exc.response.status_code}): {body}\n")
        sys.stderr.flush()
        return conversation_id, ""

    if new_conversation_id:
        conversation_id = new_conversation_id
    return conversation_id, assistant_text


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactive streaming client for openai_proxy (/v1/chat/completions)."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Proxy base URL.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Agent id to call.")
    parser.add_argument("--user", default=DEFAULT_USER, help="User id for proxy.")
    parser.add_argument(
        "--conversation-id",
        default=None,
        help="Reuse existing conversation id (optional).",
    )
    parser.add_argument("--system", default=None, help="Optional system prompt.")
    parser.add_argument(
        "--show-status",
        action="store_true",
        help="Print agent status events and heartbeat dots.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    messages: list[dict] = []
    if args.system:
        messages.append({"role": "system", "content": args.system})

    conversation_id: Optional[str] = args.conversation_id
    print(f"Streaming chat via {args.base_url} (model={args.model}).")
    print("Type /exit to quit, /reset to clear local history, /multi for multiline (end with /send).\n")

    try:
        while True:
            user_input = input("You> ").strip()
            if not user_input:
                continue
            user_input_lower = user_input.lower()
            if user_input_lower in EXIT_COMMANDS:
                print("Goodbye!")
                return 0
            if user_input_lower in RESET_COMMANDS:
                messages = [{"role": "system", "content": args.system}] if args.system else []
                conversation_id = None
                print("Local history cleared.\n")
                continue
            if user_input_lower in MULTILINE_START_COMMANDS:
                user_input = _collect_multiline_input()
                if user_input is None:
                    print("Goodbye!")
                    return 0
                if not user_input:
                    print("Canceled.\n")
                    continue

            messages.append({"role": "user", "content": user_input})
            conversation_id, assistant_text = _send_message(
                base_url=args.base_url,
                model=args.model,
                user=args.user,
                conversation_id=conversation_id,
                messages=messages,
                show_status=args.show_status,
            )
            if assistant_text:
                messages.append({"role": "assistant", "content": assistant_text})
            print("\n")
    except KeyboardInterrupt:
        print("\nGoodbye!")
        return 0


def _collect_multiline_input() -> Optional[str]:
    print("Multiline mode: finish with /send, cancel with /cancel.")
    lines: list[str] = []
    while True:
        line = input("...> ")
        cmd = line.strip().lower()
        if cmd in EXIT_COMMANDS:
            return None
        if cmd in MULTILINE_CANCEL_COMMANDS:
            return ""
        if cmd in MULTILINE_END_COMMANDS:
            break
        lines.append(line)
    return "\n".join(lines).strip()


if __name__ == "__main__":
    raise SystemExit(main())
