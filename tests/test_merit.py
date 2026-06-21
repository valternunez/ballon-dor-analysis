"""Offline unit tests for the merit-index pure helpers (no network)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from bdor.features.merit import (
    _attacking_merit,
    _cb_validity_report,
    _combine_best_role,
    _family_by_award_year,
    _position_family,
    _primary_pos,
    _season_code,
    _wavg,
    _window_sum,
    _zscore_within_group,
)


def test_position_family_priority():
    assert _position_family("GK") == "keeper"
    assert _position_family("F S") == "attack"
    assert _position_family("F M S") == "attack"
    assert _position_family("D M S") == "attack"     # any M -> attack (wingers coded M)
    assert _position_family("D S") == "defense"      # pure defender
    assert _position_family("S") == "unknown"


def test_season_code():
    assert _season_code("2017-2018") == "1718"
    assert _season_code("2020-2021") == "2021"
    assert _season_code("2024-2025") == "2425"


def test_zscore_within_group():
    df = pd.DataFrame(
        {
            "g": ["a", "a", "a", "b"],
            "x": [1.0, 2.0, 3.0, 5.0],
        }
    )
    out = _zscore_within_group(df, ["g"], ["x"])
    a = out[out.g == "a"]["x_z"]
    assert abs(a.mean()) < 1e-9          # mean ~0 within group
    assert abs(a.std(ddof=1) - 1.0) < 1e-9
    # single-row group -> zero-variance -> 0
    assert out[out.g == "b"]["x_z"].iloc[0] == 0.0


def test_wavg_minutes_weighted_and_na():
    vals = pd.Series([2.0, 4.0])
    w = pd.Series([1.0, 3.0])
    assert _wavg(vals, w) == (2 * 1 + 4 * 3) / 4  # = 3.5
    assert np.isnan(_wavg(pd.Series([np.nan, np.nan]), pd.Series([1.0, 1.0])))


def _windows_2019() -> pd.DataFrame:
    """A one-row windows table for the 2019 (calendar) award: Jan–Dec 2019 performance window."""
    return pd.DataFrame(
        {"perf_start": pd.to_datetime(["2019-01-01"]),
         "perf_end": pd.to_datetime(["2019-12-31"])},
        index=pd.Index([2019], name="award_year"),
    )


def test_window_sum_excludes_pre_window_and_lookahead_matches():
    # The leakage fix: for the Dec-2019 award only Jan–Dec 2019 matches count. A late-2018 match
    # (before the window) and a 2020 match (AFTER the ceremony — the De Bruyne leak) must drop out.
    zero = [0.0, 0.0, 0.0]
    matches = pd.DataFrame(
        {
            "player": ["P", "P", "P"],
            "date": pd.to_datetime(["2019-03-01", "2018-10-01", "2020-03-01"]),
            "npxg": [1.0, 5.0, 9.0],
            "xag": zero, "xg_chain": zero, "xg_buildup": zero, "goals": zero, "assists": zero,
            "minutes": [90.0, 90.0, 90.0],
        }
    )
    out = _window_sum(matches, _windows_2019())
    row = out[out.award_year == 2019].iloc[0]
    assert row["npxg"] == 1.0      # only the in-window match survives
    assert row["minutes"] == 90.0


def test_family_by_award_year_dominant_minutes():
    season_df = pd.DataFrame(
        {"player": ["A", "A"], "season": ["1819", "1920"],
         "position": ["F S", "F S"], "minutes": [1000, 2000]}
    )
    out = _family_by_award_year(season_df)
    fam = out[(out.player == "A") & (out.award_year == 2019)]["position_family"].iloc[0]
    assert fam == "attack"


def test_attacking_merit_window_zscore_and_na_for_defenders():
    # Two attackers + one defender qualify on window minutes; defender gets NA attacking merit.
    metrics = {"xag": 0.0, "xg_chain": 0.0, "xg_buildup": 0.0, "goals": 0.0, "assists": 0.0}
    window = pd.DataFrame(
        [
            {"player": "Att1", "award_year": 2019, "npxg": 10.0, "minutes": 3000, **metrics},
            {"player": "Att2", "award_year": 2019, "npxg": 2.0, "minutes": 3000, **metrics},
            {"player": "Def", "award_year": 2019, "npxg": 1.0, "minutes": 3000, **metrics},
        ]
    )
    family = pd.DataFrame(
        {"player": ["Att1", "Att2", "Def"], "award_year": [2019, 2019, 2019],
         "position_family": ["attack", "attack", "defense"]}
    )
    out = _attacking_merit(window, family).set_index("player")
    assert "Def" not in out.index                      # defenders excluded from attacking merit
    assert out.loc["Att1", "merit_z"] > out.loc["Att2", "merit_z"]  # higher npxg -> higher merit


# --- defensive merit + best-role combine ------------------------------------

def test_primary_pos_first_token():
    assert _primary_pos("MF,DF") == "MF"
    assert _primary_pos("DF") == "DF"
    assert _primary_pos("GK") == "GK"
    assert _primary_pos("WB") == "other"  # unrecognised -> other


def _four_dim_frames():
    attacking = pd.DataFrame(
        {
            "player": ["Att", "Mid"],
            "award_year": [2021, 2021],
            "position_family": ["attack", "attack"],
            "merit_z": [2.0, -0.1],          # Mid is a low-output destroyer on ATTACKING merit
            "merit_pc1": [1.5, -0.2],
            "merit_pc2": [0.1, 0.0],
            "minutes": [2500, 2600],
        }
    )
    mf_def = pd.DataFrame(
        {
            "player_def": ["Mid", "DefMid"], "award_year": [2021, 2021],
            "def_position": ["MF", "MF"], "def_merit_z": [0.8, 1.2], "def_minutes": [2700, 2400],
        }
    )
    cb = pd.DataFrame(
        {"player": ["CB"], "award_year": [2021], "cb_def_z": [1.5], "cb_def_z_minutes": [3000]}
    )
    gk = pd.DataFrame(
        {"player": ["GK"], "award_year": [2021], "gk_merit_z": [0.9], "gk_merit_z_minutes": [3200]}
    )
    return attacking, mf_def, cb, gk


def test_combine_best_role_four_dims():
    out = _combine_best_role(*_four_dim_frames()).set_index("player")
    assert out.loc["Att", "merit_z"] == 2.0                 # pure attacker keeps attacking
    assert out.loc["Mid", "merit_z"] == 0.8                 # destroyer: best-role picks defense
    assert out.loc["Mid", "att_merit_z"] == -0.1
    assert out.loc["DefMid", "merit_z"] == 1.2              # MF-only
    assert out.loc["DefMid", "position_family"] == "attack"
    assert out.loc["CB", "merit_z"] == 1.5                  # CB-only
    assert out.loc["CB", "position_family"] == "defense"
    assert out.loc["GK", "merit_z"] == 0.9                  # keeper-only
    assert out.loc["GK", "position_family"] == "keeper"
    assert out.loc["GK", "minutes"] == 3200


def test_combine_best_role_cb_disabled_keeps_column_drops_from_merit():
    att, mf_def, cb, gk = _four_dim_frames()
    out = _combine_best_role(att, mf_def, cb, gk, include_cb=False).set_index("player")
    assert out.loc["CB", "cb_def_z"] == 1.5                 # column still present
    assert pd.isna(out.loc["CB", "merit_z"])               # but not in the best-role max


def _cb_distribution(vvd_z, dias_z):
    """5-CB-per-year synthetic; the anchors take `vvd_z` / `dias_z`, the rest are spread below."""
    rows = []
    for yr, anchor, az in [(2019, "Virgil van Dijk", vvd_z), (2021, "Ruben Dias", dias_z)]:
        rows += [{"player": f"filler{yr}{i}", "award_year": yr, "cb_def_z": z}
                 for i, z in enumerate([-1.0, -0.5, 0.0, 0.5])]
        rows.append({"player": anchor, "award_year": yr, "cb_def_z": az})
    return pd.DataFrame(rows)


def test_cb_validity_report_passes_when_elites_rank_top():
    anchors = pd.DataFrame(
        {"player": ["Virgil van Dijk", "Ruben Dias"], "award_year": [2019, 2021]}
    )
    rep = _cb_validity_report(_cb_distribution(2.0, 2.0), anchors)  # both anchors top of their year
    assert rep["vvd_2019"] == 1.0 and rep["dias_2021"] == 1.0
    assert rep["pass"] is True


def test_cb_validity_report_fails_when_an_elite_ranks_low():
    anchors = pd.DataFrame(
        {"player": ["Virgil van Dijk", "Ruben Dias"], "award_year": [2019, 2021]}
    )
    rep = _cb_validity_report(_cb_distribution(2.0, -2.0), anchors)  # Dias at the bottom
    assert rep["dias_2021"] < 0.6
    assert rep["pass"] is False
