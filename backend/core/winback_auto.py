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

# EVERY SECOND MONDAY, not every Monday. A shop's customers hearing from it
# weekly is a newsletter; fortnightly is a shop that remembers them. Each run
# is a FESTIVAL campaign when a festival starts within FESTIVAL_HORIZON days
# and has not had one yet, and a win-back campaign otherwise.
EVERY_WEEKS = 2
FESTIVAL_HORIZON = 21
DEFAULT_OFFER = {"kind": "percent", "value": 10.0, "min_order": 0.0}


def _offer(raw) -> dict:
    from backend.core import discounts
    try:
        return discounts.clean_offer(raw) if raw else dict(DEFAULT_OFFER)
    except discounts.DiscountError:
        return dict(DEFAULT_OFFER)


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
            "day_name": DAY_NAMES[day], "cooldown_days": COOLDOWN_DAYS,
            "every_weeks": EVERY_WEEKS, "offer": _offer(s.get("offer"))}


def save_config(email: str, patch: dict) -> dict:
    cur = get_config(email)
    clean = {"enabled": cur["enabled"], "day": cur["day"], "hour": cur["hour"],
             "offer": cur["offer"]}
    if patch.get("offer") is not None:
        from backend.core import discounts
        clean["offer"] = discounts.clean_offer(patch["offer"])   # raises with a reason
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


def next_trigger(now: datetime, day: int, hour: int, last_run: str = "") -> datetime:
    nxt = _last_trigger(now, day, hour) + timedelta(days=7)
    prev = _parse_stamp(last_run)
    while prev and nxt - prev < timedelta(days=7 * EVERY_WEEKS - 1):
        nxt += timedelta(days=7)
    return nxt


def _parse_stamp(v) -> datetime | None:
    try:
        return datetime.fromisoformat(str(v)) if v else None
    except ValueError:
        return None


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
    # Every second week: the trigger a week after the last run is skipped.
    prev = _parse_stamp(st.get("last_trigger"))
    if prev and last - prev < timedelta(days=7 * EVERY_WEEKS - 1):
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
def choose_reason(email: str) -> tuple[str, str]:
    """('festival', name) when a festival is coming that has not had its
    campaign yet, else ('winback', '')."""
    from backend.core import campaign_engine
    fest = campaign_engine.upcoming_occasion(email, horizon=FESTIVAL_HORIZON)
    done = set(_state(email).get("festivals_done") or [])
    if fest and fest.get("name") and fest["name"] not in done:
        return "festival", fest["name"]
    return "winback", ""


def prepare(email: str, reason: str = "", occasion: str = "") -> dict:
    """Build this run's campaign as a draft (campaign_engine). Never sends."""
    from backend.core import campaign_engine
    if not reason:
        reason, occasion = choose_reason(email)
    cfg = get_config(email)
    try:
        draft = campaign_engine.build(email, reason, cfg["offer"], occasion=occasion,
                                      trigger="auto", limit=MAX_BATCH)
    except campaign_engine.CampaignError as e:
        if reason == "festival":
            # nobody to reach for the festival is no reason to skip win-back
            return prepare(email, "winback", "")
        return {"ok": False, "reason": str(e), "n": 0}
    c = draft["counts"]
    reachable = c["audience"] - c["unreachable"]
    why = ""
    if c["audience"] < MIN_BATCH:
        why = f"only {c['audience']} to reach, not worth a campaign yet"
    elif not reachable:
        why = "none of them have an email or phone on file"
    if why:
        campaign_engine.discard(email, draft["id"])
        return {"ok": False, "reason": why, "n": c["audience"]}
    return {"ok": True, "draft_id": draft["id"], "reason_kind": draft["reason"],
            "occasion": draft.get("occasion") or "", "n": c["audience"],
            "reachable": reachable, "value": c["value"],
            "skipped": draft.get("held_back", 0), "reason": ""}


def run_if_due(email: str, now: datetime | None = None, trigger: str = "auto") -> dict:
    """Prepare this fortnight's campaign if its moment has come. Safe to call
    as often as you like: a no-op every time but once every second week."""
    stamp = due(email, now) if trigger == "auto" else _now(email).isoformat(timespec="hours")
    if trigger == "auto" and not stamp:
        return {"skipped": True, "reason": "not due"}

    batch = prepare(email)
    st = _state(email)
    old = (st.get("pending") or {}).get("draft_id")
    if old and old != batch.get("draft_id"):
        from backend.core import campaign_engine
        campaign_engine.discard(email, old)       # a fresh run replaces the old card
    st["last_trigger"] = stamp
    st["last_run_at"] = _now(email).isoformat(timespec="seconds")
    run = {"at": st["last_run_at"], "trigger": trigger, "ok": batch["ok"],
           "n": batch.get("n", 0), "reachable": batch.get("reachable", 0),
           "skipped_cooldown": batch.get("skipped", 0),
           "value": batch.get("value", 0), "reason": batch.get("reason", ""),
           "kind": batch.get("reason_kind", ""), "occasion": batch.get("occasion", "")}
    st["runs"] = (st.get("runs") or []) + [run]
    if batch["ok"]:
        # The campaign waits for a yes. Stored as a draft, so approving it sends
        # exactly what was prepared rather than re-running the scan against
        # data that has moved since: the seller approves what they were shown.
        st["pending"] = {"at": st["last_run_at"], "draft_id": batch["draft_id"],
                         "kind": batch["reason_kind"], "occasion": batch["occasion"],
                         "reachable": batch["reachable"], "value": batch["value"],
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
        with user_store.job_scope():
            run_if_due(email)
    except Exception as e:  # noqa: BLE001
        log.warning("win-back run failed for %s: %s", email, e)


def run_due() -> dict:
    """Every account whose win-back moment has come."""
    from backend.core import auth
    ran = skipped = failed = 0
    from backend.core import billing
    for account in (auth.load_users() or {}):
        try:
            if billing.is_locked(account):   # trial over, nothing paid
                skipped += 1
                continue
            with user_store.job_scope():
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
    """The campaign waiting for approval, if there is one (with its rows)."""
    p = _state(email).get("pending")
    if not isinstance(p, dict) or not p.get("draft_id"):
        return None
    from backend.core import campaign_engine
    d = campaign_engine.get_draft(email, p["draft_id"])
    if not d or d.get("state") != "draft" or not d.get("rows"):
        return None
    return {**p, "rows": d["rows"], "n": len(d["rows"])}


def clear_pending(email: str) -> None:
    st = _state(email)
    p = st.pop("pending", None)
    _save_state(email, st)
    if isinstance(p, dict) and p.get("draft_id"):
        from backend.core import campaign_engine
        campaign_engine.discard(email, p["draft_id"])


def approve(email: str, channels: tuple[str, ...] = ("whatsapp", "email")) -> dict:
    """Send the waiting campaign. This is the only thing that puts a message in
    front of a customer, and it only runs because a person pressed a button."""
    from backend.core import campaign_engine
    p = pending(email)
    if not p:
        raise ValueError("There is no campaign waiting.")
    res = campaign_engine.send(email, p["draft_id"], channels=channels)
    st = _state(email)
    st.pop("pending", None)
    st["last_sent_at"] = _now(email).isoformat(timespec="seconds")
    if p.get("kind") == "festival" and p.get("occasion"):
        st["festivals_done"] = ((st.get("festivals_done") or []) + [p["occasion"]])[-12:]
    _save_state(email, st)
    return res


def status(email: str) -> dict:
    cfg = get_config(email)
    st = _state(email)
    now = _now(email)
    nxt = next_trigger(now, cfg["day"], cfg["hour"], st.get("last_trigger") or "")
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
                     "draft_id": p.get("draft_id") or "",
                     "kind": p.get("kind") or "winback",
                     "occasion": p.get("occasion") or "",
                     "reachable": p.get("reachable", 0),
                     "value": p.get("value", 0),
                     "skipped_cooldown": p.get("skipped_cooldown", 0)} if p else None),
        "last": runs[-1] if runs else None,
        "history": runs[-5:][::-1],
    }
