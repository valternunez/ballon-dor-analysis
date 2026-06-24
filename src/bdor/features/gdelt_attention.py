"""Windowed GDELT news-volume attention — the input to the second-proxy H⊥ regression.

The GDELT sibling of `attention.build` (pageviews). Same leakage-safe windowing via the generic
`hype._aggregate`, but de-faming **news volume** instead of search interest, so we can ask whether
the two-gate finding replicates under an independent attention signal.

**Finisher-level by construction.** The GDELT pull (`data/gdelt.pull`) covers only the award
universe (~128 finishers), not the pool-wide ~558 that pageviews reach — disambiguated per-player
news queries are expensive and rate-limited. So this frame, and the `h_perp_gd` it feeds
(`hperp.build_gdelt`), are a finisher-fit robustness check, not a pool-wide refit. See
`docs/gdelt-resume.md` and the `hperp_frame` docstring.
"""

from __future__ import annotations

import pandas as pd

from ..cache import cached_frame
from ..data import gdelt
from ..windows import load_windows
from .hype import _aggregate

CACHE_NAME = "gdelt_attention_pool"


def _build_gdelt_attention() -> pd.DataFrame:
    daily = gdelt.pull()  # award-universe daily volume; the pull is driven separately/once
    return _aggregate(daily, load_windows(), value_col="volume", prefix="gd")


def build(*, refresh: bool = False) -> pd.DataFrame:
    """Return per-(player, award_year) GDELT news-volume attention (cached, award universe)."""
    return cached_frame(CACHE_NAME, _build_gdelt_attention, refresh=refresh)
