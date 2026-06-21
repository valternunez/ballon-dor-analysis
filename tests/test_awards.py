"""Offline unit tests for the Ballon d'Or awards parse (no network).

The live end-to-end scrape is verified separately; these cover the parsing logic against
hand-built tables modelled on the real (schema-varying) Wikipedia layouts.
"""

from __future__ import annotations

import pandas as pd
import pytest

from bdor.data.awards import (
    _clean_table,
    _normalise_name,
    _NotARankingTable,
    _select_mens_table,
)


def _mens_2018_like() -> pd.DataFrame:
    """4-col schema with a footnote, a multi-club cell, accents."""
    return pd.DataFrame(
        {
            "Rank": ["1", "2", "3"],
            "Player": ["Luka Modrić[6]", "Cristiano Ronaldo", "Antoine Griezmann"],
            "Club(s)": ["Real Madrid", "Real Madrid, Juventus", "Atlético Madrid"],
            "Points": ["753", "476", "414"],
        }
    )


def _mens_2024_like() -> pd.DataFrame:
    """6-col schema: adds Nationality + Position."""
    return pd.DataFrame(
        {
            "Rank": ["1", "2"],
            "Player": ["Rodri", "Vinícius Júnior"],
            "Nationality": ["Spain", "Brazil"],
            "Position": ["Midfielder", "Forward"],
            "Club": ["Manchester City", "Real Madrid"],
            "Points": ["1170", "1129"],
        }
    )


def _womens_like() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Rank": ["1", "2"],
            "Player": ["Ada Hegerberg", "Pernille Harder"],
            "Club(s)": ["Lyon", "Wolfsburg"],
            "Points": ["136", "82"],
        }
    )


def _not_a_ranking() -> pd.DataFrame:
    return pd.DataFrame({"Foo": [1, 2], "Bar": [3, 4]})


def test_normalise_name_folds_accents():
    assert _normalise_name("Luka Modrić") == "luka modric"
    assert _normalise_name("Ousmane Dembélé") == "ousmane dembele"


def test_clean_strips_footnote_preserves_multiclub_coerces_points():
    out = _clean_table(_mens_2018_like(), 2018)
    assert out.iloc[0]["player"] == "Luka Modrić"          # footnote removed
    assert out.iloc[0]["player_norm"] == "luka modric"
    assert out.iloc[1]["club"] == "Real Madrid, Juventus"  # multi-club preserved
    assert out["points"].tolist() == [753, 476, 414]
    assert out["award_year"].unique().tolist() == [2018]
    # 4-col schema -> optional columns absent -> all NA
    assert out["country"].isna().all()
    assert out["position"].isna().all()


def test_clean_picks_up_optional_columns_when_present():
    out = _clean_table(_mens_2024_like(), 2024)
    assert out.iloc[0]["country"] == "Spain"
    assert out.iloc[0]["position"] == "Midfielder"
    assert out.iloc[0]["club"] == "Manchester City"
    assert list(out.columns) == [
        "award_year", "rank", "player", "player_norm",
        "club", "country", "position", "points",
    ]


def test_clean_forward_fills_tied_rank():
    tied = pd.DataFrame(
        {
            "Rank": ["1", "2", None],   # tie shown once -> blank on the spanned row
            "Player": ["A", "B", "C"],
            "Points": ["10", "5", "5"],
        }
    )
    out = _clean_table(tied, 2099)
    assert out["rank"].tolist() == [1, 2, 2]


def test_clean_rejects_non_ranking_table():
    with pytest.raises(_NotARankingTable):
        _clean_table(_not_a_ranking(), 2018)


def test_select_picks_mens_and_ignores_women_and_junk():
    tables = [_not_a_ranking(), _womens_like(), _mens_2018_like()]
    out = _select_mens_table(tables, "Luka Modric", 2018)
    assert out.iloc[0]["player_norm"] == "luka modric"
    assert out.iloc[0]["points"] == 753


def test_select_raises_when_no_winner_match():
    with pytest.raises(ValueError, match="no men's ranking table"):
        _select_mens_table([_womens_like(), _not_a_ranking()], "Luka Modric", 2018)
