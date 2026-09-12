"""
Win-back, on a schedule, without being asked.

WHY THIS EXISTS
---------------
The win-back card already appeared in the Approval panel whenever the data
happened to contain at-risk customers, and it said "Approve → download
campaign". Two things were wrong with that.

First, it was passive. It sat there, identical, week after week, until the
seller happened to look. The whole value of a win-back is that it is timely:
a customer who last bought 70 days ago is reachable, and the same customer at
140 days is a stranger. Nobody remembers to check on a Tuesday.

Second, it ended in a spreadsheet. A seller who downloads an Excel of messages
has to then send them, one at a time, from an app this one cannot see — so
nothing is measurable, the send never happens, and the feature quietly proves
itself useless.

So this runs on the same weekly clock as the social auto-plan: it recomputes
who has gone quiet from the seller's own sales history, writes each message
against what that person actually bought, and puts ONE card in the Approval
panel. Approving it SENDS, from the seller's own mailbox, and records who was
contacted so the result can be measured later.

THE COOLDOWN IS THE MOST IMPORTANT PART OF THIS FILE
----------------------------------------------------
An at-risk customer stays at-risk. Without a memory, a weekly job mails the
same person every week forever — which is not a win-back campaign, it is
becoming a spammer, and it takes about three weeks to get a small shop's
domain into a spam folder permanently. `COOLDOWN_DAYS` is how long someone is
left alone after being contacted, read from the campaigns this app actually
recorded (backend/core/winback_proof.py). Nobody is targeted twice inside it.

The run also stops itself when there is nothing worth sending: fewer than
MIN_BATCH people, or no sales data at all. A card that says "0 customers" every
Monday trains the seller to ignore the panel.

WHAT IT NEVER DOES: send on its own. The batch waits in the Approval panel.
Everything else in this app asks before it acts on a seller's behalf, and a
message going out to their customers in their name is the last place to make
an exception.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from backend.core import localtime, user_store

log = logging.getLogger("winback_auto")

STATE_KEY = "winback_auto"
SETTINGS_KEY = "winback_auto_settings"

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Monday morning. The social plan runs Saturday by default, on purpose: two
# different decisions landing in the panel at the same moment means one of them
# gets rubber-stamped. Monday is also when a shop is quietest and a "we've
# missed you" mail is most likely to be read.
DEFAULT_DAY = 0
DEFAULT_HOUR = 10

COOLDOWN_DAYS = 45        # leave a contacted customer alone for this long
MIN_BATCH = 3             # below this it is not worth a card
MAX_BATCH = 60            # one send, not a mailing list


# ------------------------------------------------------------------ settings
def get_config(email: str) -> dict:
    s = user_store.get_key((email or "").lower(), SETTINGS_KEY, {}) or {}
    try:
        day = int(s.get("day", DEFAULT_DAY)) % 7
    except (TypeError, ValueError):
        day = DEFAULT_DAY
    try:
        hour = max(0, min(23, int(s.get("hour", DEFAULT_HOUR))))
    except (TypeError, ValueError):
        hour = DEFAULT_HOUR
    return {"enabled": bool(s.get("enabled", True)), "day": day, "hour": hour,
            "day_name": DAY_NAMES[day], "cooldown_days": COOLDOWN_DAYS}


def save_config(email: str, patch: dict) -> dict:
    cur = get_config(email)
    clean = {"enabled": cur["enabled"], "day": cur["day"], "hour": cur["hour"]}
    if "enabled" in patch:
        clean["enabled"] = bool(patch["enabled"])
    if "day" in patch:
        try:
            clean["day"] = int(patch["day"]) % 7
        except (TypeError, ValueError):
            pass
    if "hour" in patch:
        try:
            clean["hour"] = max(0, min(23, int(patch["hour"])))
        except (TypeError, ValueError):
            pass
    user_store.set_key((email or "").lower(), SETTINGS_KEY, clean)
    st = _state(email)
    if clean["enabled"] and not st.get("armed_at"):
        st["armed_at"] = _now(email).isoformat(timespec="seconds")
        _save_state(email, st)
    return status(email)


def _now(email: str = "") -> datetime:
    return localtime.now(email)


def _state(email: str) -> dict:
    st = user_store.get_key((email or "").lower(), STATE_KEY, {}) or {}
    return st if isinstance(st, dict) else {}


def _save_state(email: str, st: dict) -> None:
    st["runs"] = (st.get("runs") or [])[-8:]
    user_store.set_key((email or "").lower(), STATE_KEY, st)


# ------------------------------------------------------------------- timing
def _last_trigger(now: datetime, day: int, hour: int) -> datetime:
    back = (now.weekday() - day) % 7
    t = datetime.combine(now.date() - timedelta(days=back),
                         datetime.min.time()).replace(hour=hour)
    if t > now:
        t -= timedelta(days=7)
    return t


def next_trigger(now: datetime, day: int, hour: int) -> datetime:
    return _last_trigger(now, day, hour) + timedelta(days=7)


def arm(email: str) -> dict:
    """When automatic win-back started watching this account.

    The first run is the first trigger AFTER this moment. Without it, turning
    the feature on at 11am on a Monday would immediately fire the 10am trigger
    that had already passed — so a seller who enables it sees a batch of
    messages to their customers appear a second later, which is exactly the
    surprise this app is meant not to produce."""
    st = _state(email)
    if not st.get("armed_at"):
        st["armed_at"] = _now(email).isoformat(timespec="seconds")
        _save_state(email, st)
    return st


def due(email: str, now: datetime | None = None) -> str | None:
    """The trigger moment that should be acted on now, or None."""
    cfg = get_config(email)
    if not cfg["enabled"]:
        return None
    now = now or _now(email)
    st = arm(email)
    try:
        armed = datetime.fromisoformat(st["armed_at"])
    except (KeyError, ValueError, TypeError):
        return None
    last = _last_trigger(now, cfg["day"], cfg["hour"])
    if last < armed:
        return None
    stamp = last.isoformat(timespec="hours")
    if st.get("last_trigger") == stamp:
        return None
    # NO CATCH-UP GUARD IS NEEDED HERE, and one used to be written that could
    # never fire. `_last_trigger` always returns the MOST RECENT trigger, so a
    # server that slept through three Mondays wakes to exactly one pending
    # trigger, not three: it prepares this week's batch against today's data
    # and the two missed weeks are simply gone. That is the right answer —
    # a win-back list from three weeks ago is a list of people who may well
    # have bought since.
    return stamp


# ----------------------------------------------------------------- cooldown
def recently_contacted(email: str, days: int = COOLDOWN_DAYS) -> set[str]:
    """Customer ids contacted within the cooldown, from campaigns this app
    actually recorded. Pending ones count: the seller was handed tap-to-send
    links, and mailing the same person again on the assumption they did not
    use them is the wrong way to be wrong."""
    from backend.core import winback_proof
    cutoff = datetime.now() - timedelta(days=days)
    out: set[str] = set()
    try:
        rows = winback_proof._load((email or "").lower())
    except Exception:  # noqa: BLE001
        return out
    for row in rows or []:
        try:
            when = datetime.fromisoformat(str(row.get("sent_at", "")).replace("Z", ""))
        except (TypeError, ValueError):
            continue
        if when < cutoff:
            continue
        for t in row.get("targets") or []:
            cid = str(t.get("customer_id") or "").strip()
            if cid:
                out.add(cid)
    return out


# --------------------------------------------------------------------- run
def build_batch(email: str) -> dict:
    """Who to reach this week, and what to say to each of them.

    Reads the seller's own sales history — the same at-risk pool the Today
    strip and the manual generator use, so the app never disagrees with
    itself about who has gone quiet."""
    from backend.core import analytics, smart, templates

    txns = smart.load_sales(email)
    if txns is None or not len(txns):
        return {"ok": False, "reason": "no sales data yet", "rows": [], "skipped": 0}

    try:
        at_risk = analytics.at_risk_cached(email, txns) or []
    except Exception as e:  # noqa: BLE001
        log.warning("win-back scan failed for %s: %s", email, e)
        return {"ok": False, "reason": str(e)[:120], "rows": [], "skipped": 0}
    if not at_risk:
        return {"ok": False, "reason": "nobody has gone quiet", "rows": [], "skipped": 0}

    cooling = recently_contacted(email)
    fresh = [c for c in at_risk if str(c.get("customer_id") or "") not in cooling]
    skipped = len(at_risk) - len(fresh)

    # Most valuable first: if the batch has to be capped, it should keep the
    # customers worth the most, not the ones the dataframe happened to sort to
    # the top.
    fresh.sort(key=lambda c: float(c.get("monetary") or 0), reverse=True)
    fresh = fresh[:MAX_BATCH]

    if len(fresh) < MIN_BATCH:
        return {"ok": False, "rows": [], "skipped": skipped,
                "reason": (f"everyone at risk was already contacted in the last "
                           f"{COOLDOWN_DAYS} days" if skipped and not fresh
                           else f"only {len(fresh)} to reach — not worth a campaign yet")}

    rows = templates.build_winback_messages(fresh)
    reachable = [r for r in rows
                 if str(r.get("email") or r.get("customer_email") or "").strip()
                 or str(r.get("phone") or r.get("customer_phone") or "").strip()]
    return {
        "ok": bool(reachable),
        "rows": rows,
        "reachable": len(reachable),
        "skipped": skipped,
        "value": round(sum(float(r.get("monetary") or 0) for r in rows), 2),
        "reason": "" if reachable else "none of them have an email or phone on file",
    }


def run_if_due(email: str, now: datetime | None = None, trigger: str = "auto") -> dict:
    """Do this week's scan if its moment has come. Safe to call as often as
    you like — it is a no-op every time but once a week."""
    stamp = due(email, now) if trigger == "auto" else _now(email).isoformat(timespec="hours")
    if trigger == "auto" and not stamp:
        return {"skipped": True, "reason": "not due"}

    batch = build_batch(email)
    st = _state(email)
    st["last_trigger"] = stamp
    st["last_run_at"] = _now(email).isoformat(timespec="seconds")
    run = {"at": st["last_run_at"], "trigger": trigger, "ok": batch["ok"],
           "n": len(batch["rows"]), "reachable": batch.get("reachable", 0),
           "skipped_cooldown": batch.get("skipped", 0),
           "value": batch.get("value", 0), "reason": batch.get("reason", "")}
    st["runs"] = (st.get("runs") or []) + [run]

    if batch["ok"]:
        # The batch waits for a yes. Stored whole, so approving it sends exactly
        # what was prepared rather than re-running the scan against data that
        # has moved since — the seller approves what they were shown.
        st["pending"] = {"at": st["last_run_at"], "rows": batch["rows"],
                         "reachable": batch.get("reachable", 0),
                         "value": batch.get("value", 0),
                         "skipped_cooldown": batch.get("skipped", 0)}
    else:
        st.pop("pending", None)
    _save_state(email, st)
    return {"skipped": False, **run}


def kick(email: str) -> bool:
    """Catch up a missed run in the background when the seller opens the app.

    The ticker only exists while the process does, and a free or restarted
    instance sleeps through Monday 10am regularly. Never blocks the home
    screen: scanning a year of orders is not something to make someone wait
    for while they are trying to look at their tasks."""
    import threading
    try:
        if not due(email):
            return False
    except Exception:  # noqa: BLE001
        return False
    threading.Thread(target=_safe_run, args=(email,), daemon=True,
                     name=f"winback-{email[:12]}").start()
    return True


def _safe_run(email: str) -> None:
    try:
        run_if_due(email)
    except Exception as e:  # noqa: BLE001
        log.warning("win-back run failed for %s: %s", email, e)


def run_due() -> dict:
    """Every account whose win-back moment has come."""
    from backend.core import auth
    ran = skipped = failed = 0
    for account in (auth.load_users() or {}):
        try:
            res = run_if_due(account)
        except Exception as e:  # noqa: BLE001
            log.warning("win-back failed for %s: %s", account, e)
            failed += 1
            continue
        if res.get("skipped"):
            skipped += 1
        else:
            ran += 1
    return {"ran": ran, "skipped": skipped, "failed": failed,
            "at": datetime.now().isoformat(timespec="seconds")}


# ------------------------------------------------------------------ pending
def pending(email: str) -> dict | None:
    """The batch waiting for approval, if there is one."""
    p = _state(email).get("pending")
    return p if isinstance(p, dict) and p.get("rows") else None


def clear_pending(email: str) -> None:
    st = _state(email)
    st.pop("pending", None)
    _save_state(email, st)


def approve(email: str, channels: tuple[str, ...] = ("email", "whatsapp")) -> dict:
    """Send the waiting batch. This is the only thing that puts a message in
    front of a customer, and it only runs because a person pressed a button."""
    from backend.core import campaigns, sitebuilder

    p = pending(email)
    if not p:
        raise ValueError("There is no win-back campaign waiting.")
    brand = ""
    try:
        brand = (sitebuilder.get_site(email) or {}).get("brand_name") or ""
    except Exception:  # noqa: BLE001
        brand = ""
    res = campaigns.send(email, p["rows"], brand or "our shop", channels=channels)
    clear_pending(email)
    st = _state(email)
    st["last_sent_at"] = _now(email).isoformat(timespec="seconds")
    _save_state(email, st)
    return res


def status(email: str) -> dict:
    cfg = get_config(email)
    st = _state(email)
    now = _now(email)
    nxt = next_trigger(now, cfg["day"], cfg["hour"])
    runs = st.get("runs") or []
    p = pending(email)
    return {
        **cfg,
        "armed_at": st.get("armed_at", ""),
        "next_run": nxt.isoformat(timespec="minutes"),
        "next_run_label": nxt.strftime("%a %d %b, %I:%M %p").replace(" 0", " "),
        "tz_label": localtime.label(email),
        "last_run_at": st.get("last_run_at", ""),
        "last_sent_at": st.get("last_sent_at", ""),
        "pending": ({"at": p["at"], "n": len(p["rows"]),
                     "reachable": p.get("reachable", 0),
                     "value": p.get("value", 0),
                     "skipped_cooldown": p.get("skipped_cooldown", 0)} if p else None),
        "last": runs[-1] if runs else None,
        "history": runs[-5:][::-1],
    }
