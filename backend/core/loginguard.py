"""
Slowing down someone who is guessing passwords.

WHY THIS EXISTS
---------------
/api/login accepted unlimited attempts. A list of leaked email/password pairs
run against it — which is how small SaaS accounts are actually taken, not by
cracking a hash — would have worked at whatever rate the network allowed. The
password hash got six times stronger in the same change that added this file,
and that does nothing against credential stuffing: the attacker already has the
password, they are only checking whether it works here.

WHAT IT DOES, AND WHY IN THIS SHAPE
  * Counts failures PER ACCOUNT, not only per IP. Per-IP alone is what everyone
    writes first and it is the one an attacker sidesteps for free, by spreading
    the same guesses over a botnet. Per-IP is still counted, as the second
    layer, because it catches the crude case cheaply.
  * Delays before it locks. The first few failures cost a second, then two,
    then four — a person who mistyped their password barely notices, a script
    trying ten thousand passwords is stopped dead. NIST allows up to 100
    consecutive failures; OWASP's advice is graduated delay rather than a cliff.
  * NEVER locks an account permanently. A permanent lock on failed attempts is
    a free denial-of-service against any user whose email address is known. The
    lock expires by itself.
  * Says the same thing either way. The endpoint returns "Invalid credentials"
    whether the address exists, the password is wrong, or the account is
    throttled, so none of it can be used to work out which emails are real.

WHAT IT IS NOT: this is in-process memory. With more than one instance each has
its own counters, so the effective limit multiplies by the instance count. That
is still far better than none, and the honest fix when this app scales out is
the same counters in Supabase or Redis — deliberately not built yet, because
one instance is what is running.
"""
from __future__ import annotations

import threading
import time

# failures -> how long the next attempt has to wait, in seconds.
# 1, 2, 4, 8, 16, then a flat minute per attempt after that.
_BACKOFF = [0, 0, 0, 1, 2, 4, 8, 16, 30, 60]
_MAX_DELAY = 60.0

WINDOW = 15 * 60          # failures older than this stop counting
LOCK_AFTER = 12           # failures in the window before a hard pause
LOCK_FOR = 15 * 60        # and how long that pause lasts
IP_LOCK_AFTER = 40        # a single address may be many sellers behind one NAT

_lock = threading.Lock()
_fails: dict[str, list[float]] = {}
_locked_until: dict[str, float] = {}


def _prune(key: str, now: float) -> list[float]:
    hits = [t for t in _fails.get(key, []) if now - t < WINDOW]
    if hits:
        _fails[key] = hits
    else:
        _fails.pop(key, None)
    return hits


def check(email: str, ip: str = "") -> tuple[bool, float]:
    """(allowed, seconds_to_wait) — call before verifying a password.

    `seconds_to_wait` is advisory: the caller sleeps it, so a slow guess costs
    the attacker wall-clock time rather than costing us a lock."""
    now = time.time()
    account = f"a:{(email or '').strip().lower()}"
    source = f"i:{ip}" if ip else ""
    with _lock:
        for key, ceiling in ((account, LOCK_AFTER), (source, IP_LOCK_AFTER)):
            if not key:
                continue
            until = _locked_until.get(key, 0)
            if until > now:
                return False, until - now
            if until:
                _locked_until.pop(key, None)
            hits = _prune(key, now)
            if len(hits) >= ceiling:
                _locked_until[key] = now + LOCK_FOR
                return False, float(LOCK_FOR)
        n = len(_fails.get(account, []))
    delay = _BACKOFF[n] if n < len(_BACKOFF) else _MAX_DELAY
    return True, float(delay)


def failed(email: str, ip: str = "") -> None:
    """Record one wrong password."""
    now = time.time()
    with _lock:
        for key in (f"a:{(email or '').strip().lower()}", f"i:{ip}" if ip else ""):
            if key:
                _fails.setdefault(key, []).append(now)


def succeeded(email: str, ip: str = "") -> None:
    """A correct password clears the account's history.

    The IP's history is deliberately NOT cleared: an attacker with one valid
    login would otherwise reset their own counter between guesses at everyone
    else's account."""
    with _lock:
        _fails.pop(f"a:{(email or '').strip().lower()}", None)
        _locked_until.pop(f"a:{(email or '').strip().lower()}", None)


def reset() -> None:
    """Tests only."""
    with _lock:
        _fails.clear()
        _locked_until.clear()


def client_ip(request) -> str:
    """The caller's address, as seen from behind Render's proxy.

    X-Forwarded-For is a chain the client can prepend to, so the FIRST entry is
    attacker-controlled and useless. The LAST entry is the one our own proxy
    wrote, which is the closest thing to the truth available here."""
    fwd = ""
    try:
        fwd = request.headers.get("x-forwarded-for", "") or ""
    except Exception:  # noqa: BLE001
        fwd = ""
    if fwd:
        return fwd.split(",")[-1].strip()
    try:
        return request.client.host if request.client else ""
    except Exception:  # noqa: BLE001
        return ""
