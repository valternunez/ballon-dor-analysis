# The Ballon d'Or rewards goals. It also rewards stories.

Does the Ballon d'Or reward on-pitch production, or narrative? This project asks the honest,
**conditional** version of that question:

> Does media attention have *independent* explanatory power for the award **after controlling for**
> what a player did on the pitch and how their team performed?

It's an **interpretation project, not a prediction one** (seven award years, 2018–2025; ~210
finisher-seasons modelled). The central quantity is **H⊥ ("Hype Score")** — the slice of a player's
attention that merit, baseline fame, and team success *don't* explain (a regression residual).

## The finding

The award is two decisions, so we test the Hype-Score question at each gate:

| Gate | question | H⊥ effect (per SD, 94% interval) | in plain terms |
|---|---|---|---|
| **A — nomination** | do you make the 30-man shortlist? | **+0.73** [0.53, 0.95], P>0 = 1.00 | ≈ **doubles** the odds of being shortlisted (~+9 pts of probability) |
| **B — placement** | given you're in, do you finish higher? | **+0.15** [0.02, 0.28], P>0 = 0.98 | adds only ~16% to the odds |

**The bias is in who gets *considered*, not who wins** — narrative's pull on nomination is ~5× its
pull on placement. Gate A is rock-solid across every robustness check; Gate B is real but modest and
duopoly-sensitive. See [`docs/findings.md`](docs/findings.md) for the full results log and
[`docs/decisions-log.md`](docs/decisions-log.md) for the war stories (including the merit-window
leakage fix). The locked methodology lives in [`PROJECT_NOTES.md`](PROJECT_NOTES.md); the per-year
performance/hype windows in [`docs/windowing.md`](docs/windowing.md).

## Deliverables

- **Public site** — `site/index.html`: a self-contained D3 scrollytelling piece (open it directly).
- **Technical report** — `report/ballon-dor.qmd` → `report/ballon-dor.html` (Quarto; regenerate, see below).

## Repo layout

```
src/bdor/
  config.py            Locked constants (spine years, paths, the leakage-safe completed_season rule).
  cache.py             Cache-first helpers (frame-level + resumable row-level). The heart.
  windows.py           Loads the award-window reference table.
  data/                One module per source: awards, understat (season + match-level), pageviews,
                       wikidata, gdelt, statsbomb, fbref_defense.
  features/            merit (date-windowed), team_success, pool (Tier-2), attention, hype, hperp (H⊥).
  models/              nomination (Gate A), placement (Gate B), robustness panel, _report helpers.
  report.py            Figures + result loaders for the Quarto writeup and the site data export.
data/reference/        Checked-in canonical data (award_windows.csv, CL/league/tournament results, …).
data/raw|cache/        Pulled/derived data (gitignored — parquet + raw JSON; rebuild from the pulls).
site/                  Public scrollytelling site (index.html + app.js + styles.css + data.js + vendored libs).
report/                Quarto writeup (.qmd) + exported figure PNGs.
tests/                 Offline unit tests (pure helpers on synthetic data; no network).
run.py                 Pipeline orchestrator — stages in dependency order.
```

## Setup

Requires **Python 3.12** (PyMC/pytensor lag newer releases).

```bash
py -3.12 -m venv .venv
source .venv/Scripts/activate          # Windows Git Bash;  .venv\Scripts\activate on cmd/PowerShell
pip install -e ".[model,report,statsbomb,fbref,dev]"
```

The Bayesian models sample with **nutpie** (numba NUTS) — no C compiler needed on Windows.

## Reproduce

```bash
python run.py --list                   # show all stages in dependency order
python run.py awards understat understat_match wikidata pageviews statsbomb fbref_defense
python run.py features models robustness report
```

Pulls are **slow, rate-limited, and cached** — run once, never re-fetch (the match-level Understat pull
is ~15k pages). Render the report with the Quarto CLI (a separate install):

```bash
QUARTO_PYTHON=.venv/Scripts/python.exe quarto render report/ballon-dor.qmd
```

Before calling anything done: `pytest -q` green + `ruff check src tests run.py` clean.

## Data sources

Performance: **Understat** (via `soccerdata`). Attention: **Wikimedia pageviews API** (all languages).
Defensive/keeper merit: **FBref / StatsBomb** (worldfootballR + committed reference CSVs) and StatsBomb
open data. Outcomes: France Football, transcribed from per-edition Wikipedia tables. The MIT
[`LICENSE`](LICENSE) covers the code only; the data stays under each provider's terms.

## Honest limits

Small N (an interpretation, not a predictor). Gate-A H⊥ is attackers-only; defenders/keepers enter
placement via role-aware merit, but purely-positional center-backs are still under-measured. One
attention proxy so far (Wikipedia; GDELT is future work). Gate B conditions on being a finisher (a
Heckman control is reported as a sensitivity check). The Hype Score is "attention beyond *measured*
merit" — for hard-to-measure roles, part of it may be value the box score misses, not narrative.
