"""Crawl the EIA v2 route tree into the `routes` table.

Run once (and again whenever EIA adds datasets):

    python -m scripts.build_catalog

Only leaves — routes that actually serve data — are stored. That is what the
agent searches, so it never has to walk the tree over the network mid-chat.
"""

from __future__ import annotations

import sys
import time

from dotenv import load_dotenv

load_dotenv()

from src import eia, store  # noqa: E402


def walk(path: str, out: list[dict], trail: tuple[str, ...] = (), blurbs: tuple[str, ...] = ()) -> None:
    try:
        meta = eia.route(path)
    except eia.EIAError as exc:
        print(f"  ! {path}: {exc}", file=sys.stderr)
        return
    time.sleep(0.15)  # be polite; EIA rate-limits keys

    children = meta.get("routes") or []
    if children:
        for child in children:
            # Many leaves have no `name` of their own; the parent's listing
            # does. Carry the breadcrumb down so search has words to match.
            walk(
                f"{path}/{child['id']}".strip("/"),
                out,
                trail + (child.get("name") or child["id"],),
                blurbs + (child.get("description") or "",),
            )
    if "data" in meta:
        out.append(
            {
                "path": path,
                "name": " › ".join(trail) or path,
                "description": " ".join(" ".join(blurbs[-2:] + (meta.get("description") or "",)).split()),
                "frequencies": [f["id"] for f in meta.get("frequency", [])],
                "facets": [{"id": f["id"], "description": f.get("description")} for f in meta.get("facets", [])],
                "data_cols": meta.get("data", {}),
                "start_period": meta.get("startPeriod"),
                "end_period": meta.get("endPeriod"),
            }
        )
        print(f"  + {path}  ({' › '.join(trail)})")


def main() -> None:
    store.init()
    leaves: list[dict] = []
    walk("", leaves)
    store.upsert_routes(leaves)
    print(f"\nStored {len(leaves)} datasets in {store.backend()}.")


if __name__ == "__main__":
    main()
