"""Stage A — nomination model: who makes the Ballon d'Or 30, among the candidate pool?

The funnel's first gate (PROJECT_NOTES "nomination→placement funnel"). A Bayesian logistic
(Bernoulli) over the Tier-2 pool:

    nominated ~ merit_z + C(position_family) + cl_round + won_cl + won_league + (1 | award_year)

**Preliminary / H-perp-free.** The thesis question at this gate (does attention get you noticed
beyond your stats?) needs H-perp for the non-nominees, which awaits a pool-wide pageview pull. This
version is the **merit + team-success baseline**: it validates that the pool is well-specified
(obvious-merit and deep-team players are likelier to be shortlisted) and sets up the H-perp add.

Modelling notes:
  * `tournament_result` is deliberately OMITTED — player-nation exists only for the 128 finishers,
    so a nonzero value would mark only nominees (a backdoor label / leakage). It returns with the
    pool nation extension.
  * `merit_z` is NaN for non-attackers and below-floor players; filled to 0 ("no individual merit
    signal"), with the `position_family` dummy absorbing the family-level base-rate shift.
  * No explicit class weighting — the Bernoulli models the true ~1:7 base rate; the merit/team pool
    curation is the imbalance control. A frequentist GroupKFold ROC-AUC reports discrimination.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..cache import cache_path
from ..data import awards
from ..features import hperp
from ..features import pool as pool_feat

# tournament_result is back in (it was dropped as finisher-only -> leakage): the StatsBomb pool maps
# nation -> tournament_result for many NON-finishers too, so a nonzero value no longer implies
# "nominee". See decisions log.
_CONTINUOUS = ["merit_z", "cl_round", "tournament_result"]
_FORMULA = (
    "nominated ~ merit_z + cl_round + won_cl + won_league + tournament_result "
    "+ C(position_family) + (1|award_year)"
)
# Stage A + H⊥ (attacker-only): the thesis test at the nomination gate. No position dummy (attackers
# only, since H⊥ is defined only where merit is). The h_perp_pv coefficient is the headline.
_CONTINUOUS_HPERP = ["merit_z", "h_perp_pv", "cl_round", "tournament_result"]
_FORMULA_HPERP = (
    "nominated ~ merit_z + h_perp_pv + cl_round + won_cl + won_league + tournament_result "
    "+ (1|award_year)"
)
_SEED = 20260619


# --- pure helpers (offline-testable) ----------------------------------------

def _prep(pool: pd.DataFrame | None = None) -> pd.DataFrame:
    """Stage-A design frame: merit_z imputed, continuous predictors z-scored, types coerced."""
    if pool is None:
        pool = pool_feat.build()
    out = pool.copy()
    out["merit_z"] = out["merit_z"].astype(float).fillna(0.0)
    out["cl_round"] = out["cl_round"].astype(float)
    out["tournament_result"] = out["tournament_result"].astype(float)
    for col in _CONTINUOUS:
        mu, sd = out[col].mean(), out[col].std(ddof=0)
        out[col] = (out[col] - mu) / sd if sd > 0 else 0.0
    out["won_cl"] = out["won_cl"].astype(int)
    out["won_league"] = out["won_league"].astype(int)
    out["nominated"] = out["nominated"].astype(int)
    out["award_year"] = out["award_year"].astype(str)  # group key must be categorical
    out["position_family"] = out["position_family"].astype("category")
    return out.reset_index(drop=True)


def _prep_hperp(
    pool: pd.DataFrame | None = None, hperp_df: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Stage-A + H⊥ design frame: pool members with a defined H⊥ joined to it, predictors z-scored.

    Restricted to candidates with a defined H⊥ — now any player with a merit dimension (attackers,
    deep mids, center-backs, keepers); `h_perp_pv` is non-null only there.
    """
    if pool is None:
        pool = pool_feat.build()
    if hperp_df is None:
        hperp_df = hperp.build()
    hp = hperp_df[["player_key", "award_year", "h_perp_pv", "pv_low_baseline"]]
    out = pool.copy()
    out["player_key"] = out["player"].map(awards.name_key)
    out = out.merge(hp, on=["player_key", "award_year"], how="left")
    out = out[out["h_perp_pv"].notna()].copy()  # complete-case: any player with a defined H⊥
    # Un-standardized passthroughs for the robustness panel's row filters.
    out["is_duopoly"] = out["player"].str.contains(r"Messi|Ronaldo", case=False, na=False)
    out["pv_low_baseline"] = out["pv_low_baseline"].fillna(False).astype(bool)
    out["merit_z"] = out["merit_z"].astype(float)
    out["cl_round"] = out["cl_round"].astype(float)
    out["h_perp_pv"] = out["h_perp_pv"].astype(float)
    out["tournament_result"] = out["tournament_result"].astype(float)
    out = out.dropna(subset=[*_CONTINUOUS_HPERP, "won_cl", "won_league", "nominated"])

    for col in _CONTINUOUS_HPERP:
        mu, sd = out[col].mean(), out[col].std(ddof=0)
        out[col] = (out[col] - mu) / sd if sd > 0 else 0.0
    out["won_cl"] = out["won_cl"].astype(int)
    out["won_league"] = out["won_league"].astype(int)
    out["nominated"] = out["nominated"].astype(int)
    out["award_year"] = out["award_year"].astype(str)
    return out.reset_index(drop=True)


# --- Bayesian fit (bambi / nutpie) ------------------------------------------

def _fit_bambi(data: pd.DataFrame, cache_name: str, formula: str, *, refresh: bool = False):
    """Fit the Bernoulli mixed model and cache the posterior (NetCDF). Sampler = nutpie (no g++)."""
    import arviz as az  # noqa: PLC0415

    path = cache_path(cache_name, suffix=".nc")
    if path.exists() and not refresh:
        return az.from_netcdf(path)

    import bambi as bmb  # noqa: PLC0415

    model = bmb.Model(formula, data=data, family="bernoulli")
    idata = model.fit(
        draws=1000, tune=1000, chains=4, inference_method="nutpie",
        nuts={"target_accept": 0.9}, random_seed=_SEED, progressbar=False,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    idata.to_netcdf(path, engine="h5netcdf")
    return idata


def fit_hperp(*, refresh: bool = False):
    """Fit Stage A + H⊥ (attacker-only); the Gate-A thesis test. Returns cached InferenceData."""
    return _fit_bambi(_prep_hperp(), "nomination_hperp_idata", _FORMULA_HPERP, refresh=refresh)


def fit(*, refresh: bool = False):
    """Fit the Stage-A baseline (all positions, no H⊥) and return arviz InferenceData (cached)."""
    return _fit_bambi(_prep(), "nomination_idata", _FORMULA, refresh=refresh)


def _fixed_effect_terms(idata) -> list[str]:
    """Common-effect variable names in the posterior (drop the year-group RE + dispersion)."""
    return [
        v for v in idata.posterior.data_vars
        if "award_year" not in v and not v.endswith(("_sigma", "_offset"))
    ]


def summary(idata) -> pd.DataFrame:
    """Coefficient table (mean, sd, 94% HDI, P>0) for the fixed effects."""
    from ._report import coef_table  # noqa: PLC0415

    return coef_table(idata, _fixed_effect_terms(idata))


def marginal_effect(focal: str = "h_perp_pv", shift: float = 1.0) -> dict:
    """AME (percentage points) of a +shift-SD change in `focal` on the probability of nomination."""
    from ._report import average_marginal_effect  # noqa: PLC0415

    return average_marginal_effect(
        _FORMULA_HPERP, "bernoulli", _prep_hperp(), fit_hperp(), focal=focal, shift=shift)


# --- frequentist discrimination anchor --------------------------------------

def discrimination(data: pd.DataFrame | None = None, n_splits: int = 5) -> float:
    """Year-grouped cross-validated ROC-AUC (a leakage-safe 'does this separate at all?' number)."""
    from sklearn.linear_model import LogisticRegression  # noqa: PLC0415
    from sklearn.metrics import roc_auc_score  # noqa: PLC0415
    from sklearn.model_selection import GroupKFold  # noqa: PLC0415

    if data is None:
        data = _prep()
    x = pd.get_dummies(
        data[["merit_z", "cl_round", "won_cl", "won_league", "position_family"]],
        columns=["position_family"], drop_first=True, dtype=float,
    )
    y = data["nominated"].to_numpy()
    groups = data["award_year"].to_numpy()

    gkf = GroupKFold(n_splits=n_splits)
    aucs = []
    for tr, te in gkf.split(x, y, groups):
        clf = LogisticRegression(class_weight="balanced", max_iter=1000)
        clf.fit(x.iloc[tr], y[tr])
        aucs.append(roc_auc_score(y[te], clf.predict_proba(x.iloc[te])[:, 1]))
    return float(np.mean(aucs))


# --- frequentist H⊥ anchor (for the robustness panel) -----------------------

_ANCHOR_FORMULA = (
    "nominated ~ h_perp_pv + merit_z + cl_round + won_cl + won_league + tournament_result "
    "+ C(award_year)"
)


def logit_anchor(data: pd.DataFrame) -> pd.DataFrame:
    """statsmodels Logit on the Stage-A + H⊥ design (year fixed effects) → coef table + 95% CI.

    The fast frequentist mirror of `fit_hperp` used by the robustness panel; year FE stand in for
    the Bayesian `(1|award_year)`. Returns rows with estimate / ci_low / ci_high / pvalue.
    """
    import statsmodels.formula.api as smf  # noqa: PLC0415

    res = smf.logit(_ANCHOR_FORMULA, data=data).fit(disp=0)
    ci = res.conf_int()
    return pd.DataFrame(
        {"estimate": res.params, "ci_low": ci[0], "ci_high": ci[1], "pvalue": res.pvalues}
    )
