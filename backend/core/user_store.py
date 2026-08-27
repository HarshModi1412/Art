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
import hashlib
import json
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
def load_state(email: str) -> dict:
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


def save_state(email: str, state: dict) -> None:
    if db.SUPABASE_ENABLED:
        db.upsert("user_state", {"email": (email or "").strip().lower(), "state": state},
                  on_conflict="email")
        return
    path = _state_path(email)
    with _lock:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)


def update_state(email: str, patch: dict) -> dict:
    """Shallow-merge `patch` into the stored state and persist. Returns the
    merged state."""
    with _lock:
        state = load_state(email)
        state.update(patch)
        if db.SUPABASE_ENABLED:
            db.upsert("user_state", {"email": (email or "").strip().lower(), "state": state},
                      on_conflict="email")
            return state
        path = _state_path(email)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
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
    if db.SUPABASE_ENABLED:
        raw = pickle.dumps(df)
        enc = _fernet().encrypt(raw)
        db.upload_blob(_blob_path(email, key), enc, content_type="application/octet-stream")
        _track_key(email, key, True)
        return
    df.to_pickle(_df_path(email, key))


def load_df(email: str, key: str):
    if db.SUPABASE_ENABLED:
        enc = db.download_blob(_blob_path(email, key))
        if not enc:
            return None
        try:
            raw = _fernet().decrypt(enc)
            return pickle.loads(raw)
        except Exception:
            return None
    path = _df_path(email, key)
    if not os.path.exists(path):
        return None
    try:
        return pd.read_pickle(path)
    except Exception:
        return None


def has_df(email: str, key: str) -> bool:
    if db.SUPABASE_ENABLED:
        return _safe_key(key) in set(get_key(email, _DATASET_KEYS, []) or [])
    return os.path.exists(_df_path(email, key))


def delete_df(email: str, key: str) -> None:
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
