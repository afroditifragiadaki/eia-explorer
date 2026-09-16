"""Tests for every API endpoint. Run them with:

    pytest

Each test sends a request with the test client (no server needed) and checks
the status code and the JSON that comes back.
"""

from __future__ import annotations

import json

from api import ask

from .conftest import DATASET_ID


# --- health and stats ---------------------------------------------------------


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "storage": "sqlite"}


def test_stats(client):
    assert client.get("/stats").json() == {"catalogue_datasets": 2, "library_datasets": 1}


# --- catalogue ----------------------------------------------------------------


def test_catalogue_search_finds_matching_dataset(client):
    results = client.get("/catalogue", params={"q": "henry hub"}).json()
    assert [r["route"] for r in results] == ["natural-gas/pri/fut"]


def test_catalogue_without_query_returns_everything(client):
    assert len(client.get("/catalogue").json()) == 2


def test_catalogue_limit_is_validated(client):
    assert client.get("/catalogue", params={"limit": 0}).status_code == 422


def test_catalogue_detail(client):
    r = client.get("/catalogue/electricity/retail-sales")
    assert r.status_code == 200
    body = r.json()
    assert body["facets"][0] == {"id": "stateid", "description": "State"}
    assert body["metrics"] == [{"id": "price", "alias": "Average Price", "units": "cents per kilowatt-hour"}]


def test_catalogue_detail_unknown_route_is_404(client):
    assert client.get("/catalogue/not/a/route").status_code == 404


# --- library ------------------------------------------------------------------


def test_library_lists_saved_datasets(client):
    items = client.get("/library").json()
    assert items[0]["id"] == DATASET_ID
    assert items[0]["rows"] == 4


def test_library_filter_is_case_insensitive_and_literal(client):
    assert len(client.get("/library", params={"contains": "ny VS"}).json()) == 1
    assert client.get("/library", params={"contains": "(("}).json() == []


# --- datasets -----------------------------------------------------------------


def test_dataset_detail_turns_missing_values_into_null(client):
    body = client.get(f"/datasets/{DATASET_ID}").json()
    assert body["series"] == ["Florida", "New York"]
    assert body["rows"] == 4
    assert body["observations"][3]["value"] is None


def test_dataset_unknown_id_is_404(client):
    assert client.get("/datasets/nope").status_code == 404
    assert client.get("/datasets/nope/csv").status_code == 404


def test_chart_returns_plotly_json(client):
    r = client.get(f"/datasets/{DATASET_ID}/chart", params={"series": ["Florida"]})
    assert r.status_code == 200
    figure = r.json()
    assert len(figure["data"]) == 1  # one line: Florida only


def test_chart_rejects_bad_input(client):
    assert client.get(f"/datasets/{DATASET_ID}/chart", params={"kind": "pie"}).status_code == 422
    assert client.get(f"/datasets/{DATASET_ID}/chart", params={"series": "Mars"}).status_code == 400


def test_csv_download(client):
    r = client.get(f"/datasets/{DATASET_ID}/csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert 'filename="residential-price-ny-vs-fl.csv"' in r.headers["content-disposition"]
    header = r.text.splitlines()[0]
    assert header == (
        "period,Florida · price (cents per kilowatt-hour),New York · price (cents per kilowatt-hour)"
    )


# --- ask ----------------------------------------------------------------------


def parse_sse(text: str) -> list[tuple[str, dict]]:
    """Turn a Server-Sent Events body back into (event, data) pairs."""
    events = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def fake_run_session(messages, client):
    """Stands in for the real agent: no Claude, no EIA, always the same steps."""
    yield {"type": "tool_call", "name": "search_catalog", "args": {"query": "prices"}}
    yield {"type": "text", "text": f"You asked: {messages[-1]['content']}"}
    yield {"type": "done", "stop_reason": "end_turn"}


def test_ask_without_key_is_503(client):
    r = client.post("/ask", json={"question": "hi"})
    assert r.status_code == 503


def test_ask_rejects_empty_question(client):
    assert client.post("/ask", json={"question": ""}).status_code == 422


def test_ask_streams_events_and_keeps_the_conversation(client, monkeypatch):
    monkeypatch.setattr(ask, "run_session", fake_run_session)
    client.app.state.anthropic = object()  # anything but None: the fake agent ignores it

    r = client.post("/ask", json={"question": "NY vs FL?"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(r.text)
    assert [name for name, _ in events] == ["start", "tool_call", "text", "done"]
    assert events[2][1] == {"text": "You asked: NY vs FL?"}

    # A follow-up in the same conversation sees the earlier question too.
    conversation_id = events[0][1]["conversation_id"]
    client.post("/ask", json={"question": "And Texas?", "conversation_id": conversation_id})
    questions = [m["content"] for m in ask.CONVERSATIONS[conversation_id] if m["role"] == "user"]
    assert questions == ["NY vs FL?", "And Texas?"]


def test_ask_unknown_conversation_is_404(client):
    client.app.state.anthropic = object()
    r = client.post("/ask", json={"question": "hi", "conversation_id": "missing"})
    assert r.status_code == 404
