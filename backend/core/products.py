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
                     "track_stock", "listed", "highlights", "unit_label", "video_url",
                     "options", "variants")

# A product may carry up to two option axes (in practice Size and Colour). The
# cross product of their values is the variant matrix, and each cell is a real
# record with its own SKU, its own stock and — optionally — its own price. A
# clothing seller cannot operate without this: one shirt is twelve things to
# count, not one.
MAX_OPTION_AXES = 2
MAX_OPTION_VALUES = 24
MAX_VARIANTS = 120


def _norm_options(raw) -> list[dict]:
    """[{name, values[]}] — at most two axes, de-duplicated, order preserved."""
    if isinstance(raw, str):
        try:
            import json as _json
            raw = _json.loads(raw)
        except Exception:
            return []
    if not isinstance(raw, (list, tuple)):
        return []
    out, seen_axis = [], set()
    for ax in raw[:MAX_OPTION_AXES]:
        if not isinstance(ax, dict):
            continue
        name = str(ax.get("name") or "").strip()[:40]
        if not name or _norm(name) in seen_axis:
            continue
        values, seen = [], set()
        for v in (ax.get("values") or [])[:MAX_OPTION_VALUES]:
            sv = str(v or "").strip()[:60]
            if sv and _norm(sv) not in seen:
                seen.add(_norm(sv))
                values.append(sv)
        if not values:
            continue
        seen_axis.add(_norm(name))
        out.append({"name": name, "values": values})
    return out


def variant_key(options: dict, axes: list[dict]) -> str:
    """A stable identity for one cell of the matrix, independent of ordering."""
    parts = []
    for ax in axes:
        parts.append(f"{_norm(ax['name'])}={_norm((options or {}).get(ax['name']))}")
    return "|".join(parts)


def variant_label(options: dict, axes: list[dict]) -> str:
    """'M / Black' — what a shopper and a packing slip both need to read."""
    vals = [str((options or {}).get(ax["name"]) or "").strip() for ax in axes]
    return " / ".join([v for v in vals if v])


def _norm_variants(raw, axes: list[dict]) -> list[dict]:
    if isinstance(raw, str):
        try:
            import json as _json
            raw = _json.loads(raw)
        except Exception:
            raw = []
    rows = raw if isinstance(raw, (list, tuple)) else []
    out, seen = [], set()
    for r in rows[:MAX_VARIANTS]:
        if not isinstance(r, dict):
            continue
        opts = r.get("options") or {}
        if not isinstance(opts, dict):
            continue
        # a variant naming an axis or value the product no longer has is stale
        clean_opts, ok = {}, True
        for ax in axes:
            val = str(opts.get(ax["name"]) or "").strip()
            match = next((v for v in ax["values"] if _norm(v) == _norm(val)), None)
            if not match:
                ok = False
                break
            clean_opts[ax["name"]] = match
        if not ok or not clean_opts:
            continue
        key = variant_key(clean_opts, axes)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "id": r.get("id") or secrets.token_hex(6),
            "key": key,
            "options": clean_opts,
            "label": variant_label(clean_opts, axes),
            "sku": str(r.get("sku") or "").strip()[:80],
            "price": _opt_num(r.get("price")),          # None = use product price
            "mrp": _opt_num(r.get("mrp")),
            "stock": _int(r.get("stock"), 0),
            "image_url": str(r.get("image_url") or "").strip()[:500],
        })
    return out


def build_matrix(axes: list[dict], existing: list[dict] | None = None) -> list[dict]:
    """Expand the axes into every combination, carrying over the SKU, stock and
    price of any cell that already existed. Editing 'Sizes: S,M,L' to add XL
    must not reset the twelve cells the seller already filled in."""
    import itertools

    axes = _norm_options(axes)
    if not axes:
        return []
    by_key = {v.get("key"): v for v in (existing or []) if v.get("key")}
    rows = []
    for combo in itertools.product(*[ax["values"] for ax in axes]):
        opts = {ax["name"]: val for ax, val in zip(axes, combo)}
        key = variant_key(opts, axes)
        prev = by_key.get(key) or {}
        rows.append({
            "id": prev.get("id") or secrets.token_hex(6),
            "key": key,
            "options": opts,
            "label": variant_label(opts, axes),
            "sku": prev.get("sku") or "",
            "price": prev.get("price"),
            "mrp": prev.get("mrp"),
            "stock": _int(prev.get("stock"), 0),
            "image_url": prev.get("image_url") or "",
        })
        if len(rows) >= MAX_VARIANTS:
            break
    return rows


def _norm_product(raw: dict) -> dict:
    _axes = _norm_options(raw.get("options"))
    _vars = _norm_variants(raw.get("variants"), _axes) if _axes else []
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
        # a short muted clip that plays when a shopper hovers the card
        "video_url": (raw.get("video_url") or "").strip()[:500],
        # ---- variants ----
        "options": _axes,
        "variants": _vars,
        "has_variants": bool(_vars),
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
                # The sidecar is authoritative for the fields it holds — it is
                # where they were written. Only a key the table also has may be
                # skipped when the sidecar copy is empty, so a stale blank can
                # never wipe a real column.
                if extra:
                    keep = {k: v for k, v in extra.items()
                            if k not in r or v not in (None, "")}
                    merged.append({**r, **keep})
                else:
                    merged.append(r)
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


# The columns the `products` table actually has, discovered once per process.
# The old code guessed — full write, and on any error a single retry with the
# storefront fields stripped — which meant the day a NEW field was added that
# the strip list didn't know about (has_variants), the retry failed too and
# every product save returned a 500. Asking the table what it holds is both
# cheaper (no failed round-trip per save) and impossible to break that way.
_COLUMNS: set[str] | None = None
_ALWAYS_SIDECAR = ("has_variants",)   # derived on read; never a column


def _known_columns(email: str) -> set[str] | None:
    """Column names on the products table, or None if we cannot tell (in which
    case we write everything and let the caller's fallback handle it)."""
    global _COLUMNS
    if _COLUMNS is not None:
        return _COLUMNS or None
    try:
        rows = db.fetch_all(T_PROD, {"email": email}) or db.fetch_all(T_PROD) or []
        if rows:
            _COLUMNS = set(rows[0].keys())
            return _COLUMNS
    except Exception:  # noqa: BLE001
        pass
    return None


def _split_row(row: dict) -> tuple[dict, dict]:
    """(columns the table can take, everything else for the JSON sidecar)."""
    cols = _known_columns(row.get("email", ""))
    if cols:
        writable = {k: v for k, v in row.items() if k in cols}
        extra = {k: v for k, v in row.items()
                 if k not in cols and k not in ("id", "email")}
    else:
        # nothing to learn from (empty table): assume the base schema only
        writable = {k: v for k, v in row.items()
                    if k not in STOREFRONT_FIELDS and k not in _ALWAYS_SIDECAR}
        extra = {k: row.get(k) for k in STOREFRONT_FIELDS}
    return writable, extra


def _write_sidecar(email: str, product_id: str, extra: dict) -> None:
    side = user_store.get_key(email, SIDECAR_KEY, {}) or {}
    side[product_id] = extra
    user_store.set_key(email, SIDECAR_KEY, side)


def _upsert_row(row: dict) -> None:
    """Write a product row to Supabase.

    Fields the table has no column for (because supabase/site.sql or
    supabase/variants.sql has not been run) are kept in the per-account JSON
    state instead and merged back on read — so a pending migration degrades to
    "stored somewhere else", never to a failed save.
    """
    global _COLUMNS
    row = {k: v for k, v in row.items() if k not in _ALWAYS_SIDECAR}
    email, pid = row.get("email", ""), row.get("id", "")

    writable, extra = _split_row(row)
    try:
        db.upsert(T_PROD, writable, on_conflict="id")
    except Exception as e:  # noqa: BLE001 — a stale column guess; re-learn and retry
        import logging
        logging.getLogger("products").warning(
            "product upsert failed (%s); retrying with the base columns only. "
            "Run supabase/site.sql and supabase/variants.sql to store these in "
            "the database instead of the JSON sidecar.", e)
        _COLUMNS = None
        base = {k: v for k, v in row.items()
                if k not in STOREFRONT_FIELDS and k not in _ALWAYS_SIDECAR}
        db.upsert(T_PROD, base, on_conflict="id")
        extra = {k: row.get(k) for k in STOREFRONT_FIELDS}

    # Only write a sidecar when there is something the table could not hold —
    # an empty one would shadow real columns on read.
    if extra:
        _write_sidecar(email, pid, extra)
    else:
        side = user_store.get_key(email, SIDECAR_KEY, {}) or {}
        if side.pop(pid, None) is not None:
            user_store.set_key(email, SIDECAR_KEY, side)


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
    # With axes defined, the matrix is the truth and product-level stock becomes
    # its roll-up — so every caller that only knows about `stock` (Supply, the
    # old storefront payload, the tiles) keeps reading a correct total.
    if clean["options"]:
        clean["variants"] = build_matrix(clean["options"], clean["variants"])
        clean["has_variants"] = bool(clean["variants"])
        if clean["variants"]:
            clean["stock"] = sum(max(0, _int(v.get("stock"), 0)) for v in clean["variants"])
    else:
        clean["variants"] = []
        clean["has_variants"] = False
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


def get_variant(p: dict, variant_id: str | None) -> dict | None:
    """One cell of the matrix, by id or by key. None when unknown."""
    if not variant_id:
        return None
    vid = str(variant_id).strip()
    for v in (p.get("variants") or []):
        if v.get("id") == vid or v.get("key") == vid:
            return v
    return None


def variant_price(p: dict, v: dict | None) -> float:
    """A variant's price, falling back to the product's when not overridden."""
    if v and v.get("price") not in (None, ""):
        return float(v["price"])
    return float(p.get("price") or 0)


def variant_mrp(p: dict, v: dict | None):
    if v and v.get("mrp") not in (None, ""):
        return float(v["mrp"])
    return p.get("mrp")


def in_stock(p: dict, variant_id: str | None = None) -> bool:
    if not p.get("track_stock", True):
        return True
    if p.get("variants"):
        if variant_id:
            v = get_variant(p, variant_id)
            return bool(v) and _int(v.get("stock"), 0) > 0
        return any(_int(v.get("stock"), 0) > 0 for v in p["variants"])
    return _int(p.get("stock"), 0) > 0


def available_units(p: dict, variant_id: str | None = None) -> int | None:
    """Units a shopper may buy, or None when this product is not stock-tracked."""
    if not p.get("track_stock", True):
        return None
    if p.get("variants"):
        if variant_id:
            v = get_variant(p, variant_id)
            return max(0, _int((v or {}).get("stock"), 0))
        return max(0, sum(_int(v.get("stock"), 0) for v in p["variants"]))
    return max(0, _int(p.get("stock"), 0))


def adjust_stock(email: str, product_id: str, delta: int,
                 variant_id: str | None = None) -> dict | None:
    """Move stock by `delta` (negative = sold). With a variant id the cell moves
    and the product total is recomputed from the matrix; without one, and with
    no matrix, the product's own count moves. No-ops when stock is not tracked."""
    email = _email(email)
    raw = next((p for p in _products_raw(email) if p["id"] == product_id), None)
    if not raw or not raw.get("track_stock", True):
        return raw
    updated = dict(raw)
    variants = [dict(v) for v in (raw.get("variants") or [])]
    if variants and variant_id:
        hit = next((v for v in variants
                    if v.get("id") == variant_id or v.get("key") == variant_id), None)
        if hit is None:
            return raw
        hit["stock"] = max(0, _int(hit.get("stock"), 0) + int(delta))
        updated["variants"] = variants
        updated["stock"] = sum(max(0, _int(v.get("stock"), 0)) for v in variants)
    elif variants:
        # no variant named on a variant product — nothing safe to decrement
        return raw
    else:
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
            "video_url": p.get("video_url") or "",
            "in_stock": in_stock(p),
            "available": available_units(p),
            "options": p.get("options") or [],
            "variants": [
                {
                    "id": v["id"],
                    "label": v.get("label") or "",
                    "options": v.get("options") or {},
                    "price": variant_price(p, v),
                    "mrp": variant_mrp(p, v),
                    "image_url": v.get("image_url") or "",
                    "in_stock": (not p.get("track_stock", True)) or _int(v.get("stock"), 0) > 0,
                    "available": (None if not p.get("track_stock", True)
                                  else max(0, _int(v.get("stock"), 0))),
                }
                for v in (p.get("variants") or [])
            ],
        })
    return out
