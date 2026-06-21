# Windowing table — performance & hype windows per award year

> Source: per-edition Wikipedia pages (verified 2026-06-18). Dates are exact unless noted.
> Drives data collection — performance stats and hype proxies are both bounded by these.

## The two windows (deliberately asymmetric)

- **Performance window** = the **official eligibility period**. Safe to use in full: a player's
  goals can't spike *because* he's the frontrunner, so performance has no reverse-causality.
- **Hype window** = performance period **truncated at the shortlist-announcement date**.
  Leakage is attention-specific: post-shortlist discourse spikes *because* a winner is
  anticipated (see PROJECT_NOTES guardrail #2). Cut it off at the shortlist.

## Regimes

- **Calendar regime (2017, 2018, 2019, 2021):** period = Jan 1 – Dec 31 of award year.
  Shortlist falls *inside* the period (Oct) → hype window is meaningfully truncated
  (Jan 1 → shortlist). Voting also closes before Dec 31, so the *effective* judged period
  is ~Jan–Oct regardless.
- **Season regime (2022–2025):** period = Aug 1 – ~Jul of the following year (2022 reform).
  Shortlist falls *after* the period ends → **no truncation needed** (the judged season
  closes ~1 month before nominees drop). The reform incidentally de-risked leakage.
- **2020:** award **cancelled (COVID)** → no outcome, dropped from all modeled data.
  Lewandowski 2020 kept only as a qualitative case study.

## Table (spine = 2017–2025)

| Award yr | Regime | Performance window | Hype window (cut at shortlist) | Shortlist date | Ceremony date | Winner |
|---|---|---|---|---|---|---|
| 2017 | calendar | 2017-01-01 → 2017-12-31 | 2017-01-01 → 2017-10-09 | 2017-10-09 | 2017-12-07 | Ronaldo |
| 2018 | calendar | 2018-01-01 → 2018-12-31 | 2018-01-01 → 2018-10-08 | 2018-10-08 | 2018-12-03 | Modrić |
| 2019 | calendar | 2019-01-01 → 2019-12-31 | 2019-01-01 → 2019-10-21 | 2019-10-21 | 2019-12-02 | Messi (6th) |
| 2020 | — | *cancelled (COVID)* | — | — | — | — |
| 2021 | calendar | 2021-01-01 → 2021-12-31 | 2021-01-01 → 2021-10-08 | 2021-10-08 | 2021-11-29 | Messi (7th) |
| 2022 | season | 2021-08-01 → 2022-07-31 | full period (shortlist after end) | 2022-08-12 | 2022-10-17 | Benzema |
| 2023 | season | 2022-08-01 → 2023-07-31 | full period | 2023-09-06 | 2023-10-30 | Messi (8th) |
| 2024 | season | 2023-08-01 → 2024-07-31 | full period | 2024-09-04 | 2024-10-28 | Rodri |
| 2025 | season | 2024-08-01 → 2025-07-13 | full period | 2025-08-07 | 2025-09-22 | Dembélé |

Notes:
- 2025 period ends 2025-07-13 (2025 FIFA Club World Cup final), not end of July.
- 2022 had no summer international tournament (World Cup was Dec 2022 → counts toward 2023).
- Season-regime "full period" hype windows: still cap at shortlist date defensively, but in
  practice the period already ends before it.

## Data-engineering implications (do NOT skip)

1. **Calendar-regime years need match-level data.** A Jan–Dec slice spans *two* FBref
   seasons (e.g. 2018 = back-half of 2017/18 + front-half of 2018/19). FBref season-aggregate
   tables can't produce this — sum **per-match logs** by date, then re-aggregate. The four
   calendar years (2017, 2018, 2019, 2021) cost more to build than the season years.
2. **2017 reaches the xG-data edge.** 2017's window reaches into the 2016/17 season — confirm
   FBref has per-match xG that far back for each top-5 league before committing.
3. **Season-regime years align with FBref season tables** (2022/23 etc.) → cheap. But 2025
   ends mid-July at the Club World Cup, so it includes a few post-season-table matches —
   may still need match-level top-up for that tail.
4. **Add an era indicator** (pre/post-2022) as a model control — the 2022 reform also shrank
   the voter pool (~170 countries → top-100 expert jury), a plausible shift in hype-sensitivity.

## Confirmed winners (for outcome join sanity check)
2017 Ronaldo · 2018 Modrić · 2019 Messi · 2021 Messi · 2022 Benzema · 2023 Messi ·
2024 Rodri · 2025 Dembélé.
