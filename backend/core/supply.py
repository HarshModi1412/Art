"""
Smart CafeX — Supply / Inventory Management.

Inventory now lives in its own Supabase table (`inventory`) when Supabase is
configured; otherwise it falls back to the per-account JSON state so local dev
keeps working. The same dual-mode pattern backs the product recipe map
(`product_inventory_map`), the waste log (`inventory_waste`) and purchase
orders (`purchase_orders`).

Pipeline:

    sales history ─▶ per-product daily units (last 30 days of the data)
    product recipe ─▶ how much of each raw material a product consumes
                       │
    (fallback: match item name to product name)
                       ▼
          raw-material average daily consumption
                       │
    DOS (days of supply) = current stock ÷ average daily consumption
    rule: DOS must stay ≥ 1.2 × the supplier's lead time, else raise a PO
    DOQ (default order quantity) = the supplier's MOQ, until the seller has
        entered their ordering cost and holding cost AND there is a month of
        sales — then monthly consumption × 12 = annual demand, EOQ =
        √(2·D·S/H), and DOQ = EOQ if EOQ > MOQ, else MOQ. The seller can
        always type their own DOQ, which wins.

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
    txns = smart.load_supply_sales(email)
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
def receive_stock(email: str, inventory_id: str, qty, reason: str = "") -> float:
    """Add stock to an inventory item. The mirror of record_waste, used when a
    purchase order is marked received.

    Returns the new stock level. Raises if the item is gone, because silently
    dropping a receipt leaves the seller's stock permanently understated and
    they will not notice until they oversell."""
    email = _email(email)
    qty = _num(qty, 0)
    if qty <= 0:
        raise ValueError("Received quantity must be greater than zero.")
    item = _get_item(email, inventory_id)
    if not item:
        raise ValueError("Inventory item not found.")
    new_stock = _num(item.get("current_stock")) + qty

    if _tables():
        db.update(T_INV, {"id": inventory_id, "email": email},
                  {"current_stock": new_stock, "updated_at": _now_iso()})
    else:
        items = get_inventory(email)
        for it in items:
            if it["id"] == inventory_id:
                it["current_stock"] = new_stock
        _save_inventory_json(email, items)
    return new_stock


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
# correlate with sales -> per-product daily demand (mean + variability)
# ---------------------------------------------------------
# Auto-fill defaults, used when the owner leaves a field blank/zero and there is
# enough sales history to suggest a value. All are editable once applied.
HOLDING_PCT = 0.20          # annual holding cost as a fraction of unit cost
DEFAULT_ORDERING = 200.0    # ₹ per order, when none entered
DEFAULT_LEAD_DAYS = 7       # supplier lead time fallback (not sales-derivable)
SERVICE_Z = 1.65            # ~95% service level for safety stock
MIN_DAYS_FOR_AUTO = 5       # need at least this many days of sales to suggest

# Replenishment rule. Stock must cover the supplier's lead time with 20% to
# spare: a 10-day supplier means ordering once fewer than 12 days of supply
# are left. The 20% is the buffer for a slow delivery or a good sales week,
# so it replaces a separate safety-stock figure in the trigger.
DOS_LEAD_MULTIPLE = 1.2
RECENT_WINDOW_DAYS = 30     # consumption rate is read over the latest month
EOQ_MIN_DAYS = 30           # a month of sales before annual demand is trusted


def _demand_stats(email: str):
    """(product_daily_mean, daily_matrix, meta).

    product_daily_mean: {norm product -> mean units/day over the span}
    daily_matrix: DataFrame (index = every day in the span, columns = norm
                  product, values = units that day, 0-filled) or None if the
                  sales data has no usable dates. Used for demand variability.
    """
    txns, source = _sales_source(email)
    if txns is None or not len(txns) or "product" not in getattr(txns, "columns", []):
        return {}, None, {"has_sales": False, "days_span": 0, "source": "",
                          "window_days": 0, "data_to": ""}
    try:
        from backend.core import products as _products
        txns = _products.canonicalize_df(email, txns)
    except Exception:
        pass
    df = txns.copy()
    df["_prod"] = df["product"].map(_norm)
    df = df[df["_prod"] != ""]
    qty_col = "quantity" if "quantity" in df.columns else None
    df["_q"] = (pd.to_numeric(df[qty_col], errors="coerce").fillna(0.0)
                if qty_col else 1.0)

    if "date" in df.columns:
        df["_d"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
        dd = df.dropna(subset=["_d"])
        if len(dd):
            dmin, dmax = dd["_d"].min(), dd["_d"].max()
            days = max(1, int((dmax - dmin).days) + 1)
            full = pd.date_range(dmin, dmax, freq="D")
            piv = dd.pivot_table(index="_d", columns="_prod", values="_q",
                                 aggfunc="sum", fill_value=0.0).reindex(full, fill_value=0.0)
            # The consumption rate is read over the latest month of the data,
            # not the whole history: a product that sold well last winter and
            # not since should not keep ordering winter quantities.
            window = int(min(RECENT_WINDOW_DAYS, len(piv)))
            recent = piv.tail(window)
            product_daily = {c: float(recent[c].mean()) for c in piv.columns}
            return product_daily, piv, {"has_sales": True, "days_span": int(days),
                                        "window_days": window, "source": source,
                                        "data_to": dmax.date().isoformat()}

    # No usable dates: fall back to totals / 1-day span.
    totals = df.groupby("_prod")["_q"].sum()
    return ({k: float(v) for k, v in totals.items()}, None,
            {"has_sales": True, "days_span": 1, "window_days": 1, "source": source,
             "data_to": ""})


def _sales_source(email: str):
    """The sales history Supply works from: the separate 'previous sales' set
    when the seller uploaded one here, otherwise their main Sales data — which
    already includes every order from their own website. Without the second
    route a seller who never used the Supply upload had no consumption rate at
    all, so days of supply could never be worked out."""
    txns = smart.load_supply_sales(email)
    if txns is not None and len(txns) and "product" in getattr(txns, "columns", []):
        return txns, "supply_sales"
    txns = smart.load_sales(email)
    if txns is not None and len(txns) and "product" in getattr(txns, "columns", []):
        return txns, "sales"
    return None, ""


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
    return product_daily.get(_norm(item.get("name")), 0.0), False


def _item_daily_std(item: dict, piv, maps_by_item: dict) -> float | None:
    """Std-dev of the item's daily consumption, for safety stock. None when the
    sales data has no dates (variability unknown)."""
    if piv is None or not len(piv):
        return None
    links = maps_by_item.get(item["id"])
    if links:
        series = None
        for prod_norm, qty in links:
            if prod_norm in piv.columns:
                col = piv[prod_norm] * qty
                series = col if series is None else series + col
        if series is None:
            return 0.0
    else:
        name = _norm(item.get("name"))
        if name not in piv.columns:
            return None
        series = piv[name]
    try:
        return float(series.std(ddof=0))
    except Exception:
        return None


# ---------------------------------------------------------
# EOQ + reorder maths
# ---------------------------------------------------------
def _eoq(annual_demand: float, ordering_cost, holding_cost) -> float | None:
    S = _opt_num(ordering_cost)
    H = _opt_num(holding_cost)
    if annual_demand > 0 and S and S > 0 and H and H > 0:
        return math.sqrt(2.0 * annual_demand * S / H)
    return None


def doq_for(avg_daily: float, moq: float, ordering_cost, holding_cost,
            days_span: int, lead_days: float, override=None) -> dict:
    """The default order quantity for one raw material, and why.

    The rule the seller asked for, in order:

      1. Their own number, if they typed one, always wins.
      2. Until they have entered BOTH what placing an order costs them and
         what holding one unit for a year costs them, AND there is at least a
         month of sales, the supplier's MOQ is the DOQ. Anything cleverer would
         be built on numbers we made up.
      3. Once all three exist: the last month's consumption × 12 is the annual
         demand D, EOQ = √(2·D·S/H), and the DOQ is the EOQ when it is larger
         than the MOQ — otherwise the MOQ, because the supplier will not sell
         fewer.

    With no MOQ on file either, it falls back to enough to cover the lead time
    with the same 20% to spare the trigger uses, so a PO is never for zero."""
    moq = max(0.0, _num(moq))
    S, H = _opt_num(ordering_cost), _opt_num(holding_cost)
    monthly = avg_daily * 30.0
    annual = monthly * 12.0
    eoq = None
    eoq_ready = bool(S and S > 0 and H and H > 0 and days_span >= EOQ_MIN_DAYS and annual > 0)
    if eoq_ready:
        eoq = math.sqrt(2.0 * annual * S / H)
    missing = []
    if not (S and S > 0):
        missing.append("ordering cost")
    if not (H and H > 0):
        missing.append("holding cost")
    if days_span < EOQ_MIN_DAYS:
        missing.append(f"a month of sales ({int(days_span)} of {EOQ_MIN_DAYS} days so far)")

    if not _blank(override) and _num(override) > 0:
        qty, basis = int(math.ceil(_num(override))), "yours"
    elif eoq_ready and eoq > moq:
        qty, basis = int(math.ceil(eoq)), "eoq"
    elif moq > 0:
        qty, basis = int(math.ceil(moq)), "moq"
    else:
        qty = int(max(1, math.ceil(avg_daily * lead_days * DOS_LEAD_MULTIPLE)))
        basis = "cover"
    return {"doq": qty, "doq_basis": basis,
            "doq_eoq": int(round(eoq)) if eoq else None,
            "eoq_ready": eoq_ready, "eoq_missing": missing,
            "monthly_consumption": round(monthly, 2),
            "annual_demand": round(annual, 1)}


def _enrich(item: dict, product_daily: dict, piv, maps_by_item: dict, meta: dict,
            linked: list[str] | None = None) -> dict:
    avg_daily, via_recipe = _item_daily_usage(item, product_daily, maps_by_item)
    std_daily = _item_daily_std(item, piv, maps_by_item)
    current = _num(item.get("current_stock"))
    moq = _int(item.get("moq"))
    annual_demand = avg_daily * 365.0
    span = int(meta.get("days_span", 0) or 0)
    enough = bool(meta.get("has_sales") and span >= MIN_DAYS_FOR_AUTO and avg_daily > 0)

    # --- lead time: not sales-derivable; fall back to a default when unset ---
    lead_raw = _num(item.get("lead_time_days"))
    lead_is_auto = lead_raw <= 0
    eff_lead = lead_raw if lead_raw > 0 else DEFAULT_LEAD_DAYS

    # --- safety stock: auto = Z * daily-demand std * sqrt(lead) ---
    auto_safety = None
    if enough and std_daily is not None and std_daily > 0:
        auto_safety = int(math.ceil(SERVICE_Z * std_daily * math.sqrt(eff_lead)))
    safety_raw = _num(item.get("safety_stock"))
    safety_is_auto = safety_raw <= 0 and auto_safety is not None
    eff_safety = safety_raw if safety_raw > 0 else (auto_safety or 0)

    # --- holding cost: auto = unit cost * holding % ---
    uc = _opt_num(item.get("unit_cost"))
    auto_holding = round(uc * HOLDING_PCT, 2) if uc and uc > 0 else None
    holding_raw = _opt_num(item.get("holding_cost"))
    holding_is_auto = (not holding_raw or holding_raw <= 0) and auto_holding is not None
    eff_holding = holding_raw if (holding_raw and holding_raw > 0) else auto_holding

    # --- ordering cost: business cost; suggest a default once selling ---
    auto_ordering = DEFAULT_ORDERING if enough else None
    ordering_raw = _opt_num(item.get("ordering_cost"))
    ordering_is_auto = (not ordering_raw or ordering_raw <= 0) and auto_ordering is not None
    eff_ordering = ordering_raw if (ordering_raw and ordering_raw > 0) else auto_ordering

    # --- days of supply, and the 1.2 × lead-time rule ---
    dos = round(current / avg_daily, 1) if avg_daily > 0 else None
    dos_threshold = round(DOS_LEAD_MULTIPLE * eff_lead, 1)
    needs_po = dos is not None and dos < dos_threshold
    # The same rule said as a stock level, for the seller who thinks in units:
    # order once stock falls below 1.2 × lead time × daily use.
    reorder_point = int(math.ceil(avg_daily * eff_lead * DOS_LEAD_MULTIPLE)) if avg_daily > 0 else 0
    below = bool(needs_po)

    # --- DOQ: MOQ until the seller's own S and H and a month of sales exist ---
    dq = doq_for(avg_daily, moq, ordering_raw, holding_raw, span, eff_lead,
                 override=item.get("reorder_qty"))
    order_qty = dq["doq"]
    basis = {"yours": "manual", "eoq": "eoq", "moq": "moq", "cover": "cover"}[dq["doq_basis"]]
    moq_applied = dq["doq_basis"] == "moq" and dq["doq_eoq"] is not None
    eoq_raw = (math.sqrt(2.0 * dq["annual_demand"] * ordering_raw / holding_raw)
               if dq["eoq_ready"] else None)

    est_line_cost = round(order_qty * float(uc), 2) if uc else None
    days_of_cover = dos
    suggestions_available = bool(enough and (safety_is_auto or holding_is_auto
                                             or ordering_is_auto or lead_is_auto))

    out = dict(item)
    out.update({
        "avg_daily_sales": round(avg_daily, 3),
        "avg_daily_consumption": round(avg_daily, 3),
        "std_daily": (round(std_daily, 3) if std_daily is not None else None),
        "usage_via_recipe": via_recipe,
        "linked_products": list(linked or []),
        "annual_demand": dq["annual_demand"] if dq["eoq_ready"] else round(annual_demand, 1),
        "monthly_consumption": dq["monthly_consumption"],
        "eoq": dq["doq_eoq"],
        "dos": dos,
        "dos_threshold": dos_threshold,
        "needs_po": bool(needs_po),
        "doq": dq["doq"],
        "doq_basis": dq["doq_basis"],
        "doq_override": (None if _blank(item.get("reorder_qty")) else _num(item.get("reorder_qty"))),
        "eoq_ready": dq["eoq_ready"],
        "eoq_missing": dq["eoq_missing"],
        "reorder_point": reorder_point,
        "below_reorder": below,
        "order_qty": int(order_qty),
        "order_basis": basis,
        "moq_applied": moq_applied,
        "suggested_qty": int(order_qty) if below else 0,
        "est_line_cost": est_line_cost,
        "days_of_cover": days_of_cover,
        # effective (used for the maths) + which came from auto-fill
        "effective_lead_time_days": round(eff_lead, 2),
        "effective_safety_stock": int(eff_safety),
        "effective_ordering_cost": (round(eff_ordering, 2) if eff_ordering else None),
        "effective_holding_cost": (round(eff_holding, 2) if eff_holding else None),
        "auto_safety_stock": auto_safety,
        "auto_ordering_cost": auto_ordering,
        "auto_holding_cost": auto_holding,
        "lead_is_auto": lead_is_auto,
        "safety_is_auto": safety_is_auto,
        "holding_is_auto": holding_is_auto,
        "ordering_is_auto": ordering_is_auto,
        "has_enough_sales": enough,
        "suggestions_available": suggestions_available,
        "reason": _reason_text(item, avg_daily, dos, dos_threshold, current, eoq_raw,
                               dq, eff_lead, lead_is_auto, below),
    })
    return out


def _reason_text(item, avg_daily, dos, dos_threshold, current, eoq_raw, dq,
                 eff_lead, lead_is_auto, below) -> str:
    """The sentence the seller reads. Written for someone who has never taken a
    supply-chain class, because that is who this is for.

    "You use about 3 a day, so what you have lasts 9 days; your supplier takes
    10, and we want 12 days in hand" says the same thing as "DOS below 1.2 × LT"
    and can be checked by the person reading it, which is the whole point of
    showing a reason at all."""
    unit = item.get("unit_label") or "unit"
    if avg_daily <= 0:
        return ("We do not know how fast this is used up yet. Link it to the products "
                "that use it (and how much each uses), and once there are sales we "
                "will work out how many days it lasts and when to order.")
    days = int(round(eff_lead))
    base = (f"You use about {round(avg_daily, 2)} {unit} a day, so the {int(current)} "
            f"you have lasts about {dos:g} day{'s' if dos != 1 else ''}. Your supplier takes "
            f"{days} day{'s' if days != 1 else ''}{' (assumed — add the real number)' if lead_is_auto else ''}, "
            f"and we keep {dos_threshold:g} days in hand — the lead time plus 20%.")
    if not below:
        return base + " Plenty for now."
    b = dq["doq_basis"]
    if b == "yours":
        q = f" Ordering {dq['doq']} {unit}, the quantity you set."
    elif b == "eoq":
        q = (f" Ordering {dq['doq']} {unit}: with your ordering and holding costs, that "
             f"is the cheapest amount to buy at a time (above the supplier's minimum).")
    elif b == "moq":
        q = (f" Ordering {dq['doq']} {unit}, the supplier's minimum."
             + (f" Add {', '.join(dq['eoq_missing'])} and we will work out the "
                f"cheapest quantity instead." if dq["eoq_missing"] else
                " The cheapest quantity works out below it, so the minimum stands."))
    else:
        q = (f" Ordering {dq['doq']} {unit} — enough to cover the wait. Add the supplier's "
             f"minimum order to use that instead.")
    return base + " Time to order." + q

def _disp(v) -> str:
    """Trim without destroying case — _norm() lowercases, which is right for
    matching and wrong for anything shown to a person."""
    return str(v or "").strip()


def get_suppliers(email: str) -> list[dict]:
    email = _email(email)
    by_name: dict[str, dict] = {}
    for it in get_inventory(email):
        name = _disp(it.get("supplier_name"))
        if not name:
            continue
        key = name.lower()
        sup = by_name.setdefault(key, {
            "name": name,
            "phone": _disp(it.get("supplier_phone")),
            "email": _disp(it.get("supplier_email")),
            "items": [], "item_count": 0, "stock_value": 0.0, "lead_time_days": None,
        })
        # first non-empty contact detail wins; a later blank never erases one
        sup["phone"] = sup["phone"] or _disp(it.get("supplier_phone"))
        sup["email"] = sup["email"] or _disp(it.get("supplier_email"))
        lead = _opt_num(it.get("lead_time_days"))
        if lead:
            sup["lead_time_days"] = max(sup["lead_time_days"] or 0, lead)
        sup["items"].append({"id": it.get("id"), "name": it.get("name"),
                             "current_stock": _num(it.get("current_stock")),
                             "unit_label": it.get("unit_label") or "unit",
                             "moq": _num(it.get("moq")),
                             "unit_cost": _opt_num(it.get("unit_cost"))})
        sup["item_count"] += 1
        sup["stock_value"] += _num(it.get("current_stock")) * (_num(it.get("unit_cost")) or 0)
    out = list(by_name.values())
    for sup in out:
        sup["stock_value"] = round(sup["stock_value"], 2)
    return sorted(out, key=lambda x: x["name"].lower())


def upsert_supplier(email: str, name: str, patch: dict) -> list[dict]:
    """Rename a supplier or change their contact details, across every item they
    supply. `name` identifies the existing supplier; patch may carry a new one."""
    email = _email(email)
    name = _disp(name)
    if not name:
        raise ValueError("Which supplier?")
    new_name = _disp(patch.get("name")) or name
    phone = _disp(patch.get("phone"))
    mail = _disp(patch.get("email"))
    touched = 0
    for it in get_inventory(email):
        if _disp(it.get("supplier_name")).lower() != name.lower():
            continue
        updated = dict(it)
        updated["supplier_name"] = new_name
        updated["supplier_phone"] = phone
        updated["supplier_email"] = mail
        if patch.get("lead_time_days") not in (None, ""):
            updated["lead_time_days"] = _num(patch.get("lead_time_days"))
        upsert_item(email, updated)
        touched += 1
    if not touched:
        raise ValueError(f"No inventory items are supplied by “{name}”.")
    return get_suppliers(email)


def detach_supplier(email: str, name: str) -> dict:
    """Clear a supplier from every item. The items themselves are untouched —
    removing a supplier must never delete your stock.

    Returns the item ids that were cleared, so the caller can offer an undo:
    once the last item is cleared the supplier no longer exists to look up by
    name, so re-attaching has to work from ids.
    """
    email = _email(email)
    name = _disp(name)
    touched = []
    for it in get_inventory(email):
        if _disp(it.get("supplier_name")).lower() != name.lower():
            continue
        touched.append(it.get("id"))
        upsert_item(email, {**it, "supplier_name": "", "supplier_phone": "",
                            "supplier_email": ""})
    return {"suppliers": get_suppliers(email), "detached_item_ids": touched}


def attach_supplier(email: str, item_ids: list[str], supplier: dict) -> list[dict]:
    """Put a supplier back on specific items — the undo for detach_supplier."""
    email = _email(email)
    wanted = {str(i) for i in (item_ids or []) if i}
    for it in get_inventory(email):
        if it.get("id") not in wanted:
            continue
        upsert_item(email, {**it,
                            "supplier_name": _disp(supplier.get("name")),
                            "supplier_phone": _disp(supplier.get("phone")),
                            "supplier_email": _disp(supplier.get("email"))})
    return get_suppliers(email)


def compute_inventory(email: str) -> dict:
    email = _email(email)
    product_daily, piv, meta = _demand_stats(email)
    mbi = _maps_by_item(email)
    linked: dict[str, list[str]] = {}
    for m in get_maps(email):
        linked.setdefault(m["inventory_id"], []).append(m["product"])
    rows = [_enrich(it, product_daily, piv, mbi, meta, linked.get(it["id"]))
            for it in get_inventory(email)]
    rows.sort(key=lambda r: (not r["below_reorder"], _norm(r.get("name"))))
    below = [r for r in rows if r["below_reorder"]]
    return {"items": rows, "below": below, "meta": meta, "n_below": len(below)}


def import_products_from_sales(email: str) -> list[dict]:
    """Seed inventory rows for any product in the sales data not already tracked
    (blank stock, a default 7-day lead time, for the owner to adjust)."""
    email = _email(email)
    txns = smart.load_supply_sales(email)
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
    """Raw materials below the DOS rule with no purchase order on its way.

    Items already on a draft/open/sent order are left out — they have their
    own purchase-order card, and listing them twice would invite a second
    order to the same supplier."""
    below = compute_inventory(email)["below"]
    try:
        from backend.core import replenish
        covered = replenish.covered_item_ids(email)
        below = [r for r in below if r["id"] not in covered]
    except Exception:  # noqa: BLE001
        pass
    if not below:
        return None
    names = ", ".join(r.get("name", "?") for r in below[:4])
    if len(below) > 4:
        names += f" +{len(below) - 4} more"
    plural = "s" if len(below) != 1 else ""
    return {
        "id": "reorder", "module": "supply", "page": "supply", "icon": "📦",
        "title": f"{len(below)} item{plural} running low — order more",
        "detail": (f"{names} {'are' if len(below) != 1 else 'is'} down to fewer days of supply "
                   "than 1.2 × the supplier's lead time. Approve and we will draft one purchase "
                   "order per supplier at each item's default order quantity, for you to check "
                   "and send."),
        "action_label": "Approve → draft purchase orders",
        "count": len(below), "names": names,
        # the tightest item, so Operations can lead with the real urgency
        # rather than a count
        "min_cover": min((_num(r.get("days_of_cover")) for r in below
                          if _num(r.get("days_of_cover")) > 0), default=None),
        "has_download": False,
    }


OVERSTOCK_DAYS = 90          # more cover than this and cash is idling
MIN_ROWS_FOR_OVERSTOCK = 3   # below this the sales rate is too noisy to judge


def build_overstock_insight(email: str) -> dict | None:
    """Items we are holding far more of than the sales rate justifies.

    The mirror of the reorder card, and the one nobody builds. Running out is
    loud — a customer complains. Overstock is silent: the money is simply not
    there when a seller wants to buy the thing that IS selling, and nothing in
    the app ever says why.

    Deliberately conservative. An item with no sales history has no meaningful
    days-of-cover, so it is skipped rather than guessed at — telling a seller
    to stop buying something on the basis of no data is worse than saying
    nothing."""
    comp = compute_inventory(email)
    rows = [r for r in comp["items"]
            if r.get("has_enough_sales")
            and _num(r.get("avg_daily_sales")) > 0
            and _num(r.get("days_of_cover")) > OVERSTOCK_DAYS]
    if len(rows) < 1:
        return None
    rows.sort(key=lambda r: -_num(r.get("days_of_cover")))
    names = ", ".join(r.get("name", "?") for r in rows[:4])
    if len(rows) > 4:
        names += f" +{len(rows) - 4} more"
    tied = 0.0
    for r in rows:
        uc = r.get("unit_cost")
        if not _blank(uc):
            tied += _num(r.get("current_stock")) * float(uc)
    return {
        "id": "overstock", "module": "supply", "page": "inventory", "icon": "📊",
        "title": f"{len(rows)} item{'s' if len(rows) != 1 else ''} overstocked",
        "detail": (f"{names} hold more than {OVERSTOCK_DAYS} days of cover at the "
                   f"current sales rate."),
        "action_label": "Review holdings",
        "count": len(rows), "names": names,
        "tied_up": round(tied, 2) if tied else None,
        "item_ids": [r["id"] for r in rows],
        "has_download": False,
    }


def build_supplier_risk_insight(email: str) -> dict | None:
    """Items with exactly one supplier and no alternative on file.

    Single-sourcing is invisible until the day it is not. It also removes the
    only honest price benchmark a small seller has — with one quote there is no
    way to know whether it is a good one."""
    items = get_inventory(email)
    if not items:
        return None
    # Count how many distinct suppliers exist across the whole account. With
    # only one supplier in total this is a business fact, not an insight worth
    # nagging about every week.
    suppliers = {_norm(i.get("supplier_name")) for i in items if (i.get("supplier_name") or "").strip()}
    if len(suppliers) < 2:
        return None
    lonely = [i for i in items
              if (i.get("supplier_name") or "").strip()
              and _num(i.get("current_stock")) > 0]
    by_supplier: dict[str, list] = {}
    for i in lonely:
        by_supplier.setdefault(_norm(i.get("supplier_name")), []).append(i)
    # An item is exposed when its supplier is the only one we buy that
    # category from.
    exposed = []
    for name, group in by_supplier.items():
        if len(group) >= 2:
            exposed.extend(group)
    if not exposed:
        return None
    exposed.sort(key=lambda r: -_num(r.get("current_stock")))
    names = ", ".join(r.get("name", "?") for r in exposed[:4])
    if len(exposed) > 4:
        names += f" +{len(exposed) - 4} more"
    return {
        "id": "supplier_risk", "module": "supply", "page": "supply", "icon": "🔗",
        "title": f"{len(exposed)} item{'s' if len(exposed) != 1 else ''} single-sourced",
        "detail": f"{names} come from one supplier with no alternative on file.",
        "action_label": "Find alternatives",
        "count": len(exposed), "names": names,
        "item_ids": [r["id"] for r in exposed],
        "has_download": False,
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


def create_pos_by_supplier(email: str, insight_id: str | None = None) -> list[dict]:
    """One purchase order per SUPPLIER for everything currently running low.

    This is what the seller actually needs, and it is not what create_po() gave
    them. One PO listing four items from three different suppliers cannot be
    sent to anybody — the seller has to retype it three times, which is exactly
    the manual work the app is supposed to remove. Worse, the approval path
    called create_po(email, insight_id) with the insight id landing in the
    item_ids argument, so approving "items running low" quietly produced no
    purchase order at all.

    So: group the low items by supplier, make one sendable order per supplier,
    and give items with no supplier linked their own order marked as such — a
    seller who has not filled in supplier details still gets a list to work
    from rather than silence.
    """
    email = _email(email)
    comp = compute_inventory(email)
    low = comp.get("below") or []
    if not low:
        return []

    groups: dict[str, list[dict]] = {}
    for r in low:
        key = (str(r.get("supplier_name") or "").strip().lower() or "__none__")
        groups.setdefault(key, []).append(r)

    made: list[dict] = []
    # Deterministic order: named suppliers alphabetically, unassigned last, so
    # the list does not reshuffle between refreshes.
    for key in sorted(groups, key=lambda k: (k == "__none__", k)):
        rows = groups[key]
        po = create_po(email, item_ids=[r["id"] for r in rows], insight_id=insight_id)
        if not po:
            continue
        po["supplier_name"] = (rows[0].get("supplier_name") or "").strip()
        po["supplier_phone"] = (rows[0].get("supplier_phone") or "").strip()
        po["supplier_email"] = (rows[0].get("supplier_email") or "").strip()
        po["unassigned_supplier"] = key == "__none__"
        made.append(po)
    return made


def create_manual_po(email: str, supplier: dict, lines: list[dict],
                     expected_on: str = "", terms: str = "", note: str = "") -> dict:
    """A purchase order the seller types out, rather than one derived from
    reorder points.

    The automatic PO only knows about items already in Inventory that have
    fallen below their reorder point. That covers restocking and nothing else —
    not a first order from a new supplier, not a sample run, not a one-off
    festive buy, not fabric for a product that does not exist yet. Those are
    most of the purchase orders a small seller actually raises, which is why
    this exists rather than forcing everything through the suggestion engine.

    Lines are free-text on purpose: a supplier order often names things the way
    the SUPPLIER calls them, which is not what Inventory calls them. Where a
    line does match an inventory item the id is kept so receiving can post
    stock against it."""
    email = _email(email)
    lines = lines or []
    if not lines:
        raise ValueError("A purchase order needs at least one line.")

    clean, total_qty, total_amount, has_cost = [], 0, 0.0, False
    for r in lines:
        name = str(r.get("name") or "").strip()[:120]
        if not name:
            continue
        qty = int(_num(r.get("order_qty")) or 0)
        if qty <= 0:
            continue
        unit_cost = r.get("unit_cost")
        amount = round(qty * float(unit_cost), 2) if not _blank(unit_cost) else None
        if amount is not None:
            total_amount += amount
            has_cost = True
        total_qty += qty
        clean.append({
            "inventory_id": str(r.get("inventory_id") or ""),
            "name": name,
            "category": str(r.get("category") or "").strip()[:60],
            "unit_label": str(r.get("unit_label") or "unit").strip()[:20],
            "supplier_name": str(supplier.get("name") or "").strip()[:120],
            "supplier_phone": str(supplier.get("phone") or "").strip()[:20],
            "supplier_email": str(supplier.get("email") or "").strip()[:120],
            "order_qty": qty,
            "unit_cost": (None if _blank(unit_cost) else float(unit_cost)),
            "line_amount": amount,
            "note": str(r.get("note") or "").strip()[:200],
        })
    if not clean:
        raise ValueError("Every line needs a name and a quantity above zero.")

    number = _next_po_number(email)
    po = {
        "id": number, "po_number": number, "insight_id": None,
        "created_at": _now_iso(), "status": "open", "source": "manual",
        "supplier": {"name": str(supplier.get("name") or "").strip()[:120],
                     "phone": str(supplier.get("phone") or "").strip()[:20],
                     "email": str(supplier.get("email") or "").strip()[:120],
                     "address": str(supplier.get("address") or "").strip()[:300]},
        "expected_on": str(expected_on or "")[:10],
        "terms": str(terms or "").strip()[:200],
        "note": str(note or "").strip()[:400],
        "n_items": len(clean), "total_qty": int(total_qty),
        "total_amount": round(total_amount, 2) if has_cost else None,
        "suppliers": [supplier.get("name")] if supplier.get("name") else [],
        "lines": clean,
        "history": [{"at": _now_iso(), "status": "open", "by": "seller"}],
    }

    if _tables():
        row = dict(po); row["email"] = email
        db.insert(T_PO, row)
    else:
        pos = user_store.get_key(email, PO_KEY, []) or []
        pos.append(po)
        user_store.set_key(email, PO_KEY, pos)
    return po


# "draft" — raised automatically by the replenishment check and waiting in the
# Approval panel. Nothing has gone to the supplier yet.
PO_STATUSES = ["draft", "open", "sent", "shipped", "received", "cancelled"]
ACTIVE_PO_STATUSES = ("draft", "open", "sent", "shipped")


def _save_po_rows(email: str, pos: list[dict]) -> None:
    user_store.set_key(_email(email), PO_KEY, pos)


def update_po(email: str, po_number: str, patch: dict) -> dict | None:
    """Change fields on one PO (lines, totals, supplier, status, history)."""
    email = _email(email)
    pos = get_purchase_orders(email)
    target = next((p for p in pos if str(p.get("po_number")) == str(po_number)), None)
    if target is None:
        return None
    target.update(patch or {})
    if _tables():
        db.update(T_PO, {"email": email, "po_number": str(po_number)}, dict(patch or {}))
    else:
        _save_po_rows(email, pos)
    return target


def _totals(lines: list[dict]) -> dict:
    total_qty, total_amount, has_cost = 0, 0.0, False
    for ln in lines:
        total_qty += int(ln.get("order_qty") or 0)
        if ln.get("line_amount") is not None:
            total_amount += float(ln["line_amount"])
            has_cost = True
    return {"n_items": len(lines), "total_qty": int(total_qty),
            "total_amount": round(total_amount, 2) if has_cost else None}


def auto_po_line(r: dict) -> dict:
    """One PO line from an enriched inventory row: the DOQ, plus why."""
    line = _po_line(r)
    line.update({
        "dos": r.get("dos"), "dos_threshold": r.get("dos_threshold"),
        "doq_basis": r.get("doq_basis"), "linked_products": r.get("linked_products") or [],
        "moq": _num(r.get("moq")),
    })
    return line


def create_auto_po(email: str, rows: list[dict], supplier: dict, note: str = "",
                   trigger: str = "") -> dict:
    """A DRAFT purchase order raised by the replenishment check — one supplier,
    one or more raw materials, each at its DOQ. It waits in the Approval panel
    until the seller approves it, which is when it is emailed."""
    email = _email(email)
    lines = [auto_po_line(r) for r in rows]
    number = _next_po_number(email)
    po = {
        "id": number, "po_number": number, "insight_id": None,
        "created_at": _now_iso(), "status": "draft", "source": "auto",
        "supplier": {"name": _disp(supplier.get("name"))[:120],
                     "phone": _disp(supplier.get("phone"))[:20],
                     "email": _disp(supplier.get("email"))[:120],
                     "address": ""},
        "expected_on": "", "terms": "",
        "note": str(note or "")[:400],
        "suppliers": [supplier.get("name")] if supplier.get("name") else [],
        "lines": lines,
        "history": [{"at": _now_iso(), "status": "draft", "by": "auto",
                     "note": str(trigger or "")[:200]}],
        **_totals(lines),
    }
    if _tables():
        row = dict(po); row["email"] = email
        db.insert(T_PO, row)
    else:
        pos = user_store.get_key(email, PO_KEY, []) or []
        pos.append(po)
        user_store.set_key(email, PO_KEY, pos)
    return po


def append_to_po(email: str, po_number: str, rows: list[dict], trigger: str = "") -> dict | None:
    """Add raw materials to a draft PO that is already waiting for the same
    supplier, instead of raising a second order to the same person."""
    po = get_po(email, po_number)
    if not po:
        return None
    lines = list(po.get("lines") or [])
    have = {ln.get("inventory_id") for ln in lines}
    for r in rows:
        if r.get("id") not in have:
            lines.append(auto_po_line(r))
    hist = list(po.get("history") or []) + [
        {"at": _now_iso(), "status": "draft", "by": "auto", "note": str(trigger or "")[:200]}]
    return update_po(email, po_number, {"lines": lines, "history": hist, **_totals(lines)})


def set_po_line_qty(email: str, po_number: str, qty_by_item: dict) -> dict | None:
    """Change quantities on a draft PO before it is sent. A quantity of 0 drops
    the line."""
    po = get_po(email, po_number)
    if not po:
        return None
    if po.get("status") not in ("draft", "open"):
        raise ValueError("Only an order that has not been sent can be changed.")
    lines = []
    for ln in po.get("lines") or []:
        iid = ln.get("inventory_id")
        if iid in qty_by_item:
            q = int(max(0, round(_num(qty_by_item[iid]))))
            if q <= 0:
                continue
            ln = dict(ln)
            ln["order_qty"] = q
            uc = ln.get("unit_cost")
            ln["line_amount"] = round(q * float(uc), 2) if not _blank(uc) else None
        lines.append(ln)
    if not lines:
        raise ValueError("An order needs at least one line — cancel it instead.")
    return update_po(email, po_number, {"lines": lines, **_totals(lines)})


def set_po_status(email: str, po_number: str, status: str,
                  note: str = "", by: str = "seller") -> dict | None:
    """Move a PO along. Receiving posts stock back into Inventory, because a PO
    that arrives and does not update stock is worse than no PO at all — the
    seller now has to remember to do it manually and will not."""
    if status not in PO_STATUSES:
        raise ValueError(f"status must be one of {PO_STATUSES}")
    email = _email(email)
    pos = get_purchase_orders(email)
    target = None
    for po in pos:
        if str(po.get("po_number")) == str(po_number):
            target = po
            break
    if target is None:
        return None

    was = target.get("status")
    target["status"] = status
    target.setdefault("history", []).append(
        {"at": _now_iso(), "status": status, "by": by, "note": str(note or "")[:200]})

    if status == "received" and was != "received":
        for ln in target.get("lines", []):
            if ln.get("inventory_id"):
                try:
                    receive_stock(email, ln["inventory_id"],
                                  float(ln.get("order_qty") or 0),
                                  reason=f"PO {po_number} received")
                except Exception:  # noqa: BLE001
                    pass

    if _tables():
        db.update(T_PO, {"email": email, "po_number": str(po_number)},
                  {"status": status, "history": target.get("history")})
    else:
        rows = user_store.get_key(email, PO_KEY, []) or []
        for r in rows:
            if str(r.get("po_number")) == str(po_number):
                r["status"] = status
                r["history"] = target.get("history")
        user_store.set_key(email, PO_KEY, rows)
    return target


# ---------------------------------------------------------
# exports
# ---------------------------------------------------------
def po_pdf_bytes(email: str, po: dict, for_supplier: bool = False) -> tuple[str, io.BytesIO]:
    """Render the PO to a professional PDF. Returns (filename, BytesIO)."""
    from backend.core import po_pdf
    try:
        from backend.core import brandname
        brand = brandname.display(email)
    except Exception:  # noqa: BLE001
        brand = "Your shop"
    buf = po_pdf.build_po_pdf(po, buyer_email=email, brand=brand, for_supplier=for_supplier)
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
