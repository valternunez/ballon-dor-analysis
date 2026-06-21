"""Offline unit tests for the Stage-A nomination prep (no network, no MCMC)."""

from __future__ import annotations

import pandas as pd

from bdor.models.nomination import _CONTINUOUS, _CONTINUOUS_HPERP, _prep, _prep_hperp


def _synthetic_pool() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "player": ["a", "b", "c", "d"],
            "award_year": [2018, 2018, 2019, 2019],
            "position_family": ["attack", "attack", "defense", "keeper"],
            "merit_z": [2.0, -1.0, None, None],  # non-attackers carry NA merit
            "cl_round": [5, 0, 4, 3],
            "won_cl": [True, False, False, False],
            "won_league": [True, False, True, False],
            "tournament_result": [5, 0, 3, 0],
            "nominated": [True, False, True, False],
        }
    )


def test_prep_imputes_missing_merit_to_zero():
    out = _prep(_synthetic_pool())
    assert out["merit_z"].notna().all()  # no NaN survives the fit
    # the two non-attackers had NA merit -> filled to 0 before standardization (so post-scaling
    # they share the same value); they should be equal to each other.
    nonatt = out[out["position_family"].isin(["defense", "keeper"])]["merit_z"]
    assert nonatt.nunique() == 1


def test_prep_standardizes_continuous_predictors():
    out = _prep(_synthetic_pool())
    for col in _CONTINUOUS:
        assert abs(out[col].mean()) < 1e-9
        assert abs(out[col].std(ddof=0) - 1.0) < 1e-9


def test_prep_coerces_types_and_keeps_tournament_result():
    out = _prep(_synthetic_pool())
    assert set(out["nominated"].unique()) <= {0, 1}
    assert set(out["won_cl"].unique()) <= {0, 1}
    # tournament_result is back in (StatsBomb nation extension dissolved the leakage), standardized
    assert "tournament_result" in out.columns
    assert abs(out["tournament_result"].mean()) < 1e-9
    assert out["award_year"].map(type).eq(str).all()  # group key is categorical


def test_prep_hperp_is_attacker_only_and_standardized():
    pool = _synthetic_pool()  # a=attack, b=attack, c=defense, d=keeper
    hperp_df = pd.DataFrame(
        {
            "player_key": ["a", "b", "c", "d"],
            "award_year": [2018, 2018, 2019, 2019],
            "h_perp_pv": [0.8, -0.4, None, None],  # only attackers have H⊥
            "pv_low_baseline": [False, False, False, False],
        }
    )
    # _prep_hperp joins on awards.name_key(player); synthetic single-token names are their own key.
    out = _prep_hperp(pool, hperp_df=hperp_df)
    assert set(out["player"]) == {"a", "b"}  # non-attackers (NA H⊥) dropped
    for col in _CONTINUOUS_HPERP:
        assert abs(out[col].mean()) < 1e-9
        assert abs(out[col].std(ddof=0) - 1.0) < 1e-9
