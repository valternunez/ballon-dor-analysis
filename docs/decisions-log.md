# Decisions & journey log

Issues, dead ends, and forced pivots — and how we fixed them. The reality-vs-plan story (good
blog material). Newest entries at the bottom. Append as things happen.

---

### FBref went dark on advanced stats → pivoted to Understat (2026-06-19)
**Issue:** FBref stopped serving its advanced/Expected columns (xG, npxG, xAG, progressive, SCA,
defense, PSxG) publicly — only basic stats (goals, assists, shots, minutes) come through.
**How discovered:** native `soccerdata`, a custom soccerdata subclass, headless *and* visible
Chrome, combined leagues *and* single-league — all returned no xG. Confirmed by a **manual human
browser check**: the columns aren't there for humans either. So it's FBref-side, not scraping.
**Fix:** switched performance source to **Understat** (different provider, its own xG model, clean
JSON, no Selenium). `read_player_season_stats` gives xg/npxg/xag/xg_chain/xg_buildup/goals/assists.
**Cost:** lost SCA, detailed defensive actions, and PSxG. So **defenders & keepers have no
individual merit metric** and enter the pool via team-success only; xg_chain/xg_buildup proxy the
dropped progression. We had *just* upgraded to a full-stat FBref scraper for position fairness, so
this was a real walk-back — but the lost metrics only touch strata the design already routed
through team-success, and the xG core that discriminates contenders is intact and working.

### FBref/GDELT both 403/429 raw requests → browser engine / backoff
**Issue:** FBref 403s plain `requests`; Wikimedia and GDELT 429 aggressive bursts.
**Fix:** FBref needed a real browser (soccerdata's Selenium); pageviews/GDELT got polite rate +
exponential backoff honoring `Retry-After`. Lesson baked into the code so re-runs survive.

### Understat codes wingers as "M" → merged F+M into one "attack" family (2026-06-19)
**Issue:** the first merit build put Gnabry/Bale/Sané atop the "midfield" leaderboard and left PCA
blank for most contenders. Understat's coarse `position` codes wingers/forwards inconsistently as M.
**Fix:** merge F and M into a single **attack** family (Understat can't reliably split winger vs
midfielder). Defensive midfielders thus get a correctly low attacking merit_z. Pure defenders → NA.

### Per-90 merit rewarded small-sample hot streaks → z-score season totals (2026-06-19)
**Issue:** per-90 z-scores put super-subs/journeymen (Stuani 877 min, Muriel) above durable elites.
**Fix:** z-score **season totals** (durability-weighted) + a couple of per-90 efficiency signals,
and raise the minutes floor to 1500. Leaderboards then became credible (Mbappé/Lewandowski/Messi).
This is the "include volume so durability counts" point from the locked design, which the first
cut missed.

### Nullable dtypes broke numpy SVD → cast to float64 (2026-06-19)
**Issue:** Understat arrives as pandas nullable Float64; `.to_numpy()` gave an object array and
PCA's SVD raised a casting error. **Fix:** `astype("float64")` the metrics before NumPy.

### GDELT theme:SOCCER returned zero; IP ban escalated → quoted names + paused (2026-06-19)
**Issue (1):** the planned `"Name" theme:SOCCER` disambiguation returned no matches — that GKG
theme code is invalid via the DOC API. **Fix:** quoted full-name phrase alone disambiguates well
(precision ~100% even for the worst collision, "Heung-min Son") — verified via an article-list
sample.
**Issue (2):** GDELT's DOC API imposes an escalating per-IP ban; collection stalled at 43/128 even
with a 6-min self-cooldown loop. **Fix:** paused; documented resume timing in `docs/gdelt-resume.md`
(rested IP overnight → resumes from the cache). GDELT is the *secondary* proxy (pageviews is the
validated primary), so partial coverage is acceptable for now.

### awards.club is ceremony-time, not judged-season → union Understat club (2026-06-19)
**Issue:** team-success initially missed Messi 2023's PSG Ligue 1 title because `awards.club` lists
his **ceremony** club (Inter Miami), not where he played the judged 2022-23 season.
**Fix:** union the **judged-season Understat club** (with a small spelling-alias map) into the club
set before looking up CL/league. Robust for any transfer case; future-proofs for the pool.

### H⊥ regression: merit_z + merit_pc1 collinear → use orthogonal PCA axes only (2026-06-19)
**Issue:** the first H⊥ fit gave merit_z a **negative** coefficient — multicollinearity, since
merit_z and merit_pc1 are ~the same composite. (Doesn't bias the residual, but makes coefficients
uninterpretable.) **Fix:** represent merit in the residualization by the **orthogonal PCA axes**
(pc1, pc2) only — exactly why PCA was chosen. merit_z stays in `model_features` for the outcome
models. Coefficients then read sensibly (fame dominant, merit/CL/tournament positive).

### Stage B: vote_share has exact zeros → Smithson–Verkuilen squeeze (2026-06-19)
**Issue:** the placement outcome is vote **share**, modeled with a Beta likelihood — but 13 of the
136 Stage-B finishers scored zero vote points (`vote_share == 0`), and Beta's support is the *open*
interval (0,1). Dropping them throws away the "nominated but got nothing" signal.
**Fix:** the standard **Smithson–Verkuilen transform** `y' = (y(n−1) + 0.5)/n` squeezes the 0/1
endpoints just inside the support, so every row survives the fit (`placement._squeeze`).

### Stage B excludes defenders & keepers by construction (2026-06-19)
**Issue (not a bug — a consequence to state):** Stage B = 136 rows, all attackers. The 33 excluded
finishers are **21 defenders + 12 keepers** — they have NA individual merit (Understat has no
defensive/keeper metric), hence no H⊥, hence can't enter a merit-conditioned outcome model. This is
the locked design (they route through the team-success pool), but it means **Stage B speaks only to
attackers**; Van Dijk/Rodri-type placements aren't tested here. Name it honestly in the writeup.

### No C compiler on Windows → nutpie (numba) instead of PyTensor's C backend (2026-06-19)
**Issue:** PyMC compiles its log-density via PyTensor, which wants `g++`. This machine has none
(`pytensor.config.cxx == ''`), so the default sampler falls back to a pure-Python linker — correct
but punishingly slow. The plan anticipated this.
**Fix:** sample with **nutpie** (`inference_method="nutpie"`), a numba-backed NUTS implementation
with prebuilt wheels — no C compiler needed (numba was already present). Fits the full 4-chain model
in ~1 min with healthy diagnostics (R̂=1.00, ESS≈3–5k). `target_accept` is passed via
`nuts={"target_accept": 0.9}` (the new pm.sample form; bare `target_accept`/`nuts_sampler_kwargs`
either collide with bambi or are deprecated).

### arviz 1.x is a different API → adapt summary + caching (2026-06-19)
**Issue:** the pinned stack resolved to **arviz 1.2 / pymc 6.0**, not the 0.x/5.x the spec assumed.
`az.summary(hdi_prob=…)` is gone (now `ci_prob` + `ci_kind="hdi"`, columns `hdi94_lb/ub`), it returns
**pretty-printed strings** (coerce with `pd.to_numeric`), the fit object is an xarray **DataTree**
(no module-level `az.to_netcdf` — use `idata.to_netcdf(path, engine="h5netcdf")`), and `h5netcdf`
needs **`h5py`** as its backend (added to the `[model]` extra alongside `nutpie`).
**Also:** the Windows console is cp1252 — printing the "⊥" glyph raises `UnicodeEncodeError`. Console
strings use ASCII "H_perp"; the Unicode H⊥ stays in code/docs only.

### Tier-2 pool: production = top-N by merit_z (one attacking stratum, not two) (2026-06-19)
**Issue:** PROJECT_NOTES sketched two production strata (forwards/wingers vs central/def mids) with
different metrics — but that assumed FBref granularity. Understat's coarse position codes can't
reliably split winger from central-mid (the same reason merit merged F+M into one "attack" family).
**Fix:** the production pool = **top-N attackers by `merit_z`** per award year (N=50). `merit_z`
already fuses the locked rate (npxg+xag/90) and volume (G+A totals) signal, so this reuses the merit
engine instead of re-deriving a rate∪volume union. Defenders/keepers (no Understat merit) enter only
via the team-success pool. Pool ≈ 150–230/yr (generous, per "bias toward inclusion").

### Stage A: drop tournament_result (finisher-only nation → leakage) (2026-06-19)
**Issue:** `tournament_result` needs player→nation, which `player_nation.csv` has only for the 128
finishers. Used as a Stage-A predictor over the whole pool, it would be nonzero *only* for nominees —
a backdoor copy of the label. **Fix:** omit it from Stage A v1 (use club-based team-success only:
cl_round/won_cl/won_league, computable identically for every pool member). It returns when nation is
extended to the pool. Also: pool inclusion is **source-based, never "because nominated"** (outcome-
based) — so nominee *recall* (sources recovered 86% of the 30) is a diagnostic, not forced to 100%.

### Cross-source feature joins merged on RAW names → join on a canonical key (2026-06-19)
**Issue (serious, found while validating pool recall):** the feature tables were merged on the raw
`player` string, but **Understat spells names differently from Wikipedia/awards** (accents/suffixes:
"Luka Modric" vs "Modrić", "Kylian Mbappe-Lottin" vs "Mbappé"). A raw-string inner-join therefore
**silently dropped every mismatched player** — 41 finishers absent from `model_features`, including
**Modrić (the 2018 WINNER and a core case study)**, Mbappé, and others. The Stage-B headline had been
computed without them.
**Fix:** a single canonical key `awards.name_key(name)` = accent-fold(alias-resolve(name)), with a
3-entry `PLAYER_ALIASES` map for the cases accent-folding can't reconcile (Mbappe-Lottin→Mbappé,
Daniel→Dani Carvajal, Fabián→Fabián Ruiz). All cross-source merges (`hperp`, `features`, pool nominee
label) now join on it. Recovered 21 attackers into Stage B (N 136→**157**); the H⊥ result was robust —
headline barely moved (+0.285→**+0.291**) and the no-duopoly case strengthened (+0.202→+0.231, HDI
still excludes 0). Lesson: never join people across data providers on a raw display name.

### H⊥ refit pool-wide: fit on the pool, drop tournament_result (2026-06-19)
**Change (for Gate A):** to test attention at nomination, H⊥ must exist for non-finishers, so the
de-fame regression is now estimated over the **whole candidate universe** (pool ∪ finishers, 728
attacker rows vs the old 136). Pulled all-language pageviews for the **443** new pool players
(reusing the resumable `pageviews`/`wikidata` machinery; **558/571 resolved**, 13 no-coverage gaps
logged). **`tournament_result` dropped from the de-fame regressors** — player→nation exists only for
finishers, so it would residualize inconsistently across the pool (same guard as Stage A); it stays a
Stage-B passthrough. **Consequence (disclosed):** finishers' H⊥ changed, so Stage B re-fit a third
time and **softened (+0.291 → +0.192)** — the pool baseline is more honest (de-famed against 728, not
136), and the placement effect being modest while nomination is strong *is* the finding, not a bug.

### H⊥ is attacker-only by construction — Gate A too (2026-06-19)
**Decision (user-confirmed):** H⊥ = "attention beyond *merit*"; defenders/keepers have no Understat
merit metric, so merit_pc1/pc2 are NA and they fall out of the de-fame fit automatically. Rather than
impute, we keep H⊥ **attacker-only** and leave non-attackers in the H⊥-free Stage-A baseline. Clean
and principled (the residual is undefined without a merit control), at the cost of not testing the
attention effect for the Van Dijk/Rodri route — named honestly.

### Robustness panel: frequentist anchors, and the leaky-window cell needed calibrating (2026-06-20)
**Choice:** the coefficient-stability panel re-fits H⊥ across specs with **frequentist anchors**
(statsmodels Beta/Logit, seconds each) rather than ~15 nutpie fits — the anchors already track the
posteriors, and the Bayesian remains the headline. Result: Gate A H⊥ is rock-solid (+0.75–0.78 every
spec); Gate B stable but modest and duopoly-sensitive (no-duopoly CI grazes 0).
**Bug caught while validating:** the first `window_leaky` cell ended the hype window *at* the ceremony
date — but the winner is announced AT the ceremony, so the leakage spike lands on/after it. Ending the
day before added only ~50 days of pre-announcement anticipation to a 12-month window → H⊥ didn't move
(false "no leakage" reading). **Fix:** push the leaky cut to **ceremony + 21 days** to actually capture
the result spike. Then Stage B H⊥ inflates +0.195 → +0.221 (and Stage A, decided pre-ceremony, stays
put) — the guardrail demonstrated in the right direction.
**Also noted:** `drop_low_baseline` is vacuous — 0 low-baseline players in the modeled samples (all
established top-merit/finisher attackers). Kept in the panel for honesty; it moves nothing.

### Quarto writeup: toolchain install + two Windows render gotchas (2026-06-20)
**Setup:** the publish layer is a `report` extra (jupyter engine + `kaleido`); the **Quarto CLI**
itself isn't pip — installed via `winget install --id Posit.Quarto` (1.9.38) and the `.venv` registered
as the `bdor` ipykernel so `.qmd` cells run with the project deps. Figures live in `src/bdor/report.py`
(tested, reusable) as plotly objects — interactive in the HTML, static PNG via kaleido — per the repo's
"logic in src/, not notebooks" rule; the `.qmd` is thin narrative. Render reads **cached** model
objects (never refits). `python run.py report` regenerates the PNGs.
**Gotcha 1 — kaleido can't serialize pandas Timestamps:** the pageview-spike figure's datetime x and
`add_vline` markers raised `TypeError: Type is not JSON serializable: Timestamp` on PNG export. Fix:
pass `s["date"].to_numpy()` and `when.isoformat()` (kaleido is fine with numpy datetime64 / ISO strings).
**Gotcha 2 — `quarto.cmd` + the space in "Program Files":** invoking the wrapper resolved its own
tools dir to `…/Files/Quarto/…` (split on the space) → `deno.exe` not found, from both Git Bash and
PowerShell. Fix: call via the 8.3 short path `C:\PROGRA~1\Quarto\bin\quarto.cmd`, with
`QUARTO_PYTHON` pointed at the `.venv` python. Rendered `report/ballon-dor.html` (self-contained, 5
interactive figures).

### Public scrollytelling site: bespoke D3, dark editorial, data inlined (2026-06-20)
A second, general-public deliverable under `site/` (the Quarto doc stays the analyst-facing report).
Hand-built static page — **D3 v7 + scrollama**, **dark-editorial** theme — with six animated charts
(de-faming bars, leaderboard, two-gate forest reveal, merit-vs-attention scatter, robustness
caterpillar, pageview spike). Distilled results are exported by `report.export_site_data()` to
`site/data.js` as `window.BDOR = {…}` — **inlined JS, not fetched**, so the page opens from `file://`
with no server/CORS. D3/scrollama/fonts come from CDNs (needs net for first view). The de-faming viz
uses `expected = expm1(log1p(actual) − H⊥)` so the actual-vs-expected gap is exactly the residual.
**Honest limitation:** no headless browser in the dev env (no playwright), so the page is
syntax-checked (`node --check`) and the data validated, but the look/animation is verified by the user
in a browser — a build-then-iterate loop, accepted up front.

### StatsBomb tournament pool (3rd source) + tournament_result un-dropped (2026-06-20)
**Added** the locked-but-deferred 3rd pool source: WC/Euro/Copa **semifinalist squads** from StatsBomb
open data (`statsbombpy`, free, no auth) — `data/statsbomb.py`, resumable per match, minutes summed
from lineup `positions`. Covered: WC2018→2018, Euro2020→2021, WC2022→2023, Euro2024+Copa2024→2024;
**no open-data major for 2019 / 2025** (documented gaps). Squad players with ≥150 tournament minutes
join the pool as `in_tournament`. **Nominee recall jumped 86% → 93%** (180→196/210; 2021 now 30/30).
**Name reconciliation:** StatsBomb uses full legal names; `awards.name_key` folded most, with **4
aliases** added (Mac Allister, Ounahi, Dani Olmo, Aguerd) so they attach their Understat features
instead of entering featureless. Tournament-only members with no Understat presence get
`position_family="other"`.
**tournament_result back in Stage A:** the StatsBomb player→nation extension means many NON-finishers
now carry a nonzero `tournament_result`, so it no longer implies "nominee" (the leakage that forced us
to drop it is gone). Re-added to the Stage-A formula → a **decisive predictor** (baseline +0.60, H⊥
model +0.47, P>0=1.00). Gate-A H⊥ headline robust (+0.72 → **+0.75**); Stage B untouched.

### Spine dropped 2017 (xG-edge) — methodology, not a bug
FBref/Understat xG begins 2017-18; the 2017 award's Jan–May half falls in xG-less 2016-17. Dropping
2017 makes all 8 needed seasons xG-clean. 2017 kept only as a degraded/qualitative panel.

### Defensive merit: a 3-source hunt, then "midfielders only" (2026-06-20)
Understat is attacking-only, so defenders & deep mids had NO individual merit (the "Jorginho blind
spot"). Hunting cross-league defensive stats hit wall after wall: live FBref/soccerdata 403s
(Cloudflare, even via a headless browser), Sofascore has no per-player season stats, WhoScored hangs,
StatsBomb open data is too partial (misses PL). What finally worked was three reconciled static
sources (FBref's *advanced* defensive stats went dark ~2022/23, so none spans the spine):
- **2017/18–2022/23** — worldfootballR_data `big5_player_defense.rds` (free raw-GitHub, read with
  `pyreadr`). All 5 leagues, full breakdown.
- **2023/24** — FBref kept only TklW+Int that season (a real Opta-gap; the user confirmed the granular
  columns are blank in-browser). A user-found Kaggle export (`anisguechtouli`) had the *full* breakdown
  back, so we used it. Committed as a reference CSV.
- **2024/25** — `hubertsidorowicz` Kaggle (needs an API token, supplied once). Committed as a reference
  CSV so a **rebuild needs neither the token nor the manual export** — only `pyreadr` for the free RDS.

**Consistent metric = tackles-won + interceptions + blocks + clearances per 90** (the set present in
all three; FBref dropped the rest for 2023/24).

**Forced pivot — center-backs are out.** Volume defensive stats are *inverted* for CB quality: elite
CBs on dominant teams make the **fewest** actions (the team has the ball; positioning prevents
desperation tackles). Evidence: ranking 2023/24 DFs by these stats puts relegation-battlers (Sol Bamba,
Kouyaté, Hübers) on top and **Rúben Dias '21 in the bottom 5%, Van Dijk '19 in the bottom 13%**. So
the defensive merit is **midfielders only**, where ball-winning *volume is* the job (Casemiro / Ndidi /
Kanté top the MF list correctly). CBs keep NA merit + the team-success route — honestly unmeasured
rather than wrongly low.

**Best-role combine:** `merit_z = max(att_merit_z, def_merit_z)` — a player is scored on whichever role
fits. Folded `def_merit_z` into the H⊥ de-fame regressors and Stage B (so deep mids are de-famed against
their ball-winning); production pool ranks on `att_merit_z` (so journeyman destroyers don't flood it).

**Namesake trap (fixed):** aggregating defensive rows by player *name* merged two different "Rodri"s
(Man City + Real Betis) into one. Fixed by aggregating on a true player id (FBref URL; name+club for the
Kaggle rows), then keeping the heaviest-minutes namesake for the name-keyed merit join.

### Merit v2 — center-back + goalkeeper merit, behind a face-validity checkpoint (2026-06-20)
Extended merit from 2 signals to **four** (attacking, MF ball-winning, CB, GK), to close the remaining
NA-merit groups. Data: worldfootballR's *other* big5 RDS files — `keepers_adv` (PSxG+/-), `misc`
(aerial win %), `passing` (progressive passes), alongside `defense` (Tkl%) — free for 2017/18-2022/23;
the recent two seasons re-exported to the committed reference CSVs from Kaggle (2023/24 = the
GuechtouliAnis "Football-Data-Scraping" set the user found; 2024/25 = hubertsidorowicz). Rebuild needs
only `pyreadr` (no token).

**Forced design calls:**
- **Team possession exists only 2017-2023** (neither recent Kaggle set has it) → dropped
  possession-adjustment for year-consistency; shipped the **efficiency** CB metric instead.
- **CB = tackle-success % + aerial-win % + progressive-passes/90** (z within season, DF). Volume is
  EXCLUDED (it's inverted for CBs); efficiency is inversion-immune; progressive passing rescues the
  positional ball-players the duel stats miss and damps journeyman noise.
- **GK = TOTAL PSxG+/- (+ ½ save%)**, z within (season, GK), 20-nineties floor. Per-90 over-rewarded
  low-minutes backups (Mirante) — the season total is durability-weighted goals-prevented.

**The checkpoint (user-chosen "decide together").** A committed anchor list
(`cb_validity_anchors.csv`) of consensus-elite CBs is scored by percentile in its year's DF
distribution. The strict gate **failed** — but for an honest reason: efficiency+ball-playing nails
duel-dominant elites (Van Dijk top, Koulibaly/Rüdiger/Saliba/Ramos high; median anchor ~84th) yet
**misses purely-positional CBs** (Dias '21 44th, Marquinhos 42nd — positioning is in no public stat)
and picks up ball-playing **fullbacks** coded "DF" (Zinchenko). Shown the leaderboard, the user chose
to **ship the partial** (documented), with `_CB_MERIT_ENABLED` as the flip-switch fallback. This is the
genuine ceiling of public CB data.

**Ripple:** best-role `merit_z = max(att, mf_def, cb_def, gk)`; H⊥ de-fames against all four (0-filled
where a role doesn't apply, ≥1 real dim required) so **defenders & keepers get an H⊥ for the first
time** (fit n 751→1025); Stage B gains `cb_def_z`+`gk_merit_z` co-controls (orthogonality) and CB/GK
finishers (Van Dijk, Dias, Courtois) now enter it (N 157→191).

### Public-site v2 — plain language + per-year scoreboard (2026-06-20)
Reworked the scrollytelling site (`site/`) for a non-technical reader, plus added the most-requested
feature. No modeling/data change — presentation + one derived payload (`report._per_year_scoreboard`).
- **"H⊥" → "Hype Score"** at every on-screen occurrence (index.html + app.js display strings; the
  symbol is gone, glossed once as "attention beyond what a player's season explains"). report.py's
  internal `H⊥` docstrings stay (they're the actual residual math).
- **Per-year scoreboard** — new `#per-year` scrolly section (one panel per award year) showing three
  faces among finishers: best season (top merit_z), the winner, most talked-about (top h_perp), with a
  derived verdict. Data via a new `per_year` key in `export_site_data`/`_site_payload`, sourced from the
  already-joined `model_features` cache. The divergence years are the thesis in one glance (Modrić '18
  won + most-hyped; Rodri '24 won ranked 13th on merit; Dembélé '25 won with near-zero buzz).
- **First-time framing** — removed the "this used to have a blind spot / we closed it / for the first
  time" changelog phrasing (the site is unpublished); the Jorginho aside + caveats now describe what the
  analysis *is*, present tense.
- **Plainer explainers** — de-jargoned the de-faming step, the two-gate label, the "is it real"
  robustness copy ("getting-noticed" / "finishing-higher"), and a plain-English Heckman sentence.
- **Glossary + technical split** — added a "What we mean" glossary (Hype Score / merit / the two gates)
  and a prominent **link to the Quarto report** (`../report/ballon-dor.html`) for the real equations.
- **News-volume proxy** framed honestly (pageviews primary; GDELT second opinion in progress, not vague
  "future work"). Verified via headless render: per-year renders, 0 "H⊥" left, no console errors.

### "How we score it" explainer + club-importance scoped as v3 (2026-06-20)
**Context:** the site explained the *results* but never the *recipe* — a reader met "Hype Score" and
"merit" cold. **Fix:** added a small, non-technical **"How we score it"** box (static `#howto` section,
`site/index.html` + a `.howto-grid` rule) right after the intro, before any chart uses the terms: two
plain-language cards (Merit = how good the season was, graded per role; Hype Score = attention beyond
what performance + fame + team success predict), reusing the existing `.figure .card` pattern. No JS,
no `report.py`, no data change.
**Club-importance question (Rodri 2024):** flagged that we capture *individual* stats + *binary*
trophies but **not how central a player was to his club** — every City player carries the identical
"won CL + won league" signal; minutes are an eligibility floor, not a signal. Decided (with the user)
to make this its **own next batch**, not bolt it onto a presentation change. Wrote
`docs/club-importance-v3.md`: candidate signals = **share of team output** (needs a new Understat
**team-totals** pull — squad totals aren't cached), **minutes share**, and **season-average match
ratings** (SofaScore/WhoScored/FotMob — kept as a *cross-check*, not the merit spine, because it's a
black-box composite, and access is gated). Open decision for that batch: does the signal enter **merit**
or the **Hype Score team-success block** (leaning the latter — fixes the bluntest control without
blurring the quality axis).

### Robustness chart fixed + a systemic SVG label-color bug (2026-06-20)
**Issue (user-reported):** the robustness caterpillar read as broken — its Gate A/Gate B legend sat
oddly top-right and rendered **gray** despite amber/red data, and each spec stacked its two gates with a
±9px offset so the colours looked **misaligned**. The Y-axis specs (`no_duopoly`, `window_leaky`, …) were
also unexplained jargon.
**Root cause (systemic):** in `site/styles.css`, `.lab { fill: var(--ink) }` / `.lab.sm { fill:
var(--muted) }` are CSS rules that **override the SVG `fill="…"` presentation attribute** — so every
`<text>` that set both a `lab` class and a colour via `.attr("fill", …)` lost its colour (muted gray/ink).
This silently affected **6 labels** across charts (robust legend, the two-gate value numbers, per-year
role labels + stat, spike markers, de-fame gap text), not just the one flagged.
**Fix:**
- **Colour bug** — switched those to `.style("fill", …)` (inline style beats the class). One-word change,
  7 sites. Restores colour on every muted label, including the gates `+0.78/+0.19` numbers and the
  per-year role headers.
- **Robustness layout** — rewrote `drawRobust` as **two colour-coded blocks grouped by gate** (Gate A
  amber, Gate B red), each stress-test on its **own clean row** (removed the ±9 offset). The coloured gate
  headings double as the legend, so the broken top-right SVG legend is **deleted**. Y labels renamed to
  plain language (`baseline`→"main model", `no_duopoly`→"drop Messi & Ronaldo",
  `drop_low_baseline`→"drop low-fame players", `window_leaky`→"window past the ceremony",
  `jackknife_year`→"leave each year out"). Bumped `#robust-chart` max-height 60→72vh for the taller chart.
- **Explainer** — added a `<details>` dropdown under the chart, "What each stress test means — and whether
  it changes the answer," with a plain line + verdict per spec and the one-line takeaway (getting-noticed
  rock-solid; finishing-higher real-but-smaller + duopoly-leaning).
**No data/model change** (the `robustness` payload in `data.js` is untouched). Verified: `node --check`
app.js OK, ruff clean, 87 tests pass, section/details balance intact, 10 robustness rows present.

### GDELT resume crashed on a soft-ban body → hardened the retry (2026-06-20)
**Issue:** resumed the GDELT pull on a "rested" IP; it cleared 5 players (43→48/128) then **crashed**
with `JSONDecodeError: Expecting value: line 1 column 1`. Cause: a *soft* ban returns HTTP **200 with
an empty/HTML body** (not a 429), so `_request`'s `resp.json()` threw — and that exception escaped both
the per-request retry loop (which only handled 429/503) and the outer cooldown loop (which only catches
`RuntimeError`), killing the whole run.
**Fix:** `_request` now wraps `resp.json()` in `try/except ValueError` and treats a non-JSON body as a
throttle — back off and retry, then raise the existing `RuntimeError` on exhaustion so the cooldown loop
catches it and resumes from cache. Soft bans now cool down gracefully instead of crashing. (ruff + 87
tests green.)
**State:** 48/128 shards saved (resumable). The IP is now *hard*-banned (empty bodies immediately), so
per our own resume guidance we are NOT retrying tonight — next attempt should be a different network or a
long (12–24h) rest. Pageviews remains the validated primary proxy; GDELT stays best-effort. See
`docs/gdelt-resume.md`.

### Merit had post-ceremony LEAKAGE on calendar years — rebuilt from match data (2026-06-21)
**Issue (a reviewer would catch on sight).** Merit aggregated **full seasons** via
`AWARD_YEAR_SEASONS`, and calendar-regime awards (2018/2019/2021) map to **two** seasons. So merit for
the Dec-2019 award folded in the *entire* 2019-20 season — most of which is played AFTER the ceremony.
The flagship case was the casualty: De Bruyne's "2019" merit was inflated by his future 20-assist
2019-20 (the leaked Jan–Jul 2020 half: xag 9.39, 8 assists), making him the single-highest-merit player
in the sample and the "robbed, identical-to-Messi" centrepiece. His real 2018-19 was injury-hit. This
**contradicted our own `docs/windowing.md`** (implication #1: calendar years need match-level data
summed by date), which the old code shortcut with full-season blends. Not caught by the robustness panel
(which only varied the *attention* window).
**Fix (the proper one, as the user asked).** New cached pull `understat.pull_matches()` (per-match
xg/xa/xg_chain/xg_buildup/goals/assists/minutes + match date from `read_schedule`; non-penalty xG via
`read_shot_events` — Understat leaves `situation=NaN` only on penalties, cross-checked by the constant
0.76 pen xG). `merit.py` attacking path rewritten to **sum match metrics inside each award year's
`perf_start..perf_end` window** (`_window_sum` / `_attacking_merit`), z-scored within (award_year,
attack) then PCA — leakage-free by construction. FBref defensive/CB/GK merit has **no match logs**, so a
shared `config.completed_season` rule gives calendar years the **most-recent completed season** (2019 ->
2018-19) instead of the look-ahead blend; the same rule fixes `team_success._season_codes` (cl_round /
won_league had the identical leak). New `understat_match` stage. 424,128 player-match rows pulled.
**Gotcha 1 (soccerdata bug).** `read_player_match_stats`/`read_shot_events` crashed mid-batch on a few
matches whose roster JSON is an empty `list` (`rosters["h"].values()` -> AttributeError, only
ConnectionError was caught). `_harden_read_match` widens the catch to return None; both callers already
`continue` on None, so bad matches are skipped (no parquet without it).
**Gotcha 2 (resume).** The pull is ~15k pages, network-throttled; it survived a PC restart and two
interruptions because soccerdata caches each match JSON — re-runs resume from the raw cache.
**Result — thesis HOLDS, slightly stronger.** Gate A (nomination) **+0.779 -> +0.733** (HDI [0.53,
0.95], P>0=1.00; robustness 0.76–0.79 every spec). Gate B (placement) **+0.186 -> +0.147** (HDI [0.02,
0.28], P>0=0.98; no-duopoly grazes 0). Ratio A/B **~5×** (was ~4×) — the "bias is in who gets
*considered*" payoff is sharper. De Bruyne 2019 merit 10.53 -> 8.54 (now ~5th, not #1); the
"identical-to-Messi" claim is dropped — new clean twin is **Lewandowski 2019 (merit 10.29, H⊥ −0.81) vs
Messi 2023 (10.37, +1.31)**. João Félix '19 / de Jong '19 (the non-top-5-league H⊥ artifacts) **vanish**
from the leaderboard — they had borrowed merit from a leaked covered season. CB face-validity gate now
`False` (Dias '21 0.44->0.33) — unchanged conclusion (documented positional-CB partial), CB still ships
via `_CB_MERIT_ENABLED`. (ruff + 92 tests green; report re-rendered; site/data.js regenerated.)

### Publication-hardening batch: effect sizes, bootstrap, Heckman, strict window, a11y, vendoring (2026-06-21)
Post-leak-fix upgrades to take the piece from correct → publication-bulletproof (user-selected).
- **Plain-language effect sizes (S1).** Logit coefficients are unreadable, so `report.effect_sizes`
  + `models/_report.average_marginal_effect` (rebuilds the bambi model, predicts observed vs a +1-SD
  counterfactual via `kind="response_params"`, no refit) now report **odds ratios** (Gate A **2.1×**,
  Gate B **1.16×**) and a Gate-A **AME of ~+9 pp** (a typical candidate ~19%→28%). Surfaced in the
  report two-gate section + dynamically on the site (`#gates-plain` ← `data.js.effects`). The per-SD
  log-odds scale is the honest basis for the "~5×" gate ratio (different likelihoods → directional).
- **Generated-regressor bootstrap (S2).** H⊥ is a first-stage residual, so naive gate CIs are
  optimistic. `robustness.bootstrap_hperp` resamples the de-fame pool (refit OLS → recompute H⊥) AND
  case-resamples the gate sample, refitting the frequentist anchors (n=400). *Gotcha:* a first version
  resampled only the de-fame stage → CI came out NARROWER than naive (captured only first-stage error);
  fixed to resample both stages → Gate A [+0.58,+1.10], Gate B [+0.04,+0.33] (still excludes 0).
- **Heckman selection check (S3).** `placement.heckman_check`: Probit nomination over the pool → IMR →
  OLS of logit(SV vote share) among finishers + IMR. Placement H⊥ keeps its sign (+0.19) with a wide
  CI crossing 0 — framed honestly as a sensitivity check (no clean exclusion restriction, small N).
- **Strict-window row (S4).** Made the merit window injectable (`merit._build_merit(windows=…)`,
  `hperp.hperp_frame(merit_df=…)`); `robustness._strict_windows` caps calendar perf_end at the ceremony.
  Both gates ≈ baseline (A +0.80, B +0.14) — the ~4-week tail is immaterial.
- **Panel/figure split.** bootstrap + heckman live in `robustness_panel` but are EXCLUDED from the
  caterpillar (different estimators/scales) via `report._CATERPILLAR_SPECS`; reported as prose notes
  (`report.robustness_extras`). strict_window IS comparable → shown in the caterpillar + site dropdown.
- **Accessibility (P1).** Palette already CVD-safe (amber/orange-red vs blue, not red/green); bumped
  `--muted`/`--faint` to WCAG-AA contrast; added `role="img"` + descriptive `aria-label` to all 7 site
  charts and `#| fig-alt:` to all 5 report figures.
- **Vendored the site (P3).** Downloaded D3 v7 + scrollama → `site/vendor/`, and the Fraunces/Inter
  woff2 + localized CSS → `site/fonts/`; `index.html` now has **zero external requests** (renders
  offline / archival-safe).
- **Repo for open-source (P2).** Added MIT `LICENSE` (+ data-attribution note); rewrote the stale
  README (was "scaffold, pulls stubbed"); fixed `.gitignore` (`*.html` was about to swallow the site's
  own `site/index.html` — added `!site/index.html`; the 26 MB report HTML stays gitignored/regenerated).
- Verified: ruff + **93 tests** green; report re-rendered; site offline-clean.

### Mobile polish — audited at iPhone width with headless Chrome (2026-06-21)
Drove a Selenium mobile audit (390×844, real device emulation, screenshots + overflow probe) of the
site and the Quarto report; neither had horizontal overflow, but found legibility/layout issues and fixed
all of them. **Site:** scrolly sticky-graphic was overlapping the step boxes (shortened graphic to 50vh +
opaque boxes); per-year scoreboard's 3 columns were cramped → **stack vertically** on phones in
`drawPerYear` (font sizes via `.style` so the `.lab` class can't shrink them); bumped in-chart fonts via a
`@media(max-width:760px)` block (scoped by chart id so it beats the class rules; per-year excluded);
scatter got tap-to-reveal tooltips + larger dots (no hover on touch); relaxed full-screen `min-height`
and disabled scroll-snap on mobile. **Report:** robustness caterpillar facets now stack vertically
(`facet_row`, cleaned `gate=` labels) instead of cramped side-by-side; disabled the plotly modebar
(`.show(config={displayModeBar:False})` per chunk — verified it embeds + still renders); suppressed
plotly's bundled-MathJax "MathZoom.js failed to load" banner via an `include-in-header` script/style.
Re-screenshotted to confirm; deployed (Pages run green, live URLs 200). ruff + 93 tests green.

### Public site rebuilt to a new editorial design + fully interactive charts (2026-06-21)
The user supplied a new design (`design.zip` → a Claude design-canvas prototype: React "dc-runtime"
`support.js`, `<sc-for>` placeholder loops, `{{vars}}`) — better for web + mobile — and asked to adopt
it and make the graphs interactive. Productionized it as a clean static site: dropped the runtime,
ported the editorial layout/copy/inline-styles verbatim (Bodoni Moda / Newsreader / IBM Plex Mono, warm
dark palette, plain-scroll — no sticky scrollytelling), and wired **real interactive charts** from the
existing `data.js`: de-faming example **tabs** (animated actual-vs-expected bars + readout), two-gate
bars (+0.73 / +0.15 with CI tooltips), a **188-point D3 scatter** coloured by Hype Score with 7 labelled
markers, the diverging leaderboard (descriptors curated from the design), the per-year breakdown
(curated verdicts), and the robustness strips — all hover + tap tooltips + on-scroll reveal. Curated
copy (leaderboard descriptors, de-faming notes, per-year verdicts) lives in `app.js` over the real data.
Vendored the 3 new fonts (24 woff2; zero external requests); removed scrollama. Validated headless:
0 JS errors, no horizontal overflow, every chart rendered, desktop + mobile screenshot-checked against
the design. Report + `src/` pipeline untouched. ruff + 93 tests green; deployed (Pages run green, live).

### 2026-06-21 — Publish-readiness round 2 (share meta, og:image, favicon, copyedit) + post-redesign chart fixes
After the redesign, a round of user-driven polish + a pre-publish sweep:
- **Scatter labels** went through three iterations on real mobile screenshots: thick stroke-halo
  (ate the glyphs) → dark pills (getBBox-positioned, still dim) → **soft-white text + a thin 1.7px
  outline** (`paint-order: stroke`), which is the legible one. Also: dropped Rodri '24's label (sits on
  Kvaratskhelia '23) and, on phones, show only the 4 well-separated anchors.
- **"Is it real?"** restored to a **labelled caterpillar** (one row per spec: main model, drop
  Messi&Ronaldo, drop low-fame, window past/before ceremony, leave-a-year-out) with estimate dot + 94%
  bar + inline value, per gate — the pre-redesign "show the options" view, restyled to the new vibe.
- **Per-year** now shows each face's real numbers again (`finished Nth · merit/Hype`) driven by
  `data.per_year`, keeping the curated verdicts (verdicts are about best-vs-winner, which still match;
  the "biggest story" column is the literal max-Hype player).
- **Leaderboard mobile overflow**: the value sat just past the bar end, so the top bar (Yamal +3.77)
  pushed its number off-screen. Now the label **flips inside the fill** (dark text) near the edge.
- **Scatter axis key**: added an explicit "↑ Vertical = attention · → Horizontal = merit" line above
  the chart (the y-label was hidden on mobile, leaving no axis context there).
- **Cache-busting**: version-tagged `styles.css/data.js/app.js` (`?v=`) — a cached `app.js` was why a
  fix that was live still looked broken on the user's phone.
- **Share readiness**: Open Graph + Twitter card + canonical + JSON-LD Article; **favicon.svg** (the
  scatter story in miniature — warm dot high, cool dot low); a generated **1200×630 og:image** card
  (Bodoni "Goals, or stories?" + the one-line finding, rendered via headless Chrome from a throwaway
  `og-card.html`). Privacy-friendly **GoatCounter** snippet added commented-out (needs the user's free
  site code to enable). Copyedit: `2018–2025` en-dash, `~210→~190` finisher-seasons (matches the
  188-point "every finisher" scatter), `centre-backs`/`30-player` consistency.
