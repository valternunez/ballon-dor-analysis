"""Tier-2 candidate pool — the universe the Stage-A nomination model runs over.

Stage A asks: of everyone who plausibly *could* have been shortlisted, who made the Ballon d'Or
30? That needs a candidate universe wider than the 30 — the "snubbed should-have-beens" are the
counterfactual. Per PROJECT_NOTES "Tier 2 candidate pool", inclusion is a UNION of merit/team-based
sources, **never attention-based** (testing hype within the pool must not bake in the answer):

  * **Production pool** — the top-N attackers by `merit_z` each award year (merit_z already fuses
    the locked rate+volume signal; Understat can't reliably split winger vs central-mid, so this is
    one attacking stratum rather than the FBref-era two — see decisions log).
  * **Team-success pool** — significant-minutes players on Champions League semifinalists
    (`cl_round >= 3`) and domestic-league champions. This is the ONLY route for defenders & keepers
    (no individual Understat merit).

The two are unioned and deduped per (player, award_year), every member gets club-based team-success
+ merit features attached, and the row is labelled `nominated` (in the 30) by a normalised-name join
to the awards table. **A nominee the sources miss is NOT added back** (that would be outcome-based
inclusion) — instead `pool_diagnostics` reports per-year nominee *recall* as a quality check.
"""

from __future__ import annotations

import pandas as pd

from ..cache import cached_frame
from ..config import AWARD_YEAR_SEASONS, REFERENCE_DIR, SPINE_YEARS
from ..data import awards, statsbomb, understat
from . import merit, team_success
from .merit import _position_family, _season_code

CACHE_NAME = "tier2_pool"
PRODUCTION_TOP_N = 50  # top attackers by merit_z per award year (tunable to ~80-120/yr pool target)
TEAM_SUCCESS_MIN_MINUTES = 900  # "significant minutes" floor for a CL-run / title squad member
TOURNAMENT_MIN_MINUTES = 150  # significant tournament minutes for a semifinalist-squad member

_FEATURE_COLS = [
    "player", "award_year", "position_family",
    "in_production", "in_team_success", "in_tournament",
    "merit_z", "merit_pc1", "merit_pc2", "minutes",
    "cl_round", "won_cl", "won_league", "nation", "tournament_result",
    "tournament_overachievement", "nominated",
]


# --- pure helpers (offline-testable) ----------------------------------------

def _season_to_award_years() -> dict[str, list[int]]:
    """Understat season code -> the award year(s) that draw on it (calendar years span two)."""
    out: dict[str, list[int]] = {}
    for award_year, seasons in AWARD_YEAR_SEASONS.items():
        for s in seasons:
            out.setdefault(_season_code(s), []).append(award_year)
    return out


def _production_pool(mer: pd.DataFrame, top_n: int = PRODUCTION_TOP_N) -> pd.DataFrame:
    """Top-N attackers by ATTACKING merit per award year → (player, award_year, in_production).

    Ranks on `att_merit_z`, not the best-role `merit_z`: the production stratum is the attacking
    universe, and a high best-role score for a bad-team destroyer (defensive-volume merit) shouldn't
    pull journeyman mids into it. Defenders/ball-winners enter via team-success / tournament.
    """
    ranked = mer.dropna(subset=["att_merit_z"]).sort_values(
        ["award_year", "att_merit_z"], ascending=[True, False]
    )
    top = ranked.groupby("award_year", group_keys=False).head(top_n)
    return top[["player", "award_year"]].assign(in_production=True).reset_index(drop=True)


def _team_success_pool(
    us: pd.DataFrame, qualifying: set[tuple[str, str]], min_minutes: int = TEAM_SUCCESS_MIN_MINUTES
) -> pd.DataFrame:
    """Significant-minutes players on qualifying (season, club) -> team-success pool rows.

    `qualifying` = the set of (season_code, reference-club-spelling) that reached a CL semifinal or
    won a domestic league. Understat team spellings are aliased to the reference spelling first.
    """
    s2ay = _season_to_award_years()
    df = us[["player", "season", "team", "minutes"]].copy()
    df["club"] = df["team"].map(lambda t: team_success._US_ALIASES.get(t, t))
    df["minutes"] = df["minutes"].astype(float)
    elig = df[df["minutes"] >= min_minutes]

    rows: list[dict] = []
    for r in elig.itertuples():
        if (r.season, r.club) in qualifying:
            for award_year in s2ay.get(r.season, []):
                rows.append({"player": r.player, "award_year": award_year})
    if not rows:
        return pd.DataFrame(columns=["player", "award_year", "in_team_success"])
    out = pd.DataFrame(rows).drop_duplicates().reset_index(drop=True)
    out["in_team_success"] = True
    return out


def _union_sources(production: pd.DataFrame, team_success_pool: pd.DataFrame) -> pd.DataFrame:
    """Outer-union the two source lists on (player, award_year); fill missing source flags False."""
    u = production.merge(team_success_pool, on=["player", "award_year"], how="outer")
    u["in_production"] = u["in_production"].fillna(False).astype(bool)
    u["in_team_success"] = u["in_team_success"].fillna(False).astype(bool)
    return u


def _us_award_year(us: pd.DataFrame) -> pd.DataFrame:
    """Per (player, award_year): total minutes, dominant position family, and the set of clubs.

    Serves both the team-success club lookup and the position/minutes fallback for pool members
    below the merit minutes floor (who are absent from merit.build()).
    """
    s2ay = _season_to_award_years()
    df = us[["player", "season", "team", "position", "minutes"]].copy()
    df["club"] = df["team"].map(lambda t: team_success._US_ALIASES.get(t, t))
    df["position_family"] = df["position"].map(_position_family)
    df["minutes"] = df["minutes"].astype(float)
    df["award_year"] = df["season"].map(lambda s: s2ay.get(s, []))
    exp = df.explode("award_year").dropna(subset=["award_year"])
    exp["award_year"] = exp["award_year"].astype(int)

    rows: list[dict] = []
    for (player, award_year), g in exp.groupby(["player", "award_year"]):
        rows.append(
            {
                "player": player,
                "award_year": award_year,
                "us_minutes": int(g["minutes"].sum()),
                "us_family": g.loc[g["minutes"].idxmax(), "position_family"],
                "clubs": set(g["club"]),
            }
        )
    return pd.DataFrame(rows)


# --- build ------------------------------------------------------------------

def _qualifying_club_seasons() -> set[tuple[str, str]]:
    """(season_code, reference-club) that reached a CL semifinal or won a domestic league."""
    cl_lookup, champs, _tourn, _nation, _overach = team_success._load_references()
    cl_sf = {key for key, rnd in cl_lookup.items() if rnd >= 3}
    return cl_sf | set(champs)


def _tournament_pool(sb: pd.DataFrame, min_minutes: int = TOURNAMENT_MIN_MINUTES) -> pd.DataFrame:
    """Semifinalist-squad players with significant tournament minutes (StatsBomb names)."""
    elig = sb[sb["minutes"] >= min_minutes][["player", "award_year"]].drop_duplicates()
    return elig.assign(in_tournament=True).reset_index(drop=True)


def _nation_map(sb: pd.DataFrame) -> dict[str, str]:
    """Canonical-name-key -> nation, from the curated finisher CSV plus the StatsBomb squads."""
    nat = pd.read_csv(REFERENCE_DIR / "player_nation.csv")
    m = {awards.name_key(p): n for p, n in zip(nat["player"], nat["nation"], strict=True)}
    for p, n in zip(sb["player"], sb["nation"], strict=True):
        m.setdefault(awards.name_key(p), n)  # curated finisher wins; StatsBomb fills the rest
    return m


def _build_pool() -> pd.DataFrame:
    mer = merit.build()
    us = understat.pull()
    sb = statsbomb.pull()

    # Understat-derived sources share a spelling, so a raw-name union is safe; then fold in the
    # tournament source on the canonical name key (StatsBomb uses full legal names).
    upool = _union_sources(
        _production_pool(mer, PRODUCTION_TOP_N),
        _team_success_pool(us, _qualifying_club_seasons(), TEAM_SUCCESS_MIN_MINUTES),
    )
    upool["player_key"] = upool["player"].map(awards.name_key)
    tpool = _tournament_pool(sb)
    tpool["player_key"] = tpool["player"].map(awards.name_key)

    pool = upool.merge(
        tpool.rename(columns={"player": "player_sb"}), on=["player_key", "award_year"], how="outer"
    )
    pool["player"] = pool["player"].fillna(pool["player_sb"])  # StatsBomb name for tournament-only
    for flag in ("in_production", "in_team_success", "in_tournament"):
        pool[flag] = pool[flag].fillna(False).astype(bool)

    # Understat aggregate (clubs + position/minutes fallback) on the canonical key.
    usa = _us_award_year(us)
    usa["player_key"] = usa["player"].map(awards.name_key)
    pool = pool.merge(usa.drop(columns=["player"]), on=["player_key", "award_year"], how="left")

    # Club-based team-success for EVERY member (team_success.build() is finisher-only).
    cl_lookup, champs, tourn, _nation, overach = team_success._load_references()

    def _club_success(row: pd.Series) -> pd.Series:
        seasons = team_success._season_codes(int(row["award_year"]))
        clubs = list(row["clubs"]) if isinstance(row["clubs"], set) else []
        cl_round = team_success._club_cl_round(clubs, seasons, cl_lookup)
        return pd.Series({"cl_round": cl_round, "won_cl": cl_round == 5,
                          "won_league": team_success._won_league(clubs, seasons, champs)})

    pool[["cl_round", "won_cl", "won_league"]] = pool.apply(_club_success, axis=1)

    # Merit features (NA for non-attackers / below-floor); position/minutes fall back to Understat
    # then to "other" for tournament-only members (no Understat presence).
    merk = mer.copy()
    merk["player_key"] = merk["player"].map(awards.name_key)
    pool = pool.merge(
        merk[["player_key", "award_year", "merit_z", "merit_pc1", "merit_pc2",
              "position_family", "minutes"]],
        on=["player_key", "award_year"], how="left",
    )
    pool["position_family"] = pool["position_family"].fillna(pool["us_family"]).fillna("other")
    pool["minutes"] = pool["minutes"].fillna(pool["us_minutes"]).fillna(0).astype(int)

    # Nation + national-team tournament result, now known pool-wide (not just finishers).
    nat = _nation_map(sb)
    pool["nation"] = pool["player_key"].map(nat)
    pool["tournament_result"] = [
        team_success._tournament_result(n if isinstance(n, str) else None, int(ay), tourn)
        for n, ay in zip(pool["nation"], pool["award_year"], strict=True)
    ]
    # Overachievement vs pre-tournament seed (de-fame robustness control; 0 if no/par run).
    pool["tournament_overachievement"] = [
        team_success._tournament_overachievement(
            n if isinstance(n, str) else None, int(ay), overach)
        for n, ay in zip(pool["nation"], pool["award_year"], strict=True)
    ]

    pool["nominated"] = _nominated_mask(pool)
    return pool[_FEATURE_COLS].sort_values(
        ["award_year", "nominated", "merit_z"], ascending=[True, False, False]
    ).reset_index(drop=True)


def _nominated_mask(pool: pd.DataFrame) -> pd.Series:
    """True where (award_year, normalised player) is in the awards 30-man shortlist."""
    aw = awards.pull()
    nominated = {(int(r.award_year), r.player_norm) for r in aw.itertuples()}
    norm = pool["player"].map(awards.name_key)
    return [
        (int(ay), nm) in nominated for ay, nm in zip(pool["award_year"], norm, strict=True)
    ]


def build(*, refresh: bool = False) -> pd.DataFrame:
    """Return the cached Tier-2 candidate pool (one row per (player, award_year))."""
    return cached_frame(CACHE_NAME, _build_pool, refresh=refresh)


def _dedupe_universe(finisher_names, pool_names) -> list[str]:
    """Dedupe finishers ∪ pool by `awards.name_key`; the finisher (first-listed) spelling wins."""
    by_key: dict[str, str] = {}
    for name in finisher_names:  # awards spellings first -> preferred display
        by_key.setdefault(awards.name_key(name), name)
    for name in pool_names:  # pool members only added if their key is new
        by_key.setdefault(awards.name_key(name), name)
    return sorted(by_key.values())


def pool_universe() -> list[str]:
    """Player names to pull attention for: awards finishers ∪ the pool, deduped by canonical key.

    Where a player appears in both (most nominees), the **awards spelling is preferred** so we reuse
    the already-cached finisher pageview shards and don't re-pull the same person under the
    Understat spelling (e.g. Mbappé). Pool-only players keep their Understat spelling. Feeds the
    pool-wide pageviews/wikidata pull and the attention build.
    """
    return _dedupe_universe(awards.pull()["player"].dropna(), build()["player"].dropna())


def pool_diagnostics(pool: pd.DataFrame | None = None) -> dict:
    """Size per year + per-year nominee recall (share of the 30 the sources recover)."""
    if pool is None:
        pool = build()
    aw = awards.pull()
    norm = pool["player"].map(awards.name_key)
    pool_keys = set(zip(pool["award_year"], norm, strict=True))

    size_per_year = pool.groupby("award_year").size().to_dict()
    recall = {}
    for year in SPINE_YEARS:
        noms = aw[aw["award_year"] == year]
        if noms.empty:
            continue
        hit = sum((year, nm) in pool_keys for nm in noms["player_norm"])
        recall[year] = (hit, len(noms))
    return {
        "n_total": len(pool),
        "size_per_year": size_per_year,
        "nominee_recall": recall,
        "n_nominated_in_pool": int(pool["nominated"].sum()),
    }
