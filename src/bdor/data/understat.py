"""Understat player-season performance pull (the merit-index inputs).

FBref stopped serving its advanced (xG/Expected) stats publicly, so we source performance
from Understat instead — a different provider with its own xG model, delivered as plain JSON
via soccerdata.Understat (no Selenium, no anti-bot fragility).

``read_player_season_stats`` returns one clean tidy table, so this module is a thin wrapper:
fetch -> standardise a couple of names -> cache. Available metrics: goals, assists, xg, npxg,
xag (Understat xA), shots, key_passes, xg_chain, xg_buildup, minutes, position.

NOT available from Understat (vs the old FBref plan): progressive passes/carries, SCA,
defensive actions, PSxG. Consequence (see PROJECT_NOTES "Merit index — REVISED"): defender &
keeper strata have no individual production metric and enter the Tier-2 pool via the
team-success + tournament pools only. xg_chain / xg_buildup serve as a buildup-involvement
proxy for the dropped progression metrics.
"""

from __future__ import annotations

import pandas as pd
import soccerdata

from ..cache import cached_frame
from ..config import PERF_SEASONS, RAW_DIR, UNDERSTAT_LEAGUES

CACHE_NAME = "understat_player_seasons"
MATCH_CACHE_NAME = "understat_player_matches"

# Rename Understat's raw names to our merit vocabulary.
_RENAME = {"np_xg": "npxg", "xa": "xag"}

# Per-match merit inputs, from read_player_match_stats + shot events (npxg) + schedule (date).
# Same signals as the season VOLUME metrics, but date-stamped so they can be sliced to each award
# year's leakage-safe performance window (see features/merit.py + docs/windowing.md).
_MATCH_METRICS = ["npxg", "xag", "xg_chain", "xg_buildup", "goals", "assists"]
_MATCH_COLS = ["league", "season", "game", "date", "player", "player_id",
               "position", "team", "minutes", *_MATCH_METRICS]


def _standardize(df: pd.DataFrame) -> pd.DataFrame:
    """Rename to merit vocabulary and derive npxg+xag. Pure / offline-testable."""
    out = df.rename(columns=_RENAME).copy()
    if {"npxg", "xag"}.issubset(out.columns):
        out["npxg_xag"] = out["npxg"] + out["xag"]
    return out


def _pull_understat() -> pd.DataFrame:
    reader = soccerdata.Understat(
        leagues=UNDERSTAT_LEAGUES,
        seasons=PERF_SEASONS,
        data_dir=RAW_DIR / "understat",
    )
    df = reader.read_player_season_stats().reset_index()
    return _standardize(df)


def pull(*, refresh: bool = False) -> pd.DataFrame:
    """Return Understat top-5-league player-season stats (cached)."""
    return cached_frame(CACHE_NAME, _pull_understat, refresh=refresh)


# --- match-level pull (date-stamped merit inputs) ---------------------------

def _penalty_xg(shots: pd.DataFrame) -> pd.DataFrame:
    """Penalty xG per (league, season, game, player_id), summed from shot events. Pure.

    Understat tags a shot's `situation` as one of OpenPlay/FromCorner/SetPiece/DirectFreekick/
    Penalty; soccerdata maps the first four to readable labels and leaves **Penalty unmapped (NaN)**
    — so a NaN situation is exactly a penalty (cross-check: Understat assigns every penalty a
    constant xG ≈ 0.76). We subtract this from a player's match xG to get non-penalty xG (npxg),
    since the season `np_xg` field has no match-level equivalent.
    """
    pens = shots[shots["situation"].isna()]
    out = (
        pens.groupby(["league", "season", "game", "player_id"])["xg"]
        .sum()
        .reset_index()
        .rename(columns={"xg": "pen_xg"})
    )
    return out


def _assemble_matches(
    pm: pd.DataFrame, schedule: pd.DataFrame, shots: pd.DataFrame
) -> pd.DataFrame:
    """Join per-match player stats to match dates + derive npxg. Pure / offline-testable.

    `pm` = read_player_match_stats(), `schedule` = read_schedule(), `shots` = read_shot_events()
    (all `.reset_index()`-ed). Returns one row per (player, match) with `_MATCH_COLS`.
    """
    m = pm.merge(
        schedule[["league", "season", "game", "date"]],
        on=["league", "season", "game"], how="left",
    ).merge(
        _penalty_xg(shots), on=["league", "season", "game", "player_id"], how="left",
    )
    m["pen_xg"] = m["pen_xg"].astype(float).fillna(0.0)
    m["xg"] = m["xg"].astype(float)
    m["npxg"] = (m["xg"] - m["pen_xg"]).clip(lower=0.0)  # clip float noise on pen-only matches
    m["xag"] = m["xa"].astype(float)
    m["date"] = pd.to_datetime(m["date"])
    return m[_MATCH_COLS].reset_index(drop=True)


def _harden_read_match(reader: soccerdata.Understat) -> None:
    """Make `reader._read_match` skip (return None) on malformed matches instead of crashing.

    soccerdata only catches ConnectionError; a handful of Understat matches return an EMPTY roster
    (`rosters["h"]` is a `[]`, not a dict), so `_read_match` raises AttributeError mid-batch and
    kills the whole pull. Both callers (`read_player_match_stats` / `read_shot_events`) already
    `continue` when `_read_match` returns None, so widening the catch cleanly drops the bad matches.
    """
    original = reader._read_match

    def _safe(url: str, match_id: int):
        try:
            return original(url, match_id)
        except (AttributeError, KeyError, TypeError, ValueError, StopIteration):
            return None

    reader._read_match = _safe  # instance-level patch, scoped to this pull


def _pull_understat_matches() -> pd.DataFrame:
    reader = soccerdata.Understat(
        leagues=UNDERSTAT_LEAGUES,
        seasons=PERF_SEASONS,
        data_dir=RAW_DIR / "understat",
    )
    _harden_read_match(reader)
    pm = reader.read_player_match_stats().reset_index()
    schedule = reader.read_schedule(include_matches_without_data=True).reset_index()
    shots = reader.read_shot_events().reset_index()
    return _assemble_matches(pm, schedule, shots)


def pull_matches(*, refresh: bool = False) -> pd.DataFrame:
    """Return date-stamped per-match merit inputs (cached). Powers leakage-safe window slicing.

    Slow first run (per-match pages for ~8 seasons × 5 leagues); cache-first thereafter.
    """
    return cached_frame(MATCH_CACHE_NAME, _pull_understat_matches, refresh=refresh)
