"""
Storefront runtime — shopper accounts, cart pricing, orders, and the loop back
into the seller's own analytics.

Design decisions this file encodes:

  * Customers are PER STORE. A shopper who signs up on one seller's site is
    that seller's customer and nobody else's — their rows land in the seller's
    RFM / Win-Back modules like any other customer.
  * A shopper must be logged in to place an order (the seller asked for this).
    Sessions are tokens persisted on the seller's account so a server restart
    does not sign every shopper out.
  * The cart is priced SERVER-SIDE at checkout. Whatever the browser sends is
    treated as a list of (product_id, qty) intents, nothing more.
  * Orders deduct stock from Product Management and, when the product is linked
    to inventory in Supply Management, consume those materials too — so EOQ and
    restock suggestions see real site demand.
  * Site orders are mirrored into the seller's Sales dataset as rows tagged
    channel="site", rebuilt idempotently on every change. The "My site" toggle
    in Listed Platforms is what includes or excludes them.
"""
from __future__ import annotations

import re
import secrets

import pandas as pd

from backend.core import auth, products, sitebuilder, smart, user_store

CUSTOMERS_KEY = "store_customers"
SESSIONS_KEY = "store_sessions"
ORDERS_KEY = "store_orders"
CHANNEL_KEY = "channel_toggles"

STATUSES = ["new", "confirmed", "packed", "shipped", "delivered", "cancelled"]
STATUS_LABELS = {
    "new": "New", "confirmed": "Confirmed", "packed": "Packed",
    "shipped": "Shipped", "delivered": "Delivered", "cancelled": "Cancelled",
}
# statuses whose revenue counts as real sales
SALES_STATUSES = {"new", "confirmed", "packed", "shipped", "delivered"}

_SESSION_LIMIT = 400          # trim the oldest tokens beyond this per store
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class StoreError(RuntimeError):
    """Message safe to show a shopper."""


def _now() -> str:
    # milliseconds, not seconds: two orders placed in the same second must still
    # sort in the order they were actually placed.
    return pd.Timestamp.now().isoformat(timespec="milliseconds")


def _norm_email(v) -> str:
    return str(v or "").strip().lower()


def _money(v) -> float:
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return 0.0


# =========================================================================
# customers
# =========================================================================
def _customers(seller: str) -> list[dict]:
    rows = user_store.get_key(seller, CUSTOMERS_KEY, []) or []
    return rows if isinstance(rows, list) else []


def _save_customers(seller: str, rows: list[dict]) -> None:
    user_store.set_key(seller, CUSTOMERS_KEY, rows)


def _public_customer(c: dict) -> dict:
    return {"id": c["id"], "name": c.get("name") or "", "email": c.get("email") or "",
            "phone": c.get("phone") or "", "address": c.get("address") or {},
            "created_at": c.get("created_at")}


def register(seller: str, email: str, password: str, name: str = "", phone: str = "") -> dict:
    seller, email = _norm_email(seller), _norm_email(email)
    if not _EMAIL_RE.match(email):
        raise StoreError("Enter a valid email address.")
    if len(password or "") < 6:
        raise StoreError("Use a password of at least 6 characters.")
    rows = _customers(seller)
    if any(_norm_email(c.get("email")) == email for c in rows):
        raise StoreError("An account with that email already exists here — log in instead.")
    cust = {
        "id": secrets.token_hex(8),
        "email": email,
        "password": auth.hash_password(password),
        "name": str(name or "").strip()[:80],
        "phone": re.sub(r"[^0-9+]", "", str(phone or ""))[:16],
        "address": {},
        "created_at": _now(),
    }
    rows.append(cust)
    _save_customers(seller, rows)
    return cust


def login(seller: str, email: str, password: str) -> dict:
    seller, email = _norm_email(seller), _norm_email(email)
    rows = _customers(seller)
    cust = next((c for c in rows if _norm_email(c.get("email")) == email), None)
    if not cust or not auth.verify_password(password or "", cust.get("password") or ""):
        raise StoreError("Wrong email or password.")
    return cust


def _sessions(seller: str) -> dict:
    s = user_store.get_key(seller, SESSIONS_KEY, {}) or {}
    return s if isinstance(s, dict) else {}


def issue_token(seller: str, customer_id: str) -> str:
    seller = _norm_email(seller)
    token = secrets.token_urlsafe(24)
    sess = _sessions(seller)
    sess[token] = {"customer_id": customer_id, "at": _now()}
    if len(sess) > _SESSION_LIMIT:
        ordered = sorted(sess.items(), key=lambda kv: kv[1].get("at") or "")
        sess = dict(ordered[-_SESSION_LIMIT:])
    user_store.set_key(seller, SESSIONS_KEY, sess)
    return token


def customer_from_token(seller: str, token: str) -> dict | None:
    seller = _norm_email(seller)
    if not token:
        return None
    entry = _sessions(seller).get(token.strip())
    if not entry:
        return None
    return next((c for c in _customers(seller) if c["id"] == entry.get("customer_id")), None)


def revoke_token(seller: str, token: str) -> None:
    seller = _norm_email(seller)
    sess = _sessions(seller)
    if sess.pop((token or "").strip(), None) is not None:
        user_store.set_key(seller, SESSIONS_KEY, sess)


def update_customer(seller: str, customer_id: str, patch: dict) -> dict:
    seller = _norm_email(seller)
    rows = _customers(seller)
    out = None
    for c in rows:
        if c["id"] == customer_id:
            if "name" in patch:
                c["name"] = str(patch["name"] or "").strip()[:80]
            if "phone" in patch:
                c["phone"] = re.sub(r"[^0-9+]", "", str(patch["phone"] or ""))[:16]
            if isinstance(patch.get("address"), dict):
                c["address"] = _clean_address(patch["address"])
            out = c
    if not out:
        raise StoreError("Account not found.")
    _save_customers(seller, rows)
    return out


def _clean_address(a: dict) -> dict:
    g = lambda k, n: str((a or {}).get(k) or "").strip()[:n]   # noqa: E731
    return {
        "line1": g("line1", 120), "line2": g("line2", 120), "city": g("city", 60),
        "state": g("state", 60), "pincode": re.sub(r"[^0-9]", "", str((a or {}).get("pincode") or ""))[:6],
        "landmark": g("landmark", 80),
    }


# =========================================================================
# cart pricing
# =========================================================================
def price_cart(seller: str, lines: list[dict]) -> dict:
    """Server-side truth for a cart. `lines` is [{product_id, qty}].

    Unknown, unlisted and out-of-stock products are reported back rather than
    silently dropped, so the storefront can tell the shopper what changed."""
    seller = _norm_email(seller)
    site = sitebuilder.get_site(seller)
    c = site["commerce"]
    catalogue = {p["id"]: p for p in products.listed_products(seller)}

    items, issues = [], []
    for raw in (lines or [])[:60]:
        pid = str((raw or {}).get("product_id") or "").strip()
        try:
            qty = int(float((raw or {}).get("qty") or 0))
        except (TypeError, ValueError):
            qty = 0
        if qty <= 0:
            continue
        p = catalogue.get(pid)
        if not p:
            issues.append({"product_id": pid, "reason": "unavailable"})
            continue
        avail = products.available_units(p)
        if avail is not None and avail <= 0:
            issues.append({"product_id": pid, "name": p["name"], "reason": "out_of_stock"})
            continue
        if avail is not None and qty > avail:
            issues.append({"product_id": pid, "name": p["name"], "reason": "reduced", "available": avail})
            qty = avail
        unit = _money(p.get("price") or 0)
        items.append({
            "product_id": pid, "name": p["name"], "category": p.get("category") or "",
            "image_url": p.get("image_url") or "", "unit_price": unit,
            "mrp": _money(p.get("mrp")) if p.get("mrp") else None,
            "qty": qty, "line_total": _money(unit * qty),
            "unit_label": p.get("unit_label") or "",
        })

    subtotal = _money(sum(i["line_total"] for i in items))
    ship = 0.0
    if items and c.get("shipping_fee"):
        free_above = _money(c.get("free_shipping_above"))
        if not free_above or subtotal < free_above:
            ship = _money(c["shipping_fee"])
    gst_pct = _money(c.get("gst_percent"))
    if gst_pct and not c.get("gst_inclusive", True):
        tax = _money(subtotal * gst_pct / 100.0)
    elif gst_pct:
        # prices already include GST — show the component, don't add it again
        tax = _money(subtotal - subtotal / (1 + gst_pct / 100.0))
    else:
        tax = 0.0
    added_tax = tax if (gst_pct and not c.get("gst_inclusive", True)) else 0.0
    total = _money(subtotal + ship + added_tax)

    return {
        "items": items, "issues": issues,
        "subtotal": subtotal, "shipping": ship,
        "gst_percent": gst_pct, "gst_inclusive": bool(c.get("gst_inclusive", True)),
        "tax": tax, "total": total,
        "currency": c.get("currency") or "INR",
        "min_order": _money(c.get("min_order")),
        "free_shipping_above": _money(c.get("free_shipping_above")),
        "cod_enabled": bool(c.get("cod_enabled", True)),
    }


# =========================================================================
# orders
# =========================================================================
def _orders(seller: str) -> list[dict]:
    rows = user_store.get_key(_norm_email(seller), ORDERS_KEY, []) or []
    return rows if isinstance(rows, list) else []


def _save_orders(seller: str, rows: list[dict]) -> None:
    user_store.set_key(_norm_email(seller), ORDERS_KEY, rows)


def _next_order_no(seller: str) -> str:
    n = len(_orders(seller)) + 1
    return f"ORD-{pd.Timestamp.now():%y%m}-{n:04d}"


def place_order(seller: str, customer: dict, lines: list[dict],
                address: dict, payment: str = "cod", note: str = "") -> dict:
    seller = _norm_email(seller)
    site = sitebuilder.get_site(seller)
    if not site.get("published"):
        raise StoreError("This store is not accepting orders right now.")

    priced = price_cart(seller, lines)
    if not priced["items"]:
        raise StoreError("Your cart is empty — nothing left in stock for these items.")
    if priced["min_order"] and priced["subtotal"] < priced["min_order"]:
        raise StoreError(f"Minimum order value is ₹{priced['min_order']:.0f}.")

    addr = _clean_address(address)
    if not addr["line1"] or not addr["city"] or not addr["pincode"]:
        raise StoreError("Address line, city and PIN code are required.")
    phone = re.sub(r"[^0-9+]", "", str((address or {}).get("phone") or customer.get("phone") or ""))
    if len(re.sub(r"\D", "", phone)) < 10:
        raise StoreError("Enter a valid 10-digit phone number.")

    pay = "cod" if payment not in ("cod", "prepaid") else payment
    if pay == "cod" and not priced["cod_enabled"]:
        raise StoreError("Cash on delivery is not available for this store.")

    order = {
        "id": secrets.token_hex(8),
        "order_no": _next_order_no(seller),
        "created_at": _now(),
        "updated_at": _now(),
        "status": "new",
        "payment": pay,
        "payment_status": "pending",
        "customer_id": customer.get("id") or "",
        "customer_name": str((address or {}).get("name") or customer.get("name") or "").strip()[:80],
        "customer_email": _norm_email(customer.get("email")),
        "phone": phone[:16],
        "address": addr,
        "note": str(note or "").strip()[:300],
        "items": priced["items"],
        "subtotal": priced["subtotal"],
        "shipping": priced["shipping"],
        "tax": priced["tax"],
        "gst_percent": priced["gst_percent"],
        "gst_inclusive": priced["gst_inclusive"],
        "total": priced["total"],
        "currency": priced["currency"],
        "history": [{"at": _now(), "status": "new", "by": "shopper"}],
    }

    rows = _orders(seller)
    rows.append(order)
    _save_orders(seller, rows)

    _consume_stock(seller, order["items"], sign=-1)
    # remember the shopper's address for next time
    try:
        update_customer(seller, customer["id"], {"address": addr, "phone": phone,
                                                 "name": order["customer_name"]})
    except StoreError:
        pass
    sync_sales(seller)
    return order


def _consume_stock(seller: str, items: list[dict], sign: int = -1) -> None:
    """Move product stock and, where a product is linked to inventory in Supply
    Management, the materials behind it. Never raises — a stock-keeping problem
    must not lose an order that a shopper already placed."""
    from backend.core import supply
    for it in items:
        try:
            products.adjust_stock(seller, it["product_id"], sign * int(it["qty"]))
        except Exception:  # noqa: BLE001
            pass
    try:
        maps = supply.get_maps(seller)
    except Exception:  # noqa: BLE001
        return
    if not maps:
        return
    by_product: dict[str, list[dict]] = {}
    for m in maps:
        by_product.setdefault(str(m.get("product") or "").strip().lower(), []).append(m)
    for it in items:
        for m in by_product.get(str(it["name"]).strip().lower(), []):
            try:
                qty = float(m.get("qty_per_unit") or 0) * int(it["qty"])
                if qty <= 0:
                    continue
                item = next((i for i in supply.get_inventory(seller)
                             if i.get("id") == m.get("inventory_id")), None)
                if not item:
                    continue
                updated = dict(item)
                cur = float(updated.get("current_stock") or 0)
                updated["current_stock"] = max(0.0, cur + sign * qty)
                supply.upsert_item(seller, updated)
            except Exception:  # noqa: BLE001
                continue


def set_status(seller: str, order_id: str, status: str, by: str = "seller") -> dict:
    seller = _norm_email(seller)
    if status not in STATUSES:
        raise StoreError("Unknown status.")
    rows = _orders(seller)
    order = next((o for o in rows if o["id"] == order_id), None)
    if not order:
        raise StoreError("Order not found.")
    was = order["status"]
    if was == status:
        return order
    order["status"] = status
    order["updated_at"] = _now()
    order.setdefault("history", []).append({"at": _now(), "status": status, "by": by})
    if status == "delivered" and order.get("payment") == "cod":
        order["payment_status"] = "paid"
    _save_orders(seller, rows)

    # cancelling puts the stock back; un-cancelling takes it out again
    if status == "cancelled" and was != "cancelled":
        _consume_stock(seller, order["items"], sign=+1)
    elif was == "cancelled" and status != "cancelled":
        _consume_stock(seller, order["items"], sign=-1)
    sync_sales(seller)
    return order


def get_orders(seller: str, status: str = "", customer_id: str = "") -> list[dict]:
    rows = _orders(seller)
    if status and status != "all":
        rows = [o for o in rows if o.get("status") == status]
    if customer_id:
        rows = [o for o in rows if o.get("customer_id") == customer_id]
    return sorted(rows, key=lambda o: o.get("created_at") or "", reverse=True)


def get_order(seller: str, order_id: str) -> dict | None:
    return next((o for o in _orders(seller) if o["id"] == order_id), None)


def order_stats(seller: str) -> dict:
    rows = _orders(seller)
    live = [o for o in rows if o.get("status") in SALES_STATUSES]
    revenue = _money(sum(_money(o.get("total")) for o in live))
    by_status = {s: 0 for s in STATUSES}
    for o in rows:
        by_status[o.get("status", "new")] = by_status.get(o.get("status", "new"), 0) + 1
    units = sum(int(i.get("qty") or 0) for o in live for i in o.get("items") or [])
    return {
        "orders": len(rows), "live_orders": len(live), "revenue": revenue,
        "units": units, "by_status": by_status,
        "customers": len(_customers(seller)),
        "aov": _money(revenue / len(live)) if live else 0.0,
    }


def orders_csv(seller: str) -> str:
    rows = []
    for o in get_orders(seller):
        for it in o.get("items") or []:
            rows.append({
                "order_no": o["order_no"], "date": o["created_at"], "status": o["status"],
                "customer": o.get("customer_name"), "email": o.get("customer_email"),
                "phone": o.get("phone"), "city": (o.get("address") or {}).get("city"),
                "pincode": (o.get("address") or {}).get("pincode"),
                "product": it.get("name"), "qty": it.get("qty"),
                "unit_price": it.get("unit_price"), "line_total": it.get("line_total"),
                "order_total": o.get("total"), "payment": o.get("payment"),
            })
    return pd.DataFrame(rows).to_csv(index=False)


# =========================================================================
# channel toggles (Listed Platforms strip) + sales mirror
# =========================================================================
def channel_enabled(seller: str, channel: str = "site") -> bool:
    t = user_store.get_key(_norm_email(seller), CHANNEL_KEY, {}) or {}
    return bool(t.get(channel, True))


def set_channel(seller: str, channel: str, enabled: bool) -> dict:
    seller = _norm_email(seller)
    t = user_store.get_key(seller, CHANNEL_KEY, {}) or {}
    t[channel] = bool(enabled)
    user_store.set_key(seller, CHANNEL_KEY, t)
    if channel == "site":
        sync_sales(seller)
    return t


def site_sales_frame(seller: str) -> pd.DataFrame:
    """Site orders as canonical transaction rows, one row per order line."""
    rows = []
    for o in _orders(seller):
        if o.get("status") not in SALES_STATUSES:
            continue
        for it in o.get("items") or []:
            rows.append({
                "date": o.get("created_at"),
                "order_id": o.get("order_no"),
                "customer_id": o.get("customer_email") or o.get("phone") or o.get("customer_id"),
                "customer_name": o.get("customer_name") or "",
                "product": it.get("name") or "",
                "category": it.get("category") or "",
                "subcategory": "",
                "quantity": int(it.get("qty") or 0),
                "amount": _money(it.get("line_total")),
                "channel": "site",
            })
    df = pd.DataFrame(rows, columns=["date", "order_id", "customer_id", "customer_name",
                                     "product", "category", "subcategory", "quantity",
                                     "amount", "channel"])
    if len(df):
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
    return df


def sync_sales(seller: str) -> int:
    """Rebuild the site's contribution to the seller's Sales dataset.

    Idempotent by construction: every existing channel="site" row is dropped
    first, then the current order book is written back. Uploaded and connector
    rows (channel missing or something else) are never touched. Returns the
    number of site rows now in the dataset."""
    seller = _norm_email(seller)
    try:
        existing = smart.load_sales(seller)
    except Exception:  # noqa: BLE001
        existing = None

    base = None
    if existing is not None and len(existing):
        base = existing.copy()
        if "channel" in base.columns:
            base = base[base["channel"].fillna("upload") != "site"]
        else:
            base["channel"] = "upload"

    site_df = site_sales_frame(seller) if channel_enabled(seller, "site") else pd.DataFrame()

    if base is None or not len(base):
        merged = site_df
    elif len(site_df):
        merged = pd.concat([base, site_df], ignore_index=True)
    else:
        merged = base

    if merged is None or not len(merged):
        # nothing left at all — clear rather than save an empty frame
        if existing is not None:
            smart.clear(seller, "sales")
        return 0

    meta = {"source": "site+uploads", "filename": "site orders + uploads"}
    smart.save_sales(seller, merged.reset_index(drop=True), meta, mode="replace")
    return int(len(site_df))
