"""Tests for the agent loop in src/agent.py, with a fake Claude client.

No real API calls: the fake client records what it was sent and replies with
a fixed final answer.
"""

from __future__ import annotations

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
