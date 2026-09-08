"""
"I want to cancel this" — as a conversation, not a button that fires.

THE DESIGN DECISION
-------------------
The obvious implementation is a Cancel button that cancels. That is wrong for
this market, and expensively so.

An Indian D2C cancellation is almost never final. A shopper who wants to cancel
usually wants a different size, a later delivery date, or reassurance that the
parcel is actually moving. A one-click cancel converts every one of those into a
lost sale and a restocking job. A shopper who can *talk to the seller* converts
a meaningful share of them into an exchange or a delayed dispatch instead.

So this module models a REQUEST, not an action:

    shopper taps Cancel
      -> request recorded against the order, status "requested"
      -> seller gets a WhatsApp message with the order, the reason and a
         one-tap link to the shopper's chat
      -> they talk
      -> seller approves or declines IN THE APP, and only approval cancels

The order does not change status while a request is open. It gains a flag, so
Orders can show it and the seller cannot ship something a shopper is arguing
about without seeing that they asked.

The same shape covers purchase orders, where the counterparty is a supplier
rather than a shopper. A supplier asking to cancel a PO is exactly the same
conversation with different names on it, so it is the same code.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from urllib.parse import quote

from backend.core import user_store

KEY = "cancel_requests"
MAX = 500

SHOPPER_REASONS = [
    ("changed_mind", "I changed my mind"),
    ("wrong_size", "I ordered the wrong size"),
    ("wrong_item", "I ordered the wrong item"),
    ("too_slow", "It is taking too long"),
    ("found_cheaper", "I found it cheaper elsewhere"),
    ("ordered_twice", "I ordered twice by mistake"),
    ("other", "Something else"),
]

# Which reasons the seller can most plausibly save, and what to try. Shown to
# the seller when the request arrives, because the difference between a saved
# sale and a lost one is usually whether they knew what to offer in the first
# thirty seconds.
SAVE_PLAY = {
    "wrong_size": "Offer a free size exchange before it ships. This is the most "
                  "recoverable reason there is.",
    "wrong_item": "Offer to swap the item rather than refund.",
    "too_slow": "Give a real dispatch date. Most 'too slow' cancels are anxiety, "
                "not a deadline.",
    "found_cheaper": "Decide once whether you match prices. Do not negotiate "
                     "case by case — it trains shoppers to ask.",
    "ordered_twice": "Cancel one, confirm the other. Quick and uncontroversial.",
    "changed_mind": "Hard to save. Cancel cleanly and quickly; a fast, gracious "
                    "cancel is what earns the next order.",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _digits(p: str) -> str:
    d = "".join(c for c in str(p or "") if c.isdigit())
    return f"91{d}" if len(d) == 10 else d


def wa_link(phone: str, text: str) -> str:
    d = _digits(phone)
    return f"https://wa.me/{d}?text={quote(text)}" if len(d) >= 11 else ""


def _all(email: str) -> list[dict]:
    rows = user_store.get_key((email or "").lower(), KEY, []) or []
    return rows if isinstance(rows, list) else []


def _save(email: str, rows: list[dict]) -> None:
    user_store.set_key((email or "").lower(), KEY, rows[-MAX:])


# --------------------------------------------------------------- raising

def raise_request(email: str, *, kind: str, ref_id: str, ref_no: str,
                  reason_code: str, reason_text: str = "",
                  raised_by: str = "shopper", counterparty: dict | None = None) -> dict:
    """Record a cancellation request. `kind` is 'order' or 'po'."""
    email = (email or "").lower()
    rows = _all(email)
    open_one = next((r for r in rows if r.get("ref_id") == ref_id
                     and r.get("status") == "requested"), None)
    if open_one:
        return open_one

    label = dict(SHOPPER_REASONS).get(reason_code, reason_code)
    req = {
        "id": secrets.token_hex(6),
        "kind": kind, "ref_id": ref_id, "ref_no": ref_no,
        "reason_code": reason_code, "reason_label": label,
        "reason_text": str(reason_text or "")[:300],
        "raised_by": raised_by, "raised_at": _now(),
        "status": "requested",         # requested -> approved | declined
        "resolved_at": "", "resolved_note": "",
        "counterparty": counterparty or {},
        "save_play": SAVE_PLAY.get(reason_code, ""),
        "notified": False,
    }
    rows.append(req)
    _save(email, rows)
    return req


def seller_message(req: dict, store_name: str) -> str:
    """What lands on the seller's phone. Written so it is actionable from the
    notification preview alone, without opening the app."""
    who = (req.get("counterparty") or {}).get("name") or "A customer"
    what = "order" if req.get("kind") == "order" else "purchase order"
    lines = [
        f"Cancellation request on {what} {req.get('ref_no')}",
        f"{who} says: {req.get('reason_label')}",
    ]
    if req.get("reason_text"):
        lines.append(f'"{req["reason_text"]}"')
    if req.get("save_play"):
        lines.append("")
        lines.append(f"Worth trying: {req['save_play']}")
    lines.append("")
    lines.append(f"Nothing has been cancelled yet. Talk to them, then approve or "
                 f"decline in {store_name}.")
    return "\n".join(lines)


def shopper_opener(req: dict, store_name: str) -> str:
    """Pre-written first message for the seller to send the shopper, so the
    chat starts with the seller sounding organised rather than surprised."""
    who = (req.get("counterparty") or {}).get("name") or "there"
    return (f"Hi {who}, this is {store_name}. I saw your cancellation request for "
            f"order {req.get('ref_no')} — {req.get('reason_label').lower()}. "
            f"Before I cancel it, is there anything I can do instead?")


def notify_payload(email: str, req: dict, store_name: str,
                   seller_phone: str) -> dict:
    """Everything the caller needs to actually deliver the notification.

    Returns links rather than sending, because whether WhatsApp sends
    automatically depends on the seller having a BSP configured. With one, the
    caller posts `seller_text`. Without one, the seller taps `seller_wa` on
    their own phone. Either way the seller learns about it."""
    cp = req.get("counterparty") or {}
    return {
        "seller_text": seller_message(req, store_name),
        "seller_wa": wa_link(seller_phone, seller_message(req, store_name)),
        "shopper_wa": wa_link(cp.get("phone") or "",
                              shopper_opener(req, store_name)),
        "shopper_phone": cp.get("phone") or "",
        "shopper_name": cp.get("name") or "",
    }


def mark_notified(email: str, req_id: str) -> None:
    rows = _all(email)
    for r in rows:
        if r.get("id") == req_id:
            r["notified"] = True
            r["notified_at"] = _now()
    _save(email, rows)


# --------------------------------------------------------------- resolving

def resolve(email: str, req_id: str, decision: str, note: str = "") -> dict:
    """approve = actually cancel. decline = keep the order, record why."""
    if decision not in ("approved", "declined"):
        return {"error": "decision must be 'approved' or 'declined'"}
    rows = _all(email)
    for r in rows:
        if r.get("id") == req_id:
            if r.get("status") != "requested":
                return r
            r["status"] = decision
            r["resolved_at"] = _now()
            r["resolved_note"] = str(note or "")[:300]
            _save(email, rows)
            return r
    return {"error": "not found"}


def open_requests(email: str, kind: str = "") -> list[dict]:
    rows = [r for r in _all(email) if r.get("status") == "requested"]
    if kind:
        rows = [r for r in rows if r.get("kind") == kind]
    return sorted(rows, key=lambda r: r.get("raised_at", ""), reverse=True)


def for_ref(email: str, ref_id: str) -> dict | None:
    return next((r for r in _all(email) if r.get("ref_id") == ref_id
                 and r.get("status") == "requested"), None)


def history(email: str, limit: int = 100) -> list[dict]:
    return sorted(_all(email), key=lambda r: r.get("raised_at", ""), reverse=True)[:limit]


def summary(email: str) -> dict:
    """How well is the seller saving cancellations? A save rate is the only
    number here that changes behaviour."""
    rows = _all(email)
    done = [r for r in rows if r.get("status") in ("approved", "declined")]
    saved = [r for r in done if r["status"] == "declined"]
    by_reason: dict[str, int] = {}
    for r in rows:
        by_reason[r.get("reason_label") or "?"] = by_reason.get(r.get("reason_label") or "?", 0) + 1
    return {
        "open": len([r for r in rows if r.get("status") == "requested"]),
        "total": len(rows), "resolved": len(done), "saved": len(saved),
        "save_rate": round(100 * len(saved) / len(done), 1) if done else None,
        "by_reason": sorted(by_reason.items(), key=lambda kv: -kv[1]),
        "enough_data": len(done) >= 10,
    }
