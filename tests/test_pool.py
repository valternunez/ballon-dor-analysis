"""Offline unit tests for the Tier-2 pool helpers (no network).

The pure helpers are exercised on synthetic merit / Understat fixtures; the live pull-backed
`build()` is validated by a scratch run (size/recall diagnostics), not here.
"""

from __future__ import annotations

import pandas as pd

from bdor.features.pool import (
    _production_pool,
    _season_to_award_years,
    _team_success_pool,
    _union_sources,
    _us_award_year,
)


def test_season_to_award_years_maps_calendar_years_to_two():
    m = _season_to_award_years()
    # 2018 (calendar regime) draws on seasons 1718 and 1819.
    assert 2018 in m["1718"]
    assert 2018 in m["1819"]
    # 2023 (season regime) draws on a single season 2223.
    assert m["2223"] == [2023]


def test_production_pool_takes_top_n_attackers_per_year():
    mer = pd.DataFrame(
        {
            "player": [f"p{i}" for i in range(5)] + ["d0"],
            "award_year": [2018] * 6,
            # ranks on ATTACKING merit; d0 (NA att_merit_z, e.g. a defensive-only mid) is excluded
            # so a bad-team destroyer's defensive-volume score can't pull it into production.
            "att_merit_z": [3.0, 2.0, 1.0, 0.5, 0.1, None],
        }
    )
    out = _production_pool(mer, top_n=3)
    assert list(out["player"]) == ["p0", "p1", "p2"]  # top 3 by att_merit_z, NA dropped
    assert out["in_production"].all()


def test_team_success_pool_filters_by_qualifying_club_and_minutes():
    us = pd.DataFrame(
        {
            "player": ["star", "sub", "outsider", "inter_guy"],
            "season": ["2223", "2223", "2223", "2223"],
            "team": ["Manchester City", "Manchester City", "Random FC", "Inter"],
            "minutes": [2000, 400, 3000, 1500],
        }
    )
    # Man City + Inter (via _US_ALIASES -> "Inter Milan") qualify; Random FC does not.
    qualifying = {("2223", "Manchester City"), ("2223", "Inter Milan")}
    out = _team_success_pool(us, qualifying, min_minutes=900)
    players = set(out["player"])
    assert players == {"star", "inter_guy"}  # 'sub' below floor, 'outsider' not qualifying
    assert out["in_team_success"].all()
    assert (out["award_year"] == 2023).all()


def test_union_sources_fills_flags_and_dedupes():
    prod = pd.DataFrame({"player": ["a", "b"], "award_year": [2018, 2018], "in_production": True})
    ts = pd.DataFrame({"player": ["b", "c"], "award_year": [2018, 2018], "in_team_success": True})
    u = _union_sources(prod, ts)
    assert len(u) == 3  # a, b, c
    row_b = u[u["player"] == "b"].iloc[0]
    assert bool(row_b["in_production"]) and bool(row_b["in_team_success"])
    row_a = u[u["player"] == "a"].iloc[0]
    assert bool(row_a["in_production"]) and not bool(row_a["in_team_success"])


def test_us_award_year_aggregates_minutes_family_and_clubs():
    us = pd.DataFrame(
        {
            "player": ["x", "x"],
            "season": ["1718", "1819"],  # both feed award_year 2018
            "team": ["Inter", "Tottenham"],  # aliased -> Inter Milan, Tottenham Hotspur
            "position": ["F S", "F M S"],
            "minutes": [1000, 2000],
        }
    )
    out = _us_award_year(us)
    row = out[(out["player"] == "x") & (out["award_year"] == 2018)].iloc[0]
    assert row["us_minutes"] == 3000
    assert row["us_family"] == "attack"
    assert row["clubs"] == {"Inter Milan", "Tottenham Hotspur"}
