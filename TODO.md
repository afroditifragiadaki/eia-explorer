# Pending fixes

Found while building and smoke-testing the first version (2026-09-16).

## Bugs

- [ ] **Closing the browser tab cancels a running question.** Streamlit stops
  the script, so the answer is lost. A dataset only reaches the library if the
  download step had already finished. Consider running the agent in a
  background thread, or saving each step as it happens.
- [ ] **Catalogue crawl: routes that fail after all retries are only printed.**
  The crawler still writes everything else, and routes missed on this run keep
  the previous crawl's rows. Collect the failures and retry them at the end,
  or report them clearly.

- [ ] **Conversations live in the API server's memory** (`CONVERSATIONS` in
  `api/ask.py`): lost on restart, not shared between server processes.
  Store them in Turso.
- [ ] **The agent can download a dataset it already has.** Seen twice: it
  charts a saved dataset, then calls `fetch_data` again "to get the numbers",
  with slightly different parameters (an explicit `end`, an extra `series`
  facet), so the cache id differs and a duplicate is saved. Cause:
  `make_chart` returns only "Chart shown", and `list_saved_datasets` returns
  no statistics. Fix: return `datasets.summarize()` from `make_chart` (or add
  a `summarize_dataset` tool), and normalise queries before hashing.

- [ ] **Frontend: conversations are not listed or restorable.** The sidebar has
  no "Recent" list yet; needs conversations stored in Turso first.
- [ ] **Frontend: no URLs per screen.** Reloading always returns to the home
  screen. Add a router (e.g. React Router) so /library/{id} can be shared.

## Not verified yet

- [ ] The fix that keeps the answer and chart visible below the status box
  (`app.py`) hasn't been checked in the browser: the re-test was cut short
  when the tab closed.
- [ ] ERCOT hourly-demand example (the hourly-data path) through the UI.
- [ ] Running the crawler and the app at the same time against the same Turso
  replica file (possible file locking).

## Quality

- [ ] **Catalogue search is keyword-only.** "solar capacity" ranks
  `coal/reserves-capacity` first. Options: better weighting on dataset names,
  full-text search (FTS5), or Turso vector search on embeddings.
- [ ] **Charts:** when a dataset has several metrics and none is chosen, the
  first one is plotted without saying so, and series with different units can
  share one axis.
- [ ] **Reads can be up to 30 s behind** writes from other processes
  (`SYNC_EVERY_S` in `src/store.py`).
- [ ] **Catalogue descriptions repeat themselves** for some routes: the
  crawler joins the parent's description with the dataset's own, and they
  are often identical (`scripts/build_catalog.py`). Skip duplicates.
- [ ] **Deprecated EIA routes** (`co2-emissions/*`) are still in the
  catalogue. Mark or drop them.
- [ ] **No automated tests.** Worth covering: `charts.parse_period`,
  `datasets._series_label`, `eia.Query.canonical`, and the agent loop with a
  fake client.
- [ ] **Test datasets:** the Turso library still holds datasets saved during
  development.

## Before deploying publicly

- [ ] If `ANTHROPIC_API_KEY` is in the server's environment, every visitor
  spends it. Either require each visitor to enter their own key (as
  forecast-playground does), or add authentication and rate limits.
- [ ] Put the EIA key behind the same limits: EIA rate-limits per key.
