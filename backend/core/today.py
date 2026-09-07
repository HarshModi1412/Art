"""
Today — the three things worth the seller's time, right now.

The app is twelve modules. None of them answers the only question a seller
actually opens it with: what should I do this morning? This builds that answer
once, and two surfaces render it — the strip above the home tiles, and the
email/WhatsApp digest. One source means the digest can never disagree with the
home screen, which is the usual way these two drift apart.

An item is only worth showing if it names a thing to DO. "Revenue is up 4%" is
not an item; "4 items are below their reorder point" is. Every item therefore
carries a module + route so the row is clickable straight into the action.

Nothing here is allowed to raise: each source is wrapped, because a broken
review file must not take down the home screen.
"""
from __future__ import annotations

import logging

import pandas as pd

log = logging.getLogger("today")

# severity -> sort weight. Money already lost outranks money at risk, which
# outranks setup chores.
_WEIGHT = {"urgent": 0, "attention": 1, "opportunity": 2, "setup": 3}


def _item(kind, title, detail, module, severity="attention", route="", value=None) -> dict:
    return {"id": kind, "title": title, "detail": detail, "module": module,
            "severity": severity, "route": route or module, "value": value,
            "weight": _WEIGHT.get(severity, 2)}


def _safe(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except Exception as e:  # noqa: BLE001
        log.debug("today source %s failed: %s", getattr(fn, "__name__", fn), e)
        return None


# ---------------------------------------------------------------------------
# sources
# ---------------------------------------------------------------------------
def _orders_items(email: str) -> list[dict]:
    from backend.core import storefront
    out = []
    new = storefront.get_orders(email, status="new")
    if new:
        value = sum(float(o.get("total") or 0) for o in new)
        out.append(_item(
            "orders_new",
            f"{len(new)} new order{'s' if len(new) != 1 else ''} to confirm",
            f"₹{value:,.0f} waiting since {str(new[-1].get('created_at') or '')[:10]}. "
            f"Confirm them so the customer hears from you today.",
            "orders", "urgent", value=value))
    packed = storefront.get_orders(email, status="packed")
    if packed:
        out.append(_item(
            "orders_packed", f"{len(packed)} packed order{'s' if len(packed) != 1 else ''} not shipped",
            "Packed but still sitting here. Mark them shipped or hand them over.",
            "orders", "attention"))
    return out


def _supply_items(email: str) -> list[dict]:
    from backend.core import supply
    state = supply.compute_inventory(email) or {}
    items = state.get("items") or []
    low = [i for i in items if i.get("needs_reorder")]
    if not low:
        return []
    worst = sorted(low, key=lambda i: float(i.get("days_cover") or 999))[:1]
    tail = ""
    if worst:
        w = worst[0]
        days = w.get("days_cover")
        tail = (f" {w.get('name','One item')} runs out in about "
                f"{int(float(days))} day{'s' if int(float(days)) != 1 else ''}."
                if days not in (None, "") else f" {w.get('name','One item')} is the tightest.")
    return [_item(
        "supply_low", f"{len(low)} item{'s' if len(low) != 1 else ''} below reorder point",
        f"Raise a purchase order before you are selling from an empty shelf.{tail}",
        "supply", "urgent")]


def _winback_items(email: str) -> list[dict]:
    from backend.core import analytics, smart
    txns = smart.load_sales(email)
    if txns is None or not len(txns):
        return []
    # /api/smart/state runs this same pass; the shared pool means the home
    # screen pays for it once, not twice.
    at_risk = analytics.at_risk_cached(email, txns, limit=0)
    if len(at_risk) < 3:
        return []
    value = sum(float(c.get("monetary") or 0) for c in at_risk)
    return [_item(
        "winback", f"{len(at_risk)} customers are slipping away",
        f"They spent ₹{value:,.0f} with you and have gone quiet. "
        f"One campaign is the cheapest revenue you will find this week.",
        "sales", "opportunity", route="rfm", value=value)]


def _complaint_items(email: str) -> list[dict]:
    from backend.core import smart
    reviews = smart.load_review(email)
    if reviews is None or not len(reviews):
        return []
    from backend.core import complaints
    res = _safe(complaints.analyze_complaints, reviews) or {}
    # `deep` is the per-theme table; `actions` is the fix-first plan. Either
    # can name the theme, so prefer whichever the run produced.
    themes = (res.get("deep") or res.get("actions") or [])[:1]
    if not themes:
        return []
    t = themes[0] if isinstance(themes[0], dict) else {}
    name = t.get("theme") or t.get("title") or t.get("name") or "a complaint theme"
    n = t.get("count") or t.get("mentions")
    return [_item(
        "complaints", f"“{name}” is your loudest complaint",
        (f"{n} mentions across your reviews. " if n else "") +
        "Fix-first plan is one click away.",
        "complaints", "attention")]


def _site_items(email: str) -> list[dict]:
    from backend.core import products, sitebuilder
    out = []
    site = sitebuilder.get_site(email) or {}
    listed = products.listed_products(email)
    if not site.get("published"):
        if listed:
            out.append(_item(
                "site_draft", "Your website is still a draft",
                f"{len(listed)} products are ready to sell on it. Publishing takes one click.",
                "site", "opportunity"))
    else:
        oos = [p for p in listed if not products.in_stock(p)]
        if oos:
            out.append(_item(
                "site_oos", f"{len(oos)} listed product{'s' if len(oos) != 1 else ''} out of stock",
                "Shoppers can see them but cannot buy them. Restock or unlist.",
                "products", "attention"))
    return out


def _catalogue_items(email: str) -> list[dict]:
    from backend.core import products
    unmatched = products.unmatched_sales_names(email) or []
    if len(unmatched) < 3:
        return []
    return [_item(
        "products_unlinked", f"{len(unmatched)} platform names are not linked to a product",
        "Their sales are not rolling up, so your best-seller list is wrong. "
        "Linking them takes a minute.",
        "products", "setup")]


_SOURCES = (_orders_items, _supply_items, _winback_items,
            _complaint_items, _site_items, _catalogue_items)


# ---------------------------------------------------------------------------
# public
# ---------------------------------------------------------------------------
def build(email: str, limit: int = 3) -> list[dict]:
    """The ranked list. `limit=0` returns everything found.

    Cached against the account's data stamp: the strip and the digest ask for
    the same rows, and nothing here changes until the seller's data does.
    """
    from backend.core import cache

    def _compute() -> list[dict]:
        found: list[dict] = []
        for src in _SOURCES:
            got = _safe(src, email)
            if got:
                found.extend(got)
        found.sort(key=lambda i: (i["weight"], -(float(i.get("value") or 0))))
        return found

    found = cache.memo("today", email, _compute, ttl=120) or []
    return found if not limit else found[:limit]


def empty_state(email: str) -> dict:
    """What to say when there is genuinely nothing to do — which is a result,
    not a blank space, and should read like one."""
    from backend.core import smart
    status = _safe(smart.data_status, email) or {}
    if not (status.get("sales") or {}).get("ready"):
        return {"title": "Nothing to act on yet",
                "detail": "Upload a sales file, or load the sample data, and this fills up.",
                "module": "sales", "cta": "Load sample data"}
    return {"title": "Nothing needs you this morning",
            "detail": "No new orders, nothing below its reorder point, no theme worth chasing.",
            "module": "", "cta": ""}


def digest_recipients_key() -> str:
    return "digest_prefs"


def get_prefs(email: str) -> dict:
    from backend.core import user_store
    p = user_store.get_key(email, digest_recipients_key(), {}) or {}
    return {
        "enabled": bool(p.get("enabled", False)),
        "email": (p.get("email") or email or "").strip(),
        "phone": (p.get("phone") or "").strip(),
        "hour": int(p.get("hour") or 8),          # local hour, 24h
        "last_sent": p.get("last_sent") or "",
    }


def set_prefs(email: str, patch: dict) -> dict:
    from backend.core import user_store
    cur = get_prefs(email)
    cur.update({k: v for k, v in (patch or {}).items()
                if k in ("enabled", "email", "phone", "hour")})
    cur["enabled"] = bool(cur["enabled"])
    try:
        cur["hour"] = max(0, min(23, int(cur["hour"])))
    except (TypeError, ValueError):
        cur["hour"] = 8
    user_store.set_key(email, digest_recipients_key(), cur)
    return cur


def send_digest(email: str, force: bool = False) -> dict:
    """Build and send one seller's digest. Called by the scheduler, and by the
    'Send me one now' button so a seller can see it before trusting it."""
    from backend.core import messaging, user_store

    prefs = get_prefs(email)
    if not force and not prefs["enabled"]:
        return {"sent": False, "reason": "digest is off"}

    today = str(pd.Timestamp.now().date())
    if not force and prefs.get("last_sent") == today:
        return {"sent": False, "reason": "already sent today"}

    items = build(email, limit=6)
    if not items:
        return {"sent": False, "reason": "nothing worth sending"}

    res = messaging.send_digest(
        to_email=prefs["email"] or email,
        items=items,
        seller_name="",
        phone=prefs["phone"],
    )
    prefs["last_sent"] = today
    user_store.set_key(email, digest_recipients_key(), prefs)
    return {"sent": bool(res.get("delivered")), "channels": res,
            "items": items, "reason": "" if res.get("delivered") else
            "no channel accepted it — check SMTP settings"}


def run_due(hour: int | None = None) -> dict:
    """Send every seller whose digest hour is now. Safe to call every hour."""
    from backend.core import auth

    hour = pd.Timestamp.now().hour if hour is None else int(hour)
    sent, skipped = 0, 0
    for account in (auth.load_users() or {}):
        prefs = get_prefs(account)
        if not prefs["enabled"] or prefs["hour"] != hour:
            skipped += 1
            continue
        if (_safe(send_digest, account) or {}).get("sent"):
            sent += 1
        else:
            skipped += 1
    return {"hour": hour, "sent": sent, "skipped": skipped}
