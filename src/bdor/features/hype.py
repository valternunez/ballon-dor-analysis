"""Windowed attention aggregates — inputs to the H⊥ regression.

H⊥ ("attention beyond merit") is a SINGLE regression (PROJECT_NOTES "H⊥ — LOCKED"):
    log(window attention) ~ log(baseline) + merit + team-success   -> residual.
This module produces that regression's *attention inputs* per (player, award_year):
  * window_mean  — mean daily attention over the judged window [perf_start, hype_cut)
  * baseline     — median daily attention over the trailing 12 months before perf_start

It does NOT compute a final de-famed value (that falls out of the regression once merit +
team-success are joined). The aggregator is generic on the value column, so it drops onto GDELT
once that pull completes. See docs/windowing.md for the leakage-safe window definitions.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..cache import cached_frame
from ..data import pageviews
from ..windows import load_windows

PAGEVIEW_CACHE = "pageview_attention"
_BASELINE_DAYS = 365
_LOW_BASELINE = 10.0  # daily-views threshold below which the baseline is thin/unreliable
_PSEUDOCOUNT = 1.0


# --- pure helpers (offline-testable) ----------------------------------------

def _window_mean(daily: pd.DataFrame, start, end, value_col: str) -> float:
    """Mean of value over [start, end). NaN if no rows."""
    mask = (daily["date"] >= start) & (daily["date"] < end)
    vals = daily.loc[mask, value_col]
    return float(vals.mean()) if len(vals) else np.nan


def _baseline_median(
    daily: pd.DataFrame, perf_start, value_col: str, days: int = _BASELINE_DAYS
) -> float:
    """Median of value over [perf_start - days, perf_start). NaN if no rows."""
    start = perf_start - pd.Timedelta(days=days)
    mask = (daily["date"] >= start) & (daily["date"] < perf_start)
    vals = daily.loc[mask, value_col]
    return float(vals.median()) if len(vals) else np.nan


def _aggregate(
    daily: pd.DataFrame, windows: pd.DataFrame, value_col: str, prefix: str
) -> pd.DataFrame:
    """Per (player, award_year): window_mean + trailing baseline (+ diagnostic log-ratio)."""
    rows: list[dict] = []
    for player, pdaily in daily.groupby("player"):
        for award_year, w in windows.iterrows():
            window_mean = _window_mean(pdaily, w["perf_start"], w["hype_cut"], value_col)
            if np.isnan(window_mean):
                continue  # player has no attention in this year's window — skip
            baseline = _baseline_median(pdaily, w["perf_start"], value_col)
            base_for_log = 0.0 if (baseline is None or np.isnan(baseline)) else baseline
            log_ratio = np.log(window_mean + _PSEUDOCOUNT) - np.log(base_for_log + _PSEUDOCOUNT)
            rows.append(
                {
                    "player": player,
                    "award_year": int(award_year),
                    f"{prefix}_window_mean": window_mean,
                    f"{prefix}_baseline": baseline,
                    f"{prefix}_low_baseline": bool(
                        np.isnan(baseline) or baseline < _LOW_BASELINE
                    ),
                    f"{prefix}_log_ratio": log_ratio,
                }
            )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(
        ["award_year", f"{prefix}_log_ratio"], ascending=[True, False]
    ).reset_index(drop=True)


# --- build ------------------------------------------------------------------

def _build_pageview_attention() -> pd.DataFrame:
    daily = pageviews.pull()
    return _aggregate(daily, load_windows(), value_col="views", prefix="pv")


def build_pageview_attention(*, refresh: bool = False) -> pd.DataFrame:
    """Return per-(player, award_year) pageview attention aggregates (cached)."""
    return cached_frame(PAGEVIEW_CACHE, _build_pageview_attention, refresh=refresh)
