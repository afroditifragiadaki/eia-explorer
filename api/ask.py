"""POST /ask: run the agent and stream every step to the browser as it happens.

The agent (src/agent.py) already produces its work as a sequence of events:
"I'm calling this tool", "here's a dataset", "here's a chart", "here's my
answer". This file sends each event to the browser the moment it exists,
using Server-Sent Events (SSE): a long-lived HTTP response that the server
keeps writing to, one small message at a time, like:

    event: tool_call
    data: {"name": "fetch_data", "args": {...}}

    event: text
    data: {"text": "New York rose from..."}

(each message ends with a blank line).
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Iterator

import anthropic
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.agent import run_session

router = APIRouter()

# Conversation history, kept in the server's memory: {conversation_id: messages}.
# Simple, but it is lost when the server restarts and it is not shared between
# several server processes. Moving it into Turso is on the TODO list.
CONVERSATIONS: dict[str, list[dict[str, Any]]] = {}


class AskRequest(BaseModel):
    """What the browser sends in the body of POST /ask."""

    question: str = Field(min_length=1, max_length=2000, description="The user's question.")
    conversation_id: str | None = Field(
        default=None,
        description="Leave empty to start a new conversation; send the id from the "
        "`start` event to ask a follow-up in the same one.",
    )


def sse(event: str, data: dict[str, Any]) -> str:
    """Format one Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def to_json_event(event: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Turn one agent event (which can hold Python objects) into plain JSON data."""
    kind = event["type"]
    if kind == "dataset":
        res = event["result"]  # a datasets.Result: too big to send whole
        return kind, {
            "id": res.id,
            "title": res.title,
            "rows": len(res.frame),
            "from_cache": res.from_cache,
        }
    if kind == "chart":
        # A Plotly figure knows how to describe itself as JSON, which
        # Plotly.js in the browser can draw directly.
        return kind, {"dataset_id": event["dataset_id"], "figure": json.loads(event["figure"].to_json())}
    # thinking / text / tool_call / error / done are already plain data.
    return kind, {k: v for k, v in event.items() if k != "type"}


def stream_answer(messages: list[dict[str, Any]], client: anthropic.Anthropic, conversation_id: str) -> Iterator[str]:
    """The body of the streaming response: yields one SSE message per step."""
    yield sse("start", {"conversation_id": conversation_id})
    try:
        for event in run_session(messages, client):
            kind, data = to_json_event(event)
            yield sse(kind, data)
    except Exception as exc:  # never end the stream silently
        yield sse("error", {"text": f"Server error: {exc}"})


@router.post("/ask")
def ask(body: AskRequest, request: Request) -> StreamingResponse:
    """Ask the agent a question. The reply is a stream of Server-Sent Events:

    `start` → any of `thinking`, `tool_call`, `dataset`, `chart`, `text`, `error` → `done`.
    """
    client: anthropic.Anthropic | None = request.app.state.anthropic
    if client is None:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY is not set on the server.")

    if body.conversation_id is None:
        conversation_id = uuid.uuid4().hex
        CONVERSATIONS[conversation_id] = []
    elif body.conversation_id in CONVERSATIONS:
        conversation_id = body.conversation_id
    else:
        raise HTTPException(status_code=404, detail="Unknown conversation_id (the server may have restarted).")

    messages = CONVERSATIONS[conversation_id]
    messages.append({"role": "user", "content": body.question})

    return StreamingResponse(
        stream_answer(messages, client, conversation_id),
        media_type="text/event-stream",
        # Ask proxies not to buffer, so each step reaches the browser immediately.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
