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

import logging
import threading
import time

log = logging.getLogger(__name__)


class SuspiciousLogin(Exception):
    """Not a crash: an event worth an operator's attention.

    It goes through errors.record() because that is where alerting already
    lives, and it is its own type so it is filtered from real faults at a
    glance in the error log.
    """

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
    """Record one wrong password, and write it down.

    The counting is what stops the attack; the LOG is what tells anyone it
    happened. Before this, a credential-stuffing run was throttled perfectly
    and left no trace at all, so the first anybody knew of it was a seller
    saying their account had been taken. Every failure now goes to the
    application log with the address it came from.

    The address is logged, the password never is, and the email is logged
    because it IS the account under attack and there is no way to act on
    "someone is being guessed at" without it.

    Crossing the lock threshold is escalated to errors.record(), which is the
    same path a crash takes, so it reaches the operator's error log and their
    alert email rather than sitting in a log nobody reads.
    """
    now = time.time()
    acct = f"a:{(email or '').strip().lower()}"
    with _lock:
        for key in (acct, f"i:{ip}" if ip else ""):
            if key:
                _fails.setdefault(key, []).append(now)
        acct_fails = len(_fails.get(acct, []))
        ip_fails = len(_fails.get(f"i:{ip}", [])) if ip else 0

    log.warning("failed login for %s from %s (%d for this account, %d from "
                "this address, in the last %d minutes)",
                (email or "?").strip().lower() or "?", ip or "unknown",
                acct_fails, ip_fails, int(WINDOW // 60))

    # One escalation per threshold crossing, not one per attempt after it.
    if acct_fails == LOCK_AFTER or (ip and ip_fails == IP_LOCK_AFTER):
        what = ("account" if acct_fails == LOCK_AFTER else "address")
        try:
            from backend.core import errors
            errors.record(
                SuspiciousLogin(
                    f"{acct_fails} failed logins for {(email or '?').strip().lower()} "
                    f"and {ip_fails} from {ip or 'unknown'} within "
                    f"{int(WINDOW // 60)} minutes; this {what} is now paused"),
                where="POST /api/login",
                extra={"ip": ip or "unknown", "account_failures": acct_fails,
                       "ip_failures": ip_fails})
        except Exception:  # noqa: BLE001 - alerting must not break the login path
            log.exception("could not escalate a login lockout")


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
