"""
E-commerce order connectors — pull a seller's orders straight into the sales
dataset that powers all the analytics.

Two live integrations, chosen for the least setup effort for the seller:

  Shopify  — the owner creates a *custom app* in their Shopify admin
             (Settings -> Apps and sales channels -> Develop apps), grants it
             read_orders / read_products, and copies the Admin API access
             token. We call the REST Admin API with the X-Shopify-Access-Token
             header. No app review, no OAuth redirect, works in minutes.

  Amazon   — Selling Partner API. The seller registers a (self-authorised)
             SP-API app in Seller Central, which yields an LWA refresh token +
             client id/secret. We exchange the refresh token for a short-lived
             access token and call the Orders API with the x-amz-access-token
             header. AWS SigV4 request signing is no longer required.

Everything normalises to the canonical transaction schema so analytics,
RFM, menu engineering, etc. work unchanged:

    date, order_id, customer_id, customer_name, product, category,
    subcategory, quantity, amount
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

CANONICAL = ["date", "order_id", "customer_id", "customer_name",
             "product", "category", "subcategory", "quantity", "amount"]

# Amazon region -> SP-API host
_AMZ_HOSTS = {
    "na": "https://sellingpartnerapi-na.amazon.com",
    "eu": "https://sellingpartnerapi-eu.amazon.com",
    "fe": "https://sellingpartnerapi-fe.amazon.com",
}
# a few common marketplaces (id -> region) for the picker / defaults
AMZ_MARKETPLACES = {
    "A21TJRUUN4KGV": {"label": "India (amazon.in)", "region": "eu"},
    "ATVPDKIKX0DER": {"label": "US (amazon.com)", "region": "na"},
    "A1F83G8C2ARO7P": {"label": "UK (amazon.co.uk)", "region": "eu"},
    "A1PA6795UKMFR9": {"label": "Germany (amazon.de)", "region": "eu"},
    "A2EUQ1WTGCTBG2": {"label": "Canada (amazon.ca)", "region": "na"},
    "A39IBJ37TRP1C6": {"label": "Australia (amazon.com.au)", "region": "fe"},
}


class CommerceError(RuntimeError):
    """Message safe to show the seller."""


# ---------------------------------------------------------
# Registry / metadata for the UI
# ---------------------------------------------------------
def catalog() -> list[dict]:
    return [
        {
            "id": "shopify", "label": "Shopify", "icon": "🛍️",
            "fields": [
                {"key": "shop_domain", "label": "Store domain", "placeholder": "your-store.myshopify.com"},
                {"key": "access_token", "label": "Admin API access token", "placeholder": "shpat_…", "secret": True},
            ],
            "help": "Shopify admin → Settings → Apps and sales channels → Develop apps → create an app, "
                    "enable read_orders + read_products, install it, then copy the Admin API access token.",
        },
        {
            "id": "amazon", "label": "Amazon", "icon": "📦",
            "fields": [
                {"key": "refresh_token", "label": "LWA refresh token", "placeholder": "Atzr|…", "secret": True},
                {"key": "lwa_client_id", "label": "LWA client id", "placeholder": "amzn1.application-oa2-client…"},
                {"key": "lwa_client_secret", "label": "LWA client secret", "placeholder": "amzn1.oa2-cs…", "secret": True},
                {"key": "marketplace_id", "label": "Marketplace", "placeholder": "A21TJRUUN4KGV (India)"},
            ],
            "help": "Seller Central → Apps & Services → Develop Apps → create an SP-API app (self-authorise) "
                    "to get the LWA refresh token and client id/secret.",
        },
    ]


def _blank_needed(creds: dict, keys: list[str]) -> None:
    missing = [k for k in keys if not str(creds.get(k) or "").strip()]
    if missing:
        raise CommerceError("Missing: " + ", ".join(missing))


# ---------------------------------------------------------
# Shopify
# ---------------------------------------------------------
def _shop_host(domain: str) -> str:
    d = (domain or "").strip().replace("https://", "").replace("http://", "").strip("/")
    if not d:
        raise CommerceError("Enter your Shopify store domain.")
    if "." not in d:
        d = f"{d}.myshopify.com"
    return d


def shopify_test(creds: dict) -> dict:
    _blank_needed(creds, ["shop_domain", "access_token"])
    host = _shop_host(creds["shop_domain"])
    r = requests.get(f"https://{host}/admin/api/2024-07/shop.json",
                     headers={"X-Shopify-Access-Token": creds["access_token"]}, timeout=25)
    if r.status_code == 401:
        raise CommerceError("Shopify rejected the token (401). Check the Admin API access token.")
    if r.status_code == 404:
        raise CommerceError("Store not found — check the store domain.")
    if not r.ok:
        raise CommerceError(f"Shopify error {r.status_code}: {r.text[:200]}")
    shop = (r.json() or {}).get("shop", {})
    return {"account": shop.get("myshopify_domain") or host, "name": shop.get("name")}


def shopify_pull(creds: dict, start: datetime, end: datetime) -> pd.DataFrame:
    _blank_needed(creds, ["shop_domain", "access_token"])
    host = _shop_host(creds["shop_domain"])
    headers = {"X-Shopify-Access-Token": creds["access_token"]}
    url = f"https://{host}/admin/api/2024-07/orders.json"
    params = {
        "status": "any", "limit": 250,
        "created_at_min": start.astimezone(timezone.utc).isoformat(),
        "created_at_max": end.astimezone(timezone.utc).isoformat(),
    }
    rows: list[dict] = []
    pages = 0
    while url and pages < 40:  # safety cap: 40 * 250 = 10k orders
        r = requests.get(url, headers=headers, params=params if pages == 0 else None, timeout=30)
        if not r.ok:
            raise CommerceError(f"Shopify error {r.status_code}: {r.text[:200]}")
        orders = (r.json() or {}).get("orders", [])
        for o in orders:
            cust = o.get("customer") or {}
            cname = " ".join(x for x in [cust.get("first_name"), cust.get("last_name")] if x)
            for li in (o.get("line_items") or [{}]):
                qty = li.get("quantity") or 1
                price = float(li.get("price") or 0)
                rows.append({
                    "date": o.get("created_at"),
                    "order_id": o.get("name") or o.get("id"),
                    "customer_id": cust.get("id"),
                    "customer_name": cname or (o.get("email") or None),
                    "product": li.get("title") or "Shopify order",
                    "category": (li.get("product_type") or None),
                    "subcategory": (li.get("vendor") or None),
                    "quantity": qty,
                    "amount": round(price * qty, 2),
                })
        # pagination via Link header
        url = _shopify_next(r.headers.get("Link", ""))
        pages += 1
    if not rows:
        raise CommerceError("No Shopify orders in that date range.")
    return pd.DataFrame(rows)[CANONICAL]


def _shopify_next(link_header: str) -> str | None:
    for part in (link_header or "").split(","):
        if 'rel="next"' in part:
            s = part.find("<"); e = part.find(">")
            if s != -1 and e != -1:
                return part[s + 1:e]
    return None


# ---------------------------------------------------------
# Amazon SP-API
# ---------------------------------------------------------
def _amz_access_token(creds: dict) -> str:
    r = requests.post("https://api.amazon.com/auth/o2/token", data={
        "grant_type": "refresh_token",
        "refresh_token": creds["refresh_token"],
        "client_id": creds["lwa_client_id"],
        "client_secret": creds["lwa_client_secret"],
    }, timeout=25)
    if not r.ok:
        raise CommerceError(f"Amazon login failed ({r.status_code}): {r.text[:200]}")
    tok = (r.json() or {}).get("access_token")
    if not tok:
        raise CommerceError("Amazon did not return an access token — check the LWA credentials.")
    return tok


def _amz_host(creds: dict) -> str:
    mkt = (creds.get("marketplace_id") or "A21TJRUUN4KGV").strip()
    region = AMZ_MARKETPLACES.get(mkt, {}).get("region") or creds.get("region") or "eu"
    return _AMZ_HOSTS.get(region, _AMZ_HOSTS["eu"])


def amazon_test(creds: dict) -> dict:
    _blank_needed(creds, ["refresh_token", "lwa_client_id", "lwa_client_secret"])
    tok = _amz_access_token(creds)
    return {"account": "Amazon Seller", "token_ok": bool(tok),
            "marketplace": (creds.get("marketplace_id") or "A21TJRUUN4KGV")}


def amazon_pull(creds: dict, start: datetime, end: datetime) -> pd.DataFrame:
    _blank_needed(creds, ["refresh_token", "lwa_client_id", "lwa_client_secret"])
    mkt = (creds.get("marketplace_id") or "A21TJRUUN4KGV").strip()
    host = _amz_host(creds)
    token = _amz_access_token(creds)
    headers = {"x-amz-access-token": token, "accept": "application/json"}
    params = {
        "MarketplaceIds": mkt,
        "CreatedAfter": start.astimezone(timezone.utc).isoformat(),
        "CreatedBefore": end.astimezone(timezone.utc).isoformat(),
    }
    rows: list[dict] = []
    next_token = None
    pages = 0
    while pages < 40:
        p = dict(params)
        if next_token:
            p = {"MarketplaceIds": mkt, "NextToken": next_token}
        r = requests.get(f"{host}/orders/v0/orders", headers=headers, params=p, timeout=30)
        if r.status_code == 403:
            raise CommerceError("Amazon denied access (403) — the SP-API app needs the Orders role and authorisation.")
        if not r.ok:
            raise CommerceError(f"Amazon Orders error {r.status_code}: {r.text[:200]}")
        payload = (r.json() or {}).get("payload", {})
        for o in payload.get("Orders", []):
            total = (o.get("OrderTotal") or {})
            rows.append({
                "date": o.get("PurchaseDate"),
                "order_id": o.get("AmazonOrderId"),
                "customer_id": (o.get("BuyerInfo") or {}).get("BuyerEmail"),
                "customer_name": (o.get("BuyerInfo") or {}).get("BuyerName"),
                "product": "Amazon order",
                "category": o.get("SalesChannel"),
                "subcategory": o.get("OrderStatus"),
                "quantity": o.get("NumberOfItemsShipped") or o.get("NumberOfItemsUnshipped") or 1,
                "amount": float(total.get("Amount") or 0),
            })
        next_token = payload.get("NextToken")
        pages += 1
        if not next_token:
            break
    if not rows:
        raise CommerceError("No Amazon orders in that date range.")
    return pd.DataFrame(rows)[CANONICAL]


# ---------------------------------------------------------
# Dispatch
# ---------------------------------------------------------
def test_connection(connector: str, creds: dict) -> dict:
    if connector == "shopify":
        return shopify_test(creds)
    if connector == "amazon":
        return amazon_test(creds)
    raise CommerceError(f"Unknown connector: {connector}")


def pull_orders(connector: str, creds: dict, days: int = 90) -> pd.DataFrame:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=max(1, int(days)))
    if connector == "shopify":
        df = shopify_pull(creds, start, end)
    elif connector == "amazon":
        df = amazon_pull(creds, start, end)
    else:
        raise CommerceError(f"Unknown connector: {connector}")
    for col in CANONICAL:
        if col not in df.columns:
            df[col] = None
    return df[CANONICAL]
