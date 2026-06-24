"""FotMob season-average player ratings — an INDEPENDENT cross-check on the merit index.

Not a merit input. The merit spine stays transparent box-score stats; this pulls FotMob's holistic
match rating purely to *validate* (or stress-test) that index — especially for centre-backs, which
box scores read poorly. FotMob's rating is **algorithmic** (≈300 Opta event stats per match, 0–10,
baseline 6) but **proprietary-weighted and offence-skewed** (shots/key-passes/take-ons dominate), so
it shares our merit's defensive blind spot — which is exactly why an *independent* pipeline agreeing
is informative, and why it must never enter `merit_z` (see docs + the plan).

Access: no official API key. The player page server-renders everything in `__NEXT_DATA__`, so ONE
request per player yields every season's average rating (all-comps + per-league), historically — no
`x-mas` token wall (that gates the JSON API, not the page). IDs come from the open suggest endpoint.
Cache-first + resumable per player (`cache.cached_records`), like the pageviews / GDELT pulls.
"""

from __future__ import annotations

import json
import logging
import re
import time

import pandas as pd
import requests

from ..cache import cached_records
from . import wikidata

logger = logging.getLogger(__name__)

CACHE_NAME = "fotmob_ratings"
_SUGGEST = "https://apigw.fotmob.com/searchapi/suggest?term={term}&lang=en"
_PLAYER = "https://www.fotmob.com/players/{pid}"
_UA = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
}
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
_SEASON_RE = re.compile(r"^\d{4}/\d{4}$")  # domestic season "2017/2018" (skip national-team "2026")
_OUT_COLS = ["player", "season", "fotmob_rating", "apps"]
_PACE_S = 1.5  # polite delay between players (two GETs each)

_session: requests.Session | None = None


def _get(url: str) -> requests.Response:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(_UA)
    return _session.get(url, timeout=25)


# --- pure helpers (offline-testable) ----------------------------------------

def _season_entries(next_data: dict) -> list[dict]:
    """Senior-career season entries from a parsed __NEXT_DATA__ dict (empty if absent). Pure."""
    data = next_data.get("props", {}).get("pageProps", {}).get("data", {})
    items = data.get("careerHistory", {}).get("careerItems", {}).get("senior", {})
    return items.get("seasonEntries", []) or []


def _aggregate_seasons(entries: list[dict], player: str) -> pd.DataFrame:
    """Per-season appearance-weighted average rating. Pure / offline-testable.

    A mid-season transfer yields two rows for one season (e.g. Van Dijk 2017/2018); we collapse them
    into an appearances-weighted mean rating. Ratingless rows (pre-2016/17 history) are dropped, and
    only domestic "YYYY/YYYY" seasons are kept (national-team single-year entries are skipped).
    """
    rows = []
    for e in entries:
        season = str(e.get("seasonName", ""))
        if not _SEASON_RE.match(season):
            continue
        rating = (e.get("rating") or {}).get("rating")
        if rating in (None, "", "0", 0):
            continue
        try:
            rows.append((season, float(rating), float(e.get("appearances") or 0)))
        except (TypeError, ValueError):
            continue
    if not rows:
        return pd.DataFrame(columns=_OUT_COLS)
    df = pd.DataFrame(rows, columns=["season", "rating", "apps"])
    df["w"] = df["apps"].where(df["apps"] > 0, 1.0)  # appearance weights; equal if apps missing
    df["wr"] = df["rating"] * df["w"]
    g = df.groupby("season", as_index=False).agg(
        wr=("wr", "sum"), w=("w", "sum"), apps=("apps", "sum")
    )
    g["fotmob_rating"] = (g["wr"] / g["w"]).round(3)
    g["apps"] = g["apps"].astype(int)
    g["player"] = player
    return g[_OUT_COLS].sort_values("season").reset_index(drop=True)


# --- network ----------------------------------------------------------------

def _resolve_id(player: str) -> str | None:
    """Top squad-member suggestion id for a player name (open endpoint, no token)."""
    try:
        j = _get(_SUGGEST.format(term=requests.utils.quote(player))).json()
        opts = (j.get("squadMemberSuggest") or [{}])[0].get("options") or []
        return opts[0]["payload"]["id"] if opts else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("fotmob: id lookup failed for %s (%s)", player, exc)
        return None


def _fetch_player(player: str) -> pd.DataFrame:
    """Resolve id → fetch the player page → parsed per-season average ratings (resumable shard)."""
    time.sleep(_PACE_S)
    pid = _resolve_id(player)
    if pid is None:
        return pd.DataFrame(columns=_OUT_COLS)
    resp = _get(_PLAYER.format(pid=pid))
    m = _NEXT_DATA_RE.search(resp.text)
    if resp.status_code != 200 or not m:
        logger.warning("fotmob: no __NEXT_DATA__ for %s (id %s, status %s)",
                       player, pid, resp.status_code)
        return pd.DataFrame(columns=_OUT_COLS)
    return _aggregate_seasons(_season_entries(json.loads(m.group(1))), player)


def pull(players: list[str] | None = None, *, refresh: bool = False) -> pd.DataFrame:
    """Per (player, season) FotMob average rating for the award universe (cached, resumable).

    One request-pair per player; the per-player cache resumes if interrupted. Cross-check data only,
    never an input to merit or the H⊥ de-fame.
    """
    universe = players if players is not None else wikidata.award_universe()
    return cached_records(CACHE_NAME, sorted(universe), _fetch_player, refresh=refresh)
