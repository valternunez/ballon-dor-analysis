"""Offline unit tests for the StatsBomb minutes/name helpers + tournament pool (no network)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from bdor.data.statsbomb import _minutes, _mmss, _player_name
from bdor.features.pool import _tournament_pool


def test_mmss_parses_cumulative_clock():
    assert _mmss("86:30") == 86.5
    assert _mmss("45:00") == 45.0
    assert _mmss(None) is None
    assert _mmss(np.nan) is None


def test_minutes_from_positions():
    # played the whole match (open final stint) -> ~95'
    assert _minutes([{"from": "00:00", "to": None}]) == 95.0
    # subbed off at 60'
    assert _minutes([{"from": "00:00", "to": "60:00"}]) == 60.0
    # came on at 70' and finished
    assert _minutes([{"from": "70:00", "to": None}]) == 25.0
    # two stints (tactical shift mid-match), still on at the whistle
    assert _minutes([{"from": "00:00", "to": "86:00"}, {"from": "86:00", "to": None}]) == 95.0
    assert _minutes([]) == 0.0
    assert _minutes(None) == 0.0


def test_player_name_prefers_nickname():
    assert _player_name("Messi", "Lionel Andrés Messi Cuccittini") == "Messi"
    assert _player_name(np.nan, "Virgil van Dijk") == "Virgil van Dijk"
    assert _player_name("", "Harry Kane") == "Harry Kane"


def test_tournament_pool_filters_by_minutes():
    sb = pd.DataFrame(
        {
            "player": ["Starter", "Sub", "Bench"],
            "award_year": [2022, 2022, 2022],
            "nation": ["Argentina", "Argentina", "Argentina"],
            "minutes": [665.0, 200.0, 30.0],
        }
    )
    out = _tournament_pool(sb, min_minutes=150)
    assert set(out["player"]) == {"Starter", "Sub"}  # Bench below the floor
    assert out["in_tournament"].all()
