"""H⊥ — attention beyond merit (the project's central quantity).

A SINGLE de-fame regression (PROJECT_NOTES "H⊥ — LOCKED"):
    log(window attention) ~ log(baseline) + merit + team-success   ->  residual = H⊥.
log(baseline) absorbs fame; merit absorbs performance-driven attention; team-success absorbs the
CL confound. The leftover residual = narrative excess.

**Fit pool-wide.** The regression is estimated over the whole candidate universe (Tier-2 pool ∪
finishers) so the fame→attention relationship isn't read off the selected finishers alone, and so H⊥
is defined for every candidate — letting Stage A test the attention question at the nomination gate,
not just Stage B at placement. Merit is now FOUR-dimensional (attacking PCA axes + MF ball-winning +
CB efficiency + GK shot-stopping); each candidate is de-famed against the role(s) they play, so
H⊥ now covers **everyone with any merit** — attackers, deep mids, CBs, AND keepers (the latter
two gaining an H⊥ for the first time). "Attention beyond *merit*"; undefined only where no merit
metric exists. The residual is computed for every such candidate, finisher or not.

`tournament_result` is NOT a de-fame regressor here: player→nation exists only for finishers, so it
would residualize inconsistently across the pool (same guard as Stage A). It is carried as a
passthrough column for Stage B (a valid placement regressor among finishers). Fit via numpy OLS.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..cache import cached_frame
from ..data import awards
from . import attention, club_importance, merit, pool, team_success

CACHE_NAME = "hperp_pageviews"
GDELT_CACHE_NAME = "hperp_gdelt"

# De-fame regressors (besides the intercept): fame + merit (all four role dims) + club success +
# club-importance (v3).
#  * merit_pc1/pc2 — attacking merit (orthogonal PCA axes). NO merit_z (collinear with merit_pc1).
#  * def_merit_z   — MF ball-winning; cb_def_z — CB efficiency+ball-playing; gk_merit_z — GK
#    shot-stopping. Each is 0 where it doesn't apply. Folding in all four de-fames a destroyer
#    (Kanté/Jorginho), a CB (Van Dijk), and a keeper against their OWN merit so their attention
#    isn't misread as narrative excess — and it gives defenders & keepers an H⊥ for the first time.
#  * NO tournament_result (finisher-only nation → inconsistent across the pool).
#  * minutes_share/xg_share — club-importance (v3, option (b)): graded per-player team-centrality
#    the blunt binary trophy flags miss (every City player shares won_league; only Rodri has the
#    minutes_share). 0 where unmeasured (non-top-5). De-faming against them means H⊥ is "attention
#    beyond merit AND how central the player was to his club" — a sharper team-context control.
_REGRESSORS = [
    "log_baseline",
    "merit_pc1",
    "merit_pc2",
    "def_merit_z",
    "cb_def_z",
    "gk_merit_z",
    "cl_round",
    "won_cl",
    "won_league",
    "minutes_share",
    "xg_share",
]
# Real merit dimensions (any one present => H⊥ is defined for the player; the others fill 0).
_MERIT_DIMS = ["merit_pc1", "merit_pc2", "def_merit_z", "cb_def_z", "gk_merit_z"]
_MERIT_PRESENT = ["merit_pc1", "def_merit_z", "cb_def_z", "gk_merit_z"]


def _ols_residual(y: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """OLS via least squares (x already includes an intercept column).

    Returns (residuals, coefficients, R²). Pure / offline-testable.
    """
    beta, _, _, _ = np.linalg.lstsq(x, y, rcond=None)
    fitted = x @ beta
    resid = y - fitted
    ss_res = float((resid**2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return resid, beta, r2


def _candidate_frame(
    att: pd.DataFrame | None = None, merit_df: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Per (player, award_year) over pool ∪ finishers: merit + club team-success + attention.

    `att` defaults to the cached pool attention; the robustness panel passes an alternate (e.g.
    leaky-window) attention frame to recompute H⊥ under a different windowing. `merit_df` likewise
    defaults to the cached merit; the strict-window robustness cell injects a merit recomputed on a
    ceremony-capped performance window.

    Joined on the canonical name key (`awards.name_key`) — never the raw player string, which
    differs across Understat and Wikipedia and silently drops mismatched players (decisions log).
    """
    mer = (merit.build() if merit_df is None else merit_df).copy()
    ts = team_success.build().copy()
    pl = pool.build().copy()
    att = (attention.build() if att is None else att).copy()
    for d in (mer, ts, pl, att):
        d["player_key"] = d["player"].map(awards.name_key)

    club_cols = ["player", "player_key", "award_year", "cl_round", "won_cl", "won_league"]
    keys = pd.concat([pl[club_cols], ts[club_cols]], ignore_index=True).drop_duplicates(
        ["player_key", "award_year"], keep="first"
    )
    # tournament_result is finisher-only (passthrough for Stage B), joined separately so a finisher
    # who is also a pool member doesn't lose it to the pool row.
    base = keys.merge(
        ts[["player_key", "award_year", "tournament_result"]],
        on=["player_key", "award_year"], how="left",
    ).merge(
        mer[["player_key", "award_year", "merit_z", "merit_pc1", "merit_pc2", "def_merit_z",
             "cb_def_z", "gk_merit_z", "position_family", "minutes"]],
        on=["player_key", "award_year"], how="left",
    )
    base = base.merge(
        club_importance.build()[["player_key", "award_year", "minutes_share", "xg_share"]],
        on=["player_key", "award_year"], how="left",
    )
    for c in ("minutes_share", "xg_share"):  # 0 = unmeasured (non-top-5), like the merit dims
        base[c] = base[c].astype(float).fillna(0.0)
    return base.merge(att.drop(columns=["player"]), on=["player_key", "award_year"], how="inner")


def hperp_frame(
    att: pd.DataFrame | None = None,
    merit_df: pd.DataFrame | None = None,
    *,
    prefix: str = "pv",
    regressors: list[str] | None = None,
) -> pd.DataFrame:
    """Compute the H⊥ table (UNCACHED) for a given attention frame. Powers the robustness panel.

    `att=None` reproduces the cached default (`build()`); pass an alternate attention (e.g. a leaky
    ceremony-window aggregate) to re-estimate H⊥ under that windowing. `merit_df` injects an
    alternate merit table (e.g. the strict ceremony-capped performance window).

    `prefix` selects which attention signal to de-fame. `"pv"` (the default: Wikipedia pageviews,
    the primary proxy, fit pool-wide) reads `pv_baseline`/`pv_window_mean` → writes `h_perp_pv`.
    `"gd"` (GDELT news volume; see `gdelt_attention`) reads `gd_*` → writes `h_perp_gd`. GDELT is
    now pulled pool-wide too (the BigQuery path made the wider pull free), so `h_perp_gd` is a
    pool-wide second-proxy refit — an independent replication of `h_perp_pv`, not just finishers.

    `regressors` overrides the de-fame regressor set (default `_REGRESSORS`); the robustness panel
    passes the pre-v3 set (no club-importance) to show H⊥ is stable with/without that control.
    """
    regs = list(_REGRESSORS if regressors is None else regressors)
    df = _candidate_frame(att, merit_df)

    df["won_cl"] = df["won_cl"].astype(float)
    df["won_league"] = df["won_league"].astype(float)
    df["log_baseline"] = np.log1p(df[f"{prefix}_baseline"].astype(float))
    df["log_window"] = np.log1p(df[f"{prefix}_window_mean"].astype(float))

    # Each player is de-famed against the merit dimension(s) they have; a role they don't play fills
    # 0 (= "no signal"), which lets CBs/keepers/mids — NA on the attacking PCA axes — survive the
    # complete-case fit and each get an H⊥. We still require ≥1 real merit dim (else "attention
    # beyond merit" is undefined).
    for col in _MERIT_DIMS:
        df[col] = df[col].astype(float)
    has_merit = df[_MERIT_PRESENT].notna().any(axis=1)
    for col in _MERIT_DIMS:
        df[col] = df[col].fillna(0.0)

    out_col = f"h_perp_{prefix}"
    df[out_col] = np.nan
    complete = df[has_merit].dropna(subset=["log_window", *regs])
    if len(complete) > len(regs) + 1:
        y = complete["log_window"].to_numpy(dtype=float)
        x = np.column_stack(
            [np.ones(len(complete)), complete[regs].to_numpy(dtype=float)]
        )
        resid, beta, r2 = _ols_residual(y, x)
        df.loc[complete.index, out_col] = resid
        hperp_frame.last_fit = {
            "n": len(complete),
            "r2": round(r2, 3),
            "coefs": dict(zip(["const", *regs], beta.round(3), strict=True)),
        }
    return df.sort_values(["award_year", out_col], ascending=[True, False]).reset_index(
        drop=True
    )


def build(*, refresh: bool = False) -> pd.DataFrame:
    """Return per-(player, award_year) features + pool-fit H⊥ residual (cached)."""
    return cached_frame(CACHE_NAME, hperp_frame, refresh=refresh)


def build_gdelt(*, refresh: bool = False) -> pd.DataFrame:
    """Return the pool-wide GDELT second-proxy H⊥ (`h_perp_gd`), cached.

    A robustness sibling of `build()`: same de-fame regression, but de-faming GDELT news volume
    (`gdelt_attention`) instead of pageviews. GDELT is now pulled pool-wide (the same universe as
    pageviews), so this is an independent pool-wide replication of `h_perp_pv` (see `hperp_frame`).
    """
    from . import gdelt_attention

    def _producer() -> pd.DataFrame:
        return hperp_frame(att=gdelt_attention.build(), prefix="gd")

    return cached_frame(GDELT_CACHE_NAME, _producer, refresh=refresh)
