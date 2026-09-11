"""So that a crash reaches somebody.

THE PROBLEM THIS SOLVES
-----------------------
Before this, an unhandled exception on the live server produced a 500 for the
seller, a traceback in a Render log nobody reads, and no notification anywhere.
The seller does not write in to say "your app threw an error". They close the tab
and never come back, and the founder's evidence that anything is wrong is a
signup that went quiet. For a product with a handful of design partners, one
silent 500 can be the whole trial.

WHAT IT DOES
Three layers, cheapest first, each independent so a missing one does not disable
the others:

  1. A ring buffer on disk. Always on, no configuration, no third party. The last
     ERROR_LIMIT failures with their request path, the account, and the
     traceback, readable at /api/admin/errors with the admin token. This is the
     layer that works on a fresh deploy with nothing set up.
  2. An email to the operator, at most once every EMAIL_THROTTLE_MINUTES per
     distinct error, when SMTP and OPERATOR_EMAIL are both configured. Throttled
     per fingerprint because the failure mode of alerting is alert fatigue: fifty
     mails for one broken endpoint trains you to ignore all of them.
  3. Sentry, if SENTRY_DSN is set and the sdk is installed. Optional on purpose —
     it is the best of the three and it is also the one that requires an account,
     so it must not be the only one.

WHAT IT DELIBERATELY DOES NOT DO
It never stores the request body, and it truncates and redacts. A traceback from
this app can contain a seller's customer list, addresses and phone numbers; an
error log is not a place to put those. It also never lets its own failure break
the request it is reporting on — every path here is wrapped, because an error
reporter that raises is worse than no error reporter.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import traceback
from datetime import datetime, timezone

log = logging.getLogger("errors")

ERROR_LIMIT = int(os.environ.get("ERROR_LOG_LIMIT") or 200)
EMAIL_THROTTLE_MINUTES = int(os.environ.get("ERROR_EMAIL_THROTTLE_MIN") or 60)

# Anything that looks like a secret or a person. Applied to the traceback text
# before it is written anywhere.
_REDACT = [
    (re.compile(r"(?i)\b(api[_-]?key|token|secret|password|authorization|bearer)"
                r"\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]{6,})"), r"\1=<redacted>"),
    (re.compile(r"\b[\w\.\-\+]+@[\w\.\-]+\.\w{2,}\b"), "<email>"),
    (re.compile(r"\b(?:\+?91[\-\s]?)?[6-9]\d{9}\b"), "<phone>"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "<card>"),
]

_LAST_EMAILED: dict[str, float] = {}


def _redact(text: str) -> str:
    out = text or ""
    for pattern, repl in _REDACT:
        out = pattern.sub(repl, out)
    return out


def _path() -> str:
    from backend.core import auth
    return os.path.join(auth.BASE_DIR, "errors.jsonl")


def location(exc: BaseException) -> str:
    """Where it broke, short enough to read out of a screenshot: the exception
    type, the deepest line in this app's own code, and the line it finally
    failed on if that was inside a library — e.g.
    "APIError at social.py:1681 → request_builder.py:78". Never raises."""
    try:
        ours, last = "", ""
        tb = exc.__traceback__
        while tb is not None:
            fn = tb.tb_frame.f_code.co_filename.replace("\\", "/")
            here = f"{os.path.basename(fn)}:{tb.tb_lineno}"
            if "/backend/" in fn:
                ours = here
            last = here
            tb = tb.tb_next
        spot = ours or last
        if last and last != spot:
            spot = f"{spot} → {last}"
        return f"{type(exc).__name__} at {spot}" if spot else type(exc).__name__
    except Exception:  # noqa: BLE001
        return ""


def _fingerprint(exc: BaseException, where: str) -> str:
    """Groups the same bug together across occurrences.

    Deliberately the exception type plus the LAST frame plus the route, not the
    message: "KeyError: 'a1b2'" and "KeyError: 'c3d4'" are one bug, and treating
    them as two is how a log becomes unreadable.
    """
    tb = exc.__traceback__
    last = ""
    while tb is not None:
        last = f"{os.path.basename(tb.tb_frame.f_code.co_filename)}:{tb.tb_lineno}"
        tb = tb.tb_next
    return hashlib.sha1(
        f"{type(exc).__name__}|{last}|{where}".encode()).hexdigest()[:12]


def record(exc: BaseException, where: str = "", email: str = "",
           extra: dict | None = None) -> dict:
    """Write one failure down and, if configured, tell somebody. Never raises."""
    entry = {}
    try:
        entry = {
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "kind": type(exc).__name__,
            "message": _redact(str(exc))[:400],
            "where": where[:200],
            # The account, not the person: enough to reproduce, and it is already
            # the key everything else in this app is stored under.
            "account": (email or "")[:120],
            "fingerprint": _fingerprint(exc, where),
            "location": location(exc),
            "traceback": _redact("".join(traceback.format_exception(
                type(exc), exc, exc.__traceback__)))[-4000:],
        }
        if extra:
            entry["extra"] = {k: str(v)[:200] for k, v in list(extra.items())[:10]}
    except Exception:  # noqa: BLE001 — reporting must never be the thing that breaks
        return {}

    try:
        _append(entry)
    except Exception as e:  # noqa: BLE001
        log.warning("could not write the error log: %s", e)
    try:
        _to_sentry(exc, entry)
    except Exception:  # noqa: BLE001
        pass
    try:
        _maybe_email(entry)
    except Exception as e:  # noqa: BLE001
        log.warning("could not send the error mail: %s", e)
    return entry


def _append(entry: dict) -> None:
    path = _path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    # Trim in place rather than growing without limit. Cheap because the file is
    # small by construction, and it keeps a runaway loop from filling the disk.
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
        if len(lines) > ERROR_LIMIT * 2:
            with open(path, "w", encoding="utf-8") as fh:
                fh.writelines(lines[-ERROR_LIMIT:])
    except Exception:  # noqa: BLE001
        pass


def _to_sentry(exc: BaseException, entry: dict) -> None:
    dsn = (os.environ.get("SENTRY_DSN") or "").strip()
    if not dsn:
        return
    import sentry_sdk  # optional dependency, imported only when configured
    with sentry_sdk.new_scope() as scope:
        scope.set_tag("route", entry.get("where", ""))
        scope.set_tag("fingerprint", entry.get("fingerprint", ""))
        if entry.get("account"):
            scope.set_user({"id": entry["account"]})
        sentry_sdk.capture_exception(exc)


def sentry_ready() -> bool:
    if not (os.environ.get("SENTRY_DSN") or "").strip():
        return False
    try:
        import sentry_sdk  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _maybe_email(entry: dict) -> None:
    from backend.core import messaging
    to = (os.environ.get("OPERATOR_EMAIL") or "").strip()
    if not to or not messaging.smtp_configured():
        return
    fp = entry.get("fingerprint") or "?"
    now = time.time()
    if now - _LAST_EMAILED.get(fp, 0) < EMAIL_THROTTLE_MINUTES * 60:
        return
    _LAST_EMAILED[fp] = now
    messaging.send(
        to_email=to,
        subject=f"[One Tap Manager] {entry['kind']} in {entry.get('where') or 'the app'}",
        text=(f"{entry['kind']}: {entry['message']}\n\n"
              f"Where: {entry.get('where')}\n"
              f"Account: {entry.get('account') or '(not signed in)'}\n"
              f"When: {entry['at']}\n"
              f"Group: {fp}\n\n{entry.get('traceback', '')}\n\n"
              f"Further mails about this same failure are held for "
              f"{EMAIL_THROTTLE_MINUTES} minutes."))


def recent(limit: int = 50) -> list[dict]:
    """Newest first."""
    try:
        with open(_path(), encoding="utf-8") as fh:
            rows = [json.loads(ln) for ln in fh if ln.strip()]
    except FileNotFoundError:
        return []
    except Exception:  # noqa: BLE001
        return []
    return rows[-limit:][::-1]


def summary(limit: int = 50) -> dict:
    """Grouped by fingerprint, because what matters is which bug and how often."""
    rows = recent(ERROR_LIMIT)
    groups: dict[str, dict] = {}
    for r in rows:
        fp = r.get("fingerprint") or "?"
        g = groups.setdefault(fp, {"fingerprint": fp, "kind": r.get("kind"),
                                   "message": r.get("message"),
                                   "where": r.get("where"), "count": 0,
                                   "first": r.get("at"), "last": r.get("at"),
                                   "accounts": set()})
        g["count"] += 1
        g["first"] = min(g["first"], r.get("at") or g["first"])
        g["last"] = max(g["last"], r.get("at") or g["last"])
        if r.get("account"):
            g["accounts"].add(r["account"])
    out = []
    for g in groups.values():
        g = dict(g)
        g["accounts_hit"] = len(g.pop("accounts"))
        out.append(g)
    out.sort(key=lambda g: g["last"], reverse=True)
    return {
        "groups": out[:limit],
        "total": len(rows),
        "channels": {
            "log": True,
            "email": bool((os.environ.get("OPERATOR_EMAIL") or "").strip())
                     and _smtp(),
            "sentry": sentry_ready(),
        },
    }


def _smtp() -> bool:
    from backend.core import messaging
    return messaging.smtp_configured()


def clear() -> int:
    n = len(recent(ERROR_LIMIT))
    try:
        os.remove(_path())
    except FileNotFoundError:
        pass
    except Exception:  # noqa: BLE001
        pass
    return n


def init_sentry() -> bool:
    """Called once at import. Returns whether Sentry is live."""
    dsn = (os.environ.get("SENTRY_DSN") or "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=dsn,
            environment=os.environ.get("RENDER_SERVICE_NAME") or "local",
            traces_sample_rate=0.0,      # errors only; tracing is not the problem
            send_default_pii=False,      # never the seller's customers
        )
        log.info("Sentry is on")
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("SENTRY_DSN is set but Sentry could not start: %s", e)
        return False
