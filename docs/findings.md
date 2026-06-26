# Findings log

Analytical discoveries as they happen — results, sanity checks that land, interpretable cases.
Honestly caveated. Newest at the bottom. These are the seeds of the writeup.

**Standing caveat (read first):** everything so far is **descriptive and pre-model**, computed on
the **awards finishers only** (a selected, high-attention sample), N is small (169 player-years;
H⊥ on 136 complete cases). The fame→attention relationship is estimated *among finishers*, which
will shift once attention is extended to the full Tier-2 pool. Treat these as direction, not proof.

---

### Pageviews: all-language ≫ English (media-prominence angle) (2026-06-19)
Messi's all-language Wikipedia traffic is **2.7× English-only** (across 181 language editions). This
is the seed of the "media-prominence bias" thread and the concrete justification for the
(expensive) all-language decision. Daily series spike on events (Messi 2022-12-18 WC final ≈ 6.9M
views vs ~0.5M baseline), confirming the attention signal is real and event-driven.

### Merit index leaderboards are credible after the durability fix (2026-06-19)
Top merit_z per year are the genuine elite producers (Mbappé, Lewandowski, Messi, Kane, Salah).
Messi's peak Barcelona seasons dominate (2018 z≈4.5, 2019≈4.1). PCA captures ~83% of attacking
variance in two axes (PC1 = output/volume ≈ 59%). Defenders/keepers correctly carry NA merit.

### H⊥ works: fame is absorbed, narrative is isolated (2026-06-19) — **headline so far**
The attention regression `log(window) ~ log(baseline) + merit(PCA) + team-success` has R²≈0.59;
`log(baseline)` (fame) dominates, merit/won_cl/tournament are positive. The residual H⊥ behaves:
- **Fame absorbed** — the Messi/Ronaldo duopoly does **not** top H⊥ (Messi 2018 H⊥≈+0.55), because
  their baseline fame is controlled. The de-fame step does what it's supposed to.
- **Won on merit, not narrative** — Benzema 2022 (winner) has H⊥≈+0.20: his attention is explained
  by elite merit + the CL win, with little narrative excess.
- **Robbed of narrative (negative H⊥)** — **De Bruyne 2019**: the *highest* merit (PC1≈10.5) yet a
  *negative* H⊥ — elite production, modest attention. **Jorginho 2021**: won Euro + CL, finished 3rd,
  but quietly (H⊥≈−2.07). The "underrated" profile, quantified.
- **Narrative darlings (positive H⊥)** — Lamine Yamal 2024 (16-yo Euro-winning wonderkid),
  Messi 2023 (World Cup), Ronaldo 2018 (Juventus transfer saga), Kvaratskhelia 2023.
- **The thesis in one comparison:** Messi-2023 and De Bruyne-2019 have ~equal elite merit (PC1≈10)
  but opposite H⊥ — same production, opposite narrative. That contrast is the whole project.

> Open question for the model: does H⊥ (narrative beyond merit+team-success) have *independent*
> explanatory power for vote share, or is it absorbed once merit/team-success are in? That's Stage B.

### Stage B answers it: narrative has independent pull on placement (2026-06-19) — **the headline**
The placement model — Beta regression of **vote share** on H⊥ + merit + team-success with a per-year
group effect (`vote_share ~ h_perp + merit_pc1 + merit_pc2 + cl_round + won_cl + won_league +
tournament_result + (1|award_year)`), fit on the attacker-finishers — gives a **clearly positive
H⊥ effect**:

| Model | H⊥ posterior mean | 94% HDI | P(H⊥>0) |
|---|---|---|---|
| Full (N=157) | **+0.291** | [+0.15, +0.43] | **1.00** |
| Drop Messi/Ronaldo (N=149) | **+0.231** | [+0.084, +0.38] | **1.00** |

> *Updated 2026-06-19:* re-fit on the **corrected** `model_features` (N 136→157) after fixing a
> raw-name join bug that had dropped 41 finishers — incl. **Modrić (2018 winner)**, Mbappé — from the
> table (see decisions log). The headline barely moved (+0.285→+0.291) and the no-duopoly case
> *strengthened* (+0.202→+0.231, HDI now further from 0): the result was robust to the omission.
> Original figures were Full(136)=+0.285 [0.13,0.43], no-duo(128)=+0.202 [0.034,0.36].
> **Superseded by the pool-wide refit (both-gates section below): Stage B settled at +0.192 — the
> figure of record. +0.291 is the finisher-fit interim.**

- **The thesis lands the unintuitive way.** Going in, the working hypothesis (PROJECT_NOTES) was that
  narrative does its work at **Gate A** (who gets *noticed*), and that placement among the curated 30
  would be merit/team-driven. Instead, even *inside the room*, attention-beyond-merit still moves you
  **up the vote** — a standardized H⊥ slope (+0.285 on the logit) comparable in size to merit itself
  (`merit_pc1` ≈ +0.45). The Ballon d'Or rewards the story, not just the goals, at the sharp end too.
- **It survives the duopoly.** The obvious worry is that Messi/Ronaldo (8 rows, huge attention + huge
  vote share) manufacture the effect. Dropping them **attenuates but does not kill** it: mean +0.20,
  HDI still excludes zero (P>0 = 0.99). So it isn't just two superstars.
- **Diagnostics are clean** (R̂ = 1.00, ESS ≈ 3–5k across terms) and a frequentist anchor agrees
  almost exactly (statsmodels Beta, no year RE: H⊥ = **+0.277**, 95% CI [0.13, 0.42], p = 2e-4) — the
  result isn't an artifact of priors or the sampler.
- Sane controls: `merit_pc1` strongly positive (+0.45), `won_league` positive (+0.39), `won_cl`
  positive but wide; `merit_pc2` (style axis) ≈ 0. H⊥'s coefficient is cleanly identified because H⊥
  is, by construction, orthogonal to those controls.

> **Caveats (honest).** Stage B conditions on *being a finisher* (selection on the outcome) — the
> principled fix is a Heckman correction; this is the descriptive v1. It speaks only to **attackers**
> (defenders/keepers have no H⊥). Attention proxy = pageviews only so far (GDELT paused at 43/128).
> N is small (157 across 7 years). Still: as a *direction*, the answer to the project's central
> question is **yes — narrative has independent explanatory power for who places, beyond merit and
> team success.**

### The Tier-2 candidate pool, and Stage A (nomination) baseline (2026-06-19)
Built the candidate universe Stage A runs over — **production ∪ team-success**, ~150–230 players/yr
(1269 rows over 7 years), inclusion merit/team-based only. Quality check = **nominee recall**: the
sources recover **86%** of the 30-man shortlists (180/210; per year 77–97%). The ~14% missed are the
honest gaps — non-top-5-league nominees (Ajax-type, no Understat), defensive mids on non-winning
clubs (Kanté '18, Pogba), and sub-top-50 attackers shortlisted on reputation/narrative (themselves a
hint of the thesis). Defenders & keepers *are* captured, via the team-success route.

**Stage A (preliminary, H⊥-free)** — Bernoulli logistic over the pool, `nominated ~ merit_z +
C(position_family) + cl_round + won_cl + won_league + (1|award_year)`:
- Everything points the sensible way: **merit_z = +1.46** (decisive, P>0=1.00), **won_cl +0.78**,
  **won_league +0.61**, **cl_round +0.55** — individual merit and deep team runs both strongly raise
  the odds of being shortlisted. Keepers who reach the pool are disproportionately nominated (+1.04;
  only elite keepers on big clubs get in), defenders ≈ baseline. R̂≈1.00, year-grouped CV **ROC-AUC =
  0.845** — the pool + merit/team features separate nominees from non-nominees well.
- This is the **baseline that validates the pool**; it does *not* yet test the thesis at Gate A.
  Whether **attention** gets you noticed beyond your stats needs H⊥ for the non-nominees (a pool-wide
  pageview pull) — the next batch. The interesting question it sets up: once H⊥ is added, does it lift
  nomination odds *after* merit + team-success, the way it lifts vote share at Stage B?

### The thesis at BOTH gates: narrative's bias is in who gets *considered* (2026-06-19) — **the payoff**
Pulled all-language pageviews for the **443** non-nominee pool players (558/571 of the universe
resolved; 13 no-coverage gaps logged), refit H⊥ **pool-wide** (de-fame regression now estimated on
**728 attacker candidates**, not 136 finishers — R²≈0.73, fame `log_baseline`≈+0.65 dominant), and
added H⊥ to Stage A. The two gates can now be compared on the same orthogonalized H⊥, both logit-link:

| Gate | what it asks | H⊥ (std, logit) | 94% HDI | P(H⊥>0) |
|---|---|---|---|---|
| **A — nomination** | do you get *noticed* (make the 30)? | **+0.72** | [+0.50, +0.95] | **>0.99** |
| **B — placement** | given noticed, do you finish *higher*? | **+0.19** | [+0.04, +0.34] | 0.99 |

- **The working hypothesis lands.** PROJECT_NOTES predicted narrative does most of its work at
  **Gate A** (getting an unglamorous-but-productive player onto voters' radar) and that Gate B is more
  merit/team-driven once the field is curated. Exactly so: **H⊥'s pull on *nomination* is ~4× its pull
  on *placement*** (+0.72 vs +0.19). At Gate A, narrative-beyond-merit is ~45% the size of merit
  itself (`merit_z`≈+1.59) — a big, decisive effect (P>0>0.99). **The Ballon d'Or's attention bias is
  mostly in *who gets considered*, not in who wins among those considered.**
- **Merit still rules nomination** (`merit_z`≈+1.59) and H⊥ is *added on top* without denting it
  (H⊥ is orthogonal to merit by construction) — so this is genuine narrative lift, not merit in
  disguise. Team-success stays positive (won_league≈+0.85, won_cl≈+0.71, cl_round≈+0.53). R̂=1.0.
- **Stage B softened** with the pool-fit H⊥: +0.291 → **+0.192** (HDI [0.04, 0.34], P>0=0.99), and the
  no-duopoly case is now *marginal* (+0.148, HDI [−0.01, 0.30], P>0=0.96). Expected — H⊥ is now
  de-famed against 728 candidates, a more honest baseline than the 136 finishers. The placement effect
  is **real but modest**; the nomination effect is the strong one. This *strengthens* the story: the
  bias concentrates at the gate the public never sees.

> **Caveats.** Gate A H⊥ is **attackers-only** (no Understat merit for defenders/keepers → H⊥
> undefined; they sit in the H⊥-free baseline). Pageviews-only proxy (GDELT still paused). The two
> coefficients live on different outcome scales (Bernoulli vs Beta) so "4×" is directional, not exact.
> Stage B still conditions on being a finisher (selection); Heckman is the principled extension.

### Robustness panel: the Gate-A finding is bulletproof; Gate B real but modest (2026-06-20)
Re-fit the H⊥ coefficient across specifications with fast **frequentist anchors** (statsmodels Beta /
Logit; they track the Bayesian posteriors — Stage B +0.192 Bayes ≈ +0.195 freq). The estimate barely
moves:

| Spec | Gate A (nomination) | Gate B (placement) |
|---|---|---|
| baseline | +0.772 | +0.195 |
| no_duopoly | +0.761 | +0.149 (CI grazes 0) |
| drop_low_baseline | +0.772 *(vacuous — 0 low-baseline players in the fit)* | +0.195 |
| window_leaky (ceremony+21d) | +0.776 | **+0.221** |
| jackknife (leave-one-year-out) | +0.747, spread [+0.68, +0.88] | +0.194, spread [+0.11, +0.26] |

- **Gate A is rock-solid.** H⊥ sits at **+0.75–0.78 across every specification**, CI always far from
  zero, year-jackknife spread tight — no single year, the duopoly, or any choice drives it. The
  "narrative gets you *noticed*" headline is about as robust as this N allows.
- **Gate B is stable but smaller and partly duopoly-leaning** — drop Messi/Ronaldo and the CI grazes
  zero (+0.149, [−0.01, +0.30]), consistent with the Bayesian no-duopoly cell. The placement effect is
  real but should be stated as *modest / duopoly-sensitive*, not headline.
- **The leakage guardrail, demonstrated.** Pushing the hype window past the ceremony (capturing the
  winner-announcement pageview spike) **inflates Stage B H⊥ +0.195 → +0.221** but leaves Stage A
  unmoved — exactly right, since nomination is decided *before* the ceremony. So the shortlist cut
  matters in the expected direction (and, reassuringly, even the leaky version only inflates ~13%
  because the 12-month window mean dilutes the spike). The guardrail isn't paranoia, but it isn't
  load-bearing for the headline either.
- **`drop_low_baseline` is vacuous here** — 0 of the modeled attackers are low-baseline (they're all
  established top-merit/finisher players). The newcomer-instability worry doesn't bite this sample;
  reported for honesty, not because it moved anything.

### Tournament pool closes the recall gap; a national-team run gets you noticed (2026-06-20)
Added the 3rd pool source — **semifinalist squads** from StatsBomb open data (WC2018, Euro2020, WC2022,
Euro2024, Copa2024). Two results:
- **Nominee recall 86% → 93%** (180 → 196 of 210; **2021 now 30/30** — the Euro 2020 squads recovered
  the misses). Remaining gaps are 2019 (no open-data Copa/AFCON) and a handful of non-top-5 names.
- **`tournament_result` is a decisive nomination predictor** (baseline **+0.60**, H⊥ model **+0.47**,
  P>0=1.00) — reaching a major-tournament semifinal with your country materially raises your odds of
  the 30, *after* merit + club success. It was previously un-usable (finisher-only nation → leakage);
  StatsBomb's player→nation for non-finishers dissolved that, so it's a real signal now.
- **The headline holds:** Gate-A H⊥ ≈ **+0.75** (was +0.72) — robust to the bigger pool and the new
  predictor. Stage B (placement) untouched (+0.192). So: get noticed via merit, club runs, *and* a
  national-team run — and, on top of all of it, narrative.

> **Caveat.** Tournament coverage is the open-data majors only (no 2019/2025 major); tournament-only
> pool members (non-top-5-league players) carry NA merit + `position_family="other"` — they're
> candidates for *recall*, not for the attacker-merit story.

### Defensive merit closes the deep-mid blind spot — and the thesis survives it (2026-06-20) — **robustness win**
We gave ball-winning midfielders an individual merit (tackles-won + interceptions + blocks + clearances
per 90, z-scored within season among MFs) and combined it best-role with attacking merit. The blind-spot
cases move exactly as they should:
- **Jorginho 2021: attacking merit −0.01 → best-role 0.57.** His H⊥ is **−1.12** — i.e. he got *less*
  attention than his merit warranted. Not over-hyped; quietly under-rated.
- **Kanté** lands 0.5–1.2 across years (best-role picks defense); **Rodri** is rescued by his deep
  playmaking (attacking 1.41) rather than tackle volume — both end up sensibly high.

**The headline thesis barely moves** once ball-winning merit is a control — so it was *not* an artifact
of measuring only attacking output:
| Gate | before (attacking-only) | after (+ defensive merit) |
|---|---|---|
| Stage A nomination H⊥ | +0.75 | **+0.762** (HDI [0.52, 1.00], P>0=1.00) |
| Stage B placement H⊥  | +0.192 | **+0.187** (HDI [0.038, 0.330], P>0=0.99) |

`def_merit_z` itself is ~0 at placement (0.009) and a small +0.05 in the de-fame fit — defensive merit
explains little *attention* (fame dominates), but it's the right control, and it specifically fixes the
destroyers. Robustness panel re-run: stable across every slice (Stage A +0.78–+0.81; Stage B +0.15–+0.22,
with the known duopoly-sensitivity).

> **Discovery — public defensive stats can't measure center-backs.** Ranking defenders by defensive-action
> volume is *inverted* vs quality: relegation-battling journeymen top the list while Rúben Dias '21 (bottom
> 5%) and Van Dijk '19 (bottom 13%) sink, because elite CBs on dominant teams simply make fewer actions.
> Volume measures *being under siege*, not defending well. Hence MF-only; CBs stay on the team-success route.

### CB + GK merit: blind spots closed (as far as public data allows), thesis still holds (2026-06-20)
Merit is now four-dimensional. The headline defender case is **fixed**: Van Dijk goes from the
**bottom 13% of DFs under volume** to the **top** under efficiency (tackle/aerial success) + ball-playing
(progressive passes); the elite-CB anchors land at a **median ~84th percentile**. Keepers get a clean
metric in **total PSxG+/- (goals prevented vs expected)** — leaderboard tops with **Donnarumma '24,
Oblak '18, Maignan, Courtois '22 (92nd), Alisson '19 (82nd)**.

**Honest limit (a finding in itself):** purely-positional center-backs stay underrated — **Rúben Dias
'21 (44th), Marquinhos '21 (42nd)** — because positioning prevents the very actions the stats count,
and no public metric captures it. Ball-playing fullbacks coded "DF" (Zinchenko) also leak in. So the CB
merit is shipped as a **documented partial**: great for duel-dominant elites, blind to the Dias
archetype.

**New coverage:** defenders & keepers receive an H⊥ for the first time (de-fame fit n 751→1025; Stage B
N 157→191). Examples — **Van Dijk H⊥ +0.54** (modest, now with merit 1.28), **Donnarumma +1.52** (the
Euro-2021-hero narrative, beyond a good-but-not-elite keeper merit), **Dias +1.12** (inflated by the
unmeasured-positioning caveat above).

**Thesis is unmoved by all of it** — adding CB + GK merit as controls barely shifts the headline, so it
was never an attacking-merit artifact:
| Gate | before v2 | after v2 (Bayesian / frequentist) |
|---|---|---|
| Stage A nomination H⊥ | +0.762 | **+0.779** / +0.810 |
| Stage B placement H⊥  | +0.187 | **+0.186** / +0.186 (no-duopoly CI now clears 0: [+0.008, +0.282]) |

### De-leaking merit (match-window) leaves the thesis intact — and sharper (2026-06-21) — **robustness win**
Rebuilt attacking merit from **date-stamped match data**, summed only inside each award year's
performance window, killing the calendar-year look-ahead that had let post-ceremony matches inflate
merit (decisions log). The headline survives the most invasive change yet:
| Gate | before (full-season blend) | after (leakage-safe windows) |
|---|---|---|
| A — nomination H⊥ | +0.779 | **+0.733** (HDI [0.53, 0.95], P>0>0.99) |
| B — placement H⊥  | +0.186 | **+0.147** (HDI [0.02, 0.28], P>0=0.98; no-duo grazes 0) |

- **The payoff is *stronger*.** A/B ratio went ~4× → **~5×**: narrative's pull on getting *noticed* is
  about five times its pull on placement. De-leaking shaved a little off both gates but widened the gap —
  the bias concentrates even more at the shortlist, the gate the public never sees.
- **The leaderboard barely moves** (Yamal/Kvaratskhelia/Pedri/Doué over-hyped; Jorginho/Lewandowski/
  De Bruyne under the radar) — so it was never a leakage artifact. But two **coverage artifacts vanish**:
  João Félix '19 and de Jong '19 had topped "narrative excess" only because the old blend borrowed merit
  from their *next* (covered-league) season; with true windows they drop out entirely. The earlier I4
  worry resolves itself.
- **De Bruyne 2019 was partly a leak.** Old merit_pc1 10.53 (sample's highest, "identical to Messi") was
  inflated by his future 2019-20 (the 20-assist year, mostly post-ceremony). Real windowed 2019:
  merit_pc1 **8.54** (~5th), H⊥ −0.58 — still elite-and-overlooked (14th), but no longer Messi's twin.
  The clean "same production, opposite buzz" pair is now **Lewandowski 2019 (10.29, −0.81) vs Messi 2023
  (10.37, +1.31)**.
- **2021, cleanly:** Lewandowski had the **best** season by merit (rank 1) and almost the **lowest** buzz
  (hype rank 26), yet finished 2nd to Messi (H⊥ +0.61). The textbook "story edged the goals" case — now
  surfaced honestly on the site.
- **Robustness re-run:** Gate A 0.76–0.79 across every spec (jackknife [0.71, 0.86]); Gate B 0.12–0.17,
  duopoly-sensitive, window-leak inflates it +0.143→+0.169 (the leakage guardrail still demonstrates).

### Effect sizes + three more stress tests: the headline survives, now in human terms (2026-06-21)
Publication-hardening additions (all leave the thesis intact):
- **In plain numbers.** At equal merit + team success, a +1-SD Hype Score **≈ doubles** the odds of
  being shortlisted (odds ratio **2.1×**; average marginal effect **~+9 percentage points** — a typical
  candidate goes from ~19% to ~28%), but adds only **~16%** to the odds of placing higher (OR 1.16×).
  On the shared per-SD log-odds scale that's the ~5× gap (directional — Gate A is a yes/no, Gate B a
  share).
- **Generated-regressor bootstrap.** Re-estimating H⊥ on resampled data and refitting both gates
  (so the cost of *measuring* H⊥ is in the interval) keeps Gate A far from zero (95% CI ≈ [+0.58,
  +1.10]) and Gate B positive (≈ [+0.04, +0.33]).
- **Heckman selection control.** Modelling who gets nominated, then correcting placement for it, leaves
  the placement effect the same sign (+0.19) — wide CI crossing zero, so a sign check, not a clean
  correction (no exclusion restriction, small N). The two-gate design remains the real selection answer.
- **Strict window.** Capping the calendar performance window at the ceremony date (no post-ceremony
  match at all) leaves both gates essentially unchanged (A +0.80, B +0.14) — the result isn't riding on
  a few late-December games.

### Club-importance (merit v3) — the thesis survives a team-centrality control (2026-06-24)
**What:** added graded **club-importance** to the H⊥ de-fame regression (option (b) in
`docs/club-importance-v3.md`): per-player **minutes_share** (11 × player minutes / team total minutes,
≈1.0 for an ever-present player) and **xg_share** (player xG / team xG), replacing nothing but
*augmenting* the blunt binary trophy flags (`won_cl`/`won_league`), which are identical for every
squad-mate. H⊥ is now "attention beyond merit **and** how central the player was to his club."
**Data:** no new pull — the cached `understat_player_seasons` already holds **full league squads**
(7124 players, 20–42 per team-season), so team totals are a groupby-sum (the v3 note's "candidate-only"
worry was wrong; see decisions-log). Validated anchors: Rodri 23-24 minutes_share **0.82** but xg_share
**0.05** (the pivot the box score misses); Messi 18-19 xg_share 0.29 / goals_share 0.39; Haaland 23-24
xg_share 0.34.
**Result — the headline barely moves (it survives):**
- **Gate A nomination: +0.733 → +0.696** (HDI [0.49, 0.91], P>0 > 0.99). Drop the control entirely
  and it's +0.78 — so controlling for centrality *lowers* the estimate by a hair, nowhere near
  explaining it away.
- **Gate B placement: +0.147 → +0.145** (HDI [0.005, 0.28], P>0 = 0.97); no-duopoly +0.128 (grazes 0,
  as before). Frequentist anchors agree (A +0.74 with vs +0.78 without; B +0.141 vs +0.144).
- **Ratio ≈ 4.8×** (was ~5×) — "the bias is in who gets *considered*" stands.
**Reading:** the sharpest available attack — "your merit index under-rates holding midfielders, so
'Rodri hype' is an artifact of that blind spot" — is now tested directly and **rejected**: even after
crediting how central a player was to his side, narrative-beyond-merit keeps essentially all its pull
at nomination and its modest pull at placement. Added as the `drop_club_importance` row on the
robustness caterpillar (site + report).

### Second attention proxy lands: the nomination effect replicates on GDELT news (2026-06-24)
**What:** rebuilt H⊥ on a **completely independent** attention signal — GDELT global news volume
(count of news documents naming each player, 2017–2025) instead of Wikipedia pageviews — via the
BigQuery public GKG table. 245k player-days over 114 of the 128 finishers; validated event-driven
(Messi peaks 2022-12-18, the World Cup final). De-famed the same way (`prefix="gd"` → `h_perp_gd`),
**finisher-fit** (GDELT covers only the award universe, not the pool).
**Result — the firm gate replicates, the modest gate stays modest:**
- **Gate A (nomination): +0.45** (95% CI [0.14, 0.76]) — clearly positive, **same sign/direction** as
  the pageviews headline (+0.74). Smaller, as expected on a finisher-only (n≈311) and noisier signal,
  but the *getting-noticed* effect is not an artifact of one data source.
- **Gate B (placement): +0.06** (95% CI [−0.07, 0.19]) — same sign, but no longer distinguishable from
  zero under the noisier finisher-fit proxy. Consistent with placement being the fragile gate.
**Reading:** the headline — narrative gets you **considered** — survives swapping the entire attention
measure for a different corpus. Reported as prose (not on the caterpillar — it's a different signal,
not the same H⊥ re-estimated under a spec choice, same treatment as the bootstrap/Heckman rows).

### FotMob ratings cross-check: merit validated; the CB gap is inherent, not ours (2026-06-24)
**What:** pulled FotMob's holistic player rating (algorithmic, ~300 Opta stats/match, 0–10) as an
**independent** check on the merit index — never folded into `merit_z` (it's a proprietary,
offence-weighted black box; folding it in would contaminate H⊥). 1099 player-seasons, 124/128 players,
2017/18–2025/26, from the player page's server-rendered data (no token wall). Joined to our merit by
`completed_season`; 509 matched finisher-seasons.
**Result:**
- **Overall agreement is strong: Spearman 0.61** (Pearson 0.63). For **attackers, 0.66** — our
  box-score merit tracks an independent 300-stat Opta model closely, a real external validation.
- **For defenders (0.29) and keepers (0.23) the two barely agree**, and FotMob *compresses* defenders
  near its 6-baseline (mean 7.15 vs attackers 7.37; CB anchors bunched — Dias 6.95–7.16, Saliba
  6.77–7.3, Van Dijk 7.16–7.45).
**Reading:** the headline takeaway is that an independent, offence-weighted Opta rating **also** fails
to separate positional centre-backs — so the CB limitation is a property of **public event data**, not
a flaw unique to our index. This upgrades the CB caveat from "our index is a partial" to "no public
single-number metric, ours or Opta's, confidently ranks positional CBs." **No spine change**: merit_z
and the H⊥ de-fame are untouched; a ratings-augmented robustness spec was deliberately skipped (a weak,
compressed defender signal would neither move H⊥ nor be an honest 'merit'). Cross-check only.

### FotMob cross-check, zoomed in: it rescues controlling mids (Rodri, Modrić), not pure CBs (2026-06-24)
A closer read of the FotMob cross-check, prompted by the Rodri/Modrić question. The aggregate
"defenders correlate weakly (0.29)" hides a role split:
- **Rodri 2024** — our production-based merit ranks him ~14th of the field; **FotMob 8.08 ≈ 98th
  percentile** (top of the 2024 finishers). A huge gap.
- **Modrić 2018** — our merit ~20th; **FotMob 7.33 ≈ 66th percentile** (above median; his adjacent
  2018/19 rating is 7.17, so the calendar-year season choice barely moves it).
**Mechanism:** both sit in the *attacking* merit family and are scored on xG-style production, but the
Opta rating rewards **on-ball involvement** (passes, progression, volume) — which deep/holding mids
have in bulk. So the rating *rescues high-involvement midfielders*, the opposite of pure positional
centre-backs (Dias/Saliba), whom it *also* compresses. The earlier blanket "ratings share our blind
spot" was too coarse: it's role-specific.
**Implication (honest, surfaced publicly):** for these two winners specifically, part of their positive
H⊥ ("attention beyond *our* merit") is plausibly **unmeasured on-pitch value, not pure narrative** —
concrete evidence for the role-caveat already in the piece. Does NOT change the model (cross-check
only; `merit_z`/de-fame frozen) or the aggregate result; it sharpens the *interpretation* of the Rodri
2024 and Modrić 2018 cases. Surfaced in the report case studies + role caveat and the site per-year
verdicts.
**Windowing note:** the cross-check joins FotMob *season-average* ratings via `completed_season`, a
coarse proxy for the 3 calendar-year awards (2018/2019/2021 = half-of-two football seasons). Small
distortion (Modrić 7.33 vs 7.17 across the two seasons); not worth a per-match re-window for a
cross-check.

### Audit pass #2 — the headline survives every new stress; ROC-AUC was stale (2026-06-24)
A 9-lens agent-team audit (UX, mobile, SWE, econometrics, applied-stats, journalist, football,
devil's-advocate, reproducibility) returned **no blockers**. The substantive analytical takeaways:
- **Prior-sensitivity (new check).** Re-fitting both gates under a deliberately *tight* N(0,0.5) and a
  *wide* N(0,5) prior on the H⊥ coefficient barely moves it — Gate A stays **[+0.67, +0.70]** (default
  +0.696), Gate B **[+0.14, +0.15]** (default +0.145). The Bayesian headline is the likelihood's, not
  the prior's. (`robustness.prior_sensitivity`.)
- **Generated-regressor bootstrap, surfaced.** The propagated 95% intervals (de-fame re-fit inside each
  resample) are **Gate A [+0.51, +1.07], Gate B [+0.02, +0.34]** — wider than the naive HDIs, both still
  off zero. These were computed but buried; now shown at the headline (site + report).
- **Convergence is clean:** worst R-hat 1.00, 0 divergent transitions, min bulk-ESS ≈ 931.
- **ROC-AUC was stale.** The nomination model's year-grouped CV ROC-AUC is **0.80**, not the 0.845 the
  docs carried (it dropped in the earlier merit-leakage match-window rebuild and the number was never
  refreshed). The report now computes it live (`report.diagnostics`) so it can't go stale again.
- **`drop_low_baseline` was a vacuous robustness spec** — `pv_low_baseline` (baseline NaN or below
  threshold) is False for every row in the candidate/finisher pools (all high-fame players), so it
  filtered 0 rows and duplicated baseline exactly. Removed from the panel/caterpillar rather than shown
  as a check that tests nothing.
- **Football copy errors caught:** "Kolo Muani World Cup *final goal*" (it was the saved final chance;
  his goal was the semi) and a Rodri "treble narrative" (City's treble was 2022-23; his 2024 case was
  the PL title + Euro 2024 Player of the Tournament). Reader-facing, not analytical.

### GDELT goes pool-wide: the nomination effect replicates on independent news data (2026-06-24)
Extended the GDELT second proxy from finisher-only (~128) to the **full candidate pool** (657, the same
universe pageviews use) — the BigQuery scan cost is flat (0.066 TB either way, since it bills bytes
*scanned* not names joined), so the wider pull was free. `gdelt_volume_daily` now covers **590 players**
(was 114); `h_perp_gd` is defined for 913 player-years.
**Result (pool-wide frequentist anchors):**
- **Gate A (nomination): +0.324, 95% CI [+0.10, +0.55], n=910** — clearly positive and significant on a
  wholly independent corpus. The "narrative gets you noticed" effect **replicates pool-wide**.
- **Gate B (placement): +0.051, [−0.08, +0.18], n=167** — same sign, not distinguishable from zero
  (placement is finisher-only by nature; the noisier signal can't resolve the small effect).
**It is attenuated** vs the pageview anchor (+0.742): the GDELT effect is ~44% the size. This is the
expected direction for a noisier instrument — news coverage is sparse and harder to disambiguate for the
hundreds of non-finalist candidates, and classical measurement error attenuates a coefficient toward
zero. **Disambiguation is sound, not broken:** GDELT window-volume correlates with pageview attention at
**Spearman 0.62** overall (0.58 pool-only), and the top pool-only players by GDELT volume are all real,
recognizable footballers (James Rodríguez, Higuaín, Shaqiri, Alexis Sánchez, Zlatan, Iniesta) — no
wrong-person inflation. So the attenuation is a genuine property of the news signal, not an artifact.
**Decision (quality gate, not a cost gate):** keep pageviews as the **primary** proxy and present
pool-wide GDELT as a **strengthened independent replication** — NOT a co-headline. The magnitudes differ
too much (+0.32 vs +0.74) to bill them as interchangeable; promoting a noisier half-size signal to
co-equal primary would overstate agreement. The honest claim is direction + significance on an
independent source, which holds. (The 1 TB free tier was never the constraint — we used 0.066 TB.)

### Tournament overachievement: the nomination effect survives it; Modrić is mostly the run (2026-06-25)
Added a de-fame **robustness control** for *tournament overachievement* — how far a player's nation
finished beyond its pre-tournament seed (curated `expected` in tournament_results.csv from FIFA
ranking/seeding; overachievement = max(0, result − expected); Croatia 2018 = +2, Morocco 2022 = +2,
Algeria 2019 = +2, favourites who won = 0). 158 pool players carry a nonzero value. It is **not** a
baseline regressor — baseline H⊥ / leaderboard / headline are byte-identical (model_features Δ = 0).
**Refitting H⊥ with the control added:**
- **Gate A (nomination): +0.742 → +0.657** [+0.45, +0.87], n=955 — drops ~11% but stays clearly
  positive and significant. The "narrative gets you noticed" effect is **not** just unmodelled surprise
  team success.
- **Gate B (placement): +0.141 → +0.085** [−0.04, +0.21], n=188 — the already-small, already-fragile
  placement effect fades to non-significant. Consistent with the standing "Gate B is real but modest,
  state cautiously" caveat.
- **Modrić 2018 (the vivid case): H⊥ +1.357 → +0.310.** Most of the single highest narrative residual in
  the dataset *was* Croatia's improbable run beyond their seed — attention any unfancied finalist draws —
  not pure voter narrative. Sharpens (doesn't overturn) the Modrić reading: role blind-spot + Opta
  rescue + overachievement together explain the bulk of his gap.
**Caveat:** the expectation is a curated pre-tournament seed (softer than the absolute results), and the
signal is asymmetric (captures positive overachievement among deep-run nations, not favourites who
flopped) — hence a sensitivity check, never the baseline. The headline holds against it where it counts.

### 2026 Hype-Watch — a forward-looking teaser (NOT a study finding) (2026-06-26)
Built a standalone, clearly-labelled "Hype-Watch": a provisional attention-beyond-merit ranking for
2026 ATTACKERS on the completed 2025-26 club season + a pre-World-Cup attention window (ends
2026-06-10). It is **fully isolated from the study** — the modelled 2018-25 payload is byte-identical
to HEAD, headline frozen (+0.696/+0.145); 2026 is NOT in SPINE_YEARS and touches neither gate (no 2026
outcome exists until ~Sept/Oct). De-fame is fit WITHIN the 2026 field on log(baseline) + attacking
merit + a data-derived team-strength proxy (team npxG+xAG — no fabricated trophies); restricted to an
above-median baseline (established following) so a breakout's spike from a near-zero base can't
dominate (the study's low-baseline guard, applied live).
**Snapshot (as of 10 June 2026, pre-WC):** most *over*-attended — **Olise +0.45** (15G 19A breakout
buzz at Bayern), João Pedro +0.29, Saka +0.21, Mbappé +0.21, Yildiz/Ferrán +0.20, Pedri +0.17 (2G but
heavy buzz), Güler +0.15. Most *under*-attended (more output than buzz) — **Harry Kane** (36 goals,
little noise — the "goals, no hype" profile), **Vinícius**, and notably **Lamine Yamal slightly
negative**: his 2024 breakout fame is now fully priced into his baseline, so he's no longer
*over*-attended. The lens working live. **Heavy caveat (surfaced on site):** no winner yet, attackers
only, team success a proxy, and the World Cup — the biggest narrative driver — is excluded and will
rewrite it. A teaser, not a result.
