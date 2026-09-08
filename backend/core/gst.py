"""
Indian GST — rates, place of supply, and the three kinds of document a seller
may lawfully issue.

READ THIS BEFORE CHANGING ANY NUMBER
------------------------------------
Rates here reflect "GST 2.0", the rationalisation notified by Notification
09/2025-Central Tax (Rate) and effective 22 September 2025. The old four-slab
5/12/18/28 structure collapsed to a principal two slabs (5% and 18%) with a new
40% demerit slab; Chapter 71's 3% for jewellery was untouched.

The change that bites hardest for a clothing seller: the apparel threshold moved
from Rs 1,000 to **Rs 2,500**, and above it the rate is now **18%**, not 12%.
Anyone carrying forward pre-2025 knowledge will get this wrong in both digits.

WHAT IS DELIBERATELY NOT A LOOKUP TABLE
---------------------------------------
It is tempting to map a 4-digit HSN to a rate. That is wrong for two of the
three categories this app serves:

  * Apparel and footwear are **price-banded** — the same HSN is 5% or 18%
    depending on the value of the individual piece (or pair).
  * Chapter 33 has **named carve-outs inside a heading** — 3304 is 18%, but
    face powder, kajal, kumkum, bindi and sindur within 3304 are 5%; 3305 is
    18% but hair oil, shampoo and mehendi are 5%.

So rate resolution is a small rule engine keyed on (HSN, unit value, carve-out),
not a dict. Adding a flat map later will silently mis-tax half the catalogue.

MONEY
-----
Everything is **integer paise**. Indian MRP is tax-inclusive by law (Legal
Metrology (Packaged Commodities) Rules, 2011 — the declared retail price
includes all taxes), so the taxable value is back-calculated OUT of the price
the shopper sees. Doing that in floats makes displayed totals drift a paisa away
from the printed MRP, which is the kind of bug that produces angry screenshots.

Section 170 of the CGST Act requires rounding to the nearest rupee, half-up,
**per tax head** — CGST and SGST round independently and can legitimately differ
by a rupee. That looks like a bug to sellers, so the invoice carries an explicit
Round Off line.

SOURCES OF DOUBT — flagged honestly rather than buried
------------------------------------------------------
`NEEDS_CA_REVIEW` below lists the three things a chartered accountant should
confirm before a seller relies on this for filing. They are in the code, not a
README, because that is where someone changing a rate will actually look.
"""
from __future__ import annotations

import re
from datetime import date

# --------------------------------------------------------------- disclaimers

NEEDS_CA_REVIEW = [
    "Imitation jewellery (HSN 7117) is set to 3%. Sources disagreed (3%, 12%, "
    "18%); the weight of evidence and the historical Schedule V position say 3%, "
    "but Schedule IV of the primary CBIC notification could not be read directly. "
    "A 6x error if wrong.",
    "The Rs 2,500 apparel threshold's treatment of discounts and multi-piece "
    "packs is not addressed by any source found. A 3-pack at Rs 2,800 and a "
    "Rs 3,200 dress discounted to Rs 2,400 both have real rate consequences.",
    "Threshold resolution on tax-inclusive prices is circular near the boundary. "
    "See THRESHOLD_RULE below for the convention this app adopts.",
]

THRESHOLD_RULE = """\
Between roughly Rs 2,625 and Rs 2,950 MRP the apparel threshold is circular:
assume 5% and the taxable value lands above Rs 2,500 (so it should be 18%);
assume 18% and it lands below (so it should be 5%).

This app's convention: **resolve the band using the taxable value computed at
the LOWER rate.** If that value exceeds the threshold, the higher rate applies.

Chosen because it is deterministic, monotonic in price, and errs toward the
higher rate — an under-collection is a liability the seller carries personally,
an over-collection is refundable. Printed on the invoice as a note so the
seller's accountant can see the assumption rather than reverse-engineer it."""


# --------------------------------------------------------------- state codes

STATES = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab",
    "04": "Chandigarh", "05": "Uttarakhand", "06": "Haryana", "07": "Delhi",
    "08": "Rajasthan", "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim",
    "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur", "15": "Mizoram",
    "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal",
    "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh",
    "24": "Gujarat", "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra", "29": "Karnataka", "30": "Goa", "31": "Lakshadweep",
    "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry", "35": "Andaman and Nicobar Islands",
    "36": "Telangana", "37": "Andhra Pradesh", "38": "Ladakh", "97": "Other Territory",
}
STATE_BY_NAME = {v.lower(): k for k, v in STATES.items()}

# Special-category states have a lower registration threshold.
SPECIAL_CATEGORY = {"11", "12", "13", "14", "15", "16", "17", "18", "02", "05"}


def state_code(name_or_code: str) -> str:
    s = (name_or_code or "").strip()
    if s in STATES:
        return s
    return STATE_BY_NAME.get(s.lower(), "")


def state_name(code: str) -> str:
    return STATES.get((code or "").strip(), "")


# --------------------------------------------------------------- GSTIN

_GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$")
_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin_check_digit(first14: str) -> str | None:
    """Luhn mod 36.

    The trailing `% 36` is load-bearing and is the single most copied-wrong line
    in every GSTIN validator on the internet. When `total % 36 == 0` the naive
    `36 - (total % 36)` yields 36, which indexes off the end of a 36-character
    alphabet; the popular JS implementation emits '[' and rejects a perfectly
    valid GSTIN. Do not 'simplify' this."""
    factor, total = 2, 0
    for ch in reversed(first14):
        cp = _CHARS.find(ch)
        if cp < 0:
            return None
        d = factor * cp
        factor = 1 if factor == 2 else 2
        total += d // 36 + d % 36
    return _CHARS[(36 - (total % 36)) % 36]


def valid_gstin(g: str) -> bool:
    g = (g or "").strip().upper()
    if not _GSTIN_RE.match(g):
        return False
    return gstin_check_digit(g[:14]) == g[14]


def gstin_state(g: str) -> str:
    """A well-formed GSTIN carries its own state code in the first two digits."""
    g = (g or "").strip().upper()
    return g[:2] if valid_gstin(g) else ""


def describe_gstin(g: str) -> dict:
    g = (g or "").strip().upper()
    if not g:
        return {"ok": False, "reason": "empty"}
    if not _GSTIN_RE.match(g):
        return {"ok": False, "reason": "A GSTIN is 15 characters: 2 digit state code, "
                                       "10 character PAN, entity digit, the letter Z, "
                                       "then a checksum."}
    if gstin_check_digit(g[:14]) != g[14]:
        return {"ok": False, "reason": "The checksum character does not match. "
                                       "Usually a typo in the PAN portion."}
    return {"ok": True, "state_code": g[:2], "state": state_name(g[:2]),
            "pan": g[2:12],
            "note": "Well-formed. This does not prove the number is registered "
                    "and active — only the GSTN portal can tell you that."}


# --------------------------------------------------------------- rate engine

SLABS = [0, 3, 5, 18, 40]

# Named carve-outs inside Chapter 33, where the heading rate is 18% but a
# specific list of products sits at 5%. Matched on the product name.
CH33_5PCT = {
    "3304": ["talcum", "face powder", "kajal", "kumkum", "bindi", "sindur", "alta"],
    "3305": ["hair oil", "shampoo", "mehendi", "mehandi", "henna"],
    "3307": ["shaving cream", "after shave", "aftershave", "agarbatti", "lotion"],
}

# Price-banded headings: (threshold in paise, low rate, high rate, unit word).
BANDED = {
    **{h: (250000, 5, 18, "piece") for h in ("61", "62", "63")},   # apparel & made-ups
    "64": (250000, 5, 18, "pair"),                                  # footwear
}

CATEGORY_HSN = {
    "clothing": "6109", "apparel": "6109", "garments": "6109",
    "footwear": "6403",
    "jewellery": "7117", "imitation jewellery": "7117",
    "gold jewellery": "7113", "silver jewellery": "7113",
    "perfume": "3303", "fragrance": "3303",
    "cosmetics": "3304", "skincare": "3304", "beauty": "3304",
    "haircare": "3305",
}


def suggest_hsn(category: str, name: str = "") -> str:
    blob = f"{category} {name}".lower()
    for key, hsn in CATEGORY_HSN.items():
        if key in blob:
            return hsn
    return ""


def resolve_rate(hsn: str, unit_value_paise: int, product_name: str = "",
                 inclusive: bool = True) -> dict:
    """The rate for ONE unit of a product. Returns {rate, why, banded}.

    `unit_value_paise` is the price of a single piece. When `inclusive` is True
    (the Indian default) the banded threshold is resolved per THRESHOLD_RULE."""
    h = re.sub(r"\D", "", hsn or "")
    if not h:
        return {"rate": 5, "why": "No HSN set — defaulted to 5%. Set an HSN to tax "
                                  "this correctly.", "banded": False, "assumed": True}

    ch = h[:2]
    head = h[:4]

    # Chapter 71 — jewellery, precious metal. Flat 3%, no bands.
    if ch == "71":
        return {"rate": 3, "why": f"HSN {head}, Chapter 71 (jewellery) — 3%.",
                "banded": False, "assumed": False}

    # Price-banded headings.
    if ch in BANDED:
        threshold, low, high, unit = BANDED[ch]
        if inclusive:
            # Resolve using the taxable value at the LOWER rate. See THRESHOLD_RULE.
            taxable_at_low = round(unit_value_paise * 100 / (100 + low))
            over = taxable_at_low > threshold
            basis = f"taxable value at {low}% is {rupees(taxable_at_low)}"
        else:
            over = unit_value_paise > threshold
            basis = f"sale value is {rupees(unit_value_paise)}"
        rate = high if over else low
        return {"rate": rate,
                "why": f"HSN {head}: {rate}% because {basis}, "
                       f"{'above' if over else 'at or below'} the "
                       f"{rupees(threshold)} per-{unit} threshold.",
                "banded": True, "threshold": threshold, "unit": unit, "assumed": False}

    # Chapter 33 carve-outs.
    if head in CH33_5PCT:
        blob = (product_name or "").lower()
        for term in CH33_5PCT[head]:
            if term in blob:
                return {"rate": 5, "why": f"HSN {head} is normally 18%, but "
                                          f"'{term}' is a named 5% exception.",
                        "banded": False, "assumed": False}
        return {"rate": 18, "why": f"HSN {head} — 18%.", "banded": False, "assumed": False}

    if head == "3306":
        return {"rate": 5, "why": "HSN 3306 (oral hygiene) — 5%.",
                "banded": False, "assumed": False}
    if ch == "33":
        return {"rate": 18, "why": f"HSN {head}, Chapter 33 — 18%.",
                "banded": False, "assumed": False}

    return {"rate": 18, "why": f"HSN {head} — defaulted to the 18% standard rate. "
                               f"Confirm this is right for your product.",
            "banded": False, "assumed": True}


# --------------------------------------------------------------- money

def rupees(paise: int) -> str:
    return f"Rs {paise // 100}.{paise % 100:02d}"


def split_inclusive(gross_paise: int, rate: int) -> tuple[int, int]:
    """Back out tax from a tax-inclusive price. Returns (taxable, tax) in paise."""
    taxable = round(gross_paise * 100 / (100 + rate))
    return taxable, gross_paise - taxable


def round_half_up(paise: int) -> int:
    """To the nearest rupee, half-up, per Section 170. Returns paise."""
    r, p = divmod(paise, 100)
    return (r + 1) * 100 if p >= 50 else r * 100


def place_of_supply(seller_state: str, delivery_state: str) -> dict:
    """Delivery address decides it — IGST Sec 10(1)(a): place of supply is where
    the movement of goods terminates. For an unregistered buyer, Sec 10(1)(ca)
    says the address on the invoice governs, and recording just the state name
    counts. So the delivery state is both the tax input and the legal record —
    which is why an order cannot reach invoicing without one."""
    s = state_code(seller_state)
    d = state_code(delivery_state)
    if not d:
        return {"ok": False, "kind": "", "reason":
                "No delivery state. Place of supply cannot be determined, and "
                "without it the invoice defaults to the seller's own state, "
                "which would misreport GSTR-1."}
    intra = bool(s) and s == d
    return {"ok": True, "kind": "intra" if intra else "inter",
            "seller_state": s, "delivery_state": d,
            "state_name": state_name(d),
            "heads": ["cgst", "sgst"] if intra else ["igst"]}


def compute_line(*, name: str, hsn: str, qty: int, unit_price_paise: int,
                 inclusive: bool, pos_kind: str) -> dict:
    """Tax for one invoice line. Rate is resolved on the UNIT value, because the
    apparel threshold is per piece — ten Rs 800 shirts on one bill are each 5%,
    they do not add up to a Rs 8,000 line at 18%."""
    r = resolve_rate(hsn, unit_price_paise, name, inclusive)
    rate = r["rate"]
    gross = unit_price_paise * qty
    if inclusive:
        taxable, tax = split_inclusive(gross, rate)
    else:
        taxable = gross
        tax = round(gross * rate / 100)

    line = {"name": name, "hsn": re.sub(r"\D", "", hsn or ""), "qty": qty,
            "unit_price": unit_price_paise, "gross": gross,
            "taxable": taxable, "rate": rate, "tax_total": tax,
            "rate_why": r["why"], "rate_assumed": r.get("assumed", False),
            "cgst": 0, "sgst": 0, "igst": 0}
    if pos_kind == "intra":
        # Half each. Split before rounding; rounding happens per head at invoice level.
        line["cgst"] = tax // 2
        line["sgst"] = tax - line["cgst"]
    else:
        line["igst"] = tax
    return line


# --------------------------------------------------------------- documents

DOC_TAX_INVOICE = "tax_invoice"
DOC_BILL_OF_SUPPLY = "bill_of_supply"
DOC_RECEIPT = "receipt"


def document_kind(seller: dict) -> dict:
    """Which document may this seller lawfully issue?

    Three, not one — and the difference is not cosmetic:

      Tax Invoice      registered, charging GST.
      Bill of Supply   REGISTERED but not charging tax (exempt supplies, or
                       composition scheme). Rule 49.
      Receipt          UNREGISTERED. CGST Sec 32(1): a person who is not
                       registered "shall not collect ... any amount by way of
                       tax". They have no GSTIN to print and are barred from the
                       tax system's documents entirely.

    The common mistake is giving an unregistered seller a Bill of Supply. That
    is a registered person's document. An unregistered seller issues a plain
    commercial receipt with no GSTIN, no tax line, and it must not be headed
    "Tax Invoice"."""
    gstin = (seller.get("gstin") or "").strip().upper()
    if not gstin:
        return {"kind": DOC_RECEIPT, "title": "Receipt", "charges_tax": False,
                "why": "No GSTIN on file. An unregistered seller cannot collect "
                       "GST (CGST Sec 32(1)) and must not issue a document "
                       "headed 'Tax Invoice'."}
    if not valid_gstin(gstin):
        return {"kind": DOC_RECEIPT, "title": "Receipt", "charges_tax": False,
                "why": "The GSTIN on file does not pass its checksum, so it is "
                       "treated as absent. Fix it in Settings to issue tax invoices."}
    if seller.get("composition"):
        return {"kind": DOC_BILL_OF_SUPPLY, "title": "Bill of Supply",
                "charges_tax": False,
                "declaration": "Composition taxable person, not eligible to "
                               "collect tax on supplies.",
                "why": "Composition dealers issue a Bill of Supply (Rule 49) and "
                       "may not charge GST."}
    return {"kind": DOC_TAX_INVOICE, "title": "Tax Invoice", "charges_tax": True,
            "why": "Registered and charging GST."}


def registration_warning(seller: dict, ships_outside_state: bool) -> dict | None:
    """The single most valuable compliance thing this app can say.

    Section 24(i) compels registration for INTER-STATE supply of goods from the
    first rupee — no turnover floor, and the general services relief does not
    extend to goods. Since a D2C seller ships nationwide by default, the Rs 40
    lakh threshold protects almost nobody. A seller who believes they are safely
    under the threshold while shipping to the next state is in breach from their
    first order, and will not find out until it is expensive."""
    if (seller.get("gstin") or "").strip():
        return None
    if not ships_outside_state:
        return {"level": "info",
                "text": "You are selling without a GSTIN. That is fine while you "
                        "ship only within your own state and stay under Rs 40 lakh "
                        "a year. Shipping to another state changes this immediately."}
    return {"level": "blocking",
            "text": "You have no GSTIN but your store accepts orders from other "
                    "states. Section 24(i) of the CGST Act requires GST "
                    "registration for inter-state sale of goods from the first "
                    "rupee — there is no turnover threshold for this. Either "
                    "register, or restrict delivery to your own state.",
            "actions": ["Add my GSTIN", "Restrict delivery to my state"]}


# --------------------------------------------------------------- numbering

def financial_year(d: date | None = None) -> str:
    """Indian FY runs 1 April - 31 March. Returns '2627' for FY 2026-27."""
    d = d or date.today()
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start % 100:02d}{(start + 1) % 100:02d}"


def invoice_number(series: str, seq: int, d: date | None = None) -> str:
    """Rule 46(b): at most 16 characters, alphanumerics plus hyphen and slash
    only, unique within a financial year.

    'INV/26-27/000123' is 17 characters and therefore ILLEGAL — the extra hyphen
    is what pushes it over. 'INV/2627/000123' is 15 and safe."""
    series = re.sub(r"[^A-Za-z0-9]", "", series or "INV")[:3].upper() or "INV"
    num = f"{series}/{financial_year(d)}/{seq:06d}"
    if len(num) > 16:
        num = f"{series}/{financial_year(d)}/{seq:04d}"[:16]
    return num


def valid_invoice_number(n: str) -> bool:
    return bool(n) and len(n) <= 16 and re.match(r"^[A-Za-z0-9/\-]+$", n) is not None
