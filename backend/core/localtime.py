"""
What time it is where the SELLER is.

WHY THIS EXISTS
---------------
Every scheduled_at in this app is a naive wall-clock time: "14 Sep, 7:00 pm"
means seven in the evening where the seller lives. The server does not live
there — Render runs in UTC, and the default region is in the United States.
Until now the app assumed India (AUTOPLAN_TZ, default Asia/Kolkata), which is
right for the sellers it was built for and wrong for everyone else: a seller in
Dubai planning "Saturday 7pm" got posts timed to 9:30pm their time, and the
weekly planner woke on Saturday two hours before their Saturday began.

So the account says which country it is in, and everything that asks "what day
is it, and what time is it now" asks here instead of the server clock.

ONE ZONE PER COUNTRY, on purpose. Picking a state or province is one more
question at setup for a difference that matters in five countries out of
fifty. Where a country genuinely spans zones the commercial centre's zone is
used (and named in the list, so nobody is misled) and the seller can still
move any individual post by hand.
"""
from __future__ import annotations

import os
from datetime import date, datetime

from backend.core import user_store

KEY = "locale_settings"
DEFAULT_COUNTRY = "IN"

# code, name, IANA zone, what the zone is called where it is ambiguous.
COUNTRIES: list[dict] = [
    {"code": "IN", "name": "India", "tz": "Asia/Kolkata"},
    {"code": "AE", "name": "United Arab Emirates", "tz": "Asia/Dubai"},
    {"code": "AU", "name": "Australia", "tz": "Australia/Sydney", "note": "eastern time"},
    {"code": "BD", "name": "Bangladesh", "tz": "Asia/Dhaka"},
    {"code": "BR", "name": "Brazil", "tz": "America/Sao_Paulo", "note": "São Paulo time"},
    {"code": "CA", "name": "Canada", "tz": "America/Toronto", "note": "eastern time"},
    {"code": "CN", "name": "China", "tz": "Asia/Shanghai"},
    {"code": "DE", "name": "Germany", "tz": "Europe/Berlin"},
    {"code": "EG", "name": "Egypt", "tz": "Africa/Cairo"},
    {"code": "ES", "name": "Spain", "tz": "Europe/Madrid"},
    {"code": "FR", "name": "France", "tz": "Europe/Paris"},
    {"code": "GB", "name": "United Kingdom", "tz": "Europe/London"},
    {"code": "ID", "name": "Indonesia", "tz": "Asia/Jakarta", "note": "western time"},
    {"code": "IT", "name": "Italy", "tz": "Europe/Rome"},
    {"code": "JP", "name": "Japan", "tz": "Asia/Tokyo"},
    {"code": "KE", "name": "Kenya", "tz": "Africa/Nairobi"},
    {"code": "LK", "name": "Sri Lanka", "tz": "Asia/Colombo"},
    {"code": "MY", "name": "Malaysia", "tz": "Asia/Kuala_Lumpur"},
    {"code": "NG", "name": "Nigeria", "tz": "Africa/Lagos"},
    {"code": "NL", "name": "Netherlands", "tz": "Europe/Amsterdam"},
    {"code": "NP", "name": "Nepal", "tz": "Asia/Kathmandu"},
    {"code": "NZ", "name": "New Zealand", "tz": "Pacific/Auckland"},
    {"code": "OM", "name": "Oman", "tz": "Asia/Muscat"},
    {"code": "PH", "name": "Philippines", "tz": "Asia/Manila"},
    {"code": "PK", "name": "Pakistan", "tz": "Asia/Karachi"},
    {"code": "QA", "name": "Qatar", "tz": "Asia/Qatar"},
    {"code": "SA", "name": "Saudi Arabia", "tz": "Asia/Riyadh"},
    {"code": "SG", "name": "Singapore", "tz": "Asia/Singapore"},
    {"code": "TH", "name": "Thailand", "tz": "Asia/Bangkok"},
    {"code": "TR", "name": "Türkiye", "tz": "Europe/Istanbul"},
    {"code": "US", "name": "United States", "tz": "America/New_York", "note": "eastern time"},
    {"code": "VN", "name": "Vietnam", "tz": "Asia/Ho_Chi_Minh"},
    {"code": "ZA", "name": "South Africa", "tz": "Africa/Johannesburg"},
]
BY_CODE = {c["code"]: c for c in COUNTRIES}


def _tzinfo(name: str):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:  # noqa: BLE001 — a machine with no tz database
        return None


def get(email: str = "") -> dict:
    """The account's country and zone, falling back to the server default."""
    saved = {}
    if email:
        try:
            saved = user_store.get_key(email, KEY, {}) or {}
        except Exception:  # noqa: BLE001
            saved = {}
    code = str(saved.get("country") or "").upper()
    if code in BY_CODE:
        c = BY_CODE[code]
        return {"country": c["code"], "country_name": c["name"], "tz": c["tz"],
                "note": c.get("note", ""), "set": True}
    env_tz = (os.environ.get("AUTOPLAN_TZ") or "").strip()
    c = BY_CODE.get(DEFAULT_COUNTRY, COUNTRIES[0])
    return {"country": c["code"], "country_name": c["name"], "tz": env_tz or c["tz"],
            "note": c.get("note", ""), "set": False}


def set_country(email: str, code: str) -> dict:
    code = str(code or "").upper()
    if code not in BY_CODE:
        raise ValueError("Pick a country from the list.")
    user_store.set_key(email, KEY, {"country": code, "tz": BY_CODE[code]["tz"]})
    return get(email)


def tz(email: str = ""):
    return _tzinfo(get(email)["tz"])


def now(email: str = "") -> datetime:
    """Naive wall-clock time where the seller is — the frame every
    scheduled_at in this app is written in."""
    z = tz(email)
    return datetime.now(z).replace(tzinfo=None) if z else datetime.now()


def today(email: str = "") -> date:
    return now(email).date()


def label(email: str = "") -> str:
    """"India (IST, UTC+5:30)" — what the seller is shown next to a time."""
    info = get(email)
    z = _tzinfo(info["tz"])
    if z is None:
        return info["country_name"]
    stamp = datetime.now(z)
    off = stamp.utcoffset()
    mins = int((off.total_seconds() if off else 0) // 60)
    sign = "+" if mins >= 0 else "-"
    hh, mm = divmod(abs(mins), 60)
    abbr = stamp.tzname() or info["tz"].split("/")[-1].replace("_", " ")
    return f"{info['country_name']} ({abbr}, UTC{sign}{hh}:{mm:02d})"


def options() -> list[dict]:
    """The picker's list: country, zone and the current time in it."""
    out = []
    for c in COUNTRIES:
        z = _tzinfo(c["tz"])
        out.append({**c, "now": datetime.now(z).strftime("%H:%M") if z else ""})
    return out
