"""The shapes of the data the API sends back.

Each class describes one kind of JSON object: which fields it has and what
type each field is. FastAPI uses them to:
  - check that what we return really has that shape (a bug fails loudly here,
    not silently in the browser),
  - drop any field we did not list (nothing leaks by accident),
  - document the response on the /docs page.
The React app will rely on exactly these shapes. This file is the contract.
"""

from __future__ import annotations

from pydantic import BaseModel


class CatalogueItem(BaseModel):
    """One EIA dataset in a search result (short version)."""

    route: str               # e.g. "electricity/retail-sales"
    name: str                # e.g. "Electricity › Electricity Sales to Ultimate Customers"
    description: str
    metrics: list[str]       # e.g. ["price", "sales", "revenue", "customers"]
    facets: list[str]        # the filters, e.g. ["stateid", "sectorid"]
    frequencies: list[str]   # e.g. ["monthly", "quarterly", "annual"]
    coverage: str            # e.g. "2001-01 → 2026-06"


class Facet(BaseModel):
    id: str
    description: str | None = None


class Metric(BaseModel):
    id: str
    alias: str | None = None
    units: str | None = None


class CatalogueDetail(BaseModel):
    """One EIA dataset with everything we know about it (long version)."""

    route: str
    name: str
    description: str
    frequencies: list[str]
    facets: list[Facet]
    metrics: list[Metric]
    start_period: str | None
    end_period: str | None


class LibraryItem(BaseModel):
    """One dataset the agent has downloaded and saved in Turso."""

    id: str
    title: str
    route: str
    rows: int
    fetched_at: str
