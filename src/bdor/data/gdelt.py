"""GDELT global news-volume pull (hype proxy #2) — via the DOC 2.0 API.

The differentiator signal. Secondary to pageviews, so we use the free no-auth DOC 2.0 API
(not BigQuery GKG). `mode=timelinevol` returns NORMALIZED volume intensity (% of all global
articles matching the query) — which already handles GDELT's source-growth-over-time.

Disambiguation: a quoted FULL-NAME phrase is inherently specific ("Mason Mount" won't match a
mountain; "Heung-min Son" is unambiguous), optionally OR'd with name-order alias variants from
Wikidata for recall. (The `theme:SOCCER` filter from the plan returned zero matches — that GKG
theme code is invalid via the DOC API — so we rely on the phrase + the precision spot-check.)

Confirmed live: historical 2017+ works; a single 8-year query keeps DAILY resolution (~3266
points); Messi volume peaks on 2022-12-18 (WC final). This lands raw daily volume only — the
de-fame / window / baseline aggregation (H⊥) is feature-stage, same per-proxy template as pageviews.
"""

from __future__ import annotations

import logging
import time
from functools import partial

import pandas as pd
import requests

from ..cache import cached_frame, cached_records
from . import wikidata

logger = logging.getLogger(__name__)

VOLUME_CACHE = "gdelt_volume_daily"
BY_PLAYER_CACHE = "gdelt_by_player"

_START = "20170101000000"
_END = "20251231000000"
_API = "https://api.gdeltproject.org/api/v2/doc/doc"
_UA = (
    "bdor-research/0.1 (Ballon d'Or hype-vs-merit analysis; "
    "contact: valter.antonio1996@gmail.com)"
)
# GDELT's DOC API imposes a cumulative per-IP/window ban that outlasts in-request backoff.
# So we fail FAST here (short retry budget) and let an orchestration-level cooldown loop
# (see pull(): _COOLDOWN) wait the ban out and resume from the per-player cache.
_BASE_DELAY = 6.0
_MAX_RETRIES = 4
_MAX_ALIASES = 3
_COOLDOWN = 360.0   # seconds to wait after a throttle wall before resuming
_COOLDOWN_CYCLES = 30
_OUT_COLS = ["player", "date", "volume"]

_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"User-Agent": _UA})
    return _session


# --- pure helpers (offline-testable) ----------------------------------------

def _is_name_variant(alias: str, name: str) -> bool:
    """A multi-word alias sharing the surname token — recovers name-order variants."""
    tokens = name.lower().split()
    if not tokens or len(alias.split()) < 2:
        return False
    surname = tokens[-1]
    return len(surname) > 1 and surname in alias.lower()


def _build_query(name: str, aliases: list[str]) -> str:
    """Quoted full name OR'd with up to N name-variant aliases (no theme filter)."""
    forms = [name]
    for alt in aliases:
        if alt != name and _is_name_variant(alt, name) and alt not in forms:
            forms.append(alt)
        if len(forms) > _MAX_ALIASES:
            break
    quoted = [f'"{f}"' for f in forms]
    return quoted[0] if len(quoted) == 1 else "(" + " OR ".join(quoted) + ")"


def _parse_timeline(payload: dict) -> pd.DataFrame:
    """timelinevol JSON -> tidy [date, volume]. Empty {} (no matches) -> empty frame."""
    timeline = payload.get("timeline", [])
    if not timeline:
        return pd.DataFrame(columns=["date", "volume"])
    data = timeline[0].get("data", [])
    if not data:
        return pd.DataFrame(columns=["date", "volume"])
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(
        df["date"].str.replace("T000000Z", "", regex=False), format="%Y%m%d"
    )
    return df.rename(columns={"value": "volume"})[["date", "volume"]]


# --- network ----------------------------------------------------------------

def _request(query: str) -> dict:
    """timelinevol GET with backoff on 429/503 + GDELT connection drops."""
    params = {
        "query": query, "mode": "timelinevol", "format": "json",
        "startdatetime": _START, "enddatetime": _END,
    }
    for attempt in range(_MAX_RETRIES):
        time.sleep(_BASE_DELAY)
        try:
            resp = _get_session().get(_API, params=params, timeout=90)
        except requests.exceptions.ConnectionError:
            time.sleep(min(15.0 * (attempt + 1), 90.0))
            continue
        if resp.status_code in (429, 503):
            retry_after = resp.headers.get("Retry-After", "")
            wait = float(retry_after) if retry_after.isdigit() else 15.0 * (attempt + 1)
            time.sleep(min(wait, 90.0))
            continue
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError:
            # A *soft* ban returns HTTP 200 with an empty / HTML body (not a 429), so json()
            # raises. Treat it as a throttle: back off and retry. Exhausting retries raises the
            # RuntimeError below, which the outer cooldown loop catches and resumes from cache —
            # rather than letting the JSONDecodeError crash the whole pull (decisions log).
            time.sleep(min(15.0 * (attempt + 1), 90.0))
            continue
    raise RuntimeError(f"gdelt: exhausted retries for query {query!r}")


def _fetch_player(player: str, *, queries: dict[str, str]) -> pd.DataFrame:
    df = _parse_timeline(_request(queries[player]))
    if df.empty:
        return pd.DataFrame(columns=_OUT_COLS)
    df["player"] = player
    return df[_OUT_COLS]


def _build_volume(players: list[str] | None) -> pd.DataFrame:
    universe = players if players is not None else wikidata.award_universe()
    wd = wikidata.pull(universe)
    aliases = {
        p: list(g.loc[g["kind"] == "alias", "value"]) for p, g in wd.groupby("player")
    }
    queries = {p: _build_query(p, aliases.get(p, [])) for p in universe}
    per_player = cached_records(
        BY_PLAYER_CACHE, sorted(universe), partial(_fetch_player, queries=queries)
    )
    if per_player.empty:
        return per_player
    return per_player.sort_values(["player", "date"]).reset_index(drop=True)


def pull(players: list[str] | None = None, *, refresh: bool = False) -> pd.DataFrame:
    """Return daily normalized GDELT volume per player (cached). Defaults to awards universe.

    GDELT bans bursty IPs for minutes at a time. The per-player cache is resumable, so on a
    throttle wall we cool down and resume — repeating until the universe is covered.
    """
    def _build() -> pd.DataFrame:
        for cycle in range(_COOLDOWN_CYCLES):
            try:
                return _build_volume(players)
            except RuntimeError as exc:  # throttle wall (exhausted retries on a player)
                if cycle == _COOLDOWN_CYCLES - 1:
                    raise
                logger.warning("gdelt throttled (%s) — cooldown %.0fs then resume", exc, _COOLDOWN)
                time.sleep(_COOLDOWN)
        raise RuntimeError("gdelt: cooldown cycles exhausted")

    return cached_frame(VOLUME_CACHE, _build, refresh=refresh)
