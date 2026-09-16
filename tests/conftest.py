"""Shared test setup ("fixtures") for the API tests.

The tests must never touch the real Turso database, EIA or Claude: they'd be
slow, cost money, and change real data. So before the app is imported we
blank the keys, and each test gets a brand-new SQLite file with a little fake
data in it.
"""

from __future__ import annotations

import os

# Must run before `api.main` is imported: load_dotenv() never overwrites a
# variable that already exists, so these empty values win over .env.
os.environ["TURSO_DATABASE_URL"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""

import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402
from src import store  # noqa: E402

DATASET_ID = "testdataset00001"

ROUTES = [
    {
        "path": "electricity/retail-sales",
        "name": "Electricity › Electricity Sales to Ultimate Customers",
        "description": "Electricity sales to ultimate customers by state and sector.",
        "frequencies": ["monthly", "annual"],
        "facets": [{"id": "stateid", "description": "State"}, {"id": "sectorid", "description": "Sector"}],
        "data_cols": {"price": {"alias": "Average Price", "units": "cents per kilowatt-hour"}},
        "start_period": "2001-01",
        "end_period": "2026-06",
    },
    {
        "path": "natural-gas/pri/fut",
        "name": "Natural Gas › Prices › Spot and Futures",
        "description": "Henry Hub natural gas spot prices.",
        "frequencies": ["daily", "monthly"],
        "facets": [{"id": "series", "description": None}],
        "data_cols": {"value": {"alias": None, "units": None}},
        "start_period": "1997-01",
        "end_period": "2026-09",
    },
]

OBSERVATIONS = pd.DataFrame(
    {
        "period": ["2026-01", "2026-01", "2026-02", "2026-02"],
        "series": ["New York", "Florida", "New York", "Florida"],
        "metric": ["price"] * 4,
        "value": [28.4, 15.9, 29.1, None],  # one missing value on purpose
        "units": ["cents per kilowatt-hour"] * 4,
    }
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A test client for the API, backed by a fresh temporary database."""
    monkeypatch.setattr(store, "LOCAL_DB", tmp_path / "test.db")
    # `with` runs the app's lifespan (startup), which creates the tables.
    with TestClient(app) as c:
        store.upsert_routes(ROUTES)
        store.save_dataset(
            DATASET_ID,
            {"route": "electricity/retail-sales", "data": ["price"], "facets": {"stateid": ["FL", "NY"]}},
            "Residential price, NY vs FL",
            OBSERVATIONS,
        )
        yield c
