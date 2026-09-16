"""The agent: turn a question into the right EIA dataset, then a chart.

The hard part of EIA is not downloading — it is knowing that "Henry Hub price"
lives at `natural-gas/pri/fut` under series `RNGWHHD`, at daily frequency. The
agent does that lookup: search the catalogue (in Turso), inspect a route,
look up facet codes, then fetch. Anything already fetched is served from the
Turso cache, so the second person to ask costs no EIA calls.

Hand-written loop so every step streams to the UI.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any, Iterator

import anthropic

from . import charts, datasets, eia, store

MODEL = "claude-opus-5"
MAX_TOKENS = 16000
MAX_TURNS = 16
FALLBACK_BETA = "server-side-fallback-2026-07-01"


SYSTEM_PROMPT = """You help people explore U.S. Energy Information Administration
(EIA) data without learning the EIA API. You find the right dataset, pull it,
and show it as a chart, then say briefly what it shows.

HOW EIA DATA IS ORGANISED
- Datasets live at *routes* such as `electricity/retail-sales`. Each route has
  metrics (data columns such as `price`, `sales`, `value`), facets (filters such
  as `stateid`, `sectorid`, `series`, `respondent`) and frequencies.
- Facet values are codes (`CA`, `RES`, `RNGWHHD`). Never guess a code: look it
  up with list_facet_values.
- Periods are formatted by frequency: annual `2024`, monthly `2024-06`,
  quarterly `2024-Q2`, daily `2024-06-01`, hourly `2024-06-01T00`. Pass `start`
  and `end` in the same format as the frequency.

DATES
- You do not know today's date from memory. The app adds it to the
  conversation as a system note after each question: use that date.
- Relative periods ("last two years", "last week", "since last summer") count
  back from that date. Choose `start` in the frequency's format, e.g. `2024-09`
  for monthly data when today is in September 2026.
- EIA data lags: check the dataset's coverage end. If the latest data is older
  than the person likely expects, say so.

WORKFLOW
1. If the question might already be answered, call list_saved_datasets first;
   reusing a saved dataset is instant.
2. Otherwise search_catalog. Try a second phrasing if the first misses: the
   catalogue uses EIA vocabulary ("retail sales" for electricity prices,
   "rto" for hourly grid data, "seds" for state totals).
3. describe_dataset on the best candidate to see its metrics, facets and coverage.
4. list_facet_values for every facet you intend to filter on.
5. fetch_data with facets that keep the result focused. Always filter a facet
   that would otherwise return hundreds of series. The fetch refuses anything
   over 50,000 rows; if that happens, narrow it and retry.
6. make_chart. Then answer in a few sentences using numbers from the summary.

GOOD HABITS
- Prefer the most direct dataset. For state electricity prices, use
  `electricity/retail-sales`, not a derived profile.
- If a fetch returns an error listing valid values, use them and retry. Do
  not give up after one error.
- Hourly data is large: limit it to a few weeks unless asked otherwise.
- State the units and the period covered. Say plainly if EIA marks a series as
  deprecated or if the latest period is older than the person likely expects.
- Do not invent numbers that are not in a tool result.
"""


def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "name": name,
        "description": description,
        "input_schema": {"type": "object", "properties": properties, "required": required},
    }


TOOLS = [
    _tool(
        "search_catalog",
        "Keyword search over every EIA dataset (route). Returns route ids, names, metrics, facets and coverage.",
        {"query": {"type": "string"}},
        ["query"],
    ),
    _tool(
        "describe_dataset",
        "Full metadata for one route: metrics with units, facets, frequencies, coverage.",
        {"route": {"type": "string"}},
        ["route"],
    ),
    _tool(
        "list_facet_values",
        "Valid codes for one facet of a route (e.g. stateid, series, respondent). "
        "Use `contains` to filter long lists by name.",
        {
            "route": {"type": "string"},
            "facet": {"type": "string"},
            "contains": {"type": "string", "description": "Case-insensitive filter on code or name."},
        },
        ["route", "facet"],
    ),
    _tool(
        "fetch_data",
        "Download a dataset from EIA (or the cache) and store it. Returns a dataset_id "
        "and a statistical summary per series.",
        {
            "route": {"type": "string"},
            "metrics": {"type": "array", "items": {"type": "string"}},
            "frequency": {"type": "string"},
            "facets": {
                "type": "object",
                "description": "Map of facet id to list of codes, e.g. {\"stateid\": [\"CA\", \"TX\"]}.",
                "additionalProperties": {"type": "array", "items": {"type": "string"}},
            },
            "start": {"type": "string"},
            "end": {"type": "string"},
            "title": {"type": "string", "description": "Human title for the saved dataset."},
        },
        ["route", "metrics", "frequency", "title"],
    ),
    _tool(
        "list_saved_datasets",
        "Datasets already downloaded into the shared library, newest first. "
        "Optional `contains` filters by title or route.",
        {"contains": {"type": "string"}},
        [],
    ),
    _tool(
        "make_chart",
        "Show a chart of a saved dataset to the user. kinds: line (default, trends), "
        "area, bar (few periods), latest_bar (compare series at the latest period), "
        "seasonal (monthly data, one line per year).",
        {
            "dataset_id": {"type": "string"},
            "kind": {"type": "string", "enum": charts.KINDS},
            "title": {"type": "string"},
            "metric": {"type": "string", "description": "Required if the dataset has several metrics."},
            "series": {"type": "array", "items": {"type": "string"}, "description": "Subset of series names."},
            "log_y": {"type": "boolean"},
        },
        ["dataset_id", "kind", "title"],
    ),
]


def _describe(route: str) -> str:
    df = store.all_routes()
    row = df[df["path"] == route.strip("/")]
    if row.empty:
        return f"No route '{route}' in the catalogue. Use search_catalog to find valid routes."
    r = row.iloc[0]
    return json.dumps(
        {
            "route": r["path"],
            "name": r["name"],
            "description": r["description"],
            "frequencies": json.loads(r["frequencies"]),
            "facets": json.loads(r["facets"]),
            "metrics": json.loads(r["data_cols"]),
            "coverage": [r["start_period"], r["end_period"]],
        },
        indent=1,
    )


def _facets(args: dict) -> str:
    values = eia.facet_values(args["route"], args["facet"])
    needle = (args.get("contains") or "").lower()
    if needle:
        values = [v for v in values if needle in json.dumps(v).lower()]
    shown = values[:60]
    lines = [f"{v['id']}: {v.get('name') or v.get('alias', '')}" for v in shown]
    if len(values) > len(shown):
        lines.append(f"... {len(values) - len(shown)} more; use `contains` to narrow.")
    return "\n".join(lines) or "No matching values."


def _saved(args: dict) -> str:
    df = store.list_datasets()
    needle = (args.get("contains") or "").lower()
    if needle:
        df = df[(df["title"].str.lower().str.contains(needle)) | (df["route"].str.contains(needle))]
    if df.empty:
        return "No saved datasets match."
    return df.head(30).to_csv(index=False)


def _dispatch(name: str, args: dict, state: dict) -> tuple[str, dict | None]:
    """Run one tool. Returns (text for the model, optional UI event)."""
    if name == "search_catalog":
        hits = store.search_routes(args["query"])
        return (json.dumps(hits, indent=1) if hits else "No matches. Try other words."), None
    if name == "describe_dataset":
        return _describe(args["route"]), None
    if name == "list_facet_values":
        return _facets(args), None
    if name == "list_saved_datasets":
        return _saved(args), None
    if name == "fetch_data":
        q = eia.Query(
            route=args["route"],
            data=list(args["metrics"]),
            frequency=args.get("frequency"),
            facets=args.get("facets") or None,
            start=args.get("start"),
            end=args.get("end"),
        )
        res = datasets.get(q, title=args.get("title"))
        state[res.id] = res
        return datasets.summarize(res), {"type": "dataset", "result": res}
    if name == "make_chart":
        ds_id = args["dataset_id"]
        res = state.get(ds_id) or datasets.load(ds_id)
        if res is None:
            return f"No dataset '{ds_id}'. Fetch it first.", None
        fig = charts.build(
            res.frame,
            kind=args.get("kind", "line"),
            title=args.get("title", res.title),
            metric=args.get("metric"),
            series=args.get("series"),
            log_y=bool(args.get("log_y")),
        )
        return "Chart shown to the user.", {"type": "chart", "figure": fig, "dataset_id": ds_id}
    return f"Unknown tool {name}.", None


def today() -> date:
    """Today's date in UTC. A separate function so tests can replace it."""
    return datetime.now(timezone.utc).date()


def date_note() -> dict[str, str]:
    """A system note with today's date, added after each question.

    Not part of SYSTEM_PROMPT: that text is cached and must stay identical
    between requests, and a server can run for weeks. Read from the clock
    every time instead.
    """
    return {"role": "system", "content": f"Today's date is {today().isoformat()} (UTC)."}


def run_session(messages: list[dict[str, Any]], client: anthropic.Anthropic) -> Iterator[dict[str, Any]]:
    """Drive one user turn, yielding events for the UI.

    Events: thinking | text | tool_call | dataset | chart | error | done.
    `messages` is mutated in place so the caller keeps the conversation.
    """
    system = [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]
    state: dict[str, datasets.Result] = {}

    # The newest message is the user's question: tell Claude the date right
    # after it. It stays in the history, so each question keeps the date it
    # was asked on.
    messages.append(date_note())

    for _ in range(MAX_TURNS):
        try:
            # `fallbacks="default"`: if Opus 5 declines, the API retries on a
            # fallback model inside the same call instead of returning nothing.
            response = client.beta.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system,
                thinking={"type": "adaptive", "display": "summarized"},
                tools=TOOLS,
                messages=messages,
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.AuthenticationError:
            yield {"type": "error", "text": "Invalid Anthropic API key."}
            return
        except anthropic.RateLimitError:
            yield {"type": "error", "text": "Rate limited by the Anthropic API — try again shortly."}
            return
        except anthropic.APIStatusError as exc:
            yield {"type": "error", "text": f"Anthropic API error {exc.status_code}: {exc.message}"}
            return
        except anthropic.APIConnectionError:
            yield {"type": "error", "text": "Network error reaching the Anthropic API."}
            return

        if response.stop_reason == "refusal":
            yield {"type": "error", "text": "The model declined this request."}
            return

        messages.append({"role": "assistant", "content": response.content})
        for block in response.content:
            if block.type == "thinking" and getattr(block, "thinking", ""):
                yield {"type": "thinking", "text": block.thinking}
            elif block.type == "text" and block.text.strip():
                yield {"type": "text", "text": block.text}

        if response.stop_reason != "tool_use":
            yield {"type": "done", "stop_reason": response.stop_reason}
            return

        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            args = block.input if isinstance(block.input, dict) else json.loads(block.input)
            yield {"type": "tool_call", "name": block.name, "args": args}
            try:
                text, event = _dispatch(block.name, args, state)
                if event:
                    yield event
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": text})
            except eia.MissingKey as exc:
                yield {"type": "error", "text": str(exc)}
                return
            except Exception as exc:  # noqa: BLE001 — the model can usually recover
                results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": f"Error: {exc}", "is_error": True}
                )
        messages.append({"role": "user", "content": results})

    yield {"type": "error", "text": f"Stopped after {MAX_TURNS} steps."}
