"""Offline unit tests for the Understat standardisation (no network)."""

from __future__ import annotations

import pandas as pd

from bdor.data.understat import _assemble_matches, _penalty_xg, _standardize


def _raw_like() -> pd.DataFrame:
    """A couple of rows shaped like soccerdata.Understat.read_player_season_stats output."""
    return pd.DataFrame(
        {
            "league": ["ENG-Premier League", "ESP-La Liga"],
            "season": ["2324", "2324"],
            "team": ["Manchester City", "Real Madrid"],
            "player": ["Erling Haaland", "Jude Bellingham"],
            "player_id": [8260, 7752],
            "position": ["F S", "M S"],
            "goals": [27, 19],
            "np_xg": [24.5, 12.1],
            "xa": [5.2, 6.4],
            "xg_chain": [30.1, 28.0],
            "xg_buildup": [8.0, 15.5],
        }
    )


def test_standardize_renames_to_merit_vocabulary():
    out = _standardize(_raw_like())
    assert "npxg" in out.columns and "np_xg" not in out.columns
    assert "xag" in out.columns and "xa" not in out.columns


def test_standardize_derives_npxg_plus_xag():
    out = _standardize(_raw_like())
    assert "npxg_xag" in out.columns
    assert out["npxg_xag"].tolist() == [24.5 + 5.2, 12.1 + 6.4]


def test_standardize_is_non_mutating():
    raw = _raw_like()
    _standardize(raw)
    assert "np_xg" in raw.columns  # original untouched


# --- match-level assembly (date-stamped merit inputs) -----------------------

def _shots_like() -> pd.DataFrame:
    """Shot events: player X has a penalty (situation NaN), player Y an open-play shot."""
    return pd.DataFrame(
        {
            "league": ["ENG-Premier League"] * 3,
            "season": ["1819"] * 3,
            "game": ["g1", "g1", "g1"],
            "player": ["X", "X", "Y"],
            "player_id": [1, 1, 2],
            "xg": [0.10, 0.76, 0.20],
            "situation": ["Open Play", pd.NA, "Open Play"],  # NaN == penalty (only unmapped value)
        }
    )


def _pm_like() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "league": ["ENG-Premier League"], "season": ["1819"], "game": ["g1"],
            "team": ["A"], "player": ["X"], "player_id": [1], "position": ["FW"],
            "minutes": [90], "goals": [1], "assists": [0],
            "xg": [0.86], "xa": [0.30], "xg_chain": [1.2], "xg_buildup": [0.4],
        }
    )


def _schedule_like() -> pd.DataFrame:
    return pd.DataFrame(
        {"league": ["ENG-Premier League"], "season": ["1819"], "game": ["g1"],
         "date": pd.to_datetime(["2019-03-01"])}
    )


def test_penalty_xg_sums_only_unmapped_situation():
    out = _penalty_xg(_shots_like()).set_index("player_id")
    assert out.loc[1, "pen_xg"] == 0.76      # X's penalty
    assert 2 not in out.index                # Y took no penalty


def test_assemble_matches_derives_npxg_and_joins_date():
    out = _assemble_matches(_pm_like(), _schedule_like(), _shots_like())
    r = out.iloc[0]
    assert abs(r["npxg"] - (0.86 - 0.76)) < 1e-9   # match xg minus penalty xg
    assert r["xag"] == 0.30                          # xa -> xag
    assert r["date"] == pd.Timestamp("2019-03-01")
