"""Offline unit tests for the Stage-B placement helpers (no network, no MCMC).

The Bayesian fit itself is validated by a scratch run + diagnostics (R̂/ESS), not here — these
tests cover the pure data-prep machinery: the Smithson–Verkuilen squeeze and `_prep`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from bdor.models.placement import _CONTINUOUS, _prep, _squeeze


def _synthetic_features() -> pd.DataFrame:
    """A small frame mirroring model_features: attackers (H⊥ present) + defenders (H⊥ NA)."""
    return pd.DataFrame(
        {
            "award_year": [2018, 2018, 2018, 2019, 2019, 2019],
            "player": [
                "Lionel Messi", "Cristiano Ronaldo", "Kevin De Bruyne",
                "Virgil van Dijk", "Sadio Mané", "Mohamed Salah",
            ],
            "vote_share": [0.30, 0.16, 0.0, 0.12, 0.05, 0.02],
            "h_perp_pv": [0.5, 1.2, -0.8, np.nan, 0.3, -0.1],  # van Dijk = defender, NA
            "merit_pc1": [4.0, 2.5, 6.0, np.nan, 1.5, 3.0],
            "merit_pc2": [0.2, -0.3, 1.1, np.nan, -0.5, 0.4],
            # non-attacking merit dims: NA for pure attackers -> filled 0 in _prep; a few carry a
            # value so each column has variance after standardization.
            "def_merit_z": [0.1, -0.2, np.nan, np.nan, 0.4, -0.3],
            "cb_def_z": [np.nan, np.nan, np.nan, 1.2, np.nan, 0.3],
            "gk_merit_z": [np.nan, 0.5, np.nan, np.nan, -0.4, np.nan],
            "cl_round": [4, 5, 3, 5, 5, 5],
            "won_cl": [False, True, False, True, True, True],
            "won_league": [True, True, True, False, False, False],
            "tournament_result": [3, 0, 0, 0, 0, 0],
        }
    )


# --- _squeeze ----------------------------------------------------------------

def test_squeeze_maps_into_open_interval():
    y = np.array([0.0, 0.1, 0.5, 0.9])
    n = len(y)
    out = _squeeze(y, n)
    assert np.all(out > 0) and np.all(out < 1)
    assert out[0] > 0  # the zero is pulled just inside the support
    assert out[-1] < 1  # the max is pulled just below 1


def test_squeeze_is_monotonic_and_vectorized():
    y = np.array([0.0, 0.2, 0.4, 0.8, 1.0])
    out = _squeeze(y)
    assert out.shape == y.shape
    assert np.all(np.diff(out) > 0)  # order-preserving


# --- _prep -------------------------------------------------------------------

def test_prep_keeps_only_complete_cases():
    out = _prep(_synthetic_features())
    assert len(out) == 5  # the NA-H⊥ defender (van Dijk) is dropped
    assert "Virgil van Dijk" not in set(out["player"])
    assert out["h_perp_pv"].notna().all()


def test_prep_squeezes_outcome_into_open_interval():
    out = _prep(_synthetic_features())
    assert (out["vote_share_sv"] > 0).all() and (out["vote_share_sv"] < 1).all()


def test_prep_standardizes_continuous_predictors():
    out = _prep(_synthetic_features())
    for col in _CONTINUOUS:
        assert abs(out[col].mean()) < 1e-9
        assert abs(out[col].std(ddof=0) - 1.0) < 1e-9


def test_prep_flags_duopoly_only():
    out = _prep(_synthetic_features())
    flagged = set(out.loc[out["is_duopoly"], "player"])
    assert flagged == {"Lionel Messi", "Cristiano Ronaldo"}


def test_prep_award_year_is_categorical_key():
    out = _prep(_synthetic_features())
    assert out["award_year"].map(type).eq(str).all()
