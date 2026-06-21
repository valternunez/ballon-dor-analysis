# Design note — "club-importance" (merit v3), the next batch

**Status:** scoped, not started. Written 2026-06-20. Prompted by the Rodri 2024 question: *do we
capture how important a player was to their club?* Answer today: **no.** This note records the gap,
the candidate signals, the data access reality, and the one decision to settle before coding.

## The gap

Two things the model sees about a player's club, neither of which is *importance*:

1. **Merit** — only the player's *own* numbers, z-scored within (position, season). For Rodri that's
   ball-winning volume (tackles + interceptions + blocks + clearances per 90). It does not know he was
   City's metronome or that the team's level dropped without him.
2. **Team success** (`features/team_success.py` → `features/hperp.py` regressors) — only **binary /
   ordinal trophies**: `won_cl`, `won_league`, `cl_round` (0–5). City won the treble, so Rodri carries
   "won CL + won league" — **but so does every City player with enough minutes.** The signal is
   identical across teammates.

Minutes (`MIN_MINUTES = 1500`, `merit.py`) are an **eligibility floor only**, never a signal of
indispensability. So "how central was this player to that team" is unmodeled. This is the most
interesting open direction for merit, and it's exactly where a deep-lying pivot like Rodri is
under-credited by a box score.

## Candidate signals (in rough order of value-vs-cost)

### 1. Share of team output — *the principled one, needs new data*
Player goals ÷ team goals; xG share; shot / chance-creation share. Captures "carried the attack."
- **Blocker:** needs **team totals**, which are **not cached**. The Understat pull
  (`data/understat.py`) grabs only Ballon-d'Or-relevant *players*, not full squads, so team totals
  can't be reconstructed by summing what we have.
- **Fix:** a new **Understat team-level pull** (Understat exposes team season pages with team xG /
  goals / shots). Cache-first like every other pull. Coverage needed: 2017/18–2024/25, top-5 leagues.
- **Caveat:** an attack-share metric naturally helps forwards/attacking mids; it does little for a
  defensive pivot or a CB. So it's *part* of importance, not all of it — pair it with (2).

### 2. Minutes share — *cheap, partial*
Player minutes ÷ team available minutes across the season — a durability / "always on the pitch"
proxy for indispensability. Closer to what makes Rodri Rodri than attack-share is. Still wants team
context (games played, available minutes) but is lighter than full team totals.

### 3. Season-average match rating (SofaScore / WhoScored / FotMob) — *captures the intuition, but black-box + gated*
A composite per-match rating rewards duels, interceptions, progression and sheer involvement, so a
pivot rates highly with zero goals. A **season-average rating** natively encodes the "Rodri was
consistently top-rated when he won it" observation our box score misses.
- **Use as a cross-check / supplementary signal, NOT the merit spine.** The whole project asks whether
  hype beats *transparent, decomposable* merit; importing an opaque composite (which may itself bake in
  some reputation) into the spine would muddy that. As an independent agreement check it's excellent;
  as the backbone it's self-defeating.
- **Access is the bottleneck** (see `docs/decisions-log.md`): SofaScore sits behind Cloudflare;
  WhoScored hangs; FotMob has an API but **historical** season ratings (2017–2025) are the gated part.
  Current-season ratings are easy; the back-catalogue is the real risk. Treat coverage as best-effort.

## The one decision to settle before coding

Where does a share/importance signal enter?

- **(a) As a new merit dimension** — `merit_z = max(..., importance_z)`. Pro: directly raises
  under-credited pivots in the leaderboard. Con: "importance" isn't quite "performance quality" —
  conceptually it's a different axis, and stacking it into the best-role max could over-reward a
  high-volume player on a great team.
- **(b) As a richer team-success regressor in the Hype Score model** — replace/augment the binary
  `won_cl`/`won_league` flags with a graded "how much of this team was this player." Pro: cleaner
  separation (merit = individual quality; team block = team context); makes the Hype Score's "team
  success" control far less blunt. Con: doesn't change the merit leaderboard, only the de-faming.

**Leaning (b)** — it fixes the bluntest part of the current model (every teammate identical) without
blurring the merit/quality axis, and it's the more defensible framing for the thesis. But leave it
open; decide with the data in hand.

## Scope guardrails for the batch

- New **Understat team-totals pull** (cache-first) → derive `goal_share`, `xg_share`, `shot_share`,
  `minutes_share`. Validate on obvious cases (Messi/Ronaldo near-1.0 attack share; Rodri high minutes
  share, modest attack share).
- Match ratings only if FotMob historical access proves workable — otherwise defer to a follow-up and
  ship shares + minutes-share alone. Don't let the gated source block the batch.
- Re-fit merit and/or Hype Score per the (a)/(b) decision; re-run the robustness panel; confirm the
  headline two-gate result is unmoved (the thesis must survive, not depend on, this enrichment).
- Living logs as usual: dated `decisions-log.md` + a `findings.md` entry if importance changes any
  leaderboard or the Rodri case specifically.
