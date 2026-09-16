"""Thin client for the EIA v2 API.

Behaviour below was checked against the live API, not the docs:

- The catalogue is a tree of *routes* (`electricity/retail-sales`, `petroleum/pri/gnd`).
  A route either has child `routes` or it is a leaf with `frequency`, `facets`
  and `data` columns. Depth varies by branch.
- Every value comes back as a **string** ("34.74"), with its units in a sibling
  `<column>-units` field. Coerce before plotting or everything sorts as text.
- A single request returns at most 5000 rows. Asking for more silently
  truncates with a warning, so `fetch` paginates with `offset`.
- A bad column/facet is a 400 with a readable message listing the valid values.
  That message is passed straight to the agent, which can act on it.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import pandas as pd
import requests

BASE = "https://api.eia.gov/v2"
PAGE = 5000
TIMEOUT = 60


class MissingKey(RuntimeError):
    pass


class EIAError(RuntimeError):
    pass


def _key() -> str:
    key = os.environ.get("EIA_API_KEY", "").strip()
    if not key:
        raise MissingKey(
            "EIA_API_KEY is not set. Get a free key at https://www.eia.gov/opendata/ "
            "and put it in .env."
        )
    return key


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{BASE}/{path.strip('/')}/" if path else f"{BASE}/"
    # EIA answers bursts with HTTP 429 OVER_RATE_LIMIT; a short backoff clears it.
    for delay in (2, 5, 15, 0):
        r = requests.get(url, params={"api_key": _key(), **(params or {})}, timeout=TIMEOUT)
        if r.status_code != 429 or not delay:
            break
        time.sleep(delay)
    try:
        body = r.json()
    except ValueError:
        raise EIAError(f"EIA returned HTTP {r.status_code} with a non-JSON body.")
    if r.status_code != 200 or "error" in body:
        raise EIAError(f"EIA HTTP {r.status_code}: {body.get('error', body)}")
    return body


def route(path: str = "") -> dict[str, Any]:
    """Metadata for a route: children for a branch, columns/facets for a leaf."""
    return _get(path)["response"]


def facet_values(path: str, facet: str) -> list[dict[str, str]]:
    return _get(f"{path}/facet/{facet}")["response"]["facets"]


@dataclass
class Query:
    route: str
    data: list[str]
    frequency: str | None = None
    facets: dict[str, list[str]] | None = None
    start: str | None = None
    end: str | None = None

    def params(self) -> dict[str, Any]:
        p: dict[str, Any] = {
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
        }
        if self.frequency:
            p["frequency"] = self.frequency
        for i, col in enumerate(self.data):
            p[f"data[{i}]"] = col
        for facet, values in (self.facets or {}).items():
            p[f"facets[{facet}][]"] = list(values)
        if self.start:
            p["start"] = self.start
        if self.end:
            p["end"] = self.end
        return p

    def canonical(self) -> dict[str, Any]:
        """Order-independent form, used as the cache key."""
        return {
            "route": self.route.strip("/"),
            "data": sorted(self.data),
            "frequency": self.frequency,
            "facets": {k: sorted(v) for k, v in sorted((self.facets or {}).items())},
            "start": self.start,
            "end": self.end,
        }


def count(q: Query) -> int:
    body = _get(f"{q.route}/data", {**q.params(), "length": 0})
    return int(body["response"].get("total", 0))


def fetch(q: Query, max_rows: int = 50_000) -> pd.DataFrame:
    """Download every row for `q` (up to `max_rows`), as a wide frame.

    Value columns are coerced to float. Each `<col>-units` column is kept so
    the caller can label axes honestly.
    """
    total = count(q)
    if total > max_rows:
        raise EIAError(
            f"This query matches {total:,} rows, over the {max_rows:,} row limit. "
            "Narrow it with facets (e.g. specific states/series) or a start/end date."
        )
    frames = []
    for offset in range(0, total, PAGE):
        body = _get(f"{q.route}/data", {**q.params(), "offset": offset, "length": PAGE})
        frames.append(pd.DataFrame(body["response"]["data"]))
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    for col in q.data:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df
