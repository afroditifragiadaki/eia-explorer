"""Presentation layer: CSS and small layout helpers.

Kept apart from app.py so the page logic stays readable. Streamlit's own theme
(see .streamlit/config.toml) handles colour, radius and type; this file covers
the few things the theme cannot express — the hero band, chrome removal, and
card polish.

Everything here is cosmetic. Nothing in this module affects a single number.
"""

from __future__ import annotations

import streamlit as st

CSS = """
<style>
/* --- remove stock Streamlit chrome ------------------------------------- */
#MainMenu, footer, header [data-testid="stStatusWidget"] { visibility: hidden; }
.stAppDeployButton { display: none; }
.block-container { padding-top: 2.2rem; padding-bottom: 4rem; max-width: 1180px; }

/* --- hero --------------------------------------------------------------- */
.ex-hero {
  border-radius: 18px;
  padding: 2.4rem 2.2rem 2rem;
  margin-bottom: 1.6rem;
  background:
    radial-gradient(1200px 300px at 10% -40%, rgba(94,234,212,.22), transparent 60%),
    linear-gradient(135deg, rgba(56,189,248,.16), rgba(129,140,248,.10));
  border: 1px solid rgba(148,163,184,.22);
}
.ex-hero h1 {
  font-size: 2.35rem; line-height: 1.12; margin: 0 0 .55rem;
  letter-spacing: -0.025em; font-weight: 700;
}
.ex-hero p { margin: 0; opacity: .82; font-size: 1.03rem; max-width: 62ch; }

/* --- little pills under the hero ---------------------------------------- */
.ex-pills { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: 1.25rem; }
.ex-pill {
  font-size: .78rem; padding: .32rem .7rem; border-radius: 999px;
  border: 1px solid rgba(148,163,184,.3); background: rgba(148,163,184,.10);
  white-space: nowrap;
}
.ex-pill b { font-weight: 600; }

/* --- metric cards -------------------------------------------------------- */
[data-testid="stMetric"] { padding: .9rem 1rem; }
[data-testid="stMetricLabel"] { opacity: .68; font-size: .8rem; }

/* --- tabs ---------------------------------------------------------------- */
.stTabs [data-baseweb="tab-list"] { gap: .35rem; }
.stTabs [data-baseweb="tab"] {
  padding: .55rem 1rem; border-radius: 10px 10px 0 0; font-weight: 500;
}

/* --- verdict line -------------------------------------------------------- */
.ex-verdict {
  border-left: 3px solid var(--primary-color, #38bdf8);
  padding: .55rem 0 .55rem .9rem; margin: .4rem 0 1.1rem;
  font-size: 1.02rem; line-height: 1.5;
}
.ex-verdict .win { font-weight: 700; }
.ex-verdict .warn { opacity: .8; }

/* --- footnotes ----------------------------------------------------------- */
.ex-note { font-size: .8rem; opacity: .6; line-height: 1.6; }
</style>
"""


def inject() -> None:
    st.html(CSS)


def hero(title: str, subtitle: str, pills: list[str] | None = None) -> None:
    pill_html = ""
    if pills:
        items = "".join(f'<span class="ex-pill">{p}</span>' for p in pills)
        pill_html = f'<div class="ex-pills">{items}</div>'
    st.html(f'<div class="ex-hero"><h1>{title}</h1><p>{subtitle}</p>{pill_html}</div>')


def verdict(html: str) -> None:
    st.html(f'<div class="ex-verdict">{html}</div>')


def note(text: str) -> None:
    st.html(f'<div class="ex-note">{text}</div>')
