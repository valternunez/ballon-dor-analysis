"""Cache-first data helpers — the heart of the reproducible data layer.

Every data pull in this project is slow, rate-limited, and idempotent (all-language
pageviews for ~100 players x 8 seasons, GDELT sweeps, match-level FBref logs). So we
run each pull *once*, cache the result as parquet, and never hit the network again
unless explicitly refreshed.

Two granularities:

* ``cached_frame``   — frame-level: one parquet per logical dataset. Use for small,
  single-shot pulls (e.g. the Ballon d'Or awards table).
* ``cached_records`` — row-level and *resumable*: one parquet shard per key, so a
  rate-limit crash mid-pull resumes instead of restarting. Use for per-entity pulls
  (per player-season pageviews / GDELT volume).

Rule of thumb: imported or re-run -> it's a module; slow to produce -> cache it here.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any

import pandas as pd
from tqdm import tqdm

from .config import CACHE_DIR

_SAFE_KEY = re.compile(r"[^A-Za-z0-9._-]+")


def _slug(value: Any) -> str:
    """Filesystem-safe slug for a cache key part."""
    return _SAFE_KEY.sub("_", str(value)).strip("_")


def cache_path(name: str, *, root: Path = CACHE_DIR, suffix: str = ".parquet") -> Path:
    """Resolve the on-disk path for a named cache entry."""
    return root / f"{_slug(name)}{suffix}"


def cached_frame(
    name: str,
    producer: Callable[[], pd.DataFrame],
    *,
    refresh: bool = False,
    root: Path = CACHE_DIR,
) -> pd.DataFrame:
    """Return a cached DataFrame, computing + caching it on first miss.

    Parameters
    ----------
    name : logical dataset name (becomes ``{name}.parquet`` under the cache root).
    producer : zero-arg callable that produces the DataFrame on a cache miss.
    refresh : if True, ignore any existing cache and recompute.
    """
    path = cache_path(name, root=root)
    if path.exists() and not refresh:
        return pd.read_parquet(path)

    df = producer()
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return df


def cached_records(
    name: str,
    keys: Sequence[Any] | Iterable[Any],
    fetch_one: Callable[[Any], pd.DataFrame],
    *,
    refresh: bool = False,
    root: Path = CACHE_DIR,
    progress: bool = True,
) -> pd.DataFrame:
    """Resumable per-key pull: fetch + cache each key separately, then concatenate.

    Each key gets its own parquet shard under ``{root}/{name}/{key}.parquet``. Only
    missing shards trigger a ``fetch_one`` call, so an interrupted pull (rate limit,
    crash) resumes from where it stopped on the next run.

    ``fetch_one`` should return a DataFrame for the single key (may be empty). The key
    is *not* added automatically — include any identifying columns in the returned frame.
    """
    keys = list(keys)
    shard_dir = root / _slug(name)
    shard_dir.mkdir(parents=True, exist_ok=True)

    iterator = tqdm(keys, desc=f"pull:{name}") if progress else keys
    frames: list[pd.DataFrame] = []
    for key in iterator:
        shard = shard_dir / f"{_slug(key)}.parquet"
        if shard.exists() and not refresh:
            frames.append(pd.read_parquet(shard))
            continue
        df = fetch_one(key)
        df.to_parquet(shard, index=False)
        frames.append(df)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)
