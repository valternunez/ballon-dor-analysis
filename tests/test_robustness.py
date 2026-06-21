"""Offline unit tests for the robustness-panel helpers (no network, no fitting)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from bdor.models.nomination import logit_anchor
from bdor.models.robustness import _PANEL_COLS, _jackknife, _leaky_windows, _strict_windows


def test_leaky_windows_pushes_hype_cut_to_ceremony():
    from bdor.windows import load_windows

    leaky = _leaky_windows()
    orig = load_windows()
    # the leaky cut lands AFTER the ceremony (captures the announcement spike) and is well past
    # the original shortlist cut
    assert (leaky["hype_cut"] > leaky["ceremony_date"]).all()
    assert (leaky["hype_cut"] > orig["hype_cut"]).all()


def test_strict_windows_caps_calendar_perf_end_at_ceremony():
    from bdor.windows import load_windows

    strict = _strict_windows()
    orig = load_windows()
    cal = orig["regime"] == "calendar"
    # calendar years: perf window no longer runs past the ceremony (the ~4-week tail is dropped)
    assert (strict.loc[cal, "perf_end"] <= strict.loc[cal, "ceremony_date"]).all()
    assert (strict.loc[cal, "perf_end"] < orig.loc[cal, "perf_end"]).all()
    # season years: unchanged (their window already ends before the shortlist)
    assert (strict.loc[~cal, "perf_end"] == orig.loc[~cal, "perf_end"]).all()


def test_jackknife_holds_out_each_year_once_and_summarizes_spread():
    # synthetic prep: 4 years, the cell_fn returns the dropped year's index as the "estimate"
    prep = pd.DataFrame({"award_year": ["2018", "2019", "2021", "2022"] * 3})
    seen = []

    def cell_fn(sub):
        held = set(prep["award_year"]) - set(sub["award_year"])
        seen.append(held.pop())
        return (float(len(sub)), 0.0, 0.0, len(sub))  # estimate = remaining-row count

    row = _jackknife("B_placement", prep, cell_fn)
    assert sorted(seen) == ["2018", "2019", "2021", "2022"]  # each year out exactly once
    assert set(_PANEL_COLS) <= set(row)
    assert row["spec"] == "jackknife_year"
    assert row["ci_low"] <= row["estimate"] <= row["ci_high"]  # spread envelope brackets median


def test_logit_anchor_returns_hperp_estimate_and_ci():
    rng = np.random.default_rng(0)
    n = 120
    h = rng.normal(size=n)
    # nomination probability rises with H_perp -> the anchor should recover a positive coefficient
    p = 1 / (1 + np.exp(-(0.5 + 1.2 * h)))
    df = pd.DataFrame(
        {
            "nominated": (rng.uniform(size=n) < p).astype(int),
            "h_perp_pv": h,
            "merit_z": rng.normal(size=n),
            "cl_round": rng.normal(size=n),
            "won_cl": rng.integers(0, 2, n),
            "won_league": rng.integers(0, 2, n),
            "tournament_result": rng.integers(0, 6, n).astype(float),
            "award_year": rng.choice(["2018", "2019", "2021"], n),
        }
    )
    out = logit_anchor(df)
    r = out.loc["h_perp_pv"]
    assert np.isfinite(r["estimate"]) and r["ci_low"] < r["ci_high"]
    assert r["estimate"] > 0  # signal recovered
