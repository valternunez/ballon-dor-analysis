"""Club-importance features (merit v3) — how central a player was to his club.

The model knows a player's own production and his club's binary trophies, but not how *central* he
was. Rodri's City won the league — but so did every City squad player with enough minutes (the same
`won_league` flag for all). This module adds graded, per-player team-centrality:

  * `minutes_share` = 11 × player_minutes / team_total_minutes   (1.0 ≈ an ever-present outfielder)
  * `xg_share`      = player_xg / team_xg
  * `goals_share`   = player_goals / team_goals

Built entirely from the already-cached Understat season table, which carries **full league squads**
(≈20–42 players per team-season), so team totals are a groupby-sum — no new network pull. (The
v3 note's worry that the pull was candidate-only was outdated; see decisions-log.)

Season-level, mapped to each award year by `config.completed_season` — the leakage-safe season
the binary trophies already use. Wired in as a graded team-success CONTROL in the H⊥ de-fame model
(option (b) in the design note): it sharpens the team-context confound without touching the merit
index or the public leaderboard. Validated anchors: Rodri 23-24 minutes_share ≈ 0.82 but xg_share
≈ 0.05 (the pivot the box score misses); Messi 18-19 xg_share ≈ 0.29 / goals_share ≈ 0.39.
"""

from __future__ import annotations

import pandas as pd

from ..cache import cached_frame
from ..config import completed_season
from ..data import awards, understat
from .merit import _season_code

CACHE_NAME = "club_importance_features"
# Award spine (2020 cancelled, 2017 pre-xG). Each maps 1:1 to a completed season.
_SPINE = [2018, 2019, 2021, 2022, 2023, 2024, 2025]
_SHARE_COLS = ["minutes_share", "xg_share", "goals_share"]


def _team_shares(seasons: pd.DataFrame) -> pd.DataFrame:
    """Per (player, team, season) team-centrality shares. Pure / offline-testable.

    `minutes_share` divides by team_total_minutes/11 (11 outfield+keeper slots are on the pitch at
    all times, so the sum of every player's minutes ≈ games × 90 × 11) → 1.0 for an ever-present
    player. xG/goals shares divide by the team's summed player totals (0 where the team total is 0).
    """
    s = seasons.copy()
    for c in ("minutes", "goals", "xg"):
        s[c] = s[c].astype(float)
    tot = (
        s.groupby(["league", "season", "team"])
        .agg(team_minutes=("minutes", "sum"), team_xg=("xg", "sum"),
             team_goals=("goals", "sum"))
        .reset_index()
    )
    s = s.merge(tot, on=["league", "season", "team"], how="left")
    s["minutes_share"] = (
        (11.0 * s["minutes"] / s["team_minutes"]).where(s["team_minutes"] > 0, 0.0).clip(upper=1.0)
    )
    s["xg_share"] = (s["xg"] / s["team_xg"]).where(s["team_xg"] > 0, 0.0)
    s["goals_share"] = (s["goals"] / s["team_goals"]).where(s["team_goals"] > 0, 0.0)
    return s


def _primary_club_rows(shares: pd.DataFrame) -> pd.DataFrame:
    """One row per (player, season): the club where the player logged the most minutes.

    Mid-season transfers produce two club rows; we keep the player's primary club (most minutes), so
    a centrality share reflects the team he was actually central to. Edge case — most candidates are
    single-club in a season.
    """
    idx = shares.groupby(["player", "season"])["minutes"].idxmax()
    return shares.loc[idx]


def _build_club_importance() -> pd.DataFrame:
    shares = _primary_club_rows(_team_shares(understat.pull()))
    code_to_year = {_season_code(completed_season(y)): y for y in _SPINE}
    shares = shares[shares["season"].isin(code_to_year)].copy()
    shares["award_year"] = shares["season"].map(code_to_year).astype(int)
    shares["player_key"] = shares["player"].map(awards.name_key)
    return shares[["player", "player_key", "award_year", *_SHARE_COLS]].reset_index(drop=True)


def build(*, refresh: bool = False) -> pd.DataFrame:
    """Return per-(player, award_year) club-importance shares (cached)."""
    return cached_frame(CACHE_NAME, _build_club_importance, refresh=refresh)
