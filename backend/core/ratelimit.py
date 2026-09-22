"""A ceiling on how fast one caller may hit the API.

WHY THIS EXISTS
---------------
loginguard.py already stops password guessing, and aicaps.py already stops one
account spending the AI budget. Neither of them is a rate limit on the API as a
whole: every other endpoint accepted requests as fast as the network allowed.
On a 512MB instance that is not only an abuse problem, it is the memory
problem, because a few hundred concurrent requests each holding a dataframe is
how the service gets restarted.

THE SHAPE, AND WHY IT IS NOT A TOKEN BUCKET
-------------------------------------------
A fixed window per caller per minute. It is less smooth than a sliding window
or a leaky bucket and it needs one integer per caller instead of a timestamp
list, which is the trade that matters here: this runs on the same small box it
is protecting, so the limiter itself has to be close to free.

BOUNDED ON PURPOSE. The key is caller-controlled, so an attacker rotating
source addresses would otherwise grow this dict until the process dies — the
limiter becoming the outage it exists to prevent. Two defences: the whole table
is dropped when the window rolls, so nothing survives a minute, and it refuses
to track more than _MAX_KEYS distinct callers within one window. Past that
ceiling a caller that is not already known is allowed through rather than
denied, because failing open on an over-full table is the behaviour that keeps
real sellers working while an attack is happening; the per-endpoint limits and
loginguard are what actually hold the line on the sensitive routes.

WHAT IT IS NOT: in-process, like loginguard. With more than one instance each
has its own counters and the effective limit multiplies by the instance count.
One instance is what runs today; the honest fix when that changes is the same
counters in Redis, and the shape here does not have to change for that.
"""
from __future__ import annotations

import threading
import time

WINDOW = 60.0          # seconds in one window

# Requests per window, per caller. The default is deliberately generous: the
# app is chatty (a single screen can make a dozen calls) and a limit a real
# seller can reach is a bug, not a defence.
DEFAULT_LIMIT = 240

# Endpoints where a much lower ceiling is correct, longest prefix wins. These
# are the ones where a single request is expensive, sends mail, or is worth
# guessing at. Login is here as a second layer only; loginguard is the real one
# and it counts per ACCOUNT, which is what an attacker on a botnet cannot dodge.
LIMITS: dict[str, int] = {
    "/api/login": 20,
    "/api/register": 10,
    "/api/auth/google": 20,
    "/api/password-reset": 6,
    "/api/password-reset/request": 6,
    "/api/store/password-reset": 6,
    "/api/client-error": 30,
}

# Never limited. The scheduler calls tick every 15 minutes and locking it out
# would silently stop every seller's posts going out, which is a far worse
# failure than the one this file prevents.
EXEMPT: tuple[str, ...] = ("/api/admin/tick", "/healthz")

_MAX_KEYS = 20_000

_lock = threading.Lock()
_counts: dict[str, int] = {}
_window_start = [0.0]


def limit_for(path: str) -> int:
    """The ceiling for this path. Longest matching prefix wins."""
    best, best_len = DEFAULT_LIMIT, -1
    for prefix, n in LIMITS.items():
        if path.startswith(prefix) and len(prefix) > best_len:
            best, best_len = n, len(prefix)
    return best


def exempt(path: str) -> bool:
    return path.startswith(EXEMPT)


def check(caller: str, path: str) -> tuple[bool, int]:
    """(allowed, retry_after_seconds). Never raises."""
    if exempt(path):
        return True, 0
    cap = limit_for(path)
    now = time.time()
    with _lock:
        if now - _window_start[0] >= WINDOW:
            _window_start[0] = now
            _counts.clear()
        key = caller + " " + (path if cap != DEFAULT_LIMIT else "*")
        n = _counts.get(key)
        if n is None:
            if len(_counts) >= _MAX_KEYS:
                return True, 0          # fail open, see the module docstring
            n = 0
        if n >= cap:
            return False, max(1, int(WINDOW - (now - _window_start[0])) + 1)
        _counts[key] = n + 1
    return True, 0


def reset() -> None:
    """For tests."""
    with _lock:
        _counts.clear()
        _window_start[0] = 0.0
