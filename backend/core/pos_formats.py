"""
POS export fingerprinting.

Every major POS lets the OWNER export their own sales report as CSV/Excel from
their own dashboard. That path needs no partner approval, no API key, and no
integration deal — it works today. What it *did* need was the owner fiddling
with column mapping.

This module removes that step: it fingerprints the export by its column
signature, and if it recognises the POS it returns a ready-made mapping plus a
friendly label ("Looks like a PetPooja export — mapped it for you").

Adding a new POS = adding one entry to SIGNATURES. No other code changes.

IMPORTANT HONESTY NOTE: these signatures are built from real export files we
have seen and from column names published in vendor help docs. Report layouts
differ by POS version, by which report the owner picks, and by region. So a
match is treated as a *suggestion the user can override*, never as gospel —
detection failing simply falls back to the normal auto-mapper.
"""
import re

import pandas as pd


def _norm(col: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(col).lower())


# Each signature:
#   required : columns that MUST be present (normalized) for a match
#   hints    : extra columns that raise confidence (not required)
#   mapping  : canonical role -> the export's column name (normalized)
#   label    : what we tell the user
#   note     : any caveat worth surfacing
SIGNATURES: list[dict] = [
    {
        "id": "petpooja_itemwise",
        "label": "PetPooja — item-wise sales report",
        "required": ["invoiceno", "itemname", "finaltotal"],
        "hints": ["tableno", "servername", "covers", "hsn", "variation", "subtotal"],
        "mapping": {
            "date": "date", "order_id": "invoiceno", "product": "itemname",
            "category": "category", "subcategory": "variation",
            "quantity": "qty", "amount": "finaltotal",
        },
        "note": "Revenue read from 'Final Total' (the line total incl. tax/discount), not unit Price.",
    },
    {
        "id": "petpooja_orderwise",
        "label": "PetPooja — order-wise sales report",
        "required": ["invoiceno", "grosstotal"],
        "hints": ["tableno", "servername", "covers", "paymenttype", "nettotal"],
        "mapping": {
            "date": "date", "order_id": "invoiceno", "amount": "grosstotal",
            "customer_name": "customername", "customer_id": "phone",
        },
        "note": "Order-level export: item and category insights need the item-wise report instead.",
    },
    {
        "id": "toast_orderdetails",
        "label": "Toast — order details export",
        "required": ["orderid", "menuitem"],
        "hints": ["checkid", "serviceareas", "server", "diningoption", "netprice", "guestcount"],
        "mapping": {
            "date": "openeddate", "order_id": "orderid", "product": "menuitem",
            "category": "menugroup", "subcategory": "menusubgroup",
            "quantity": "qty", "amount": "netprice",
        },
        "note": None,
    },
    {
        "id": "square_items",
        "label": "Square — item sales export",
        "required": ["item", "grosssales"],
        "hints": ["transactionid", "netsales", "category", "qty", "modifiersapplied"],
        "mapping": {
            "date": "date", "order_id": "transactionid", "product": "item",
            "category": "category", "quantity": "qty", "amount": "netsales",
        },
        "note": "Uses Net Sales (after discounts) as revenue.",
    },
    {
        "id": "posist_itemwise",
        "label": "Posist / Restroworks — item-wise sales",
        "required": ["billno", "itemname"],
        "hints": ["outletname", "itemcategory", "itemtotal", "grossamount", "netamount"],
        "mapping": {
            "date": "date", "order_id": "billno", "product": "itemname",
            "category": "itemcategory", "quantity": "quantity", "amount": "netamount",
        },
        "note": None,
    },
]


def detect_format(df: pd.DataFrame) -> dict | None:
    """Identify the POS export by its column signature.

    Returns {"id", "label", "note", "mapping", "confidence", "matched_hints"}
    or None when nothing matches confidently. The mapping uses the file's REAL
    column names (not normalized) so it can be applied directly.
    """
    norm_to_real = {_norm(c): str(c) for c in df.columns}
    present = set(norm_to_real)

    best = None
    for sig in SIGNATURES:
        if not all(r in present for r in sig["required"]):
            continue
        hits = sum(1 for h in sig["hints"] if h in present)
        # confidence: required columns are the gate, hints break ties
        confidence = round(min(0.6 + 0.08 * hits, 0.98), 2)
        if best is None or confidence > best["confidence"]:
            mapping = {}
            for role, col_norm in sig["mapping"].items():
                real = norm_to_real.get(col_norm)
                if real:
                    mapping[role] = real
            best = {
                "id": sig["id"], "label": sig["label"], "note": sig["note"],
                "mapping": mapping, "confidence": confidence,
                "matched_hints": [h for h in sig["hints"] if h in present],
            }
    return best


def describe_supported() -> list[dict]:
    """For the UI: which POS exports we recognise out of the box."""
    seen, out = set(), []
    for sig in SIGNATURES:
        vendor = sig["label"].split("—")[0].strip()
        if vendor not in seen:
            seen.add(vendor)
            out.append({"vendor": vendor, "report": sig["label"]})
    return out
