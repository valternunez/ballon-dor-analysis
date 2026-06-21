"""Stage B — placement model: does narrative-beyond-merit move you up the vote share?

The thesis test (PROJECT_NOTES "Conditional spec" step 4). Given a player is a Ballon d'Or
finisher, we model **vote share** as a function of H⊥ (attention beyond merit) while controlling
for merit and team-success, with a per-year group effect:

    vote_share ~ h_perp + merit(pca axes) + team-success + (1 | award_year)     [Beta likelihood]

**The deliverable is the posterior of the H⊥ coefficient.** A 94% HDI crossing zero is itself the
finding: "once merit and team-success are in, narrative has no independent pull on placement."

Why H⊥'s effect reads cleanly: H⊥ is the OLS residual of log-attention on
[log_baseline, merit_pc1, merit_pc2, def_merit_z, cb_def_z, gk_merit_z, team-success], so in-sample
it is orthogonal to merit and team-success — putting them all in the outcome model together is fine
(unlike the H⊥ regression itself, where those controls were collinear).

Two practical wrinkles handled here:
  * **Zeros.** A chunk of finishers (the tail of the 30) scored zero vote points (`vote_share` 0),
    but the Beta likelihood lives on the open interval (0, 1). We apply the Smithson–Verkuilen
    squeeze `(y(n-1) + 0.5)/n` so every row survives.
  * **CBs & keepers** now have a merit (FBref CB-efficiency / GK PSxG+/-), hence an H⊥, hence they
    ENTER Stage B — a few (Van Dijk, Dias, Courtois) join the attacker majority, controlled by
    cb_def_z / gk_merit_z. The no-merit tournament-only members stay out.

Heavy deps (bambi / arviz / statsmodels) are imported *inside* the fitting functions so the pure
helpers (`_squeeze`, `_prep`) stay offline-testable without the `[model]` extra.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..cache import cache_path
from ..features import build as build_features

# Standardized continuous predictors (per-SD effects → comparable, sane priors). won_cl/won_league
# stay binary 0/1. H⊥ is the headline term.
# def_merit_z / cb_def_z / gk_merit_z mirror the H⊥ de-fame regressors (H⊥ is orthogonal to them
# in-sample, so valid co-controls): they credit a finisher's ball-winning / CB / GK merit
# so H⊥ keeps capturing only the excess. CB & keeper finishers (Van Dijk, Dias, Courtois) now enter
# Stage B for the first time, so these controls are required to keep the headline read clean.
_CONTINUOUS = ["h_perp_pv", "merit_pc1", "merit_pc2", "def_merit_z", "cb_def_z", "gk_merit_z",
               "cl_round", "tournament_result"]
_BINARY = ["won_cl", "won_league"]
_PREDICTORS = ["h_perp_pv", "merit_pc1", "merit_pc2", "def_merit_z", "cb_def_z", "gk_merit_z",
               "cl_round", "won_cl", "won_league", "tournament_result"]
_FORMULA = (
    "vote_share_sv ~ h_perp_pv + merit_pc1 + merit_pc2 + def_merit_z + cb_def_z + gk_merit_z "
    "+ cl_round + won_cl + won_league + tournament_result + (1|award_year)"
)
_DUOPOLY = r"Messi|Ronaldo"
_SEED = 20260619


# --- pure helpers (offline-testable) ----------------------------------------

def _squeeze(y: np.ndarray | pd.Series, n: int | None = None) -> np.ndarray:
    """Smithson–Verkuilen transform: map [0, max] into the open interval (0, 1).

    `(y*(n-1) + 0.5)/n` with n = sample size. Pulls the 0/1 endpoints just inside the
    support so a Beta likelihood is well-defined while keeping every row.
    """
    y = np.asarray(y, dtype=float)
    if n is None:
        n = len(y)
    return (y * (n - 1) + 0.5) / n


def _prep(df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Stage-B model frame: complete cases (H⊥ defined), squeezed outcome, z-scored predictors.

    Standardization is computed on the full complete-case sample so that the no-duopoly refit
    (a row filter applied *after* prep) keeps the same scale → coefficients stay comparable.
    """
    if df is None:
        df = build_features()
    out = df[df["h_perp_pv"].notna()].copy()
    for col in ("def_merit_z", "cb_def_z", "gk_merit_z"):  # 0 where the role doesn't apply
        out[col] = out[col].astype(float).fillna(0.0)
    # Cast nullable Float64 → float so numpy / bambi / statsmodels behave.
    num_cols = [*_PREDICTORS, "vote_share"]
    out[num_cols] = out[num_cols].astype(float)

    n = len(out)
    out["vote_share_sv"] = _squeeze(out["vote_share"].to_numpy(), n)
    for col in _CONTINUOUS:
        mu, sd = out[col].mean(), out[col].std(ddof=0)
        out[col] = (out[col] - mu) / sd if sd > 0 else 0.0
    out["award_year"] = out["award_year"].astype(str)  # group key must be categorical
    out["is_duopoly"] = out["player"].str.contains(_DUOPOLY, case=False, na=False)
    return out.reset_index(drop=True)


# --- Bayesian fit (bambi / PyMC) --------------------------------------------

def _fit_bambi(data: pd.DataFrame, cache_name: str, *, refresh: bool = False):
    """Fit the Beta mixed model and cache the posterior (NetCDF) to disk.

    Sampler = **nutpie** (numba-backed NUTS): this machine has no C compiler, so PyTensor can't
    build the C logp; nutpie compiles via numba and needs no g++ (see decisions log). The fit
    object is an xarray DataTree (arviz 1.x) cached with the h5netcdf engine.
    """
    import arviz as az  # noqa: PLC0415  (heavy; lazy so helpers stay offline)

    path = cache_path(cache_name, suffix=".nc")
    if path.exists() and not refresh:
        return az.from_netcdf(path)

    import bambi as bmb  # noqa: PLC0415

    # Default weakly-informative priors (bambi auto-scales to the data) — adequate at this N;
    # predictors are standardized so the implied scale is sensible. family="beta" → logit link
    # on the mean + a positive dispersion (kappa).
    model = bmb.Model(_FORMULA, data=data, family="beta")
    idata = model.fit(
        draws=1000, tune=1000, chains=4, inference_method="nutpie",
        nuts={"target_accept": 0.9}, random_seed=_SEED, progressbar=False,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    idata.to_netcdf(path, engine="h5netcdf")
    return idata


def fit(*, refresh: bool = False, drop_duopoly: bool = False):
    """Fit Stage B and return arviz InferenceData (cached).

    drop_duopoly=True refits on the same standardized frame with the 8 Messi/Ronaldo rows
    removed (the duopoly-dominance robustness slice).
    """
    data = _prep()
    if drop_duopoly:
        data = data[~data["is_duopoly"]].reset_index(drop=True)
        return _fit_bambi(data, "placement_idata_noduo", refresh=refresh)
    return _fit_bambi(data, "placement_idata", refresh=refresh)


def summary(idata) -> pd.DataFrame:
    """Tidy coefficient table; the `h_perp_pv` row is the headline (the thesis in one number)."""
    from ._report import coef_table  # noqa: PLC0415

    return coef_table(idata, _PREDICTORS)


def marginal_effect(focal: str = "h_perp_pv", shift: float = 1.0) -> dict:
    """AME (percentage points) of a +shift-SD change in `focal` on predicted vote share."""
    from ._report import average_marginal_effect  # noqa: PLC0415

    return average_marginal_effect(_FORMULA, "beta", _prep(), fit(), focal=focal, shift=shift)


# --- frequentist anchor (statsmodels Beta regression) -----------------------

def betareg_anchor(data: pd.DataFrame | None = None) -> pd.DataFrame:
    """statsmodels Beta regression on the same design (no year RE) — a cheap cross-check.

    Always runs even if PyTensor won't compile; a sign/scale agreement with the Bayesian
    posterior is a sanity check. Returns the coefficient table (estimate + 95% CI).
    """
    from statsmodels.othermod.betareg import BetaModel  # noqa: PLC0415

    if data is None:
        data = _prep()
    formula = (
        "vote_share_sv ~ h_perp_pv + merit_pc1 + merit_pc2 + def_merit_z + cb_def_z + gk_merit_z "
        "+ cl_round + won_cl + won_league + tournament_result"
    )
    res = BetaModel.from_formula(formula, data).fit(disp=0)
    ci = res.conf_int()
    out = pd.DataFrame(
        {"estimate": res.params, "ci_low": ci[0], "ci_high": ci[1], "pvalue": res.pvalues}
    )
    # Keep just the mean-model rows (drop the precision/phi block prefixed "precision-").
    return out[~out.index.astype(str).str.startswith("precision-")]


# --- Heckman selection sensitivity ------------------------------------------

_HECKMAN_SELECT = ["h_perp_pv", "merit_z", "cl_round", "won_cl", "won_league", "tournament_result"]
_HECKMAN_OUTCOME = ["h_perp_pv", "merit_pc1", "merit_pc2", "def_merit_z", "cb_def_z", "gk_merit_z",
                    "cl_round", "won_cl", "won_league", "tournament_result", "imr"]


def heckman_check() -> tuple[float, float, float, int]:
    """Two-step Heckman sensitivity for the Stage-B H⊥ effect. Returns (estimate, lo, hi, n).

    Stage 1: a **Probit** of nomination over the whole candidate pool (`nomination._prep_hperp`),
    from which we form the inverse Mills ratio λ = φ(Xγ)/Φ(Xγ). Stage 2: among finishers, OLS of the
    logit-transformed (SV-squeezed) vote share on the usual predictors **plus λ**, so selection into
    the shortlist is controlled. The `h_perp_pv` slope is the deliverable.

    **Honest limit:** there's no clean exclusion restriction (a variable that drives nomination but
    not placement), so with small N this is identified mainly off functional form — a *sensitivity
    check* that the placement effect keeps its sign under a selection control, not a fix.
    """
    import numpy as np  # noqa: PLC0415
    import statsmodels.api as sm  # noqa: PLC0415
    from scipy.stats import norm  # noqa: PLC0415

    from ..data import awards  # noqa: PLC0415
    from . import nomination  # noqa: PLC0415

    sel = nomination._prep_hperp().copy()
    x_sel = sm.add_constant(sel[_HECKMAN_SELECT].astype(float))
    probit = sm.Probit(sel["nominated"].astype(int), x_sel).fit(disp=0)
    xb = x_sel.to_numpy(dtype=float) @ probit.params.to_numpy()
    sel["imr"] = norm.pdf(xb) / norm.cdf(xb)
    sel["player_key"] = sel["player"].map(awards.name_key)

    fin = _prep().copy()
    fin["player_key"] = fin["player"].map(awards.name_key)
    fin = fin.merge(
        sel[["player_key", "award_year", "imr"]], on=["player_key", "award_year"], how="left"
    ).dropna(subset=["imr"])

    y = np.log(fin["vote_share_sv"] / (1.0 - fin["vote_share_sv"]))
    x_out = sm.add_constant(fin[_HECKMAN_OUTCOME].astype(float))
    ols = sm.OLS(y, x_out).fit()
    ci = ols.conf_int().loc["h_perp_pv"]
    return float(ols.params["h_perp_pv"]), float(ci[0]), float(ci[1]), int(len(fin))
