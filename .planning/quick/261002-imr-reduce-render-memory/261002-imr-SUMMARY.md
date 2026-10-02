---
quick_id: 261002-imr
slug: reduce-render-memory
status: complete
date: 2026-10-02
commit: da2a610
---

# Summary: reduce server memory on sales upload "Confirm & save"

## What changed

- `backend/main.py`: browser sessions expire after `SESSION_IDLE_MINUTES`
  (default 60, swept at most once a minute) and are dropped on `/api/logout`.
  `/api/smart/map` releases the raw upload once saved, no longer re-downloads
  the saved file, no longer builds the unused `insights`, and frees memory at
  the end. `/api/smart/upload` drops the raw bytes after parsing and frees
  memory before replying.
- `backend/core/memory.py` (new): `release()` = `gc.collect()` + glibc
  `malloc_trim(0)` on Linux (no-op trim elsewhere).
- `backend/core/user_store.py`: `remember_df()` seeds the dataset cache with a
  just-saved frame; save/load drop the plaintext/ciphertext buffers early.
- `backend/core/smart.py`: `save_sales/save_review/save_supply_sales` take
  `keep_in_memory=False`; only Confirm & save opts in (other callers pass a
  live session frame they keep using).
- `scripts/test_upload_memory.py` (new): 22 checks; fails on the old code.

## Evidence

| 145k-row CSV, Supabase path simulated | before | after |
|---|---|---|
| Confirm & save peak memory | +109MB | +57MB |
| Confirm & save time (local) | 3.4s | 0.9s |

Test suites: test_upload_memory 22/0, test_upload_resilience 35/0,
test_supabase_mode 24/0, test_analytics_backend 10/0, test_replenish 118/0,
test_auth_hardening 70/0, test_onboarding 116/0, test_instant_approve 65/0,
test_launch_readiness 72/0. test_perf_resilience 102/2: the same two
frontend checks fail on the code before this change too.

## Not done / follow-ups

- Not pushed. Render auto-deploys `main` on commit, so pushing ships it.
- The single biggest remaining spike is the Excel upload itself (openpyxl:
  ~+150MB at 150k rows). Asking sellers to use CSV for big files avoids it.
- `MALLOC_ARENA_MAX=2` on Render would cut fragmentation further (env var,
  needs the user's go-ahead because it changes production config).
