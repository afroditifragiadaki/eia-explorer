"""eia-explorer — ask for EIA energy data in words, get a chart.

The agent finds the right dataset in EIA's catalogue, pulls it through the
API, and caches it in Turso so every later request for it is instant. The
Library and Catalogue tabs work without an Anthropic key.
"""

from __future__ import annotations

import json
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from src import charts, datasets, store, ui  # noqa: E402
from src.agent import run_session  # noqa: E402

st.set_page_config(page_title="eia-explorer", page_icon="⚡", layout="wide")
ui.inject()

EXAMPLES = [
    "How have residential electricity prices changed in California vs Texas since 2015?",
    "Show Henry Hub natural gas spot prices over the last two years",
    "What did ERCOT hourly demand look like last week?",
    "Weekly US retail gasoline prices since 2020",
]


@st.cache_data(ttl=300, show_spinner=False)
def catalog() -> pd.DataFrame:
    return store.all_routes()


@st.cache_data(ttl=30, show_spinner=False)
def library() -> pd.DataFrame:
    return store.list_datasets()


@st.cache_data(ttl=300, show_spinner="Loading from the library…")
def load(ds_id: str) -> datasets.Result | None:
    return datasets.load(ds_id)


store.init()

# ------------------------------------------------------------------ sidebar ---
with st.sidebar:
    st.markdown("### ⚡ eia-explorer")
    st.caption("EIA energy data, without learning the EIA API.")
    st.divider()
    st.markdown(f"**Storage:** {'Turso' if store.backend() == 'turso' else 'local SQLite'}")
    st.markdown(f"**Catalogue:** {len(catalog())} datasets")
    st.markdown(f"**Library:** {len(library())} saved")
    if not os.environ.get("EIA_API_KEY"):
        st.warning("Set `EIA_API_KEY` in .env to download new data.")
    st.divider()
    api_key = os.environ.get("ANTHROPIC_API_KEY") or st.text_input(
        "Anthropic API key", type="password", placeholder="sk-ant-…",
        help="Only needed for the Ask tab.",
    )
    if st.button("New conversation", width="stretch"):
        st.session_state.pop("messages", None)
        st.session_state.pop("transcript", None)
        st.rerun()

ui.hero(
    "Ask for energy data. Get a chart.",
    "EIA publishes hundreds of energy datasets behind an API most people never learn. "
    "Describe what you want; the agent finds the dataset, pulls it, and plots it.",
    pills=[
        f"<b>{len(catalog())}</b> EIA datasets indexed",
        f"<b>{len(library())}</b> already cached",
        "electricity · gas · petroleum · coal · SEDS · STEO",
    ],
)

t_ask, t_lib, t_cat = st.tabs(["💬 Ask", "📚 Library", "🗂 Catalogue"])


# ---------------------------------------------------------------------- ask ---
def render(item: dict) -> None:
    kind = item["type"]
    if kind == "text":
        st.markdown(item["text"])
    elif kind == "thinking":
        with st.expander("Reasoning", expanded=False):
            st.caption(item["text"])
    elif kind == "tool_call":
        st.caption(f"→ `{item['name']}` {json.dumps(item['args'])[:160]}")
    elif kind == "dataset":
        res = item["result"]
        src = "from library" if res.from_cache else "downloaded from EIA"
        st.caption(f"📦 **{res.title}** — {len(res.frame):,} rows, {src} · id `{res.id}`")
    elif kind == "chart":
        st.plotly_chart(item["figure"], width="stretch")
    elif kind == "error":
        st.error(item["text"])


with t_ask:
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("transcript", [])

    for role, items in st.session_state.transcript:
        with st.chat_message(role):
            for item in items:
                render(item)

    prompt = st.chat_input("e.g. coal production in Wyoming since 2010", disabled=not api_key)
    if not st.session_state.transcript:
        if not api_key:
            st.info("Add an Anthropic API key in the sidebar (or `.env`) to ask questions. "
                    "The Library and Catalogue tabs work without one.", icon="💬")
        cols = st.columns(2)
        for i, ex in enumerate(EXAMPLES):
            if cols[i % 2].button(ex, key=f"ex{i}", width="stretch", disabled=not api_key):
                prompt = ex

    if prompt and api_key:
        import anthropic

        st.chat_message("user").markdown(prompt)
        st.session_state.transcript.append(("user", [{"type": "text", "text": prompt}]))
        st.session_state.messages.append({"role": "user", "content": prompt})
        shown: list[dict] = []
        with st.chat_message("assistant"):
            # Steps go in the collapsible status; the answer and charts go below
            # it, so they stay visible once the status collapses.
            status = st.status("Working…", expanded=True)
            body = st.container()
            for event in run_session(st.session_state.messages, anthropic.Anthropic(api_key=api_key)):
                if event["type"] == "done":
                    continue
                if event["type"] in ("tool_call", "thinking"):
                    with status:
                        render(event)
                    if event["type"] == "tool_call":
                        status.update(label=f"Running {event['name']}…")
                    continue
                with body:
                    render(event)
                shown.append(event)
            status.update(label="Done", state="complete", expanded=False)
        st.session_state.transcript.append(("assistant", shown))
        # Rerun so the sidebar counts and the Library pick up the new dataset.
        library.clear()
        st.rerun()


# ------------------------------------------------------------------ library ---
with t_lib:
    lib = library()
    if lib.empty:
        st.info("Nothing saved yet. Ask a question and the data lands here.")
    else:
        c1, c2 = st.columns([3, 1])
        needle = c1.text_input("Filter", placeholder="title or route")
        if c2.button("↻ Refresh", width="stretch"):
            library.clear()
            st.rerun()
        view = lib[lib["title"].str.contains(needle, case=False) | lib["route"].str.contains(needle, case=False)] if needle else lib
        pick = st.selectbox(
            "Dataset", view["id"],
            format_func=lambda i: f"{view.set_index('id').at[i, 'title']}  ·  {view.set_index('id').at[i, 'route']}",
        )
        res = load(pick) if pick else None
        if res is not None and not res.frame.empty:
            df = res.frame
            a, b, c = st.columns(3)
            metric = a.selectbox("Metric", sorted(df["metric"].unique()))
            kind = b.selectbox("Chart", charts.KINDS)
            all_series = sorted(df.loc[df["metric"] == metric, "series"].unique())
            series = c.multiselect("Series", all_series, default=all_series[:8])
            try:
                st.plotly_chart(
                    charts.build(df, kind, res.title, metric=metric, series=series or None),
                    width="stretch",
                )
            except ValueError as exc:
                st.warning(str(exc))
            with st.expander("Data"):
                wide = df[df["metric"] == metric].pivot_table(index="period", columns="series", values="value")
                st.dataframe(wide, width="stretch")
            st.download_button(
                "Download CSV", df.to_csv(index=False), file_name=f"{res.id}.csv", mime="text/csv",
            )


# ---------------------------------------------------------------- catalogue ---
with t_cat:
    q = st.text_input("Search EIA datasets", placeholder="e.g. nuclear outages, crude imports, state CO2")
    if q:
        hits = store.search_routes(q, limit=25)
        if not hits:
            st.info("No matches. Try EIA vocabulary: 'retail sales', 'rto', 'seds', 'steo'.")
        for h in hits:
            with st.expander(f"**{h['name']}** — `{h['route']}`"):
                st.write(h["description"])
                st.caption(
                    f"metrics: {', '.join(h['metrics'])} · facets: {', '.join(h['facets'])} · "
                    f"frequencies: {', '.join(h['frequencies'])} · coverage: {h['coverage']}"
                )
    else:
        cat = catalog()
        top = cat["path"].str.split("/").str[0].value_counts()
        st.bar_chart(top, horizontal=True)
        ui.note("Datasets per EIA category. Search above to explore.")
