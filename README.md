# The Ballon d'Or rewards goals — and stories.

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
| **A — nomination** | do you make the 30-man shortlist? | **+0.70** [0.49, 0.91], P>0 > 0.99 | ≈ **doubles** the odds of being shortlisted (~+8 pts of probability) |
| **B — placement** | given you're in, do you finish higher? | **+0.15** [0.01, 0.28], P>0 = 0.97 | adds only ~16% to the odds |

**The bias is in who gets *considered*, not who wins** — narrative's pull on nomination is ~5× its
pull on placement. Gate A holds across every robustness check; Gate B is real but modest and
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
data/cache/            Mostly gitignored, BUT a committed ~15 MB frozen snapshot (derived model/feature
                       outputs + *.nc posteriors + attention/news signals) reproduces the published
                       results offline. Bulky re-pullable raw caches + raw JSON stay gitignored.
site/                  Public scrollytelling site (index.html + app.js + styles.css + data.js + vendored libs).
report/                Quarto writeup (.qmd); figure PNGs are regenerated build artifacts (gitignored).
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

### 1. Reproduce the published results — offline, exact (recommended)

A **frozen analysis snapshot** is committed under `data/cache/` (derived model/feature outputs + the
`*.nc` posteriors + the attention/news signals), so the published figures, `site/data.js`, and the
headline numbers regenerate from a clone with **no network and no credentials**:

```bash
python run.py report                   # regenerates report/figures + site/data.js from the snapshot
QUARTO_PYTHON=.venv/Scripts/python.exe quarto render report/ballon-dor.qmd
cp report/ballon-dor.html site/report/ballon-dor.html   # refresh the copy the live site links to
pytest -q && ruff check src tests run.py
```

This is the only path that yields the **exact** published numbers — re-pulling (below) hits live data
that has since drifted.

### 2. Full rebuild from source (optional — re-pulls live data, will drift)

```bash
python run.py --list                   # all stages in dependency order
python run.py awards understat understat_match wikidata pageviews statsbomb fbref_defense
python run.py features models robustness report
```

Heavier and partly external: pulls are **slow + rate-limited** (the match-level Understat pull is ~15k
pages); `fbref_defense` needs **R + worldfootballR** (recent seasons fall back to the committed
reference CSVs); the GDELT second proxy (`gdelt_bq`) needs a **Google Cloud service-account credential**
(`GOOGLE_APPLICATION_CREDENTIALS`, free sandbox tier). Add `--refresh`-equivalent re-pulls only if you
want fresh (drifted) data. The public site auto-deploys to GitHub Pages on push to `site/**`
(`.github/workflows/pages.yml`).

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
