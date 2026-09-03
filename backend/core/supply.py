"""
Smart CafeX — Supply / Inventory Management.

Inventory now lives in its own Supabase table (`inventory`) when Supabase is
configured; otherwise it falls back to the per-account JSON state so local dev
keeps working. The same dual-mode pattern backs the product recipe map
(`product_inventory_map`), the waste log (`inventory_waste`) and purchase
orders (`purchase_orders`).

Pipeline:

    sales history ─▶ per-product daily units
    product recipe ─▶ how much of each item a product consumes
                       │
    (fallback: match item name to product name)
                       ▼
              item average daily usage
                       │
    lead time + safety stock ─▶ reorder point ─▶ below-ROP?
    ordering cost + holding cost ─▶ EOQ ─▶ order qty (bounded below by MOQ)

Each item gets its own restock suggestion. "Open" on a suggestion builds a
proper Purchase Order PDF (backend.core.po_pdf) with a PO number saved in the
backend and the file downloaded to the user's machine.

`smart` is imported for load_sales only; used at call time, never at import
time, so the smart <-> supply pair does not deadlock on import.
"""
from __future__ import annotations

import io
import math
import secrets

import pandas as pd

from backend.core import db, smart, user_store

# JSON-state fallback keys (used when Supabase is not configured)
INVENTORY_KEY = "smart_inventory"
MAP_KEY = "smart_product_map"
WASTE_KEY = "smart_waste"
PO_KEY = "smart_purchase_orders"
REORDER_SIG_KEY = "smart_reorder_sig"

# Supabase table names
T_INV = "inventory"
T_MAP = "product_inventory_map"
T_WASTE = "inventory_waste"
T_PO = "purchase_orders"


def _tables() -> bool:
    return bool(db.SUPABASE_ENABLED)


def _email(email: str) -> str:
    return (email or "").strip().lower()


def _safe_fetch(table: str, match: dict) -> list[dict]:
    """Read rows for a supply table, tolerating a not-yet-created table.

    The inventory tables must be created once (supabase/inventory.sql). Until
    then — or on any transient PostgREST error — reads degrade to an empty list
    so a missing table can never take down the rest of the app (home, insights,
    other modules). Writes still surface real errors so setup problems are
    visible where the user is actually adding data.
    """
    try:
        return db.fetch_all(table, match)
    except Exception as e:  # noqa: BLE001 - defensive by design
        import logging
        logging.getLogger("supply").warning(
            "inventory read on %r failed (%s); is supabase/inventory.sql run?",
            table, e)
        return []


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


def _opt_num(v):
    """None when blank, else float."""
    return None if _blank(v) else _num(v)


def _now_iso() -> str:
    return pd.Timestamp.now().isoformat(timespec="seconds")


# ---------------------------------------------------------
# inventory items — normalisation
# ---------------------------------------------------------
def _normalise_item(raw: dict) -> dict:
    """Coerce a stored row (table row OR legacy JSON item) into the canonical
    shape the rest of the module expects. Legacy JSON items used `sku` and
    `supplier`; we map those onto the new fields."""
    return {
        "id": raw.get("id") or secrets.token_hex(8),
        "name": (raw.get("name") or raw.get("sku") or "").strip(),
        "category": (raw.get("category") or "").strip(),
        "unit_label": (raw.get("unit_label") or "unit").strip() or "unit",
        "current_stock": _num(raw.get("current_stock"), 0),
        "lead_time_days": _num(raw.get("lead_time_days"), 0),
        "safety_stock": _num(raw.get("safety_stock"), 0),
        "moq": _num(raw.get("moq"), 0),
        "ordering_cost": _opt_num(raw.get("ordering_cost")),
        "holding_cost": _opt_num(raw.get("holding_cost")),
        "unit_cost": _opt_num(raw.get("unit_cost")),
        "reorder_qty": _opt_num(raw.get("reorder_qty")),
        "supplier_name": (raw.get("supplier_name") or raw.get("supplier") or "").strip(),
        "supplier_phone": (raw.get("supplier_phone") or "").strip(),
        "supplier_email": (raw.get("supplier_email") or "").strip(),
    }


def _clean_item(item: dict, existing_id: str | None) -> dict:
    clean = _normalise_item(item)
    clean["id"] = existing_id or item.get("id") or secrets.token_hex(8)
    clean["name"] = clean["name"][:160]
    clean["category"] = clean["category"][:80]
    clean["unit_label"] = clean["unit_label"][:24]
    clean["supplier_name"] = clean["supplier_name"][:160]
    clean["supplier_phone"] = clean["supplier_phone"][:40]
    clean["supplier_email"] = clean["supplier_email"][:160]
    if not clean["name"]:
        raise ValueError("Item name is required.")
    return clean


# ---------------------------------------------------------
# inventory CRUD
# ---------------------------------------------------------
def get_inventory(email: str) -> list[dict]:
    email = _email(email)
    if _tables():
        rows = _safe_fetch(T_INV, {"email": email})
    else:
        rows = user_store.get_key(email, INVENTORY_KEY, []) or []
        rows = rows if isinstance(rows, list) else []
    items = [_normalise_item(r) for r in rows]
    items.sort(key=lambda r: _norm(r.get("name")))
    return items


def _save_inventory_json(email: str, items: list[dict]) -> None:
    user_store.set_key(_email(email), INVENTORY_KEY, items)


def upsert_item(email: str, item: dict) -> list[dict]:
    email = _email(email)
    current = get_inventory(email)
    iid = item.get("id")
    exists = bool(iid) and any(it.get("id") == iid for it in current)
    clean = _clean_item(item, iid if exists else None)

    if _tables():
        row = dict(clean)
        row["email"] = email
        row["updated_at"] = _now_iso()
        db.upsert(T_INV, row, on_conflict="id")
    else:
        if exists:
            items = [clean if it.get("id") == clean["id"] else it for it in current]
        else:
            items = current + [clean]
        _save_inventory_json(email, items)
    return get_inventory(email)


def delete_item(email: str, iid: str) -> list[dict]:
    email = _email(email)
    if _tables():
        db.delete(T_MAP, {"email": email, "inventory_id": iid})
        db.delete(T_INV, {"id": iid, "email": email})
    else:
        items = [it for it in get_inventory(email) if it.get("id") != iid]
        _save_inventory_json(email, items)
        maps = [m for m in get_maps(email) if m.get("inventory_id") != iid]
        user_store.set_key(email, MAP_KEY, maps)
    return get_inventory(email)


def _get_item(email: str, iid: str) -> dict | None:
    return next((it for it in get_inventory(email) if it.get("id") == iid), None)


# ---------------------------------------------------------
# product -> inventory recipe map
# ---------------------------------------------------------
def get_maps(email: str) -> list[dict]:
    email = _email(email)
    if _tables():
        rows = _safe_fetch(T_MAP, {"email": email})
    else:
        rows = user_store.get_key(email, MAP_KEY, []) or []
        rows = rows if isinstance(rows, list) else []
    out = []
    for r in rows:
        out.append({
            "id": r.get("id") or secrets.token_hex(6),
            "product": (r.get("product") or "").strip(),
            "inventory_id": r.get("inventory_id") or "",
            "qty_per_unit": _num(r.get("qty_per_unit"), 1),
        })
    return out


def upsert_map(email: str, product: str, inventory_id: str, qty_per_unit) -> list[dict]:
    email = _email(email)
    product = (product or "").strip()
    if not product or not inventory_id:
        raise ValueError("Both a product and an inventory item are required.")
    qty = _num(qty_per_unit, 1)
    if qty <= 0:
        raise ValueError("Quantity per unit must be greater than zero.")
    existing = next((m for m in get_maps(email)
                     if _norm(m["product"]) == _norm(product)
                     and m["inventory_id"] == inventory_id), None)
    if _tables():
        if existing:
            db.update(T_MAP, {"id": existing["id"], "email": email},
                      {"qty_per_unit": qty})
        else:
            db.insert(T_MAP, {
                "id": secrets.token_hex(8), "email": email, "product": product,
                "inventory_id": inventory_id, "qty_per_unit": qty,
            })
    else:
        maps = get_maps(email)
        if existing:
            for m in maps:
                if m["id"] == existing["id"]:
                    m["qty_per_unit"] = qty
        else:
            maps.append({"id": secrets.token_hex(8), "product": product,
                         "inventory_id": inventory_id, "qty_per_unit": qty})
        user_store.set_key(email, MAP_KEY, maps)
    return get_maps(email)


def delete_map(email: str, map_id: str) -> list[dict]:
    email = _email(email)
    if _tables():
        db.delete(T_MAP, {"id": map_id, "email": email})
    else:
        maps = [m for m in get_maps(email) if m.get("id") != map_id]
        user_store.set_key(email, MAP_KEY, maps)
    return get_maps(email)


def get_products(email: str) -> list[str]:
    """Products available to link inventory to. Prefers canonical products from
    Product Management; falls back to (canonicalised) raw sales names + any name
    already used in the recipe map."""
    try:
        from backend.core import products as _products
        canon = _products.product_names(email)
    except Exception:
        _products, canon = None, []
    if canon:
        have = {_norm(x) for x in canon}
        for m in get_maps(email):
            n = _norm(m["product"])
            if n and n not in have:
                canon.append(m["product"]); have.add(n)
        return sorted(canon, key=_norm)
    names: dict[str, str] = {}
    txns = smart.load_sales(email)
    if txns is not None and "product" in getattr(txns, "columns", []):
        try:
            if _products:
                txns = _products.canonicalize_df(email, txns)
        except Exception:
            pass
        for p in txns["product"].dropna():
            n = _norm(p)
            if n and n not in names:
                names[n] = str(p).strip()
    for m in get_maps(email):
        n = _norm(m["product"])
        if n and n not in names:
            names[n] = m["product"]
    return [names[k] for k in sorted(names)]


# ---------------------------------------------------------
# waste / spoilage
# ---------------------------------------------------------
def record_waste(email: str, inventory_id: str, qty, reason: str = "") -> list[dict]:
    email = _email(email)
    qty = _num(qty, 0)
    if qty <= 0:
        raise ValueError("Waste quantity must be greater than zero.")
    item = _get_item(email, inventory_id)
    if not item:
        raise ValueError("Inventory item not found.")
    new_stock = max(0.0, _num(item.get("current_stock")) - qty)
    reason = (reason or "").strip()[:240]

    if _tables():
        db.update(T_INV, {"id": inventory_id, "email": email},
                  {"current_stock": new_stock, "updated_at": _now_iso()})
        db.insert(T_WASTE, {
            "id": secrets.token_hex(8), "email": email, "inventory_id": inventory_id,
            "item_name": item.get("name", ""), "qty": qty, "reason": reason,
        })
    else:
        items = get_inventory(email)
        for it in items:
            if it["id"] == inventory_id:
                it["current_stock"] = new_stock
        _save_inventory_json(email, items)
        log = user_store.get_key(email, WASTE_KEY, []) or []
        log.append({"id": secrets.token_hex(8), "inventory_id": inventory_id,
                    "item_name": item.get("name", ""), "qty": qty,
                    "reason": reason, "ts": _now_iso()})
        user_store.set_key(email, WASTE_KEY, log[-500:])
    return get_waste(email)


def get_waste(email: str, limit: int = 60) -> list[dict]:
    email = _email(email)
    if _tables():
        rows = _safe_fetch(T_WASTE, {"email": email})
    else:
        rows = user_store.get_key(email, WASTE_KEY, []) or []
        rows = rows if isinstance(rows, list) else []
    rows = sorted(rows, key=lambda r: str(r.get("ts", "")), reverse=True)
    return rows[:limit]


# ---------------------------------------------------------
# correlate with sales -> per-product average daily units
# ---------------------------------------------------------
def _product_daily(email: str) -> tuple[dict, dict]:
    """({normalised product -> avg units/day}, meta) from the account's saved
    Sales data: total units sold per product over the dataset's day span."""
    txns = smart.load_sales(email)
    if txns is None or not len(txns) or "product" not in getattr(txns, "columns", []):
        return {}, {"has_sales": False, "days_span": 0}
    try:
        from backend.core import products as _products
        txns = _products.canonicalize_df(email, txns)
    except Exception:
        pass
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


def _maps_by_item(email: str) -> dict:
    out: dict[str, list[tuple[str, float]]] = {}
    for m in get_maps(email):
        out.setdefault(m["inventory_id"], []).append((_norm(m["product"]), m["qty_per_unit"]))
    return out


def _item_daily_usage(item: dict, product_daily: dict, maps_by_item: dict) -> tuple[float, bool]:
    """(avg units/day consumed, whether a product recipe was used)."""
    links = maps_by_item.get(item["id"])
    if links:
        total = 0.0
        for prod_norm, qty in links:
            total += product_daily.get(prod_norm, 0.0) * qty
        return total, True
    # Fallback: item name matches a product name directly.
    return product_daily.get(_norm(item.get("name")), 0.0), False


# ---------------------------------------------------------
# EOQ + reorder maths
# ---------------------------------------------------------
def _eoq(annual_demand: float, ordering_cost, holding_cost) -> float | None:
    S = _opt_num(ordering_cost)
    H = _opt_num(holding_cost)
    if annual_demand > 0 and S and S > 0 and H and H > 0:
        return math.sqrt(2.0 * annual_demand * S / H)
    return None


def _enrich(item: dict, product_daily: dict, maps_by_item: dict) -> dict:
    avg_daily, via_recipe = _item_daily_usage(item, product_daily, maps_by_item)
    lead = _num(item.get("lead_time_days"))
    safety = _num(item.get("safety_stock"))
    current = _num(item.get("current_stock"))
    moq = _int(item.get("moq"))
    annual_demand = avg_daily * 365.0

    reorder_point = int(math.ceil(avg_daily * lead + safety))
    below = reorder_point > 0 and current <= reorder_point

    eoq_raw = _eoq(annual_demand, item.get("ordering_cost"), item.get("holding_cost"))

    if not _blank(item.get("reorder_qty")):
        base = max(1, _int(item.get("reorder_qty")))
        basis = "manual"
    elif eoq_raw:
        base = max(1, int(math.ceil(eoq_raw)))
        basis = "eoq"
    else:
        # Bring stock back above the reorder point plus one lead-time cycle.
        base = int(max(1, math.ceil(reorder_point - current + avg_daily * lead)))
        basis = "cover"

    order_qty = base
    moq_applied = False
    if moq > 0 and moq > order_qty:
        order_qty = moq
        moq_applied = True

    unit_cost = item.get("unit_cost")
    est_line_cost = round(order_qty * float(unit_cost), 2) if not _blank(unit_cost) else None
    days_of_cover = round(current / avg_daily, 1) if avg_daily > 0 else None

    out = dict(item)
    out.update({
        "avg_daily_sales": round(avg_daily, 3),
        "usage_via_recipe": via_recipe,
        "annual_demand": round(annual_demand, 1),
        "eoq": (int(round(eoq_raw)) if eoq_raw else None),
        "reorder_point": reorder_point,
        "below_reorder": bool(below),
        "order_qty": int(order_qty),
        "order_basis": basis,
        "moq_applied": moq_applied,
        "suggested_qty": int(order_qty) if below else 0,
        "est_line_cost": est_line_cost,
        "days_of_cover": days_of_cover,
        "reason": _reason_text(item, avg_daily, reorder_point, current, eoq_raw,
                               basis, order_qty, moq, moq_applied, below),
    })
    return out


def _reason_text(item, avg_daily, rop, current, eoq_raw, basis, order_qty, moq, moq_applied, below) -> str:
    unit = item.get("unit_label") or "unit"
    if avg_daily <= 0:
        base = ("No sales usage detected yet, so demand is unknown. "
                "Link this item to the products that use it, or upload Sales data.")
    else:
        base = (f"Uses about {round(avg_daily, 2)} {unit}/day. Reorder point "
                f"{rop} = daily usage x {int(_num(item.get('lead_time_days')))}d lead "
                f"+ {int(_num(item.get('safety_stock')))} safety.")
    if not below:
        return base + f" Current stock {int(current)} is above the reorder point."
    if basis == "eoq":
        base += f" Economic order quantity is {int(round(eoq_raw))} {unit}."
    elif basis == "manual":
        base += " Using your manual reorder quantity."
    else:
        base += " EOQ needs ordering & holding cost; using a lead-time cover estimate."
    if moq_applied:
        base += f" Raised to the supplier MOQ of {moq}."
    return base + f" Suggested order: {order_qty} {unit}."


# ---------------------------------------------------------
# compute
# ---------------------------------------------------------
def compute_inventory(email: str) -> dict:
    email = _email(email)
    product_daily, meta = _product_daily(email)
    mbi = _maps_by_item(email)
    rows = [_enrich(it, product_daily, mbi) for it in get_inventory(email)]
    rows.sort(key=lambda r: (not r["below_reorder"], _norm(r.get("name"))))
    below = [r for r in rows if r["below_reorder"]]
    return {"items": rows, "below": below, "meta": meta, "n_below": len(below)}


def import_products_from_sales(email: str) -> list[dict]:
    """Seed inventory rows for any product in the sales data not already tracked
    (blank stock, a default 7-day lead time, for the owner to adjust)."""
    email = _email(email)
    txns = smart.load_sales(email)
    if txns is None or "product" not in getattr(txns, "columns", []):
        return get_inventory(email)
    have = {_norm(it.get("name")) for it in get_inventory(email)}
    seen: dict[str, str] = {}
    for p in txns["product"].dropna():
        n = _norm(p)
        if n and n not in seen:
            seen[n] = str(p).strip()
    for n, disp in seen.items():
        if n in have:
            continue
        upsert_item(email, {
            "name": disp[:160], "current_stock": 0, "lead_time_days": 7,
            "safety_stock": 0, "moq": 0, "unit_label": "unit",
        })
    return get_inventory(email)


# ---------------------------------------------------------
# reorder signature + approval-panel insight
# ---------------------------------------------------------
def reorder_signature(email: str) -> str:
    below = compute_inventory(email)["below"]
    return "|".join(sorted(f"{_norm(r.get('name'))}:{r['suggested_qty']}" for r in below))


def mark_reorder_handled(email: str, state: str) -> None:
    user_store.set_key(_email(email), REORDER_SIG_KEY,
                       {"sig": reorder_signature(email), "state": state})


def reorder_decision_state(email: str) -> str:
    rec = user_store.get_key(_email(email), REORDER_SIG_KEY, None) or {}
    if rec.get("state") in ("approved", "dismissed") and rec.get("sig") == reorder_signature(email):
        return rec["state"]
    return "pending"


def clear_reorder_handled(email: str) -> None:
    user_store.set_key(_email(email), REORDER_SIG_KEY, {})


def build_reorder_insight(email: str) -> dict | None:
    below = compute_inventory(email)["below"]
    if not below:
        return None
    names = ", ".join(r.get("name", "?") for r in below[:4])
    if len(below) > 4:
        names += f" +{len(below) - 4} more"
    plural = "s" if len(below) != 1 else ""
    return {
        "id": "reorder", "module": "supply", "page": "supply", "icon": "📦",
        "title": f"Reorder {len(below)} item{plural} below reorder point",
        "detail": (f"{names} {'are' if len(below) != 1 else 'is'} at or below the reorder point "
                   "(daily usage x lead time + safety stock). Approve to generate purchase "
                   "orders with EOQ / MOQ suggested quantities — saved to your account and "
                   "downloaded as a PDF."),
        "action_label": "Approve → generate purchase order",
        "count": len(below), "has_download": True,
    }


# ---------------------------------------------------------
# purchase orders
# ---------------------------------------------------------
def get_purchase_orders(email: str) -> list[dict]:
    email = _email(email)
    if _tables():
        rows = _safe_fetch(T_PO, {"email": email})
        rows = sorted(rows, key=lambda r: str(r.get("created_at", "")))
    else:
        rows = user_store.get_key(email, PO_KEY, []) or []
        rows = rows if isinstance(rows, list) else []
    return rows


def get_po(email: str, po_number: str) -> dict | None:
    return next((p for p in get_purchase_orders(email) if p.get("po_number") == po_number), None)


def latest_po(email: str) -> dict | None:
    pos = get_purchase_orders(email)
    return pos[-1] if pos else None


def po_for_insight(email: str, insight_id: str) -> dict | None:
    matched = [p for p in get_purchase_orders(email) if p.get("insight_id") == insight_id]
    return matched[-1] if matched else latest_po(email)


def _next_po_number(email: str) -> str:
    now = pd.Timestamp.now()
    same_day = [p for p in get_purchase_orders(email)
                if str(p.get("po_number", "")).startswith(f"PO-{now.strftime('%Y%m%d')}")]
    return f"PO-{now.strftime('%Y%m%d')}-{len(same_day) + 1:03d}"


def _po_line(r: dict) -> dict:
    qty = int(r.get("order_qty") or 0)
    if qty <= 0:
        qty = max(int(_num(r.get("moq"))), 1)
    unit_cost = r.get("unit_cost")
    line_amount = round(qty * float(unit_cost), 2) if not _blank(unit_cost) else None
    return {
        "inventory_id": r.get("id", ""),
        "name": r.get("name", ""),
        "category": r.get("category", ""),
        "unit_label": r.get("unit_label", "unit"),
        "supplier_name": r.get("supplier_name", ""),
        "supplier_phone": r.get("supplier_phone", ""),
        "supplier_email": r.get("supplier_email", ""),
        "current_stock": _num(r.get("current_stock")),
        "avg_daily_sales": r.get("avg_daily_sales"),
        "lead_time_days": _num(r.get("lead_time_days")),
        "reorder_point": r.get("reorder_point"),
        "order_qty": qty,
        "unit_cost": (None if _blank(unit_cost) else float(unit_cost)),
        "line_amount": line_amount,
    }


def create_po(email: str, item_ids: list[str] | None = None,
              insight_id: str | None = None) -> dict | None:
    """Build + persist a Purchase Order. If item_ids is given, the PO covers
    exactly those items (that's the per-suggestion "Open" flow); otherwise it
    covers every item currently below its reorder point."""
    email = _email(email)
    comp = compute_inventory(email)
    by_id = {it["id"]: it for it in comp["items"]}
    if item_ids:
        chosen = [by_id[i] for i in item_ids if i in by_id]
    else:
        chosen = comp["below"]
    if not chosen:
        return None

    lines, total_qty, total_amount, has_cost = [], 0, 0.0, False
    suppliers: list[str] = []
    for r in chosen:
        line = _po_line(r)
        total_qty += line["order_qty"]
        if line["line_amount"] is not None:
            total_amount += line["line_amount"]
            has_cost = True
        if line["supplier_name"] and line["supplier_name"] not in suppliers:
            suppliers.append(line["supplier_name"])
        lines.append(line)

    po = {
        "id": _next_po_number(email),
        "po_number": _next_po_number(email),
        "insight_id": insight_id,
        "created_at": _now_iso(),
        "status": "open",
        "n_items": len(lines),
        "total_qty": int(total_qty),
        "total_amount": round(total_amount, 2) if has_cost else None,
        "suppliers": suppliers,
        "lines": lines,
    }
    po["id"] = po["po_number"]

    if _tables():
        row = dict(po)
        row["email"] = email
        db.insert(T_PO, row)
    else:
        pos = user_store.get_key(email, PO_KEY, []) or []
        pos.append(po)
        user_store.set_key(email, PO_KEY, pos)

    if not item_ids:
        mark_reorder_handled(email, "approved")
    return po


# ---------------------------------------------------------
# exports
# ---------------------------------------------------------
def po_pdf_bytes(email: str, po: dict) -> tuple[str, io.BytesIO]:
    """Render the PO to a professional PDF. Returns (filename, BytesIO)."""
    from backend.core import po_pdf
    buf = po_pdf.build_po_pdf(po, buyer_email=email)
    return f"{po.get('po_number', 'purchase_order')}.pdf", buf


def po_excel(email: str, po: dict) -> tuple[str, io.BytesIO]:
    lines = po.get("lines", [])
    df = pd.DataFrame([{
        "Item": l.get("name", ""),
        "Supplier": l.get("supplier_name", ""),
        "Supplier phone": l.get("supplier_phone", ""),
        "Supplier email": l.get("supplier_email", ""),
        "Current Stock": l.get("current_stock", 0),
        "Avg Daily Usage": l.get("avg_daily_sales", 0),
        "Lead Time (days)": l.get("lead_time_days", 0),
        "Reorder Point": l.get("reorder_point", 0),
        "Order Qty": l.get("order_qty", 0),
        "Unit Cost": ("" if _blank(l.get("unit_cost")) else l.get("unit_cost")),
        "Line Amount": ("" if _blank(l.get("line_amount")) else l.get("line_amount")),
    } for l in lines])
    total_row = {c: "" for c in df.columns}
    total_row["Item"] = "TOTAL"
    total_row["Order Qty"] = po.get("total_qty", "")
    if po.get("total_amount") is not None:
        total_row["Line Amount"] = po.get("total_amount")
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
            ws.column_dimensions[chr(65 + i)].width = min(44, max(12, longest + 2, len(str(col)) + 2))
    buf.seek(0)
    return f"{po.get('po_number', 'purchase_order')}.xlsx", buf
