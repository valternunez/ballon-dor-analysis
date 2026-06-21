"""Offline unit tests for config helpers (no network)."""

from __future__ import annotations

from bdor.config import completed_season


def test_completed_season_calendar_drops_lookahead():
    # Calendar award years span two seasons; keep only the one that ENDS in the award year
    # (finished before the ceremony), not the look-ahead second season.
    assert completed_season(2018) == "2017-2018"
    assert completed_season(2019) == "2018-2019"
    assert completed_season(2021) == "2020-2021"


def test_completed_season_season_regime_unchanged():
    assert completed_season(2022) == "2021-2022"
    assert completed_season(2024) == "2023-2024"
    assert completed_season(2025) == "2024-2025"
