"""Ballon d'Or outcome data — vote points per finisher per award year.

THE JOIN TARGET. Everything else (performance, pageviews, GDELT) attaches to the
(award_year, player) keys produced here.

Approach:
  * For each year in config.SPINE_YEARS, fetch the per-edition Wikipedia page and
    pandas.read_html all tables on it.
  * The page carries several tables (men's, women's, Kopa, Yashin). The men's ranking
    table SCHEMA VARIES by year (2018: Rank/Player/Club(s)/Points; 2024 adds
    Nationality/Position), so parsing is by HEADER NAME, not column position.
  * Disambiguate the men's ranking by selecting the table whose rank-1 player matches the
    known winner in award_windows.csv (accent-insensitive). This doubles as validation.
  * Clean: strip footnote markers, coerce points, forward-fill tied ranks, normalise names.
  * Model uses vote POINTS / share, not rank (PROJECT_NOTES.md "Outcome variable").
"""

from __future__ import annotations

import re
from io import StringIO

import pandas as pd
import requests
from unidecode import unidecode

from ..cache import cached_frame
from ..config import AWARD_YEARS
from ..windows import load_windows

CACHE_NAME = "awards_results"

# Output schema (the contract for downstream joins). country/position are nullable —
# not every year's table carries them.
COLUMNS = [
    "award_year",
    "rank",
    "player",
    "player_norm",
    "club",
    "country",
    "position",
    "points",
]

_WIKI_URL = "https://en.wikipedia.org/wiki/{year}_Ballon_d%27Or"
_USER_AGENT = (
    "bdor-research/0.1 (Ballon d'Or hype-vs-merit analysis; "
    "contact: valter.antonio1996@gmail.com)"
)
_FOOTNOTE_RE = re.compile(r"\[[^\]]*\]")

# Header text (lowercased, footnotes stripped) -> canonical column name.
_HEADER_SYNONYMS = {
    "rank": "rank",
    "player": "player",
    "points": "points",
    "pts": "points",
    "club": "club",
    "clubs": "club",
    "club(s)": "club",
    "nationality": "country",
    "country": "country",
    "position": "position",
    "pos": "position",
    "pos.": "position",
}
_REQUIRED = {"player", "points"}


class _NotARankingTable(Exception):
    """Raised when a parsed table lacks the men's-ranking columns."""


def _normalise_name(s: str) -> str:
    """Accent-fold + lowercase for join keys / winner matching."""
    return unidecode(str(s)).strip().lower()


# Understat player spelling -> Wikipedia/awards spelling, for the few players where accent-folding
# alone leaves the keys different (suffix, nickname). WITHOUT this, the cross-source feature joins
# (awards outcome <-> Understat merit) silently drop the player — e.g. Mbappé, a multi-year top
# finisher, and the keys must agree for the model tables to include him. See decisions log.
PLAYER_ALIASES = {
    "Kylian Mbappe-Lottin": "Kylian Mbappé",
    "Daniel Carvajal": "Dani Carvajal",
    "Fabián": "Fabián Ruiz",
    # StatsBomb tournament names that differ from the Understat spelling (else they'd duplicate).
    "Alexis MacAllister": "Alexis Mac Allister",
    "Azzedine Ounahi": "Azz-Eddine Ounahi",
    "Daniel Olmo": "Dani Olmo",
    "Nayef Aguerd": "Naif Aguerd",
}


def name_key(name: str) -> str:
    """Canonical join key for a player: alias-resolved, then accent-folded + lowercased.

    The single source of truth for matching names ACROSS sources (Understat ↔ Wikipedia). Use this
    as the merge key wherever a feature table built from Understat names meets the awards table.
    """
    return _normalise_name(PLAYER_ALIASES.get(name, name))


def _strip_footnotes(value):
    """Remove '[6]'-style reference markers from a cell; pass non-strings through."""
    if not isinstance(value, str):
        return value
    return _FOOTNOTE_RE.sub("", value).strip()


def _flatten_columns(columns) -> list[str]:
    """Flatten a possibly-MultiIndex header to a list of single strings."""
    if isinstance(columns, pd.MultiIndex):
        flat = []
        for tup in columns:
            parts = [
                str(p) for p in tup if str(p) and not str(p).startswith("Unnamed")
            ]
            flat.append(parts[-1] if parts else "")
        return flat
    return [str(c) for c in columns]


def _clean_table(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """Normalise one raw table into the COLUMNS schema.

    Raises _NotARankingTable if the table lacks the required ranking headers.
    """
    flat = _flatten_columns(df.columns)

    # Recognised header -> position (first occurrence wins).
    canon_by_pos: dict[int, str] = {}
    for i, raw in enumerate(flat):
        key = _strip_footnotes(raw).strip().lower()
        name = _HEADER_SYNONYMS.get(key)
        if name and name not in canon_by_pos.values():
            canon_by_pos[i] = name

    present = set(canon_by_pos.values())
    if not _REQUIRED.issubset(present):
        raise _NotARankingTable(
            f"{year}: headers {flat!r} missing {_REQUIRED - present}"
        )

    out = pd.DataFrame()
    for i, name in canon_by_pos.items():
        out[name] = df.iloc[:, i].map(_strip_footnotes)

    # rank: tied ranks may be shown once (blank on the spanned rows) -> forward-fill.
    if "rank" in out.columns:
        out["rank"] = pd.to_numeric(out["rank"], errors="coerce").ffill().astype("Int64")
    else:
        out["rank"] = pd.Series(range(1, len(out) + 1), dtype="Int64")

    out["points"] = pd.to_numeric(out["points"], errors="coerce").astype("Int64")
    out["player"] = out["player"].astype(str).str.strip()
    out["player_norm"] = out["player"].map(_normalise_name)
    out["award_year"] = year

    for opt in ("club", "country", "position"):
        if opt in out.columns:
            out[opt] = out[opt].astype("string").str.strip()
        else:
            out[opt] = pd.array([pd.NA] * len(out), dtype="string")

    # Drop footer / note rows that carry no real finisher.
    out = out[(out["player"] != "") & out["player"].notna() & out["points"].notna()]
    return out[COLUMNS].reset_index(drop=True)


def _select_mens_table(tables: list[pd.DataFrame], winner: str, year: int) -> pd.DataFrame:
    """Pick the men's ranking table as the one whose rank-1 player is the known winner."""
    winner_norm = _normalise_name(winner)
    seen: list[str] = []
    for tbl in tables:
        try:
            cleaned = _clean_table(tbl, year)
        except _NotARankingTable:
            continue
        if cleaned.empty:
            continue
        top = cleaned.sort_values("rank").iloc[0]
        seen.append(top["player_norm"])
        if top["player_norm"] == winner_norm:
            return cleaned
    raise ValueError(
        f"{year}: no men's ranking table with rank-1 == {winner!r}. "
        f"Rank-1 players seen across candidate tables: {seen}"
    )


def _scrape_awards() -> pd.DataFrame:
    windows = load_windows()
    frames: list[pd.DataFrame] = []
    for year in AWARD_YEARS:
        winner = str(windows.loc[year, "winner"])
        resp = requests.get(
            _WIKI_URL.format(year=year),
            headers={"User-Agent": _USER_AGENT},
            timeout=30,
        )
        resp.raise_for_status()
        tables = pd.read_html(StringIO(resp.text))
        frames.append(_select_mens_table(tables, winner, year))
    return pd.concat(frames, ignore_index=True)


def pull(*, refresh: bool = False) -> pd.DataFrame:
    """Return the Ballon d'Or results table (cached)."""
    return cached_frame(CACHE_NAME, _scrape_awards, refresh=refresh)
