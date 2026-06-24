"""Pipeline orchestrator — the executable table of contents.

Lists the project's stages in dependency order and runs them. Unimplemented stages report
as STUB rather than crashing the listing. This is intentionally thin: the real work lives in
the bdor package; this just wires the stages together.

Usage:
    python run.py            # list stages and their status
    python run.py --list     # same
    python run.py <stage>    # run a single stage (e.g. `python run.py awards`)
"""

from __future__ import annotations

import sys

from bdor import features, models, report
from bdor.config import ensure_dirs
from bdor.data import (
    awards,
    fbref_defense,
    fotmob,
    gdelt,
    gdelt_bq,
    pageviews,
    statsbomb,
    understat,
    wikidata,
)
from bdor.features import pool
from bdor.models import robustness

# (stage name, description, callable). Order = dependency order.
# Pulls needing args (player lists) are listed but not directly runnable yet — they come
# online once `awards` defines the player universe.
STAGES = [
    ("awards", "Ballon d'Or vote points per finisher (join target)", awards.pull),
    ("understat", "Top-5-league player-season performance stats (xG)", understat.pull),
    ("understat_match", "Date-stamped per-match merit inputs (leakage-safe windows)",
     understat.pull_matches),
    ("wikidata", "Language sitelinks + name aliases per player", wikidata.pull),
    ("pageviews", "All-language daily Wikipedia pageviews", pageviews.pull),
    ("gdelt", "Disambiguated global news volume (DOC 2.0 API)", gdelt.pull),
    ("gdelt_bq", "Global news volume via BigQuery GKG (free sandbox; DOC-API alternative)",
     gdelt_bq.build),
    ("fotmob", "Season-avg FotMob (Opta) player ratings — merit cross-check, not a spine input",
     fotmob.pull),
    ("statsbomb", "Semifinalist tournament squads (Tier-2 pool 3rd source)", statsbomb.pull),
    ("fbref_defense", "Cross-league defensive actions (def. merit)", fbref_defense.pull),
    ("features", "Build merit index + H-perp (residualised hype)", features.build),
    ("pool", "Tier-2 candidate pool (production u team-success)", pool.build),
    ("models", "Stage-A nomination + Stage-B placement (PyMC/bambi)", models.run),
    ("robustness", "H-perp coefficient-stability panel (frequentist)", robustness.build),
    ("report", "Generate writeup figures (Quarto reads report/ballon-dor.qmd)", report.run),
]

# Stages with a working implementation. Listed explicitly so `--list` never has to *call*
# a stage to learn its status (calling a pull() would hit the network).
IMPLEMENTED = {
    "awards", "understat", "understat_match", "wikidata", "pageviews", "gdelt", "gdelt_bq",
    "fotmob", "statsbomb", "fbref_defense", "features", "pool", "models", "robustness", "report",
}


def list_stages() -> None:
    print("Ballon d'Or pipeline - stages (dependency order):\n")
    for name, desc, _fn in STAGES:
        status = "ready" if name in IMPLEMENTED else "STUB"
        print(f"  [{status:>5}]  {name:<10} {desc}")
    print("\nRun one with:  python run.py <stage>")


def run_stage(name: str) -> None:
    match = next((s for s in STAGES if s[0] == name), None)
    if match is None:
        print(f"unknown stage: {name!r}")
        print("known:", ", ".join(s[0] for s in STAGES))
        raise SystemExit(2)
    _, _, fn = match
    if fn is None:
        print(f"stage {name!r} is not yet runnable from run.py (needs upstream inputs).")
        raise SystemExit(1)
    df = fn()
    print(f"{name}: {len(df)} rows")


def main(argv: list[str]) -> None:
    ensure_dirs()
    args = argv[1:]
    if not args or args[0] in ("--list", "-l", "list"):
        list_stages()
        return
    run_stage(args[0])


if __name__ == "__main__":
    main(sys.argv)
