"""
Discount codes a Marketing Campaign hands out, and the checkout that honours them.

WHY THIS EXISTS
---------------
Win-back messages used to promise "Use code BACK15-D720 for 15% off" with a
code that existed nowhere but the message. A shopper who came back and typed it
at checkout got nothing — the single worst outcome a win-back can have, because
it turns "they missed me" into "they lied to me".

So every code is now a real record: issued for one customer by one campaign,
for the offer the seller chose, valid for a fixed window, and good for exactly
one order on the seller's own website. When it is used, the order number is
written onto it, which makes a redeemed code the hardest proof there is that a
campaign brought someone back (see `campaign_stats`).

THE RULES
---------
* One offer per campaign, the same for everyone in it: a flat amount ("₹200
  off") or a percentage ("15% off"), optionally above a minimum order.
* One code per customer, single use, VALID_DAYS long.
* Codes are short and readable — the customer's first name and five characters
  from an alphabet without 0/O/1/I/L — because people type them on a phone.
  31^5 is ~28 million suffixes per name; the public check endpoint is rate
  limited on top of that.

Storage is one dict per seller keyed by code, so two campaigns writing at once
merge per code instead of overwriting each other (user_store._merge_value).
"""
from __future__ import annotations

import re
import secrets
import threading
from datetime import date, datetime, timedelta

from backend.core import user_store

KEY = "discount_codes"
VALID_DAYS = 14
KEEP_EXPIRED_DAYS = 120          # old codes are pruned after this
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

_lock = threading.Lock()


class DiscountError(ValueError):
    """A code that cannot be used, with a reason a shopper can read."""


# ------------------------------------------------------------------- offer
def clean_offer(raw: dict | None) -> dict:
    """Validate the seller's offer. Raises DiscountError with a plain reason."""
    raw = raw or {}
    kind = str(raw.get("kind") or "flat").strip().lower()
    if kind not in ("flat", "percent"):
        raise DiscountError("Choose an amount off or a percentage off.")
    try:
        value = round(float(raw.get("value") or 0), 2)
    except (TypeError, ValueError):
        raise DiscountError("Enter the discount as a number.")
    if value <= 0:
        raise DiscountError("Enter a discount above zero.")
    if kind == "percent" and value > 90:
        raise DiscountError("A percentage discount can be at most 90%.")
    try:
        min_order = max(0.0, round(float(raw.get("min_order") or 0), 2))
    except (TypeError, ValueError):
        min_order = 0.0
    if kind == "flat" and min_order and value >= min_order:
        raise DiscountError("The discount must be smaller than the minimum order.")
    return {"kind": kind, "value": value, "min_order": min_order}


def offer_label(offer: dict, symbol: str = "₹") -> str:
    """'₹200 off' / '15% off', plus the minimum when there is one."""
    v = offer.get("value") or 0
    num = f"{v:,.0f}" if float(v).is_integer() else f"{v:,.2f}"
    base = f"{num}% off" if offer.get("kind") == "percent" else f"{symbol}{num} off"
    if offer.get("min_order"):
        m = offer["min_order"]
        mnum = f"{m:,.0f}" if float(m).is_integer() else f"{m:,.2f}"
        base += f" on orders above {symbol}{mnum}"
    return base


def amount_for(offer: dict, subtotal: float) -> float:
    """What this offer takes off this subtotal. Never more than the subtotal."""
    subtotal = max(0.0, float(subtotal or 0))
    if offer.get("kind") == "percent":
        off = subtotal * float(offer.get("value") or 0) / 100.0
    else:
        off = float(offer.get("value") or 0)
    return round(min(off, subtotal), 2)


# ------------------------------------------------------------------- store
def _norm(seller: str) -> str:
    return (seller or "").strip().lower()


def _codes(seller: str, fresh: bool = False) -> dict:
    if fresh:
        # Redemption must see what another request wrote a moment ago, not this
        # request's memoised copy — that is the difference between a code being
        # single-use and being single-use-per-request.
        try:
            rows = user_store._read_state(_norm(seller)).get(KEY)  # noqa: SLF001
        except Exception:  # noqa: BLE001
            rows = user_store.get_key(_norm(seller), KEY, {})
    else:
        rows = user_store.get_key(_norm(seller), KEY, {})
    return rows if isinstance(rows, dict) else {}


def normalize_code(code: str | None) -> str:
    return re.sub(r"[^A-Z0-9-]", "", str(code or "").upper())[:24]


def _prefix(name: str, fallback: str) -> str:
    first = re.sub(r"[^A-Za-z]", "", (str(name or "").split() or [""])[0]).upper()
    return (first[:6] if len(first) >= 2 else fallback)


def _today(seller: str) -> date:
    try:
        from backend.core import localtime
        return localtime.today(seller)
    except Exception:  # noqa: BLE001
        return date.today()


def issue(seller: str, campaign_id: str, customers: list[dict], offer: dict,
          prefix_fallback: str = "OFFER", valid_days: int = VALID_DAYS) -> dict[str, dict]:
    """One fresh code per customer for this campaign.

    Returns {customer_id: code_record}. Re-issuing for the same campaign and
    customer returns the code already issued, so rebuilding a preview does not
    leave a trail of orphan codes."""
    seller = _norm(seller)
    offer = clean_offer(offer)
    until = (_today(seller) + timedelta(days=valid_days)).isoformat()
    with _lock:
        codes = dict(_codes(seller, fresh=True))
        existing = {(r.get("campaign_id"), r.get("customer_id")): r
                    for r in codes.values() if isinstance(r, dict)}
        out: dict[str, dict] = {}
        now = datetime.now().isoformat(timespec="seconds")
        for c in customers or []:
            cid = str(c.get("customer_id") or "").strip()
            if not cid:
                continue
            prev = existing.get((campaign_id, cid))
            if prev:
                out[cid] = prev
                continue
            pre = _prefix(c.get("customer_name") or "", prefix_fallback)
            for _ in range(20):
                code = f"{pre}-{''.join(secrets.choice(ALPHABET) for _ in range(5))}"
                if code not in codes:
                    break
            rec = {"code": code, "campaign_id": campaign_id, "customer_id": cid,
                   "customer_name": str(c.get("customer_name") or "")[:80],
                   "kind": offer["kind"], "value": offer["value"],
                   "min_order": offer["min_order"], "valid_until": until,
                   "created_at": now, "redeemed_at": "", "order_no": "",
                   "order_total": 0.0, "discount_given": 0.0}
            codes[code] = rec
            out[cid] = rec
        codes = _prune(codes, seller)
        user_store.set_key(seller, KEY, codes)
    return out


def _prune(codes: dict, seller: str) -> dict:
    cutoff = (_today(seller) - timedelta(days=KEEP_EXPIRED_DAYS)).isoformat()
    return {k: v for k, v in codes.items()
            if isinstance(v, dict) and (v.get("redeemed_at") or str(v.get("valid_until") or "") >= cutoff)}


# ------------------------------------------------------------------- checkout
def check(seller: str, code: str, subtotal: float, fresh: bool = False,
          symbol: str = "") -> dict:
    """Is this code usable on this subtotal? Returns the record and the amount
    off; raises DiscountError with a reason a shopper can act on."""
    seller = _norm(seller)
    code = normalize_code(code)
    if not code:
        raise DiscountError("Enter a code.")
    rec = _codes(seller, fresh=fresh).get(code)
    if not isinstance(rec, dict):
        raise DiscountError("That code is not valid for this shop.")
    if rec.get("redeemed_at"):
        raise DiscountError("That code has already been used.")
    if str(rec.get("valid_until") or "") < _today(seller).isoformat():
        raise DiscountError("That code has expired.")
    min_order = float(rec.get("min_order") or 0)
    if min_order and float(subtotal or 0) < min_order:
        raise DiscountError(f"This code works on orders of {symbol}{min_order:,.0f} or more.")
    off = amount_for(rec, subtotal)
    if off <= 0:
        raise DiscountError("Add something to your bag first.")
    return {"code": code, "amount": off, "kind": rec.get("kind"),
            "value": rec.get("value"), "min_order": min_order,
            "valid_until": rec.get("valid_until")}


def redeem(seller: str, code: str, subtotal: float, order_no: str,
           order_total: float) -> dict:
    """Spend the code on one order. Checked again under the lock against the
    stored state, so two tabs placing orders at once cannot both use it."""
    seller = _norm(seller)
    code = normalize_code(code)
    with _lock:
        res = check(seller, code, subtotal, fresh=True)
        codes = dict(_codes(seller, fresh=True))
        rec = dict(codes[code])
        rec.update({"redeemed_at": datetime.now().isoformat(timespec="seconds"),
                    "order_no": str(order_no or "")[:40],
                    "order_total": round(float(order_total or 0), 2),
                    "discount_given": res["amount"]})
        codes[code] = rec
        user_store.set_key(seller, KEY, codes)
    return res


def release(seller: str, code: str, order_no: str) -> None:
    """Give a code back when the order it was used on is cancelled."""
    seller = _norm(seller)
    code = normalize_code(code)
    with _lock:
        codes = dict(_codes(seller, fresh=True))
        rec = codes.get(code)
        if not isinstance(rec, dict) or rec.get("order_no") != order_no:
            return
        rec = dict(rec)
        rec.update({"redeemed_at": "", "order_no": "", "order_total": 0.0,
                    "discount_given": 0.0})
        codes[code] = rec
        user_store.set_key(seller, KEY, codes)


# ------------------------------------------------------------------- results
def campaign_stats(seller: str, campaign_id: str) -> dict:
    """How many of a campaign's codes came back, and what those orders were."""
    rows = [r for r in _codes(seller).values()
            if isinstance(r, dict) and r.get("campaign_id") == campaign_id]
    used = [r for r in rows if r.get("redeemed_at")]
    return {"issued": len(rows), "redeemed": len(used),
            "revenue": round(sum(float(r.get("order_total") or 0) for r in used), 2),
            "discount_given": round(sum(float(r.get("discount_given") or 0) for r in used), 2),
            "redeemed_by": [{"customer_name": r.get("customer_name"), "code": r.get("code"),
                             "order_no": r.get("order_no"), "at": r.get("redeemed_at")}
                            for r in used][:50]}


def all_stats(seller: str) -> dict[str, dict]:
    ids = {r.get("campaign_id") for r in _codes(seller).values() if isinstance(r, dict)}
    return {cid: campaign_stats(seller, cid) for cid in ids if cid}
