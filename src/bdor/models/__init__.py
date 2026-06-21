"""Outcome models — the funnel's two gates.

* **Stage A (nomination)** — a Bayesian logistic over the Tier-2 candidate pool: who makes the 30?
  Preliminary / H⊥-free (the attention term awaits a pool-wide pageview pull).
* **Stage B (placement)** — a Bayesian Beta regression of vote share among finishers, whose headline
  is the **posterior of the H⊥ coefficient** (the project's thesis in one number).

`run()` is the orchestration entry point used by `run.py models`; it fits and reports both gates.
"""

from __future__ import annotations

import pandas as pd

from . import nomination, placement


def _fmt_hperp(table: pd.DataFrame, label: str) -> str:
    """One-line headline for the H⊥ row of a coefficient table."""
    r = table.loc["h_perp_pv"]
    lo, hi = r["hdi94_lb"], r["hdi94_ub"]
    return (
        f"  [{label}] H_perp: mean={r['mean']:+.3f}  94% HDI=[{lo:+.3f}, {hi:+.3f}]  "
        f"P(H_perp>0)={r['p_positive']:.2f}"
    )


def _run_nomination(*, refresh: bool) -> pd.DataFrame:
    """Stage A: baseline (all positions) + H⊥ model (attackers). Print both, return the H⊥ table."""
    baseline = nomination.summary(nomination.fit(refresh=refresh))
    print("\nStage A - nomination BASELINE (all positions, no H_perp):\n")
    print(baseline.to_string())
    try:
        print(f"\n  [discrimination] year-grouped CV ROC-AUC = {nomination.discrimination():.3f}")
    except Exception as exc:  # noqa: BLE001
        print(f"\n  [discrimination] skipped ({type(exc).__name__}: {exc})")

    hperp_tbl = nomination.summary(nomination.fit_hperp(refresh=refresh))
    print("\nStage A + H_perp (attackers only) - does narrative get you NOTICED?\n")
    print(hperp_tbl.to_string())
    r = hperp_tbl.loc["h_perp_pv"]
    print(
        f"\n  Headline (Gate A) H_perp: mean={r['mean']:+.3f}  "
        f"94% HDI=[{r['hdi94_lb']:+.3f}, {r['hdi94_ub']:+.3f}]  P(H_perp>0)={r['p_positive']:.2f}"
    )
    return hperp_tbl


def _run_placement(*, refresh: bool) -> pd.DataFrame:
    """Stage B: fit (full + no-duopoly), print the H⊥ headline + anchor, return the summary."""
    full = placement.summary(placement.fit(refresh=refresh))
    noduo = placement.summary(placement.fit(refresh=refresh, drop_duopoly=True))

    print("\nStage B - placement (Beta regression, vote share):\n")
    print(full.to_string())
    print("\nHeadline - does narrative beyond merit move you up the vote?")
    print(_fmt_hperp(full, "full   "))
    print(_fmt_hperp(noduo, "no-duo "))

    try:
        a = placement.betareg_anchor().loc["h_perp_pv"]
        print(
            f"\n  [anchor] statsmodels Beta (no year RE) H_perp: "
            f"est={a['estimate']:+.3f}  95% CI=[{a['ci_low']:+.3f}, {a['ci_high']:+.3f}]  "
            f"p={a['pvalue']:.3f}"
        )
    except Exception as exc:  # noqa: BLE001
        print(f"\n  [anchor] skipped ({type(exc).__name__}: {exc})")
    return full


def run(*, refresh: bool = False) -> pd.DataFrame:
    """Fit + report both funnel gates; return the Stage-B summary (the project's headline)."""
    _run_nomination(refresh=refresh)
    return _run_placement(refresh=refresh)
