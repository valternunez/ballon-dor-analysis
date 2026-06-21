"""Robustness panel — is the H⊥ effect stable across specifications?

The headline H⊥ coefficients come from one specification each. For a small-N descriptive study,
PROJECT_NOTES (Conditional spec step 5) wants a **coefficient-stability panel**: re-fit the H⊥
effect under deliberately varied choices and show it doesn't wander. This module produces the
plot-ready data (the caterpillar figure itself lives in the Quarto writeup).

Engine = the **frequentist anchors** (statsmodels Beta for Stage B, Logit for Stage A): seconds per
cell, and already shown to track the Bayesian posteriors (Stage B +0.192 Bayes vs +0.195 freq). The
posteriors stay the headline; this shows the point estimate is stable.

Specs (per gate): baseline · no_duopoly · drop_low_baseline · window_leaky · jackknife_year.
`window_leaky` recomputes H⊥ with the hype window stretched to the ceremony date (the leakage we
designed against) — H⊥ should INFLATE, demonstrating that the shortlist cut matters.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..cache import cached_frame
from ..data import awards, pageviews
from ..features import _outcome as build_outcome
from ..features import build as build_features
from ..features import hperp, hype, pool
from ..windows import load_windows
from . import nomination, placement

CACHE_NAME = "robustness_panel"
_PANEL_COLS = ["gate", "spec", "estimate", "ci_low", "ci_high", "n"]
# The winner is revealed AT the ceremony, so the announcement pageview spike lands on/after it. To
# make the leaky window genuinely leak the outcome, extend past the ceremony to capture that spike
# (the shortlist date is ~50 days earlier — see decisions log).
_LEAK_BUFFER_DAYS = 21


# --- leaky-window H⊥ (the leakage-demonstration cell) -----------------------

def _leaky_windows() -> pd.DataFrame:
    """Award windows with the hype cut pushed PAST the ceremony, to include the result spike."""
    w = load_windows().copy()
    w["hype_cut"] = w["ceremony_date"] + pd.Timedelta(days=_LEAK_BUFFER_DAYS)
    return w


def _leaky_hperp() -> pd.DataFrame:
    """Recompute the H⊥ table with attention windowed to the (leaky) ceremony date."""
    daily = pageviews.pull(pool.pool_universe())
    att = hype._aggregate(daily, _leaky_windows(), value_col="views", prefix="pv")
    return hperp.hperp_frame(att)


def _model_features_from_hp(hp: pd.DataFrame) -> pd.DataFrame:
    """Stage-B model frame (outcome ⋈ an alternate H⊥ table), mirroring features.build.

    Used for any cell that recomputes H⊥ (leaky attention window, strict ceremony-capped merit).
    """
    out = build_outcome()
    out["player_key"] = out["player"].map(awards.name_key)
    return out.merge(
        hp.drop(columns=["player"]), on=["award_year", "player_key"], how="inner"
    )


# --- strict-window H⊥ (calendar perf window capped at the ceremony) ----------

def _strict_windows() -> pd.DataFrame:
    """Award windows with the calendar-year PERFORMANCE window capped at the ceremony date.

    Calendar regimes nominally run to Dec 31, ~4 weeks past the early-Dec ceremony; this drops that
    tail so the merit can't reflect even a single post-ceremony match. Season regimes are unchanged.
    """
    w = load_windows().copy()
    cal = w["regime"] == "calendar"
    w.loc[cal, "perf_end"] = w.loc[cal, ["perf_end", "ceremony_date"]].min(axis=1)
    return w


def _strict_hperp() -> pd.DataFrame:
    """Recompute the H⊥ table from a merit built on the ceremony-capped performance window."""
    from ..features import merit  # noqa: PLC0415  (avoid a heavy import at module load)

    strict_merit = merit._build_merit(windows=_strict_windows())
    return hperp.hperp_frame(merit_df=strict_merit)


# --- one cell = the H⊥ coefficient from a frequentist fit -------------------

def _b_cell(prep_df: pd.DataFrame) -> tuple[float, float, float, int]:
    """Stage-B H⊥ estimate + 95% CI + n from the statsmodels Beta anchor (NaNs if it fails)."""
    try:
        r = placement.betareg_anchor(prep_df).loc["h_perp_pv"]
        return float(r["estimate"]), float(r["ci_low"]), float(r["ci_high"]), len(prep_df)
    except Exception:  # noqa: BLE001  (a degenerate subset shouldn't kill the panel)
        return float("nan"), float("nan"), float("nan"), len(prep_df)


def _a_cell(prep_df: pd.DataFrame) -> tuple[float, float, float, int]:
    """Stage-A H⊥ estimate + 95% CI + n from the statsmodels Logit anchor (NaNs if it fails)."""
    try:
        r = nomination.logit_anchor(prep_df).loc["h_perp_pv"]
        return float(r["estimate"]), float(r["ci_low"]), float(r["ci_high"]), len(prep_df)
    except Exception:  # noqa: BLE001
        return float("nan"), float("nan"), float("nan"), len(prep_df)


def _jackknife(gate: str, prep: pd.DataFrame, cell_fn) -> dict:
    """Leave-one-award-year-out: median estimate, with [min, max] as the spread envelope."""
    ests = []
    for year in sorted(prep["award_year"].unique()):
        est, _, _, _ = cell_fn(prep[prep["award_year"] != year])
        if not np.isnan(est):
            ests.append(est)
    arr = np.array(ests, dtype=float)
    return {
        "gate": gate, "spec": "jackknife_year",
        "estimate": float(np.median(arr)) if len(arr) else float("nan"),
        "ci_low": float(arr.min()) if len(arr) else float("nan"),
        "ci_high": float(arr.max()) if len(arr) else float("nan"),
        "n": len(prep),
    }


# --- generated-regressor bootstrap (H⊥ is a first-stage residual) -----------

_BOOTSTRAP_N = 400
_BOOTSTRAP_SEED = 20260621


def _bootstrap_rows() -> list[dict]:
    """Propagate the H⊥-estimation uncertainty the naive anchor CIs ignore.

    H⊥ is the residual of a first-stage de-fame OLS, then used as a predictor in the gate models, so
    the naive gate CIs are optimistic (a generated-regressor problem). Each iteration captures BOTH
    sources: (1) refit the de-fame OLS on a resampled fit set → new betas → recompute H⊥; then
    (2) **case-resample the gate sample** and refit the frequentist anchor on it. The percentile CI
    therefore includes both the first-stage error and the usual gate-sampling error (so it is ≥ the
    naive CI, not narrower). Returns one row per gate: the bootstrap median + percentile CI.
    """
    rng = np.random.default_rng(_BOOTSTRAP_SEED)
    cand = hperp.hperp_frame().copy()
    xcols = hperp._REGRESSORS
    fit = cand["h_perp_pv"].notna()
    y_fit = cand.loc[fit, "log_window"].to_numpy(float)
    x_fit = np.column_stack([np.ones(int(fit.sum())), cand.loc[fit, xcols].to_numpy(float)])
    allm = cand["log_window"].notna() & cand[xcols].notna().all(axis=1)
    x_all = np.column_stack([np.ones(int(allm.sum())), cand.loc[allm, xcols].to_numpy(float)])
    logw_all = cand.loc[allm, "log_window"].to_numpy(float)

    def _resample(df: pd.DataFrame) -> pd.DataFrame:
        return df.iloc[rng.integers(0, len(df), len(df))]

    a_est: list[float] = []
    b_est: list[float] = []
    for _ in range(_BOOTSTRAP_N):
        ridx = rng.integers(0, len(y_fit), len(y_fit))
        beta, _res, _rk, _sv = np.linalg.lstsq(x_fit[ridx], y_fit[ridx], rcond=None)
        boot = cand.copy()
        boot["h_perp_pv"] = np.nan
        boot.loc[allm, "h_perp_pv"] = logw_all - x_all @ beta
        try:  # gate sample is case-resampled too → captures gate-sampling + first-stage error
            a_est.append(float(nomination.logit_anchor(
                _resample(nomination._prep_hperp(hperp_df=boot))).loc["h_perp_pv", "estimate"]))
        except Exception:  # noqa: BLE001  (a degenerate resample shouldn't kill the bootstrap)
            pass
        try:
            b_prep = _resample(placement._prep(_model_features_from_hp(boot)))
            b_est.append(float(placement.betareg_anchor(b_prep).loc["h_perp_pv", "estimate"]))
        except Exception:  # noqa: BLE001
            pass

    def _boot_row(gate: str, ests: list[float]) -> dict:
        arr = np.array(ests, dtype=float)
        if not len(arr):
            return {"gate": gate, "spec": "bootstrap_hperp", "estimate": float("nan"),
                    "ci_low": float("nan"), "ci_high": float("nan"), "n": 0}
        lo, hi = np.nanpercentile(arr, [2.5, 97.5])  # median estimate keeps it inside its own CI
        return {"gate": gate, "spec": "bootstrap_hperp", "estimate": float(np.nanmedian(arr)),
                "ci_low": float(lo), "ci_high": float(hi), "n": len(arr)}

    return [_boot_row("A_nomination", a_est), _boot_row("B_placement", b_est)]


# --- Heckman selection sensitivity (Stage B) --------------------------------

def _heckman_row() -> dict:
    """Stage-B H⊥ under a Heckman selection control (inverse Mills ratio). Sensitivity only."""
    try:
        e, lo, hi, n = placement.heckman_check()
        return {"gate": "B_placement", "spec": "heckman", "estimate": e,
                "ci_low": lo, "ci_high": hi, "n": n}
    except Exception:  # noqa: BLE001
        return {"gate": "B_placement", "spec": "heckman", "estimate": float("nan"),
                "ci_low": float("nan"), "ci_high": float("nan"), "n": 0}


# --- panel ------------------------------------------------------------------

def _row(gate: str, spec: str, cell: tuple) -> dict:
    e, lo, hi, n = cell
    return {"gate": gate, "spec": spec, "estimate": e, "ci_low": lo, "ci_high": hi, "n": n}


def _build_panel() -> pd.DataFrame:
    # Standardize on the full frame, then filter rows per spec (keeps the per-SD scale comparable).
    bp = placement._prep(build_features())
    ap = nomination._prep_hperp()
    leaky = _leaky_hperp()
    strict = _strict_hperp()

    b_specs = {
        "baseline": bp,
        "no_duopoly": bp[~bp["is_duopoly"]],
        "drop_low_baseline": bp[~bp["pv_low_baseline"].fillna(False)],
        "window_leaky": placement._prep(_model_features_from_hp(leaky)),
        "window_strict": placement._prep(_model_features_from_hp(strict)),
    }
    a_specs = {
        "baseline": ap,
        "no_duopoly": ap[~ap["is_duopoly"]],
        "drop_low_baseline": ap[~ap["pv_low_baseline"]],
        "window_leaky": nomination._prep_hperp(hperp_df=leaky),
        "window_strict": nomination._prep_hperp(hperp_df=strict),
    }

    rows = [_row("B_placement", s, _b_cell(df)) for s, df in b_specs.items()]
    rows += [_row("A_nomination", s, _a_cell(df)) for s, df in a_specs.items()]
    rows.append(_jackknife("B_placement", bp, _b_cell))
    rows.append(_jackknife("A_nomination", ap, _a_cell))
    rows += _bootstrap_rows()
    rows.append(_heckman_row())
    return pd.DataFrame(rows, columns=_PANEL_COLS)


def build(*, refresh: bool = False) -> pd.DataFrame:
    """Build (and cache) the H⊥ coefficient-stability panel, and print a compact summary."""
    panel = cached_frame(CACHE_NAME, _build_panel, refresh=refresh)
    print("\nRobustness panel - H_perp coefficient across specifications (frequentist anchors):\n")
    for gate, g in panel.groupby("gate"):
        print(f"  {gate}:")
        for r in g.itertuples():
            print(
                f"    {r.spec:<18} est={r.estimate:+.3f}  "
                f"95% CI/spread=[{r.ci_low:+.3f}, {r.ci_high:+.3f}]  n={r.n}"
            )
    return panel
