"""Project-wide constants and paths.

The *why* behind each constant lives in PROJECT_NOTES.md — this module is just the
single source of truth so nothing downstream hardcodes a path or a year list.
"""

from __future__ import annotations

from pathlib import Path

# Repo root = three parents up from this file (src/bdor/config.py -> repo root).
BASE_DIR: Path = Path(__file__).resolve().parents[2]

DATA_DIR: Path = BASE_DIR / "data"
RAW_DIR: Path = DATA_DIR / "raw"
CACHE_DIR: Path = DATA_DIR / "cache"
PROCESSED_DIR: Path = DATA_DIR / "processed"
REFERENCE_DIR: Path = DATA_DIR / "reference"

DOCS_DIR: Path = BASE_DIR / "docs"

# The modeled "spine": full-feature award years only.
# 2020 excluded — award cancelled (COVID), no outcome.
# 2017 dropped from the spine — FBref xG only exists from 2017-18, so the 2017 award
#   (its Jan-May half falls in the xG-less 2016-17 season) can't get full features. With
#   2017 out, all 8 needed FBref seasons are xG-clean. See PROJECT_NOTES.md "spine".
SPINE_YEARS: list[int] = [2018, 2019, 2021, 2022, 2023, 2024, 2025]

# Outcome (awards) years we scrape: the spine PLUS 2017 as a degraded/qualitative panel.
AWARD_YEARS: list[int] = [2017, *SPINE_YEARS]

# Football seasons the spine needs (8; all have xG via Understat). soccerdata accepts this
# format via its SeasonCode parser (verified: "2017-2018" -> season_id 2017).
PERF_SEASONS: list[str] = [
    "2017-2018",
    "2018-2019",
    "2019-2020",
    "2020-2021",
    "2021-2022",
    "2022-2023",
    "2023-2024",
    "2024-2025",
]

# Performance source = Understat (FBref dropped — no longer serves advanced stats publicly
# as of 2026-06). These league IDs are verified against soccerdata.Understat.read_leagues().
UNDERSTAT_LEAGUES: list[str] = [
    "ENG-Premier League",
    "ESP-La Liga",
    "ITA-Serie A",
    "GER-Bundesliga",
    "FRA-Ligue 1",
]

# Which football season(s) each award year draws on. Calendar-regime years (2018/2019/2021)
# span TWO seasons -> calendar-year construction is deferred to feature-build (per-90
# weighted avg recommended). Season-regime years map 1:1.
AWARD_YEAR_SEASONS: dict[int, list[str]] = {
    2018: ["2017-2018", "2018-2019"],
    2019: ["2018-2019", "2019-2020"],
    2021: ["2020-2021", "2021-2022"],
    2022: ["2021-2022"],
    2023: ["2022-2023"],
    2024: ["2023-2024"],
    2025: ["2024-2025"],
}

# Award-eligibility regimes (see docs/windowing.md).
#   calendar : Jan-Dec of the award year (2017-2021)   -> award year spans TWO football seasons
#   season   : Aug-Jul football season (2022 reform on) -> award year maps to one season
CALENDAR_REGIME_YEARS: list[int] = [2017, 2018, 2019, 2021]
SEASON_REGIME_YEARS: list[int] = [2022, 2023, 2024, 2025]

# Canonical reference table of per-year windows (committed to git).
AWARD_WINDOWS_CSV: Path = REFERENCE_DIR / "award_windows.csv"


def completed_season(award_year: int) -> str:
    """The most-recent football season that FINISHED on/before the ceremony — the leakage-safe
    season for any season-aggregate feature (club trophies, FBref defensive merit).

    Calendar-regime award years span two seasons; the *second* one ends the following summer,
    i.e. AFTER the ceremony, so crediting it is look-ahead. We keep only the season whose end
    year equals the award year (2019 -> 2018-2019, decided by ~May 2019, inside the window).
    Season-regime years map 1:1, so this returns their single season unchanged. See
    docs/windowing.md (the perf window) + docs/decisions-log.md (the leakage fix).
    """
    seasons = AWARD_YEAR_SEASONS[award_year]
    for s in seasons:
        if int(s.split("-")[1]) == award_year:
            return s
    return seasons[-1]


def ensure_dirs() -> None:
    """Create the gitignored data subdirectories if missing (idempotent)."""
    for d in (RAW_DIR, CACHE_DIR, PROCESSED_DIR, REFERENCE_DIR):
        d.mkdir(parents=True, exist_ok=True)
