"""
A seller's contact book: phone numbers and emails added by hand.

Uploaded sales often have no phone or email at all, or an old one. The
Marketing Campaign lets the seller type them in per customer; they are kept
here, keyed by the customer id from the sales data, so the next campaign (and
the automatic one every second Monday) already has them. A hand-entered value
wins over the uploaded one: the seller typed it because the file was wrong.
"""
from __future__ import annotations

import re
from datetime import datetime

from backend.core import user_store

KEY = "contact_book"
MAX = 5000


class ContactError(ValueError):
    pass


def book(email: str) -> dict:
    b = user_store.get_key(email, KEY, {}) or {}
    return b if isinstance(b, dict) else {}


def clean_phone(v) -> str:
    raw = str(v or "").strip()
    if not raw:
        return ""
    d = re.sub(r"\D", "", raw)
    if not (10 <= len(d) <= 15):
        raise ContactError("Enter a full phone number (10 digits, or with country code).")
    return ("+" + d) if raw.startswith("+") else d


def clean_email(v) -> str:
    e = str(v or "").strip().lower()
    if not e:
        return ""
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", e):
        raise ContactError("That email address does not look right.")
    return e


def save(email: str, customer_id: str, phone=None, mail=None, name: str = "") -> dict:
    """Set one customer's phone and/or email. None leaves a field alone, ""
    clears it. Returns the stored entry."""
    cid = str(customer_id or "").strip()
    if not cid:
        raise ContactError("Which customer is this for?")
    b = dict(book(email))
    entry = dict(b.get(cid) or {})
    if phone is not None:
        entry["phone"] = clean_phone(phone)
    if mail is not None:
        entry["email"] = clean_email(mail)
    if name:
        entry["name"] = str(name)[:80]
    entry["updated_at"] = datetime.now().isoformat(timespec="seconds")
    b[cid] = entry
    if len(b) > MAX:
        for k in sorted(b, key=lambda k: b[k].get("updated_at") or "")[:len(b) - MAX]:
            b.pop(k, None)
    user_store.set_key(email, KEY, b)
    return entry


def apply(email: str, profiles: list[dict]) -> list[dict]:
    """Fill in / correct each profile's phone and email from the book."""
    b = book(email)
    if not b:
        return profiles
    for p in profiles:
        e = b.get(str(p.get("customer_id") or ""))
        if not e:
            continue
        if e.get("phone"):
            p["phone"] = e["phone"]
        if e.get("email"):
            p["email"] = e["email"]
    return profiles
