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

import os
import threading
import time

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


# ---------------------------------------------------------
# Table helpers (thin wrappers over PostgREST)
# ---------------------------------------------------------
def fetch_one(table_name: str, match: dict) -> dict | None:
    c = client()
    if not c:
        return None
    q = c.table(table_name).select("*")
    for k, v in match.items():
        q = q.eq(k, v)
    data = (q.limit(1).execute().data) or []
    return data[0] if data else None


def fetch_all(table_name: str, match: dict | None = None) -> list[dict]:
    c = client()
    if not c:
        return []
    q = c.table(table_name).select("*")
    for k, v in (match or {}).items():
        q = q.eq(k, v)
    return (q.execute().data) or []


def upsert(table_name: str, row: dict, on_conflict: str | None = None):
    c = client()
    if not c:
        return None
    q = c.table(table_name)
    if on_conflict:
        return q.upsert(row, on_conflict=on_conflict).execute()
    return q.upsert(row).execute()


def insert(table_name: str, row: dict):
    c = client()
    if not c:
        return None
    return c.table(table_name).insert(row).execute()


def update(table_name: str, match: dict, patch: dict):
    """UPDATE ... SET patch WHERE match. Returns the PostgREST response."""
    c = client()
    if not c:
        return None
    q = c.table(table_name).update(patch)
    for k, v in match.items():
        q = q.eq(k, v)
    return q.execute()


def delete(table_name: str, match: dict):
    c = client()
    if not c:
        return None
    q = c.table(table_name).delete()
    for k, v in match.items():
        q = q.eq(k, v)
    return q.execute()


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
