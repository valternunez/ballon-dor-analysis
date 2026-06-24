"""Offline unit tests for the H⊥ OLS helper and vote-share outcome (no network)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import bdor.features.hperp as hp
from bdor.features.hperp import _REGRESSORS, _ols_residual


def test_defame_regressors_exclude_tournament_result():
    # nation exists only for finishers -> tournament_result would residualize inconsistently across
    # the pool (and is a finisher-only leakage risk). It must NOT be a de-fame regressor.
    assert "tournament_result" not in _REGRESSORS
    assert "log_baseline" in _REGRESSORS and "merit_pc1" in _REGRESSORS


def test_ols_residual_recovers_perfect_fit():
    rng = np.random.default_rng(0)
    x_raw = rng.normal(size=(50, 2))
    x = np.column_stack([np.ones(50), x_raw])
    beta_true = np.array([1.0, 2.0, -3.0])
    y = x @ beta_true  # no noise -> residuals ~0, R² ~1
    resid, beta, r2 = _ols_residual(y, x)
    assert np.allclose(resid, 0, atol=1e-8)
    assert np.allclose(beta, beta_true, atol=1e-8)
    assert abs(r2 - 1.0) < 1e-9


def test_ols_residual_orthogonal_to_regressors():
    rng = np.random.default_rng(1)
    x_raw = rng.normal(size=(80, 2))
    x = np.column_stack([np.ones(80), x_raw])
    y = x @ np.array([0.5, 1.0, 2.0]) + rng.normal(scale=0.5, size=80)
    resid, _, r2 = _ols_residual(y, x)
    # OLS residuals are orthogonal to each regressor column.
    assert np.allclose(x.T @ resid, 0, atol=1e-8)
    assert 0.0 <= r2 <= 1.0


@pytest.mark.parametrize("prefix", ["pv", "gd"])
def test_hperp_frame_prefix_selects_attention_and_output_column(monkeypatch, prefix):
    # hperp_frame(prefix=...) de-fames the matching {prefix}_* attention + writes h_perp_{prefix}.
    # Monkeypatch _candidate_frame so the test is fully offline (no merit/pool/attention pull).
    rng = np.random.default_rng(3)
    n = 15
    frame = pd.DataFrame(
        {
            "player": [f"P{i}" for i in range(n)],
            "player_key": [f"p{i}" for i in range(n)],
            "award_year": [2018] * n,
            f"{prefix}_baseline": rng.uniform(1, 100, n),
            f"{prefix}_window_mean": rng.uniform(1, 5000, n),
            "merit_pc1": rng.normal(size=n),
            "merit_pc2": rng.normal(size=n),
            "def_merit_z": np.nan,
            "cb_def_z": np.nan,
            "gk_merit_z": np.nan,
            "cl_round": rng.integers(0, 6, n).astype(float),
            "won_cl": rng.integers(0, 2, n),
            "won_league": rng.integers(0, 2, n),
            "minutes_share": rng.uniform(0, 1, n),
            "xg_share": rng.uniform(0, 0.4, n),
        }
    )
    monkeypatch.setattr(hp, "_candidate_frame", lambda att=None, merit_df=None: frame.copy())

    out = hp.hperp_frame(prefix=prefix)
    other = "gd" if prefix == "pv" else "pv"
    assert f"h_perp_{prefix}" in out.columns
    assert f"h_perp_{other}" not in out.columns
    assert out[f"h_perp_{prefix}"].notna().sum() == n  # every row has merit_pc1 -> H⊥ defined
    assert abs(out[f"h_perp_{prefix}"].mean()) < 1e-6  # OLS residuals (with intercept) sum to ~0


def test_vote_share_sums_to_one_per_year():
    # Mirror features._outcome on a synthetic awards frame.
    aw = pd.DataFrame(
        {
            "award_year": [2018, 2018, 2018, 2019, 2019],
            "player": ["A", "B", "C", "D", "E"],
            "rank": [1, 2, 3, 1, 2],
            "points": [600, 300, 100, 700, 300],
        }
    )
    year_total = aw.groupby("award_year")["points"].transform("sum")
    aw["vote_share"] = aw["points"] / year_total
    sums = aw.groupby("award_year")["vote_share"].sum()
    assert np.allclose(sums.to_numpy(), 1.0)
    assert abs(aw.loc[0, "vote_share"] - 0.6) < 1e-9  # 600 / 1000
