"""
Which market a visitor is in, and so which currency they are priced in.

WHY
---
The US is the primary market from September 2026: dollars by default, rupees for
buyers in India. The two price lists are set by hand in pricing.py, never
converted (see currency.py).

HOW A VISITOR IS PLACED, first match wins
-----------------------------------------
1. `?region=in` or `?region=us` on the URL, which also sets a cookie so the
   choice sticks. This is the visible "Prices in ₹ / $" switch on the pages.
2. The `otm_region` cookie from an earlier choice.
3. A country header from the edge. Cloudflare sends CF-IPCountry; the others
   are there so a move of host does not silently break this.
4. The region in Accept-Language (en-IN, hi-IN and so on mean India).
5. Otherwise the US.

A signed-in seller is billed in the currency saved on their account at signup
(billing.billing_currency), not in whatever this guesses on a given day, so a
trip abroad never changes what they pay.
"""
from __future__ import annotations

import re

COOKIE = "otm_region"
REGIONS = {"us": "USD", "in": "INR"}
DEFAULT = "us"

_COUNTRY_HEADERS = ("cf-ipcountry", "x-country-code", "x-vercel-ip-country",
                    "cloudfront-viewer-country", "x-appengine-country",
                    "fly-client-country")

# Languages spoken almost only in India, so a browser set to them is in India
# even when it gives no region subtag.
_INDIAN_LANGS = ("hi", "ta", "kn", "te", "mr", "bn", "gu", "ml", "pa", "or")


def _from_query_or_cookie(query: dict | None, cookies: dict | None) -> str | None:
    for src in ((query or {}).get("region"), (cookies or {}).get(COOKIE)):
        r = str(src or "").strip().lower()
        if r in REGIONS:
            return r
    return None


def _from_headers(headers) -> str | None:
    for h in _COUNTRY_HEADERS:
        cc = str(headers.get(h) or "").strip().upper()
        if len(cc) == 2 and cc not in ("XX", "T1"):
            return "in" if cc == "IN" else "us"
    lang = str(headers.get("accept-language") or "")
    first = lang.split(",")[0].strip().lower()
    if not first:
        return None
    if re.match(r"^[a-z]{2,3}-in\b", first) or first.split("-")[0] in _INDIAN_LANGS:
        return "in"
    return None


def detect(request) -> str:
    """'us' or 'in' for this request. Never raises."""
    try:
        explicit = _from_query_or_cookie(dict(request.query_params), dict(request.cookies))
        if explicit:
            return explicit
        return _from_headers(request.headers) or DEFAULT
    except Exception:  # noqa: BLE001 - a guess must never break a page
        return DEFAULT


def currency_for(region: str) -> str:
    return REGIONS.get(str(region or "").lower(), "USD")


def detect_currency(request) -> str:
    return currency_for(detect(request))


def explicit_choice(request) -> str | None:
    """The region named on the URL, if any, so the response can remember it."""
    try:
        r = str(request.query_params.get("region") or "").strip().lower()
        return r if r in REGIONS else None
    except Exception:  # noqa: BLE001
        return None
