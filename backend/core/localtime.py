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


def _saved(email: str) -> dict:
    if not email:
        return {}
    try:
        return user_store.get_key(email, KEY, {}) or {}
    except Exception:  # noqa: BLE001
        return {}


def get(email: str = "") -> dict:
    """The account's country, zone, selling country and currency.

    `country` is where the SELLER is (drives the clock and, for India, GST).
    `selling_country` is the market they sell to (drives the default currency).
    `currency` is the one base currency the whole shop is priced in. All three
    fall back sensibly: an unset selling country follows the seller's country,
    and an unset currency follows the selling country (India->INR, US->USD,
    UK->GBP, eurozone->EUR, otherwise USD)."""
    from backend.core import currency  # local import avoids an import cycle
    saved = _saved(email)
    code = str(saved.get("country") or "").upper()
    if code in BY_CODE:
        c = BY_CODE[code]
        base = {"country": c["code"], "country_name": c["name"], "tz": c["tz"],
                "note": c.get("note", ""), "set": True}
    else:
        env_tz = (os.environ.get("AUTOPLAN_TZ") or "").strip()
        c = BY_CODE.get(DEFAULT_COUNTRY, COUNTRIES[0])
        base = {"country": c["code"], "country_name": c["name"],
                "tz": env_tz or c["tz"], "note": c.get("note", ""), "set": False}

    selling = str(saved.get("selling_country") or "").upper()
    if selling not in BY_CODE:
        selling = base["country"]           # sell where you are, unless told otherwise
    ccy = currency.normalize(saved.get("currency") or currency.for_country(selling))
    base["selling_country"] = selling
    base["selling_country_name"] = BY_CODE.get(selling, {}).get("name", selling)
    base["currency"] = ccy
    base["currency_symbol"] = currency.symbol(ccy)
    base["charges_tax"] = base["country"] == "IN"   # GST is India-only, by policy
    return base


def _write(email: str, patch: dict) -> None:
    cur = _saved(email)
    cur.update({k: v for k, v in patch.items() if v is not None})
    user_store.set_key(email, KEY, cur)


def set_country(email: str, code: str) -> dict:
    code = str(code or "").upper()
    if code not in BY_CODE:
        raise ValueError("Pick a country from the list.")
    _write(email, {"country": code, "tz": BY_CODE[code]["tz"]})
    return get(email)


def set_settings(email: str, country: str | None = None,
                 selling_country: str | None = None,
                 currency_code: str | None = None) -> dict:
    """Save any of the account's market settings. Each is optional so the
    Account tab can change one without disturbing the others."""
    from backend.core import currency
    patch: dict = {}
    if country is not None:
        c = str(country).upper()
        if c not in BY_CODE:
            raise ValueError("Pick a country from the list.")
        patch["country"] = c
        patch["tz"] = BY_CODE[c]["tz"]
    if selling_country is not None:
        s = str(selling_country).upper()
        if s not in BY_CODE:
            raise ValueError("Pick a selling country from the list.")
        patch["selling_country"] = s
    if currency_code is not None:
        if not currency.is_valid(currency_code):
            raise ValueError("Pick a currency from the list.")
        patch["currency"] = currency.normalize(currency_code)
    _write(email, patch)
    return get(email)


def currency_code(email: str = "") -> str:
    """The one base currency this account is priced in."""
    return get(email)["currency"]


def charges_tax(email: str = "") -> bool:
    """Whether an order or invoice for this seller carries tax. GST for India;
    nothing outside it, by product policy, until proper VAT/sales-tax exists."""
    return get(email)["country"] == "IN"


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
