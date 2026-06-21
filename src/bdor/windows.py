"""Award-window reference table loader.

The per-year performance and hype windows are canonical project data, derived once from
docs/windowing.md and stored in data/reference/award_windows.csv. Everything that bounds a
pull by date (performance stats, pageviews, GDELT) reads them from here so the windowing
rules live in exactly one place.

See docs/windowing.md for the rationale (two windows, two regimes, the shortlist leakage cut).
"""

from __future__ import annotations

import pandas as pd

from .config import AWARD_WINDOWS_CSV

_DATE_COLS = ["perf_start", "perf_end", "hype_cut", "ceremony_date"]


def load_windows() -> pd.DataFrame:
    """Load the award-window table with parsed dates, indexed by award_year.

    Columns: regime, perf_start, perf_end, hype_cut (shortlist date), ceremony_date, winner.
    """
    df = pd.read_csv(AWARD_WINDOWS_CSV, parse_dates=_DATE_COLS)
    return df.set_index("award_year").sort_index()


def window_for(award_year: int) -> pd.Series:
    """Return the single-row window record for one award year."""
    windows = load_windows()
    if award_year not in windows.index:
        raise KeyError(
            f"award_year {award_year} not in spine; have {list(windows.index)}"
        )
    return windows.loc[award_year]
