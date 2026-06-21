"""Wikipedia pageviews pull — the primary hype proxy.

For each player we sum DAILY pageviews across ALL language editions (article titles from
wikidata.sitelinks). Daily (not monthly) so the feature layer can respect the exact shortlist
hype_cut without smearing the leakage boundary (docs/windowing.md).

This module lands raw view counts only. The de-fame / window-mean / trailing-baseline
aggregation (H⊥) is feature-stage, NOT here.

Caching: per-player shards (one fetch_one pulls all of a player's languages) via cached_records
("pageviews_by_lang", resumable); the assembled all-language daily sum is cached via cached_frame
("pageviews_all_lang_daily"). Per-language shards are retained for the later media-bias breakdown.
"""

from __future__ import annotations

import time
from functools import partial
from urllib.parse import quote

import pandas as pd
import requests

from ..cache import cached_frame, cached_records
from . import wikidata

ALL_LANG_CACHE = "pageviews_all_lang_daily"
BY_LANG_CACHE = "pageviews_by_lang"

# One request returns the whole range. 2016-01-01 covers trailing-12mo baselines (incl. the
# 2017 degraded panel); end 2025-12-31 covers the latest hype window.
_START = "20160101"
_END = "20251231"

_PV_API = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"
_UA = (
    "bdor-research/0.1 (Ballon d'Or hype-vs-merit analysis; "
    "contact: valter.antonio1996@gmail.com)"
)
_OUT_COLS = ["player", "lang", "date", "views"]

_BASE_DELAY = 0.1   # ~10 req/s base; Wikimedia REST 429s aggressive bursts
_MAX_RETRIES = 6    # exponential backoff absorbs transient 429/503

_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"User-Agent": _UA})
    return _session


# --- pure helpers (offline-testable) ----------------------------------------

def _encode_title(title: str) -> str:
    """Wikipedia title -> pageviews path segment (spaces->underscores, everything %-encoded)."""
    return quote(title.replace(" ", "_"), safe="")


def _aggregate_all_lang(per_lang: pd.DataFrame) -> pd.DataFrame:
    """Sum per-language daily views into one all-language series per (player, date)."""
    if per_lang.empty:
        return pd.DataFrame(columns=["player", "date", "views"])
    return (
        per_lang.groupby(["player", "date"], as_index=False)["views"].sum()
        .sort_values(["player", "date"])
        .reset_index(drop=True)
    )


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=_OUT_COLS)


# --- network ----------------------------------------------------------------

def _request(url: str) -> requests.Response | None:
    """GET with polite rate + backoff on 429/503. Returns None for 404 (no such article)."""
    for attempt in range(_MAX_RETRIES):
        time.sleep(_BASE_DELAY)
        resp = _get_session().get(url, timeout=30)
        if resp.status_code == 404:
            return None
        if resp.status_code in (429, 503):
            retry_after = resp.headers.get("Retry-After", "")
            wait = float(retry_after) if retry_after.isdigit() else 2.0**attempt
            time.sleep(min(wait, 60.0))
            continue
        resp.raise_for_status()
        return resp
    resp.raise_for_status()  # exhausted retries on a persistent 429/503 -> fail loudly
    return None


def _fetch_article(player: str, lang: str, title: str) -> pd.DataFrame:
    url = (
        f"{_PV_API}/{lang}.wikipedia/all-access/all-agents/"
        f"{_encode_title(title)}/daily/{_START}/{_END}"
    )
    resp = _request(url)
    if resp is None:
        return _empty()
    items = resp.json().get("items", [])
    if not items:
        return _empty()
    df = pd.DataFrame(items)
    df["player"] = player
    df["lang"] = lang
    df["date"] = pd.to_datetime(df["timestamp"].str[:8], format="%Y%m%d")
    return df[_OUT_COLS]


def _fetch_player(player: str, *, sitelinks: dict[str, list[tuple[str, str]]]) -> pd.DataFrame:
    """Fetch all language editions for one player -> [player, lang, date, views]."""
    frames = [_fetch_article(player, lang, title) for lang, title in sitelinks.get(player, [])]
    frames = [f for f in frames if not f.empty]
    return pd.concat(frames, ignore_index=True) if frames else _empty()


def _build_all_lang(players: list[str] | None) -> pd.DataFrame:
    sl = wikidata.pull(players)
    sl = sl[sl["kind"] == "sitelink"]
    sitelinks = {
        p: list(zip(g["key"], g["value"], strict=False)) for p, g in sl.groupby("player")
    }
    universe = sorted(sitelinks)
    per_lang = cached_records(
        BY_LANG_CACHE, universe, partial(_fetch_player, sitelinks=sitelinks)
    )
    return _aggregate_all_lang(per_lang)


def pull(players: list[str] | None = None, *, refresh: bool = False) -> pd.DataFrame:
    """Return all-language daily pageviews per player (cached). Defaults to the awards universe."""
    return cached_frame(ALL_LANG_CACHE, lambda: _build_all_lang(players), refresh=refresh)
