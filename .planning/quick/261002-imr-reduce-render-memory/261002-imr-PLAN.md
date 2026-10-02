---
quick_id: 261002-imr
slug: reduce-render-memory
date: 2026-10-02
mode: quick
---

# Reduce server memory on sales upload "Confirm & save"

## Problem (evidence)

- Render `Smart_Helper` (512MB starter) was OOM-killed at 2026-10-02 07:42:44Z
  (`server_failed`, `oomKilled.memoryLimit=512Mi`).
- Logs: `POST /api/smart/upload?kind=sales 200` at 07:41:37, then nothing until
  the restart, so the kill happened inside `POST /api/smart/map` (Confirm & save).
  The browser showed its 502/503 text: "The server did not answer...".
- Idle memory on the live instance sits at 260-300MB of 512MB.
- Local profile (scratchpad memprof.py, 145k-row / 15.8MB CSV, Supabase path
  simulated): Confirm & save adds +109MB on top of the ~36MB pending upload.
  Steps: build_transactions +32, save_sales +47, replenish.after_sales +72,
  build_insights +63 (all stacked on the still-held raw upload).

## Root causes

1. `_data_sessions` in backend/main.py never evicts. Every browser session
   (each device, each logout -> login, since the client mints a new id) keeps
   its own `txns_df` copy of the sales table and any `raw_dfs` until restart.
   This is what pushes the idle baseline toward the limit.
2. `/api/smart/map` keeps the raw pending upload alive for the whole request,
   re-downloads + decrypts + unpickles the file it just saved (`load_sales`
   after `save_sales`), and builds `insights` that the only caller
   (smart.js `mapConfirm`) never reads; the home screen rebuilds them on the
   next `/api/smart/state` anyway.
3. Supabase save/load keep both the pickle bytes and the encrypted bytes alive
   through the network call.

## Tasks

1. Session store: track last use; sweep sessions idle > `SESSION_IDLE_MINUTES`
   (default 60) at most once a minute from `get_session`; drop the session on
   `/api/logout`. Safe: `_require_txns` re-hydrates from the account.
2. `/api/smart/map`: pop the pending upload from the session as soon as the
   transactions are built; `save_*` return the saved frame and prime the
   dataset cache so nothing is re-downloaded; stop computing `insights`
   in the response; free memory (gc + glibc `malloc_trim`) after the request.
   Also free after `/api/smart/upload`.
3. `user_store.save_df/load_df`: drop the plaintext/ciphertext buffer as soon
   as the next stage has it.

## Verify

- memprof.py before/after numbers on the same 145k-row file.
- Existing test suites still pass; upload -> map round trip returns 200 with
  the same `rows/added/mode` fields; legacy analytics endpoints still see data.
