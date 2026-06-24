"""Offline unit tests for the windowed-attention helpers (no network)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from bdor.features.hype import _aggregate, _baseline_median, _window_mean


def _daily(player: str, dates: list[str], vals: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {"player": player, "date": pd.to_datetime(dates), "views": vals}
    )


def test_window_mean_inclusive_start_exclusive_end():
    d = _daily("P", ["2018-01-01", "2018-01-02", "2018-01-03"], [10, 20, 30])
    # [01-01, 01-03) -> 01-01 + 01-02 = mean(10,20) = 15
    s, e = pd.Timestamp("2018-01-01"), pd.Timestamp("2018-01-03")
    assert _window_mean(d, s, e, "views") == 15.0
    out_of_range = _window_mean(d, pd.Timestamp("2019-01-01"), pd.Timestamp("2019-02-01"), "views")
    assert np.isnan(out_of_range)


def test_baseline_median_trailing_window():
    # 3 days just before perf_start 2018-01-01 -> median of [4,6,8] = 6
    d = _daily("P", ["2017-12-29", "2017-12-30", "2017-12-31", "2018-01-05"], [4, 6, 8, 999])
    assert _baseline_median(d, pd.Timestamp("2018-01-01"), "views", days=365) == 6.0


def _windows() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "award_year": [2018],
            "perf_start": pd.to_datetime(["2018-01-01"]),
            "hype_cut": pd.to_datetime(["2018-10-09"]),
        }
    ).set_index("award_year")


def test_aggregate_window_spike_vs_baseline():
    # Low baseline in 2017, big spike inside the 2018 window.
    dates = ["2017-06-01", "2018-06-01"]
    d = _daily("Spiker", dates, [5.0, 5000.0])
    out = _aggregate(d, _windows(), "views", "pv")
    row = out.iloc[0]
    assert row["pv_window_mean"] == 5000.0
    assert row["pv_baseline"] == 5.0
    assert row["pv_log_ratio"] > 5  # window >> baseline
    assert bool(row["pv_low_baseline"]) is True  # baseline 5 < 10


def test_aggregate_skips_year_with_no_window_data():
    # Only baseline-period data, nothing inside the 2018 window -> skipped.
    d = _daily("OnlyBaseline", ["2017-06-01"], [100.0])
    out = _aggregate(d, _windows(), "views", "pv")
    assert out.empty


def test_aggregate_steady_star_low_ratio():
    # Same level inside and before the window -> log_ratio ~ 0.
    d = _daily("Steady", ["2017-06-01", "2018-06-01"], [1000.0, 1000.0])
    out = _aggregate(d, _windows(), "views", "pv")
    assert abs(out.iloc[0]["pv_log_ratio"]) < 0.01
    assert bool(out.iloc[0]["pv_low_baseline"]) is False


def test_aggregate_reused_for_gdelt_volume_with_gd_prefix():
    # The GDELT second proxy reuses the same generic aggregator with a different value column
    # ("volume") and prefix ("gd"); columns must be gd_*, never pv_*.
    d = pd.DataFrame(
        {"player": "Spiker", "date": pd.to_datetime(["2017-06-01", "2018-06-01"]),
         "volume": [5.0, 5000.0]}
    )
    out = _aggregate(d, _windows(), "volume", "gd")
    row = out.iloc[0]
    assert row["gd_window_mean"] == 5000.0
    assert row["gd_baseline"] == 5.0
    assert {"gd_window_mean", "gd_baseline", "gd_low_baseline", "gd_log_ratio"} <= set(out.columns)
    assert not any(c.startswith("pv_") for c in out.columns)
