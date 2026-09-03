"""
Smart CafeX — Supply Management.

Sits on top of the account's saved Sales data (backend.core.smart) and turns a
simple inventory list into reorder decisions:

    current stock  ─┐
    sales history ──┼─▶ average daily usage ─▶ reorder point
    lead time     ──┘        (usage × lead time + safety stock) ─▶ below-ROP?

When one or more items are at/below their reorder point the account gets a
single "Reorder" card in the Approval panel. Approving it (or the module's
"Generate purchase order" button) builds a Purchase Order with a suggested
reorder quantity per item, saves the PO to the account (backend) and returns
an Excel for download.

Inventory items, purchase orders and the last-handled reorder signature all
live in the user's JSON state via user_store — no new tables required.

`smart` is imported for load_sales only; it is used at call time, never at
import time, so the smart <-> supply pair does not deadlock on import.
"""
from __future__ import annotations

import io
import math
import secrets

import pandas as pd

from backend.core import smart, user_store

INVENTORY_KEY = "smart_inventory"
PO_KEY = "smart_purchase_orders"
REORDER_SIG_KEY = "smart_reorder_sig"


# ---------------------------------------------------------
# small helpers
# ---------------------------------------------------------
def _norm(s) -> str:
    return str(s or "").strip().lower()


def _num(v, default=0.0) -> float:
    try:
        if v is None or v == "":
            return float(default)
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _int(v, default=0) -> int:
    return int(round(_num(v, default)))


def _blank(v) -> bool:
    return v is None or v == ""


# ---------------------------------------------------------
# inventory CRUD (stored as a list in the account state)
# ---------------------------------------------------------
def get_inventory(email: str) -> list[dict]:
    items = user_store.get_key(email, INVENTORY_KEY, []) or []
    return items if isinstance(items, list) else []


def _save_inventory(email: str, items: list[dict]) -> None:
    user_store.set_key(email, INVENTORY_KEY, items)


def upsert_item(email: str, item: dict) -> list[dict]:
    items = get_inventory(email)
    iid = item.get("id")
    clean = {
        "id": iid or secrets.token_hex(4),
        "sku": str(item.get("sku", "")).strip()[:120],
        "current_stock": _num(item.get("current_stock"), 0),
        "lead_time_days": _num(item.get("lead_time_days"), 0),
        "safety_stock": _num(item.get("safety_stock"), 0),
        "reorder_qty": (None if _blank(item.get("reorder_qty")) else _num(item.get("reorder_qty"))),
        "unit_cost": (None if _blank(item.get("unit_cost")) else _num(item.get("unit_cost"))),
        "supplier": str(item.get("supplier", "")).strip()[:120],
    }
    if not clean["sku"]:
        raise ValueError("Item name (SKU) is required.")
    if iid and any(it.get("id") == iid for it in items):
        items = [clean if it.get("id") == iid else it for it in items]
    else:
        items.append(clean)
    _save_inventory(email, items)
    return items


def delete_item(email: str, iid: str) -> list[dict]:
    items = [it for it in get_inventory(email) if it.get("id") != iid]
    _save_inventory(email, items)
    return items


# ---------------------------------------------------------
# correlate with sales -> average daily usage
# ---------------------------------------------------------
def _sales_usage(email: str) -> tuple[dict, dict]:
    """({normalised product -> avg units/day}, meta) from the account's saved
    Sales data: total units sold per product over the dataset's day span."""
    txns = smart.load_sales(email)
    if txns is None or not len(txns) or "product" not in getattr(txns, "columns", []):
        return {}, {"has_sales": False, "days_span": 0}
    df = txns.copy()
    days = 1
    if "date" in df.columns:
        dts = pd.to_datetime(df["date"], errors="coerce").dropna()
        if len(dts):
            days = max(1, int((dts.max().normalize() - dts.min().normalize()).days) + 1)
    qty_col = "quantity" if "quantity" in df.columns else None
    usage: dict[str, float] = {}
    for prod, g in df.groupby(df["product"].map(_norm)):
        if not prod:
            continue
        units = float(pd.to_numeric(g[qty_col], errors="coerce").fillna(0).sum()) if qty_col else float(len(g))
        usage[prod] = units / days
    return usage, {"has_sales": True, "days_span": int(days)}


def _enrich(item: dict, usage: dict) -> dict:
    avg_daily = float(usage.get(_norm(item.get("sku")), 0.0))
    lead = _num(item.get("lead_time_days"), 0)
    safety = _num(item.get("safety_stock"), 0)
    current = _num(item.get("current_stock"), 0)
    reorder_point = int(math.ceil(avg_daily * lead + safety))
    below = reorder_point > 0 and current <= reorder_point
    if not _blank(item.get("reorder_qty")):
        order_qty = max(1, _int(item.get("reorder_qty")))
    else:
        # bring stock back above the reorder point plus one lead-time cycle
        order_qty = int(max(1, math.ceil(reorder_point - current + avg_daily * lead)))
    days_cover = round(current / avg_daily, 1) if avg_daily > 0 else None
    out = dict(item)
    out.update({
        "avg_daily_sales": round(avg_daily, 2),
        "reorder_point": reorder_point,
        "below_reorder": bool(below),
        "suggested_qty": order_qty if below else 0,
        "days_of_cover": days_cover,
    })
    return out


def compute_inventory(email: str) -> dict:
    usage, meta = _sales_usage(email)
    rows = [_enrich(it, usage) for it in get_inventory(email)]
    rows.sort(key=lambda r: (not r["below_reorder"], _norm(r.get("sku"))))
    below = [r for r in rows if r["below_reorder"]]
    return {"items": rows, "below": below, "meta": meta, "n_below": len(below)}


def import_products_from_sales(email: str) -> list[dict]:
    """Seed inventory rows for any product in the sales data not already tracked
    (blank stock, a default 7-day lead time, for the owner to adjust)."""
    txns = smart.load_sales(email)
    if txns is None or "product" not in getattr(txns, "columns", []):
        return get_inventory(email)
    have = {_norm(it.get("sku")) for it in get_inventory(email)}
    seen: dict[str, str] = {}
    for p in txns["product"].dropna():
        n = _norm(p)
        if n and n not in seen:
            seen[n] = str(p).strip()
    items = get_inventory(email)
    for n, disp in seen.items():
        if n in have:
            continue
        items.append({
            "id": secrets.token_hex(4), "sku": disp[:120],
            "current_stock": 0, "lead_time_days": 7, "safety_stock": 0,
            "reorder_qty": None, "unit_cost": None, "supplier": "",
        })
    _save_inventory(email, items)
    return items


# ---------------------------------------------------------
# reorder signature + approval-panel insight
# ---------------------------------------------------------
def reorder_signature(email: str) -> str:
    below = compute_inventory(email)["below"]
    return "|".join(sorted(f"{_norm(r.get('sku'))}:{r['suggested_qty']}" for r in below))


def mark_reorder_handled(email: str, state: str) -> None:
    user_store.set_key(email, REORDER_SIG_KEY, {"sig": reorder_signature(email), "state": state})


def reorder_decision_state(email: str) -> str:
    """pending unless the current below-ROP set is exactly the one the owner
    last approved/dismissed (so a changed set re-surfaces the card)."""
    rec = user_store.get_key(email, REORDER_SIG_KEY, None) or {}
    if rec.get("state") in ("approved", "dismissed") and rec.get("sig") == reorder_signature(email):
        return rec["state"]
    return "pending"


def clear_reorder_handled(email: str) -> None:
    user_store.set_key(email, REORDER_SIG_KEY, {})


def build_reorder_insight(email: str) -> dict | None:
    below = compute_inventory(email)["below"]
    if not below:
        return None
    names = ", ".join(r.get("sku", "?") for r in below[:4])
    if len(below) > 4:
        names += f" +{len(below) - 4} more"
    plural = "s" if len(below) != 1 else ""
    return {
        "id": "reorder", "module": "supply", "page": "supply", "icon": "📦",
        "title": f"Reorder {len(below)} item{plural} below reorder point",
        "detail": (f"{names} {'are' if len(below) != 1 else 'is'} at or below the reorder point "
                   "(average daily sales × lead time + safety stock). Approve to generate a purchase "
                   "order with suggested quantities — saved to your account and downloaded as Excel."),
        "action_label": "Approve → generate purchase order",
        "count": len(below), "has_download": True,
    }


# ---------------------------------------------------------
# purchase orders
# ---------------------------------------------------------
def get_purchase_orders(email: str) -> list[dict]:
    pos = user_store.get_key(email, PO_KEY, []) or []
    return pos if isinstance(pos, list) else []


def get_po(email: str, po_number: str) -> dict | None:
    return next((p for p in get_purchase_orders(email) if p.get("po_number") == po_number), None)


def latest_po(email: str) -> dict | None:
    pos = get_purchase_orders(email)
    return pos[-1] if pos else None


def po_for_insight(email: str, insight_id: str) -> dict | None:
    matched = [p for p in get_purchase_orders(email) if p.get("insight_id") == insight_id]
    return matched[-1] if matched else latest_po(email)


def create_po(email: str, insight_id: str | None = None) -> dict | None:
    """Build + persist a Purchase Order for every item currently below its
    reorder point. Marks the current reorder set as handled(approved)."""
    below = compute_inventory(email)["below"]
    if not below:
        return None
    pos = get_purchase_orders(email)
    now = pd.Timestamp.now()
    po_number = f"PO-{now.strftime('%Y%m%d')}-{len(pos) + 1:03d}"
    lines, total_qty, total_value, has_cost = [], 0, 0.0, False
    for r in below:
        qty = int(r["suggested_qty"])
        unit_cost = r.get("unit_cost")
        line_value = qty * float(unit_cost) if not _blank(unit_cost) else None
        total_qty += qty
        if line_value is not None:
            total_value += line_value
            has_cost = True
        lines.append({
            "sku": r.get("sku", ""), "supplier": r.get("supplier", ""),
            "current_stock": _num(r.get("current_stock")),
            "avg_daily_sales": r.get("avg_daily_sales"),
            "lead_time_days": _num(r.get("lead_time_days")),
            "reorder_point": r.get("reorder_point"),
            "order_qty": qty,
            "unit_cost": (None if _blank(unit_cost) else float(unit_cost)),
            "line_value": line_value,
        })
    po = {
        "po_number": po_number, "insight_id": insight_id,
        "created_at": now.isoformat(timespec="seconds"), "status": "open",
        "n_items": len(lines), "total_qty": total_qty,
        "total_value": round(total_value, 2) if has_cost else None,
        "lines": lines,
    }
    pos.append(po)
    user_store.set_key(email, PO_KEY, pos)
    mark_reorder_handled(email, "approved")
    return po


def po_excel(email: str, po: dict) -> tuple[str, io.BytesIO]:
    lines = po.get("lines", [])
    df = pd.DataFrame([{
        "Item (SKU)": l.get("sku", ""),
        "Supplier": l.get("supplier", ""),
        "Current Stock": l.get("current_stock", 0),
        "Avg Daily Sales": l.get("avg_daily_sales", 0),
        "Lead Time (days)": l.get("lead_time_days", 0),
        "Reorder Point": l.get("reorder_point", 0),
        "Order Qty": l.get("order_qty", 0),
        "Unit Cost": ("" if _blank(l.get("unit_cost")) else l.get("unit_cost")),
        "Line Value": ("" if _blank(l.get("line_value")) else l.get("line_value")),
    } for l in lines])
    total_row = {c: "" for c in df.columns}
    total_row["Item (SKU)"] = "TOTAL"
    total_row["Order Qty"] = po.get("total_qty", "")
    if po.get("total_value") is not None:
        total_row["Line Value"] = po.get("total_value")
    df = pd.concat([df, pd.DataFrame([total_row])], ignore_index=True)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Purchase Order", startrow=4)
        ws = writer.sheets["Purchase Order"]
        ws["A1"] = "PURCHASE ORDER"
        ws["A2"] = f"PO Number: {po.get('po_number', '')}"
        ws["A3"] = f"Created: {po.get('created_at', '')}"
        for i, col in enumerate(df.columns):
            longest = int(df[col].astype(str).str.len().max()) if len(df) else 12
            ws.column_dimensions[chr(65 + i)].width = min(40, max(12, longest + 2, len(str(col)) + 2))
    buf.seek(0)
    return f"{po.get('po_number', 'purchase_order')}.xlsx", buf
