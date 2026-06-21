"""StatsBomb open-data pull — semifinalist tournament squads (the Tier-2 pool's 3rd source).

The candidate pool's production + team-success sources miss players who mattered via a national-team
run (defenders, non-top-5-league players). StatsBomb open data (free, no auth) covers the spine's
majors with full lineups, so we pull the **semifinalist nations' squads + minutes** per tournament.

Coverage (verified): World Cup 2018 (→2018 award), Euro 2020 (→2021), World Cup 2022 (→2023),
Euro 2024 + Copa América 2024 (→2024). No open-data major for 2019 (Copa/AFCON) or 2025 (gaps we
document). Award-year mapping mirrors data/reference/tournament_results.csv.

Cache-first + resumable per match (one lineup fetch per match shard); minutes are summed from the
lineup `positions` time ranges. StatsBomb uses full legal names — reconciliation to Understat/awards
spellings happens downstream in the pool via `awards.name_key`.
"""

from __future__ import annotations

from functools import partial

import pandas as pd

from ..cache import cached_frame, cached_records
from ..config import REFERENCE_DIR

CACHE_NAME = "statsbomb_tournament"
LINEUP_CACHE = "statsbomb_lineups"

# (competition_id, season_id, tournament label as in tournament_results.csv, award_year)
_TOURNAMENTS = [
    (43, 3, "World Cup 2018", 2018),
    (55, 43, "Euro 2020", 2021),
    (43, 106, "World Cup 2022", 2023),
    (55, 282, "Euro 2024", 2024),
    (223, 282, "Copa America 2024", 2024),
]
_SEMIFINAL = 3  # tournament_results.result >= 3 means reached the semifinal


# --- pure helpers (offline-testable) ----------------------------------------

def _mmss(value) -> float | None:
    """'86:31' -> 86.52 minutes; None/NaN -> None."""
    if not isinstance(value, str) or ":" not in value:
        return None
    mm, ss = value.split(":")
    return int(mm) + int(ss) / 60.0


def _minutes(positions) -> float:
    """Minutes on the pitch from a lineup `positions` list (cumulative MM:SS stints).

    A player's time = last exit − first entry; an open final stint (`to is None`) means they played
    to the whistle, approximated at 95' (covers stoppage). Robust to empty/odd records.
    """
    if not isinstance(positions, (list, tuple)) or not positions:
        return 0.0
    starts = [m for m in (_mmss(p.get("from")) for p in positions) if m is not None]
    if not starts:
        return 0.0
    if any(p.get("to") is None for p in positions):
        end = 95.0
    else:
        ends = [m for m in (_mmss(p.get("to")) for p in positions) if m is not None]
        end = max(ends) if ends else min(starts)
    return max(0.0, round(end - min(starts), 1))


def _player_name(nickname, full_name) -> str:
    """Prefer the StatsBomb nickname (common name) over the full legal name when present."""
    return nickname if isinstance(nickname, str) and nickname.strip() else full_name


def _semifinalists() -> dict[tuple[int, str], set[str]]:
    """(award_year, tournament) -> set of nations that reached the semifinal (result >= 3)."""
    tr = pd.read_csv(REFERENCE_DIR / "tournament_results.csv")
    sf = tr[tr["result"] >= _SEMIFINAL]
    out: dict[tuple[int, str], set[str]] = {}
    for r in sf.itertuples():
        out.setdefault((int(r.award_year), r.tournament), set()).add(r.nation)
    return out


# --- network ----------------------------------------------------------------

def _fetch_lineup(match_id: int, *, tasks: dict) -> pd.DataFrame:
    """One match -> per-player rows for the semifinalist teams in it (minutes summed per stint)."""
    from statsbombpy import sb  # noqa: PLC0415  (lazy; the [statsbomb] extra)

    award_year, tournament, sf_nations = tasks[match_id]
    rows: list[dict] = []
    for team, df in sb.lineups(match_id).items():
        if team not in sf_nations:
            continue
        for r in df.itertuples():
            rows.append(
                {
                    "award_year": award_year,
                    "tournament": tournament,
                    "nation": team,
                    "player": _player_name(r.player_nickname, r.player_name),
                    "full_name": r.player_name,
                    "match_id": match_id,
                    "minutes": _minutes(r.positions),
                }
            )
    cols = ["award_year", "tournament", "nation", "player", "full_name", "match_id", "minutes"]
    return pd.DataFrame(rows, columns=cols)


def _build() -> pd.DataFrame:
    from statsbombpy import sb  # noqa: PLC0415

    sf_map = _semifinalists()
    tasks: dict[int, tuple] = {}
    for comp, season, label, year in _TOURNAMENTS:
        sf_nations = sf_map.get((year, label), set())
        if not sf_nations:
            continue
        matches = sb.matches(comp, season)
        for m in matches.itertuples():
            if m.home_team in sf_nations or m.away_team in sf_nations:
                tasks[int(m.match_id)] = (year, label, sf_nations)

    per_match = cached_records(LINEUP_CACHE, list(tasks), partial(_fetch_lineup, tasks=tasks))
    if per_match.empty:
        return per_match
    squads = (
        per_match.groupby(["award_year", "tournament", "nation", "player", "full_name"],
                          as_index=False)["minutes"].sum()
        .sort_values(["award_year", "nation", "minutes"], ascending=[True, True, False])
        .reset_index(drop=True)
    )
    return squads


def pull(*, refresh: bool = False) -> pd.DataFrame:
    """Per-(award_year, tournament, nation, player): summed tournament minutes (cached)."""
    return cached_frame(CACHE_NAME, _build, refresh=refresh)
