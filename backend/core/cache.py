"""
A small in-process cache, for work this app was repeating on every page load.

WHAT WAS SLOW
-------------
The home screen alone asked the server for the same expensive things several
times: `/api/smart/state` and `/api/today` each loaded the account's sales
dataset and each ran the at-risk RFM pass over it. On a local disk that is
merely wasteful; on Render with Supabase every load is a network download plus
a Fernet decrypt plus a pickle parse, which is why the app felt slow there and
snappy locally.

HOW IT IS KEYED
---------------
Not on time alone — on a **fingerprint of the data**. Every entry carries the
account's dataset stamp (which datasets exist, their row counts and their
`updated_at`). Upload a file, add records, clear a dataset or take an order and
the stamp changes, so the cache misses and recomputes. A TTL is the backstop for
anything the stamp cannot see, not the primary mechanism — which means a seller
never looks at a stale number waiting for a timer to run out.

SCOPE
-----
Deliberately per-process and bounded. This is not Redis and must not become
load-bearing: every caller has to work correctly with the cache disabled, and
`clear(email)` after any write is the contract.
"""
from __future__ import annotations

import threading
import time

_LOCK = threading.RLock()
_ENTRIES: dict[tuple, tuple[float, str, object]] = {}   # key -> (expiry, stamp, value)
_MAX = 512
_DEFAULT_TTL = 120.0


def _evict_if_needed() -> None:
    if len(_ENTRIES) <= _MAX:
        return
    # drop the soonest-to-expire half; cheap, and this only runs when full
    for k, _ in sorted(_ENTRIES.items(), key=lambda kv: kv[1][0])[: _MAX // 2]:
        _ENTRIES.pop(k, None)


def stamp(email: str) -> str:
    """A cheap fingerprint of the account's data. Anything that changes what a
    computation would return must change this."""
    from backend.core import user_store
    try:
        st = user_store.get_key(email, "smart_data", {}) or {}
        parts = []
        for kind in ("sales", "review", "supply_sales"):
            k = st.get(kind) or {}
            parts.append(f"{kind}:{k.get('rows', 0)}:{k.get('updated_at', '')}")
        # site orders mirror into sales without touching smart_data, so count them
        orders = user_store.get_key(email, "store_orders", []) or []
        parts.append(f"orders:{len(orders)}")
        return "|".join(parts)
    except Exception:  # noqa: BLE001 — a fingerprint failure must only cost a cache miss
        return str(time.time())


def get(namespace: str, email: str, ttl: float = _DEFAULT_TTL, extra: str = ""):
    """Cached value, or None. Misses whenever the account's data has changed."""
    key = (namespace, email, extra)
    now = time.time()
    with _LOCK:
        hit = _ENTRIES.get(key)
        if not hit:
            return None
        expiry, saved_stamp, value = hit
        if expiry < now:
            _ENTRIES.pop(key, None)
            return None
    if saved_stamp != stamp(email):
        with _LOCK:
            _ENTRIES.pop(key, None)
        return None
    return value


def put(namespace: str, email: str, value, ttl: float = _DEFAULT_TTL, extra: str = ""):
    with _LOCK:
        _ENTRIES[(namespace, email, extra)] = (time.time() + ttl, stamp(email), value)
        _evict_if_needed()
    return value


def memo(namespace: str, email: str, build, ttl: float = _DEFAULT_TTL, extra: str = ""):
    """get-or-build. `build` is only called on a miss."""
    hit = get(namespace, email, ttl, extra)
    if hit is not None:
        return hit
    return put(namespace, email, build(), ttl, extra)


def clear(email: str = "", namespace: str = "") -> int:
    """Drop entries. Call after ANY write that changes what a cached call would
    return — uploads, order status, product edits, channel toggles."""
    with _LOCK:
        keys = [k for k in _ENTRIES
                if (not email or k[1] == email) and (not namespace or k[0] == namespace)]
        for k in keys:
            _ENTRIES.pop(k, None)
        return len(keys)


def stats() -> dict:
    with _LOCK:
        return {"entries": len(_ENTRIES), "max": _MAX}
