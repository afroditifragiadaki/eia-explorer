"""Tests for the agent loop in src/agent.py, with a fake Claude client.

No real API calls: the fake client records what it was sent and replies with
a fixed final answer.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from types import SimpleNamespace

from src import agent


class FakeMessages:
    """Stands in for `client.beta.messages`: records each request."""

    def __init__(self):
        self.requests = []

    def create(self, **kwargs):
        # Copy the list: the agent keeps appending to the same one.
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        answer = SimpleNamespace(type="text", text="Done.")
        return SimpleNamespace(stop_reason="end_turn", content=[answer])


def fake_client():
    return SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages()))


def test_date_note_uses_the_clock(monkeypatch):
    monkeypatch.setattr(agent, "today", lambda: date(2027, 3, 1))
    assert agent.date_note() == {"role": "system", "content": "Today's date is 2027-03-01 (UTC)."}


def test_every_question_is_followed_by_todays_date(monkeypatch):
    client = fake_client()
    messages = [{"role": "user", "content": "Henry Hub, last two years"}]

    monkeypatch.setattr(agent, "today", lambda: date(2026, 9, 16))
    list(agent.run_session(messages, client))

    sent = client.beta.messages.requests[0]["messages"]
    assert sent == [
        {"role": "user", "content": "Henry Hub, last two years"},
        {"role": "system", "content": "Today's date is 2026-09-16 (UTC)."},
    ]

    # A follow-up on a later day gets that day's date, after the new question.
    messages.append({"role": "user", "content": "And last week?"})
    monkeypatch.setattr(agent, "today", lambda: date(2026, 9, 17))
    list(agent.run_session(messages, client))

    sent = client.beta.messages.requests[1]["messages"]
    assert [m["role"] for m in sent] == ["user", "system", "assistant", "user", "system"]
    assert sent[-1]["content"] == "Today's date is 2026-09-17 (UTC)."


def test_system_prompt_stays_fixed_so_it_can_be_cached(monkeypatch):
    client = fake_client()
    for day in (1, 2):
        monkeypatch.setattr(agent, "today", lambda day=day: date(2026, 9, day))
        list(agent.run_session([{"role": "user", "content": "hi"}], client))
    first, second = client.beta.messages.requests
    assert first["system"] == second["system"]
    assert "2026-09" not in first["system"][0]["text"]


class ScriptedMessages:
    """Replies with a fixed list of responses, one per call."""

    def __init__(self, responses):
        self.responses = list(responses)

    def create(self, **kwargs):
        return self.responses.pop(0)


def scripted_client(*responses):
    return SimpleNamespace(beta=SimpleNamespace(messages=ScriptedMessages(responses)))


def trace_records(caplog):
    return [json.loads(r.getMessage()) for r in caplog.records if r.name == "eia-explorer.agent"]


def test_the_agents_path_is_logged(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="eia-explorer.agent")
    monkeypatch.setattr(agent, "_dispatch", lambda name, args, state: ("3 hits", None))
    usage = SimpleNamespace(input_tokens=100, output_tokens=20)
    call = SimpleNamespace(type="tool_use", id="t1", name="search_catalog", input={"query": "henry hub"})
    answer = SimpleNamespace(type="text", text="Done.")
    client = scripted_client(
        SimpleNamespace(stop_reason="tool_use", content=[call], model="claude-opus-5", usage=usage),
        SimpleNamespace(stop_reason="end_turn", content=[answer], model="fallback-model", usage=usage),
    )

    events = list(agent.run_session([{"role": "user", "content": "gas price?"}], client, "conv1"))

    records = trace_records(caplog)
    assert [r["event"] for r in records] == ["run_start", "model_turn", "tool_call", "model_turn", "run_end"]
    assert {r["run_id"] for r in records} == {events[-1]["run_id"]}
    assert {r["conversation_id"] for r in records} == {"conv1"}
    assert records[0]["question"] == "gas price?"
    assert records[1]["usage"] == {"input_tokens": 100, "output_tokens": 20}
    assert records[2]["tool"] == "search_catalog" and records[2]["args"] == {"query": "henry hub"}
    assert records[3]["model"] == "fallback-model"  # the fallback is visible
    assert records[4]["outcome"] == "done"
    assert records[4]["usage"] == {"input_tokens": 200, "output_tokens": 40}


def test_tool_errors_are_logged(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="eia-explorer.agent")

    def boom(name, args, state):
        raise ValueError("bad facet")

    monkeypatch.setattr(agent, "_dispatch", boom)
    call = SimpleNamespace(type="tool_use", id="t1", name="fetch_data", input={})
    answer = SimpleNamespace(type="text", text="Sorry.")
    client = scripted_client(
        SimpleNamespace(stop_reason="tool_use", content=[call]),
        SimpleNamespace(stop_reason="end_turn", content=[answer]),
    )

    list(agent.run_session([{"role": "user", "content": "x"}], client))

    tool = [r for r in trace_records(caplog) if r["event"] == "tool_call"][0]
    assert tool["error"] == "ValueError: bad facet"
