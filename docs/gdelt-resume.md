# GDELT pull — paused, how/when to resume

> **SUPERSEDED (2026-06-24): use BigQuery, not this DOC-API pull.** The DOC 2.0 API IP-ban never
> cleared, so the second proxy now comes from the **BigQuery public GKG table** (`data/gdelt_bq.py`,
> `python run.py gdelt_bq`) — free in a no-billing sandbox project, ~0.066 TB scan. It writes the same
> `gdelt_volume_daily` cache. The notes below are kept only as the record of the DOC-API dead end.
>
> **POOL-WIDE DONE (2026-06-24).** The BigQuery pull now resolves over `pool.pool_universe()` (657),
> not just the ~128 finishers — `gdelt_volume_daily` covers **590 players**. Scan cost stayed flat
> (0.066 TB; BigQuery bills bytes scanned, not names joined). `h_perp_gd` is therefore a pool-wide
> independent replication; the nomination effect reproduces (Gate A +0.32, attenuated vs pageviews
> +0.74 — a noisier signal), kept as a strengthened replication, not a co-headline. See findings +
> decisions logs. Nothing left to resume.

**Paused at: 2026-06-19 16:38, resumed 2026-06-20 ~21:25 (got to 48), hard-banned again.**

## State
- **48 / 128** players collected (43 → 48 on the 2026-06-20 resume before the IP hard-banned).
  Per-player shards are cached in `data/cache/gdelt_by_player/` (each = the full daily timeline
  2017-01-01 → 2025-12-31, ~3266 points).
- `data/cache/gdelt_volume_daily.parquet` (the assembled all-player frame) is **NOT** written yet —
  it only assembles once all players are collected.
- Nothing is lost: the pull is resumable per player.

## Why it paused
GDELT's DOC 2.0 API bans bursty IPs, and the ban **escalates** with repeated hits. The 2026-06-20
resume cleared 5 players then the IP went into a **hard ban**: GDELT started returning HTTP **200 with
an empty/HTML body** (a *soft* ban, not a 429). Originally `resp.json()` crashed on that
(`JSONDecodeError`) and killed the whole run. **Fixed 2026-06-20** — `_request` now treats a non-JSON
body as a throttle (back off → retry → eventually the `RuntimeError` the cooldown loop catches), so a
soft ban now cools down and resumes instead of crashing. But the IP itself is still escalated; the
code, disambiguation, and data quality remain verified good (Messi WC-final spike; ~100% precision on
"Son"). This is purely a rate-limit / throughput problem.

## How to resume
```
python run.py gdelt
```
Reads the 48 cached shards, skips them, continues from player 49. The self-cooldown loop is already
baked into `gdelt.pull` (`_COOLDOWN` / `_COOLDOWN_CYCLES` in `src/bdor/data/gdelt.py`), and now
survives soft-ban (empty-body) responses without crashing.

## When to resume (pick a rested-IP time)
- The IP was **hard-banned again at 2026-06-20 ~21:25** after a brief resume — it's escalated, not
  rested. **Do NOT retry tonight.**
- **Best: a different network/IP**, or a long rest (overnight+, ideally 12–24h since the last hit).
  A genuinely rested IP should clear the remaining ~80 players in ~10 minutes (6s pacing, no ban).
- **Do NOT retry within ~2 hours of the last hit** — immediate retries reset the escalation clock and
  deepen the ban (we just saw this: hammering it cleared only 5 players then hard-banned).

## On resume — don't babysit
Kick it off and walk away. Do **not** run parallel GDELT queries alongside it — concurrent /
bursty requests are exactly what escalated the ban. One steady process at a time.

## If it still won't finish
The IP may be escalated to a multi-hour/day ban. Either wait longer, resume from a different
network, or ship v1 on pageviews-only (the validated primary hype proxy) and treat GDELT as
best-effort enrichment — it's the secondary signal, so partial/late coverage is acceptable.
