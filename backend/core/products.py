"""
Smart CafeX — Product Management.

Canonical products are what the seller actually sells (e.g. "ABC"). The same
product often appears on a sales platform under a different name (e.g. "DRF" on
Amazon). A product can carry any number of platform aliases; sales rows are
rolled up from aliases to the canonical product across the whole app, and the
Supply module links inventory recipes to the canonical product.

Storage is dual-mode, matching the rest of the backend: the `products` and
`product_aliases` Supabase tables when configured, else per-account JSON state.
Reads tolerate a not-yet-created table (run supabase/products.sql once) so a
missing table can never blank the app.

`smart` is imported lazily (for load_sales) to avoid an import cycle.
"""
from __future__ import annotations

import secrets

import pandas as pd

from backend.core import db, user_store

PROD_KEY = "smart_products"            # JSON fallback
ALIAS_KEY = "smart_product_aliases"
SIDECAR_KEY = "smart_product_storefront"   # storefront fields when the DB lacks the columns
T_PROD = "products"
T_ALIAS = "product_aliases"


def _tables() -> bool:
    return bool(db.SUPABASE_ENABLED)


def _email(email: str) -> str:
    return (email or "").strip().lower()


def _norm(s) -> str:
    return str(s or "").strip().lower()


def _blank(v) -> bool:
    return v is None or v == ""


def _opt_num(v):
    if _blank(v):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _now_iso() -> str:
    return pd.Timestamp.now().isoformat(timespec="seconds")


def _safe_fetch(table: str, match: dict) -> list[dict]:
    try:
        return db.fetch_all(table, match)
    except Exception as e:  # noqa: BLE001 - defensive: table may not exist yet
        import logging
        logging.getLogger("products").warning(
            "product read on %r failed (%s); is supabase/products.sql run?", table, e)
        return []


# ---------------------------------------------------------
# normalisation
# ---------------------------------------------------------
def _bool(v, default=True) -> bool:
    """Tolerant truthiness — JSON, Supabase and form values all land here."""
    if v is None or v == "":
        return default
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


def _int(v, default=0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _str_list(v, limit=8, maxlen=300) -> list[str]:
    if v is None or v == "":
        return []
    if isinstance(v, str):
        try:
            import json as _json
            v = _json.loads(v)
        except Exception:
            v = [x for x in v.split("\n")]
    if not isinstance(v, (list, tuple)):
        return []
    out = []
    for x in v:
        s = str(x or "").strip()
        if s:
            out.append(s[:maxlen])
        if len(out) >= limit:
            break
    return out


# Fields added for the Website Builder storefront. Kept in one place so the
# Supabase writer can drop them cleanly on a database that has not run
# supabase/site.sql yet (see _upsert_row).
STOREFRONT_FIELDS = ("description", "image_url", "images", "mrp", "stock",
                     "track_stock", "listed", "highlights", "unit_label")


def _norm_product(raw: dict) -> dict:
    return {
        "id": raw.get("id") or secrets.token_hex(8),
        "name": (raw.get("name") or "").strip(),
        "category": (raw.get("category") or "").strip(),
        "sku": (raw.get("sku") or "").strip(),
        "price": _opt_num(raw.get("price")),
        "unit_cost": _opt_num(raw.get("unit_cost")),
        "status": (raw.get("status") or "active").strip() or "active",
        # ---- storefront ----
        "description": (raw.get("description") or "").strip()[:4000],
        "image_url": (raw.get("image_url") or "").strip()[:500],
        "images": _str_list(raw.get("images"), limit=8, maxlen=500),
        "mrp": _opt_num(raw.get("mrp")),
        "stock": _int(raw.get("stock"), 0),
        "track_stock": _bool(raw.get("track_stock"), True),
        # every product is listed on the site by default — the seller turns it
        # off per product from the Product Management page.
        "listed": _bool(raw.get("listed"), True),
        "highlights": _str_list(raw.get("highlights"), limit=6, maxlen=200),
        "unit_label": (raw.get("unit_label") or "").strip()[:40],
    }


def _norm_alias(raw: dict) -> dict:
    return {
        "id": raw.get("id") or secrets.token_hex(8),
        "product_id": raw.get("product_id") or "",
        "alias": (raw.get("alias") or "").strip(),
        "platform": (raw.get("platform") or "").strip(),
    }


# ---------------------------------------------------------
# raw accessors
# ---------------------------------------------------------
def _products_raw(email: str) -> list[dict]:
    email = _email(email)
    if _tables():
        rows = _safe_fetch(T_PROD, {"email": email})
        side = user_store.get_key(email, SIDECAR_KEY, {}) or {}
        if side:
            merged = []
            for r in rows:
                extra = side.get(r.get("id")) or {}
                merged.append({**r, **{k: v for k, v in extra.items() if v not in (None, "")}}
                              if extra else r)
            rows = merged
    else:
        rows = user_store.get_key(email, PROD_KEY, []) or []
        rows = rows if isinstance(rows, list) else []
    return [_norm_product(r) for r in rows]


def get_aliases(email: str) -> list[dict]:
    email = _email(email)
    if _tables():
        rows = _safe_fetch(T_ALIAS, {"email": email})
    else:
        rows = user_store.get_key(email, ALIAS_KEY, []) or []
        rows = rows if isinstance(rows, list) else []
    return [_norm_alias(r) for r in rows]


# ---------------------------------------------------------
# products CRUD
# ---------------------------------------------------------
def get_products(email: str) -> list[dict]:
    """Canonical products, each with its aliases embedded, sorted by name."""
    email = _email(email)
    prods = _products_raw(email)
    aliases = get_aliases(email)
    by_prod: dict[str, list[dict]] = {}
    for a in aliases:
        by_prod.setdefault(a["product_id"], []).append(a)
    out = []
    for p in prods:
        p = dict(p)
        p["aliases"] = by_prod.get(p["id"], [])
        out.append(p)
    out.sort(key=lambda r: _norm(r.get("name")))
    return out


def _upsert_row(row: dict) -> None:
    """Write a product row to Supabase, surviving a database that has not run
    supabase/site.sql yet: on a column error we retry with the storefront
    fields stripped and keep them in the per-account JSON state instead, so a
    seller never loses a save because of a pending migration."""
    try:
        db.upsert(T_PROD, row, on_conflict="id")
        return
    except Exception as e:  # noqa: BLE001 - column may not exist yet
        import logging
        logging.getLogger("products").warning(
            "product upsert with storefront columns failed (%s); "
            "retrying without them — run supabase/site.sql to migrate.", e)
    slim = {k: v for k, v in row.items() if k not in STOREFRONT_FIELDS}
    db.upsert(T_PROD, slim, on_conflict="id")
    extra = {k: row.get(k) for k in STOREFRONT_FIELDS}
    side = user_store.get_key(row["email"], SIDECAR_KEY, {}) or {}
    side[row["id"]] = extra
    user_store.set_key(row["email"], SIDECAR_KEY, side)


def upsert_product(email: str, item: dict) -> list[dict]:
    email = _email(email)
    current = _products_raw(email)
    iid = item.get("id")
    exists = bool(iid) and any(p["id"] == iid for p in current)
    clean = _norm_product(item)
    clean["id"] = iid if exists else (item.get("id") or secrets.token_hex(8))
    clean["name"] = clean["name"][:160]
    if not clean["name"]:
        raise ValueError("Product name is required.")
    clean["category"] = clean["category"][:80]
    clean["sku"] = clean["sku"][:80]
    if clean["status"] not in ("active", "archived"):
        clean["status"] = "active"
    if clean["stock"] < 0:
        clean["stock"] = 0
    # an archived product is never on the storefront
    if clean["status"] == "archived":
        clean["listed"] = False

    if _tables():
        row = dict(clean)
        row["email"] = email
        row["updated_at"] = _now_iso()
        _upsert_row(row)
    else:
        if exists:
            items = [clean if p["id"] == clean["id"] else p for p in current]
        else:
            items = current + [clean]
        user_store.set_key(email, PROD_KEY, items)
    return get_products(email)


def delete_product(email: str, product_id: str) -> list[dict]:
    email = _email(email)
    if _tables():
        db.delete(T_ALIAS, {"email": email, "product_id": product_id})
        db.delete(T_PROD, {"id": product_id, "email": email})
    else:
        items = [p for p in _products_raw(email) if p["id"] != product_id]
        user_store.set_key(email, PROD_KEY, items)
        al = [a for a in get_aliases(email) if a["product_id"] != product_id]
        user_store.set_key(email, ALIAS_KEY, al)
    return get_products(email)


# ---------------------------------------------------------
# aliases CRUD
# ---------------------------------------------------------
def add_alias(email: str, product_id: str, alias: str, platform: str = "") -> list[dict]:
    email = _email(email)
    alias = (alias or "").strip()
    platform = (platform or "").strip()[:60]
    if not alias:
        raise ValueError("An alias (the platform product name) is required.")
    if not any(p["id"] == product_id for p in _products_raw(email)):
        raise ValueError("Choose an existing product to link the alias to.")
    existing = next((a for a in get_aliases(email) if _norm(a["alias"]) == _norm(alias)), None)

    if _tables():
        if existing:
            db.update(T_ALIAS, {"id": existing["id"], "email": email},
                      {"product_id": product_id, "platform": platform})
        else:
            db.insert(T_ALIAS, {
                "id": secrets.token_hex(8), "email": email, "product_id": product_id,
                "alias": alias[:160], "platform": platform,
            })
    else:
        al = get_aliases(email)
        if existing:
            for a in al:
                if a["id"] == existing["id"]:
                    a["product_id"] = product_id
                    a["platform"] = platform
        else:
            al.append({"id": secrets.token_hex(8), "product_id": product_id,
                       "alias": alias[:160], "platform": platform})
        user_store.set_key(email, ALIAS_KEY, al)
    return get_products(email)


def delete_alias(email: str, alias_id: str) -> list[dict]:
    email = _email(email)
    if _tables():
        db.delete(T_ALIAS, {"id": alias_id, "email": email})
    else:
        al = [a for a in get_aliases(email) if a["id"] != alias_id]
        user_store.set_key(email, ALIAS_KEY, al)
    return get_products(email)


# ---------------------------------------------------------
# roll-up: platform name -> canonical product name
# ---------------------------------------------------------
def alias_map(email: str) -> dict:
    """{normalised name -> canonical product display name}. Includes each
    product's own name (so canonical names stay stable) and every alias."""
    prods = _products_raw(email)
    by_id = {p["id"]: p["name"] for p in prods}
    m: dict[str, str] = {}
    for p in prods:
        if p["name"]:
            m[_norm(p["name"])] = p["name"]
    for a in get_aliases(email):
        name = by_id.get(a["product_id"])
        if name and a["alias"]:
            m[_norm(a["alias"])] = name
    return m


def canonicalize_df(email: str, df):
    """Return a copy of a transactions frame whose `product` column is rolled up
    to canonical product names. Unknown names pass through unchanged. Safe to
    call with no products defined (returns the frame unchanged)."""
    try:
        if df is None or "product" not in getattr(df, "columns", []):
            return df
        m = alias_map(email)
        if not m:
            return df
        out = df.copy()
        out["product"] = out["product"].map(lambda v: m.get(_norm(v), v))
        return out
    except Exception:
        return df


def product_names(email: str) -> list[str]:
    """Active canonical product names (for the Supply links picker)."""
    return sorted((p["name"] for p in _products_raw(email)
                   if p["name"] and p["status"] != "archived"), key=_norm)


# ---------------------------------------------------------
# sales-side helpers (for the Product Management page)
# ---------------------------------------------------------
def sales_product_names(email: str) -> list[str]:
    """Distinct raw product names as they appear in the account's Sales data."""
    from backend.core import smart
    txns = smart.load_sales(email)
    names: dict[str, str] = {}
    if txns is not None and "product" in getattr(txns, "columns", []):
        for p in txns["product"].dropna():
            n = _norm(p)
            if n and n not in names:
                names[n] = str(p).strip()
    return [names[k] for k in sorted(names)]


def unmatched_sales_names(email: str) -> list[str]:
    """Raw sales product names not yet covered by any product name or alias —
    i.e. platform names still waiting to be linked to a canonical product."""
    m = alias_map(email)
    return [n for n in sales_product_names(email) if _norm(n) not in m]


# ---------------------------------------------------------
# storefront helpers (Website Builder)
# ---------------------------------------------------------
def get_product(email: str, product_id: str) -> dict | None:
    return next((p for p in get_products(email) if p["id"] == product_id), None)


def listed_products(email: str) -> list[dict]:
    """Active products the seller has switched on for their own website."""
    return [p for p in get_products(email)
            if p.get("listed") and p.get("status") != "archived"]


def in_stock(p: dict) -> bool:
    if not p.get("track_stock", True):
        return True
    return _int(p.get("stock"), 0) > 0


def available_units(p: dict) -> int | None:
    """Units a shopper may buy, or None when this product is not stock-tracked."""
    if not p.get("track_stock", True):
        return None
    return max(0, _int(p.get("stock"), 0))


def adjust_stock(email: str, product_id: str, delta: int) -> dict | None:
    """Move a stock-tracked product's units by `delta` (negative = sold).
    No-ops for products that do not track stock. Returns the updated product."""
    email = _email(email)
    raw = next((p for p in _products_raw(email) if p["id"] == product_id), None)
    if not raw or not raw.get("track_stock", True):
        return raw
    updated = dict(raw)
    updated["stock"] = max(0, _int(raw.get("stock"), 0) + int(delta))
    upsert_product(email, updated)
    return updated


def set_listed(email: str, product_id: str, listed: bool) -> list[dict]:
    """Flip a single product's 'show on my website' switch."""
    raw = next((p for p in _products_raw(_email(email)) if p["id"] == product_id), None)
    if not raw:
        raise ValueError("Product not found.")
    updated = dict(raw)
    updated["listed"] = bool(listed)
    return upsert_product(email, updated)


def storefront_payload(email: str) -> list[dict]:
    """Public shape of the catalogue — never leaks cost price or SKU."""
    out = []
    for p in listed_products(email):
        out.append({
            "id": p["id"],
            "name": p["name"],
            "category": p.get("category") or "",
            "description": p.get("description") or "",
            "price": p.get("price"),
            "mrp": p.get("mrp"),
            "image_url": p.get("image_url") or "",
            "images": p.get("images") or [],
            "highlights": p.get("highlights") or [],
            "unit_label": p.get("unit_label") or "",
            "in_stock": in_stock(p),
            "available": available_units(p),
        })
    return out
