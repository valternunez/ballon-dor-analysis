# CLAUDE.md — ballon-dor-analysis

**Project:** "Does the Ballon d'Or reward goals or narratives?" — an interpretation study (not a
prediction one; N is small). The thesis is *conditional*: does media attention have independent
explanatory power for the award **after controlling for** on-pitch merit and team success? The
central quantity is **H⊥** = attention beyond merit (a regression residual).

## ⚠️ Standing instruction — keep the living logs current (do this EVERY time)

The journey and the findings are part of the deliverable (this becomes a blog post — the war
stories and the results both matter). So, continuously and without being asked:

- **`docs/decisions-log.md`** — every time we hit an **issue, dead end, or forced pivot** and how
  we fixed it (+ the cost/tradeoff). Reality keeps breaking the plan; record each break.
- **`docs/findings.md`** — every time we **discover something analytical** (a result, a sanity
  check that lands, a surprising leaderboard, an interpretable H⊥ case). Caveat honestly.

Append a dated entry as it happens — don't batch it up for later.

## Current status / next (update me as we go)
Data pulls done: awards, understat, wikidata, **pageviews pulled POOL-WIDE** (558/571 players;
gdelt paused 43/128). Features: merit, **pool-wide attention** (`features/attention.py`), team-success,
**H⊥ refit pool-wide** (`hperp` now fits the de-fame regression on 728 attacker candidates, drops
tournament_result) → `model_features.parquet`, **Tier-2 pool** (`tier2_pool.parquet`, 86% recall).
All bambi models via **nutpie** (no C compiler — see decisions-log).
**BOTH gates + the thesis test DONE** (`python run.py models`):
- **Stage A nomination** `models/nomination.py`: baseline (all positions) + **Stage A + H⊥**
  (attackers). **Gate-A H⊥ = +0.72** (HDI [0.50, 0.95], P>0=1.00) — narrative strongly gets you
  *noticed*; merit_z +1.59 still dominant; CV ROC-AUC 0.845.
- **Stage B placement** `models/placement.py`: pool-fit **H⊥ = +0.192** (HDI [0.04, 0.34], P>0=0.99);
  no-duopoly marginal (+0.148, HDI [−0.01, 0.30]).
- **PAYOFF (working hypothesis confirmed):** H⊥'s pull on *nomination* is ~4× its pull on *placement*
  → "the bias is in who gets **considered**, not who wins." See `docs/findings.md`.
- Cached idata: `nomination_idata.nc`, `nomination_hperp_idata.nc`, `placement_idata{,_noduo}.nc`.
**Robustness panel DONE** (`python run.py robustness` → `models/robustness.py`, `robustness_panel.parquet`):
frequentist anchors re-fit H⊥ across specs. **Gate A bulletproof** (+0.75–0.78 every spec, tight
jackknife); **Gate B stable but modest + duopoly-sensitive** (no-duopoly CI grazes 0). Leakage shown:
ceremony+21d window inflates Stage B +0.195→+0.221, Stage A unmoved (decided pre-ceremony). See findings.
**Quarto writeup DONE** — `report/ballon-dor.qmd` + `src/bdor/report.py` (figures: two-gate forest,
robustness caterpillar, H⊥ leaderboard, merit-vs-attention, pageview spike; plotly interactive + PNG via
kaleido). `python run.py report` regenerates figures; render with
`QUARTO_PYTHON=<.venv python> C:\PROGRA~1\Quarto\bin\quarto.cmd render report/ballon-dor.qmd` →
`report/ballon-dor.html` (self-contained). Toolchain: `[report]` extra + winget Quarto + `bdor` ipykernel.
**Public scrollytelling site DONE (v2)** — `site/` (index.html + styles.css + app.js + data.js): bespoke
D3 v7 + scrollama, dark-editorial deck, **7 animated charts**. `report.export_site_data()` → `site/data.js`.
v2: **"H⊥" renamed "Hype Score"** site-wide (symbol gone; report.py math docstrings keep ⊥); new
**per-year scoreboard** (`#per-year` scrolly + `report._per_year_scoreboard` → `per_year` payload from
`model_features`: best season vs winner vs most-talked-about per year); plain-language rewrites (de-jargon
+ first-time framing, no "used to/now"); **glossary** + link to the Quarto report; Heckman explained
plainly; proxy framed honestly. Open `site/index.html` in a browser.
**StatsBomb tournament pool DONE** — `data/statsbomb.py` (`statsbombpy` open data; `[statsbomb]` extra;
`python run.py statsbomb`). 3rd pool source (semifinalist squads, ≥150 min) → **recall 86%→93%**
(2021 30/30); player→nation extension **re-enabled `tournament_result`** at Gate A (decisive: +0.60
baseline / +0.47 H⊥). Gate-A H⊥ robust at **+0.75**; Stage B untouched. Coverage: WC2018/Euro2020/
WC2022/Euro2024/Copa2024 (no major for 2019/2025). 4 name aliases added to `awards.PLAYER_ALIASES`.
**Merit is 4-DIMENSIONAL DONE** — `data/fbref_defense.py` now pulls defense + keepers_adv + misc +
passing RDS (worldfootballR, free, 2017/18–2022/23) + committed reference CSVs for 2023/24
(GuechtouliAnis Kaggle) & 2024/25 (hubertsidorowicz); `[fbref]` extra (`pyreadr`); `python run.py
fbref_defense`. `merit.build` best-role combines four signals: **attacking** (Understat PCA),
**MF ball-winning** (TklW+Int+Blocks+Clr/90), **CB** (tackle% + aerial% + prog-passes/90 — efficiency,
volume excluded as inverted), **GK** (total PSxG+/- + ½ save%). `merit_z = max(...)`. **CB is a
documented PARTIAL** — shipped past a face-validity checkpoint (`cb_validity_anchors.csv`,
`_CB_MERIT_ENABLED` switch): nails duel-dominant elites (Van Dijk bottom-13%→top) but misses
positional CBs (Dias 44th) + some FB noise — the public-data ceiling (decisions log). H⊥ de-fames vs
all four dims (0-filled per role) → **defenders & keepers get an H⊥ for the first time** (fit n
751→1025); Stage B adds `cb_def_z`+`gk_merit_z` co-controls, N 157→191. **Thesis robust** (Stage A
+0.762→**+0.779**, Stage B +0.187→**+0.186**; no-duopoly Stage B CI now clears 0). GK leaderboard clean
(Donnarumma/Oblak/Courtois/Alisson); Van Dijk H⊥ +0.54, Donnarumma +1.52. Site + logs updated.
**"How we score it" explainer DONE** — static `#howto` section in `site/index.html` (+ `.howto-grid`
in styles.css), inserted after the intro: two plain cards (Merit / Hype Score), no JS/data change.
**Club-importance scoped as v3 (next batch)** — `docs/club-importance-v3.md`: we capture individual
stats + binary trophies but NOT how central a player was to his club (Rodri 2024). Candidate signals:
share-of-team-output (needs a new Understat team-totals pull), minutes-share, season-avg match ratings
(cross-check only — black-box + gated). Open: enter merit vs Hype-Score team block (leaning latter).
**GDELT pull at 48/128, hard-banned again** (2026-06-20) — resume cleared 43→48 then the IP soft-banned
(HTTP 200 empty body); `_request` **hardened** to treat non-JSON bodies as a throttle (no more
`JSONDecodeError` crash — decisions log). Next attempt needs a different network or a 12–24h rest; not
retrying immediately. `h_perp_gd` second proxy still gated on the pull completing.
**Robustness chart polished** (2026-06-20) — fixed a systemic SVG label-colour bug (`.attr`→`.style`
fill; was muted by `.lab` CSS), regrouped the caterpillar into Gate A/Gate B blocks (one clean row each,
plain-language Y labels), and added a "what each stress test means" dropdown. Site-only, no model change.
**MERIT LEAKAGE FIXED — match-window rebuild (2026-06-21)** — pre-publication review caught that merit
blended FULL seasons, so calendar years (2018/2019/2021) credited post-ceremony matches (De Bruyne's
"2019" was mostly his future 2019-20). Rebuilt attacking merit from **date-stamped match data**
(`understat.pull_matches`, new `understat_match` stage; 424k player-matches) summed inside each award
year's `perf_start..perf_end` window (`merit._window_sum`/`_attacking_merit`); FBref defensive/CB/GK +
team-success `cl_round`/`won_league` use the leakage-safe `config.completed_season` (no match logs).
Refit whole chain. **Thesis holds, sharper:** Gate A **+0.733** (HDI [0.53,0.95], P>0=1.00), Gate B
**+0.147** (HDI [0.02,0.28], P>0=0.98), ratio **~5×** (was ~4×). De Bruyne 2019 merit 10.53→8.54 (no
longer #1/"Messi's twin" → new twin **Lewandowski 2019 vs Messi 2023**); João Félix/de Jong H⊥ artifacts
gone; spike fig now **Rodri 2024** (post-cut ceremony spike). Also fixed (pre-pub review): site scatter
uses role-aware `merit_z` (defenders no longer pinned at 0), "most talked-about"→"most over-hyped",
2021→Lewandowski, Hype-Score="beyond *measured* merit" caveats, nationality caveat, stale-comment.
ruff + 92 tests green; report re-rendered; site/data.js regenerated. See decisions-log + findings.
**PUBLICATION-HARDENING batch DONE (2026-06-21)** — (S1) plain-language **effect sizes**:
`report.effect_sizes` + `models/_report.average_marginal_effect` → odds ratios (Gate A **2.1×**, Gate B
**1.16×**) + Gate-A **AME ~+9pp** (~19%→28%), surfaced in report + site (`#gates-plain`←`data.js.effects`).
(S2) **generated-regressor bootstrap** (`robustness.bootstrap_hperp`, resamples both de-fame + gate;
A [+0.58,+1.10], B [+0.04,+0.33]). (S3) **Heckman** sensitivity (`placement.heckman_check`; B +0.19, sign
holds, wide). (S4) **strict-window** row (injectable `merit._build_merit(windows=)` /
`hperp.hperp_frame(merit_df=)`; A +0.80, B +0.14 ≈ baseline). bootstrap+heckman kept in panel but OFF the
caterpillar (`report._CATERPILLAR_SPECS`), cited as prose (`report.robustness_extras`). (P1) a11y: AA
contrast bump, `role=img`+aria-labels on 7 site charts, `#| fig-alt` on 5 report figs (palette already
CVD-safe). (P3) **site vendored** (`site/vendor/` d3+scrollama, `site/fonts/` woff2 — zero external
requests). (P2) **MIT LICENSE** + data-attribution, README rewritten, `.gitignore` fixed
(`!site/index.html`). ruff + **93 tests** green; report re-rendered; site offline-clean.
**Next/optional:** **`git init` + first commit** (pending user OK on license/commit-scope); finish GDELT
(rested IP) + wire `h_perp_gd`; club-importance v3.

## Where the canon lives
- `PROJECT_NOTES.md` — the locked methodology (thesis, funnel, merit index, H⊥, GDELT, modeling spec).
- `docs/windowing.md` — per-award-year performance/hype windows (leakage-safe).
- `docs/decisions-log.md` / `docs/findings.md` — the living logs (above).
- `docs/gdelt-resume.md` — GDELT pull paused at 43/128; how/when to resume.

## Stack & conventions
- **Python only** (single language). Env: `.venv` on **Python 3.12** (`py -3.12`). Core deps install
  via `pip install -e .`; heavy modeling deps (PyMC/bambi/statsmodels) are the `[model]` extra,
  installed at the modeling stage. PCA/OLS currently use numpy to avoid pulling that early.
- **Cache-first data layer**: every pull/feature wraps `cached_frame`/`cached_records`
  (src/bdor/cache.py) → parquet under `data/cache/` (gitignored). Pulls are slow/rate-limited;
  never re-fetch. Reference data is curated CSVs under `data/reference/` (committed).
- **Pipeline stages**: `python run.py --list` shows them; `python run.py <stage>` runs one
  (awards → understat → wikidata → pageviews → gdelt → features → models).
- **Before calling anything done**: offline `pytest -q` green + `ruff check src tests run.py` clean.
  Tests cover pure helpers on synthetic data (no network); live pulls are validated by scratch
  spot-checks, not unit tests.
- Data source = **Understat** for performance (FBref stopped serving advanced stats publicly —
  see decisions-log). Outcome = vote **points/share**, not rank.
