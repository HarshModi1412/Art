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
    }


class CapReached(RuntimeError):
    """Not a paywall. The seller has done nothing wrong."""


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
