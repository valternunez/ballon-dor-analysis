"""Wikidata resolver — QID + all-language sitelinks + name aliases per player.

The bridge from a player name to their Wikipedia article title in EVERY language edition
(so pageviews can sum across all languages — the locked all-language decision) and to name
aliases (reused by GDELT later).

Flow per player name:
  1. wbsearchentities -> candidate QIDs (names are ambiguous: "Lionel Messi" returns the
     footballer Q615, a book, and a tax trial).
  2. wbgetentities on the candidates -> pick the one whose occupation (P106) is association
     football player (Q937857); fallback to a candidate whose search description mentions
     football/soccer; else mark unresolved.
  3. Emit a tidy long frame: rows (player, qid, kind, key, value) with kind in {sitelink, alias}.
     sitelink rows: key=lang, value=article title. alias rows: key=lang, value=alias text.

Cached per player via cached_records (resumable). Pure helpers are offline-testable.
"""

from __future__ import annotations

import re
import time

import pandas as pd
import requests

from ..cache import cached_records

CACHE_NAME = "wikidata_entities"
COLUMNS = ["player", "qid", "kind", "key", "value"]

_WD_API = "https://www.wikidata.org/w/api.php"
_UA = (
    "bdor-research/0.1 (Ballon d'Or hype-vs-merit analysis; "
    "contact: valter.antonio1996@gmail.com)"
)
_FOOTBALLER_QID = "Q937857"  # occupation: association football player

# Sitelink keys that match the language-wiki regex but are NOT language Wikipedias.
_NON_LANGUAGE_WIKIS = {
    "commonswiki", "specieswiki", "metawiki", "wikidatawiki", "sourceswiki",
    "mediawikiwiki", "incubatorwiki", "wikimaniawiki", "foundationwiki",
    "outreachwiki", "betawikiversity",
}
_LANG_WIKI_RE = re.compile(r"^[a-z][a-z0-9_-]*wiki$")

_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"User-Agent": _UA})
    return _session


# --- pure helpers (offline-testable) ----------------------------------------

def _is_language_wiki(sitelink_key: str) -> bool:
    return bool(_LANG_WIKI_RE.match(sitelink_key)) and sitelink_key not in _NON_LANGUAGE_WIKIS


def _wiki_to_lang(sitelink_key: str) -> str:
    """'enwiki' -> 'en' (the lang code; pageviews builds '<lang>.wikipedia')."""
    return sitelink_key[:-4]


def _occupations(entity: dict) -> list[str]:
    out = []
    for stmt in entity.get("claims", {}).get("P106", []):
        try:
            out.append(stmt["mainsnak"]["datavalue"]["value"]["id"])
        except (KeyError, TypeError):
            continue
    return out


def _pick_footballer(entities: dict, order: list[str], descriptions: dict[str, str]) -> str | None:
    """Choose the footballer QID: by P106, else by a football/soccer description, else None."""
    footballers = [
        q for q in order if q in entities and _FOOTBALLER_QID in _occupations(entities[q])
    ]
    if footballers:
        return max(footballers, key=lambda q: len(entities[q].get("sitelinks", {})))
    for q in order:
        desc = descriptions.get(q, "").lower()
        if "football" in desc or "soccer" in desc:
            return q
    return None


def _extract_rows(player: str, qid: str, entity: dict) -> pd.DataFrame:
    rows: list[tuple] = []
    for key, link in entity.get("sitelinks", {}).items():
        if _is_language_wiki(key):
            rows.append((player, qid, "sitelink", _wiki_to_lang(key), link["title"]))
    seen: set[str] = set()
    for lang, alts in entity.get("aliases", {}).items():
        for alt in alts:
            val = alt.get("value")
            if val and val not in seen:
                seen.add(val)
                rows.append((player, qid, "alias", lang, val))
    if not rows:
        return _unresolved(player)
    return pd.DataFrame(rows, columns=COLUMNS)


def _unresolved(player: str) -> pd.DataFrame:
    return pd.DataFrame([[player, pd.NA, "unresolved", pd.NA, pd.NA]], columns=COLUMNS)


# --- network ----------------------------------------------------------------

def _search(name: str, session: requests.Session) -> list[dict]:
    resp = session.get(
        _WD_API,
        params={
            "action": "wbsearchentities", "search": name, "language": "en",
            "uselang": "en", "format": "json", "type": "item", "limit": 7,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("search", [])


def _get_entities(qids: list[str], session: requests.Session) -> dict:
    resp = session.get(
        _WD_API,
        params={
            "action": "wbgetentities", "ids": "|".join(qids),
            "props": "claims|sitelinks|aliases|labels", "format": "json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("entities", {})


def _resolve_one(name: str) -> pd.DataFrame:
    session = _get_session()
    time.sleep(0.05)  # polite
    results = _search(name, session)
    if not results:
        return _unresolved(name)
    order = [r["id"] for r in results]
    descriptions = {r["id"]: r.get("description", "") for r in results}
    entities = _get_entities(order, session)
    qid = _pick_footballer(entities, order, descriptions)
    if qid is None or qid not in entities:
        return _unresolved(name)
    return _extract_rows(name, qid, entities[qid])


def award_universe() -> list[str]:
    """Unique player names from the Ballon d'Or finishers (default resolution universe)."""
    from .awards import pull as awards_pull

    players = awards_pull()["player"].dropna().unique().tolist()
    return sorted(players)


def pull(players: list[str] | None = None, *, refresh: bool = False) -> pd.DataFrame:
    """Return sitelinks + aliases per player (cached, resumable). Defaults to awards universe."""
    if players is None:
        players = award_universe()
    return cached_records(CACHE_NAME, players, _resolve_one, refresh=refresh)
