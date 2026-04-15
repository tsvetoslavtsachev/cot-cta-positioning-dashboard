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
from pathlib import Path
from typing import Dict, List, Any, Optional

import requests

BASE_TFF = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"
BASE_DISAGG = "https://publicreporting.cftc.gov/resource/kh3c-gbw2.json"
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=3y&interval=1wk"
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
        "query_name": "E-MINI S&P 500 STOCK INDEX",
        "price_symbol": "ES=F",
        "price_label": "S&P 500",
    },
    {
        "key": "nasdaq",
        "title": "Nasdaq Mini",
        "subtitle": "US Equities",
        "report_family": "tff",
        "query_name": "NASDAQ-100 STOCK INDEX",
        "price_symbol": "NQ=F",
        "price_label": "Nasdaq 100",
    },
    {
        "key": "us10y",
        "title": "UST 10Y Note",
        "subtitle": "Rates",
        "report_family": "tff",
        "query_name": "10-YEAR U.S. TREASURY NOTES",
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
        "price_symbol": "EURUSD=X",
        "price_label": "EUR/USD",
    },
    {
        "key": "gbpfx",
        "title": "British Pound",
        "subtitle": "FX",
        "report_family": "tff",
        "query_name": "BRITISH POUND STERLING",
        "price_symbol": "GBPUSD=X",
        "price_label": "GBP/USD",
    },
    {
        "key": "dxy",
        "title": "USD Index",
        "subtitle": "FX",
        "report_family": "tff",
        "query_name": "U.S. DOLLAR INDEX",
        "price_symbol": "DX-Y.NYB",
        "price_label": "DXY",
    },
    {
        "key": "bitcoin",
        "title": "Bitcoin Futures",
        "subtitle": "Crypto",
        "report_family": "tff",
        "query_name": "BITCOIN",
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

    return {
        "date": row.get("report_date_as_yyyy_mm_dd"),
        "market_name": row.get("market_and_exchange_names"),
        "open_interest": oi,
        "primary_long": managed_long,
        "primary_short": managed_short,
        "primary_net": none_safe_sub(managed_long, managed_short),
        "secondary_long": swap_long,
        "secondary_short": swap_short,
        "secondary_net": none_safe_sub(swap_long, swap_short),
        "tertiary_long": producer_long,
        "tertiary_short": producer_short,
        "tertiary_net": none_safe_sub(producer_long, producer_short),
        "report_family": "disaggregated",
    }



def none_safe_sub(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return a - b



def sort_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(rows, key=lambda x: x.get("date") or "")



def fetch_market(market: Dict[str, Any]) -> Dict[str, Any]:
    family = market["report_family"]
    if family == "tff":
        base_url = BASE_TFF
    else:
        base_url = BASE_DISAGG

    params = {
        "$limit": 5000,
        "$order": "report_date_as_yyyy_mm_dd ASC",
        "$where": f"upper(market_and_exchange_names) like '%{market['query_name'].upper()}%'",
    }
    rows = fetch_json(base_url, params=params)

    # Exclude combined/consolidated reports — they duplicate individual exchange rows
    # and cause apparent spikes when mixed with the standard series.
    rows = [
        r for r in rows
        if "COMBINED" not in str(r.get("market_and_exchange_names", "")).upper()
    ]

    normalizer = normalize_tff_row if family == "tff" else normalize_disagg_row
    normalized = [normalizer(row) for row in rows][-LOOKBACK:]
    normalized = sort_rows(normalized)
    prices = fetch_price_series(market["price_symbol"])

    payload = {
        "metadata": {
            "key": market["key"],
            "title": market["title"],
            "subtitle": market["subtitle"],
            "report_family": family,
            "source_url": base_url,
            "price_symbol": market["price_symbol"],
            "price_label": market["price_label"],
            "record_count": len(normalized),
        },
        "cot": normalized,
        "prices": prices,
    }
    return payload



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

    from datetime import datetime, timezone

    manifest["generated_at"] = datetime.now(