"""
Per-account persistent storage.

Two things need to survive across logins (not just a browser session):
  * Position Strategy  — the owner's current/target position + checklist.
  * Smart CafeX        — the Sales/Review files they uploaded, their task list,
                         approved/dismissed insights, etc.

Both are keyed to the logged-in email, so the same account picks up where it
left off on any device.

Storage backend is pluggable (see backend/core/db.py):
  * Supabase configured -> JSON state lives in the `user_state` table (jsonb);
    the uploaded DataFrames live in a private Storage bucket, Fernet-encrypted
    before upload (defence in depth on top of Supabase's own at-rest AES).
  * Otherwise -> the original local layout under the data dir:
        user_data/<sha256(email)>/state.json
        user_data/<sha256(email)>/df_<key>.pkl

Public function signatures are unchanged.
"""
import contextlib
import contextvars
import copy
import hashlib
import json
import math
import os
import pickle
import tempfile
import threading
import warnings

import pandas as pd

from backend.core import auth, db

_DATASET_KEYS = "_dataset_keys"   # list of df keys present, tracked inside state


def _resolve_root() -> str:
    """Pick a writable root for per-account local data (local/fallback mode)."""
    candidate = os.path.join(auth.BASE_DIR, "user_data")
    try:
        os.makedirs(candidate, exist_ok=True)
        probe = os.path.join(candidate, ".write_test")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        return candidate
    except OSError as e:
        fallback = os.path.join(tempfile.gettempdir(), "cafex_user_data")
        os.makedirs(fallback, exist_ok=True)
        warnings.warn(
            f"CAFEX_DATA_DIR ({auth.BASE_DIR!r}) is not writable ({e}); "
            f"falling back to {fallback!r}. Saved data will NOT survive a "
            f"restart until this is fixed (attach a persistent disk or "
            f"point CAFEX_DATA_DIR at a writable path)."
        )
        return fallback


_ROOT = _resolve_root()


def root() -> str:
    """The writable data directory actually in use (a mounted disk when one is
    attached, otherwise the temp fallback). Anything that must survive a
    restart belongs under here, never inside the checked-out repository."""
    return _ROOT
_lock = threading.Lock()


def _safe(email: str) -> str:
    return hashlib.sha256((email or "").strip().lower().encode()).hexdigest()[:32]


def _user_dir(email: str) -> str:
    d = os.path.join(_ROOT, _safe(email))
    os.makedirs(d, exist_ok=True)
    return d


def _state_path(email: str) -> str:
    return os.path.join(_user_dir(email), "state.json")


# ---------------------------------------------------------
# JSON state
# ---------------------------------------------------------
# Every load_state() in Supabase mode is a full HTTPS round trip to PostgREST.
# Nothing about that is obvious from the call sites: reading one flag looks
# free, so the modules read one flag at a time and a single home screen ended
# up making ~48 of them. At 50-200ms each that is the whole of the "the page
# never loads" complaint, and any one of them timing out took the whole
# response down with it.
#
# So we memoise per REQUEST rather than for a duration. A request only ever
# reads one account, and it can only see writes it made itself, so the first
# read pays the round trip and the rest are free. The cache dies with the
# request, which means no TTL to tune and no window in which a second request
# - or a second Render instance - can serve a stale value.
_scope: contextvars.ContextVar = contextvars.ContextVar("user_state_scope", default=None)


@contextlib.contextmanager
def request_scope():
    """Open a memoisation window. main.py wraps every HTTP request in one."""
    token = _scope.set({})
    try:
        yield
    finally:
        _scope.reset(token)


def _norm_email(email: str) -> str:
    return (email or "").strip().lower()


def _scope_get(email: str):
    box = _scope.get()
    if box is None:                      # outside a request (CLI, tests, jobs)
        return None
    hit = box.get(_norm_email(email))
    # Copy on the way out. update_state() and a good deal of module code mutate
    # the dict they are handed; sharing one object would let a half-finished
    # edit leak into the next reader inside the same request.
    return copy.deepcopy(hit) if hit is not None else None


def _scope_put(email: str, state: dict) -> None:
    box = _scope.get()
    if box is not None:
        box[_norm_email(email)] = copy.deepcopy(state)


def load_state(email: str) -> dict:
    cached = _scope_get(email)
    if cached is not None:
        return cached
    state = _read_state(email)
    _scope_put(email, state)
    return state


def _read_state(email: str) -> dict:
    if db.SUPABASE_ENABLED:
        row = db.fetch_one("user_state", {"email": (email or "").strip().lower()})
        if not row:
            return {}
        state = row.get("state")
        return state if isinstance(state, dict) else {}
    path = _state_path(email)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _jsonb_safe(v):
    """Postgres JSONB refuses NaN and ±Infinity, and ONE of them anywhere in an
    account's state makes the whole save fail — every write for that account,
    whatever it was saving. They are how pandas says "no value", so they get
    in easily (an average over no rows, a ratio over zero). Stored as null,
    which is what they meant. numpy numbers become plain ones on the way."""
    if isinstance(v, float):               # numpy float64 is a float too
        return float(v) if math.isfinite(v) else None
    if isinstance(v, dict):
        return {k: _jsonb_safe(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonb_safe(x) for x in v]
    if v is None or isinstance(v, (str, bool, int)):
        return v
    try:                                   # numpy scalars and friends
        import numpy as _np
        if isinstance(v, _np.generic):
            return _jsonb_safe(v.item())
    except Exception:  # noqa: BLE001
        pass
    return v


def save_state(email: str, state: dict) -> None:
    if db.SUPABASE_ENABLED:
        state = _jsonb_safe(state)
        db.upsert("user_state", {"email": _norm_email(email), "state": state},
                  on_conflict="email")
        _scope_put(email, state)
        return
    path = _state_path(email)
    with _lock:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    _scope_put(email, state)


def update_state(email: str, patch: dict) -> dict:
    """Shallow-merge `patch` into the stored state and persist. Returns the
    merged state."""
    with _lock:
        state = load_state(email)
        state.update(patch)
        if db.SUPABASE_ENABLED:
            state = _jsonb_safe(state)
            db.upsert("user_state", {"email": _norm_email(email), "state": state},
                      on_conflict="email")
            _scope_put(email, state)
            return state
        path = _state_path(email)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        _scope_put(email, state)
        return state


def get_key(email: str, key: str, default=None):
    return load_state(email).get(key, default)


def set_key(email: str, key: str, value) -> dict:
    return update_state(email, {key: value})


# ---------------------------------------------------------
# DataFrame storage
#   local:    pickled, one file per key
#   supabase: Fernet-encrypted pickle in the Storage bucket, one object per key
# ---------------------------------------------------------
def _safe_key(key: str) -> str:
    return "".join(ch for ch in str(key) if ch.isalnum() or ch in ("_", "-"))


def _df_path(email: str, key: str) -> str:
    return os.path.join(_user_dir(email), f"df_{_safe_key(key)}.pkl")


def _blob_path(email: str, key: str) -> str:
    return f"{_safe(email)}/df_{_safe_key(key)}.parquet"


def _fernet():
    # Imported lazily to avoid an import cycle (secrets_store imports user_store).
    from backend.core import secrets_store
    return secrets_store._fernet()


def _track_key(email: str, key: str, present: bool) -> None:
    keys = set(get_key(email, _DATASET_KEYS, []) or [])
    sk = _safe_key(key)
    if present:
        keys.add(sk)
    else:
        keys.discard(sk)
    set_key(email, _DATASET_KEYS, sorted(keys))


def save_df(email: str, key: str, df: pd.DataFrame) -> None:
    _DF_CACHE.pop((email, key), None)
    if db.SUPABASE_ENABLED:
        raw = pickle.dumps(df)
        enc = _fernet().encrypt(raw)
        db.upload_blob(_blob_path(email, key), enc, content_type="application/octet-stream")
        _track_key(email, key, True)
        return
    df.to_pickle(_df_path(email, key))


# Loaded datasets, kept in memory between requests. On Supabase every load is a
# network download + Fernet decrypt + pickle parse, and the home screen alone
# used to do it several times per visit. Keyed on the account's data stamp, so
# an upload or a new order invalidates it rather than a timer.
_DF_CACHE: dict[tuple, object] = {}
_DF_CACHE_MAX = 24


def _df_cache_get(email: str, key: str):
    from backend.core import cache
    hit = _DF_CACHE.get((email, key))
    if not hit:
        return None
    saved_stamp, df = hit
    if saved_stamp != cache.stamp(email):
        _DF_CACHE.pop((email, key), None)
        return None
    # hand out a copy: callers routinely mutate what they are given
    return df.copy()


def _df_cache_put(email: str, key: str, df):
    from backend.core import cache
    if df is None:
        return None
    if len(_DF_CACHE) >= _DF_CACHE_MAX:
        _DF_CACHE.clear()
    _DF_CACHE[(email, key)] = (cache.stamp(email), df)
    return df.copy()


def load_df(email: str, key: str):
    cached = _df_cache_get(email, key)
    if cached is not None:
        return cached

    if db.SUPABASE_ENABLED:
        enc = db.download_blob(_blob_path(email, key))
        if not enc:
            return None
        try:
            raw = _fernet().decrypt(enc)
            return _df_cache_put(email, key, pickle.loads(raw))
        except Exception:
            return None
    path = _df_path(email, key)
    if not os.path.exists(path):
        return None
    try:
        return _df_cache_put(email, key, pd.read_pickle(path))
    except Exception:
        return None


def has_df(email: str, key: str) -> bool:
    if db.SUPABASE_ENABLED:
        return _safe_key(key) in set(get_key(email, _DATASET_KEYS, []) or [])
    return os.path.exists(_df_path(email, key))


def delete_df(email: str, key: str) -> None:
    _DF_CACHE.pop((email, key), None)
    if db.SUPABASE_ENABLED:
        db.remove_blob(_blob_path(email, key))
        _track_key(email, key, False)
        return
    path = _df_path(email, key)
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass
