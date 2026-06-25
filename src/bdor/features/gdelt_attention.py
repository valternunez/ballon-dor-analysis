"""Windowed GDELT news-volume attention — the input to the second-proxy H⊥ regression.

The GDELT sibling of `attention.build` (pageviews). Same leakage-safe windowing via the generic
`hype._aggregate`, but de-faming **news volume** instead of search interest, so we can ask whether
the two-gate finding replicates under an independent attention signal.

**Pool-wide.** The GDELT pull (`data/gdelt_bq.build` → the shared `gdelt.VOLUME_CACHE`) now covers
the full candidate pool (`pool.pool_universe()`), the same universe pageviews reach — the BigQuery
path made the wider pull free (flat scan cost). So this frame, and the `h_perp_gd` it feeds
(`hperp.build_gdelt`), are a pool-wide refit: an independent like-for-like replication of the
pageview H⊥, not just a finisher check. See `docs/gdelt-resume.md` and the `hperp_frame` docstring.
"""

from __future__ import annotations

import pandas as pd

from ..cache import cached_frame
from ..data import gdelt
from ..windows import load_windows
from .hype import _aggregate

CACHE_NAME = "gdelt_attention_pool"


def _build_gdelt_attention() -> pd.DataFrame:
    daily = gdelt.pull()  # pool-wide daily volume from the shared cache; the pull is driven once
    return _aggregate(daily, load_windows(), value_col="volume", prefix="gd")


def build(*, refresh: bool = False) -> pd.DataFrame:
    """Return per-(player, award_year) GDELT news-volume attention (cached, pool-wide)."""
    return cached_frame(CACHE_NAME, _build_gdelt_attention, refresh=refresh)
