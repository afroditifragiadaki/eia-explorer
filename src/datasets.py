"""Get a dataset: from the Turso cache if fresh, otherwise from EIA (then cache it).

This is the one function both the agent and the UI call. Everything EIA-shaped
is flattened here into a single long table: period, series, metric, value, units.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from . import eia, store


@dataclass
class Result:
    id: str
    title: str
    frame: pd.DataFrame  # long: period, series, metric, value, units
    from_cache: bool


def _series_label(df: pd.DataFrame, q: eia.Query) -> pd.Series:
    """A readable name per row, built from whichever descriptive columns vary.

    EIA names its label columns inconsistently (`stateDescription`,
    `sectorName`, `series-description`, `area-name`), so rather than map each
    route, take every non-value text column and keep the ones that actually
    distinguish rows. Constant columns ("Natural Gas" on every row) add noise.
    """
    skip = {"period", *q.data, "units"} | {c for c in df.columns if c.endswith("-units")}
    text = [c for c in df.columns if c not in skip]
    # Prefer a human column over its id twin: `stateid` vs `stateDescription`.
    # Description columns first: when nothing varies, the single label should be
    # "Henry Hub Natural Gas Spot Price", not `area-name` = "NA".
    human = sorted(
        (c for c in text if any(k in c.lower() for k in ("name", "description"))),
        key=lambda c: "description" not in c.lower(),
    )
    cols = human or text
    varying = [c for c in cols if df[c].nunique(dropna=False) > 1]
    cols = varying or cols[:1]
    if not cols:
        return pd.Series(q.route, index=df.index)
    return df[cols].astype(str).agg(" · ".join, axis=1)


def _to_long(df: pd.DataFrame, q: eia.Query) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["period", "series", "metric", "value", "units"])
    series = _series_label(df, q)
    parts = []
    for col in q.data:
        if col not in df.columns:
            continue
        units = df.get(f"{col}-units", df.get("units", pd.Series("", index=df.index)))
        parts.append(
            pd.DataFrame(
                {
                    "period": df["period"].astype(str),
                    "series": series,
                    "metric": col,
                    "value": df[col],
                    "units": units.fillna("").astype(str),
                }
            )
        )
    return pd.concat(parts, ignore_index=True)


def get(q: eia.Query, title: str | None = None, refresh: bool = False) -> Result:
    canonical = q.canonical()
    ds_id = store.dataset_id(canonical)
    if not refresh:
        hit = store.cached(ds_id, q.frequency)
        if hit:
            return Result(ds_id, hit["title"], store.load_dataset(ds_id), True)

    long = _to_long(eia.fetch(q), q)
    title = title or q.route
    store.save_dataset(ds_id, canonical, title, long)
    return Result(ds_id, title, long, False)


def load(ds_id: str) -> Result | None:
    df = store.list_datasets()
    row = df[df["id"] == ds_id]
    if row.empty:
        return None
    return Result(ds_id, row.iloc[0]["title"], store.load_dataset(ds_id), True)


def summarize(res: Result, max_series: int = 15) -> str:
    """Compact text for the model: shape, coverage, and per-series stats.

    The model never needs every row to describe a dataset — it needs ranges,
    latest values and change, which fit in a few hundred tokens.
    """
    df = res.frame.dropna(subset=["value"])
    if df.empty:
        return f"Dataset {res.id} ({res.title}) is empty: the query matched no rows."
    df = df.sort_values("period")
    lines = [
        f"dataset_id: {res.id}  ({'cache' if res.from_cache else 'fresh from EIA'})",
        f"title: {res.title}",
        f"rows: {len(df):,}  periods: {df['period'].iloc[0]} → {df['period'].iloc[-1]}",
        f"series: {df['series'].nunique()}  metrics: {', '.join(df['metric'].unique())}",
        "",
        "series | metric | units | first | last | min | max | mean",
    ]
    groups = list(df.groupby(["series", "metric"], sort=False))
    for (series, metric), g in groups[:max_series]:
        first, last = g.iloc[0], g.iloc[-1]
        lines.append(
            f"{series} | {metric} | {g['units'].iloc[0]} | "
            f"{first['value']:.4g} ({first['period']}) | {last['value']:.4g} ({last['period']}) | "
            f"{g['value'].min():.4g} | {g['value'].max():.4g} | {g['value'].mean():.4g}"
        )
    if len(groups) > max_series:
        lines.append(f"... and {len(groups) - max_series} more series")
    return "\n".join(lines)
