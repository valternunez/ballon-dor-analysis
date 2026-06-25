"""GDELT news-volume pull via the **BigQuery** public GKG table (hype proxy #2, robust path).

The DOC 2.0 API IP-bans bursty callers (see `data/gdelt.py` + docs/gdelt-resume.md); the *same*
GDELT data lives in BigQuery's public `gdelt-bq.gdeltv2.gkg_partitioned`, which doesn't. We count,
per player per day, how many GKG documents name that player (`V2Persons`), 2017–2025.

**Strictly free**: run from a BigQuery **sandbox** project (no billing account → cannot be charged;
hard 1 TB/month cap). `dry_run()` estimates bytes for $0; `build()` refuses the real query if the
estimate exceeds the free tier (`_FREE_TIER_BYTES`) — at which point the fallback is MediaCloud.
Output is the SAME `[player, date, volume]` frame the DOC-API path produced, cached to the SAME
`gdelt.VOLUME_CACHE`, so the feature wiring (`features/gdelt_attention`, `hperp.build_gdelt`, the
`proxy_gdelt` spec) reads it unchanged. The metric is a daily article *count*, not the DOC API's
normalized %, but H⊥ log-transforms and de-fames it, so the scale washes out.

**Pool-wide.** The pull resolves over the full candidate pool (`pool.pool_universe()`, the same list
pageviews use), not just the ~128 finishers — so `h_perp_gd` is a pool-wide refit, a like-for-like
independent replication of the pageview H⊥, not a finisher-only check. Cost is flat: BigQuery bills
bytes *scanned* (`DATE`+`V2Persons` over the partitions), and the names CTE is a post-scan in-memory
join, so widening the name list from ~128 to ~657 scans the same bytes (`dry_run()` confirms).
"""

from __future__ import annotations

import logging

import pandas as pd
from unidecode import unidecode

from ..cache import cached_frame
from . import gdelt, wikidata

logger = logging.getLogger(__name__)

_TABLE = "gdelt-bq.gdeltv2.gkg_partitioned"
_START = "2017-01-01"
_END = "2026-01-01"  # exclusive upper bound (covers through 2025-12-31)
_FREE_TIER_BYTES = 1024**4  # 1 TiB/month BigQuery sandbox cap — the "free" gate
_OUT_COLS = ["player", "date", "volume"]


# --- pure helpers (offline-testable) ----------------------------------------

def _fold(name: str) -> str:
    """Accent-fold + lowercase + collapse whitespace — the join key for GKG person names.

    GKG person strings are diacritic-inconsistent ("Mbappé"/"Mbappe"); folding both sides (here, and
    in SQL via NORMALIZE+strip-combining-marks) makes the match robust. Same `unidecode` the rest of
    the project uses for name keys.
    """
    return " ".join(unidecode(str(name)).lower().split())


def _name_pairs(aliases: dict[str, list[str]]) -> list[tuple[str, str]]:
    """(folded_form, player) pairs: each player's full name + surname-sharing name-order variants.

    Reuses `gdelt._is_name_variant` so recall logic matches the DOC-API path. De-duplicated on the
    folded form within a player; an empty/degenerate fold is dropped.
    """
    pairs: list[tuple[str, str]] = []
    for player, alts in aliases.items():
        forms = {_fold(player)}
        for alt in alts:
            if alt != player and gdelt._is_name_variant(alt, player):
                forms.add(_fold(alt))
        for form in forms:
            if form:
                pairs.append((form, player))
    return sorted(set(pairs))


def _sql_literal(text: str) -> str:
    """Single-quoted SQL string literal with quotes escaped (names are trusted, but be correct)."""
    return "'" + str(text).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _build_sql(pairs: list[tuple[str, str]], *, start: str = _START, end: str = _END) -> str:
    """Build the GKG person-mention count query. Pure string → offline-testable.

    Scans only `DATE` + `V2Persons` over the 2017–2025 partitions (columnar → minimal bytes),
    explodes `V2Persons`, folds each person name like `_fold` (NORMALIZE NFD + strip combining marks
    + lower), and inner-joins to our names so only the ~128 players survive. One row per
    (player, day) with the document count as `volume`.
    """
    names = ",\n      ".join(
        f"STRUCT({_sql_literal(form)} AS form, {_sql_literal(player)} AS player)"
        for form, player in pairs
    )
    return f"""
    WITH names AS (
      SELECT * FROM UNNEST([
      {names}
      ])
    )
    SELECT
      n.player AS player,
      DATE(PARSE_TIMESTAMP('%Y%m%d%H%M%S', CAST(g.DATE AS STRING))) AS date,
      COUNT(*) AS volume
    FROM `{_TABLE}` AS g,
      UNNEST(SPLIT(g.V2Persons, ';')) AS person_raw
    JOIN names AS n
      ON REGEXP_REPLACE(NORMALIZE(LOWER(TRIM(SPLIT(person_raw, ',')[OFFSET(0)])), NFD), r'\\pM', '')
         = n.form
    WHERE g._PARTITIONTIME >= '{start}' AND g._PARTITIONTIME < '{end}'
      AND g.V2Persons IS NOT NULL AND g.V2Persons != ''
    GROUP BY player, date
    """


# --- BigQuery (live; lazy import so the helpers above stay offline) ----------

def _client():
    from google.cloud import bigquery  # noqa: PLC0415  (optional [gdelt-bq] extra)

    return bigquery.Client()


def _universe() -> list[str]:
    """The pull universe: the full candidate pool (finishers ∪ Tier-2), matching pageviews.

    Lazy import of `features.pool` to avoid a heavy import chain at load; this is the one knob that
    makes the proxy pool-wide rather than finisher-only.
    """
    from ..features import pool  # noqa: PLC0415

    return pool.pool_universe()


def _pairs() -> list[tuple[str, str]]:
    universe = _universe()
    wd = wikidata.pull(universe)  # resumable: only pool players not yet resolved are fetched
    aliases = {p: list(g.loc[g["kind"] == "alias", "value"]) for p, g in wd.groupby("player")}
    return _name_pairs({p: aliases.get(p, []) for p in universe})


def dry_run() -> int:
    """Estimate bytes the real query would scan (BigQuery dry-run — free, no scan). Prints TB."""
    from google.cloud import bigquery  # noqa: PLC0415

    sql = _build_sql(_pairs())
    cfg = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    job = _client().query(sql, job_config=cfg)
    n = int(job.total_bytes_processed)
    logger.info("gdelt_bq dry-run: %.3f TB (%d bytes); free tier = 1 TB", n / 1024**4, n)
    print(f"gdelt_bq dry-run: {n / 1024**4:.3f} TB would be scanned "
          f"({'within' if n <= _FREE_TIER_BYTES else 'OVER'} the free 1 TB tier)")
    return n


def _query() -> pd.DataFrame:
    n = dry_run()
    if n > _FREE_TIER_BYTES:
        raise RuntimeError(
            f"gdelt_bq: query would scan {n / 1024**4:.2f} TB > 1 TB free tier — not running. "
            "Fall back to MediaCloud (see docs/gdelt-resume.md / the plan)."
        )
    df = _client().query(_build_sql(_pairs())).to_dataframe()
    if df.empty:
        return pd.DataFrame(columns=_OUT_COLS)
    df["date"] = pd.to_datetime(df["date"])
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    return df.sort_values(["player", "date"])[_OUT_COLS].reset_index(drop=True)


def build(*, refresh: bool = False) -> pd.DataFrame:
    """Pull daily GKG mention counts per player and cache to `gdelt.VOLUME_CACHE` (free, gated).

    Writes the SAME `gdelt_volume_daily` cache the DOC-API path uses, so `features/gdelt_attention`
    and the `proxy_gdelt` robustness spec light up automatically. Raises if the dry-run exceeds the
    free tier (→ MediaCloud fallback).
    """
    return cached_frame(gdelt.VOLUME_CACHE, _query, refresh=refresh)
