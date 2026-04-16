#!/usr/bin/env python3
"""One-time diagnostic: find current CFTC market names for affected markets.

Run locally (not inside GitHub Actions) to discover which market names
the CFTC currently uses for the TFF COMBINED contracts post-2022.

Usage:
    python scripts/discover_cftc_names.py

Output shows every unique market_and_exchange_names string that the CFTC API
returns, sorted by most-recent-date descending, so COMBINED contracts appear
at the top.  Use these names to update query_name in fetch_cot.py.
"""

from __future__ import annotations

import json
import requests

BASE_TFF = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"
HEADERS = {"User-Agent": "cot-cta-dashboard/1.0"}
TIMEOUT = 30

# Short, broad search terms — designed to match BOTH old and new COMBINED names
SEARCHES = [
    ("sp500",  "S&P 500"),
    ("nasdaq", "NASDAQ"),
    ("us10y",  "TREASURY"),
    ("gbpfx",  "BRITISH POUND"),
    ("dxy",    "DOLLAR INDEX"),
    # Working markets for reference
    ("vix",    "VIX"),
    ("eurfx",  "EURO FX"),
]


def main() -> None:
    for key, search_term in SEARCHES:
        params = {
            "$limit": 100,
            "$order": "report_date_as_yyyy_mm_dd DESC",
            "$where": f"upper(market_and_exchange_names) like '%{search_term.upper()}%'",
        }
        try:
            rows = requests.get(BASE_TFF, params=params, headers=HEADERS, timeout=TIMEOUT).json()
        except Exception as exc:
            print(f"\n=== {key} — ERROR: {exc}")
            continue

        # Group by name, track earliest and latest date
        name_ranges: dict[str, dict] = {}
        for r in rows:
            name = r.get("market_and_exchange_names", "")
            date_val = str(r.get("report_date_as_yyyy_mm_dd") or "")[:10]
            if name not in name_ranges:
                name_ranges[name] = {"first": date_val, "last": date_val, "count": 0}
            name_ranges[name]["count"] += 1
            if date_val > name_ranges[name]["last"]:
                name_ranges[name]["last"] = date_val
            if date_val < name_ranges[name]["first"]:
                name_ranges[name]["first"] = date_val

        print(f"\n{'='*70}")
        print(f"  {key}  (search: '{search_term}', {len(rows)} total rows from API)")
        print(f"{'='*70}")
        for name, info in sorted(name_ranges.items(), key=lambda x: x[1]["last"], reverse=True):
            flag = "  *** POST-2022 ***" if info["last"] >= "2023" else ""
            print(f"  {info['first']} → {info['last']}  ({info['count']} rows){flag}")
            print(f"    Name: {name}")


if __name__ == "__main__":
    main()
