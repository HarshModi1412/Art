"""A hard ceiling on what one account can spend of our money in a day.

WHY THIS EXISTS, AND WHY IT IS NOT THE BILLING CODE
---------------------------------------------------
billing.py answers "is this seller entitled to this feature?" and, with
LAUNCH_MODE on, the answer is always yes — deliberately, because everything is
free during launch. That is a fine answer for a feature flag and a dangerous one
for a feature that spends real money per call.

The arithmetic: a ChatGPT image is about ₹3.70, a Veo clip about ₹105. A normal
seller planning four posts a week costs roughly ₹60 a month, comfortably inside
₹999 Pro. One seller who discovers the video button and enjoys it costs more than
their subscription in an afternoon, and there is no ceiling anywhere to stop
them. A flat price with an unmetered variable cost behind it is not a pricing
mistake, it is an unbounded liability.

So this is a separate, blunter mechanism that sits UNDERNEATH billing and applies
to everyone, on every plan, in launch mode or out of it. It is not a paywall and
it must never read like one — the seller has done nothing wrong, they have used a
lot of an expensive thing today, and tomorrow it resets. The message says exactly
that, tells them what is left, and points at the free route (their own photo,
their own phone camera, Google Flow) rather than at an upgrade page.

Two design choices worth keeping:

  * The counter is per calendar day in IST, not a rolling 24-hour window. A
    rolling window means a seller who hits the cap at 4pm is confused about when
    it lifts; "tomorrow" is a thing everyone already understands.
  * Video and images have separate budgets. They differ 30x in price, so one
    shared number would either be too tight for images or far too loose for
    video.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from backend.core import user_store

KEY = "ai_daily_usage"
# The monthly image allowance is a SEPARATE product limit that sits on top of the
# daily spend guard above. The daily cap answers "is one account spending a
# runaway amount of our money today"; this answers "how many pictures does a
# plan include this month". A seller meets this one long before the daily cap —
# 30 a month is about one a day — so it is the number the UI tracks, and the one
# whose message points at uploading a photo rather than at coming back tomorrow.
MONTH_KEY = "image_monthly_usage"
IST = timezone(timedelta(hours=5, minutes=30))

# What one call of each kind costs us, in rupees, roughly, as of September 2026.
# Used only to explain the cap to a human — never to bill anyone.
UNIT_COST_INR = {"image": 3.7, "video": 105.0, "text": 0.2, "vision": 0.2}

# Defaults chosen so a real seller never notices, and a runaway account is capped
# at roughly the price of a Pro subscription per day rather than per hour.
# Overridable per deployment because the right number depends on the plan mix.
def _cap(kind: str) -> int:
    env = {
        "image": ("AI_CAP_IMAGES_PER_DAY", 40),
        "video": ("AI_CAP_VIDEOS_PER_DAY", 3),
        "text": ("AI_CAP_TEXT_PER_DAY", 300),
        "vision": ("AI_CAP_VISION_PER_DAY", 60),
    }.get(kind)
    if not env:
        return 0
    name, default = env
    try:
        return max(0, int(os.environ.get(name) or default))
    except ValueError:
        return default


def _today() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d")


def _month() -> str:
    # Calendar month in IST, so "resets on the 1st" means the same thing to a
    # seller in Surat as the counter does on the server. A rolling 30 days would
    # be a fairer budget and a worse promise: nobody can say when it lifts.
    return datetime.now(IST).strftime("%Y-%m")


def _month_cap() -> int:
    """Pictures one account may generate in a calendar month. 30 by default —
    about one a day — overridable per deployment with AI_IMAGES_PER_MONTH. 0
    turns the monthly limit off entirely (the daily spend guard still applies)."""
    try:
        return max(0, int(os.environ.get("AI_IMAGES_PER_MONTH") or 30))
    except ValueError:
        return 30


def _load(email: str) -> dict:
    raw = user_store.get_key(email, KEY, {}) or {}
    if not isinstance(raw, dict) or raw.get("day") != _today():
        # A new day wipes yesterday rather than accumulating history. This is a
        # budget guard, not an analytics store.
        return {"day": _today(), "counts": {}}
    raw.setdefault("counts", {})
    return raw


def used(email: str, kind: str) -> int:
    return int((_load(email).get("counts") or {}).get(kind) or 0)


def remaining(email: str, kind: str) -> int:
    return max(0, _cap(kind) - used(email, kind))


def status(email: str) -> dict:
    """What the UI shows next to a generate button, so nobody is surprised."""
    st = _load(email)
    counts = st.get("counts") or {}
    return {
        "day": st["day"],
        "kinds": {k: {"used": int(counts.get(k) or 0), "cap": _cap(k),
                      "left": max(0, _cap(k) - int(counts.get(k) or 0))}
                  for k in ("image", "video", "text", "vision")},
        "resets": "tomorrow morning",
        # The monthly image allowance, carried alongside the daily counts so the
        # one /api/studio/ai-usage call the UI already makes gets both at once.
        "month": image_month_status(email),
    }


# ---------------------------------------------------------------------------
# The monthly image allowance (the product limit the seller actually watches)
# ---------------------------------------------------------------------------
def _load_month(email: str) -> dict:
    raw = user_store.get_key(email, MONTH_KEY, {}) or {}
    if not isinstance(raw, dict) or raw.get("month") != _month():
        # A new month starts the count at zero. Like the daily guard this is a
        # budget, not a history, so last month is not carried forward.
        return {"month": _month(), "used": 0}
    raw.setdefault("used", 0)
    return raw


def image_month_used(email: str) -> int:
    return int(_load_month(email).get("used") or 0)


def image_month_left(email: str) -> int:
    cap = _month_cap()
    return max(0, cap - image_month_used(email)) if cap else 0


def image_month_status(email: str) -> dict:
    """What the Social Media Manager's picture tracker shows: how many of the
    month's images are used, how many remain, and when it resets."""
    cap = _month_cap()
    used_now = image_month_used(email)
    return {
        "month": _month(),
        "used": used_now,
        "cap": cap,
        "left": max(0, cap - used_now) if cap else 0,
        # A calendar-month reset, said the way a person would.
        "resets": "on the 1st",
        # No cap configured means no monthly limit — the UI hides the tracker.
        "enabled": bool(cap),
    }


class CapReached(RuntimeError):
    """Not a paywall. The seller has done nothing wrong."""


class MonthlyImageCapReached(CapReached):
    """The month's picture allowance is used up.

    A subclass of CapReached on purpose: every place that already handles the
    daily cap — the 429 handler, and the routes that turn a cap into an "upload
    your own photo" task — catches it unchanged. Callers that want to tell the
    two apart (a different message, a different HTTP code) check the type."""


def _message(kind: str, cap: int) -> str:
    if kind == "video":
        return (f"That is {cap} clip{'s' if cap != 1 else ''} today, which is the "
                f"daily limit — clips are by far the most expensive thing here, so "
                f"there is a ceiling on them. It lifts tomorrow morning. In the "
                f"meantime you can film one on your phone, or make one free in "
                f"Google Flow and upload it — the button is right there on the post.")
    if kind == "image":
        return (f"That is {cap} pictures today, which is the daily limit. It lifts "
                f"tomorrow morning. Your own photographs still work as they always "
                f"do, and they usually look better anyway.")
    return (f"That is {cap} AI runs today, which is the daily limit. It lifts "
            f"tomorrow morning — nothing else in the app is affected.")


def check(email: str, kind: str) -> None:
    """Raise CapReached if this call would go over. Call BEFORE spending."""
    cap = _cap(kind)
    if cap and used(email, kind) >= cap:
        raise CapReached(_message(kind, cap))


def _month_message(cap: int) -> str:
    return (f"That is all {cap} AI pictures for this month — the monthly picture "
            f"allowance. It resets on the 1st. Until then you can add your own "
            f"photo to a post (a real photo of the real product usually looks "
            f"better anyway), and we will still write the caption. Approving a "
            f"post now puts it on your task list with the shot we would have made, "
            f"so you know what to take a picture of.")


def check_image_month(email: str) -> None:
    """Raise MonthlyImageCapReached if this account has used its month's pictures.

    Call BEFORE spending, alongside check(email, "image"). Kept separate from the
    daily guard because the two mean different things to the seller and read
    differently: one lifts tomorrow, the other on the 1st, and only this one
    sends them to the upload route instead."""
    cap = _month_cap()
    if cap and image_month_used(email) >= cap:
        raise MonthlyImageCapReached(_month_message(cap))


def consume_image_month(email: str, n: int = 1) -> dict:
    """Record pictures that were actually generated this month.

    Called AFTER the image succeeds, for the same reason the daily counter is:
    a failed generation cost the seller's allowance nothing."""
    st = _load_month(email)
    st["used"] = int(st.get("used") or 0) + max(1, n)
    user_store.set_key(email, MONTH_KEY, st)
    return image_month_status(email)


def consume(email: str, kind: str, n: int = 1) -> dict:
    """Record a call that actually happened.

    Called AFTER the generation succeeds, on purpose: a failed call cost us
    nothing on most providers, and charging a seller's daily budget for our own
    failure is the kind of small unfairness that gets noticed.
    """
    st = _load(email)
    counts = st.setdefault("counts", {})
    counts[kind] = int(counts.get(kind) or 0) + max(1, n)
    user_store.set_key(email, KEY, st)
    return status(email)


def caps() -> dict:
    """The configured ceilings, and what a full day of each would cost us."""
    return {k: {"per_day": _cap(k),
                "unit_cost_inr": UNIT_COST_INR.get(k),
                "worst_case_inr": round(_cap(k) * UNIT_COST_INR.get(k, 0), 2)}
            for k in ("image", "video", "text", "vision")}
