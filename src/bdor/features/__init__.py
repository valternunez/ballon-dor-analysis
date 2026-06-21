"""Feature builders — turn the cached raw pulls into model inputs.

`build()` assembles the **model-ready feature table**: the Ballon d'Or outcome (rank, points,
vote_share) joined to merit + pageview attention + team-success + H⊥, per (player, award_year).
This is the dataset the Stage-A/Stage-B outcome models consume.
"""

from __future__ import annotations

import pandas as pd

from ..cache import cached_frame
from ..data import awards
from . import hperp, merit  # noqa: F401  (merit re-exported for direct use)

MODEL_CACHE = "model_features"


def _outcome() -> pd.DataFrame:
    """Per (player, award_year): rank, points, and vote_share (= points / year total)."""
    aw = awards.pull()[["award_year", "player", "rank", "points"]].copy()
    aw["points"] = pd.to_numeric(aw["points"], errors="coerce")
    year_total = aw.groupby("award_year")["points"].transform("sum")
    aw["vote_share"] = aw["points"] / year_total
    return aw


def _build_model_features() -> pd.DataFrame:
    outcome = _outcome()
    feats = hperp.build()  # team-success + attention + merit + h_perp_pv (+ player_key)
    # Both carry the Wikipedia spelling here, but join on the canonical key for safety/consistency.
    outcome["player_key"] = outcome["player"].map(awards.name_key)
    return outcome.merge(
        feats.drop(columns=["player"]), on=["award_year", "player_key"], how="inner"
    ).sort_values(["award_year", "rank"]).reset_index(drop=True)


def build(*, refresh: bool = False) -> pd.DataFrame:
    """Build (and cache) the model-ready feature table."""
    return cached_frame(MODEL_CACHE, _build_model_features, refresh=refresh)
