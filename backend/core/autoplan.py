"""
Automatic weekly social planning — the Social Media Manager plans next week on
its own, once a week, and hands the seller a short list to approve.

THE FLOW, IN ORDER
------------------
  1. **Trigger.** Once a week on the seller's chosen day (Saturday by default)
     at their chosen hour, India time. `run_due()` is safe to call as often as
     you like — every quarter hour from the in-process scheduler, from a Render
     cron hitting /api/social/autoplan/run, and opportunistically when a seller
     opens the app — because each account's week is planned at most once.
  2. **Occasions.** Festivals whose run-up or day falls in the week (and the
     ones starting soon after), wedding season, the weather season, and salary
     week — the moments people actually shop.
  3. **What is already planned.** Posts already on the calendar for that week
     count against the week's total. Cancelled and skipped posts do not.
  4. **Sales.** Which products are selling (ride the momentum with proof) and
     which are struggling (informational posts are what sell — +0.58 elasticity
     in the research social.py is built on — so a slowing product gets the
     detail and the answer, not a discount).
  5. **Decide.** The week's total is the seller's cadence (2 / 4 / 6 posts) and
     is NEVER exceeded: if 2 of 4 already exist, exactly 2 are added. Days are
     spread across the week's best free days, one post a day, in the arc's
     order (tease → reveal → prove → place → close).
  6. **Studio.** Each post is built from Product Studio: the product's own
     photographs and the brand's aesthetic go into the image prompt (photo
     posts) or the video prompt (reels), and the post lands on the calendar
     as a draft.
  7. **Approval panel.** Drafts appear on Home with Approve / Details / Cancel.
     What Approve does per format lives in main.py's /api/social/approve-ready.

WHY IT ARMS BEFORE IT FIRES
---------------------------
The first time an account is looked at, the planner only records when it was
switched on. The first automatic plan is the next trigger AFTER that moment.
Without this, deploying the feature on a Friday would have planned the rest of
the week for every account at once — posts nobody asked for, with no warning.
"Plan next week now" is there for a seller who does not want to wait.

WHY IT CATCHES UP
-----------------
A free Render instance sleeps. If Saturday 9am passes while it is asleep, the
week still gets planned the next time anything wakes it — as long as the week
being planned has not already finished. Days that have already gone by are
skipped rather than filled with posts dated in the past.
"""
from __future__ import annotations

import logging
import os
import secrets
import threading
import time
from datetime import date, datetime, timedelta

from backend.core import social, user_store

log = logging.getLogger("autoplan")

STATE_KEY = "social_autoplan"
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DEFAULT_DAY = 5          # Saturday
DEFAULT_HOUR = 9         # 9am local

# Reach by weekday, strongest first (Wed, Thu, Mon, Fri, Tue, Sat, Sun), and
# the hour each day's slot goes out — the same table build_week() uses, keyed
# by weekday so a partly-filled week keeps each day's proven hour.
REACH_ORDER = [2, 3, 0, 4, 1, 5, 6]
HOUR_FOR_DAY = {2: 18, 3: 12, 0: 19, 4: 9, 1: 20, 5: 18, 6: 11}

# At most this many posts about one product in a week, when the catalogue has
# enough to go round. Four posts about one kurta reads as a broken feed.
PER_PRODUCT_CAP = 2

# Which beat a slot keeps when the week only has room for some of them. The
# reveal and the "in a real life" beat carry the most sales weight.
BEAT_KEEP_ORDER = ["reveal", "place", "prove", "tease", "close"]
ARC_ORDER = ["tease", "reveal", "prove", "place", "close"]

ACTIVE_STATES = ("draft", "ready", "approved", "scheduled", "published")


# --------------------------------------------------------------- time
def _tz(email: str = ""):
    from backend.core import localtime
    return localtime.tz(email)


def _tz_label(email: str = "") -> str:
    try:
        from backend.core import localtime
        info = localtime.get(email)
        z = localtime.tz(email)
        return (datetime.now(z).tzname() or info["tz"].split("/")[-1]) if z else ""
    except Exception:  # noqa: BLE001
        return ""


def now_local(email: str = "") -> datetime:
    """Naive wall-clock time WHERE THE SELLER IS. Every scheduled_at in the app
    is a naive local time, so the planner has to decide in the same frame — and
    the server is not in that frame (Render runs in UTC). The account's country
    says which zone that is; see backend/core/localtime.py."""
    from backend.core import localtime
    return localtime.now(email)


def next_monday(d: date) -> date:
    """The Monday strictly after `d` — the start of 'next week'."""
    return d + timedelta(days=7 - d.weekday())


def _last_trigger(now: datetime, day: int, hour: int) -> datetime:
    back = (now.weekday() - day) % 7
    t = datetime.combine(now.date() - timedelta(days=back), datetime.min.time()).replace(hour=hour)
    if t > now:
        t -= timedelta(days=7)
    return t


def next_trigger(now: datetime, day: int, hour: int) -> datetime:
    return _last_trigger(now, day, hour) + timedelta(days=7)


# --------------------------------------------------------------- settings
def get_config(email: str) -> dict:
    s = social.get_settings(email)
    day = s.get("auto_plan_day", DEFAULT_DAY)
    hour = s.get("auto_plan_hour", DEFAULT_HOUR)
    try:
        day = int(day) % 7
    except (TypeError, ValueError):
        day = DEFAULT_DAY
    try:
        hour = max(0, min(23, int(hour)))
    except (TypeError, ValueError):
        hour = DEFAULT_HOUR
    return {"enabled": bool(s.get("auto_plan", True)), "day": day, "hour": hour,
            "day_name": DAY_NAMES[day]}


def save_config(email: str, patch: dict) -> dict:
    clean = {}
    if "enabled" in patch:
        clean["auto_plan"] = bool(patch["enabled"])
    if "day" in patch:
        try:
            clean["auto_plan_day"] = int(patch["day"]) % 7
        except (TypeError, ValueError):
            pass
    if "hour" in patch:
        try:
            clean["auto_plan_hour"] = max(0, min(23, int(patch["hour"])))
        except (TypeError, ValueError):
            pass
    social.save_settings(email, clean)
    st = _state(email)
    if clean.get("auto_plan") and not st.get("armed_at"):
        st["armed_at"] = now_local(email).isoformat(timespec="seconds")
        _save_state(email, st)
    return status(email)


def _state(email: str) -> dict:
    st = user_store.get_key((email or "").lower(), STATE_KEY, {}) or {}
    return st if isinstance(st, dict) else {}


def _save_state(email: str, st: dict) -> None:
    st["briefs"] = (st.get("briefs") or [])[-6:]
    user_store.set_key((email or "").lower(), STATE_KEY, st)


def arm(email: str) -> dict:
    """Record when automatic planning started watching this account. The first
    automatic run is the first trigger after this moment — never one before."""
    st = _state(email)
    if not st.get("armed_at"):
        st["armed_at"] = now_local(email).isoformat(timespec="seconds")
        _save_state(email, st)
    return st


def due(email: str, now: datetime | None = None) -> date | None:
    """The week (its Monday) that should be planned now, or None."""
    cfg = get_config(email)
    if not cfg["enabled"]:
        return None
    now = now or now_local(email)
    st = arm(email)
    try:
        armed = datetime.fromisoformat(st["armed_at"])
    except (KeyError, ValueError):
        return None
    last = _last_trigger(now, cfg["day"], cfg["hour"])
    if last < armed:
        return None
    target = next_monday(last.date())
    if st.get("last_target") == target.isoformat():
        return None
    if now.date() > target + timedelta(days=6):
        return None                       # that week is over; wait for the next trigger
    return target


def status(email: str) -> dict:
    cfg = get_config(email)
    st = _state(email)
    now = now_local(email)
    nxt = next_trigger(now, cfg["day"], cfg["hour"])
    armed = st.get("armed_at")
    # If the most recent trigger was missed (and is after arming), it will run
    # at the next wake-up — say so rather than showing next week's date.
    pending = due(email, now) if cfg["enabled"] else None
    briefs = st.get("briefs") or []
    return {
        **cfg,
        "armed_at": armed,
        "next_run": nxt.isoformat(timespec="minutes"),
        "next_run_label": nxt.strftime("%a %d %b, %I:%M %p").replace(" 0", " "),
        # every time on this screen is the seller's own wall clock
        "tz_label": _tz_label(email),
        "next_week": next_monday(nxt.date()).isoformat(),
        "pending_week": pending.isoformat() if pending else "",
        "running": _running(email),
        "last_run_at": st.get("last_run_at") or "",
        "last_target": st.get("last_target") or "",
        "last": briefs[-1] if briefs else None,
    }


# --------------------------------------------------------------- 2. occasions
SEASONS = {
    # Indian climate seasons, with what they change about what people buy.
    "summer": {"months": (3, 4, 5), "label": "Summer",
               "clothing": "breathable cotton and linen, light colours",
               "jewellery": "lightweight pieces that sit well on warm skin",
               "perfume": "fresh, citrus and aquatic notes that hold up in heat"},
    "monsoon": {"months": (6, 7, 8, 9), "label": "Monsoon",
                "clothing": "quick-dry fabrics, colour-fast dyes, easy care",
                "jewellery": "anti-tarnish care and storage in humid weather",
                "perfume": "longer-lasting scents for humid days"},
    "festive": {"months": (10, 11), "label": "Festive season",
                "clothing": "occasion wear, gifting and family events",
                "jewellery": "gifting and occasion pieces",
                "perfume": "gift sets and evening scents"},
    "winter": {"months": (12, 1, 2), "label": "Winter",
               "clothing": "layering, warmer fabrics and deeper colours",
               "jewellery": "statement pieces for weddings and parties",
               "perfume": "warm, woody and amber notes"},
}


def season_for(d: date) -> tuple[str, dict]:
    for key, s in SEASONS.items():
        if d.month in s["months"]:
            return key, s
    return "summer", SEASONS["summer"]


def opportunities(week_start: date, category: str = "") -> list[dict]:
    """Every reason this particular week is a good week to post something
    specific, most important first."""
    week_end = week_start + timedelta(days=6)
    out: list[dict] = []
    for f in social.FESTIVALS_2026:
        if category and f.get("categories") and category not in f["categories"]:
            continue
        d = date.fromisoformat(f["date"])
        start = d - timedelta(days=f.get("lead", 7))
        end = d + timedelta(days=f.get("span", 0))
        if start <= week_end and end >= week_start:
            on_day = week_start <= d <= week_end
            out.append({
                "kind": "festival", "priority": 1, "key": f.get("key", ""),
                "name": f["name"], "date": f["date"],
                "text": (f"{f['name']} is on {d.strftime('%a %d %b')} — this week."
                         if on_day else
                         f"{f['name']} run-up starts {start.strftime('%a %d %b')} "
                         f"({f['name']} on {d.strftime('%d %b')}). The week can lead into it."
                         if start >= week_start else
                         f"{f['name']} run-up is live ({f['name']} on "
                         f"{d.strftime('%d %b')}). People are shopping for it now."),
                "note": f.get("note", ""),
            })
        elif week_end < start <= week_end + timedelta(days=14):
            out.append({
                "kind": "festival_soon", "priority": 2, "key": f.get("key", ""),
                "name": f["name"], "date": f["date"],
                "text": (f"{f['name']} run-up starts {start.strftime('%d %b')}. "
                         f"This week can warm the audience up before it does."),
                "note": f.get("note", ""),
            })
    mid = week_start + timedelta(days=3)
    wed = social.WEDDING_MONTHS.get(mid.month, "low")
    if wed in ("high", "medium") and category in ("clothing", "jewellery", ""):
        out.append({"kind": "wedding", "priority": 3, "name": "Wedding season",
                    "text": f"Wedding demand is {wed} this month — a second driver "
                            f"alongside the festival calendar."})
    skey, s = season_for(mid)
    out.append({"kind": "season", "priority": 4, "name": s["label"], "key": skey,
                "text": f"{s['label']}: " + s.get(category or "clothing", s["clothing"]) + "."})
    days = [week_start + timedelta(days=i) for i in range(7)]
    if any(d.day <= 5 or d.day >= 30 for d in days):
        out.append({"kind": "payday", "priority": 5, "name": "Salary week",
                    "text": "Salary lands this week — the week people have the most to "
                            "spend. A good week for the piece you most want to move."})
    return sorted(out, key=lambda o: o["priority"])


# --------------------------------------------------------------- 3. existing plan
def existing_for_week(email: str, week_start: date) -> list[dict]:
    week_end = week_start + timedelta(days=6)
    out = []
    for p in social._posts(email):
        if p.get("state") not in ACTIVE_STATES:
            continue
        d = (p.get("scheduled_at") or "")[:10]
        try:
            on = date.fromisoformat(d)
        except ValueError:
            continue
        if week_start <= on <= week_end:
            out.append(p)
    return out


# --------------------------------------------------------------- 4. sales
def _norm(s) -> str:
    return " ".join(str(s or "").lower().split())


def sales_signals(email: str, catalogue: list[dict]) -> dict:
    """Which products are doing well and which are struggling.

    Compares the latest four weeks of sales with the four before, anchored on
    the last date IN the data rather than today — an upload that ends last
    month would otherwise make every product look dead."""
    by_name = {_norm(p.get("name")): p for p in catalogue if p.get("name")}
    rows: dict[str, dict] = {}
    anchor = None
    try:
        from backend.core import products as _products
        from backend.core import smart
        import pandas as pd
        txns = smart.load_sales(email)
        if txns is not None and len(txns) and "product" in txns.columns:
            txns = _products.canonicalize_df(email, txns)
            df = txns[["date", "product", "amount"] +
                      (["quantity"] if "quantity" in txns.columns else [])].copy()
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.dropna(subset=["date"])
            if len(df):
                anchor = df["date"].max().normalize()
                recent_from = anchor - pd.Timedelta(days=27)
                prior_from = anchor - pd.Timedelta(days=55)
                df["key"] = df["product"].map(_norm)
                df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
                if "quantity" not in df.columns:
                    df["quantity"] = 1
                df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(1)
                rec = df[df["date"] >= recent_from].groupby("key").agg(
                    rev=("amount", "sum"), units=("quantity", "sum"))
                pri = df[(df["date"] >= prior_from) & (df["date"] < recent_from)].groupby(
                    "key").agg(rev=("amount", "sum"), units=("quantity", "sum"))
                for k in set(rec.index) | set(pri.index):
                    rows[k] = {
                        "rev_recent": float(rec["rev"].get(k, 0.0)),
                        "rev_prior": float(pri["rev"].get(k, 0.0)),
                        "units_recent": float(rec["units"].get(k, 0.0)),
                        "units_prior": float(pri["units"].get(k, 0.0)),
                    }
    except Exception as e:  # noqa: BLE001 — planning never depends on analytics
        log.warning("sales signals unavailable: %s", e)
        rows = {}

    has_data = bool(rows)
    per: dict[str, dict] = {}
    for key, p in by_name.items():
        r = rows.get(key, {"rev_recent": 0.0, "rev_prior": 0.0,
                           "units_recent": 0.0, "units_prior": 0.0})
        growth = ((r["rev_recent"] - r["rev_prior"]) / r["rev_prior"]
                  if r["rev_prior"] > 0 else None)
        per[p.get("id") or key] = {**r, "growth": growth, "name": p.get("name"),
                                   "stock": p.get("stock")}

    winners, strugglers = [], []
    if has_data:
        ranked = sorted(per.items(), key=lambda kv: -kv[1]["rev_recent"])
        top = ranked[0][1]["rev_recent"] if ranked else 0
        for pid, r in ranked:
            if r["rev_recent"] <= 0 or len(winners) >= 3:
                continue
            # A product still selling but falling fast is not a winner, and
            # a long tail of small sellers is not "doing well" either.
            if (r["growth"] is not None and r["growth"] <= -0.3) or r["rev_recent"] < 0.25 * top:
                continue
            rising = r["growth"] is not None and r["growth"] >= 0.25
            winners.append({"id": pid, "name": r["name"], "signal": "winner",
                            "label": "Rising" if rising else "Best seller",
                            "why": (f"Rs {r['rev_recent']:,.0f} in the last 4 weeks"
                                    + (f", up {r['growth'] * 100:.0f}%" if rising else "")
                                    + ".")})
        win_ids = {w["id"] for w in winners}
        for pid, r in per.items():
            if pid in win_ids:
                continue
            stock = r.get("stock") or 0
            if r["rev_prior"] > 0 and r["growth"] is not None and r["growth"] <= -0.3:
                strugglers.append({"id": pid, "name": r["name"], "signal": "struggling",
                                   "label": "Slowing", "score": -r["growth"],
                                   "why": f"Sales down {abs(r['growth']) * 100:.0f}% on "
                                          f"the 4 weeks before."})
            elif r["rev_recent"] <= 0 and stock > 0:
                strugglers.append({"id": pid, "name": r["name"], "signal": "struggling",
                                   "label": "Not selling", "score": 1 + stock / 1000,
                                   "why": f"No sales in the last 4 weeks, {stock} in stock."})
        strugglers.sort(key=lambda s: -s["score"])
        strugglers = strugglers[:3]
    else:
        # No sales data yet: the honest proxy is stock. The products holding
        # the most stock are the ones the seller most needs people to see.
        stocked = sorted([(pid, r) for pid, r in per.items() if (r.get("stock") or 0) > 0],
                         key=lambda kv: -(kv[1].get("stock") or 0))
        for pid, r in stocked[:2]:
            strugglers.append({"id": pid, "name": r["name"], "signal": "struggling",
                               "label": "Most stock", "score": r.get("stock") or 0,
                               "why": f"{r.get('stock')} in stock — no sales data yet, "
                                      f"so this is the piece to put in front of people."})
    return {"has_data": has_data, "anchor": anchor.date().isoformat() if anchor is not None else "",
            "winners": winners, "strugglers": strugglers, "per_product": per}


# --------------------------------------------------------------- 5. decide
def pick_days(week_start: date, need: int, taken: set[date],
              now: datetime) -> list[datetime]:
    """The best free days of the week, one post a day, never in the past."""
    days = []
    for wd in REACH_ORDER:
        d = week_start + timedelta(days=wd)
        when = datetime.combine(d, datetime.min.time()).replace(hour=HOUR_FOR_DAY[wd])
        if when <= now:
            continue
        days.append((d in taken, REACH_ORDER.index(wd), when))
    # Free days first (a day that already has a post is only used when the week
    # has no free day left), strongest reach first within each group.
    days.sort(key=lambda t: (t[0], t[1]))
    return sorted(t[2] for t in days[:need])


def choose_beats(cadence: str, need: int, existing: list[dict], occasion: dict | None,
                 rotation: int, shootable: list[str]) -> list[dict]:
    """The arc slots still missing from the week, in arc order."""
    shape = social.slate_shape(cadence, occasion, rotation=rotation, shootable=shootable)
    have = [p.get("beat") for p in existing if p.get("beat")]
    remaining = []
    for slot in shape:
        if slot["beat"] in have:
            have.remove(slot["beat"])
            continue
        remaining.append(slot)
    if len(remaining) > need:
        keep_rank = {b: i for i, b in enumerate(BEAT_KEEP_ORDER)}
        order = sorted(range(len(remaining)),
                       key=lambda i: (keep_rank.get(remaining[i]["beat"], 9), i))
        keep = sorted(order[:need])
        remaining = [remaining[i] for i in keep]
    while len(remaining) < need:          # existing posts had no beats; top up
        extra = shape[len(remaining) % len(shape)]
        remaining.append(dict(extra))
    remaining.sort(key=lambda s: ARC_ORDER.index(s["beat"]) if s["beat"] in ARC_ORDER else 9)
    return remaining


def _festival_tagged(p: dict, occasion: dict | None) -> bool:
    if not occasion:
        return False
    tag = (occasion.get("name") or "").split()[0].lower()
    hay = " ".join(str(x).lower() for x in (p.get("festival_tags") or []))
    return bool(tag) and (tag in hay or tag in str(p.get("category") or "").lower()
                          or tag in str(p.get("name") or "").lower())


def assign_products(slots: list[dict], catalogue: list[dict], signals: dict,
                    existing: list[dict], occasions: list[dict | None]) -> list[tuple[dict, dict]]:
    """(product, reason) for each slot.

    Winners get the beats that PROVE — a real person using it, someone else
    already bought it — because momentum is easiest to extend. Strugglers get
    the beats that INFORM — the reveal, the one detail, the question people
    actually have — because informational content is what moves a sale that
    is not happening. A live festival's closing beat goes to a product tagged
    for it. Nobody gets more than two posts in the week while the catalogue
    has enough to go round."""
    by_id = {p.get("id"): p for p in catalogue}
    winners = [by_id[w["id"]] for w in signals.get("winners", []) if w["id"] in by_id]
    strugglers = [by_id[s["id"]] for s in signals.get("strugglers", []) if s["id"] in by_id]
    sig_for = {w["id"]: w for w in signals.get("winners", [])}
    sig_for.update({s["id"]: s for s in signals.get("strugglers", [])})

    counts: dict[str, int] = {}
    for p in existing:
        pid = p.get("product_id") or p.get("product_name")
        counts[pid] = counts.get(pid, 0) + 1
    cap = PER_PRODUCT_CAP if len(catalogue) * PER_PRODUCT_CAP >= len(slots) + len(existing) else 99

    out = []
    prev_id, prev_beat, prev_info = None, None, None
    for slot, occ in zip(slots, occasions):
        beat = slot["beat"]
        # A tease withholds a product and the reveal shows it: the same piece,
        # or the week's opening makes no sense.
        if beat == "reveal" and prev_beat == "tease" and prev_id in by_id \
                and counts.get(prev_id, 0) < max(cap, 2):
            chosen = by_id[prev_id]
            counts[prev_id] = counts.get(prev_id, 0) + 1
            prev_beat = beat
            out.append((chosen, {**prev_info,
                                 "reason": ("Shows what the tease held back. "
                                            + prev_info.get("base", "")).strip()}))
            continue
        prefs: list[tuple[dict, str]] = []
        if beat == "close" and occ:
            prefs += [(p, "festival") for p in catalogue if _festival_tagged(p, occ)]
        if beat in ("place", "close"):
            prefs += [(p, "winner") for p in winners]
            prefs += [(p, "struggling") for p in strugglers]
        else:                                   # tease, reveal, prove
            prefs += [(p, "struggling") for p in strugglers]
            prefs += [(p, "winner") for p in winners]
        if occ:
            prefs += [(p, "festival") for p in catalogue if _festival_tagged(p, occ)]
        prefs += [(p, "steady") for p in sorted(
            catalogue, key=lambda p: counts.get(p.get("id"), 0))]

        chosen, why = None, "steady"
        for p, kind in prefs:
            pid = p.get("id")
            if counts.get(pid, 0) >= cap:
                continue
            if pid == prev_id and len(catalogue) > 1:
                continue                         # no same piece on back-to-back days
            chosen, why = p, kind
            break
        if chosen is None:
            chosen, why = min(catalogue, key=lambda p: counts.get(p.get("id"), 0)), "steady"
        pid = chosen.get("id")
        counts[pid] = counts.get(pid, 0) + 1
        prev_id, prev_beat = pid, beat
        sig = sig_for.get(pid) or {}
        label = slot["archetype_label"]
        base = f"{sig['label']}: {sig['why']}" if sig else ""
        if why == "festival" and occ:
            reason = f"Tagged for {occ['name']}, and the run-up is live."
        elif why == "winner" and sig:
            reason = base + (" Leading with a best seller opens the week strong."
                             if beat in ("tease", "reveal")
                             else f" A '{label}' post rides that momentum.")
        elif why == "struggling" and sig:
            reason = base + {
                "tease": " Opening the week on it puts it back in front of people.",
                "reveal": " Showing it properly is the first job.",
                "prove": f" A '{label}' post answers what stops people buying.",
            }.get(beat, f" A '{label}' post helps people picture owning it.")
        else:
            reason = f"Keeps {chosen.get('name')} in rotation so the week is not one product."
        prev_info = {"signal": why, "reason": reason, "base": base,
                     "signal_label": sig.get("label", "")}
        out.append((chosen, dict(prev_info)))
    return out


# --------------------------------------------------------------- 6. studio
def _reference_photo(email: str, product: dict) -> str:
    try:
        from backend.core import studio
        mat = studio.get_material(email, product.get("id") or "")
        for u in (mat.get("shots") or []):
            if u:
                return u
    except Exception:  # noqa: BLE001
        pass
    return product.get("image_url") or next((u for u in (product.get("images") or []) if u), "")


def _angle_for(slot: dict, info: dict, occasion: dict | None, season: dict) -> str:
    angle = slot["job"]
    if info["signal"] == "winner":
        angle += " This is one of our best sellers right now — say so plainly, as a fact."
    elif info["signal"] == "struggling":
        angle += (" Lead with the concrete detail a buyer needs — material, fit, care — "
                  "the thing that removes their doubt. No discount.")
    if not occasion and season:
        angle += f" Season: {season.get('label', '')}."
    return angle


def _full_catalogue(email: str) -> list[dict]:
    from backend.core import products
    out = []
    for p in products.listed_products(email):
        out.append({k: p.get(k) for k in ("id", "name", "price", "description", "category",
                                          "stock", "image_url", "images", "festival_tags")})
    return [p for p in out if p.get("name")]


def plan_week(email: str, week_start: date | None = None, trigger: str = "manual",
              now: datetime | None = None, catalogue: list[dict] | None = None) -> dict:
    """Plan one week (Monday `week_start`). Returns the brief shown to the
    seller: what was found, what already existed, what was added and why."""
    now = now or now_local(email)
    week_start = week_start or next_monday(now.date())
    week_end = week_start + timedelta(days=6)
    s = social.get_settings(email)
    category = s.get("category") or ""
    cadence = s.get("cadence") or "standard"
    target = social.CADENCE.get(cadence, social.CADENCE["standard"])["posts"]
    catalogue = catalogue if catalogue is not None else _full_catalogue(email)

    brief = {"week_start": week_start.isoformat(), "week_end": week_end.isoformat(),
             "week_label": f"{week_start.strftime('%d %b')} – {week_end.strftime('%d %b')}",
             "trigger": trigger, "ran_at": now.isoformat(timespec="seconds"),
             "target": target, "cadence": cadence, "existing": 0, "added": 0,
             "posts": [], "opportunities": [], "winners": [], "strugglers": [],
             "sales_data": False, "note": ""}

    brief["opportunities"] = opportunities(week_start, category)
    existing = existing_for_week(email, week_start)
    brief["existing"] = len(existing)
    need = max(0, target - len(existing))
    if not catalogue:
        brief["note"] = "No products listed yet — add one and planning starts next week."
        return _finish(email, brief, week_start)
    signals = sales_signals(email, catalogue)
    brief.update(sales_data=signals["has_data"], sales_anchor=signals["anchor"],
                 winners=signals["winners"], strugglers=signals["strugglers"])
    if need == 0:
        brief["note"] = (f"Next week already has {len(existing)} post"
                         f"{'' if len(existing) == 1 else 's'} planned — your "
                         f"{social.CADENCE[cadence]['label'].lower()} week is "
                         f"{target}, so nothing was added.")
        return _finish(email, brief, week_start)

    taken = set()
    for p in existing:
        try:
            taken.add(date.fromisoformat((p.get("scheduled_at") or "")[:10]))
        except ValueError:
            pass
    times = pick_days(week_start, need, taken, now)
    if len(times) < need:
        brief["note"] = (f"Only {len(times)} day{'' if len(times) == 1 else 's'} of that "
                         f"week {'is' if len(times) == 1 else 'are'} still ahead, so "
                         f"only {len(times)} post{'' if len(times) == 1 else 's'} "
                         f"{'was' if len(times) == 1 else 'were'} added.")
        need = len(times)
    if need == 0:
        return _finish(email, brief, week_start)

    lead_occ = social.occasion_for(week_start + timedelta(days=3), category)
    try:
        from backend.core import studio
        shootable = studio.shootable_shot_types(email)
    except Exception:  # noqa: BLE001
        shootable = []
    slots = choose_beats(cadence, need, existing, lead_occ,
                         rotation=week_start.isocalendar()[1], shootable=shootable)
    occasions = [social.occasion_for(t.date(), category) for t in times]
    picks = assign_products(slots, catalogue, signals, existing, occasions)
    season_key, season = season_for(week_start + timedelta(days=3))

    # The week's story is about whichever product opens it.
    theme = social.week_theme(picks[0][0], lead_occ)
    rows = social._posts(email)
    made = []
    prev = None
    for slot, when, occ, (product, info) in zip(slots, times, occasions, picks):
        story = social._story_context(theme, slot, prev)
        angle = _angle_for(slot, info, occ, season)
        cap = social.write_caption(email, product, slot["pillar"], angle=angle,
                                   occasion=occ, story=story, slot=slot)
        script = None
        image_prompt, prompt_sources = "", []
        if slot["format"] == "reel":
            script = social.write_reel_script(email, product, slot["pillar"], angle=angle,
                                              occasion=occ, story=story,
                                              shot_type=slot["shot_type"],
                                              theme=theme["note"])
        else:
            # Product Studio builds the picture's instruction now, from the
            # product's own photographs and the brand's aesthetic, so the
            # seller can read exactly what will be drawn before approving.
            # The picture itself is only made on Approve — generating it here
            # would spend the day's allowance on posts they may cancel.
            try:
                from backend.core import studio
                pv = studio.preview_prompt(email, product.get("id") or "", slot["pillar"],
                                           slot["format"], angle, use_reference=True,
                                           occasion_key=(occ or {}).get("key", ""),
                                           shot_type=slot["shot_type"])
                image_prompt, prompt_sources = pv.get("prompt", ""), pv.get("sources", [])
            except Exception as e:  # noqa: BLE001 — the post is still worth planning
                log.info("prompt preview failed for %s: %s", product.get("name"), e)
        post = {
            "id": secrets.token_hex(6),
            "created_at": social._now(),
            "product_id": product.get("id") or "",
            "product_name": product.get("name") or "",
            "pillar": slot["pillar"],
            "pillar_name": social.PILLAR_BY_ID[slot["pillar"]]["name"],
            "format": slot["format"],
            "beat": slot["beat"], "beat_job": slot["beat_job"],
            "archetype": slot["archetype"], "archetype_label": slot["archetype_label"],
            "shot_type": slot["shot_type"], "earns": slot["earns"],
            "theme": theme["name"], "theme_note": theme["note"],
            "occasion": (occ or {}).get("name", ""),
            "occasion_days": (occ or {}).get("days_away"),
            "occasion_key": (occ or {}).get("key", ""),
            "caption": cap, "text": social.assemble(cap),
            "checks": social.caption_check(cap, s),
            "script": script,
            "scheduled_at": when.isoformat(timespec="minutes"),
            "state": "draft",
            "provider": cap.get("provider", "template"),
            "image_url": "", "image_generated": False,
            "image_prompt": image_prompt, "prompt_sources": prompt_sources,
            "reference_photo": _reference_photo(email, product),
            "video_url": "", "metrics": {},
            # Where this post came from and why it is this product.
            "source": "autoplan", "autoplan_week": week_start.isoformat(),
            "signal": info["signal"], "signal_label": info.get("signal_label", ""),
            "plan_reason": info["reason"],
        }
        made.append(post)
        rows.append(post)
        prev = slot
    social._save_posts(email, rows)
    brief["added"] = len(made)
    brief["posts"] = [{"id": p["id"], "product_name": p["product_name"],
                       "format": p["format"], "scheduled_at": p["scheduled_at"],
                       "signal": p["signal"], "plan_reason": p["plan_reason"],
                       "occasion": p["occasion"]} for p in made]
    if not brief["note"]:
        brief["note"] = (f"Added {len(made)} post{'' if len(made) == 1 else 's'}"
                         + (f" to the {len(existing)} already planned" if existing else "")
                         + f" — {target} for the week, as your cadence says.")
    return _finish(email, brief, week_start)


def _finish(email: str, brief: dict, week_start: date) -> dict:
    st = _state(email)
    st["last_target"] = week_start.isoformat()
    st["last_run_at"] = brief["ran_at"]
    st.setdefault("armed_at", brief["ran_at"])
    briefs = [b for b in (st.get("briefs") or []) if b.get("week_start") != brief["week_start"]]
    briefs.append(brief)
    st["briefs"] = briefs
    _save_state(email, st)
    try:
        from backend.core import cache
        cache.clear(email)
    except Exception:  # noqa: BLE001
        pass
    return brief


def latest_brief(email: str, week: str = "") -> dict | None:
    briefs = _state(email).get("briefs") or []
    if week:
        return next((b for b in reversed(briefs) if b.get("week_start") == week), None)
    return briefs[-1] if briefs else None


def cancel_week(email: str, week: str) -> int:
    """Cancel every undecided auto-planned post for that week."""
    rows = social._posts(email)
    n = 0
    for p in rows:
        if p.get("source") == "autoplan" and p.get("autoplan_week") == week \
                and p.get("state") == "draft":
            p["state"] = "cancelled"
            p["state_at"] = social._now()
            n += 1
    social._save_posts(email, rows)
    return n


# --------------------------------------------------------------- running it
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()
_RUNNING: dict[str, float] = {}


def _lock(email: str) -> threading.Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(email, threading.Lock())


def _running(email: str) -> bool:
    t = _RUNNING.get((email or "").lower())
    return bool(t and time.time() - t < 900)


def run_for(email: str, week_start: date | None = None, trigger: str = "manual") -> dict:
    """Plan one account's week, one run at a time per account."""
    email = (email or "").lower()
    lk = _lock(email)
    if not lk.acquire(blocking=False):
        return {"skipped": True, "reason": "a plan is already being made for this account"}
    _RUNNING[email] = time.time()
    try:
        return plan_week(email, week_start, trigger)
    finally:
        _RUNNING.pop(email, None)
        lk.release()


def run_if_due(email: str) -> dict | None:
    target = due(email)
    if not target:
        return None
    return run_for(email, target, trigger="schedule")


def kick(email: str) -> bool:
    """Start a due plan in the background and return at once — used when a
    seller opens the app, so a missed Saturday catches up without making the
    home screen wait for a dozen caption calls."""
    try:
        if not due(email) or _running(email):
            return False
    except Exception:  # noqa: BLE001
        return False
    t = threading.Thread(target=_safe_run_if_due, args=(email,), daemon=True,
                         name=f"autoplan-{email[:12]}")
    t.start()
    return True


def _safe_run_if_due(email: str) -> None:
    try:
        run_if_due(email)
    except Exception as e:  # noqa: BLE001
        log.warning("autoplan failed for %s: %s", email, e)


def run_due() -> dict:
    """Every account whose planning moment has come. Safe to call often."""
    from backend.core import auth
    ran, skipped, failed = 0, 0, 0
    for account in (auth.load_users() or {}):
        try:
            res = run_if_due(account)
        except Exception as e:  # noqa: BLE001
            log.warning("autoplan failed for %s: %s", account, e)
            failed += 1
            continue
        if res and not res.get("skipped"):
            ran += 1
        else:
            skipped += 1
    return {"ran": ran, "skipped": skipped, "failed": failed,
            "at": now_local(email).isoformat(timespec="seconds")}


# --------------------------------------------------------------- in-process scheduler
_SCHED_STARTED = False
_SCHED_GUARD = threading.Lock()
TICK_SECONDS = 15 * 60


def ensure_scheduler() -> bool:
    """Start the background ticker once per process. Off with
    AUTOPLAN_SCHEDULER=off (tests, or when a Render cron job does it instead)."""
    global _SCHED_STARTED
    if _SCHED_STARTED or os.environ.get("AUTOPLAN_SCHEDULER", "on").lower() in ("off", "0", "false"):
        return False
    with _SCHED_GUARD:
        if _SCHED_STARTED:
            return False
        _SCHED_STARTED = True
    threading.Thread(target=_loop, daemon=True, name="autoplan-scheduler").start()
    return True


def _loop() -> None:
    time.sleep(60)                     # let the app finish booting first
    while True:
        try:
            run_due()
        except Exception as e:  # noqa: BLE001
            log.warning("autoplan tick failed: %s", e)
        time.sleep(TICK_SECONDS)
