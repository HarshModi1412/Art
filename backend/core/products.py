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
def _norm_product(raw: dict) -> dict:
    return {
        "id": raw.get("id") or secrets.token_hex(8),
        "name": (raw.get("name") or "").strip(),
        "category": (raw.get("category") or "").strip(),
        "sku": (raw.get("sku") or "").strip(),
        "price": _opt_num(raw.get("price")),
        "unit_cost": _opt_num(raw.get("unit_cost")),
        "status": (raw.get("status") or "active").strip() or "active",
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

    if _tables():
        row = dict(clean)
        row["email"] = email
        row["updated_at"] = _now_iso()
        db.upsert(T_PROD, row, on_conflict="id")
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
