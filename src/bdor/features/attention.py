"""Pool-wide windowed attention — the inputs to the pool H⊥ regression.

Same recipe as the finisher-only `hype.build_pageview_attention`, but over the **whole candidate
universe** (`pool.pool_universe()` = finishers ∪ Tier-2 pool). This is what lets H⊥ ("attention
beyond merit") be estimated across all candidates, so Stage A can test the attention question at the
nomination gate — not just Stage B at placement.

Thin by design: the heavy lifting (the all-language daily pageviews pull, the leakage-safe
windowing) already exists — we just point the generic aggregator at the pool universe.
"""

from __future__ import annotations

import pandas as pd

from ..cache import cached_frame
from ..data import pageviews
from ..windows import load_windows
from . import pool
from .hype import _aggregate

CACHE_NAME = "pageview_attention_pool"


def _build_pool_attention() -> pd.DataFrame:
    universe = pool.pool_universe()
    daily = pageviews.pull(universe)  # cached superset (the pull is driven separately/once)
    return _aggregate(daily, load_windows(), value_col="views", prefix="pv")


def build(*, refresh: bool = False) -> pd.DataFrame:
    """Return per-(player, award_year) pageview attention for the whole pool universe (cached)."""
    return cached_frame(CACHE_NAME, _build_pool_attention, refresh=refresh)
