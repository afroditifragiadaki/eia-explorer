"""Endpoints for one saved dataset: its data, a chart of it, and a CSV file.

    GET /datasets/{id}        → the data points as JSON (Library → open a card)
    GET /datasets/{id}/chart  → a Plotly figure as JSON (the chart-type buttons)
    GET /datasets/{id}/csv    → a file download (the "Download CSV" button)
"""

from __future__ import annotations

import json
import re
from typing import Literal

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from src import charts, store

from .schemas import DatasetDetail

router = APIRouter(prefix="/datasets", tags=["datasets"])


def load_or_404(dataset_id: str) -> tuple[dict, pd.DataFrame]:
    """Shared by all three endpoints: the dataset's details and rows, or a 404."""
    meta = store.get_dataset_meta(dataset_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"No saved dataset with id '{dataset_id}'.")
    return meta, store.load_dataset(dataset_id)


@router.get("/{dataset_id}", response_model=DatasetDetail)
def get_dataset(
    dataset_id: str,
    metric: str | None = Query(None, description="Only this metric, e.g. 'price'."),
):
    """A saved dataset with every data point."""
    meta, df = load_or_404(dataset_id)
    all_metrics = sorted(df["metric"].unique())
    if metric:
        df = df[df["metric"] == metric]
    # JSON has no "NaN": turn pandas' missing values into None (null in JSON).
    df = df.astype(object).where(df.notna(), None)
    return {
        "id": meta["id"],
        "title": meta["title"],
        "route": meta["route"],
        "fetched_at": meta["fetched_at"],
        "query": json.loads(meta["query_json"]),
        "metrics": all_metrics,
        "series": sorted(df["series"].unique()),
        "rows": len(df),
        "observations": df.to_dict(orient="records"),
    }


@router.get("/{dataset_id}/chart")
def get_chart(
    dataset_id: str,
    kind: Literal["line", "area", "bar", "latest_bar", "seasonal"] = "line",
    metric: str | None = Query(None, description="Which metric to plot. Default: the first one."),
    series: list[str] | None = Query(None, description="Only these series. Repeat the parameter for several."),
    log_y: bool = False,
):
    """A Plotly figure, as JSON that Plotly.js in the browser can draw directly."""
    meta, df = load_or_404(dataset_id)
    try:
        fig = charts.build(df, kind=kind, title=meta["title"], metric=metric, series=series, log_y=log_y)
    except ValueError as exc:  # e.g. a metric or series that isn't in this dataset
        raise HTTPException(status_code=400, detail=str(exc))
    # The figure is already JSON text; send it as-is instead of re-encoding it.
    return Response(content=fig.to_json(), media_type="application/json")


@router.get("/{dataset_id}/csv")
def download_csv(
    dataset_id: str,
    layout: Literal["wide", "long"] = Query(
        "wide", description="wide: one column per series (good for Excel). long: one row per value."
    ),
):
    """The dataset as a CSV file download."""
    meta, df = load_or_404(dataset_id)
    if layout == "wide":
        df = df.assign(column=df["series"] + " · " + df["metric"] + " (" + df["units"] + ")")
        df = df.pivot_table(index="period", columns="column", values="value", aggfunc="first").reset_index()
        df.columns.name = None
    # A safe file name from the title: "Residential electricity, CA vs TX" → "residential-electricity-ca-vs-tx"
    slug = re.sub(r"[^a-z0-9]+", "-", meta["title"].lower()).strip("-") or dataset_id
    return Response(
        content=df.to_csv(index=False),
        media_type="text/csv",
        # "attachment" tells the browser to save the file instead of showing it.
        headers={"Content-Disposition": f'attachment; filename="{slug}.csv"'},
    )
