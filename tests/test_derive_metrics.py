"""Missing-data trap tests for derive_metrics.

These lock in the audit fix: a *missing* input must be flagged (None +
``data_quality``), never silently faked into a neutral 50 / z 0 or a false
0/100 extreme. Complete data must score exactly as before (regression).
"""

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import derive_metrics as dm  # noqa: E402


def wdate(i: int) -> str:
    return (date(2024, 1, 2) + timedelta(weeks=i)).isoformat()


def make_payload(nets, ois=None, secondary=None, prices=None):
    n = len(nets)
    if ois is None:
        ois = [100_000] * n
    if secondary is None:
        secondary = list(nets)  # same sign → not Divergence
    cot = []
    for i in range(n):
        cot.append(
            {
                "date": wdate(i),
                "primary_net": nets[i],
                "secondary_net": secondary[i],
                "open_interest": ois[i],
            }
        )
    return {"cot": cot, "prices": prices or []}


META = {"key": "test", "title": "Test Market"}


def test_complete_data_scores_normally():
    nets = [float(x) for x in range(100, 100 + 20)]
    summary = dm.build_market_summary(META, make_payload(nets))
    assert summary["primary_percentile"] is not None
    assert summary["primary_zscore"] is not None
    assert 0.0 <= summary["primary_percentile"] <= 100.0
    assert summary["regime"] != "Insufficient Data"
    assert summary["watchlist_score"] is not None
    assert summary["data_quality"] == []


def test_missing_latest_net_is_flagged_not_faked():
    nets = [-200_000.0 - i * 1000 for i in range(20)]
    nets[-1] = None
    summary = dm.build_market_summary(META, make_payload(nets))
    assert summary["primary_percentile"] is None  # NOT 50, NOT 100
    assert summary["primary_zscore"] is None
    assert summary["regime"] == "Insufficient Data"
    assert summary["watchlist_score"] is None
    assert "missing_primary_net" in summary["data_quality"]
    assert "missing" in summary["takeaway"].lower()


def test_missing_oi_drops_momentum_not_clamps_to_max():
    base = {
        "primary_percentile": 90.0,
        "primary_zscore": 2.0,
        "primary_delta_4w": 50_000.0,
        "oi_delta_4w": 50_000.0,
        "primary_net": 100_000,
        "secondary_net": 100_000,
        "price_change_4w_pct": 0.0,
    }
    s_with_oi = dm.score_market(dict(base, open_interest=2_000_000), None)
    s_missing = dm.score_market(dict(base, open_interest=None), None)
    assert s_missing < s_with_oi


def test_missing_oi_is_flagged():
    nets = [float(x) for x in range(100, 120)]
    ois = [100_000] * 19 + [None]
    summary = dm.build_market_summary(META, make_payload(nets, ois=ois))
    assert "missing_open_interest" in summary["data_quality"]
    assert summary["watchlist_score"] is not None


def test_insufficient_history_is_flagged():
    nets = [float(x) for x in range(100, 106)]  # 6 < MIN_HISTORY_OBS
    summary = dm.build_market_summary(META, make_payload(nets))
    assert summary["primary_percentile"] is None
    assert summary["primary_zscore"] is None
    assert any(d.startswith("insufficient_history") for d in summary["data_quality"])


def test_zero_dispersion_is_flagged():
    nets = [500.0] * 12
    summary = dm.build_market_summary(META, make_payload(nets))
    assert summary["primary_percentile"] is None
    assert summary["primary_zscore"] is None
    assert "zero_dispersion" in summary["data_quality"]


def test_pct_change_reference_no_div_by_zero():
    assert dm.pct_change(10.0, 0) is None
    assert dm.pct_change(10.0, None) is None
    assert dm.pct_change(None, 5.0) is None
    assert dm.pct_change(10.0, 5.0) == pytest.approx(100.0)


def test_percentile_empty_and_zscore_short():
    assert dm.percentile([], 5.0) == 50.0
    assert dm.zscore([5.0], 5.0) == 0.0
