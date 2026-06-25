"""Reporting layer — result loaders + figures for the Quarto writeup.

Per the repo philosophy (logic in ``src/``, not notebooks), the blog's figures and result-loading
live here as tested, reusable functions; ``report/ballon-dor.qmd`` is thin narrative calling them.
Everything reads the **cached** model objects (idata NetCDF, parquet) — the writeup never refits.

Figures are plotly ``Figure`` objects: interactive when embedded in the rendered HTML, and exported
to static PNG by :func:`build_all` (kaleido). Heavy imports (plotly) are lazy so the pure data
helpers stay offline-testable.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .config import CACHE_DIR
from .data import awards

_ROOT = Path(__file__).resolve().parents[2]
FIGURE_DIR = _ROOT / "report" / "figures"
SITE_DATA = _ROOT / "site" / "data.js"

_TEMPLATE = "plotly_white"
# Case studies the narrative is built around (player substring, award_year, one-line label).
_CASES = [
    ("Modrić", 2018, "won on narrative"),
    ("Lewandowski", 2019, "elite merit, low buzz"),
    ("Benzema", 2022, "won on merit + CL"),
    ("Messi", 2023, "elite merit + narrative"),
]


# --- data loaders (offline-testable) ----------------------------------------

def _cache(name: str) -> pd.DataFrame:
    return pd.read_parquet(CACHE_DIR / f"{name}.parquet")


def load_panel() -> pd.DataFrame:
    """The robustness panel (gate, spec, estimate, ci_low, ci_high, n)."""
    return _cache("robustness_panel")


def leaderboard(n: int = 8, df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Top narrative-excess (+H⊥) and lowest (−H⊥) finishers, with a `kind` label."""
    if df is None:
        df = _cache("model_features")
    fin = df[df["h_perp_pv"].notna()][
        ["award_year", "player", "rank", "vote_share", "h_perp_pv", "merit_pc1"]
    ].copy()
    top = fin.sort_values("h_perp_pv", ascending=False).head(n).assign(kind="narrative excess")
    bottom = fin.sort_values("h_perp_pv").head(n).assign(kind="under the radar")
    return pd.concat([top, bottom], ignore_index=True)


def case_studies(df: pd.DataFrame | None = None) -> pd.DataFrame:
    """The H⊥ / merit / vote-share rows for the narrative's case-study players."""
    if df is None:
        df = _cache("model_features")
    rows = []
    for sub, year, label in _CASES:
        m = df[
            (df["award_year"] == year)
            & df["player"].str.contains(sub, case=False, na=False)
            & df["h_perp_pv"].notna()
        ]
        if len(m):
            r = m.iloc[0]
            rows.append(
                {"player": r["player"], "award_year": year, "label": label,
                 "rank": int(r["rank"]), "vote_share": float(r["vote_share"]),
                 "h_perp_pv": float(r["h_perp_pv"]), "merit_pc1": float(r["merit_pc1"])}
            )
    return pd.DataFrame(rows)


def _hperp_row(table: pd.DataFrame) -> dict:
    r = table.loc["h_perp_pv"]
    return {"mean": float(r["mean"]), "lo": float(r["hdi94_lb"]), "hi": float(r["hdi94_ub"]),
            "p_pos": float(r["p_positive"])}


def headline_stats() -> dict:
    """Gate-A and Gate-B H⊥ posteriors from the CACHED idata (no refit) — for the prose + forest."""
    from .models import nomination, placement  # noqa: PLC0415  (heavy; lazy)

    return {
        "gate_a": _hperp_row(nomination.summary(nomination.fit_hperp())),
        "gate_b": _hperp_row(placement.summary(placement.fit())),
    }


def effect_sizes(stats: dict | None = None) -> dict:
    """Interpretable effect sizes: per-SD odds ratios (both gates) + a Gate-A probability AME.

    Turns the logit coefficients into human terms: an odds ratio (exp of the per-SD coefficient) per
    gate, plus the average marginal effect in percentage points for nomination (the most tangible
    statement). The per-SD log-odds scale is also the honest basis for the "~5×" gate comparison.
    """
    from .models import nomination  # noqa: PLC0415

    s = stats or headline_stats()

    def _or(g: dict) -> dict:
        return {"or": float(np.exp(g["mean"])), "or_lo": float(np.exp(g["lo"])),
                "or_hi": float(np.exp(g["hi"]))}

    return {
        "gate_a_or": _or(s["gate_a"]),
        "gate_b_or": _or(s["gate_b"]),
        "ratio": float(s["gate_a"]["mean"] / s["gate_b"]["mean"]),
        "gate_a_ame": nomination.marginal_effect(),  # percentage-point change in shortlist prob
    }


def diagnostics() -> dict:
    """MCMC convergence + discrimination diagnostics from the CACHED headline fits (no refit).

    For the methods appendix: worst-case R-hat and min bulk-ESS across both posteriors, the total
    divergence count, and the leakage-safe cross-validated ROC-AUC of the nomination model.
    """
    import arviz as az  # noqa: PLC0415

    from .models import nomination, placement  # noqa: PLC0415

    def _conv(idata) -> dict:
        s = az.summary(idata)
        ss = getattr(idata, "sample_stats", None)
        div = int(ss["diverging"].sum()) if ss is not None and "diverging" in ss else 0
        return {"rhat": float(s["r_hat"].max()), "ess": int(s["ess_bulk"].min()), "div": div}

    a, b = _conv(nomination.fit_hperp()), _conv(placement.fit())
    return {
        "rhat_max": max(a["rhat"], b["rhat"]),
        "ess_bulk_min": min(a["ess"], b["ess"]),
        "divergences": a["div"] + b["div"],
        "roc_auc": float(nomination.discrimination()),
    }


def prior_sensitivity_extent() -> dict | None:
    """Per-gate H⊥ range across default/tight/wide priors (for the prose 'not the prior' note).

    Reads the cached `prior_sensitivity` table (built by the robustness stage); returns the default
    estimate plus the min/max across all three prior settings per gate, so the report can state how
    little the headline moves. None if the cache hasn't been built yet.
    """
    from .cache import cache_path  # noqa: PLC0415

    if not cache_path("prior_sensitivity").exists():
        return None
    return _prior_extent(_cache("prior_sensitivity"))


def _prior_extent(t: pd.DataFrame) -> dict:
    """Per-gate {default, min, max} H⊥ estimate across prior settings. Pure / offline-testable."""
    def _g(gate: str) -> dict:
        g = t[t["gate"] == gate]
        default = float(g[g["prior"] == "default"]["estimate"].iloc[0])
        return {"default": default, "min": float(g["estimate"].min()),
                "max": float(g["estimate"].max())}

    return {"a": _g("A_nomination"), "b": _g("B_placement")}


def robustness_extras() -> dict:
    """Bootstrap + Heckman + strict-window rows, for the prose robustness notes."""
    p = load_panel()

    def _get(gate: str, spec: str) -> dict | None:
        r = p[(p["gate"] == gate) & (p["spec"] == spec)]
        if not len(r):
            return None
        r = r.iloc[0]
        return {"est": float(r["estimate"]), "lo": float(r["ci_low"]),
                "hi": float(r["ci_high"]), "n": int(r["n"])}

    return {
        "bootstrap_a": _get("A_nomination", "bootstrap_hperp"),
        "bootstrap_b": _get("B_placement", "bootstrap_hperp"),
        "heckman_b": _get("B_placement", "heckman"),
        "prior": prior_sensitivity_extent(),
        "strict_a": _get("A_nomination", "window_strict"),
        "strict_b": _get("B_placement", "window_strict"),
        # drop_club_importance = H⊥ refit WITHOUT the v3 team-centrality control (baseline has it).
        "noclub_a": _get("A_nomination", "drop_club_importance"),
        "noclub_b": _get("B_placement", "drop_club_importance"),
        # proxy_gdelt = H⊥ rebuilt on GDELT news volume (independent of pageviews); finisher-fit.
        "gdelt_a": _get("A_nomination", "proxy_gdelt"),
        "gdelt_b": _get("B_placement", "proxy_gdelt"),
    }


# --- figures (plotly) -------------------------------------------------------

def fig_two_gate(stats: dict | None = None):
    """The headline: H⊥ coefficient + 94% interval at Gate A (nomination) vs Gate B (placement)."""
    import plotly.graph_objects as go  # noqa: PLC0415

    s = stats or headline_stats()
    gates = [("Gate A — nomination\n(get noticed)", s["gate_a"]),
             ("Gate B — placement\n(finish higher)", s["gate_b"])]
    fig = go.Figure()
    for label, g in gates:
        fig.add_trace(go.Scatter(
            x=[g["mean"]], y=[label], mode="markers",
            error_x={"type": "data", "symmetric": False,
                     "array": [g["hi"] - g["mean"]], "arrayminus": [g["mean"] - g["lo"]]},
            marker={"size": 13}, name=label, showlegend=False,
            hovertemplate="H⊥=%{x:.2f}<extra></extra>",
        ))
    fig.add_vline(x=0, line_dash="dot", line_color="grey")
    fig.update_layout(
        template=_TEMPLATE, title="Narrative beyond merit (H⊥): its pull at each gate",
        xaxis_title="H⊥ coefficient (standardized, logit) — 94% HDI", yaxis_title="",
        height=320, margin={"l": 10, "r": 30, "t": 50, "b": 40},
    )
    return fig


# Specs whose H⊥ estimate is on the SAME standardized anchor scale → comparable caterpillar points.
# bootstrap_hperp (re-standardized per resample) and heckman (OLS-on-logit) are different scales,
# reported as prose robustness notes instead (see `robustness_extras`).
_CATERPILLAR_SPECS = [
    "baseline", "no_duopoly",
    "window_leaky", "window_strict", "drop_club_importance", "jackknife_year",
]


def fig_robustness(panel: pd.DataFrame | None = None):
    """Caterpillar of the H⊥ coefficient across point-comparable specifications, by gate."""
    import plotly.express as px  # noqa: PLC0415

    p = (panel if panel is not None else load_panel()).copy()
    p = p[p["spec"].isin(_CATERPILLAR_SPECS)]
    p["err_hi"] = p["ci_high"] - p["estimate"]
    p["err_lo"] = p["estimate"] - p["ci_low"]
    # Facets STACKED (facet_row), not side-by-side: each gate gets the full width — readable on a
    # phone and still clean on desktop. Clean up the "gate=…" facet labels.
    fig = px.scatter(
        p, x="estimate", y="spec", facet_row="gate", error_x="err_hi", error_x_minus="err_lo",
        color="gate", template=_TEMPLATE,
        title="Robustness: H⊥ across specifications (frequentist anchors)",
    )
    fig.add_vline(x=0, line_dash="dot", line_color="grey")
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1].replace("_", " ")))
    fig.update_xaxes(matches=None, title="H⊥ estimate (95% CI / spread)")
    fig.update_yaxes(title="")
    fig.update_layout(showlegend=False, height=560, margin={"t": 60})
    return fig


def fig_leaderboard(n: int = 8):
    """Diverging bars: narrative darlings (+H⊥) vs under-the-radar producers (−H⊥)."""
    import plotly.express as px  # noqa: PLC0415

    lb = leaderboard(n).sort_values("h_perp_pv")
    lb["who"] = lb["player"] + " '" + (lb["award_year"] % 100).astype(str).str.zfill(2)
    fig = px.bar(
        lb, x="h_perp_pv", y="who", color="kind", orientation="h", template=_TEMPLATE,
        title="Narrative excess (H⊥) — most over-attended vs most under-the-radar finishers",
        color_discrete_map={"narrative excess": "#d62728", "under the radar": "#1f77b4"},
    )
    fig.add_vline(x=0, line_dash="dot", line_color="grey")
    fig.update_layout(xaxis_title="H⊥ (attention beyond merit)", yaxis_title="",
                      height=520, margin={"t": 50}, legend_title="")
    return fig


def fig_merit_vs_attention(df: pd.DataFrame | None = None):
    """Merit vs windowed attention, colored by H⊥ — the Messi-23 vs De Bruyne-19 contrast."""
    import plotly.express as px  # noqa: PLC0415

    d = (df if df is not None else _cache("model_features"))
    d = d[d["h_perp_pv"].notna()].copy()
    fig = px.scatter(
        d, x="merit_pc1", y="log_window", color="h_perp_pv", template=_TEMPLATE,
        color_continuous_scale="RdBu_r", color_continuous_midpoint=0,
        hover_data=["player", "award_year"],
        title="Same production, opposite narrative — merit vs attention (colour = H⊥)",
    )
    for sub, year in [("Messi", 2023), ("Lewandowski", 2019)]:
        m = d[(d["award_year"] == year) & d["player"].str.contains(sub, na=False)]
        if len(m):
            r = m.iloc[0]
            fig.add_annotation(x=r["merit_pc1"], y=r["log_window"],
                               text=f"{sub} '{year % 100}", showarrow=True, arrowhead=2)
    fig.update_layout(xaxis_title="merit (PC1: output/volume)",
                      yaxis_title="log window attention", height=460, margin={"t": 50})
    return fig


def fig_spike(player: str = "Rodri", year: int = 2024):
    """Daily all-language pageviews for one player, with the leakage-safe window markers.

    Rodri 2024 (a winner) shows the point cleanly: his ceremony-announcement spike is ~3× his
    biggest in-window day, and sits AFTER the shortlist cut — the attention the window drops.
    """
    import plotly.graph_objects as go  # noqa: PLC0415

    from .windows import load_windows  # noqa: PLC0415

    daily = _cache("pageviews_all_lang_daily")
    key = awards.name_key(player)
    s = daily[daily["player"].map(awards.name_key) == key].sort_values("date")
    w = load_windows().loc[year]
    # datetimes -> numpy / ISO strings: kaleido (PNG export) can't JSON-serialize pandas Timestamps.
    fig = go.Figure(go.Scatter(x=s["date"].to_numpy(), y=s["views"], mode="lines", name="views"))
    # Markers cluster on the right (2023-24), shortlist-cut & ceremony days apart, so on-line top
    # labels collide at narrow widths. Leave the lines unlabelled and put a colour-keyed legend in
    # the empty upper-left (pageviews ~0 there pre-2023) instead — robust at any width.
    markers = [(w["perf_start"], "window start", "green"),
               (w["hype_cut"], "shortlist cut", "orange"),
               (w["ceremony_date"], "ceremony", "red")]
    for i, (when, label, color) in enumerate(markers):
        fig.add_vline(x=when.isoformat(), line_dash="dash", line_color=color)
        fig.add_annotation(xref="paper", yref="paper", x=0.015, y=0.97 - i * 0.11,
                           xanchor="left", yanchor="top", text=f"╌ {label}", showarrow=False,
                           font={"color": color, "size": 12})
    fig.update_layout(template=_TEMPLATE, height=360, margin={"t": 50},
                      title=f"Attention is event-driven — {player} daily pageviews ({year} award)",
                      xaxis_title="", yaxis_title="all-language daily views")
    return fig


# --- build all (static PNG export) ------------------------------------------

def build_all(out_dir: Path | str = FIGURE_DIR) -> dict:
    """Build every figure and export a static PNG (kaleido) to `out_dir`; returns the figures."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    figs = {
        "two_gate": fig_two_gate(),
        "robustness": fig_robustness(),
        "leaderboard": fig_leaderboard(),
        "merit_vs_attention": fig_merit_vs_attention(),
        "spike": fig_spike(),
    }
    for name, fig in figs.items():
        fig.write_image(out / f"{name}.png", width=900, height=520, scale=2)
    return figs


# --- public scrollytelling site: distilled data export ----------------------

def _records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> JSON-native records (to_json handles numpy dtypes cleanly)."""
    return json.loads(df.to_json(orient="records"))


def _defame_rows(df: pd.DataFrame, cases: list[tuple[str, int]]) -> list[dict]:
    """Per example player: actual window attention vs the merit/fame-expected level (gap = story).

    `expected = expm1(log1p(actual) − H⊥)` inverts the de-fame residual, so the gap is exactly the
    attention H⊥ flags as unexplained by merit + fame + team.
    """
    rows = []
    for sub, year in cases:
        m = df[(df["award_year"] == year)
               & df["player"].str.contains(sub, case=False, na=False)
               & df["h_perp_pv"].notna()]
        if len(m):
            r = m.iloc[0]
            actual = float(r["pv_window_mean"])
            h = float(r["h_perp_pv"])
            rows.append({"player": r["player"], "year": int(year),
                         "actual": round(actual), "h_perp": round(h, 2),
                         "expected": round(float(np.expm1(np.log1p(actual) - h)))})
    return rows


def _spike_series(player: str = "Rodri", year: int = 2024) -> dict:
    """Weekly-downsampled daily pageviews + the leakage-safe window markers, for one player."""
    from .windows import load_windows  # noqa: PLC0415

    daily = _cache("pageviews_all_lang_daily")
    key = awards.name_key(player)
    s = daily[daily["player"].map(awards.name_key) == key].sort_values("date")
    weekly = (s.set_index("date")["views"].resample("W").mean().dropna())
    w = load_windows().loc[year]
    return {
        "player": player, "year": int(year),
        "dates": [d.strftime("%Y-%m-%d") for d in weekly.index],
        "views": [round(float(v)) for v in weekly.to_numpy()],
        "markers": {k: w[k].strftime("%Y-%m-%d")
                    for k in ("perf_start", "hype_cut", "ceremony_date")},
    }


def _per_year_scoreboard(df: pd.DataFrame) -> list[dict]:
    """Per award year, the three faces among finishers: who PLAYED best (top merit), who got TALKED
    about most (top Hype Score), and who actually WON — with each face's rank on the other two axes.

    When the three are different people, that divergence is the thesis in one row. Pure / offline.
    """
    d = df[df["h_perp_pv"].notna() & df["merit_z"].notna()].copy()

    def _face(r: pd.Series) -> dict:
        return {
            "player": r["player"],
            "merit_z": round(float(r["merit_z"]), 2),
            "h_perp": round(float(r["h_perp_pv"]), 2),
            "rank": int(r["rank"]),
            "vote_share": round(float(r["vote_share"]), 3),
            "merit_rank": int(r["merit_rank"]),
            "hype_rank": int(r["hype_rank"]),
        }

    out = []
    for year in sorted(d["award_year"].unique()):
        g = d[d["award_year"] == year].copy()
        winner = g[g["rank"] == 1]
        if g.empty or winner.empty:
            continue
        g["merit_rank"] = g["merit_z"].rank(ascending=False, method="min").astype(int)
        g["hype_rank"] = g["h_perp_pv"].rank(ascending=False, method="min").astype(int)
        winner = g[g["rank"] == 1].iloc[0]
        best = g.loc[g["merit_z"].idxmax()]
        hyped = g.loc[g["h_perp_pv"].idxmax()]
        faces = {winner["player"], best["player"], hyped["player"]}
        out.append({
            "year": int(year),
            "winner": _face(winner),
            "best_season": _face(best),
            "most_hyped": _face(hyped),
            "diverge": len(faces) > 1,
        })
    return out


def _site_payload(stats, lb, cases, panel, scatter, defame, spike, per_year,
                  effects=None, robust_extra=None) -> dict:
    """Pure assembler: the distilled results the scrollytelling page consumes (offline-testable)."""
    return {
        "headline": {"gateA": stats["gate_a"], "gateB": stats["gate_b"]},
        "effects": effects,
        "robust_extra": robust_extra,
        "leaderboard": _records(lb),
        "cases": _records(cases),
        "robustness": _records(panel),
        "scatter": _records(scatter),
        "defame": defame,
        "spike": spike,
        "per_year": per_year,
    }


def export_site_data(path: Path | str = SITE_DATA) -> dict:
    """Build the distilled payload from cache and write `site/data.js` (`window.BDOR = {…}`)."""
    mf = _cache("model_features")
    # Public scatter uses role-aware merit_z (defined for every role) — NOT attacking merit_pc1,
    # which is null for defenders/keepers and would stack elite CBs (Van Dijk) at x=0.
    sc = mf[mf["h_perp_pv"].notna()][
        ["player", "award_year", "rank", "vote_share", "merit_z", "log_window", "h_perp_pv"]
    ].rename(columns={"award_year": "year", "merit_z": "merit", "log_window": "attention",
                      "h_perp_pv": "h_perp"})
    ren = {"award_year": "year", "h_perp_pv": "h_perp", "merit_pc1": "merit"}
    stats = headline_stats()
    payload = _site_payload(
        stats=stats,
        lb=leaderboard(8).rename(columns=ren),
        cases=case_studies().rename(columns=ren),
        panel=load_panel(),
        scatter=sc,
        defame=_defame_rows(mf, [("Modrić", 2018), ("De Bruyne", 2019), ("Lamine Yamal", 2024)]),
        spike=_spike_series(),
        per_year=_per_year_scoreboard(mf),
        effects=effect_sizes(stats),
        robust_extra=robustness_extras(),
    )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("window.BDOR = " + json.dumps(payload) + ";\n", encoding="utf-8")
    return payload


def run(*, refresh: bool = False) -> pd.DataFrame:
    """run.py stage entry: (re)generate the figure PNGs + the site data; return the leaderboard."""
    build_all()
    export_site_data()
    print(f"report: figures -> {FIGURE_DIR}  |  site data -> {SITE_DATA}")
    return leaderboard()
