"""
Money, in the seller's own currency.

WHY THIS EXISTS
---------------
The app was built for India, so the rupee and its grouping (1,20,000, not
120,000) were written straight into every price. The moment a seller in the US
or UK signs in, that is wrong in two visible ways at once: the symbol and the
grouping. This module is the single place that knows both, so a price is
formatted the same way everywhere and adding a currency later is one entry here
rather than a hunt through the app.

WHAT IT IS NOT
--------------
Not FX. We never convert one currency into another — a shop priced in pounds is
priced in pounds, full stop. Converting would mean a rate, a rate means a source
and a moment, and a price that quietly changes with the market is not a price.
Each seller picks ONE base currency for their shop; everything they see and
every order is in it.

MINOR UNITS
-----------
Razorpay, Stripe and PayPal all take the amount in the currency's smallest unit
(paise, cents). All four currencies here are two-decimal, so that is always
amount * 100 — but it goes through minor_units() so a zero-decimal currency
added later cannot silently be multiplied wrong.
"""
from __future__ import annotations

CURRENCIES: dict[str, dict] = {
    "INR": {"code": "INR", "symbol": "₹", "name": "Indian rupee",
            "decimals": 2, "grouping": "IN"},
    "USD": {"code": "USD", "symbol": "$", "name": "US dollar",
            "decimals": 2, "grouping": "WEST"},
    "GBP": {"code": "GBP", "symbol": "£", "name": "British pound",
            "decimals": 2, "grouping": "WEST"},
    "EUR": {"code": "EUR", "symbol": "€", "name": "Euro",
            "decimals": 2, "grouping": "WEST"},
}
DEFAULT = "INR"

# Which currency a country most likely sells in, so picking the selling country
# fills the currency in for the seller instead of asking twice. Anything not
# listed falls back to USD, which is the safest default for an unlisted market.
_EUROZONE = ("DE", "FR", "ES", "IT", "NL", "IE", "PT", "AT", "BE", "FI",
             "GR", "SK", "SI", "LT", "LV", "EE", "LU", "MT", "CY", "HR")
COUNTRY_CCY: dict[str, str] = {
    "IN": "INR", "US": "USD", "GB": "GBP",
    **{c: "EUR" for c in _EUROZONE},
}


def is_valid(code: str) -> bool:
    return str(code or "").upper() in CURRENCIES


def normalize(code: str | None) -> str:
    c = str(code or "").upper()
    return c if c in CURRENCIES else DEFAULT


def for_country(country_code: str | None) -> str:
    """The currency a seller in this country would default to."""
    return COUNTRY_CCY.get(str(country_code or "").upper(), "USD")


def info(code: str | None) -> dict:
    return CURRENCIES[normalize(code)]


def symbol(code: str | None) -> str:
    return CURRENCIES[normalize(code)]["symbol"]


def options() -> list[dict]:
    """The currency picker's list."""
    return [{"code": c["code"], "symbol": c["symbol"], "name": c["name"]}
            for c in CURRENCIES.values()]


def _group_indian(int_str: str) -> str:
    """12,00,000 grouping: last three digits, then twos. Sign handled by caller."""
    if len(int_str) <= 3:
        return int_str
    head, tail = int_str[:-3], int_str[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts) + "," + tail


def _grouped(amount: float, code: str, decimals: int) -> str:
    """The absolute number, grouped for the currency, with `decimals` places.
    No symbol and no sign — the caller places the sign before the symbol."""
    ccy = CURRENCIES[normalize(code)]
    amount = abs(round(float(amount or 0), decimals))
    if decimals > 0:
        whole = int(amount)
        frac = round(amount - whole, decimals)
        frac_str = ("%0.*f" % (decimals, frac))[2:]  # drop the leading "0."
    else:
        whole = int(round(amount))
        frac_str = ""
    whole_str = str(whole)
    if ccy["grouping"] == "IN":
        grouped = _group_indian(whole_str)
    else:
        grouped = "{:,}".format(whole)
    return grouped + ("." + frac_str if frac_str else "")


def fmt(amount, code: str | None, decimals: int = 0) -> str:
    """Symbol + grouped amount, e.g. fmt(120000, 'INR') -> '₹1,20,000',
    fmt(1200, 'USD') -> '$1,200'. A negative amount reads '-$500', sign before
    the symbol. Whole-number by default, which is how the app shows most money;
    pass decimals=2 for line items and invoices."""
    neg = float(amount or 0) < 0
    body = symbol(code) + _grouped(amount, code, decimals)
    return ("-" + body) if neg else body


def fmt2(amount, code: str | None) -> str:
    """Symbol + amount with the currency's decimal places (2 for all of ours).
    For invoices and cart lines, where 1,200.00 is expected."""
    return fmt(amount, code, decimals=CURRENCIES[normalize(code)]["decimals"])


def minor_units(amount, code: str | None) -> int:
    """The amount in the currency's smallest unit, for a payment gateway.
    All four currencies are two-decimal, so this is amount * 100; the exponent
    is read from the table so a zero-decimal currency added later is correct."""
    decimals = CURRENCIES[normalize(code)]["decimals"]
    return int(round(float(amount or 0) * (10 ** decimals)))


def from_minor(units: int, code: str | None) -> float:
    decimals = CURRENCIES[normalize(code)]["decimals"]
    return round(int(units or 0) / (10 ** decimals), decimals)
