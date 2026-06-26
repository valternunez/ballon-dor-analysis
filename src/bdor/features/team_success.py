"""Team-success / tournament block — the confound hub for the H⊥ regression.

Per (player, award_year): the player's club achievements (deepest Champions League round,
domestic league title) and their national team's major-tournament result. Joins curated
reference CSVs (data/reference/, Wikipedia-grounded) to the awards finishers via club + nation.

Why team-success matters (PROJECT_NOTES "H⊥ — LOCKED"): it's residualized out of hype so that
winning-the-CL attention doesn't masquerade as pure narrative; it's also the pool-entry route for
defenders/keepers (who have no individual merit metric from Understat).

Grain = the awards finisher rows (club comes straight from `awards.club`, tied to the award year);
spine award years only (2017 is the degraded panel, absent from AWARD_YEAR_SEASONS).
"""

from __future__ import annotations

import re

import pandas as pd

from ..cache import cached_frame
from ..config import AWARD_YEAR_SEASONS, REFERENCE_DIR, completed_season
from ..data import awards, understat
from .merit import _season_code

CACHE_NAME = "team_success"
_CLUB_ALIASES = {"Milan": "AC Milan"}  # awards uses both "Milan" and "AC Milan"
# Understat club spellings -> the reference-CSV spelling (only clubs that appear in the references).
_US_ALIASES = {
    "Inter": "Inter Milan",
    "Paris Saint Germain": "Paris Saint-Germain",
    "Tottenham": "Tottenham Hotspur",
    "RasenBallsport Leipzig": "RB Leipzig",
    "Atletico Madrid": "Atlético Madrid",
}


# --- pure helpers (offline-testable) ----------------------------------------

def _norm_clubs(club_str: str) -> list[str]:
    """awards.club -> list of clubs (multi-club entries are double-space separated)."""
    if not isinstance(club_str, str):
        return []
    parts = [p.strip() for p in re.split(r"\s{2,}", club_str) if p.strip()]
    return [_CLUB_ALIASES.get(p, p) for p in parts]


def _season_codes(award_year: int) -> list[str]:
    """Leakage-safe season code(s) for an award year's CLUB features (cl_round / won_league).

    Calendar-regime award years span two seasons; the second finishes the summer AFTER the
    ceremony, so crediting its CL run / title is look-ahead. We keep only the completed season
    (config.completed_season) — its trophies were decided inside the window. Season-regime years
    are 1:1 and unchanged. Returns a single-element list (callers iterate). See decisions-log.
    """
    return [_season_code(completed_season(award_year))]


def _club_cl_round(
    clubs: list[str], seasons: list[str], cl_lookup: dict[tuple[str, str], int]
) -> int:
    """Deepest CL round across the player's club(s) in the award-year's season(s). 0 if none."""
    return max(
        (cl_lookup.get((s, c), 0) for c in clubs for s in seasons),
        default=0,
    )


def _won_league(clubs: list[str], seasons: list[str], champs: set[tuple[str, str]]) -> bool:
    return any((s, c) in champs for c in clubs for s in seasons)


def _tournament_result(
    nation: str | None, award_year: int, tourn: dict[tuple[int, str], int]
) -> int:
    if nation is None:
        return 0
    return tourn.get((award_year, nation), 0)


def _tournament_overachievement(
    nation: str | None, award_year: int, overach: dict[tuple[int, str], int]
) -> int:
    """How far a nation's tournament finish beat its pre-tournament expectation (>=0).

    `overach` maps (award_year, nation) -> max(0, result - expected), where `expected` is a curated
    pre-tournament seed (FIFA ranking / consensus favourite, see tournament_results.csv). 0 when the
    nation is unknown or didn't record a deep run. Croatia 2018 = +2; favourites who won = 0. Pure.
    """
    if nation is None:
        return 0
    return overach.get((award_year, nation), 0)


# --- reference loaders ------------------------------------------------------

def _load_references() -> tuple[dict, set, dict, dict, dict]:
    cl = pd.read_csv(REFERENCE_DIR / "cl_results.csv", dtype={"season": str})
    cl_lookup = {(r.season, r.club): int(r.cl_round) for r in cl.itertuples()}

    champ = pd.read_csv(REFERENCE_DIR / "league_champions.csv", dtype={"season": str})
    champs = {(r.season, r.club) for r in champ.itertuples()}

    tour = pd.read_csv(REFERENCE_DIR / "tournament_results.csv")
    tourn = (
        tour.groupby(["award_year", "nation"])["result"].max().to_dict()
    )  # max result if a nation features in multiple tournaments that year
    # Overachievement = finish beyond the pre-tournament seed (>=0); 0 when on/below expectation.
    tour["overach"] = (tour["result"] - tour["expected"]).clip(lower=0)
    overach = tour.groupby(["award_year", "nation"])["overach"].max().to_dict()

    nat = pd.read_csv(REFERENCE_DIR / "player_nation.csv")
    nation = dict(zip(nat["player"], nat["nation"], strict=True))
    return cl_lookup, champs, tourn, nation, overach


# --- build ------------------------------------------------------------------

def _judged_season_clubs() -> dict[tuple[str, str], set[str]]:
    """(player, understat-season) -> set of judged-season clubs (reference spelling).

    awards.club is the player's club AT THE CEREMONY, which is wrong for transfer cases (e.g.
    Messi 2023 lists Inter Miami, not PSG where he played the judged season). Unioning the
    Understat per-season club fixes the domestic-title / CL credit for those players.
    """
    us = understat.pull()[["player", "season", "team"]].copy()
    us["club"] = us["team"].map(lambda t: _US_ALIASES.get(t, t))
    return us.groupby(["player", "season"])["club"].agg(set).to_dict()


def _build_team_success() -> pd.DataFrame:
    aw = awards.pull()
    cl_lookup, champs, tourn, nation, overach = _load_references()
    us_clubs = _judged_season_clubs()

    rows: list[dict] = []
    for r in aw.itertuples():
        award_year = int(r.award_year)
        if award_year not in AWARD_YEAR_SEASONS:
            continue  # 2017 = degraded panel, no spine team-success
        seasons = _season_codes(award_year)
        clubs = set(_norm_clubs(r.club))
        for s in seasons:  # union the judged-season Understat club(s)
            clubs |= us_clubs.get((r.player, s), set())
        clubs = list(clubs)
        nat = nation.get(r.player)
        cl_round = _club_cl_round(clubs, seasons, cl_lookup)
        rows.append(
            {
                "player": r.player,
                "award_year": award_year,
                "nation": nat,
                "cl_round": cl_round,
                "won_cl": cl_round == 5,
                "won_league": _won_league(clubs, seasons, champs),
                "tournament_result": _tournament_result(nat, award_year, tourn),
                "tournament_overachievement": _tournament_overachievement(
                    nat, award_year, overach
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(["award_year", "player"]).reset_index(drop=True)


def build(*, refresh: bool = False) -> pd.DataFrame:
    """Return per-(player, award_year) team-success block (cached)."""
    return cached_frame(CACHE_NAME, _build_team_success, refresh=refresh)
