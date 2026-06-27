# Ballon d'Or — Hype vs. Merit — Project Notes

> Living doc for design decisions and methodological guardrails. Updated 2026-06-18.

## Thesis (refined)

**Not** "Hype vs. Merit" as a clean binary — they're heavily confounded (players get
hype *because* they produce, and narrative is itself partly a merit signal). The honest,
more interesting question:

> **Does narrative/attention have *independent* explanatory power for Ballon d'Or
> outcomes *after controlling for* on-pitch production and team success?**

If hype survives as a predictor once conditioned on npxG+xA, team results, and
tournament performance — that's the story. If it doesn't, "they're inseparable" is
itself the conclusion. Plan the writeup around this conditional question, not the versus.

## Scope

- Ballon d'Or top-5 finishers, 2008–2025 (post-FIFA-merger era is cleaner). N ≈ 85–90
  player-seasons. **Small N → interpretation project, not prediction.** Frame as a
  feature on what wins the award, with a small *descriptive* modeling demo — not a
  predictive flex.
- Lead with case studies; let the model be connective tissue, not the headline.

## Guardrails (do not violate)

### 1. Reframe thesis as conditional, not versus
Hype and merit are collinear. SHAP won't cleanly separate them. Don't hide this —
the conditional question ("hype's marginal contribution after production") *is* the
finding. Bootstrap feature importances and show the CIs are wide.

> **Windowing dates are now locked** in [docs/windowing.md](docs/windowing.md) — per-year
> performance & hype windows, shortlist/ceremony dates, regime split (2017–2025).

### 2. Reverse-causality / data-leakage on hype features — CRITICAL
Pageviews + news mentions spike *after* the December announcement every year.
Aggregating hype over the full calendar year leaks the outcome into the predictor.
- Window hype proxies to the **qualifying period only** (the season before the vote,
  ending **before** the shortlist/ceremony).
- Decide windowing **early** — it changes data collection.
- A sharp reader will call this out → reputational as well as methodological.

### 3. Small-N modeling needs humility baked in
Ordinal logistic on ~85 rows with ~12 correlated features overfits; coefficients
unstable. Fine for *descriptive* SHAP narrative, dangerous as inference.
- Lean descriptive. Bootstrap importances, show wide CIs.
- "Here's how unstable these rankings are with this little data" > a clean bar chart.

### 4. Case studies are what people actually read — build around them
- Modric 2018 (low production, won)
- Lewandowski 2020 (huge production, robbed — and the award was **cancelled**; handle that)
- Benzema 2022 (narrative + CL)
- Ronaldo 2013 (FIFA extended the voting deadline — hype-vs-merit poster child)
- Messi 2010 (original list)
Build the piece around 3–4 of these; model connects them.

## Modeling design — the nomination→placement funnel (Tiers 0–2)

Tiers 0–2 are **one funnel, not three analyses.** A player passes two gates:
- **Gate A — Nomination:** of everyone who had a good season, who makes the 30-man list?
- **Gate B — Placement:** given you're nominated, who actually places / wins?

This is a **two-stage (hurdle) model**, so the hype question gets asked *twice*:

| Stage | Pool | Outcome | Model | Hype question |
|---|---|---|---|---|
| **A: Nomination** | Tier 2 candidate pool | nominated? (binary) | logistic, class-weighted | Does attention get you *noticed* beyond your stats? |
| **B: Placement** | Tier 1 (the 30) | vote share | beta regression | Once in the room, does attention move you *up*? |
| B′ (sharp end) | Tier 0 (top 5) | vote share | beta | sanity-check Stage B at the top |

**Why this is the better story:** hype may matter at one gate but not the other.
Working hypothesis — **narrative does most of its work at Gate A** (getting an
unglamorous-but-productive player onto voters' radar), while Gate B is more
merit/team-success driven because the field is already curated. If the data shows
that → headline becomes *"the Ballon d'Or's bias isn't in who wins, it's in who gets
considered."*

### Tier 2 candidate pool — definition (the critical design choice)
The pool defines the counterfactual ("snubbed should-have-beens"). Fail modes:
- **Too narrow** (top forwards by npxG+xA only) → biases toward attackers, drops the
  defenders/keepers/deep-mids who actually place (Kanté '17, Van Dijk '19, Modrić '18,
  Rodri '24).
- **Too wide** (every starter in 5 leagues) → non-nominees are squad players, not real
  counterfactuals; logistic separates them trivially on raw stats and hype never gets
  tested.

**Fix — mirror how voters generate candidates: a UNION of three merit-based sources,
deduped** (~80–120 players/season, top-5 leagues):
1. **Production pool** — per-position top-N each season (position-stratified, minutes-qualified).
2. **Team-success pool** — significant-minutes players from CL semifinalist clubs + domestic-league winners.
3. **Tournament pool** — standouts from that cycle's WC/Euros semifinalist squads (StatsBomb).

**Every inclusion rule is merit/team-based, NEVER attention-based** — so testing hype
*within* the pool doesn't bake in the answer. This is the whole game.

#### Pool construction — locked

Three principles:
1. **Bias toward inclusion.** False candidate = cheap (Stage A sorts it out); missed
   candidate = expensive (it's the snub the thesis needs). Generous N, modest minutes floor.
2. **Rank cross-league in ONE pool**, not top-N per league (don't over-sample weak leagues).
   FBref xG is one model across all 5 leagues → comparable. Rank globally *within each
   position stratum*.
3. **Dual metric per stratum:** an expected/skill per-90 rate + a raw volume total; union
   them. Catches both the efficient low-minutes guy and the durable high-volume star.

| Stratum | Expected metric (/90) | Volume catch (total) | Min mins | Top-N each |
|---|---|---|---|---|
| Forwards / wingers / att. mids | npxg + xag | G + A | 1500 | 30 |
| Central / defensive mids | xag + xg_chain + xg_buildup | G + A + key_passes | 1800 | 20 |
| Defenders (CB + FB) | — (team-success pool only — Understat has no defensive metric) | — | — | — |
| Goalkeepers | — (team-success pool only — Understat has no keeper metric) | — | — | — |

> REVISED (Understat): the dropped SCA/progression metrics are replaced by xg_chain/xg_buildup
> for outfield creators; defenders & keepers now have NO production-pool route and enter only
> via the team-success + tournament pools.

- Union the two lists per stratum + dedupe → production pool ≈ 70–90/season. Union with
  team-success pool (CL semifinalists + league winners) + tournament pool (WC/Euro years) →
  ~80–120/season after global dedupe.
- **Defenders/keepers lean on the team-success pool by design** — individual defensive stats
  poorly predict nomination (Van Dijk '19 = team success + reputation). Modest production-N
  for them is intentional, not a compromise.
- **xAG over raw assists** for the skill metric (more stable); raw assists in the volume catch.
- **Position assignment:** by where the player logged the most minutes, NOT the FBref label
  (fields are messy: `FW,MF`). Hybrids (Messi) → Forwards.

#### Temporal constraint — DECIDED (spine drops 2017)
xG only exists from **2017–18 onward** (Understat covers 2014–15+, but the 2017 *award*'s
Jan–May half falls in 2016-17 which we don't need once 2017 is dropped). Combined with
pageviews-since-2015:
- **Spine = 7 award years: 2018, 2019, 2021, 2022, 2023, 2024, 2025** (`config.SPINE_YEARS`).
  2020 cancelled; **2017 dropped** (xG-edge) → all 8 needed football seasons are xG-clean.
  ~7 × ~100 ≈ 700 Stage-A rows; Tier 0 ≈ 35 rows.
- **2017 + pre-2017 = degraded/qualitative panel** (`AWARD_YEARS` keeps 2017's outcome). G+A
  only; not the same dataset — don't merge as if it is.

### Consistency rules across all three tiers
- **Same hype windowing** (cut at shortlist date, follow 2022 eligibility shift) — or the
  funnel isn't comparable.
- **Same H⊥ construction** (de-fame → residualize vs merit index). Stage A and Stage B use
  the *same* orthogonalized hype feature so its effect is directly comparable across gates.

### Honesty caveat
Stage B conditions on passing Stage A (selection on outcome). Two-stage hurdle is fine for
a descriptive blog; the rigorous version is a **Heckman selection correction** — name it as
the principled extension, don't over-engineer v1.

### Outcome variable (applies to Stage B / Tiers 0–1)
Use **vote points / vote share**, NOT rank or won-vs-not. Points encode *margin* (Modrić
edging Ronaldo ≠ Messi lapping the field). Beta regression on share among the relevant pool.
Reason binary is bad: ~13 of 18 winners are Messi/Ronaldo → "won" model mostly learns to
recognize two players. Report results with AND without the duopoly.

### Merit index — LOCKED (REVISED 2026-06: source = Understat, not FBref)
> **Source change (forced).** FBref stopped serving advanced stats publicly (confirmed via
> soccerdata + a manual browser check). Performance now comes from **Understat** (JSON, no
> Selenium). Available metrics: goals, assists, **xg, npxg, xag (xA), shots, key_passes,
> xg_chain, xg_buildup**, minutes, position. **GONE:** progressive passes/carries, SCA,
> tackles/interceptions/blocks, PSxG−GA. Consequence: **defender & keeper strata have NO
> individual production metric → they enter the Tier-2 pool via the team-success + tournament
> pools ONLY** (already their locked route). xg_chain / xg_buildup act as a buildup-involvement
> proxy for the dropped progression metrics. The structure below stands; only the available
> column set is thinner (see the revised tables).

Goal: squeeze the available production stats into 1–2 summary "merit" numbers. **Merit is a
CONTROL, not the headline** (the star is H⊥ = attention beyond merit) → prioritize
completeness/defensibility over pretty axes. The better merit absorbs on-pitch quality, the
more credible that residual hype is real.

**Backbone = `merit_z`: within-position-season z-scores.** (Confirmed.)
- Standardize each stat relative to positional peers *that season* → "how dominant for your
  role." Makes positions comparable (a +2SD keeper and +2SD forward both readable), and
  auto-partials-out era inflation + league scoring trends.
- The award's forward-bias is NOT baked into merit — it's estimated by the model via position
  terms. Merit = "how good for your role"; model learns "voters reward a forward's dominance
  more than a fullback's."

**Include BOTH expected AND actual output** (npxG *and* goals, xAG *and* assists). (Confirmed.)
- Reason: finishing overperformance (scored 30 on 22 xG) is merit *in voters' eyes*. If merit
  is xG-only, that overperformance leaks onto the hype residual = misattribution. Let merit
  absorb it. Also include season totals + minutes so durability counts, not just per-90 rates.

**Squeeze method — three, in priority order:**
1. **PCA → 1–2 axes (PRIMARY).** Auto-finds axes: PC1 ≈ output/volume, PC2 ≈ finisher-vs-creator
   style. Key benefit: axes are *orthogonal* → the residualization (predict hype from merit,
   take leftover) is mathematically clean. Report loadings WITH bootstrap (loadings unstable at
   this N — don't over-claim PC2's meaning).
2. **Ridge / elastic-net on standardized stats (ROBUSTNESS).** Keeps all 12, regularization
   keeps estimates stable despite overlap. If H⊥ holds whether merit = PCA-axes or ridge-fit →
   reassuring.
3. **A-priori npxG+xAG/90 composite (ANCHOR).** Transparent, blog-friendly headline version.
   Throws away info → check, not workhorse.

**Cross-position construction** (REVISED to Understat-available metrics):
| Family | Quality (/90, z within pos-season) | Output/volume (totals) | Reduce via |
|---|---|---|---|
| Attacking (FW/W/AM/CM) | npxg, xag, npxg+xag, xg_chain, xg_buildup | goals, assists, G+A, shots, key_passes, minutes | PCA → 2 axes + `merit_z` |
| Central/def mids | xag, xg_chain, xg_buildup, key_passes | G+A, minutes | composite → `merit_z` |
| Defenders | *(no individual metric available)* → team-success pool only | minutes | — |
| Keepers | *(no individual metric available)* → team-success pool only | minutes | — |
Position from Understat is coarse (`F`/`M`/`D`/`GK` combos, e.g. "F S", "D M S") — map to a
family by the dominant letter; fine for stratification.

- **Stage A** (nomination, all positions): `merit_z` + position dummies + team-success block +
  tournament. Cross-position → scalar mandatory.
- **Stage B** (placement, ~80% attackers): attacking PCA axes + `merit_z` for non-attackers +
  team-success. Run both "axes" and "scalar-only" versions.

**Stays OUT of merit (separate third block):** team-success/tournament (CL round ordinal, won
league/CL binary, major-tournament result ordinal). It's the confound hub — merit-correlated
AND hype-generating. Residualize hype against BOTH merit AND this block (see step 3 below) so
winning-CL hype doesn't masquerade as pure narrative.

### H⊥ (de-fame + residualize) — LOCKED
The hype-side mirror of the merit index. Raw pageviews mix 3 things: (1) **baseline fame**
(Messi = 10× traffic every season, a near-constant), (2) **performance-driven attention**
(merit leaking into hype), (3) **narrative excess** (what we want). Subtract (1) and (2),
the leftover = H⊥.

**Baseline fame = trailing-12-month pre-window MEDIAN, in LOGS.** (Confirmed.)
- Window = the 12 months ending the day the performance window starts (e.g. 2017 award →
  baseline = all of 2016; 2023 award → 2021-08-01→2022-07-31). Predetermined → leakage-safe.
- **Median** not mean (robust to transfer-saga spikes). **Logs** because pageviews are skewed +
  multiplicative → de-fame is a *ratio*: log(window views) − log(baseline) = "how many × above
  his own normal." A 50% bump reads the same for Messi and a fullback.
- **Why 12mo (not 24):** pageviews API starts Jul 2015; a 24mo baseline for the 2017 award would
  need early-2015 (uncovered). 12mo is the longest window clean across the whole spine. Footnote it.
- Naturally handles rising stars: if attention rose in step with production, the merit step zeroes
  it; if faster (PSG glamour, marketing), H⊥ catches it — which is the question.

**ONE combined regression, not two sequential steps.** (Confirmed — cleaner than de-fame-then-residualize.)
> H⊥ = residual of:
> **log(window attention) ~ log(baseline) + PCA merit axes + `merit_z` + team-success block**
- `log(baseline)` absorbs fame; merit terms absorb performance-driven attention; residual =
  narrative excess. Bonus: read the `log(baseline)` coef = "how much of attention is just fame."
- Collinearity among these controls is FINE — it muddies individual coefs, not the residual.
  (Opposite of the outcome model, where collinearity DID matter.)

**Window summary = MEAN DAILY views over the exact window.** (Confirmed.)
- Use **daily** pageviews (API provides from 2015-07), not monthly — the window ends on a precise
  shortlist date; monthly would smear across the leakage boundary.
- **Peak day** = later enrichment (a single iconic moment can drive outsized narrative); not core v1.

**Language editions = ALL languages summed.** (Confirmed — chose accuracy over the pragmatic basket.)
- Enumerate each player's language editions via **Wikidata sitelinks**, sum pageviews across all.
- Heavier pull, but makes the **media-prominence-bias finding airtight** (H⊥ feeds a cross-player
  model → cross-player comparability matters; English-only would under-count non-EN-sphere players).
- Loops back to the "media bias is partly the finding" thread.

**Newcomers / thin baseline:** (Confirmed.) A breakout teen may have ~no Wikipedia presence 12mo
prior → tiny baseline → log-ratio explodes. Fix: **add a small pseudocount before logging** +
**flag low-baseline player-seasons** for a with/without robustness check. Say upfront: hype signal
unreliable for first-season breakouts.

**Generalizes per proxy:** same recipe (own baseline → log-ratio → residual) applies to GDELT &
Reddit. Each proxy gets its own baseline + residual; combine standardized residuals. Pageviews =
the template.

### GDELT — LOCKED
Goal: a clean, disambiguated news-volume number that drops into the SAME de-fame template.
The differentiator signal, but the messiest — disambiguation is the whole job.

**Product:** (Confirmed.)
- **GKG (Global Knowledge Graph) via BigQuery = backbone** — extracts canonical *person entities*
  + *themes* per article (what makes disambiguation possible). Coverage Feb 2015 → spans spine.
  Free tier (1 TB/mo) covers it.
- **DOC 2.0 API = prototyping** (free, no-auth, ready-made volume/tone timelines, 2017+).
- Natively **multilingual** (65+ langs) → matches the all-language pageviews decision, reinforces
  the media-prominence-bias measurement.

**Disambiguation stack** (collisions are catastrophic for Son/Mount/Sterling/Saka/Mané/Rodri/Kane):
(Confirmed.)
1. GKG **person-entity** match, not raw text.
2. AND **football-theme filter** (GKG `SOCCER`/sports tags) — kills "son"/"mount" noise.
3. **Full-name + alias phrases, accent-normalized** (Mbappé/Mbappe). **Reuse Wikidata "also known
   as" aliases** — already hitting Wikidata for pageview sitelinks → alias list is free.
4. **Validate precision:** sample matched articles for collision-prone names, report rough
   precision per flagged player, exclude/down-weight dirty ones. Honesty move — say so in writeup.

**Off-pitch news decision:** (Confirmed.)
- **Primary signal = football-disambiguated volume** (entity + football theme; doubles as the
  disambiguation filter).
- **Off-pitch attention = labeled SECONDARY feature** (player-entity volume outside sports themes;
  transfers still count as football). Kept because off-pitch notoriety = legit "narrative beyond
  merit," BUT sparse + **sign on votes ambiguous** → case-study sidebar (Benzema 2022 trial), not
  core v1 modeling.
- **Coherence caveat (flag honestly):** pageviews are *unfiltered* (Valbuena-trial spike counts in
  pageview H⊥); GDELT-primary is football-filtered. Each proxy de-famed/residualized/standardized
  *separately* before combining → acceptable, but a real asymmetry worth one sentence.

**Plumbing:** (Confirmed.)
- **Normalize via GDELT %-of-all-articles intensity**, NOT raw counts (GDELT indexes more sources
  each year → raw volume inflates over time). DOC `timelinevol` already does this.
- Then identical de-fame template: own trailing-12mo baseline → log-ratio → residual. No new machinery.
- **Tone = optional enrichment** (separates positive narrative vs scandal volume; useful for the
  off-pitch sign question). Later add, not v1 core.

### Conditional spec (operationalizes the thesis)
1. Build merit per **Merit index — LOCKED** above (PCA primary). ~12 stats → ~2 axes + `merit_z`,
   plus the separate team-success block. Small N can support this.
2. Build H⊥ per **H⊥ (de-fame + residualize) — LOCKED** above: one regression of log-attention on
   log-baseline + merit + team-success → residual = **excess attention unexplained by merit/fame.**
   H⊥'s coefficient in the outcome model IS the thesis in one number.
3. Feed H⊥ (+ merit + team-success + position) into the two-gate outcome models (Stage A
   logistic, Stage B beta) — see funnel design.
4. Fit Bayesian via **PyMC (using bambi)** — formula syntax, weakly-informative priors, year
   group effect → headline is the **posterior of the H⊥ effect**; a credible interval crossing
   zero IS the finding. (DECIDED over sklearn+bootstrap: at N≈85 with year-clustering + duopoly
   dominance, bootstrap CIs are *less* trustworthy — block-bootstrap on ~8 year-blocks is thin;
   Bayesian + weak priors + partial pooling degrades gracefully and the posterior IS the
   deliverable. bambi kills the PyMC boilerplate.) Cost: minute-scale fits + MCMC diagnostics →
   cache fitted model objects so Quarto doesn't refit on render.
5. **Robustness panel** (coefficient-stability plot of H⊥): with/without duopoly; shortlist
   vs ceremony window (shows the leakage); pageviews-only vs +GDELT; with/without off-pitch
   news. SHAP demoted to descriptive + bootstrapped.

## Stack / data (from original plan)

- Performance: **Understat via soccerdata** (Python, JSON). Per-season goals, assists, xg, npxg,
  xag, shots, key_passes, xg_chain, xg_buildup, minutes, position. (FBref was the original plan
  but stopped serving advanced stats publicly — 2026-06.) Team-level (CL round, league position,
  won league/CL) + StatsBomb open data for Euros/WC tournament features: still TODO.
- Awards results: Wikipedia tables via pandas `read_html`.
- Hype proxies:
  - **Wikipedia pageviews API** — free, no auth, monthly back to 2015. Best S/N. Do first.
  - **GDELT** — free global news index, mentions/tone by month. The differentiator.
  - pytrends (Google Trends) — increasingly broken (429s, empty returns). **Garnish only**,
    not load-bearing. Say so as a limitation.
  - Reddit via PRAW — r/soccer mention counts. Garnish.
  - Skip Twitter/X — API paywalled. Mention as limitation.
- Python + pandas + scikit-learn + SHAP. Plotly/Altair. Quarto blog or polished notebook.

### Stack — LOCKED (Python-only, single language)
- **Core:** pandas · soccerdata (**Understat** — FBref dropped) · scikit-learn (PCA merit index +
  Stage-A classifier) · shap (descriptive + bootstrapped).
- **statsmodels** — REQUIRED: the FWL residualization (→ H⊥) + beta regression (Stage B vote
  share) + ordinal logit. sklearn can't do beta regression / inferential output.
- **PyMC via bambi** — the Bayesian outcome models (DECIDED over bootstrap; see Conditional spec
  step 4). bambi = brms-like formula syntax, all Python.
- **Glue:** requests (Wikipedia pageviews API, GDELT DOC API, Wikidata SPARQL — soccerdata is
  football-stats only) · google-cloud-bigquery (only if GDELT GKG backbone vs lighter DOC API) ·
  pyarrow (parquet cache) · plotly or altair (charts).
- **Quarto** = publish layer (executes Python inline, renders the blog — subsumes "narrative
  notebook" role). No R / brms — stay single-language.

### Repo shape — DECIDED
- `src/` = cache-first pulls + feature builders + model code (reproducible spine). NOT notebooks —
  pulls are slow/rate-limited/idempotent; need resumability, diffs, testability.
- `data/raw/` + the bulky/re-pullable `data/cache/` shards = gitignored. But a **frozen analysis
  snapshot** (the derived model/feature outputs + `*.nc` posteriors + the assembled attention/news
  signals, ~15 MB) IS committed, so the published site/report/headline reproduce **offline, exactly**
  from a clone — a re-pull would drift. `data/reference/` (curated CSVs) is committed. See README.
- `*.qmd` = Quarto case studies + results → the blog ("notebooks that ship"; the repo has no scratch
  notebooks dir — exploratory work is disposable, logic lives in `src/`).
- `run.py` / Makefile = orchestrate stages. Cache fitted Bayesian model objects (slow fits).
- Rule: imported/re-run → module; read by a human → notebook/Quarto. Slow Bayesian fits → script
  that caches model objects; `.qmd` reads results.

## Scope decisions

- **Streamlit demo**: nice LinkedIn hook but lowest ROI / highest time-per-insight.
  First thing to cut if weekends slip. Do NOT let it eat GDELT work. Clean Quarto post
  with strong visuals beats a janky app.
- **Women's Ballon d'Or** (since 2018): compelling extension *or* scope trap (sparser
  media coverage, different attention dynamics). Future work, not v1.
- Wikipedia pageviews API only goes back to 2015 → hype features only available for
  ~2015–2025 seasons. Pre-2015 case studies (Messi 2010, Ronaldo 2013) are
  qualitative/illustrative, not in the modeled hype dataset. Note this gap explicitly.

## Title

Avoid "Twelve Years of Data Say…" — overpromises certainty for N=85 descriptive work,
and it's ~18 years now (2008–2025). Prefer something signaling nuance:
> "The Ballon d'Or Rewards Goals. It Also Rewards Stories. Can You Tell Them Apart?"
Honest answer: "mostly no — and that's the interesting part."

## Phases (≈4 weekends)

1. Data collection — awards results + performance stats first (boring, cache once).
2. Hype features — Wikipedia pageviews first, then GDELT. **Get windowing right here.**
3. EDA + case studies — the part people read.
4. Modeling — conditional spec (see separate methodology sketch). SHAP + bootstrapped CIs.
5. Writeup (+ Streamlit demo if time).
