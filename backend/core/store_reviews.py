"""
Product reviews on the seller's own website, and where they go next.

WHO CAN REVIEW
--------------
Only someone who actually bought the product from this shop: their account
(or the guest session every order creates) must have an order containing it
that was not cancelled. That is the line between reviews a seller can show and
the fake-review problem every open review box ends up with. Reviews are marked
"Verified buyer" for exactly that reason. One review per customer per product;
writing again updates it.

WHERE THEY GO
-------------
Every visible review is also a row of the account's Review data, as source
"site" (smart.save_review), so Review Analytics, Complaint Analysis and the
positioning work see the website's reviews next to uploaded ones and the ones
pulled from WooCommerce or Wix. Hiding a review takes it out of both.
"""
from __future__ import annotations

import secrets
import threading
from datetime import datetime

from backend.core import user_store

KEY = "store_reviews"
MAX = 5000
_lock = threading.Lock()


class ReviewError(ValueError):
    """A reason a shopper or seller can read."""


def _norm(seller: str) -> str:
    return (seller or "").strip().lower()


def _all(seller: str) -> list[dict]:
    rows = user_store.get_key(_norm(seller), KEY, []) or []
    return rows if isinstance(rows, list) else []


def _save(seller: str, rows: list[dict]) -> None:
    user_store.set_key(_norm(seller), KEY, rows[-MAX:])


def bought(seller: str, customer: dict, product_id: str) -> str:
    """The order number in which this customer bought this product, or ""."""
    from backend.core import storefront
    cid = str((customer or {}).get("id") or "")
    if not cid:
        return ""
    for o in storefront.get_orders(seller, customer_id=cid):
        if o.get("status") == "cancelled":
            continue
        if any(str(i.get("product_id")) == str(product_id) for i in o.get("items") or []):
            return o.get("order_no") or "order"
    return ""


def _shown_name(name: str) -> str:
    """"Asha Kapoor" -> "Asha K." : enough to be real, not a full name."""
    parts = str(name or "").split()
    if not parts:
        return "A customer"
    return parts[0] + (f" {parts[-1][0]}." if len(parts) > 1 else "")


def add(seller: str, customer: dict, product_id: str, rating, text: str) -> dict:
    from backend.core import products
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        rating = 0
    if not 1 <= rating <= 5:
        raise ReviewError("Pick 1 to 5 stars.")
    text = " ".join(str(text or "").split())
    if len(text) < 3:
        raise ReviewError("Write a few words about it.")
    if len(text) > 1000:
        raise ReviewError("Keep it under 1000 characters.")
    order_no = bought(seller, customer, product_id)
    if not order_no:
        raise ReviewError("Only customers who bought this can review it.")
    p = products.get_product(seller, product_id) or {}
    with _lock:
        rows = list(_all(seller))
        now = datetime.now().isoformat(timespec="seconds")
        cid = str(customer.get("id"))
        mine = next((r for r in rows if r.get("customer_id") == cid
                     and r.get("product_id") == str(product_id)), None)
        if mine:
            mine.update({"rating": rating, "text": text, "updated_at": now})
            rec = mine
        else:
            rec = {"id": secrets.token_hex(6), "product_id": str(product_id),
                   "product_name": p.get("name") or "", "customer_id": cid,
                   "name": _shown_name(customer.get("name") or ""), "rating": rating,
                   "text": text, "order_no": order_no, "created_at": now,
                   "updated_at": now, "hidden": False}
            rows.append(rec)
        _save(seller, rows)
    sync(seller)
    return public(rec)


def public(r: dict) -> dict:
    return {"id": r["id"], "name": r.get("name") or "A customer", "rating": r.get("rating"),
            "text": r.get("text") or "", "date": str(r.get("created_at") or "")[:10],
            "verified": True}


def for_product(seller: str, product_id: str, customer: dict | None = None) -> dict:
    rows = [r for r in _all(seller) if r.get("product_id") == str(product_id) and not r.get("hidden")]
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    avg = round(sum(r["rating"] for r in rows) / len(rows), 1) if rows else None
    mine = None
    if customer:
        mine = next((public(r) for r in _all(seller) if r.get("customer_id") == str(customer.get("id"))
                     and r.get("product_id") == str(product_id)), None)
    return {"count": len(rows), "average": avg, "reviews": [public(r) for r in rows[:50]],
            "can_review": bool(customer and bought(seller, customer, product_id)),
            "mine": mine}


def summary(seller: str) -> dict:
    """{product_id: {"average", "count"}} for product cards."""
    out: dict = {}
    for r in _all(seller):
        if r.get("hidden"):
            continue
        s = out.setdefault(r["product_id"], {"total": 0, "count": 0})
        s["total"] += r["rating"]
        s["count"] += 1
    return {k: {"average": round(v["total"] / v["count"], 1), "count": v["count"]} for k, v in out.items()}


def list_all(seller: str) -> list[dict]:
    rows = sorted(_all(seller), key=lambda r: r.get("created_at") or "", reverse=True)
    return [{**public(r), "product_name": r.get("product_name") or "", "hidden": bool(r.get("hidden")),
             "order_no": r.get("order_no") or ""} for r in rows]


def set_hidden(seller: str, review_id: str, hidden: bool) -> dict:
    with _lock:
        rows = list(_all(seller))
        r = next((x for x in rows if x.get("id") == review_id), None)
        if not r:
            raise ReviewError("That review no longer exists.")
        r["hidden"] = bool(hidden)
        _save(seller, rows)
    sync(seller)
    return {"id": review_id, "hidden": bool(hidden)}


def sync(seller: str) -> int:
    """Write the visible website reviews into the Review data as source
    "site" (replacing the previous site rows, never touching the others)."""
    import pandas as pd
    from backend.core import smart
    rows = [r for r in _all(seller) if not r.get("hidden")]
    df = pd.DataFrame([{"Review": r["text"], "Rating": r["rating"], "Date": r.get("created_at"),
                        "Product": r.get("product_name") or "", "Reviewer": r.get("name") or ""}
                       for r in rows], columns=["Review", "Rating", "Date", "Product", "Reviewer"])
    smart.save_review(_norm(seller), df, {"files": "Website reviews"}, mode="replace", source="site")
    return len(df)
