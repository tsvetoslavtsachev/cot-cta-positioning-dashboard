#!/usr/bin/env python3
"""Build derived files used by the dashboard.

Outputs:
- data/derived/watchlist.json
- data/derived/weekly_changes.json
- data/derived/narratives.json
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DERIVED_DIR = DATA_DIR / "derived"



def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))



def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")



def percentile(values: List[float], current: float) -> float:
    if not values:
        return 50.0
    below = sum(1 for v in values if v <= current)
    return round(100.0 * below / len(values), 2)



def zscore(values: List[float], current: float) -> float:
    if len(values) < 2:
        return 0.0
    mu = mean(values)
    sigma = pstdev(values)
    if sigma == 0:
        return 0.0
    return round((current - mu) / sigma, 4)



def sign(num: Optional[float]) -> int:
    if num is None:
        return 0
    if num > 0:
        return 1
    if num < 0:
        return -1
    return 0



def pct_change(new: Optional[float], old: Optional[float]) -> Optional[float]:
    if new is None or old in (None, 0):
        return None
    return ((new - old) / abs(old)) * 100.0



def score_market(latest: Dict[str, Any], previous_4w: Optional[Dict[str, Any]]) -> float:
    primary_pct = latest.get("primary_percentile", 50.0)
    primary_z = latest.get("primary_zscore", 0.0)
    pct_extreme = abs(primary_pct - 50.0) / 50.0
    z_extreme = min(abs(primary_z), 3.0) / 3.0

    delta_4w = latest.get("primary_delta_4w") or 0.0
    oi = latest.get("open_interest") or 1.0
    momentum_4w = min(abs(delta_4w) / max(oi, 1.0) * 10.0, 1.0)

    divergence_score = 1.0 if sign(latest.get("primary_net")) != sign(latest.get("secondary_net")) else 0.0

    oi_change = latest.get("oi_delta_4w") or 0.0
    oi_confirmation = min(abs(oi_change) / max(oi, 1.0) * 10.0, 1.0)

    price_4w = latest.get("price_change_4w_pct") or 0.0
    price_position_dislocation = 1.0 if sign(price_4w) != sign(delta_4w) and abs(price_4w) > 1.0 else 0.0

    score = (
        0.30 * pct_extreme
        + 0.20 * z_extreme
        + 0.15 * momentum_4w
        + 0.15 * divergence_score
        + 0.10 * oi_confirmation
        + 0.10 * price_position_dislocation
    )
    return round(score * 100.0, 2)



def regime_label(row: Dict[str, Any]) -> str:
    pct = row.get("primary_percentile", 50.0)
    price = row.get("price_change_4w_pct") or 0.0
    delta = row.get("primary_delta_4w") or 0.0
    primary_sign = sign(row.get("primary_net"))
    secondary_sign = sign(row.get("secondary_net"))

    if primary_sign != 0 and secondary_sign != 0 and primary_sign != secondary_sign:
        return "Divergence"
    if pct >= 85 and delta > 0:
        return "Crowded Long"
    if pct <= 15 and delta < 0:
        return "Crowded Short"
    if pct <= 15 and price > 0:
        return "Contrarian Long"
    if pct >= 85 and price < 0:
        return "Contrarian Short"
    return "Neutral / Transition"



def build_market_summary(market_meta: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    cot = payload.get("cot", [])
    if not cot:
        raise ValueError("No COT rows found")

    nets = [r.get("primary_net") for r in cot if r.get("primary_net") is not None]
    latest = dict(cot[-1])
    previous_4w = cot[-5] if len(cot) >= 5 else None

    latest["primary_percentile"] = percentile(nets, latest.get("primary_net") or 0.0)
    latest["primary_zscore"] = zscore(nets, latest.get("primary_net") or 0.0)

    if previous_4w:
        latest["primary_delta_4w"] = safe_sub(latest.get("primary_net"), previous_4w.get("primary_net"))
        latest["oi_delta_4w"] = safe_sub(latest.get("open_interest"), previous_4w.get("open_interest"))
    else:
        latest["primary_delta_4w"] = 0.0
        latest["oi_delta_4w"] = 0.0

    latest["price_change_4w_pct"] = None
    prices = payload.get("prices", [])
    if len(prices) >= 5:
        latest_close = prices[-1].get("close")
        prior_close = prices[-5].get("close")
        latest["price_change_4w_pct"] = round(pct_change(latest_close, prior_close) or 0.0, 2)

    latest["regime"] = regime_label(latest)
    latest["watchlist_score"] = score_market(latest, previous_4w)
    latest["market_key"] = market_meta["key"]
    latest["market_title"] = market_meta["title"]
    latest["subtitle"] = market_meta.get("subtitle")
    latest["price_label"] = market_meta.get("price_label")
    latest["takeaway"] = build_takeaway(latest)
    latest["changes"] = build_changes(latest, previous_4w)
    latest["narrative"] = build_narrative(latest)
    return latest



def safe_sub(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return a - b



def build_takeaway(row: Dict[str, Any]) -> str:
    regime = row.get("regime")
    pct = row.get("primary_percentile", 50.0)
    delta = row.get("primary_delta_4w") or 0.0
    if regime == "Divergence":
        return "Fast money and slower cohorts are pulling in different directions."
    if regime == "Crowded Long":
        return f"Positioning remains stretched on the long side ({pct:.0f}th percentile)."
    if regime == "Crowded Short":
        return f"Short crowding remains heavy ({pct:.0f}th percentile from the bottom)."
    if regime == "Contrarian Long":
        return "Bearish positioning is no longer fully confirmed by price action."
    if regime == "Contrarian Short":
        return "Bullish positioning looks vulnerable to an unwind."
    if delta > 0:
        return "Positioning is improving but not yet in an extreme regime."
    return "Positioning is easing without a clear high-conviction signal."



def build_changes(latest: Dict[str, Any], previous_4w: Optional[Dict[str, Any]]) -> List[str]:
    changes: List[str] = []
    delta = latest.get("primary_delta_4w") or 0.0
    pct = latest.get("primary_percentile", 50.0)
    price = latest.get("price_change_4w_pct")
    regime = latest.get("regime")

    direction = "added to longs" if delta > 0 else "added to shorts" if delta < 0 else "held positioning broadly steady"
    changes.append(f"Primary cohort {direction} over the last 4 weeks.")
    changes.append(f"Primary positioning sits near the {pct:.0f}th percentile of the selected history.")
    if sign(latest.get("primary_net")) != sign(latest.get("secondary_net")):
        changes.append("Primary and secondary cohorts remain in divergence.")
    if price is not None:
        price_dir = "rose" if price > 0 else "fell" if price < 0 else "was flat"
        changes.append(f"Price {price_dir} {abs(price):.2f}% over the same 4-week window.")
    changes.append(f"Current regime: {regime}.")
    return changes[:5]



def build_narrative(row: Dict[str, Any]) -> str:
    market = row.get("market_title")
    regime = row.get("regime")
    pct = row.get("primary_percentile", 50.0)
    delta = row.get("primary_delta_4w") or 0.0
    delta_word = "rose" if delta > 0 else "fell" if delta < 0 else "was broadly unchanged"
    delta_abs = abs(delta)
    price = row.get("price_change_4w_pct")
    sec_relation = "diverging from" if sign(row.get("primary_net")) != sign(row.get("secondary_net")) else "confirmed by"
    price_phrase = "Price context is unavailable."
    if price is not None:
        direction = "up" if price > 0 else "down" if price < 0 else "flat"
        price_phrase = f"Price is {direction} {abs(price):.2f}% over the same 4-week window."
    return (
        f"{market} remains in a {regime} setup. Primary positioning is at the {pct:.0f}th percentile over the recent history. "
        f"Over the last 4 weeks, net positioning {delta_word} by {delta_abs:,.0f} contracts and is currently {sec_relation} the secondary cohort. "
        f"{price_phrase}"
    )



def main() -> None:
    manifest = read_json(DATA_DIR / "manifest.json")
    watchlist = []
    weekly_changes = []
    narratives = []

    for market in manifest.get("markets", []):
        payload = read_json(DATA_DIR / market["file"])
        summary = build_market_summary(market, payload)
        watchlist.append(
            {
                "market": summary["market_key"],
                "title": summary["market_title"],
                "subtitle": summary.get("subtitle"),
                "date": summary.get("date"),
                "score": summary.get("watchlist_score"),
                "regime": summary.get("regime"),
                "primary_percentile": summary.get("primary_percentile"),
                "primary_zscore": summary.get("primary_zscore"),
                "primary_net": summary.get("primary_net"),
                "primary_delta_4w": summary.get("primary_delta_4w"),
                "secondary_net": summary.get("secondary_net"),
                "price_change_4w_pct": summary.get("price_change_4w_pct"),
                "takeaway": summary.get("takeaway"),
            }
        )
        weekly_changes.append(
            {
                "market": summary["market_key"],
                "title": summary["market_title"],
                "date": summary.get("date"),
                "changes": summary.get("changes"),
            }
        )
        narratives.append(
            {
                "market": summary["market_key"],
                "title": summary["market_title"],
                "date": summary.get("date"),
                "narrative": summary.get("narrative"),
            }
        )

    watchlist.sort(key=lambda x: x.get("score") or 0.0, reverse=True)
    for index, row in enumerate(watchlist, start=1):
        row["rank"] = index

    write_json(DERIVED_DIR / "watchlist.json", watchlist)
    write_json(DERIVED_DIR / "weekly_changes.json", weekly_changes)
    write_json(DERIVED_DIR / "narratives.json", narratives)
    print("✓ Derived files written")


if __name__ == "__main__":
    main()
