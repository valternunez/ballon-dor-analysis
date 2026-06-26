"""Offline unit tests for the team-success join helpers (no network)."""

from __future__ import annotations

from bdor.features.team_success import (
    _club_cl_round,
    _norm_clubs,
    _season_codes,
    _tournament_overachievement,
    _tournament_result,
    _won_league,
)


def test_norm_clubs_splits_double_space_and_aliases():
    assert _norm_clubs("Real Madrid") == ["Real Madrid"]
    assert _norm_clubs("Real Madrid  Juventus") == ["Real Madrid", "Juventus"]
    assert _norm_clubs("Juventus  Milan") == ["Juventus", "AC Milan"]  # Milan -> AC Milan
    assert _norm_clubs(None) == []


def test_season_codes_calendar_year_uses_completed_season_only():
    # Leakage fix: a calendar award keeps only the season that finished before the ceremony
    # (2018 -> 2017-18, not 2018-19 which ends after the Dec ceremony). Season years are 1:1.
    assert _season_codes(2018) == ["1718"]
    assert _season_codes(2019) == ["1819"]
    assert _season_codes(2024) == ["2324"]


def test_club_cl_round_takes_max_across_clubs_and_seasons():
    cl = {("1718", "Real Madrid"): 5, ("1819", "Juventus"): 2}
    # Ronaldo 2018: Real Madrid (won, 5) + Juventus -> max 5
    assert _club_cl_round(["Real Madrid", "Juventus"], ["1718", "1819"], cl) == 5
    assert _club_cl_round(["Nowhere FC"], ["1718"], cl) == 0


def test_won_league_any():
    champs = {("2122", "AC Milan"), ("2122", "Manchester City")}
    assert _won_league(["AC Milan"], ["2122"], champs) is True
    assert _won_league(["Roma"], ["2122"], champs) is False


def test_tournament_result_lookup_and_default():
    tourn = {(2018, "France"): 5, (2018, "Croatia"): 4}
    assert _tournament_result("Croatia", 2018, tourn) == 4
    assert _tournament_result("Brazil", 2018, tourn) == 0     # didn't feature
    assert _tournament_result(None, 2018, tourn) == 0


def test_tournament_overachievement_lookup_and_default():
    # max(0, result - expected): Croatia 2018 overachieved (final from outside the contenders);
    # France (favourite that won) is on par -> 0; unknown / no-run -> 0.
    overach = {(2018, "Croatia"): 2, (2018, "France"): 0}
    assert _tournament_overachievement("Croatia", 2018, overach) == 2
    assert _tournament_overachievement("France", 2018, overach) == 0   # on par with expectation
    assert _tournament_overachievement("Brazil", 2018, overach) == 0   # no recorded run
    assert _tournament_overachievement(None, 2018, overach) == 0
