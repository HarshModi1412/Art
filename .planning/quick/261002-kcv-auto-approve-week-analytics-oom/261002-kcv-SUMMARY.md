---
quick_id: 261002-kcv
slug: auto-approve-week-analytics-oom
status: complete
date: 2026-10-02
commit: 20e3b34 (user's commit of the main work), a40ddb9, afca886
---

# Summary: auto-approve the planned week; Sales Analytics OOM

## What changed

- `20e3b34` (committed and deployed by the user, live 09:16Z):
  - OOM: single-flight dataset loads + `copy=False` reads (user_store);
    supply demand stats cached per data stamp and narrowed to 3 columns;
    `calculate_rfm` reads 4 columns, vectorised (identical output); the home
    screen no longer copies the sales table into the session (loaded on use,
    keyed on cache.stamp); `memory.one_at_a_time` gate on the 10 dataset
    endpoints.
  - Auto-approve: planned weeks approve themselves through
    `main._approve_post_ready` in a background worker, one post at a time;
    hidden from the panel meanwhile; failures flagged and shown as cards;
    `auto_plan_approve` setting (default on).
- `a40ddb9` fix(state): background jobs run in `user_store.job_scope()` so
  their writes merge; same-record changes merge field by field; a key absent
  at read time merges as empty; Windows read/replace retries.
- `afca886` fix(tasks): derived task id, so a racing duplicate collapses.

## Evidence

- Repro (300k rows, cold process, simulated Supabase): first three requests
  together +437MB -> +150MB; one at a time +232MB -> +151MB; 12.7s -> 7.6s.
- Production after 20e3b34: peak 333MB (09:21Z), settled ~285MB, no OOM.
- Tests: test_dataset_memory 22/0; test_autoplan_auto_approve 25/0 (8 runs
  in a row); test_concurrent_approve 15/0. Full suite vs 20e3b34: no new
  failures; pre-existing unchanged (ai_labelling 1, perf_resilience 2,
  publisher 2, festival_content, social_manager, autoplan run-now + crash,
  craft_and_a11y 3, hig, mobile_css, watermark 3, website_builder).

## Found and fixed along the way

- 20e3b34 alone had two defects (now fixed, not yet deployed): a slow
  background job could put approved posts back to draft, and a reel could
  get two "make the reel" tasks.
