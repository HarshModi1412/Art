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
import time
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


@contextlib.contextmanager
def job_scope():
    """request_scope() for work that runs outside a request: the weekly
    planner, the auto-approve worker, the publisher, the win-back scan.

    Without a scope a background job had no record of what it read, so its
    write could not be merged (update_state) and simply replaced the key: the
    planner spends minutes writing captions, then saved the posts list it read
    at the start, putting back to draft every post approved in the meantime.
    Inside a request it does nothing; the request's own scope already applies."""
    if _scope.get() is not None:
        yield
        return
    with request_scope():
        yield


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


# Every write in this process bumps the account's version. A request records
# the version its memoised copy was taken at, so update_state can tell whether
# anyone else has written since: if not, the copy IS the stored state and the
# extra read is skipped (on Supabase that read is a full round trip, and the
# home screen is budgeted at one per request: test_perf_resilience).
_versions: dict[str, int] = {}
_vlock = threading.Lock()


def _version(email: str) -> int:
    return _versions.get(_norm_email(email), 0)


def _bump(email: str) -> int:
    with _vlock:
        e = _norm_email(email)
        _versions[e] = _versions.get(e, 0) + 1
        return _versions[e]


def _scope_put(email: str, state: dict, version: int | None = None) -> None:
    box = _scope.get()
    if box is not None:
        e = _norm_email(email)
        box[e] = copy.deepcopy(state)
        box[e + "#v"] = _version(email) if version is None else version


def _scope_version(email: str):
    box = _scope.get()
    return None if box is None else box.get(_norm_email(email) + "#v")


def load_state(email: str) -> dict:
    cached = _scope_get(email)
    if cached is not None:
        return cached
    # the version BEFORE the read: a write that lands during it makes this
    # copy look older than it is, which costs a re-read, never a lost write
    v = _version(email)
    state = _read_state(email)
    _scope_put(email, state, v)
    return state


def _replace(tmp: str, path: str) -> None:
    """os.replace, patient on Windows. There a file another thread has open
    for reading cannot be replaced (WinError 5), and the weekly auto-approve
    reads an account's state in the background while requests write it. Linux
    (Render) never hits this; a local run and the test suites did."""
    for attempt in range(40):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if os.name != "nt" or attempt == 39:
                raise
            time.sleep(0.025)


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
    # On Windows a file being replaced by another thread cannot be opened for
    # that instant (WinError 5 / 32). Reading it as "no state" made the
    # background auto-approve see an empty account, and a write after such a
    # read would save an empty one. Wait it out instead. Linux never hits this.
    for attempt in range(40):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except PermissionError:
            if os.name != "nt" or attempt == 39:
                return {}
            time.sleep(0.025)
        except Exception:
            return {}
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
        _scope_put(email, state, _bump(email))
        return
    path = _state_path(email)
    with _lock:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        _replace(tmp, path)
    _scope_put(email, state, _bump(email))


_MISSING = object()   # this request never read the state: nothing to merge against
_ABSENT = object()    # it read the state and the key was not in it


def _merge_value(base, ours, theirs):
    """Three-way merge of one key: `base` is what this request last saw,
    `ours` what it wants to write, `theirs` what is stored now.

    WHY: the per-request memo above means a request writes from the copy it
    read when it started. Approve all sends two approvals at once and each
    spends seconds drawing a picture, so each saved the posts list as it was
    before the other's approval, and the last one to finish put every other
    post back to draft. A seller had to press Approve all once per post.

    When nobody else wrote the key, ours wins exactly as before. When someone
    did, a dict merges per sub-key and a list of {"id": ...} records merges per
    record, each side keeping what it changed. Anything else is last-writer."""
    if base is _ABSENT:
        if isinstance(ours, list) and isinstance(theirs, list):
            base = []
        elif isinstance(ours, dict) and isinstance(theirs, dict):
            base = {}
        else:
            base = None
    if base is _MISSING or theirs == base:
        return ours
    if isinstance(ours, dict) and isinstance(base, dict) and isinstance(theirs, dict):
        out = dict(theirs)
        for k in set(base) | set(ours):
            b, o = base.get(k, _MISSING), ours.get(k, _MISSING)
            if o is _MISSING:
                if b is not _MISSING:
                    out.pop(k, None)          # we deleted it
            elif b is _MISSING or o != b:
                out[k] = _merge_value(b, o, theirs.get(k, _MISSING)) \
                    if b is not _MISSING and k in theirs else o
        return out
    ids = _record_ids(base), _record_ids(ours), _record_ids(theirs)
    if None not in ids:
        base_by = {r["id"]: r for r in base}
        ours_by = {r["id"]: r for r in ours}
        out = []
        for r in theirs:
            rid = r["id"]
            if rid in base_by and rid not in ours_by:
                continue                       # we removed it
            mine = ours_by.get(rid)
            if mine is None or mine == base_by.get(rid):
                out.append(r)                  # we did not touch it: theirs
            elif rid in base_by and r != base_by[rid]:
                # both sides changed this record (the planner retagging a post
                # while the approver scheduled it): merge it field by field,
                # so each keeps the fields it changed
                out.append(_merge_value(base_by[rid], mine, r))
            else:
                out.append(mine)
        have = {r["id"] for r in out}
        out.extend(r for r in ours if r["id"] not in have and r["id"] not in base_by)
        return out
    return ours


def _record_ids(v):
    """The ids of a list of {"id": ...} dicts, or None if it is not one."""
    if not isinstance(v, list) or not all(isinstance(r, dict) and "id" in r for r in v):
        return None
    ids = [r["id"] for r in v]
    return ids if len(set(map(str, ids))) == len(ids) else None


def update_state(email: str, patch: dict) -> dict:
    """Merge `patch` into the stored state and persist. Returns the merged
    state.

    Starts from the CURRENT stored state, not this request's memoised copy,
    so keys this request never touched keep whatever another request wrote
    meanwhile, and the keys it did touch are merged against what it last saw
    (see _merge_value). When no other write has happened in this process
    since the copy was taken, the copy is the stored state and no read is
    spent finding that out."""
    with _lock:
        seen = _scope_get(email)
        if seen is not None and _scope_version(email) == _version(email):
            state = dict(seen)   # nobody wrote since: it IS the stored state
        else:
            state = _read_state(email)
        for k, v in patch.items():
            # read the state but the key was not there yet: it was empty, not
            # unknown, so a job that started before anyone wrote it merges
            # its additions rather than replacing what was written meanwhile
            base = seen.get(k, _ABSENT) if seen is not None else _MISSING
            state[k] = _merge_value(base, v, state.get(k))
        if db.SUPABASE_ENABLED:
            state = _jsonb_safe(state)
            db.upsert("user_state", {"email": _norm_email(email), "state": state},
                      on_conflict="email")
            _scope_put(email, state, _bump(email))
            return state
        path = _state_path(email)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        _replace(tmp, path)
        _scope_put(email, state, _bump(email))
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
        # the plaintext is not needed for the (slow) network call; on a 512MB
        # box holding both through the upload is a dataset's worth of memory
        del raw
        db.upload_blob(_blob_path(email, key), enc, content_type="application/octet-stream")
        del enc
        _track_key(email, key, True)
        return
    df.to_pickle(_df_path(email, key))


# Loaded datasets, kept in memory between requests. On Supabase every load is a
# network download + Fernet decrypt + pickle parse, and the home screen alone
# used to do it several times per visit. Keyed on the account's data stamp, so
# an upload or a new order invalidates it rather than a timer.
_DF_CACHE: dict[tuple, object] = {}
_DF_CACHE_MAX = 24


def _df_cache_get(email: str, key: str, copy: bool = True):
    from backend.core import cache
    hit = _DF_CACHE.get((email, key))
    if not hit:
        return None
    saved_stamp, df = hit
    if saved_stamp != cache.stamp(email):
        _DF_CACHE.pop((email, key), None)
        return None
    # hand out a copy: callers routinely mutate what they are given
    return df.copy() if copy else df


def _df_cache_put(email: str, key: str, df, copy: bool = True):
    from backend.core import cache
    if df is None:
        return None
    if len(_DF_CACHE) >= _DF_CACHE_MAX:
        _DF_CACHE.clear()
    _DF_CACHE[(email, key)] = (cache.stamp(email), df)
    return df.copy() if copy else df


def remember_df(email: str, key: str, df) -> None:
    """Seed the cache with a frame that was just saved, so the next load_df
    does not download, decrypt and unpickle the very bytes we uploaded a
    moment ago. Call it AFTER the write that changes cache.stamp(email) (the
    smart_data row count / updated_at), or the entry is born stale. The cache
    takes ownership: the caller must not mutate `df` afterwards."""
    if df is None:
        return
    from backend.core import cache
    if len(_DF_CACHE) >= _DF_CACHE_MAX:
        _DF_CACHE.clear()
    _DF_CACHE[(email, key)] = (cache.stamp(email), df)


# One cold load per dataset at a time. The home screen fires its first few
# requests together, and on a fresh process every one of them missed the
# cache and downloaded, decrypted and unpickled the whole sales table at once:
# three or four full copies in flight, which is what OOM-killed the 512MB
# instance on 2 October 2026 when a seller opened Sales Analytics right after
# a deploy. The others now wait for the first and are served from the cache.
_LOAD_LOCKS: dict[tuple, threading.Lock] = {}
_LOAD_LOCKS_GUARD = threading.Lock()


def _load_lock(email: str, key: str) -> threading.Lock:
    with _LOAD_LOCKS_GUARD:
        lk = _LOAD_LOCKS.get((email, key))
        if lk is None:
            lk = _LOAD_LOCKS[(email, key)] = threading.Lock()
        return lk


def load_df(email: str, key: str, copy: bool = True):
    """The saved frame, or None.

    copy=False hands out the cached frame itself, for callers that only read
    it (select columns, group, sum). It saves a full copy of the dataset per
    call; a caller that adds a column or assigns into it must keep the
    default, or it corrupts every later reader."""
    cached = _df_cache_get(email, key, copy)
    if cached is not None:
        return cached
    with _load_lock(email, key):
        cached = _df_cache_get(email, key, copy)    # someone loaded it meanwhile
        if cached is not None:
            return cached
        return _load_df_uncached(email, key, copy)


def _load_df_uncached(email: str, key: str, copy: bool):
    if db.SUPABASE_ENABLED:
        enc = db.download_blob(_blob_path(email, key))
        if not enc:
            return None
        try:
            raw = _fernet().decrypt(enc)
            del enc
            df = pickle.loads(raw)
            del raw
            return _df_cache_put(email, key, df, copy)
        except Exception:
            return None
    path = _df_path(email, key)
    if not os.path.exists(path):
        return None
    try:
        return _df_cache_put(email, key, pd.read_pickle(path), copy)
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


def purge(email: str) -> None:
    """Erase every scrap of this account's saved state and all its stored
    DataFrames. Used by BOTH the Account tab's Reset (login kept) and Delete
    (login also removed) — this only removes the per-account state/data this
    module owns, never the login row or the purchase ledger.

    Supabase mode: drop every DataFrame blob this account tracks, then the
    user_state row. Local mode: remove the whole per-account directory, which
    is state.json plus every df_*.pkl in one go."""
    email_n = _norm_email(email)
    # forget any in-memory copies first, so a later read in the same process
    # rebuilds from the now-empty store rather than serving a stale dict/frame.
    for k in [key for key in _DF_CACHE if key[0] == email or key[0] == email_n]:
        _DF_CACHE.pop(k, None)
    box = _scope.get()
    if box is not None:
        box.pop(email_n, None)

    if db.SUPABASE_ENABLED:
        for key in list(get_key(email, _DATASET_KEYS, []) or []):
            try:
                db.remove_blob(_blob_path(email, key))
            except Exception:  # noqa: BLE001
                pass
        try:
            db.delete("user_state", {"email": email_n})
        except Exception:  # noqa: BLE001
            pass
        return

    import shutil
    d = os.path.join(_ROOT, _safe(email))
    try:
        if os.path.isdir(d):
            shutil.rmtree(d)
    except OSError:
        pass
