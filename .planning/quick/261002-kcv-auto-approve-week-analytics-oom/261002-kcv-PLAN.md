---
quick_id: 261002-kcv
slug: auto-approve-week-analytics-oom
date: 2026-10-02
mode: quick
---

# Auto-approve the planned week; Sales Analytics OOM

## Requests (from the user)

1. "Don't ask for week schedule approve, just do it."
2. "Sales analytics also ran out of memory."

## Evidence for 2

- Render `server_failed` oomKilled 512Mi at 2026-10-02 08:46:54Z, ~2 min after
  the deploy of ed6de43 (includes da2a610..56a2af5).
- Logs: `/api/smart/state` started 08:45:16 and never completed; `/api/today`
  completed 08:46:06; `/api/analytics` was opened in that window. After the
  restart the same two requests answered in under a second.
- Memory: old instance sat at ~400MB after the big upload; new instance went to
  375MB in its first minute, then was killed; settled at 255MB after.
- Local repro (scratchpad memprof2.py, 300k rows, cold process, simulated
  Supabase): smart/state + today + analytics together +437MB; one at a time
  +232MB. Breakdown of smart/state: supply.compute_inventory +109MB run 4x per
  page (reorder + overstock cards, insights built twice: state + history);
  hydrate_session +118MB (full copy into the session on every home load);
  calculate_rfm copies the whole frame; cold loads stampede (each request
  downloads + unpickles its own copy).

## Tasks

1. user_store.load_df: single-flight per (email, key); `copy=False` read path.
2. supply._demand_stats: memoised per data stamp + product aliases; copies
   three columns, not the frame; names normalised once per distinct value.
3. analytics.calculate_rfm: select 4 columns, vectorised (identical output).
4. smart.hydrate_session: drop a stale session copy instead of reloading;
   main._require_txns loads on demand, keyed on cache.stamp.
5. memory.one_at_a_time gate on the dataset endpoints (state, today, history,
   analytics, subcategory, detail, rfm, winback, report pdf, smart/map).
6. autoplan auto-approve: after a plan (and on kick, for weeks left waiting)
   a background worker approves each autoplan draft through
   main._approve_post_ready, one at a time; those drafts are hidden from the
   panel; a failure is flagged and becomes a card. Setting
   `auto_plan_approve` (default on), `auto_approve` on the settings endpoint.
