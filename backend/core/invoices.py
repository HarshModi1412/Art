"""
Tax invoices, bills of supply and plain receipts — the records, not the maths.

Rate and place-of-supply logic lives in `gst.py`. This module is about the
document: numbering it legally, storing it so it can never silently vanish, and
producing the two exports a seller's accountant actually asks for.

TWO RULES THAT LOOK LIKE OVER-ENGINEERING AND ARE NOT
-----------------------------------------------------
1. **Numbers are allocated at ISSUE, never at checkout.** Rule 46(b) requires a
   consecutive series. If a number were reserved when a cart was created, every
   abandoned cart would punch a permanent hole in the sequence, and gaps in an
   invoice series are exactly what a GST audit looks for.

2. **Invoices are never hard-deleted.** GSTR-1 Table 13 requires the number
   RANGE issued and the COUNT of cancelled documents. Delete a row and that
   table becomes unproducible for the rest of the financial year. Cancelling
   sets a status and keeps everything.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone

from backend.core import gst, user_store

KEY = "gst_invoices"
SETTINGS_KEY = "gst_settings"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _email(e: str) -> str:
    return (e or "").strip().lower()


# --------------------------------------------------------------- settings

def blank_settings() -> dict:
    return {
        "gstin": "", "legal_name": "", "trade_name": "",
        "state": "", "composition": False,
        "pickup_address": {"line1": "", "line2": "", "city": "", "state": "", "pincode": ""},
        "series": "INV",
        "prices_include_tax": True,     # the Indian default, and legally required for MRP
        "default_hsn": "",
        "ships_outside_state": True,
        "place_of_supply_recorded": True,
    }


def get_settings(email: str) -> dict:
    s = blank_settings()
    s.update(user_store.get_key(_email(email), SETTINGS_KEY, {}) or {})
    return s


def save_settings(email: str, patch: dict) -> dict:
    s = get_settings(email)
    for k, v in (patch or {}).items():
        if k in s:
            s[k] = v
    s["gstin"] = (s.get("gstin") or "").strip().upper()
    # A GSTIN carries its own state code; trusting the typed state over the
    # number is how invoices end up with the wrong place of supply.
    if gst.valid_gstin(s["gstin"]):
        s["state"] = gst.state_name(gst.gstin_state(s["gstin"])) or s.get("state") or ""
    user_store.set_key(_email(email), SETTINGS_KEY, s)
    return s


def settings_status(email: str) -> dict:
    s = get_settings(email)
    doc = gst.document_kind(s)
    warn = gst.registration_warning(s, bool(s.get("ships_outside_state")))
    missing = []
    if not (s.get("legal_name") or "").strip():
        missing.append("legal name")
    if not (s.get("pickup_address") or {}).get("pincode"):
        missing.append("pickup address")
    return {"settings": s, "document": doc, "warning": warn,
            "gstin_check": gst.describe_gstin(s.get("gstin") or "") if s.get("gstin") else None,
            "missing": missing,
            "ready": not missing,
            "needs_ca_review": gst.NEEDS_CA_REVIEW,
            "threshold_rule": gst.THRESHOLD_RULE}


# --------------------------------------------------------------- storage

def _all(email: str) -> list[dict]:
    return user_store.get_key(_email(email), KEY, []) or []


def _save(email: str, rows: list[dict]) -> None:
    user_store.set_key(_email(email), KEY, rows)


def _next_seq(rows: list[dict], fy: str) -> int:
    """Per financial year, per seller. Counts cancelled invoices too — a
    cancelled number is spent, not returned to the pool."""
    used = [r.get("seq", 0) for r in rows if r.get("fy") == fy]
    return (max(used) + 1) if used else 1


# --------------------------------------------------------------- issue

def build_from_order(email: str, order: dict) -> dict:
    """Compute an invoice for an order WITHOUT allocating a number.

    Used for the preview a seller sees before pressing Issue, and by the tests.
    Nothing here touches storage, so it is safe to call as often as you like."""
    s = get_settings(email)
    doc = gst.document_kind(s)
    inclusive = bool(s.get("prices_include_tax", True))

    delivery_state = ((order.get("address") or {}).get("state") or "").strip()
    pos = gst.place_of_supply(s.get("state") or "", delivery_state)

    lines, blockers = [], []
    if not pos["ok"]:
        blockers.append(pos["reason"])

    for it in (order.get("items") or []):
        qty = max(1, int(it.get("qty") or 1))
        unit_paise = int(round(float(it.get("price") or 0) * 100))
        hsn = it.get("hsn") or s.get("default_hsn") or ""
        if doc["charges_tax"]:
            line = gst.compute_line(name=it.get("name") or "", hsn=hsn, qty=qty,
                                    unit_price_paise=unit_paise, inclusive=inclusive,
                                    pos_kind=pos.get("kind") or "intra")
        else:
            gross = unit_paise * qty
            line = {"name": it.get("name") or "", "hsn": re.sub(r"\D", "", hsn),
                    "qty": qty, "unit_price": unit_paise, "gross": gross,
                    "taxable": gross, "rate": 0, "tax_total": 0,
                    "cgst": 0, "sgst": 0, "igst": 0,
                    "rate_why": doc["why"], "rate_assumed": False}
        if line.get("rate_assumed"):
            blockers.append(f"No HSN for '{line['name']}' — the rate is a guess.")
        lines.append(line)

    shipping_paise = int(round(float(order.get("shipping") or 0) * 100))
    heads = {"cgst": 0, "sgst": 0, "igst": 0}
    taxable = 0
    for ln in lines:
        taxable += ln["taxable"]
        for h in heads:
            heads[h] += ln[h]

    # Section 170: round each head half-up, independently. CGST and SGST can
    # legitimately land a rupee apart, which looks like a bug and is not.
    rounded = {h: gst.round_half_up(v) for h, v in heads.items()}
    tax_total = sum(rounded.values())
    grand_raw = taxable + sum(heads.values()) + shipping_paise
    grand = gst.round_half_up(grand_raw)

    return {
        "document": doc, "place_of_supply": pos, "inclusive": inclusive,
        "lines": lines, "taxable": taxable, "shipping": shipping_paise,
        "heads": rounded, "heads_exact": heads, "tax_total": tax_total,
        "round_off": grand - grand_raw, "grand_total": grand,
        "blockers": sorted(set(blockers)),
        "seller": {k: s.get(k) for k in ("gstin", "legal_name", "trade_name",
                                          "state", "pickup_address", "composition")},
        "buyer": {"name": order.get("customer_name") or "",
                  "phone": order.get("phone") or "",
                  "address": order.get("address") or {},
                  "state": delivery_state,
                  "state_code": gst.state_code(delivery_state)},
        "order_no": order.get("order_no") or "", "order_id": order.get("id") or "",
    }


def issue(email: str, order: dict, force: bool = False) -> dict:
    """Allocate a number and store the invoice. Idempotent per order."""
    email = _email(email)
    rows = _all(email)
    existing = next((r for r in rows if r.get("order_id") == order.get("id")
                     and r.get("status") != "cancelled"), None)
    if existing:
        return existing

    built = build_from_order(email, order)
    if built["blockers"] and not force:
        return {"error": "blocked", "blockers": built["blockers"], "preview": built}

    s = get_settings(email)
    today = date.today()
    fy = gst.financial_year(today)
    seq = _next_seq(rows, fy)
    number = gst.invoice_number(s.get("series") or "INV", seq, today)

    inv = dict(built)
    inv.update({"id": f"{fy}-{seq:06d}", "number": number, "seq": seq, "fy": fy,
                "issued_at": _now(), "date": today.isoformat(),
                "status": "issued", "cancelled_at": "", "cancel_reason": "",
                "irn": None, "qr_payload": None})
    rows.append(inv)
    _save(email, rows)
    return inv


def cancel(email: str, invoice_id: str, reason: str = "") -> dict:
    """Soft cancel. The number stays spent and the row stays in the series,
    because GSTR-1 Table 13 needs both."""
    rows = _all(email)
    for r in rows:
        if r.get("id") == invoice_id:
            r["status"] = "cancelled"
            r["cancelled_at"] = _now()
            r["cancel_reason"] = str(reason or "")[:200]
            _save(_email(email), rows)
            return r
    return {"error": "not found"}


def get(email: str, invoice_id: str) -> dict | None:
    return next((r for r in _all(email) if r.get("id") == invoice_id), None)


def for_order(email: str, order_id: str) -> dict | None:
    return next((r for r in _all(email)
                 if r.get("order_id") == order_id and r.get("status") != "cancelled"), None)


def listing(email: str, fy: str = "") -> list[dict]:
    rows = _all(email)
    if fy:
        rows = [r for r in rows if r.get("fy") == fy]
    return sorted(rows, key=lambda r: r.get("seq", 0), reverse=True)


# --------------------------------------------------------------- GSTR-1

B2CL_THRESHOLD_PAISE = 10000000        # Rs 1 lakh, cut from Rs 2.5 lakh in Aug 2024


def gstr1(email: str, fy: str = "") -> dict:
    """The shape a seller's accountant needs.

    For a typical D2C seller almost everything lands in Table 7 (B2CS) as a
    rate x state grid, so the core of this is one group-by. Table 13 is the one
    people forget, and the reason invoices are never hard-deleted."""
    rows = [r for r in listing(email, fy) if r.get("status") == "issued"]
    cancelled = [r for r in listing(email, fy) if r.get("status") == "cancelled"]

    b2cl, b2cs = [], {}
    hsn: dict[tuple, dict] = {}

    for r in rows:
        pos = r.get("place_of_supply") or {}
        st = pos.get("delivery_state") or ""
        inter = pos.get("kind") == "inter"
        total = r.get("grand_total", 0)

        if inter and total > B2CL_THRESHOLD_PAISE:
            b2cl.append({"number": r["number"], "date": r["date"],
                         "value": total, "pos": st,
                         "state": gst.state_name(st),
                         "igst": (r.get("heads") or {}).get("igst", 0)})
        else:
            for ln in r.get("lines", []):
                key = (st, ln["rate"])
                b = b2cs.setdefault(key, {"pos": st, "state": gst.state_name(st),
                                          "rate": ln["rate"], "taxable": 0,
                                          "cgst": 0, "sgst": 0, "igst": 0})
                b["taxable"] += ln["taxable"]
                for h in ("cgst", "sgst", "igst"):
                    b[h] += ln[h]

        for ln in r.get("lines", []):
            k = (ln["hsn"], ln["rate"])
            h = hsn.setdefault(k, {"hsn": ln["hsn"], "rate": ln["rate"],
                                   "qty": 0, "taxable": 0, "tax": 0})
            h["qty"] += ln["qty"]
            h["taxable"] += ln["taxable"]
            h["tax"] += ln["tax_total"]

    nums = sorted(r["number"] for r in listing(email, fy))
    return {
        "fy": fy or gst.financial_year(),
        "b2cl": sorted(b2cl, key=lambda x: x["number"]),
        "b2cs": sorted(b2cs.values(), key=lambda x: (x["state"], x["rate"])),
        "hsn_summary": sorted(hsn.values(), key=lambda x: (x["hsn"], x["rate"])),
        "documents_issued": {
            "series_from": nums[0] if nums else "",
            "series_to": nums[-1] if nums else "",
            "total": len(nums), "cancelled": len(cancelled)},
        "note": "B2CL threshold is Rs 1 lakh (reduced from Rs 2.5 lakh, "
                "Notification 12/2024-CT). Everything else is consolidated into "
                "B2CS as a rate x state grid.",
    }


def gstr1_csv(email: str, fy: str = "") -> str:
    d = gstr1(email, fy)
    out = ["Table,Place of supply,Rate,Taxable value,CGST,SGST,IGST,Invoice,Date"]
    r2 = lambda p: f"{p / 100:.2f}"                                  # noqa: E731
    for b in d["b2cs"]:
        out.append(f"B2CS,{b['state']},{b['rate']}%,{r2(b['taxable'])},"
                   f"{r2(b['cgst'])},{r2(b['sgst'])},{r2(b['igst'])},,")
    for b in d["b2cl"]:
        out.append(f"B2CL,{b['state']},,{r2(b['value'])},,,{r2(b['igst'])},"
                   f"{b['number']},{b['date']}")
    out.append("")
    out.append("HSN summary,,,,,,,,")
    out.append("HSN,Rate,Quantity,Taxable value,Tax,,,,")
    for h in d["hsn_summary"]:
        out.append(f"{h['hsn']},{h['rate']}%,{h['qty']},{r2(h['taxable'])},{r2(h['tax'])},,,,")
    out.append("")
    di = d["documents_issued"]
    out.append("Documents issued,,,,,,,,")
    out.append(f"From,{di['series_from']},To,{di['series_to']},"
               f"Total,{di['total']},Cancelled,{di['cancelled']},")
    return "\n".join(out)
