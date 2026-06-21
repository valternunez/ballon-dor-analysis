"""Shared posterior-summary helper for the outcome models (Stage A + Stage B).

arviz 1.x quirks live here in one place: `az.summary` uses `ci_prob`/`ci_kind` (columns
`hdi94_lb`/`hdi94_ub`) and returns *pretty-printed strings*, so we coerce to numeric and append
P(coef > 0) from the raw posterior draws.
"""

from __future__ import annotations

import pandas as pd


def coef_table(idata, var_names: list[str]) -> pd.DataFrame:
    """Tidy coefficient table: posterior mean, sd, 94% HDI, R̂, ESS, and P(coef > 0)."""
    import arviz as az  # noqa: PLC0415  (heavy; lazy so callers stay offline until they fit)

    table = az.summary(idata, var_names=var_names, ci_prob=0.94, ci_kind="hdi")
    table = table.apply(pd.to_numeric, errors="coerce")

    # P(coef > 0) keyed to az's row labels. A categorical term is ONE posterior variable with a
    # level dimension; az.summary expands it to "var[level]" rows, so build those keys to match.
    post = idata.posterior
    p_pos: dict[str, float] = {}
    for v in var_names:
        da = post[v]
        extra = [d for d in da.dims if d not in ("chain", "draw")]
        if not extra:
            p_pos[v] = float((da.values > 0).mean())
        else:
            for lvl in da[extra[0]].values:
                p_pos[f"{v}[{lvl}]"] = float((da.sel({extra[0]: lvl}).values > 0).mean())
    table["p_positive"] = [p_pos.get(idx, float("nan")) for idx in table.index]
    return table


def average_marginal_effect(
    formula: str, family: str, data, idata, focal: str = "h_perp_pv", shift: float = 1.0
) -> dict:
    """Average marginal effect (percentage points) of a +`shift`-SD change in `focal`.

    Predictors are pre-standardized, so `shift=1` is +1 SD. Rebuilds the bambi model (no refit) and
    uses the cached posterior to predict the mean response for the observed data vs a counterfactual
    with `focal` shifted, averages the per-observation difference, and summarizes across draws (94%
    interval). Gives the logit coefficients a human reading: "+1 SD Hype Score moves the probability
    by ~X pp." Returns mean/lo/hi in pp + the baseline mean (`base_pct`).
    """
    import bambi as bmb  # noqa: PLC0415  (heavy; lazy)
    import numpy as np  # noqa: PLC0415

    model = bmb.Model(formula, data, family=family)

    def _mu(frame) -> np.ndarray:
        post = model.predict(idata, data=frame, inplace=False, kind="response_params").posterior
        n = len(frame)
        var = next(v for v in post.data_vars
                   if any(post[v].sizes.get(d, 0) == n for d in post[v].dims))
        da = post[var]
        obs = next(d for d in da.dims if da.sizes[d] == n)
        return da.mean(dim=obs).to_numpy().ravel()

    base = _mu(data)
    cf = data.copy()
    cf[focal] = cf[focal] + shift
    diff = (_mu(cf) - base) * 100.0
    return {
        "mean": float(diff.mean()), "lo": float(np.percentile(diff, 3.0)),
        "hi": float(np.percentile(diff, 97.0)), "base_pct": float(base.mean() * 100.0),
    }
