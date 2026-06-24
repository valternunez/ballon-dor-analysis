"""Offline unit tests for the club-importance (v3) share helpers (no network)."""

from __future__ import annotations

import pandas as pd

from bdor.features.club_importance import _primary_club_rows, _team_shares


def _seasons() -> pd.DataFrame:
    # One team (Alpha, 1819) with three players; one player split across two clubs.
    return pd.DataFrame(
        {
            "league": ["L"] * 4,
            "season": ["1819"] * 4,
            "team": ["Alpha", "Alpha", "Alpha", "Beta"],
            "player": ["Star", "Mid", "Sub", "Star"],
            "minutes": [3000.0, 3000.0, 600.0, 200.0],
            "goals": [20.0, 5.0, 1.0, 0.0],
            "xg": [18.0, 4.0, 1.0, 0.0],
        }
    )


def test_team_shares_sum_and_bounds():
    out = _team_shares(_seasons())
    alpha = out[out["team"] == "Alpha"]
    # xg/goals shares within a team sum to 1 (team total = sum of its players).
    assert abs(alpha["xg_share"].sum() - 1.0) < 1e-9
    assert abs(alpha["goals_share"].sum() - 1.0) < 1e-9
    # Star carries the attack.
    star = alpha[alpha["player"] == "Star"].iloc[0]
    assert star["xg_share"] > 0.7
    # minutes_share is in [0, 1]; team_minutes = 6600, 11*3000/6600 = 5.0 -> clipped to 1.0.
    assert (out["minutes_share"] >= 0).all() and (out["minutes_share"] <= 1.0).all()
    assert star["minutes_share"] == 1.0


def test_team_shares_zero_when_team_total_zero():
    df = pd.DataFrame(
        {"league": ["L"], "season": ["1819"], "team": ["Z"], "player": ["P"],
         "minutes": [0.0], "goals": [0.0], "xg": [0.0]}
    )
    out = _team_shares(df)
    assert out["xg_share"].iloc[0] == 0.0
    assert out["goals_share"].iloc[0] == 0.0
    assert out["minutes_share"].iloc[0] == 0.0


def test_primary_club_rows_keeps_max_minutes_club():
    out = _primary_club_rows(_team_shares(_seasons()))
    star = out[out["player"] == "Star"]
    assert len(star) == 1  # one row per (player, season)
    assert star.iloc[0]["team"] == "Alpha"  # 3000 min at Alpha > 200 at Beta
