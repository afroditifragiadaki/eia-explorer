"""Turn a long dataset (period, series, metric, value, units) into a Plotly figure."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

KINDS = ["line", "area", "bar", "latest_bar", "seasonal"]


def parse_period(p: pd.Series) -> pd.Series:
    """EIA periods come as 2026, 2026-06, 2026-Q2, 2026-06-01, or 2026-06-01T00."""
    s = p.astype(str)
    if s.str.contains("Q").any():
        return pd.PeriodIndex(s.str.replace("-", ""), freq="Q").to_timestamp().to_series(index=p.index)
    if s.str.fullmatch(r"\d{4}").all():
        return pd.to_datetime(s, format="%Y")
    if s.str.contains("T").any():
        return pd.to_datetime(s.str.replace(r"T(\d{2})$", r" \1:00", regex=True), errors="coerce")
    return pd.to_datetime(s, errors="coerce")


def build(
    df: pd.DataFrame,
    kind: str = "line",
    title: str = "",
    metric: str | None = None,
    series: list[str] | None = None,
    log_y: bool = False,
) -> go.Figure:
    d = df.dropna(subset=["value"]).copy()
    if metric:
        d = d[d["metric"] == metric]
    elif d["metric"].nunique() > 1:
        # Two metrics on one axis (price in cents vs sales in GWh) is misleading.
        d = d[d["metric"] == d["metric"].iloc[0]]
    if series:
        d = d[d["series"].isin(series)]
    if d.empty:
        raise ValueError("Nothing left to plot after filtering by metric/series.")

    d["date"] = parse_period(d["period"])
    d = d.sort_values("date")
    units = d["units"].iloc[0] if "units" in d else ""
    ylab = f"{d['metric'].iloc[0]} ({units})" if units else d["metric"].iloc[0]
    labels = {"value": ylab, "date": "", "series": ""}
    many = d["series"].nunique() > 1

    if kind == "area":
        fig = px.area(d, x="date", y="value", color="series" if many else None, labels=labels)
    elif kind == "bar":
        fig = px.bar(d, x="date", y="value", color="series" if many else None, labels=labels, barmode="group")
    elif kind == "latest_bar":
        last = d.sort_values("date").groupby("series").tail(1).sort_values("value")
        fig = px.bar(last, x="value", y="series", orientation="h", text=last["value"].round(2),
                     labels=labels | {"series": ""})
        fig.update_traces(textposition="outside", cliponaxis=False)
        title = title or f"Latest value ({last['period'].max()})"
    elif kind == "seasonal":
        d["year"] = d["date"].dt.year.astype(str)
        d["month"] = d["date"].dt.month
        fig = px.line(d, x="month", y="value", color="year", facet_col="series" if many else None,
                      labels=labels | {"month": "month"})
    else:
        fig = px.line(d, x="date", y="value", color="series" if many else None, labels=labels)

    fig.update_layout(
        title=title,
        height=440,
        margin=dict(l=10, r=10, t=56, b=10),
        legend=dict(orientation="h", yanchor="top", y=-0.12, x=0),
    )
    if log_y:
        fig.update_yaxes(type="log")
    return fig
