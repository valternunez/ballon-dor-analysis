"""FBref defensive / keeper season stats — the non-attacking merit source.

Understat carries NO defensive or goalkeeping metric, so defenders, deep mids, and keepers had no
individual merit at all (the "Jorginho blind spot", plus the keeper gap). This module assembles
per-player-season big-5 stats that the merit layer turns into THREE non-attacking signals:

  * **MF ball-winning** — tackles-won + interceptions + blocks + clearances per 90 (VOLUME).
  * **CB quality** — tackle success % + aerial-duel win % (EFFICIENCY; volume is inverted for CBs —
    elite CBs on dominant sides make the fewest actions, so we measure how WELL not how MUCH).
  * **GK shot-stopping** — PSxG+/- (post-shot xG minus goals allowed) + save %.

FBref's advanced stats went dark ~2022/23 (Opta transition), so no single source spans the spine —
three are reconciled (see decisions log):

  * 2017/18-2022/23 — worldfootballR_data RDS files (free raw-GitHub, via ``pyreadr``): defense +
    misc (aerials) + keepers_adv (PSxG+/-) + keepers (save%).
  * 2023/24        — ``data/reference/fbref_defense_2023_2024.csv`` (Kaggle big-5 export).
  * 2024/25        — ``data/reference/fbref_defense_2024_2025.csv`` (hubertsidorowicz/Kaggle big-5).

Recent seasons are committed reference CSVs so a rebuild needs no Kaggle token or manual FBref
export; only the free RDS files are fetched live.

(Team possession for a possession-adjusted CB volume metric is only available 2017-2023, so we ship
the year-consistent efficiency-only CB metric instead — see decisions log.)

Output: one row per (player, season), big-5 only — defensive COUNTS + efficiency %s + keeper stats.
Season codes match ``merit._season_code`` ('2017-2018' -> '1718').
"""

from __future__ import annotations

import os
import tempfile
import urllib.request

import pandas as pd

from ..cache import cached_frame
from ..config import REFERENCE_DIR

CACHE_NAME = "fbref_defense"

_WFR_BASE = (
    "https://raw.githubusercontent.com/JaseZiv/worldfootballR_data/master/"
    "data/fb_big5_advanced_season_stats/"
)
_BIG5 = {"Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1"}

# MF ball-winning volume (summed across stints). Used by the midfield defensive merit.
METRICS = ["tackles_won", "interceptions", "blocks", "clearances"]
# Counts summed across stints: ball-winning volume + progressive passes (CB ball-playing signal).
_SUM_COLS = [*METRICS, "prog_passes"]
# CB-efficiency + keeper signals — ratios / nets carried from the heaviest stint, NOT summed.
_CARRY = ["tackle_pct", "aerial_win_pct", "psxg_net", "save_pct"]
_SCHEMA = [
    "season", "player", "nationality", "position", "squad", "league", "nineties",
    *_SUM_COLS, *_CARRY,
]


# --- pure helpers (offline-testable) ----------------------------------------

def _season_from_end(end: int) -> str:
    """FBref Season_End_Year -> Understat-style season code (2018 -> '1718')."""
    return f"{(end - 1) % 100:02d}{end % 100:02d}"


def _aggregate(df: pd.DataFrame) -> pd.DataFrame:
    """One row per real player-season, then one per (player-name, season).

    Aggregating by `pid` (a true player id — worldfootballR's URL, or name+club for the reference
    rows) sums a mid-season mover's COUNTS without merging two different players who share a name
    (the Man City vs Real Betis "Rodri" trap). Efficiency %s / PSxG+/- are carried from the
    heaviest-minutes stint (they don't sum). The downstream merit join is name-keyed, so a final
    dedup keeps the heaviest-minutes namesake.
    """
    df = df.dropna(subset=["nineties"]).copy()
    sums = df.groupby(["pid", "season"], as_index=False)[["nineties", *_SUM_COLS]].sum(min_count=1)
    heaviest = df.sort_values("nineties").groupby(["pid", "season"], as_index=False).tail(1)
    meta = heaviest[
        ["pid", "season", "player", "nationality", "position", "squad", "league", *_CARRY]
    ]
    person = sums.merge(meta, on=["pid", "season"], how="left")
    return (
        person.sort_values("nineties")
        .groupby(["player", "season"], as_index=False)
        .tail(1)
        .reset_index(drop=True)
    )


# --- worldfootballR RDS loader (2017/18-2022/23) ----------------------------

def _fetch_rds(name: str) -> pd.DataFrame:
    """Download + read a worldfootballR `.rds` into a DataFrame (temp file; trusted raw GitHub)."""
    import pyreadr  # noqa: PLC0415  (heavy/optional; only on a cache miss)

    req = urllib.request.Request(_WFR_BASE + name, headers={"User-Agent": "Mozilla/5.0"})
    payload = urllib.request.urlopen(req, timeout=120).read()  # noqa: S310
    tmp = tempfile.NamedTemporaryFile(suffix=".rds", delete=False)
    try:
        tmp.write(payload)
        tmp.close()
        return next(iter(pyreadr.read_r(tmp.name).values()))
    finally:
        os.unlink(tmp.name)


def _load_worldfootballr() -> pd.DataFrame:
    """Big-5 outfield (defense + aerials) ∪ keepers (PSxG+/- + save%), seasons ending 2018-2023."""
    defense = _fetch_rds("big5_player_defense.rds")
    misc = _fetch_rds("big5_player_misc.rds")[["Url", "Season_End_Year", "Won_percent_Aerial"]]
    passing = _fetch_rds("big5_player_passing.rds")[["Url", "Season_End_Year", "Prog"]]
    outfield = defense.merge(misc, on=["Url", "Season_End_Year"], how="left").merge(
        passing, on=["Url", "Season_End_Year"], how="left"
    )
    out = pd.DataFrame(
        {
            "pid": outfield["Url"].astype(str),
            "season": outfield["Season_End_Year"].astype(int).map(_season_from_end),
            "player": outfield["Player"].astype(str),
            "nationality": outfield["Nation"].astype(str),
            "position": outfield["Pos"].astype(str),
            "squad": outfield["Squad"].astype(str),
            "league": outfield["Comp"].astype(str),
            "nineties": pd.to_numeric(outfield["Mins_Per_90"], errors="coerce"),
            "tackles_won": pd.to_numeric(outfield["TklW_Tackles"], errors="coerce"),
            "interceptions": pd.to_numeric(outfield["Int"], errors="coerce"),
            "blocks": pd.to_numeric(outfield["Blocks_Blocks"], errors="coerce"),
            "clearances": pd.to_numeric(outfield["Clr"], errors="coerce"),
            "prog_passes": pd.to_numeric(outfield["Prog"], errors="coerce"),
            "tackle_pct": pd.to_numeric(outfield["Tkl_percent_Vs"], errors="coerce"),
            "aerial_win_pct": pd.to_numeric(outfield["Won_percent_Aerial"], errors="coerce"),
            "psxg_net": pd.NA,
            "save_pct": pd.NA,
        }
    )

    kadv = _fetch_rds("big5_player_keepers_adv.rds")
    kbas = _fetch_rds("big5_player_keepers.rds")[["Url", "Season_End_Year", "Save_percent"]]
    keepers = kadv.merge(kbas, on=["Url", "Season_End_Year"], how="left")
    gk = pd.DataFrame(
        {
            "pid": keepers["Url"].astype(str),
            "season": keepers["Season_End_Year"].astype(int).map(_season_from_end),
            "player": keepers["Player"].astype(str),
            "nationality": keepers["Nation"].astype(str),
            "position": "GK",
            "squad": keepers["Squad"].astype(str),
            "league": keepers["Comp"].astype(str),
            "nineties": pd.to_numeric(keepers["Mins_Per_90"], errors="coerce"),
            "tackles_won": pd.NA, "interceptions": pd.NA, "blocks": pd.NA, "clearances": pd.NA,
            "prog_passes": pd.NA, "tackle_pct": pd.NA, "aerial_win_pct": pd.NA,
            "psxg_net": pd.to_numeric(keepers["PSxG+_per__minus__Expected"], errors="coerce"),
            "save_pct": pd.to_numeric(keepers["Save_percent"], errors="coerce"),
        }
    )

    both = pd.concat([out, gk], ignore_index=True)
    return both[both["league"].isin(_BIG5)].reset_index(drop=True)


def _load_reference(filename: str) -> pd.DataFrame:
    """Read a committed big-5 reference CSV (standard schema; tolerant of new cols)."""
    df = pd.read_csv(REFERENCE_DIR / filename, dtype={"season": str})
    for c in ["nineties", *METRICS, *_CARRY]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["pid"] = df["player"].astype(str) + "|" + df["squad"].astype(str)
    return df[["pid", *[c for c in _SCHEMA if c in df.columns]]]


# --- build ------------------------------------------------------------------

def _build() -> pd.DataFrame:
    frames = [
        _load_worldfootballr(),
        _load_reference("fbref_defense_2023_2024.csv"),
        _load_reference("fbref_defense_2024_2025.csv"),
    ]
    df = pd.concat(frames, ignore_index=True)
    df["season"] = df["season"].astype(str)
    for c in _SCHEMA:
        if c not in df.columns:
            df[c] = pd.NA
    out = _aggregate(df)
    return out[_SCHEMA].sort_values(["season", "player"]).reset_index(drop=True)


def pull(*, refresh: bool = False) -> pd.DataFrame:
    """Return per-(player, season) big-5 defensive + keeper stats (cached)."""
    return cached_frame(CACHE_NAME, _build, refresh=refresh)
