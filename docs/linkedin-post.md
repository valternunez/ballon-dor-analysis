# LinkedIn launch post — Ballon d'Or analysis

Balanced angle (finding-led, with a craft note). Plain text — LinkedIn does **not** render markdown,
so there are no `*asterisks*`; emphasis is via CAPS / line breaks. Paste as-is.

---

## THE POST (copy everything between the lines)

```
Every year we accuse the Ballon d'Or of rewarding the story, not the season.

So I built a model to test it — and the bias isn't where everyone thinks.

The question
Not "hype vs merit" — they're hopelessly tangled (players get talked about because they're good). The sharper, fairer question: does attention still predict the award AFTER you control for what a player actually did and how their team performed?

How it works
Merit, graded per position from match-level data: goals and chance-creation for attackers, tackles and interceptions for midfielders, goals prevented for keepers, duels and ball-progression for defenders.
Then a "Hype Score": how much the world actually watched a player (Wikipedia views, every language) minus what their performance, fame and team success predict. The gap is attention they didn't earn on the pitch.

The finding
The award is really two decisions: making the 30-player shortlist, then placing in the vote.

Narrative's pull on getting NOTICED is about five times its pull on who actually WINS. One extra standard deviation of buzz roughly doubles your odds of being shortlisted — but barely moves the final ranking.

So the bias isn't in who wins. It's in who gets considered.

(Lewandowski's 2019 and 2021 were among the best seasons in the whole dataset — and almost nobody was talking about them.)

The honest caveats are in there too: 7 award years is a small sample, and it leans on one attention proxy. Fully open-source — Python, Bayesian models, leakage-safe windows, and an interactive site where you can explore every player and year.

Curious what football people and data people make of it.

#DataScience #Football #Statistics #BallonDor
```

**Image to attach:** `site/og-image.jpg` (the 1200×630 "Goals, or stories?" card).
Alternative visual if you'd rather lead with a chart: a screenshot of the scatter ("the matrix") or
the two-gate bars.

---

## FIRST COMMENT (post immediately after publishing — keeps the link out of the body)

```
Interactive piece (best on desktop, works fine on mobile):
https://valternunez.github.io/ballon-dor-analysis/

Full technical write-up + methods:
https://valternunez.github.io/ballon-dor-analysis/report/ballon-dor.html

Code (MIT):
https://github.com/valternunez/ballon-dor-analysis
```

---

## WHEN TO POST

- **Day:** Tuesday, Wednesday or Thursday (Wed is strongest). Avoid Fri–Mon.
- **Time:** ~**15:00 UTC** (≈16:00–17:00 CET / 10:00–11:00 US-Eastern) — the window where the EU
  afternoon and the US morning overlap, best for a mixed/global audience.
- **2026 note:** late-afternoon engagement has risen; a Wed ~16:00 local slot also performs well if
  your audience is concentrated in one region.

## THE FIRST HOUR DECIDES REACH — playbook

1. Post when you have **60 minutes free** right after. The first hour's engagement sets distribution.
2. Add the **first comment with the links** within ~1 minute of posting.
3. **Reply to every comment** quickly — replies count as engagement and boost reach. Ask a question
   back to keep threads going.
4. Don't edit the post for the first ~30 min (editing can dampen reach).
5. Nudge 3–5 people likely to engage early (DM/share) — early velocity compounds.

## RULES OF THUMB BAKED IN

- Hook is the first 2 lines (what shows before "…see more") — it's a question + a tease.
- Length ~1,700 chars (sweet spot is 1,300–1,900) with whitespace; LinkedIn rewards dwell time.
- **Link in the first comment, not the body** — body links cut reach ~60%; even comment links are
  slightly throttled now, so the post is written to stand on its own.
- **4 hashtags** (3–5 is optimal; >5 is penalised).

## IF IT UNDER-PERFORMS

The highest-ceiling format on LinkedIn is a **PDF/document carousel** (~6.6% avg engagement vs ~2%
for text). If this text post lands flat after a few days, I can turn the finding into a 6–7 slide
carousel (hook → the two gates → the scatter → a couple of cases → "explore it") and you re-post.

## ALTERNATE HOOKS (swap line 1–2 if you want a different flavour)

- Contrarian: "The Ballon d'Or 'narrative bias' is real — but it's not rigging who wins. It's rigging
  who even gets considered. Here's the data."
- Builder: "I spent way too long turning a football pub argument into a Bayesian model. Verdict: the
  hype doesn't win you the award — it gets you in the room."
