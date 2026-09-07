"""
Cancellation analysis — built from the seller's own storefront Orders.

WHY THIS SHAPE
--------------
A cancelled order is not one thing. Killing an order before it is packed costs
almost nothing; the same order cancelled after it has shipped costs forward
freight, reverse freight, the COD handling fee and a week of blocked stock. So
every number here is split by the stage the order had reached, and every number
is shown in rupees as well as per cent — because the percentages are small and
the rupees are not.

Two things this deliberately does NOT do:

* It does not guess a reason. A cancellation with no reason is counted as
  "Not recorded" and shown as its own bar, because a reason breakdown built on
  half the data is a confident lie. `reason_coverage` is reported so the seller
  can see how much of the picture they actually have.

* It does not quote a percentage on a handful of orders. Below MIN_DENOMINATOR
  it reports counts and rupees only. At 50-500 orders a month, "this product
  has a 40% cancellation rate" usually means two cancellations out of five.

Scope: this reads the storefront's own orders, where the app knows the real
status history. Marketplace cancellations would need their own import — the
functions here take a list of order dicts, so that stays a small change.
"""
from __future__ import annotations

import pandas as pd

MIN_DENOMINATOR = 20        # below this, counts and rupees only — never a rate

# The stage an order had reached when it was cancelled. Cost rises steeply down
# this list, which is why it is the primary split rather than a footnote.
STAGE_ORDER = ["before_packing", "packed", "after_dispatch", "unknown"]
STAGE_LABELS = {
    "before_packing": "Before packing",
    "packed": "Packed, not shipped",
    "after_dispatch": "After dispatch",
    "unknown": "Stage not recorded",
}
STAGE_NOTE = {
    "before_packing": "Costs you almost nothing — just the lost sale.",
    "packed": "Packing materials and labour are already spent.",
    "after_dispatch": "The expensive one: freight out, freight back, and stock "
                      "tied up for a week.",
    "unknown": "These orders were cancelled before the app started recording "
               "the stage.",
}

# Offered when the seller cancels an order. Kept short on purpose — a long list
# gets ignored and everything lands on "Other", which is how reason data dies.
REASONS = [
    {"id": "out_of_stock",   "label": "Out of stock",              "fault": "seller"},
    {"id": "pricing_error",  "label": "Wrong price or listing",    "fault": "seller"},
    {"id": "cannot_ship",    "label": "Can't ship in time",        "fault": "seller"},
    {"id": "unserviceable",  "label": "Address not serviceable",   "fault": "courier"},
    {"id": "customer_asked", "label": "Customer changed their mind", "fault": "buyer"},
    {"id": "unreachable",    "label": "Customer not reachable",    "fault": "buyer"},
    {"id": "cod_refused",    "label": "Refused / cash not ready",  "fault": "buyer"},
    {"id": "duplicate",      "label": "Duplicate order",           "fault": "buyer"},
    {"id": "suspect",        "label": "Looked like a fake order",  "fault": "buyer"},
    {"id": "damaged",        "label": "Damaged before dispatch",   "fault": "seller"},
    {"id": "other",          "label": "Something else",            "fault": "unknown"},
]
REASON_LABEL = {r["id"]: r["label"] for r in REASONS}
REASON_FAULT = {r["id"]: r["fault"] for r in REASONS}
FAULT_LABELS = {"seller": "Your side", "buyer": "Customer's side",
                "courier": "Courier / address", "unknown": "Not recorded"}


def _money(v) -> float:
    try:
        return round(float(v or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _rate(part: int, whole: int):
    """A percentage, or None when the denominator is too small to mean anything."""
    if not whole or whole < MIN_DENOMINATOR:
        return None
    return round(part / whole * 100, 1)


def stage_of(order: dict) -> str:
    """How far an order had got before it was cancelled, from its own history."""
    history = order.get("history") or []
    reached = [h.get("status") for h in history if isinstance(h, dict)]
    if "shipped" in reached:
        return "after_dispatch"
    if "packed" in reached:
        return "packed"
    if reached:
        return "before_packing"
    return "unknown"


def _bucket(rows: list[dict], key_fn, label_fn=None) -> list[dict]:
    out: dict = {}
    for o in rows:
        k = key_fn(o)
        if k is None:
            continue
        b = out.setdefault(k, {"key": k, "label": (label_fn or str)(k),
                               "orders": 0, "value": 0.0})
        b["orders"] += 1
        b["value"] += _money(o.get("total"))
    rows_out = sorted(out.values(), key=lambda b: b["value"], reverse=True)
    for b in rows_out:
        b["value"] = _money(b["value"])
    return rows_out


def analyse(orders: list[dict]) -> dict:
    """The whole picture, from a list of storefront orders."""
    orders = [o for o in (orders or []) if isinstance(o, dict)]
    total = len(orders)
    cancelled = [o for o in orders if o.get("status") == "cancelled"]
    live = [o for o in orders if o.get("status") != "cancelled"]

    gross = _money(sum(_money(o.get("total")) for o in orders))
    lost = _money(sum(_money(o.get("total")) for o in cancelled))
    net = _money(gross - lost)

    result = {
        "available": total > 0,
        "orders": total,
        "cancelled": len(cancelled),
        "delivered_or_live": len(live),
        "rate": _rate(len(cancelled), total),
        "gross_value": gross,
        "cancelled_value": lost,
        "net_value": net,
        "min_denominator": MIN_DENOMINATOR,
        "enough_data": total >= MIN_DENOMINATOR,
        "reasons": [],
        "reason_coverage": None,
        "faults": [],
        "stages": [],
        "by_payment": [],
        "by_product": [],
        "trend": {"x": [], "cancelled": [], "orders": []},
        "note": ("Cancelled orders are already excluded from your sales figures "
                 "and from every insight built on them — this page is the only "
                 "place they are counted."),
    }
    if not cancelled:
        return result

    # ---- stage ----
    staged = _bucket(cancelled, stage_of, lambda k: STAGE_LABELS.get(k, k))
    order_index = {s: i for i, s in enumerate(STAGE_ORDER)}
    staged.sort(key=lambda b: order_index.get(b["key"], 99))
    for b in staged:
        b["note"] = STAGE_NOTE.get(b["key"], "")
        b["share"] = _rate(b["orders"], len(cancelled))
    result["stages"] = staged

    # ---- reason, and how much of it we actually have ----
    with_reason = [o for o in cancelled if (o.get("cancel_reason") or "").strip()]
    result["reason_coverage"] = (round(len(with_reason) / len(cancelled) * 100, 1)
                                 if cancelled else None)
    reasons = _bucket(
        cancelled,
        lambda o: (o.get("cancel_reason") or "").strip() or "not_recorded",
        lambda k: REASON_LABEL.get(k, "Not recorded" if k == "not_recorded" else k),
    )
    for b in reasons:
        b["share"] = _rate(b["orders"], len(cancelled))
        b["fault"] = REASON_FAULT.get(b["key"], "unknown")
    result["reasons"] = reasons

    # ---- whose side it was on ----
    faults = _bucket(
        cancelled,
        lambda o: REASON_FAULT.get((o.get("cancel_reason") or "").strip(), "unknown"),
        lambda k: FAULT_LABELS.get(k, k),
    )
    for b in faults:
        b["share"] = _rate(b["orders"], len(cancelled))
    result["faults"] = faults

    # ---- payment method: the single most informative cut in India ----
    pay = {}
    for o in orders:
        k = (o.get("payment") or "cod").lower()
        p = pay.setdefault(k, {"key": k, "label": "Cash on delivery" if k == "cod" else "Paid online",
                               "orders": 0, "cancelled": 0, "value": 0.0})
        p["orders"] += 1
        if o.get("status") == "cancelled":
            p["cancelled"] += 1
            p["value"] += _money(o.get("total"))
    for p in pay.values():
        p["rate"] = _rate(p["cancelled"], p["orders"])
        p["value"] = _money(p["value"])
    result["by_payment"] = sorted(pay.values(), key=lambda p: -p["orders"])

    # ---- which products get cancelled ----
    prod = {}
    for o in cancelled:
        for it in (o.get("items") or []):
            name = str(it.get("name") or "").strip()
            if not name:
                continue
            b = prod.setdefault(name, {"key": name, "label": name, "orders": 0, "value": 0.0})
            b["orders"] += 1
            b["value"] += _money(it.get("line_total"))
    result["by_product"] = sorted(
        ({**b, "value": _money(b["value"])} for b in prod.values()),
        key=lambda b: b["value"], reverse=True)[:10]

    # ---- trend, weekly (daily is noise at this volume) ----
    try:
        df = pd.DataFrame([{
            "date": pd.to_datetime(o.get("created_at"), errors="coerce"),
            "cancelled": 1 if o.get("status") == "cancelled" else 0,
        } for o in orders]).dropna(subset=["date"])
        if len(df):
            wk = df.set_index("date").resample("W").agg(orders=("cancelled", "size"),
                                                        cancelled=("cancelled", "sum"))
            result["trend"] = {
                "x": wk.index.strftime("%d %b").tolist(),
                "orders": wk["orders"].astype(int).tolist(),
                "cancelled": wk["cancelled"].astype(int).tolist(),
            }
    except Exception:  # noqa: BLE001 — a chart must never take the page down
        pass

    return result


def headline(res: dict) -> str:
    """One sentence for the top of the page. Rupees first: the percentage is
    small and forgettable, the money is neither."""
    if not res.get("available"):
        return "No orders on your website yet."
    n, val = res["cancelled"], res["cancelled_value"]
    if not n:
        return "Nothing cancelled. Every order you have taken is still live."
    rate = res.get("rate")
    tail = f" — {rate}% of your orders" if rate is not None else ""
    worst = next((s for s in res.get("stages") or []
                  if s["key"] == "after_dispatch"), None)
    extra = ""
    if worst and worst["orders"]:
        extra = (f" {worst['orders']} of them had already shipped, which is where "
                 f"the real money goes.")
    return (f"₹{val:,.0f} cancelled across {n} order{'s' if n != 1 else ''}{tail}."
            + extra)
