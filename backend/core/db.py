"""
Supabase gateway — the single place the backend talks to Supabase.

The rest of the app never imports the supabase SDK directly. It calls the
adapters in auth.py / user_store.py / billing.py, and those adapters ask this
module whether Supabase is configured (SUPABASE_ENABLED) and, if so, route
reads/writes here. When the env vars are absent, every adapter falls back to
its original local-file behaviour, so the app still runs in development with
nothing configured.

Environment variables (set these in your host / .env):
    SUPABASE_URL           https://<project>.supabase.co
    SUPABASE_SECRET_KEY    the secret key (sb_secret_...) — server-side only,
                           bypasses RLS. (SUPABASE_SERVICE_KEY /
                           SUPABASE_SERVICE_ROLE_KEY are also accepted.)
    SUPABASE_BUCKET        optional, defaults to "user-datasets"

Design notes:
  * The client is built lazily and cached — importing this module never fails
    just because supabase isn't installed or configured.
  * Session-token lookups happen on nearly every request, so we keep a tiny
    in-process TTL cache to avoid a round-trip per call.
  * DataFrame blobs live in Supabase Storage (private bucket), encrypted before
    upload (see user_store.save_df) — table rows stay small and fast.
"""
from __future__ import annotations

import logging
import os
import threading
import time

log = logging.getLogger("db")

_URL = (os.environ.get("SUPABASE_URL") or "").strip()
_KEY = (
    (os.environ.get("SUPABASE_SECRET_KEY") or "").strip()          # new-style: sb_secret_...
    or (os.environ.get("SUPABASE_SERVICE_KEY") or "").strip()      # legacy names
    or (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
)

SUPABASE_ENABLED = bool(_URL and _KEY)
BUCKET = (os.environ.get("SUPABASE_BUCKET") or "user-datasets").strip()

_client = None
_client_lock = threading.Lock()


def client():
    """Return a cached supabase client, or None when not configured."""
    global _client
    if not SUPABASE_ENABLED:
        return None
    if _client is None:
        with _client_lock:
            if _client is None:
                from supabase import create_client  # imported lazily on purpose
                _client = create_client(_URL, _KEY)
    return _client


# ---------------------------------------------------------------------------
# Table helpers, and why every read here is wrapped
# ---------------------------------------------------------------------------
# A REAL OUTAGE, found in the Render logs on 10 September 2026:
#
#   GET /api/smart/state   -> 500
#   GET /api/product-type  -> 500
#   httpx.ReadError: [Errno 11] Resource temporarily unavailable
#     ... httpcore/_sync/http2.py, line 438, in _read_incoming_data
#
# The home screen of the live app was returning 500. The immediate cause was a
# socket read failing inside httpcore's synchronous HTTP/2 backend under Python
# 3.14 (which is what Render installs by default — see .python-version, now
# pinned). But the reason a socket hiccup could take the whole home screen down
# is this file: `.execute()` was called bare, so any transport error propagated
# straight through the endpoint.
#
# That is the wrong shape. Supabase is a REMOTE service over the public internet.
# It will occasionally be slow, reset a connection, or rate-limit, and none of
# those should be indistinguishable from "the app is broken". Every module that
# reads through here already has a local-file fallback for the case where
# Supabase is not configured at all; a failed read should land in exactly that
# fallback rather than in a stack trace.
#
# So: reads degrade and are recorded. Writes still raise, because a silently
# swallowed write loses the seller's data, which is worse than an error — but
# they raise a typed error, and they are recorded too.
class TransportProblem(RuntimeError):
    """Supabase could not be reached or answered badly. Not the caller's fault."""


# Which tables have failed recently, for the health endpoint and so the log is
# not one line per row. Reset when a read succeeds again.
_DEGRADED: dict[str, str] = {}
_LOGGED: set[str] = set()


def degraded() -> dict[str, str]:
    """Tables that are currently failing, and how."""
    return dict(_DEGRADED)


def _note_ok(table_name: str) -> None:
    _DEGRADED.pop(table_name, None)
    _LOGGED.discard(table_name)


def _note_fail(table_name: str, exc: BaseException, op: str) -> None:
    _DEGRADED[table_name] = f"{type(exc).__name__}: {exc}"[:200]
    if table_name not in _LOGGED:
        _LOGGED.add(table_name)
        log.warning("Supabase %s on %r failed (%s: %s). Falling back to local "
                    "storage for this call; further failures on this table are "
                    "not logged until one succeeds.",
                    op, table_name, type(exc).__name__, exc)
    try:
        from backend.core import errors
        errors.record(exc, where=f"supabase {op} {table_name}")
    except Exception:  # noqa: BLE001
        pass


def _reset_client() -> None:
    """Drop the cached client so the retry builds a fresh connection pool.

    The observed failure is a dead or half-open pooled connection, so retrying on
    the same pool retries the same broken socket.
    """
    global _client
    with _client_lock:
        _client = None


def _read(table_name: str, build, empty, op: str = "read"):
    """Run a read, once, then once more on a fresh connection, then degrade."""
    c = client()
    if not c:
        return empty
    for attempt in (1, 2):
        try:
            out = build(c).execute()
            _note_ok(table_name)
            return out
        except Exception as exc:  # noqa: BLE001 — a remote service, not a bug here
            if attempt == 1:
                _reset_client()
                c = client()
                if not c:
                    _note_fail(table_name, exc, op)
                    return empty
                continue
            _note_fail(table_name, exc, op)
            return empty
    return empty


def fetch_one(table_name: str, match: dict) -> dict | None:
    def build(c):
        q = c.table(table_name).select("*")
        for k, v in match.items():
            q = q.eq(k, v)
        return q.limit(1)

    res = _read(table_name, build, None)
    data = (getattr(res, "data", None) or []) if res is not None else []
    return data[0] if data else None


def fetch_all(table_name: str, match: dict | None = None) -> list[dict]:
    def build(c):
        q = c.table(table_name).select("*")
        for k, v in (match or {}).items():
            q = q.eq(k, v)
        return q

    res = _read(table_name, build, None)
    return (getattr(res, "data", None) or []) if res is not None else []


def _write(table_name: str, build, op: str):
    """Writes retry once and then RAISE. A lost write is worse than an error."""
    c = client()
    if not c:
        return None
    for attempt in (1, 2):
        try:
            out = build(c).execute()
            _note_ok(table_name)
            return out
        except Exception as exc:  # noqa: BLE001
            if attempt == 1:
                _reset_client()
                c = client()
                if not c:
                    _note_fail(table_name, exc, op)
                    raise TransportProblem(
                        f"Could not save to {table_name}: {exc}") from exc
                continue
            _note_fail(table_name, exc, op)
            raise TransportProblem(
                f"Could not save to {table_name}: {exc}") from exc
    return None


def upsert(table_name: str, row: dict, on_conflict: str | None = None):
    def build(c):
        q = c.table(table_name)
        return q.upsert(row, on_conflict=on_conflict) if on_conflict else q.upsert(row)

    return _write(table_name, build, "upsert")


def insert(table_name: str, row: dict):
    return _write(table_name, lambda c: c.table(table_name).insert(row), "insert")


def update(table_name: str, match: dict, patch: dict):
    """UPDATE ... SET patch WHERE match. Returns the PostgREST response."""
    def build(c):
        q = c.table(table_name).update(patch)
        for k, v in match.items():
            q = q.eq(k, v)
        return q

    return _write(table_name, build, "update")


def delete(table_name: str, match: dict):
    def build(c):
        q = c.table(table_name).delete()
        for k, v in match.items():
            q = q.eq(k, v)
        return q

    return _write(table_name, build, "delete")


# ---------------------------------------------------------
# Storage helpers (private bucket for encrypted DataFrame blobs)
# ---------------------------------------------------------
def upload_blob(path: str, data: bytes, content_type: str = "application/octet-stream") -> bool:
    c = client()
    if not c:
        return False
    store = c.storage.from_(BUCKET)
    opts = {"content-type": content_type, "upsert": "true"}
    try:
        store.upload(path=path, file=data, file_options=opts)
        return True
    except Exception:
        # Older/newer SDKs: fall back to update (object already exists) then upload.
        try:
            store.update(path=path, file=data, file_options=opts)
            return True
        except Exception:
            store.upload(path, data, opts)
            return True


def download_blob(path: str) -> bytes | None:
    c = client()
    if not c:
        return None
    try:
        return c.storage.from_(BUCKET).download(path)
    except Exception:
        return None


def remove_blob(path: str) -> None:
    c = client()
    if not c:
        return
    try:
        c.storage.from_(BUCKET).remove([path])
    except Exception:
        pass


# ---------------------------------------------------------
# Session-token cache (token_hash -> email), short TTL
# ---------------------------------------------------------
_sess_cache: dict[str, tuple[str, float]] = {}
_sess_lock = threading.Lock()
_SESS_TTL = 300.0  # seconds


def cache_session(token_hash: str, email: str) -> None:
    with _sess_lock:
        _sess_cache[token_hash] = (email, time.time() + _SESS_TTL)


def cached_session(token_hash: str) -> str | None:
    with _sess_lock:
        rec = _sess_cache.get(token_hash)
        if not rec:
            return None
        email, exp = rec
        if time.time() > exp:
            _sess_cache.pop(token_hash, None)
            return None
        return email


def drop_cached_session(token_hash: str) -> None:
    with _sess_lock:
        _sess_cache.pop(token_hash, None)
