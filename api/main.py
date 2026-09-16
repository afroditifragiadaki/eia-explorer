"""HTTP API for eia-explorer.

The React frontend talks only to this. Everything it does is a thin wrapper
around `src/` — the same code the Streamlit app uses — so the logic lives in
one place and this file is just "which URL calls which function".

Run it:
    fastapi dev api/main.py
Then open http://127.0.0.1:8000/docs for the interactive docs.
"""

from __future__ import annotations

from dotenv import load_dotenv

# Load .env before importing src/, which reads the keys from the environment.
load_dotenv()

import json  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

import anthropic  # noqa: E402
from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from src import store  # noqa: E402

from .ask import router as ask_router  # noqa: E402
from .datasets import router as datasets_router  # noqa: E402
from .schemas import CatalogueDetail, CatalogueItem, LibraryItem  # noqa: E402
from .settings import get_settings  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code before `yield` runs once when the server starts, after it once on
    # shutdown. Make sure the tables exist before the first request arrives.
    store.init()
    # One Anthropic client for the whole server, reused by every request.
    # None if there is no key: /ask then answers 503 instead of crashing.
    key = get_settings().anthropic_api_key
    app.state.anthropic = anthropic.Anthropic(api_key=key) if key else None
    yield


app = FastAPI(
    title="eia-explorer API",
    version="0.1.0",
    description="Find, cache and chart U.S. Energy Information Administration data.",
    lifespan=lifespan,
)

# CORS: browsers only let a page read replies from another address (our API
# on :8000, called from the React app on :5173) if the API says it's allowed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Endpoints defined in other files are attached here.
app.include_router(ask_router)
app.include_router(datasets_router)


@app.get("/health")
def health() -> dict:
    """Is the API up, and which database is it using?"""
    return {"status": "ok", "storage": store.backend()}


@app.get("/stats")
def stats() -> dict:
    """How many datasets are in the EIA catalogue and in our library?"""
    catalogue = store.all_routes()  # DataFrame: one row per EIA dataset
    library = store.list_datasets()  # DataFrame: one row per saved dataset
    return {
        "catalogue_datasets": len(catalogue),
        "library_datasets": len(library),
    }


# --- catalogue: every dataset the EIA API serves ------------------------------


@app.get("/catalogue", response_model=list[CatalogueItem])
def search_catalogue(
    q: str = Query("", max_length=200, description="Search words, e.g. 'solar capacity'. Empty = everything."),
    limit: int = Query(25, ge=1, le=250, description="Maximum number of results."),
):
    """Search the EIA catalogue. Powers the Catalogue screen's search box."""
    return store.search_routes(q, limit=limit)


@app.get("/catalogue/{route:path}", response_model=CatalogueDetail)
def get_catalogue_entry(route: str):
    """Everything about one EIA dataset, e.g. /catalogue/electricity/retail-sales."""
    df = store.all_routes()
    match = df[df["path"] == route.strip("/")]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"No EIA dataset at route '{route}'.")
    row = match.iloc[0]
    metrics = json.loads(row["data_cols"] or "{}")  # stored as JSON text in Turso
    return {
        "route": row["path"],
        "name": row["name"],
        "description": row["description"] or "",
        "frequencies": json.loads(row["frequencies"] or "[]"),
        "facets": json.loads(row["facets"] or "[]"),
        "metrics": [{"id": key, **info} for key, info in metrics.items()],
        "start_period": row["start_period"],
        "end_period": row["end_period"],
    }


# --- library: datasets the agent has already downloaded -----------------------


@app.get("/library", response_model=list[LibraryItem])
def get_library(
    contains: str = Query("", max_length=200, description="Only titles containing this text (case-insensitive)."),
):
    """Every saved dataset, newest first. Powers the Library screen."""
    df = store.list_datasets()
    if contains:
        # regex=False: treat the text literally, so "(" or "+" can't break the search.
        df = df[df["title"].str.contains(contains, case=False, regex=False)]
    return df.to_dict(orient="records")
