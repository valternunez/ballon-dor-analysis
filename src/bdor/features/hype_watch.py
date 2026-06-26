"""2026 Hype-Watch — a forward-looking, PRE-CEREMONY teaser (NOT a modelled award year).

Fully isolated from the study: this never touches `config.SPINE_YEARS`, the gate models, the de-fame
regressors, or the published H⊥ / leaderboard. It produces a *provisional* "attention beyond merit"
ranking for 2026 **attackers**, from the completed 2025-26 club season plus a **pre-World-Cup**
attention window. The de-fame is fit WITHIN the 2026 field (its own fame/merit/team relationship),
so the score compares *within* 2026 but is NOT on the study's pool-wide scale.

Honest limitations (surfaced on the site):
  * **No outcome.** The 2026 shortlist (~Aug) + ceremony (~Sept/Oct) haven't happened — this touches
    neither gate; it is the descriptive residual only.
  * **Pre-World-Cup.** The window ends 2026-06-10; the WC (from 2026-06-11) — the biggest historical
    driver of Ballon d'Or narrative — is excluded and will reshape this.
  * **Attackers only.** 2025-26 has Understat attacking merit but no FBref defensive reference.
  * **Team success is a proxy** (team attacking output), not curated trophies — final 2025-26
    standings / CL results aren't curated here, so we de-fame on a data-derived team-strength
    signal rather than fabricating titles.

Data goes to SEPARATE caches (`understat_2526_seasons`, `pageviews_2026_hypewatch`) so the study's
caches are never refreshed by this teaser.
"""

from __future__ import annotations

from functools import partial

import numpy as np
import pandas as pd
import soccerdata

from ..cache import cached_frame, cached_records
from ..config import RAW_DIR, UNDERSTAT_LEAGUES
from ..data import pageviews, wikidata
from ..data.understat import _standardize
from . import hperp, hype, merit

SEASON = "2025-2026"
WINDOW_START = pd.Timestamp("2025-08-01")
SNAPSHOT = pd.Timestamp("2026-06-10")  # window end — pre-WC cut (the WC kicks off 2026-06-11)
SNAPSHOT_LABEL = "10 June 2026"
PV_START = "20240101"  # back far enough for a trailing-12mo baseline before WINDOW_START
PV_END = "20260610"
TOP_N = 40
MIN_MINUTES = 1200  # single-season floor (a touch below the study's 1500 to keep the field full)
# Keep only attackers with an established following (>= the field-median baseline), so a breakout's
# attention spike from a near-zero base can't dominate — this is hype among players already on the
# radar, not the study's low-baseline artifact. Mirrors the spirit of hype._LOW_BASELINE.
_BASELINE_FLOOR_FRAC = 1.0  # floor = frac x field-median baseline

SEASON_CACHE = "understat_2526_seasons"
PV_CACHE = "pageviews_2026_hypewatch"
CACHE_NAME = "hype_watch_2026"

# Within-field de-fame: attention beyond fame (baseline) + attacking merit + team context.
_DEFAME = ["log_baseline", "att_merit_z", "team_strength_z"]
_OUT_COLS = ["player", "team", "goals", "assists", "att_merit_z",
             "window_mean", "baseline", "h_perp_2026"]
# Understat legal-name spellings → the common display name (only the awkward ones).
_DISPLAY = {"Kylian Mbappe-Lottin": "Kylian Mbappé"}
_TEAM_DISPLAY = {"RasenBallsport Leipzig": "RB Leipzig"}


# --- 2025-26 season pull (separate cache) ------------------------------------

def _pull_season() -> pd.DataFrame:
    def _build() -> pd.DataFrame:
        reader = soccerdata.Understat(
            leagues=UNDERSTAT_LEAGUES, seasons=[SEASON], data_dir=RAW_DIR / "understat"
        )
        return _standardize(reader.read_player_season_stats().reset_index())

    return cached_frame(SEASON_CACHE, _build)


# --- attacking merit, season-level (mirrors merit._attacking_merit, one field) ----

def _attacking_merit(season: pd.DataFrame) -> pd.DataFrame:
    """Per-player attacking merit z-scored within the 2025-26 attacking field. Pure-ish."""
    df = season.copy()
    df["position_family"] = df["position"].map(merit._position_family)
    df["minutes"] = df["minutes"].astype(float)
    nineties = df["minutes"] / 90.0
    rate_cols = [f"{m}_p90" for m in merit._RATE]
    for metric, col in zip(merit._RATE, rate_cols, strict=True):
        df[col] = df[metric].astype(float) / nineties
    metric_cols = merit._VOLUME + rate_cols
    df = df.replace([np.inf, -np.inf], np.nan)

    att = df[(df["minutes"] >= MIN_MINUTES) & (df["position_family"] == "attack")].copy()
    att = att.dropna(subset=metric_cols)
    att["__field"] = 0  # single group → z within the whole 2026 attacking field
    att = merit._zscore_within_group(att, ["__field"], metric_cols)
    z_cols = [f"{c}_z" for c in metric_cols]
    att["att_merit_z"] = att[z_cols].mean(axis=1)
    return att


def _team_strength(season: pd.DataFrame) -> pd.Series:
    """Team total (npxg + xag) over 2025-26 — a data-derived team-context proxy (no trophies)."""
    s = season.copy()
    s["_c"] = s["npxg"].astype(float) + s["xag"].astype(float)
    return s.groupby("team")["_c"].sum().rename("team_strength")


# --- 2026 attention pull (separate cache, custom date range) ------------------

def _fetch_article(player: str, lang: str, title: str) -> pd.DataFrame:
    """One language edition over the 2026 window range; reuses the pageviews fetch primitives."""
    url = (
        f"{pageviews._PV_API}/{lang}.wikipedia/all-access/all-agents/"
        f"{pageviews._encode_title(title)}/daily/{PV_START}/{PV_END}"
    )
    resp = pageviews._request(url)
    if resp is None:
        return pageviews._empty()
    items = resp.json().get("items", [])
    if not items:
        return pageviews._empty()
    df = pd.DataFrame(items)
    df["player"] = player
    df["lang"] = lang
    df["date"] = pd.to_datetime(df["timestamp"].str[:8], format="%Y%m%d")
    return df[pageviews._OUT_COLS]


def _fetch_player(player: str, *, sitelinks: dict[str, list[tuple[str, str]]]) -> pd.DataFrame:
    frames = [_fetch_article(player, lang, title) for lang, title in sitelinks.get(player, [])]
    frames = [f for f in frames if not f.empty]
    return pd.concat(frames, ignore_index=True) if frames else pageviews._empty()


def _pull_pageviews(players: list[str]) -> pd.DataFrame:
    def _build() -> pd.DataFrame:
        sl = wikidata.pull(players)
        sl = sl[sl["kind"] == "sitelink"]
        sitelinks = {
            p: list(zip(g["key"], g["value"], strict=False)) for p, g in sl.groupby("player")
        }
        universe = sorted(sitelinks)
        per_lang = cached_records(
            f"{PV_CACHE}_by_lang", universe, partial(_fetch_player, sitelinks=sitelinks)
        )
        return pageviews._aggregate_all_lang(per_lang)

    return cached_frame(PV_CACHE, _build)


def _window_attention(daily: pd.DataFrame) -> pd.DataFrame:
    """Per player: mean daily views over the window + trailing-12mo baseline before it."""
    rows = []
    for player, pdaily in daily.groupby("player"):
        rows.append({
            "player": player,
            "window_mean": hype._window_mean(pdaily, WINDOW_START, SNAPSHOT, "views"),
            "baseline": hype._baseline_median(pdaily, WINDOW_START, "views"),
        })
    return pd.DataFrame(rows, columns=["player", "window_mean", "baseline"])


# --- de-fame (within the 2026 field) -----------------------------------------

def _defame(frame: pd.DataFrame) -> pd.DataFrame:
    """h_perp_2026 = residual of log(window attention) on log(baseline) + merit + team strength."""
    f = frame.copy()
    f["log_baseline"] = np.log1p(f["baseline"].astype(float))
    f["log_window"] = np.log1p(f["window_mean"].astype(float))
    f["h_perp_2026"] = np.nan
    complete = f.dropna(subset=["log_window", *_DEFAME])
    if len(complete) > len(_DEFAME) + 1:
        y = complete["log_window"].to_numpy(dtype=float)
        x = np.column_stack([np.ones(len(complete)), complete[_DEFAME].to_numpy(dtype=float)])
        resid, _beta, _r2 = hperp._ols_residual(y, x)
        f.loc[complete.index, "h_perp_2026"] = resid
    return f


def build(*, refresh: bool = False) -> pd.DataFrame:
    """Build (and cache) the provisional 2026 Hype-Watch leaderboard. NETWORK on first run."""
    def _producer() -> pd.DataFrame:
        season = _pull_season()
        att = _attacking_merit(season).merge(_team_strength(season), on="team", how="left")
        pool = att.sort_values("att_merit_z", ascending=False).head(TOP_N).copy()

        daily = _pull_pageviews(sorted(pool["player"].unique()))
        frame = pool.merge(_window_attention(daily), on="player", how="left")
        frame = frame.dropna(subset=["baseline", "window_mean"])
        # established-following floor (drops thin-baseline breakouts whose residual is unreliable)
        frame = frame[frame["baseline"] >= _BASELINE_FLOOR_FRAC * frame["baseline"].median()].copy()

        ts = frame["team_strength"].astype(float)
        frame["team_strength_z"] = ((ts - ts.mean()) / ts.std(ddof=0)).fillna(0.0)
        frame = _defame(frame)

        out = frame[frame["h_perp_2026"].notna()][_OUT_COLS].copy()
        out["player"] = out["player"].replace(_DISPLAY)
        out["team"] = out["team"].replace(_TEAM_DISPLAY)
        return out.sort_values("h_perp_2026", ascending=False).reset_index(drop=True)

    return cached_frame(CACHE_NAME, _producer, refresh=refresh)
