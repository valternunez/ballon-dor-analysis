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
+0.762→**+0.779**, Stage B +0.187→**+0.186**; no-duopoly Stage B CI grazes 0). GK leaderboard clean
(Donnarumma/Oblak/Courtois/Alisson); Van Dijk H⊥ +0.54, Donnarumma +1.52. Site + logs updated.
**"How we score it" explainer DONE** — static `#howto` section in `site/index.html` (+ `.howto-grid`
in styles.css), inserted after the intro: two plain cards (Merit / Hype Score), no JS/data change.
**Club-importance v3 DONE (option b) — thesis survives (2026-06-24)** — added graded team-centrality
(`features/club_importance.py`: `minutes_share`, `xg_share`) as a **de-fame control** in
`hperp._REGRESSORS` (NOT a merit dim, NOT a placement predictor). **No new pull needed** — the cached
`understat_player_seasons` already holds full league squads (7124 players), so team totals are a
groupby-sum (the v3 note's "candidate-only" worry was wrong). Anchors land (Rodri 23-24 minutes_share
0.82 / xg_share 0.05). **Headline held: Gate A +0.733→+0.696, Gate B +0.147→+0.145** (ratio ~4.8×);
new `drop_club_importance` row on the robustness caterpillar (+0.78 A / +0.14 B without it). Refit chain
+ regenerated report/site. See findings + decisions log.
**GDELT second proxy DONE — via BigQuery, free (2026-06-24)** — the DOC 2.0 API stayed IP-banned, so
we switched paths to the **BigQuery public GKG table** (`data/gdelt_bq.py`, `[gdelt-bq]` extra,
`gdelt_bq` stage). Counts per-player daily `V2Persons` mentions (accent-folded join to wikidata
names), writing the SAME `gdelt_volume_daily` cache → `gdelt_attention`/`build_gdelt`/`proxy_gdelt`
lit up unchanged. Kept free via a no-billing **sandbox** project + a `dry_run()` gate; the scan is only
**0.066 TB** (read just DATE+V2Persons), well within the 1 TB free tier. 245k player-days, Messi WC
spike validates disambiguation. **The nomination effect replicates: Gate A +0.45 (CI [0.14, 0.76])**;
Gate B +0.06 (same sign, not significant on the noisier finisher-fit sample). Surfaced as prose in the
report + site robustness sections (not the caterpillar — a different signal, like bootstrap/Heckman).
Auth = a user-created service-account key (in Downloads, never committed).
**FotMob ratings cross-check DONE (2026-06-24)** — pulled FotMob's Opta-based season-avg player ratings
(`data/fotmob.py`, `fotmob` stage; via the player page's `__NEXT_DATA__`, no token; SofaScore stayed
Cloudflare-walled). **Cross-check only — never an input to `merit_z` or the de-fame** (it's a
proprietary, offence-weighted black box). 1099 player-seasons, 124/128. Validation: our merit agrees
with the Opta rating **overall Spearman 0.61 / attackers 0.66** (solid external check), but both
**barely separate defenders (0.29)** — so the CB caveat is reframed as a *public-data* limit, not
ours. No spine/headline change; ratings-augmented robustness spec deliberately skipped. CB caveat
upgraded on site + report; stale "GDELT future work" caveat refreshed.
**FotMob zoom — Modrić/Rodri (2026-06-24)** — the Opta rating *rescues high-involvement controlling
mids* our xG-merit under-reads: **Rodri 2024 ~98th pct (8.08)** vs our ~14th; **Modrić 2018 ~66th pct
(7.33)** vs ~20th (opposite of pure CBs, which it compresses). Surfaced in report case studies + role
caveat + site per-year verdicts: part of those two winners' H⊥ is plausibly unmeasured merit, not
narrative. No model change; calendar-year (2018/19/21) season-avg coarseness noted (small).
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
**PUBLISHED (2026-06-21)** — `git init` + commits done; pushed to **public GitHub
`valternunez/ballon-dor-analysis`**. Site live on **GitHub Pages → https://valternunez.github.io/
ballon-dor-analysis/** via `.github/workflows/pages.yml` (publishes `site/` on push to `site/**`); the
rendered report is bundled at `site/report/ballon-dor.html` (the site's "full report" link). Pages
source = GitHub Actions; `.nojekyll` added. Re-render flow: `quarto render` → `cp report/ballon-dor.html
site/report/` → push.
**SITE REDESIGNED (2026-06-21)** — public site rebuilt to the user's new editorial design (Bodoni/Newsreader/Mono, warm dark, plain-scroll) as a clean static site; dropped the design's React runtime; all charts now real + interactive from `data.js` (defame tabs, gate bars, 188-pt D3 scatter, leaderboard, per-year, robustness). Fonts vendored; live on Pages. Report unchanged.
**PUBLISH-READINESS ROUND 2 (2026-06-21)** — post-redesign polish + share meta. Scatter labels →
**soft-white + thin outline** (after halo/pill misfires); "Is it real?" → **labelled caterpillar** (specs
as rows w/ values); per-year shows **each face's real numbers** again (`data.per_year` + curated
verdicts); leaderboard value **flips inside the bar** near the edge (Yamal +3.77 no longer clips on
mobile); **explicit scatter axis key** (↑ attention / → merit); **cache-busting `?v=`** on css/js.
Share: **OG + Twitter + canonical + JSON-LD**, **favicon.svg**, generated **1200×630 `og-image.png`**
card; **GoatCounter** snippet added commented-out (user pastes free site code to enable). Copyedit
(2018–2025, ~190 finisher-seasons, centre-backs/30-player). Live on Pages.
**ANALYTICS REMOVED (2026-06-21)** — GoatCounter snippet deleted from `site/index.html` at the user's
request (no tracking on the site). Report page got the site favicon (inlined data-URI in the qmd
`include-in-header`).
**AUDIT PASS #2 + FIX SWEEP DONE (2026-06-24)** — ran a 9-lens agent-team audit (UX, mobile, SWE,
econometrics, applied-stats, journalist, football, devil's-advocate, reproducibility → synthesis).
**No blockers**; analysis reproduces exactly (Gate A +0.696, Gate B +0.145, R-hat 1.00, 0 divergences,
min ESS≈931) and the generated-regressor bootstrap is correct. Fixed all 22 findings (copy + disclosure,
**no headline change**): site CI label **94%→95%** on the freq caterpillar (gate cards stay 94% HDI);
**jackknife row relabelled** "leave-one-year spread"; stale static fallbacks **2.1×→2.0×, +9→+8pp,
19→27%** + aria **+0.73→+0.70**; **Van Dijk verdict +0.92→+0.87** (now interpolated from `per_year` so
it can't drift); **Kolo Muani "WC final goal"→"final chance"**, **Rodri "treble"→PL title + Euro 2024
POTT**; **bootstrap interval surfaced** at the headline (site `#gates-boot` + report) — Gate A
[+0.51,+1.07], Gate B [+0.02,+0.34]; **"gap runs both ways" / reverse-causality caveat** added (site +
report limitations). Modeling: **`drop_low_baseline` dropped everywhere** (structural no-op — `pv_low_
baseline` False for the all-famous pool); **`robustness.prior_sensitivity()` added** (tight/wide Normal
on the H⊥ slope → Gate A stays [+0.67,+0.70], Gate B [+0.14,+0.15], cited in report+findings);
**`report.diagnostics()`** added (live R-hat/ESS/divergences + **ROC-AUC now 0.80**, the old 0.845 was
stale post-merit-leakage-rebuild). Mobile: **44px tap targets**, **tap-to-reveal tooltips** on
scatter/leaderboard (scroll-safe `click`), leaderboard stack viewport-aware (no clip at ~360px), scatter
aspect floor lowered. a11y: **`<main>` + skip-link**. Assets: **og-image.png→og-image.jpg** (191KB→48KB,
`og:image:type` added). ruff + **109 tests** green; panel + data.js + figures refit; report re-rendered →
`site/report/`; `?v=20260624e`.
**GDELT POOL-WIDE DONE (2026-06-24)** — switched `gdelt_bq._pairs()` from `wikidata.award_universe()`
(~128) to `pool.pool_universe()` (657) via a `_universe()` helper, so `h_perp_gd` is now fit **pool-wide**
like pageviews (the inner join in `hperp._candidate_frame` made every downstream stage —
`gdelt_attention`→`build_gdelt`→`proxy_gdelt` — go pool-wide unchanged). **Cost flat:** dry-run 0.066 TB
for 657 names = same as 128 (BigQuery bills bytes scanned, not names joined); wikidata already pool-wide
cached. `gdelt_volume_daily` now **590 players** (was 114). **Result:** Gate A **+0.324 [+0.10, +0.55],
n=910** (was finisher-fit n=311) — replicates direction + significance on an independent corpus but
**attenuated** vs pageviews +0.742 (~half size; expected for a noisier, harder-to-disambiguate
pool-wide news signal). Gate B +0.051 (finisher-only, n.s.). **Quality-gated to a *strengthened
replication*, NOT a co-headline** (the user's "co-headline if 1 TB room" gate was reframed to quality:
1 TB never bound; the +0.32-vs-+0.74 magnitude gap does). Disambiguation sound (GDELT↔pageview Spearman
0.62; top pool-only players all real). Report + site GDELT/caveat prose reframed to pool-wide; docstrings
de-finisher'd. **Headline frozen** (pageviews +0.696/+0.145). ruff + tests green; `?v=20260624f`.
**TOURNAMENT OVERACHIEVEMENT control DONE (2026-06-25)** — added a de-fame **robustness control** for
how far a player's nation finished beyond its pre-tournament seed (curated `expected` in
`tournament_results.csv` from FIFA ranking/seeding; overachievement = max(0, result−expected): Croatia
2018 +2, Morocco 2022 +2, Algeria 2019 +2, favourites who won 0). `team_success._tournament_
overachievement` (pure, tested) + pool-wide in `pool.build()` (158 players nonzero); merged into
`hperp._candidate_frame` 0-filled but **NOT** in `_REGRESSORS` (baseline frozen — model_features Δ=0).
New `robustness._overachievement_hperp()` + `overachievement` panel/caterpillar spec;
`report.overachievement_case()` for the Modrić delta. **Result:** Gate A **+0.742→+0.657** [+0.45,+0.87]
(survives — nomination bias isn't just surprise success), Gate B **+0.141→+0.085** (fades, as expected
for the fragile placement effect), **Modrić 2018 +1.357→+0.310** (most of the top residual *was*
Croatia's run). Sensitivity-only (curated pre-event seed is softer than absolute results; asymmetric).
Surfaced in report (robustness + Modrić case) + site (robustness para + Modrić verdict + caterpillar);
fixed a stale site "breakout newcomers" line. ruff + 110 tests green; `?v=20260625a`.
**2026 HYPE-WATCH teaser DONE (2026-06-26)** — forward-looking, **fully isolated** site teaser (NOT a
modelled year; study payload byte-identical to HEAD, headline frozen). New `features/hype_watch.py` +
`run.py hype_watch` stage + cache-guarded `report.hype_watch_payload`; SEPARATE caches
(`understat_2526_seasons`, `pageviews_2026_hypewatch`) so the study's caches are never touched.
Provisional attention-beyond-merit for 2026 **attackers** on the completed 2025-26 club season + a
**pre-WC** window (ends 2026-06-10); within-field de-fame on log(baseline)+att_merit_z+**team-strength
proxy** (team npxG+xAG — no fabricated 2025-26 trophies); **above-median baseline floor** drops
thin-baseline breakouts (the low-baseline artifact, applied live). Snapshot top: **Olise +0.45**, João
Pedro, Saka, Mbappé, Pedri, Güler; under-attended tail: **Kane** (goals-no-buzz), **Yamal** (2024 fame
now priced in → slightly negative), Vinícius. Site `#hypewatch-section` = Live/provisional badge,
diverging over/under bars, snapshot date, prominent "not the study / WC will rewrite this" caveats;
Quarto report left clean. ruff + 112 tests green; `?v=20260626a`. **The right time to add 2026 as a real
out-of-sample 8th spine year is after the ~Sept/Oct 2026 ceremony.**
**Next/optional:** add 2026 as a real spine year post-ceremony (out-of-sample test of the thesis).

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
