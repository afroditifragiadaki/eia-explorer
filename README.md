# eia-explorer

Ask for U.S. energy data in plain English and get a chart.

The U.S. Energy Information Administration (EIA) publishes hundreds of datasets
through its API, covering electricity, natural gas, petroleum, coal, state
energy totals (SEDS) and short-term forecasts (STEO). Using them normally means
learning a route tree, facet codes and period formats. Here, an agent does
that work: it finds the right dataset, downloads it, caches it in
[Turso](https://turso.tech) and plots it.

## How it works

```
question ──► agent (Claude Opus 5)
               │ search_catalog      ◄── Turso: routes (232 EIA datasets, crawled once)
               │ describe_dataset
               │ list_facet_values   ◄── EIA API (live codes: states, series, BAs…)
               │ list_saved_datasets ◄── Turso: datasets (the shared library)
               │ fetch_data          ◄── Turso cache hit? else EIA API → saved to Turso
               └ make_chart          ──► Plotly in Streamlit
```

| File | Role |
|---|---|
| `src/eia.py` | EIA v2 client: pagination, retry on rate limits (HTTP 429), numeric conversion |
| `src/store.py` | Turso (embedded replica) or local SQLite: catalogue, datasets, observations |
| `src/datasets.py` | Serves a dataset from the cache or from EIA, then stores it in one long format |
| `src/agent.py` | Tool definitions and the agent loop, which emits each step as an event for the UI |
| `src/charts.py` | Handles every EIA period format; line, area, bar, latest-value and seasonal charts |
| `scripts/build_catalog.py` | Crawls the EIA route tree into the `routes` table |
| `app.py` | Streamlit app with Ask, Library and Catalogue tabs |

## What the live API actually does

These behaviours were checked against the live API:

- **Every value is a string** (`"34.74"`), so values are converted to numbers
  before they are stored.
- **A request returns at most 5,000 rows.** Larger requests are cut off with
  only a warning, so `fetch` pages through results with `offset`. Queries over
  50,000 rows are refused, and the agent is told to narrow them.
- **Many datasets have no `name` of their own.** `aeo/2019` and
  `natural-gas/pri/fut` return `null`. The crawler builds a name from the
  parent routes (`Petroleum › Prices › Weekly Retail Gasoline…`) instead;
  without that, a search for "gasoline price" found nothing.
- **Label columns are named inconsistently** (`stateDescription`,
  `sectorName`, `series-description`, `area-name`). Series names are built from
  whichever descriptive columns actually differ between rows.
- **EIA rate-limits quickly.** A full crawl hits HTTP 429, so requests back off
  and retry.
- **Turso makes each SQL statement a network round-trip.** `executemany` over a
  few thousand rows took minutes. Inserting 500 rows per statement takes seconds.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # add EIA_API_KEY, optionally Turso + Anthropic
python -m scripts.build_catalog   # ~1–2 min, one-off
streamlit run app.py
```

Without Turso credentials, everything runs on `data/eia.db`.

## API (FastAPI)

The backend for the React frontend. It wraps `src/` and adds no
logic of its own.

```bash
fastapi dev api/main.py        # http://127.0.0.1:8000/docs
pip install -r requirements-dev.txt && pytest   # tests: temp SQLite, no network
```

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness and storage backend |
| `GET /stats` | Catalogue and library counts |
| `GET /catalogue?q=&limit=` | Search the EIA catalogue |
| `GET /catalogue/{route}` | One EIA dataset's metadata |
| `GET /library?contains=` | Saved datasets |
| `GET /datasets/{id}` | A saved dataset's data points |
| `GET /datasets/{id}/chart` | Plotly figure JSON (`kind`, `metric`, `series`, `log_y`) |
| `GET /datasets/{id}/csv` | CSV download (`layout=wide\|long`) |
| `POST /ask` | Run the agent; streams Server-Sent Events |

| File | Role |
|---|---|
| `api/main.py` | App, startup, CORS, catalogue and library endpoints |
| `api/ask.py` | `POST /ask` and the event stream |
| `api/datasets.py` | Dataset data, chart and CSV endpoints |
| `api/schemas.py` | Response models (the API contract) |
| `api/settings.py` | Settings from environment variables |
| `tests/` | Endpoint tests with a temporary database and a fake agent |

## Web app (React)

The frontend in `web/`, built with Vite and React. It talks only to the API.

```bash
cd web
npm install
npm run dev            # http://localhost:5173 (the API must be running on :8000)
npm run build          # production files in web/dist/
```

| Path | Role |
|---|---|
| `src/App.jsx` | Screen switching and shared state |
| `src/api.js` | Backend address, JSON requests, the `/ask` stream reader |
| `src/hooks/` | `useApi` (fetch + state), `useDebounced`, `useConversation` |
| `src/screens/` | Home, Answer, Library (+ dataset view), Catalogue |
| `src/components/` | Sidebar, Chart (Plotly, lazy-loaded), dataset details, icons |
| `src/index.css` | Theme tokens and all styles |

Set `VITE_API_URL` in `web/.env` when the API runs elsewhere.

## Caching

A dataset's ID is a hash of its normalised query, so the same question asked in
different words reuses the same cached rows. Hourly and daily data expire after
6 hours; everything else expires after 7 days.

## Ideas for later

- Scheduled refresh of popular datasets
- Semantic search over the catalogue (Turso supports vector columns)
- Charts that combine datasets (e.g. gas price against power price)
- Shareable links to a saved chart
