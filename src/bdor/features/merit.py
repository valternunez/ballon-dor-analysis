"""Merit index — within-position-season standardized production, per player-award-year.

The backbone every downstream model regresses against (PROJECT_NOTES "Merit index — LOCKED
(REVISED)"). TWO complementary signals, combined **best-role**:

  * **Attacking merit** (Understat): expected (npxg, xag) + involvement (xg_chain, xg_buildup) +
    output (goals, assists). Built from **date-stamped match data** summed over each award year's
    leakage-safe **performance window** (docs/windowing.md), NOT from blended full seasons — so a
    calendar-regime award (2018/2019/2021) no longer credits matches played AFTER the ceremony (the
    De Bruyne-2019 leak). z-scored within (award_year, attack) → att_merit_z + PCA axes.
  * **Defensive merit** (FBref via `fbref_defense`): tackles-won + interceptions + blocks +
    clearances per 90, z-scored within (season, MF). Fixes the "Jorginho blind spot" — ball-winning
    deep mids had NO individual metric (Understat is attacking-only) and so read as low-merit.
    **Midfielders only** — for center-backs, action volume measures being-under-siege not quality
    (it's inverted: elite CBs on dominant teams make few actions), so CBs keep NA merit and the
    team-success route. See the module constants + decisions log.

**Best-role combine:** `merit_z = max(att_merit_z, def_merit_z)` — a player's merit is the better
evidence of value in the role they actually play (a poacher scores on attack, a destroyer wins the
ball). Ball-winning mids (Kanté, Jorginho), previously near-zero on attacking merit, now surface at
their true level; pure attackers are unaffected. Center-backs & keepers remain NA.

Pipeline (attacking): match stats -> sum within the award-year performance window -> per-90 + volume
-> z within (award_year, attack) -> PCA. (defensive/CB/GK): FBref has no match logs, so those use
the **completed season** (config.completed_season) for calendar years — the most recent season that
finished before the ceremony — instead of blending the look-ahead second season. Then combine
best-role. The asymmetry (attacking = true date window, defensive = completed season) is the public
data ceiling; see docs/decisions-log.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..cache import cached_frame
from ..config import AWARD_YEAR_SEASONS, REFERENCE_DIR, completed_season
from ..data import awards, fbref_defense, understat
from ..windows import load_windows

CACHE_NAME = "merit_features"
MIN_MINUTES = 1500  # z-score population floor (tunable); aligns w/ the Tier-2 forward floor

# Defensive merit: same minutes floor (expressed as 90s). The 4 defensive actions are z-scored
# within (season, primary position) then averaged.
DEF_MIN_NINETIES = MIN_MINUTES / 90.0
GK_MIN_NINETIES = 20.0  # ~1800 min — keepers need a near-full season (low-minutes PSxG+/- is noisy)
# **Midfielders only.** Defensive-action VOLUME measures being-under-siege, not defending well —
# for center-backs it's inverted (elite CBs on dominant teams make few actions: Rúben Dias '21 beat
# only 5% of DFs, Van Dijk '19 only 13%, while relegation-battling journeymen top the list). For a
# DESTROYER, though, ball-winning volume IS the job, so the MF signal is sound (Casemiro / Ndidi /
# Kanté rank top). CBs keep NA merit and the team-success route, as before. See decisions log.
_DEF_FAMILIES = ("MF",)  # primary FBref position that earns a VOLUME (ball-winning) merit
# FBref primary position -> our coarse Understat-style family (M and F both 'attack'; see below).
_FB_POS_FAMILY = {"DF": "defense", "MF": "attack", "FW": "attack", "GK": "keeper"}

# Center-back merit = EFFICIENCY + ball-playing, NOT defensive volume (volume is inverted for CB
# quality — elite CBs on dominant sides make the fewest actions). Tackle % + aerial-duel win %
# are inversion-immune; progressive passes/90 capture the positional ball-players (Dias, Chiellini)
# whom the duel stats miss, and also damp journeyman noise (weak-team CBs progress the ball less).
_CB_EFFICIENCY = ["tackle_pct", "aerial_win_pct"]
_CB_SIGNALS = [*_CB_EFFICIENCY, "prog_passes_p90"]
# Checkpoint flag: whether the (gated) CB merit feeds the best-role merit_z. Flip to False to fall
# back to NA-for-CB (defenders stay on the team-success route) without losing the cb_def_z column.
_CB_MERIT_ENABLED = True

# Merit blends DURABILITY-weighted production (season totals — a small-sample hot streak has a
# low total) with EFFICIENCY (a couple of per-90 rates). z-scored within (season, family).
_VOLUME = ["npxg", "xag", "xg_chain", "xg_buildup", "goals", "assists"]  # season totals
_RATE = ["npxg", "xag"]  # -> per-90 efficiency signals
_MERIT_FAMILIES = ("attack",)  # only outfield-attacking players get an individual merit metric


# --- pure helpers (offline-testable) ----------------------------------------

def _position_family(pos: str) -> str:
    """Understat coarse position -> family. F and M are merged into 'attack': Understat codes
    wingers/forwards inconsistently as M, so we can't reliably split winger-vs-midfielder.
    Defensive midfielders thus get a (correctly low) attacking merit_z. Priority GK > F|M > D.
    """
    tokens = set(str(pos).split())
    if "GK" in tokens:
        return "keeper"
    if "F" in tokens or "M" in tokens:
        return "attack"
    if "D" in tokens:
        return "defense"
    return "unknown"


def _season_code(season: str) -> str:
    """'2017-2018' -> Understat season code '1718' (last two digits of each year)."""
    start, end = season.split("-")
    return start[-2:] + end[-2:]


def _zscore_within_group(df: pd.DataFrame, group_cols: list[str], cols: list[str]) -> pd.DataFrame:
    """Add `<col>_z` = z-score of col within each group. Zero-variance/single-row -> 0."""
    out = df.copy()
    grouped = out.groupby(group_cols)
    for col in cols:
        mean = grouped[col].transform("mean")
        std = grouped[col].transform("std")  # sample std (ddof=1)
        out[f"{col}_z"] = ((out[col] - mean) / std).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return out


def _pca(matrix: np.ndarray, n_components: int = 2) -> tuple[np.ndarray, np.ndarray]:
    """Simple PCA via SVD (inputs already standardized). Returns (scores, explained-var ratio)."""
    centered = matrix - matrix.mean(axis=0)
    _, singular, vt = np.linalg.svd(centered, full_matrices=False)
    scores = centered @ vt[:n_components].T
    evr = (singular**2 / (singular**2).sum())[:n_components]
    return scores, evr


def _wavg(values: pd.Series, weights: pd.Series) -> float:
    """Minutes-weighted average over non-NA values; NA if all missing."""
    mask = values.notna()
    if not mask.any() or weights[mask].sum() == 0:
        return np.nan
    return float((values[mask] * weights[mask]).sum() / weights[mask].sum())


def _family_by_award_year(season_df: pd.DataFrame) -> pd.DataFrame:
    """Per (player, award_year) dominant position family (minutes-weighted) from season data.

    Position is leakage-safe (a player's role doesn't depend on the award outcome), so we derive it
    from the full season table — this also keeps the family identical to the rest of the pipeline
    (pool.py uses the same `_position_family` on the same season positions).
    """
    df = season_df[["player", "season", "position", "minutes"]].copy()
    df["position_family"] = df["position"].map(_position_family)
    df["minutes"] = df["minutes"].astype(float)
    s2ay: dict[str, list[int]] = {}
    for award_year, seasons in AWARD_YEAR_SEASONS.items():
        for s in seasons:
            s2ay.setdefault(_season_code(s), []).append(award_year)
    df["award_year"] = df["season"].map(lambda s: s2ay.get(s, []))
    exp = df.explode("award_year").dropna(subset=["award_year"])
    exp["award_year"] = exp["award_year"].astype(int)
    rows: list[dict] = []
    for (player, award_year), g in exp.groupby(["player", "award_year"]):
        rows.append({
            "player": player, "award_year": award_year,
            "position_family": g.loc[g["minutes"].idxmax(), "position_family"],
        })
    return pd.DataFrame(rows, columns=["player", "award_year", "position_family"])


def _window_sum(matches: pd.DataFrame, windows: pd.DataFrame) -> pd.DataFrame:
    """Sum each player's per-match merit metrics + minutes inside each award year's performance
    window (`perf_start`..`perf_end`). Pure / offline-testable — THE leakage-safe aggregation.

    Only award years present in AWARD_YEAR_SEASONS are built (skips 2017, which predates xG data).
    """
    m = matches.copy()
    m["date"] = pd.to_datetime(m["date"])
    metric_cols = [*_VOLUME, "minutes"]
    for c in metric_cols:
        m[c] = m[c].astype(float)
    out: list[pd.DataFrame] = []
    for award_year in AWARD_YEAR_SEASONS:
        if award_year not in windows.index:
            continue
        w = windows.loc[award_year]
        sel = m[(m["date"] >= w["perf_start"]) & (m["date"] <= w["perf_end"])]
        if sel.empty:
            continue
        g = sel.groupby("player", as_index=False)[metric_cols].sum()
        g["award_year"] = int(award_year)
        out.append(g)
    if not out:
        return pd.DataFrame(columns=["player", "award_year", *metric_cols])
    return pd.concat(out, ignore_index=True)


def _attacking_merit(
    window_merit: pd.DataFrame, family: pd.DataFrame
) -> pd.DataFrame:
    """Window-summed metrics + family -> attacking merit (att_merit_z + PCA axes) per award year.

    z-scored within (award_year) over qualifying ATTACK players (>= MIN_MINUTES window minutes),
    then a single pooled PCA for the two axes. Defenders/keepers get NA here (FBref route).
    """
    win = window_merit.merge(family, on=["player", "award_year"], how="left")
    nineties = win["minutes"] / 90.0
    rate_cols = [f"{m}_p90" for m in _RATE]
    for metric, col in zip(_RATE, rate_cols, strict=True):
        win[col] = win[metric] / nineties
    metric_cols = _VOLUME + rate_cols
    win = win.replace([np.inf, -np.inf], np.nan)

    attack = win[
        (win["minutes"] >= MIN_MINUTES) & win["position_family"].isin(_MERIT_FAMILIES)
    ].copy()
    attack = attack.dropna(subset=metric_cols)
    attack = _zscore_within_group(attack, ["award_year"], metric_cols).reset_index(drop=True)
    z_cols = [f"{c}_z" for c in metric_cols]
    attack["merit_z"] = attack[z_cols].mean(axis=1)

    attack["merit_pc1"] = np.nan
    attack["merit_pc2"] = np.nan
    if len(attack) >= 2:
        scores, evr = _pca(attack[z_cols].to_numpy(dtype=float))
        if np.corrcoef(scores[:, 0], attack["merit_z"])[0, 1] < 0:  # orient PC1 = more merit
            scores[:, 0] = -scores[:, 0]
        attack["merit_pc1"] = scores[:, 0]
        attack["merit_pc2"] = scores[:, 1]
        _build_merit.last_pca_evr = tuple(round(float(x), 3) for x in evr)  # for verification

    attack["minutes"] = attack["minutes"].astype(int)
    keep = ["player", "award_year", "position_family",
            "merit_z", "merit_pc1", "merit_pc2", "minutes"]
    return attack[keep].sort_values(
        ["award_year", "merit_z"], ascending=[True, False]
    ).reset_index(drop=True)


# --- defensive merit (FBref) ------------------------------------------------

def _primary_pos(pos: str) -> str:
    """First FBref position token -> {DF, MF, FW, GK, other} ('MF,DF' -> 'MF')."""
    tok = str(pos).split(",")[0].strip()
    return tok if tok in ("DF", "MF", "FW", "GK") else "other"


def _build_defensive_season_merit() -> pd.DataFrame:
    """Per (player, season) defensive merit: 4 actions/90, z within (season, DF|MF), averaged.

    Restricted to DF/MF primary positions (forwards' pressing shouldn't read as 'merit' and beat
    their attacking score via the best-role max; keepers have no metric here).
    """
    d = fbref_defense.pull().copy()
    d["primary_pos"] = d["position"].map(_primary_pos)
    d = d[(d["nineties"] >= DEF_MIN_NINETIES) & d["primary_pos"].isin(_DEF_FAMILIES)].copy()

    rate_cols = [f"{m}_p90" for m in fbref_defense.METRICS]
    for metric, col in zip(fbref_defense.METRICS, rate_cols, strict=True):
        d[col] = d[metric].astype(float) / d["nineties"].astype(float)

    d = _zscore_within_group(d, ["season", "primary_pos"], rate_cols)
    d["def_merit_z"] = d[[f"{c}_z" for c in rate_cols]].mean(axis=1)
    return d[["player", "season", "primary_pos", "nineties", "def_merit_z"]].reset_index(drop=True)


def _defensive_to_award_year(season_def: pd.DataFrame) -> pd.DataFrame:
    """Aggregate defensive season merit to per-award-year (nineties-weighted).

    Uses the leakage-safe COMPLETED season for calendar years (no match logs for FBref → can't
    date-slice; the completed season finished before the ceremony, so it doesn't look ahead).
    """
    rows: list[dict] = []
    for award_year in AWARD_YEAR_SEASONS:
        codes = {_season_code(completed_season(award_year))}
        sub = season_def[season_def["season"].isin(codes)]
        for player, g in sub.groupby("player"):
            total_90 = g["nineties"].sum()
            if total_90 == 0:
                continue
            rows.append(
                {
                    "player_def": player,
                    "award_year": award_year,
                    "def_position": g.loc[g["nineties"].idxmax(), "primary_pos"],
                    "def_merit_z": _wavg(g["def_merit_z"], g["nineties"]),
                    "def_minutes": int(total_90 * 90),
                }
            )
    return pd.DataFrame(rows)


def _build_cb_season_merit() -> pd.DataFrame:
    """Per (player, season) CENTRE-BACK merit: tackle% + aerial-win% + progressive-passes/90,
    z within (season, DF), averaged. EFFICIENCY + ball-playing — see `_CB_SIGNALS`. DF only.
    """
    d = fbref_defense.pull().copy()
    d["primary_pos"] = d["position"].map(_primary_pos)
    d = d[(d["nineties"] >= DEF_MIN_NINETIES) & (d["primary_pos"] == "DF")].copy()
    d["prog_passes_p90"] = d["prog_passes"].astype(float) / d["nineties"].astype(float)
    d = d.dropna(subset=_CB_SIGNALS, how="all")
    d = _zscore_within_group(d, ["season", "primary_pos"], _CB_SIGNALS)
    d["cb_def_z"] = d[[f"{c}_z" for c in _CB_SIGNALS]].mean(axis=1)
    return d[["player", "season", "nineties", "cb_def_z"]].reset_index(drop=True)


def _build_gk_season_merit() -> pd.DataFrame:
    """Per (player, season) KEEPER merit: total PSxG+/- (+ half save%), z within (season, GK).

    PSxG+/- (post-shot xG minus goals allowed) already nets out shot difficulty, so it's not
    inversion-prone. We use the season TOTAL (goals prevented, durability-weighted) — per-90
    over-rewards small samples (a backup over-performing on a handful of shots). PSxG is an advanced
    stat with a 2022/23 Opta gap -> no GK merit that season.
    """
    d = fbref_defense.pull().copy()
    d = d[d["position"].astype(str).str.startswith("GK")]
    d = d[d["nineties"] >= GK_MIN_NINETIES].dropna(subset=["psxg_net"]).copy()
    d = _zscore_within_group(d, ["season"], ["psxg_net", "save_pct"])
    d["gk_merit_z"] = (d["psxg_net_z"] + 0.5 * d["save_pct_z"]) / 1.5
    return d[["player", "season", "nineties", "gk_merit_z"]].reset_index(drop=True)


def _merit_to_award_year(season_df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    """Generic nineties-weighted per-award-year aggregate of one merit signal.

    Calendar years use the leakage-safe COMPLETED season (see `_defensive_to_award_year`).
    """
    rows: list[dict] = []
    for award_year in AWARD_YEAR_SEASONS:
        codes = {_season_code(completed_season(award_year))}
        sub = season_df[season_df["season"].isin(codes)]
        for player, g in sub.groupby("player"):
            total_90 = g["nineties"].sum()
            if total_90 == 0:
                continue
            rows.append(
                {
                    "player": player,
                    "award_year": award_year,
                    value_col: _wavg(g[value_col], g["nineties"]),
                    f"{value_col}_minutes": int(total_90 * 90),
                }
            )
    return pd.DataFrame(rows, columns=["player", "award_year", value_col, f"{value_col}_minutes"])


def _cb_validity_report(cb_ay: pd.DataFrame, anchors: pd.DataFrame) -> dict:
    """Where do consensus-elite CBs land in their award year's DF `cb_def_z` distribution?

    The face-validity gate: a good CB metric must rank the elites high (the volume metric ranked
    Van Dijk '19 / Dias '21 near the BOTTOM). Returns per-anchor percentiles + a pass/fail verdict.
    """
    cb = cb_ay.dropna(subset=["cb_def_z"]).copy()
    cb["key"] = cb["player"].map(awards.name_key)
    cb["pct"] = cb.groupby("award_year")["cb_def_z"].rank(pct=True)
    rows = []
    for r in anchors.itertuples():
        hit = cb[(cb["key"] == awards.name_key(r.player)) & (cb["award_year"] == int(r.award_year))]
        rows.append(
            {
                "player": r.player,
                "award_year": int(r.award_year),
                "percentile": float(hit["pct"].iloc[0]) if len(hit) else None,
            }
        )
    found = [x["percentile"] for x in rows if x["percentile"] is not None]
    pick = lambda nm, yr: next(  # noqa: E731
        (x["percentile"] for x in rows if nm in x["player"] and x["award_year"] == yr), None
    )
    vvd, dias = pick("van Dijk", 2019), pick("Dias", 2021)
    median = float(np.median(found)) if found else None
    share_top_half = (sum(p >= 0.5 for p in found) / len(found)) if found else 0.0
    passed = bool(
        median is not None and median >= 0.75 and share_top_half >= 0.8
        and vvd is not None and vvd >= 0.6 and dias is not None and dias >= 0.6
    )
    return {
        "anchors": rows, "median": median, "share_top_half": share_top_half,
        "vvd_2019": vvd, "dias_2021": dias, "n_found": len(found), "pass": passed,
    }


def _combine_best_role(
    attacking: pd.DataFrame, mf_def: pd.DataFrame, cb: pd.DataFrame, gk: pd.DataFrame,
    *, include_cb: bool = True,
) -> pd.DataFrame:
    """Outer-join the four award-year merit signals on the canonical name key; merit_z = best-role
    max over the player's applicable dims (NaN-skipping). `include_cb=False` keeps the cb_def_z
    column but drops it from merit_z (the checkpoint fallback)."""
    att = attacking.rename(columns={"merit_z": "att_merit_z"}).copy()
    att["key"] = att["player"].map(awards.name_key)
    mf = mf_def.copy()
    mf["key"] = mf["player_def"].map(awards.name_key)
    cbk = cb.rename(columns={"player": "player_cb"}).copy()
    cbk["key"] = cbk["player_cb"].map(awards.name_key)
    gkk = gk.rename(columns={"player": "player_gk"}).copy()
    gkk["key"] = gkk["player_gk"].map(awards.name_key)

    m = (
        att.merge(mf, on=["key", "award_year"], how="outer")
        .merge(cbk, on=["key", "award_year"], how="outer")
        .merge(gkk, on=["key", "award_year"], how="outer")
    )
    m["player"] = m["player"].fillna(m["player_def"]).fillna(m["player_cb"]).fillna(m["player_gk"])

    dims = ["att_merit_z", "def_merit_z", "gk_merit_z"] + (["cb_def_z"] if include_cb else [])
    m["merit_z"] = m[dims].max(axis=1)

    # Family: attacker's (if present), else inferred from the available non-attacking dimension.
    inferred = np.select(
        [m["cb_def_z"].notna(), m["gk_merit_z"].notna(), m["def_merit_z"].notna()],
        ["defense", "keeper", "attack"], default=None,
    )
    m["position_family"] = m["position_family"].where(m["position_family"].notna(), inferred)
    m["minutes"] = (
        m["minutes"].fillna(m["def_minutes"]).fillna(m["cb_def_z_minutes"])
        .fillna(m["gk_merit_z_minutes"]).fillna(0).astype(int)
    )

    cols = ["player", "award_year", "position_family", "merit_z", "att_merit_z",
            "merit_pc1", "merit_pc2", "def_merit_z", "cb_def_z", "gk_merit_z", "minutes"]
    return m[cols].sort_values(
        ["award_year", "merit_z"], ascending=[True, False]
    ).reset_index(drop=True)


# --- build ------------------------------------------------------------------

def _build_merit(windows: pd.DataFrame | None = None) -> pd.DataFrame:
    # Attacking merit from DATE-STAMPED match data, summed over each award year's leakage-safe
    # performance window (no full-season blend → no post-ceremony look-ahead for calendar years).
    # `windows` defaults to the canonical table; the robustness panel passes a stricter one (perf
    # window capped at the ceremony date) to show the ~4-week calendar tail doesn't move merit.
    matches = understat.pull_matches().copy()
    family = _family_by_award_year(understat.pull())
    windows = load_windows() if windows is None else windows
    attacking = _attacking_merit(_window_sum(matches, windows), family)

    mf_def = _defensive_to_award_year(_build_defensive_season_merit())  # MF ball-winning volume
    cb = _merit_to_award_year(_build_cb_season_merit(), "cb_def_z")     # CB efficiency
    gk = _merit_to_award_year(_build_gk_season_merit(), "gk_merit_z")   # GK shot-stopping

    # Face-validity gate (the checkpoint) — does the CB metric rank consensus-elite CBs high?
    anchors = pd.read_csv(REFERENCE_DIR / "cb_validity_anchors.csv")
    _build_merit.cb_validity = _cb_validity_report(cb, anchors)
    _build_merit.cb_gate_passed = _build_merit.cb_validity["pass"]

    return _combine_best_role(attacking, mf_def, cb, gk, include_cb=_CB_MERIT_ENABLED)


def build(*, refresh: bool = False) -> pd.DataFrame:
    """Return per-(player, award_year) merit features (cached)."""
    return cached_frame(CACHE_NAME, _build_merit, refresh=refresh)
