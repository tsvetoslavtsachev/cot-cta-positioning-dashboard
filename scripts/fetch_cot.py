#!/usr/bin/env python3
"""Fetch and normalize weekly COT data into static JSON files.

This script is intentionally lightweight so it can run inside GitHub Actions.
It uses public CFTC JSON endpoints and writes a `manifest.json` plus one file
per market under `data/markets/`.

Notes:
- Financial futures use the Traders in Financial Futures endpoint.
- Commodity examples use the Disaggregated endpoint.
- Price data is optional and fetched from Yahoo Finance chart API.
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

import requests

# S13c cut-over (INIT-22): per-market cohort rows now come FROM data-core (the
# guarded base), not a local CFTC fetch. consumer.cot_rows(key) reproduces the cot
# array; WTI (oil-reuse) + any base-absent series fall back to the CFTC path below.
# Requires the `collectors` package on the path + DATACORE_ROOT (set in CI). If the
# wiring is unavailable the import fails CLOSED to None -> every market uses CFTC,
# so the dashboard keeps working as before (strangler: production never stops).
try:
    from collectors.cot import consumer as _cot_consumer
except Exception as _exc:  # pragma: no cover - environment-dependent
    _cot_consumer = None
    print(f"  [base] collectors.cot.consumer unavailable ({_exc}); CFTC fallback for all")

BASE_TFF = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"
BASE_DISAGG = "https://publicreporting.cftc.gov/resource/kh3c-gbw2.json"
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=3y&interval=1d"
LOOKBACK = 156
HEADERS = {"User-Agent": "cot-cta-dashboard/1.0"}
TIMEOUT = 30

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
MARKETS_DIR = DATA_DIR / "markets"
DERIVED_DIR = DATA_DIR / "derived"

MARKETS: List[Dict[str, Any]] = [
    {
        "key": "sp500",
        "title": "E-mini S&P 500",
        "subtitle": "US Equities",
        "report_family": "tff",
        # Post-2022 CFTC name dropped "STOCK INDEX": "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE"
        # Shorter query matches both old ("E-MINI S&P 500 STOCK INDEX - CME") and new name.
        # MICRO variant is excluded by deduplicate_by_date(); highest OI wins.
        "query_name": "E-MINI S&P 500",
        "name_must_not_contain": "MICRO",              # belt-and-suspenders: skip micro contract
        "price_symbol": "ES=F",
        "price_label": "S&P 500",
    },
    {
        "key": "nasdaq",
        "title": "Nasdaq Mini",
        "subtitle": "US Equities",
        "report_family": "tff",
        # Post-2022 CFTC name: "NASDAQ-100 Consolidated - CHICAGO MERCANTILE EXCHANGE"
        # Old name was "NASDAQ-100 STOCK INDEX (MINI) - CME".  Both contain "NASDAQ-100".
        "query_name": "NASDAQ-100",
        "name_must_not_contain": "MICRO",              # exclude micro variant
        "price_symbol": "NQ=F",
        "price_label": "Nasdaq 100",
    },
    {
        "key": "us10y",
        "title": "UST 10Y Note",
        "subtitle": "Rates",
        "report_family": "tff",
        # Post-2022 CFTC name: "UST 10Y NOTE - CHICAGO BOARD OF TRADE"
        # Old name was "10-YEAR U.S. TREASURY NOTES - CHICAGO BOARD OF TRADE".
        # "UST 10Y NOTE" does NOT match the Ultra variant ("ULTRA UST 10Y"), so no extra filter needed.
        "query_name": "UST 10Y NOTE",
        "price_symbol": "ZN=F",
        "price_label": "US 10Y Note",
    },
    {
        "key": "vix",
        "title": "VIX Futures",
        "subtitle": "Volatility",
        "report_family": "tff",
        "query_name": "VIX FUTURES",
        "price_symbol": "^VIX",
        "price_label": "VIX",
    },
    {
        "key": "eurfx",
        "title": "Euro FX",
        "subtitle": "FX",
        "report_family": "tff",
        "query_name": "EURO FX",
        "name_must_contain": "CHICAGO MERCANTILE",   # pin to CME listing only
        "name_must_not_contain": "/",                # exclude EUR/GBP, EUR/JPY cross-rates
        "price_symbol": "EURUSD=X",
        "price_label": "EUR/USD",
    },
    {
        "key": "gbpfx",
        "title": "British Pound",
        "subtitle": "FX",
        "report_family": "tff",
        # Post-2022 CFTC name dropped "STERLING": "BRITISH POUND - CHICAGO MERCANTILE EXCHANGE"
        # Old name was "BRITISH POUND STERLING - CME".  Both contain "BRITISH POUND".
        "query_name": "BRITISH POUND",
        "name_must_not_contain": "/",                  # exclude EUR/GBP and other cross-rates
        "price_symbol": "GBPUSD=X",
        "price_label": "GBP/USD",
    },
    {
        "key": "dxy",
        "title": "USD Index",
        "subtitle": "FX",
        "report_family": "tff",
        # Post-2022 CFTC name: "USD INDEX - ICE FUTURES U.S."
        # Old name was "U.S. DOLLAR INDEX - ICE FUTURES U.S." — "USD INDEX" ≠ "U.S. DOLLAR INDEX"
        # so the LIKE query won't match historical rows; the chart will show post-2022 data only,
        # which is still ~4 years and sufficient for positioning analysis.
        "query_name": "USD INDEX",
        "price_symbol": "DX-Y.NYB",
        "price_label": "DXY",
    },
    {
        "key": "bitcoin",
        "title": "Bitcoin Futures",
        "subtitle": "Crypto",
        "report_family": "tff",
        "query_name": "BITCOIN",
        "name_must_contain": "CHICAGO MERCANTILE",   # pin to CME listing only
        "price_symbol": "BTC-USD",
        "price_label": "BTC/USD",
    },
    {
        "key": "gold",
        "title": "Gold",
        "subtitle": "Commodities",
        "report_family": "disaggregated",
        "query_name": "GOLD",
        "price_symbol": "GC=F",
        "price_label": "Gold Futures",
    },
    {
        "key": "wti",
        "title": "WTI Crude",
        "subtitle": "Commodities",
        "report_family": "disaggregated",
        "query_name": "CRUDE OIL, LIGHT SWEET",
        "price_symbol": "CL=F",
        "price_label": "WTI Futures",
    },
    {
        "key": "corn",
        "title": "Corn",
        "subtitle": "Commodities",
        "report_family": "disaggregated",
        "query_name": "CORN",
        "price_symbol": "ZC=F",
        "price_label": "Corn Futures",
    },
]


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def parse_num(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def fetch_json(url: str, params: Optional[Dict[str, Any]] = None) -> Any:
    response = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def fetch_price_series(symbol: str) -> List[Dict[str, Any]]:
    try:
        payload = fetch_json(YAHOO_CHART.format(symbol=symbol))
        result = payload["chart"]["result"][0]
        timestamps = result.get("timestamp", [])
        quote = result.get("indicators", {}).get("quote", [{}])[0]
        closes = quote.get("close", [])
        series = []
        for ts, close in zip(timestamps, closes):
            if close is None:
                continue
            series.append({"timestamp": ts, "close": close})
        return series
    except Exception:
        return []


def none_safe_sub(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return a - b


def normalize_tff_row(row: Dict[str, Any]) -> Dict[str, Any]:
    asset_mgr_long = parse_num(row.get("asset_mgr_positions_long"))
    asset_mgr_short = parse_num(row.get("asset_mgr_positions_short"))
    lev_long = parse_num(row.get("lev_money_positions_long"))
    lev_short = parse_num(row.get("lev_money_positions_short"))
    dealer_long = parse_num(row.get("dealer_positions_long_all"))
    dealer_short = parse_num(row.get("dealer_positions_short_all"))
    other_long = parse_num(row.get("other_rept_positions_long"))
    other_short = parse_num(row.get("other_rept_positions_short"))
    oi = parse_num(row.get("open_interest_all"))

    return {
        "date": row.get("report_date_as_yyyy_mm_dd"),
        "market_name": row.get("market_and_exchange_names"),
        "open_interest": oi,
        "primary_long": lev_long,
        "primary_short": lev_short,
        "primary_net": none_safe_sub(lev_long, lev_short),
        "secondary_long": asset_mgr_long,
        "secondary_short": asset_mgr_short,
        "secondary_net": none_safe_sub(asset_mgr_long, asset_mgr_short),
        "tertiary_long": dealer_long,
        "tertiary_short": dealer_short,
        "tertiary_net": none_safe_sub(dealer_long, dealer_short),
        "other_long": other_long,
        "other_short": other_short,
        "report_family": "tff",
    }


def normalize_disagg_row(row: Dict[str, Any]) -> Dict[str, Any]:
    managed_long = parse_num(row.get("m_money_positions_long_all"))
    managed_short = parse_num(row.get("m_money_positions_short_all"))
    producer_long = parse_num(row.get("prod_merc_positions_long"))
    producer_short = parse_num(row.get("prod_merc_positions_short"))
    swap_long = parse_num(row.get("swap_positions_long_all"))
    swap_short = parse_num(row.get("swap_positions_short_all"))
    oi = parse_num(row.get("open_interest_all"))

    # For disaggregated (commodity) reports the analytically correct pairing is
    # Managed Money (fast money / CTA proxy) vs. Producers/Commercials (natural
    # hedgers with fundamental supply/demand information).  Swap Dealers are
    # intermediaries — they move inversely to MM as counterparties and would
    # appear as a misleading "inverse" secondary line if used here.
    return {
        "date": row.get("report_date_as_yyyy_mm_dd"),
        "market_name": row.get("market_and_exchange_names"),
        "open_interest": oi,
        "primary_long": managed_long,
        "primary_short": managed_short,
        "primary_net": none_safe_sub(managed_long, managed_short),
        "secondary_long": producer_long,
        "secondary_short": producer_short,
        "secondary_net": none_safe_sub(producer_long, producer_short),
        "tertiary_long": swap_long,
        "tertiary_short": swap_short,
        "tertiary_net": none_safe_sub(swap_long, swap_short),
        "report_family": "disaggregated",
    }


def sort_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(rows, key=lambda x: x.get("date") or "")


def _safe_oi(row: Dict[str, Any]) -> float:
    """Return open interest as float; 0.0 on any parse failure."""
    val = row.get("open_interest_all")
    if val is None:
        return 0.0
    try:
        return float(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return 0.0


def deduplicate_by_date(raw_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep exactly one raw API row per report date.

    The CFTC LIKE query can return multiple contract variants for the same date
    (standard + COMBINED + MICRO + cross-rates etc.).  Strategy:

    1. Drop MICRO / MINI-SIZED sub-standard contracts (often incomplete data).
    2. Among remaining rows for the same date, keep the one with the highest
       open_interest_all.

    This naturally handles the CFTC's post-2022 switch from per-exchange to
    COMBINED-only reporting: COMBINED rows have the highest aggregate OI for
    recent dates and are selected automatically.  For older dates where both
    individual and COMBINED exist, COMBINED still wins (higher OI), giving a
    consistent series throughout.
    """
    from collections import defaultdict

    # Drop sub-standard contract variants
    EXCLUDE = ("MICRO", "MINI-SIZED")
    filtered = [
        r for r in raw_rows
        if not any(kw in str(r.get("market_and_exchange_names", "")).upper() for kw in EXCLUDE)
    ]
    if not filtered:
        filtered = raw_rows  # fallback: keep everything if nothing survives

    # Group by normalised date (YYYY-MM-DD), keep highest open interest
    by_date: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in filtered:
        date_key = str(row.get("report_date_as_yyyy_mm_dd") or "")[:10]
        by_date[date_key].append(row)

    result = []
    for date_rows in by_date.values():
        result.append(max(date_rows, key=_safe_oi))
    return result


def _cot_from_base(key: str) -> List[Dict[str, Any]]:
    """The cot array sourced from data-core (S13c), truncated to LOOKBACK weeks to
    preserve this dashboard's window. [] -> caller uses the CFTC fallback below."""
    if _cot_consumer is None:
        return []
    try:
        rows = _cot_consumer.cot_rows(key)
        return rows[-LOOKBACK:] if rows else []
    except Exception as exc:
        print(f"  [{key}] base read failed ({exc}); CFTC fallback")
        return []


def _assemble(market: Dict[str, Any], cot: List[Dict[str, Any]],
              prices: List[Dict[str, Any]], source: str) -> Dict[str, Any]:
    """Build the markets/<key>.json payload (identical shape regardless of source)."""
    family = market["report_family"]
    base_url = BASE_TFF if family == "tff" else BASE_DISAGG
    return {
        "metadata": {
            "key": market["key"],
            "title": market["title"],
            "subtitle": market["subtitle"],
            "report_family": family,
            "source_url": base_url,
            "price_symbol": market["price_symbol"],
            "price_label": market["price_label"],
            "record_count": len(cot),
            "cot_source": source,
        },
        "cot": cot,
        "prices": prices,
    }


def fetch_market(market: Dict[str, Any]) -> Dict[str, Any]:
    # S13c base-first: the guarded base holds the full cohort history for every
    # migrated market; only WTI (oil-reuse) + base-absent series hit CFTC below.
    base_cot = _cot_from_base(market["key"])
    if base_cot:
        prices = fetch_price_series(market["price_symbol"])
        return _assemble(market, base_cot, prices, "data-core")

    family = market["report_family"]
    base_url = BASE_TFF if family == "tff" else BASE_DISAGG

    params = {
        "$limit": 5000,
        "$order": "report_date_as_yyyy_mm_dd DESC",  # most recent first → ensures we get latest data within limit
        "$where": f"upper(market_and_exchange_names) like '%{market['query_name'].upper()}%'",
    }
    rows = fetch_json(base_url, params=params)

    # Step 1 — log unique market names found (diagnostic: visible in Actions logs)
    unique_names = sorted({r.get("market_and_exchange_names", "") for r in rows})
    print(f"  [{market['key']}] {len(rows)} raw rows, unique names: {unique_names}")

    # Step 2 — apply optional name filters (pin to specific exchange / exclude cross-rates)
    must_contain = market.get("name_must_contain")
    if must_contain:
        pinned = [
            r for r in rows
            if must_contain.upper() in str(r.get("market_and_exchange_names", "")).upper()
        ]
        if pinned:
            rows = pinned
        else:
            print(f"  [{market['key']}] WARNING: name_must_contain '{must_contain}' matched nothing — using all rows")

    must_not_contain = market.get("name_must_not_contain")
    if must_not_contain:
        rows = [
            r for r in rows
            if must_not_contain.upper() not in str(r.get("market_and_exchange_names", "")).upper()
        ]

    # Step 4 — one row per date: drop MICRO/MINI-SIZED, keep highest open interest
    rows = deduplicate_by_date(rows)

    normalizer = normalize_tff_row if family == "tff" else normalize_disagg_row
    # Sort ASC first (API returned DESC), then take the most recent LOOKBACK weeks
    normalized = sort_rows([normalizer(row) for row in rows])[-LOOKBACK:]
    prices = fetch_price_series(market["price_symbol"])
    return _assemble(market, normalized, prices, "cftc")


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    ensure_dir(DATA_DIR)
    ensure_dir(MARKETS_DIR)
    ensure_dir(DERIVED_DIR)

    manifest = {
        "generated_at": None,
        "sources": {
            "tff": BASE_TFF,
            "disaggregated": BASE_DISAGG,
            "price": YAHOO_CHART,
        },
        "markets": [],
        "failures": [],
    }

    for market in MARKETS:
        try:
            payload = fetch_market(market)
            output_name = f"{market['key']}.json"
            write_json(MARKETS_DIR / output_name, payload)
            manifest["markets"].append(
                {
                    "key": market["key"],
                    "title": market["title"],
                    "subtitle": market["subtitle"],
                    "report_family": market["report_family"],
                    "file": f"markets/{output_name}",
                    "record_count": payload["metadata"]["record_count"],
                    "price_label": market["price_label"],
                }
            )
            print(f"✓ {market['key']}: {payload['metadata']['record_count']} rows")
        except Exception as exc:
            manifest["failures"].append(
                {"key": market["key"], "title": market["title"], "error": str(exc)}
            )
            print(f"✗ {market['key']}: {exc}")

    manifest["generated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    manifest["derived_files"] = {
        "watchlist": "derived/watchlist.json",
        "weekly_changes": "derived/weekly_changes.json",
        "narratives": "derived/narratives.json",
    }
    write_json(DATA_DIR / "manifest.json", manifest)


if __name__ == "__main__":
    main()
