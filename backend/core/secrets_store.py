"""
Encrypted per-account credential storage.

Third-party commerce credentials (Shopify tokens, Amazon SP-API keys) and the
per-account DataFrame blobs are encrypted with Fernet (AES-128-CBC + HMAC).
Ciphertext lives in the user's JSON state (credentials) or the Storage bucket
(DataFrames), keyed to their login — the same trust boundary as user_store.

Key management (in priority order):
  1. env CS_SECRET_KEY  — a urlsafe base64 Fernet key. ALWAYS set this in
     production so the key is backed up independently of the data store.
  2. Supabase configured — a generated key is persisted in the `app_config`
     table so it survives restarts/redeploys.
  3. local file .fernet_key beside the user data (dev fallback).
"""
from __future__ import annotations

import json
import os

from cryptography.fernet import Fernet, InvalidToken

from backend.core import db, user_store

_CONN_KEY = "commerce_connections"
_APP_CONFIG_KEY = "fernet_key"


def _key() -> bytes:
    env = os.environ.get("CS_SECRET_KEY")
    if env:
        return env.encode() if isinstance(env, str) else env

    if db.SUPABASE_ENABLED:
        try:
            row = db.fetch_one("app_config", {"key": _APP_CONFIG_KEY})
            if row and row.get("value"):
                val = row["value"]
                return val.encode() if isinstance(val, str) else val
            k = Fernet.generate_key()
            db.upsert("app_config", {"key": _APP_CONFIG_KEY, "value": k.decode()},
                      on_conflict="key")
            return k
        except Exception:
            # If app_config is unreachable, fall back to a process-stable key so
            # the app keeps working (won't survive a restart — set CS_SECRET_KEY).
            globals().setdefault("_EPHEMERAL", Fernet.generate_key())
            return globals()["_EPHEMERAL"]

    # local dev: persist a generated key beside the user data
    root = getattr(user_store, "_ROOT", None) or "."
    path = os.path.join(root, ".fernet_key")
    try:
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read().strip()
        k = Fernet.generate_key()
        with open(path, "wb") as f:
            f.write(k)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return k
    except OSError:
        globals().setdefault("_EPHEMERAL", Fernet.generate_key())
        return globals()["_EPHEMERAL"]


def _fernet() -> Fernet:
    return Fernet(_key())


def encrypt_dict(data: dict) -> str:
    return _fernet().encrypt(json.dumps(data).encode()).decode()


def decrypt_dict(token: str) -> dict:
    try:
        return json.loads(_fernet().decrypt(token.encode()).decode())
    except (InvalidToken, ValueError):
        return {}


# ---------------------------------------------------------
# Per-account connection records
# ---------------------------------------------------------
def save_connection(email: str, connector: str, credentials: dict, meta: dict | None = None) -> None:
    conns = user_store.get_key(email, _CONN_KEY, {}) or {}
    conns[connector] = {
        "enc": encrypt_dict(credentials),
        **(meta or {}),
    }
    user_store.set_key(email, _CONN_KEY, conns)


def get_credentials(email: str, connector: str) -> dict | None:
    conns = user_store.get_key(email, _CONN_KEY, {}) or {}
    rec = conns.get(connector)
    if not rec or not rec.get("enc"):
        return None
    return decrypt_dict(rec["enc"])


def connection_meta(email: str, connector: str) -> dict | None:
    conns = user_store.get_key(email, _CONN_KEY, {}) or {}
    rec = conns.get(connector)
    if not rec:
        return None
    return {k: v for k, v in rec.items() if k != "enc"}


def is_connected(email: str, connector: str) -> bool:
    conns = user_store.get_key(email, _CONN_KEY, {}) or {}
    return bool(conns.get(connector, {}).get("enc"))


def delete_connection(email: str, connector: str) -> None:
    conns = user_store.get_key(email, _CONN_KEY, {}) or {}
    if connector in conns:
        conns.pop(connector, None)
        user_store.set_key(email, _CONN_KEY, conns)
