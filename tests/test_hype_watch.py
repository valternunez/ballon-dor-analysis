"""Offline unit tests for the 2026 Hype-Watch helpers (no network).

The Hype-Watch is a forward-looking teaser, fully isolated from the modelled study; these cover its
pure de-fame + attacking-merit logic on synthetic data.
"""

from __future__ import annotations

import pandas as pd

from bdor.features.hype_watch import _attacking_merit, _defame


def test_defame_flags_attention_beyond_fame_and_merit():
    # A clean field where attention tracks fame (window ~ 1.25*baseline), plus one "Hyped" player
    # whose inputs sit in the MIDDLE of the field (low leverage) but whose attention is ~8x what the
    # model predicts -> it carries the largest positive residual (hype the numbers don't explain).
    base = [60, 80, 100, 120, 140, 160, 90, 110, 130, 70]
    rows = [
        {"player": f"P{i}", "baseline": float(b), "window_mean": round(b * 1.25),
         "att_merit_z": (b - 100) / 50.0, "team_strength_z": (b - 100) / 80.0}
        for i, b in enumerate(base)
    ]
    rows.append({"player": "Hyped", "baseline": 100.0, "window_mean": 1000.0,
                 "att_merit_z": 0.0, "team_strength_z": 0.0})  # central inputs, anomalous attention
    out = _defame(pd.DataFrame(rows))
    assert "h_perp_2026" in out.columns
    assert out["h_perp_2026"].notna().all()
    assert out.loc[out["player"] == "Hyped", "h_perp_2026"].iloc[0] == out["h_perp_2026"].max()


def test_attacking_merit_rewards_more_production_and_filters_low_minutes():
    season = pd.DataFrame({
        "player": ["Striker", "Mid", "Bench"],
        "team": ["X", "Y", "Z"],
        "position": ["F", "M", "F"],
        "minutes": [2700.0, 2400.0, 300.0],          # Bench below MIN_MINUTES -> dropped
        "npxg": [20.0, 5.0, 4.0],
        "xag": [8.0, 6.0, 1.0],
        "xg_chain": [25.0, 18.0, 3.0],
        "xg_buildup": [10.0, 12.0, 2.0],
        "goals": [22.0, 4.0, 3.0],
        "assists": [7.0, 6.0, 0.0],
    })
    out = _attacking_merit(season)
    assert set(out["player"]) == {"Striker", "Mid"}        # low-minutes bench filtered out
    striker = out.loc[out["player"] == "Striker", "att_merit_z"].iloc[0]
    mid = out.loc[out["player"] == "Mid", "att_merit_z"].iloc[0]
    assert striker > mid                                    # more production -> higher merit
