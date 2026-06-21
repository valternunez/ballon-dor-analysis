"""Offline unit tests for the fbref_defense pure helpers (no network).

The live three-source pull is validated by a scratch run (season coverage + Rodri spot-check);
these cover the season-code map and the pid-aware aggregation that avoids the namesake trap.
"""

from __future__ import annotations

import pandas as pd

from bdor.data.fbref_defense import METRICS, _aggregate, _season_from_end


def test_season_from_end_maps_to_understat_code():
    assert _season_from_end(2018) == "1718"
    assert _season_from_end(2023) == "2223"
    assert _season_from_end(2021) == "2021"  # the 2020-2021 season


def _synthetic_rows() -> pd.DataFrame:
    """One mid-season mover (single pid, two clubs) + two different players named 'Rodri'."""
    return pd.DataFrame(
        {
            "pid": ["url_a", "url_a", "url_b", "url_c"],
            "season": ["1718"] * 4,
            "player": ["Mover", "Mover", "Rodri", "Rodri"],
            "nationality": ["ESP"] * 4,
            "position": ["MF"] * 4,
            "squad": ["ClubA1", "ClubA2", "BigClub", "SmallClub"],
            "league": ["Premier League"] * 4,
            "nineties": [10.0, 5.0, 20.0, 3.0],
            "tackles_won": [10.0, 5.0, 30.0, 3.0],
            "interceptions": [2.0, 1.0, 6.0, 1.0],
            "blocks": [4.0, 2.0, 8.0, 1.0],
            "clearances": [6.0, 3.0, 12.0, 2.0],
            "prog_passes": [20.0, 10.0, 60.0, 5.0],
            "tackle_pct": [50.0, 50.0, 70.0, 40.0],
            "aerial_win_pct": [55.0, 55.0, 65.0, 45.0],
            "psxg_net": [pd.NA, pd.NA, pd.NA, pd.NA],
            "save_pct": [pd.NA, pd.NA, pd.NA, pd.NA],
        }
    )


def test_aggregate_sums_mover_but_not_namesakes():
    out = _aggregate(_synthetic_rows())
    # One row per player-name: the mover (combined), and ONE 'Rodri' (the prominent namesake).
    assert len(out) == 2
    mover = out[out["player"] == "Mover"].iloc[0]
    assert mover["nineties"] == 15.0  # 10 + 5 stints summed (same pid)
    assert mover["tackles_won"] == 15.0

    rodri = out[out["player"] == "Rodri"].iloc[0]
    assert rodri["nineties"] == 20.0  # NOT 23 — the two Rodris were not merged
    assert rodri["squad"] == "BigClub"  # the heavier-minutes namesake wins
    assert rodri["tackles_won"] == 30.0


def test_aggregate_preserves_metric_schema():
    out = _aggregate(_synthetic_rows())
    for m in METRICS:
        assert m in out.columns
