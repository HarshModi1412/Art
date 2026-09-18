"""
Credits — a monthly allowance plus purchased packs, spent by actual usage.

WHAT THIS IS, AND HOW IT SITS NEXT TO THE OTHER TWO METERS
----------------------------------------------------------
The app already has two ceilings and this is a THIRD thing, deliberately kept
separate from both:

  * billing.py  answers "is this seller entitled to this feature?" (tier +
    purchased credit packs). Untouched here.
  * aicaps.py   is the blunt daily/monthly guard on our own spend (the 30
    pictures a month a plan includes, and the runaway-account day ceiling).
    Untouched here — it stays the actual gate.

This module adds a single, human-readable CREDIT BALANCE the seller watches: a
monthly grant that refills on the 1st, plus any credit packs they have bought
(which never expire), and it is spent by ACTUAL USAGE — a picture costs more
than a line of text, a video costs much more than a picture — so "you have N
credits left" means something honest.

The point is a meter the seller understands and can top up, not a new wall.
During launch (and in general) the aicaps ceilings above remain the thing that
actually stops a runaway; this balance only ever goes down and shows a "buy
more" button when it is low. Nothing here raises a 402 on its own.

CALIBRATION
-----------
Per-call cost to us, from aicaps.UNIT_COST_INR (Sept 2026):
    image ₹3.70   video ₹105   text ₹0.20   vision ₹0.20
Peg one credit at ≈ ₹0.37 so a picture is 10 credits. The monthly grant is 300
credits — about 30 pictures, "roughly one a day", the same shape as the monthly
picture allowance the seller already knows. A line of text or a vision read is
1 credit; a video, 30× a picture, is 280.

    image  = 10     video = 280
    text   = 1      vision = 1

Everything overridable per deployment:
    CREDITS_PER_MONTH        monthly grant (default 300; 0 turns the grant off)
    CREDIT_COST_IMAGE / _VIDEO / _TEXT / _VISION   per-generation cost
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from backend.core import billing, pricing, user_store

# The monthly grant is counted like the picture allowance in aicaps: a per-month
# "used" tally in the account's state, reset when the calendar month rolls over
# in IST so "resets on the 1st" means the same to the seller and the server.
USAGE_KEY = "credit_monthly_usage"
IST = timezone(timedelta(hours=5, minutes=30))

_DEFAULT_COST = {"image": 10, "video": 280, "text": 1, "vision": 1}
_COST_ENV = {"image": "CREDIT_COST_IMAGE", "video": "CREDIT_COST_VIDEO",
             "text": "CREDIT_COST_TEXT", "vision": "CREDIT_COST_VISION"}


def _int_env(name: str, default: int) -> int:
    try:
        return max(0, int(os.environ.get(name) or default))
    except (TypeError, ValueError):
        return default


def monthly_grant() -> int:
    """Credits granted every calendar month. 0 turns the grant off entirely
    (purchased packs still work)."""
    return _int_env("CREDITS_PER_MONTH", 300)


def cost(kind: str) -> int:
    """Credits one generation of this kind costs. 0 for an unknown kind."""
    env = _COST_ENV.get(kind)
    if not env:
        return 0
    return _int_env(env, _DEFAULT_COST.get(kind, 0))


def costs() -> dict:
    """The per-generation price list, for the UI and the meter."""
    return {k: cost(k) for k in _DEFAULT_COST}


def _month() -> str:
    return datetime.now(IST).strftime("%Y-%m")


def _load(email: str) -> dict:
    raw = user_store.get_key(email, USAGE_KEY, {}) or {}
    if not isinstance(raw, dict) or raw.get("month") != _month():
        # A new month starts the count at zero — this is a budget, not a history.
        return {"month": _month(), "used": 0}
    raw.setdefault("used", 0)
    return raw


def monthly_used(email: str) -> int:
    return int(_load(email).get("used") or 0)


def monthly_left(email: str) -> int:
    g = monthly_grant()
    return max(0, g - monthly_used(email)) if g else 0


def purchased(email: str) -> int:
    """Credits from packs the seller bought — these never expire."""
    return int(billing.credit_pool(email))


def balance(email: str) -> int:
    """Everything the seller can spend right now: this month's grant + packs."""
    return monthly_left(email) + purchased(email)


def can_afford(email: str, kind: str) -> bool:
    c = cost(kind)
    return c <= 0 or balance(email) >= c


def _spend_monthly(email: str, n: int) -> None:
    if n <= 0:
        return
    st = _load(email)
    st["used"] = int(st.get("used") or 0) + n
    user_store.set_key(email, USAGE_KEY, st)


def spend(email: str, kind: str, n: int = 1) -> dict:
    """Deduct what a successful generation actually cost — the month's grant
    first, then purchased packs. Best-effort: it clamps at zero and never
    raises, so a billing hiccup can't fail a generation the seller already saw.
    Call it AFTER the generation succeeds, the same rule aicaps.consume follows.
    """
    total = cost(kind) * max(1, int(n))
    if total <= 0:
        return status(email)
    try:
        from_month = min(monthly_left(email), total)
        _spend_monthly(email, from_month)
        rest = total - from_month
        if rest > 0:
            # spend_credits is all-or-nothing; if the pack pool is short we take
            # what accounting we can and let the aicaps ceilings be the real
            # stop. Overspend during launch is never billed to the seller.
            billing.spend_credits(email, rest)
    except Exception:  # noqa: BLE001 — a meter must never break a generation
        pass
    return status(email)


def status(email: str) -> dict:
    """What the Account tab's Credits card shows, in one call."""
    g = monthly_grant()
    packs = [{"id": c["id"], "name": c["name"], "price_inr": c["price_inr"],
              "credits": c["credits"], "description": c.get("description", "")}
             for c in pricing.CREDIT_PACKS.values()]
    return {
        "monthly_grant": g,
        "monthly_used": monthly_used(email),
        "monthly_left": monthly_left(email),
        "purchased": purchased(email),
        "balance": balance(email),
        "resets": "on the 1st",
        "enabled": bool(g),
        "costs": costs(),
        "packs": packs,
        "launch_mode": pricing.launch_mode(),
    }
