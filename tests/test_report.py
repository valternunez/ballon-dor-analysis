"""Offline unit tests for the report data helpers (no figures, no rendering)."""

from __future__ import annotations

import pandas as pd

from bdor.report import (
    _hperp_row,
    _per_year_scoreboard,
    _prior_extent,
    _site_payload,
    case_studies,
    leaderboard,
)


def _synthetic_features() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "award_year": [2018, 2019, 2023, 2024, 2019],
            "player": [
                "Luka Modrić", "Robert Lewandowski", "Lionel Messi", "Lamine Yamal", "Defender",
            ],
            "rank": [1, 14, 1, 8, 30],
            "vote_share": [0.30, 0.005, 0.31, 0.06, 0.0],
            "h_perp_pv": [1.46, -0.77, 1.25, 3.82, None],  # defender = NA H⊥
            "merit_pc1": [2.0, 10.5, 9.9, 2.4, None],
        }
    )


def test_leaderboard_splits_top_and_bottom_by_hperp():
    lb = leaderboard(n=2, df=_synthetic_features())
    assert len(lb) == 4  # top 2 + bottom 2
    top = lb[lb["kind"] == "narrative excess"]
    bottom = lb[lb["kind"] == "under the radar"]
    assert list(top["player"]) == ["Lamine Yamal", "Luka Modrić"]  # highest H⊥ first
    assert bottom.iloc[0]["player"] == "Robert Lewandowski"  # lowest H⊥
    assert "Defender" not in set(lb["player"])  # NA-H⊥ excluded


def test_case_studies_pulls_named_players_with_hperp():
    cs = case_studies(df=_synthetic_features())
    assert {"Player", "Year", "h_perp_pv"} <= set(c for c in cs.columns) | {"Player", "Year"}
    players = set(cs["player"])
    assert "Luka Modrić" in players and "Robert Lewandowski" in players
    assert (cs["award_year"].isin([2018, 2019, 2022, 2023])).all()


def test_prior_extent_summarizes_default_and_range_per_gate():
    t = pd.DataFrame({
        "gate": ["A_nomination"] * 3 + ["B_placement"] * 3,
        "prior": ["default", "tight", "wide"] * 2,
        "estimate": [0.70, 0.66, 0.72, 0.145, 0.12, 0.151],
    })
    out = _prior_extent(t)
    assert out["a"]["default"] == 0.70
    assert out["a"]["min"] == 0.66 and out["a"]["max"] == 0.72  # range brackets the default
    assert out["b"]["default"] == 0.145
    assert out["b"]["min"] == 0.12 and out["b"]["max"] == 0.151


def test_hperp_row_extracts_posterior_summary():
    table = pd.DataFrame(
        {"mean": [0.72], "hdi94_lb": [0.50], "hdi94_ub": [0.95], "p_positive": [1.0]},
        index=["h_perp_pv"],
    )
    out = _hperp_row(table)
    assert out == {"mean": 0.72, "lo": 0.50, "hi": 0.95, "p_pos": 1.0}


def test_site_payload_has_expected_keys_and_record_shapes():
    stats = {"gate_a": {"mean": 0.72}, "gate_b": {"mean": 0.19}}
    df = _synthetic_features()[df_cols()]
    payload = _site_payload(
        stats=stats, lb=df, cases=df, panel=df, scatter=df,
        defame=[{"player": "X", "year": 2024, "actual": 10, "expected": 1, "h_perp": 3.0}],
        spike={"player": "X", "year": 2024, "dates": [], "views": [], "markers": {}},
        per_year=[{"year": 2024, "winner": {}, "best_season": {}, "most_hyped": {},
                   "diverge": True}],
        effects={"gate_a_or": {"or": 2.0}},
        robust_extra={"bootstrap_a": {"est": 0.7}},
    )
    assert set(payload) == {"headline", "effects", "robust_extra", "leaderboard", "cases",
                            "robustness", "scatter", "defame", "spike", "per_year"}
    assert payload["headline"]["gateA"]["mean"] == 0.72
    assert isinstance(payload["leaderboard"], list) and isinstance(payload["leaderboard"][0], dict)


def df_cols():
    return ["player", "award_year", "h_perp_pv"]


def _per_year_synthetic() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "award_year": [2024, 2024, 2024],
            "player": ["Winner", "BestSeason", "MostHyped"],
            "rank": [1, 10, 8],
            "vote_share": [0.30, 0.05, 0.07],
            "merit_z": [1.4, 3.1, 0.5],
            "h_perp_pv": [0.6, 0.2, 3.7],
        }
    )


def test_per_year_scoreboard_picks_three_faces_and_ranks():
    yr = _per_year_scoreboard(_per_year_synthetic())[0]
    assert yr["year"] == 2024
    assert yr["winner"]["player"] == "Winner"          # rank == 1
    assert yr["best_season"]["player"] == "BestSeason"  # max merit_z
    assert yr["most_hyped"]["player"] == "MostHyped"    # max h_perp
    assert yr["diverge"] is True
    # winner is 2nd on merit (3.1 > 1.4 > 0.5) and 2nd on hype (3.7 > 0.6 > 0.2)
    assert yr["winner"]["merit_rank"] == 2 and yr["winner"]["hype_rank"] == 2


def test_per_year_scoreboard_flags_no_divergence():
    df = pd.DataFrame(
        {
            "award_year": [2019, 2019], "player": ["Messi", "Other"], "rank": [1, 2],
            "vote_share": [0.4, 0.1], "merit_z": [4.0, 0.5], "h_perp_pv": [2.0, 0.1],
        }
    )
    yr = _per_year_scoreboard(df)[0]
    assert yr["winner"]["player"] == "Messi"            # top on merit, hype, and the vote
    assert yr["best_season"]["player"] == "Messi"
    assert yr["most_hyped"]["player"] == "Messi"
    assert yr["diverge"] is False
