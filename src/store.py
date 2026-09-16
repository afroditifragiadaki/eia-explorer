"""Persistence: the searchable EIA catalogue and a cache of downloaded datasets.

Runs on Turso when TURSO_DATABASE_URL is set (as an embedded replica: reads
are local, writes go to Turso and sync back), and on a plain local SQLite
file otherwise. `libsql` mirrors the `sqlite3` API, so nothing else changes.

Data is stored long — one row per (period, series, metric) — because that is
the shape both SQL and Plotly want, and it works for every EIA route whatever
its facets are called.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
LOCAL_DB = ROOT / "data" / "eia.db"
REPLICA_DB = ROOT / "data" / "turso-replica.db"
INSERT_CHUNK = 500
SYNC_EVERY_S = 30
_last_sync = 0.0

SCHEMA = """
CREATE TABLE IF NOT EXISTS routes (
    path         TEXT PRIMARY KEY,
    name         TEXT,
    description  TEXT,
    frequencies  TEXT,   -- JSON list of ids
    facets       TEXT,   -- JSON list of {id, description}
    data_cols    TEXT,   -- JSON {col: {alias, units}}
    start_period TEXT,
    end_period   TEXT,
    crawled_at   TEXT
);
CREATE TABLE IF NOT EXISTS datasets (
    id          TEXT PRIMARY KEY,   -- hash of the canonical query
    route       TEXT NOT NULL,
    query_json  TEXT NOT NULL,
    title       TEXT,
    row_count   INTEGER,
    fetched_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS observations (
    dataset_id TEXT NOT NULL,
    period     TEXT NOT NULL,
    series     TEXT NOT NULL,
    metric     TEXT NOT NULL,
    value      REAL,
    units      TEXT
);
CREATE INDEX IF NOT EXISTS obs_dataset ON observations(dataset_id);
"""


def backend() -> str:
    return "turso" if os.environ.get("TURSO_DATABASE_URL") else "sqlite"


@contextmanager
def connect(write: bool = False) -> Iterator[Any]:
    REPLICA_DB.parent.mkdir(parents=True, exist_ok=True)
    if backend() == "turso":
        import libsql

        conn = libsql.connect(
            str(REPLICA_DB),
            sync_url=os.environ["TURSO_DATABASE_URL"],
            auth_token=os.environ.get("TURSO_AUTH_TOKEN", ""),
        )
        # Reads hit the local replica. Pulling from Turso on every open made a
        # page load take ~10 s, so only pull if it has been a while; writes
        # always sync (below), so this process never misses its own changes.
        global _last_sync
        if write or time.monotonic() - _last_sync > SYNC_EVERY_S:
            conn.sync()
            _last_sync = time.monotonic()
    else:
        conn = sqlite3.connect(LOCAL_DB)
    try:
        yield conn
        if write:
            conn.commit()
            if backend() == "turso":
                conn.sync()
    finally:
        conn.close()


def init() -> None:
    with connect(write=True) as conn:
        for stmt in SCHEMA.split(";"):
            if stmt.strip():
                conn.execute(stmt)


# --- catalogue --------------------------------------------------------------


def upsert_routes(rows: list[dict[str, Any]]) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with connect(write=True) as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO routes VALUES (?,?,?,?,?,?,?,?,?)",
            [
                (
                    r["path"],
                    r["name"],
                    r["description"],
                    json.dumps(r["frequencies"]),
                    json.dumps(r["facets"]),
                    json.dumps(r["data_cols"]),
                    r.get("start_period"),
                    r.get("end_period"),
                    now,
                )
                for r in rows
            ],
        )


def all_routes() -> pd.DataFrame:
    with connect() as conn:
        cur = conn.execute("SELECT * FROM routes ORDER BY path")
        cols = [d[0] for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


def search_routes(query: str, limit: int = 12) -> list[dict[str, Any]]:
    """Keyword search over the catalogue.

    The catalogue is a few hundred rows, so scoring in Python is simpler and
    more forgiving than FTS: a hit in the name or path counts more than one in
    the description, and every query word contributes.
    """
    df = all_routes()
    if df.empty:
        return []
    words = [w for w in query.lower().replace("-", " ").split() if len(w) > 1]
    name = (df["name"].fillna("") + " " + df["path"].str.replace("/", " ")).str.lower()
    desc = (df["description"].fillna("") + " " + df["data_cols"].fillna("")).str.lower()
    score = sum(name.str.contains(w, regex=False) * 3 + desc.str.contains(w, regex=False) for w in words)
    df = df.assign(score=score)
    df = df[df["score"] > 0].sort_values("score", ascending=False).head(limit)
    return [
        {
            "route": r.path,
            "name": r.name,
            "description": (r.description or "")[:240],
            "metrics": list(json.loads(r.data_cols or "{}")),
            "facets": [f["id"] for f in json.loads(r.facets or "[]")],
            "frequencies": json.loads(r.frequencies or "[]"),
            "coverage": f"{r.start_period} → {r.end_period}",
        }
        for r in df.itertuples()
    ]


# --- dataset cache ----------------------------------------------------------


def dataset_id(canonical: dict[str, Any]) -> str:
    blob = json.dumps(canonical, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


def max_age(frequency: str | None) -> timedelta:
    # Hourly grid data moves daily; most EIA series are monthly or slower.
    if frequency and ("hour" in frequency or frequency == "daily"):
        return timedelta(hours=6)
    return timedelta(days=7)


def cached(ds_id: str, frequency: str | None) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, route, query_json, title, row_count, fetched_at FROM datasets WHERE id = ?",
            (ds_id,),
        ).fetchone()
    if not row:
        return None
    fetched = datetime.fromisoformat(row[5])
    if datetime.now(timezone.utc) - fetched > max_age(frequency):
        return None
    return dict(zip(["id", "route", "query_json", "title", "row_count", "fetched_at"], row))


def save_dataset(ds_id: str, canonical: dict[str, Any], title: str, long: pd.DataFrame) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with connect(write=True) as conn:
        conn.execute("DELETE FROM observations WHERE dataset_id = ?", (ds_id,))
        conn.execute(
            "INSERT OR REPLACE INTO datasets VALUES (?,?,?,?,?,?)",
            (ds_id, canonical["route"], json.dumps(canonical), title, len(long), now),
        )
        rows = [
            (ds_id, r.period, r.series, r.metric, None if pd.isna(r.value) else float(r.value), r.units)
            for r in long.itertuples()
        ]
        # On Turso every statement is a network round-trip, so executemany of
        # 10k rows takes minutes. Multi-row VALUES in chunks takes seconds.
        for i in range(0, len(rows), INSERT_CHUNK):
            chunk = rows[i : i + INSERT_CHUNK]
            conn.execute(
                "INSERT INTO observations VALUES " + ",".join(["(?,?,?,?,?,?)"] * len(chunk)),
                [v for row in chunk for v in row],
            )


def load_dataset(ds_id: str) -> pd.DataFrame:
    with connect() as conn:
        rows = conn.execute(
            "SELECT period, series, metric, value, units FROM observations WHERE dataset_id = ?",
            (ds_id,),
        ).fetchall()
    return pd.DataFrame(rows, columns=["period", "series", "metric", "value", "units"])


def list_datasets() -> pd.DataFrame:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, title, route, row_count, fetched_at FROM datasets ORDER BY fetched_at DESC"
        ).fetchall()
    return pd.DataFrame(rows, columns=["id", "title", "route", "rows", "fetched_at"])
