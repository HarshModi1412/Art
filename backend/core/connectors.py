"""
POS API connectors — pull sales data straight from the café's POS.

=========================  READ THIS BEFORE TRUSTING IT  =====================
Access reality as of this build:

  PetPooja — the published API is the ONLINE ORDERING API: it lets aggregators
    push orders INTO the POS and sync menus. It is partner-gated ("contact us")
    and is not a general "pull my sales history" API. Credentials are issued
    per-integration (app_key, app_secret, access_token, restaurant_id).
    => The adapter below encodes that credential shape and the request pattern,
       but the exact reporting endpoint is NOT publicly documented. It is
       marked verified=False and MUST be confirmed against real credentials
       before being trusted. Do not ship it as "working" until then.

  Toast — has a genuinely public, documented Orders API (bulk orders by date
    range), OAuth 2.0 client-credentials auth, and a sandbox environment. A
    free developer account is available; sandbox access is requested from
    Toast's developer relations team. Toast is US-focused, so it matters for
    later expansion, not for Bengaluru cafés.

  Every POS also lets the OWNER export CSV/Excel themselves. That path needs
  zero approval and works right now — see backend/core/pos_formats.py. For an
  early-stage product that is the integration that actually ships.
==============================================================================

All adapters normalize to the canonical transaction schema so everything
downstream (analytics, RFM, menu engineering) works unchanged:

    date, order_id, customer_id, customer_name, product, category,
    subcategory, quantity, amount
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import pandas as pd

CANONICAL = ["date", "order_id", "customer_id", "customer_name",
             "product", "category", "subcategory", "quantity", "amount"]


class ConnectorError(RuntimeError):
    """Raised with a message safe to show the café owner."""


@dataclass
class Connector:
    """Base adapter. Subclasses implement fetch_orders()."""
    name: str = "base"
    label: str = "Base connector"
    verified: bool = False          # has this been proven against a live account?
    needs: list[str] = field(default_factory=list)   # required credential keys

    def validate(self, creds: dict) -> None:
        missing = [k for k in self.needs if not creds.get(k)]
        if missing:
            raise ConnectorError(f"{self.label}: missing credential(s): {', '.join(missing)}")

    def fetch_orders(self, creds: dict, start: date, end: date) -> pd.DataFrame:
        raise NotImplementedError

    @staticmethod
    def _empty() -> pd.DataFrame:
        return pd.DataFrame(columns=CANONICAL)


class PetPoojaConnector(Connector):
    """PetPooja adapter — SHAPE ONLY, NOT VERIFIED.

    The credential set and the header/payload convention below follow PetPooja's
    published integration pattern (app_key / app_secret / access_token /
    restaurant_id posted as JSON). The *reporting* endpoint is not public, so
    `endpoint` is configurable via env var rather than hardcoded to a guess.
    Until someone runs this against real credentials, treat it as a stub.
    """

    def __init__(self):
        super().__init__(
            name="petpooja",
            label="PetPooja",
            verified=False,
            needs=["app_key", "app_secret", "access_token", "restaurant_id"],
        )

    def fetch_orders(self, creds: dict, start: date, end: date) -> pd.DataFrame:
        self.validate(creds)
        endpoint = creds.get("endpoint") or os.getenv("PETPOOJA_REPORT_ENDPOINT")
        if not endpoint:
            raise ConnectorError(
                "PetPooja API access isn't configured. PetPooja issues API credentials "
                "per partner integration, and their public API covers online ordering "
                "rather than sales-history export. For now, export your sales report "
                "from the PetPooja dashboard and upload the file — Cafe_X reads that "
                "format automatically."
            )
        import requests  # imported lazily so the app runs without the dependency
        payload = {
            "app_key": creds["app_key"], "app_secret": creds["app_secret"],
            "access_token": creds["access_token"], "restaurant_id": creds["restaurant_id"],
            "start_date": start.isoformat(), "end_date": end.isoformat(),
        }
        try:
            r = requests.post(endpoint, json=payload, timeout=30)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            raise ConnectorError(f"PetPooja request failed: {e}")
        return self.normalize(data)

    @staticmethod
    def normalize(data: dict) -> pd.DataFrame:
        """Flatten an orders-with-items payload into canonical rows."""
        orders = data.get("orders") or data.get("data") or []
        rows = []
        for o in orders:
            oid = o.get("order_id") or o.get("invoice_no") or o.get("orderID")
            when = o.get("created_on") or o.get("order_date") or o.get("date")
            cust = o.get("customer") or {}
            for it in (o.get("items") or o.get("order_items") or []):
                qty = pd.to_numeric(it.get("quantity", it.get("qty", 1)), errors="coerce")
                rows.append({
                    "date": when, "order_id": oid,
                    "customer_id": cust.get("phone") or cust.get("customer_id"),
                    "customer_name": cust.get("name"),
                    "product": it.get("name") or it.get("item_name"),
                    "category": it.get("category") or it.get("item_category"),
                    "subcategory": it.get("variation"),
                    "quantity": qty,
                    "amount": pd.to_numeric(it.get("final_total", it.get("total", it.get("price"))),
                                            errors="coerce"),
                })
        df = pd.DataFrame(rows, columns=CANONICAL)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"], errors="coerce", format="mixed")
        return df


class ToastConnector(Connector):
    """Toast adapter — built against Toast's PUBLIC documented API.

    Auth: OAuth 2.0 client credentials -> bearer token.
    Data: bulk orders endpoint, queried by business date, scoped to a
    restaurant GUID via the Toast-Restaurant-External-ID header.
    Still marked verified=False until run against a real sandbox account.
    """

    AUTH_URL = "https://ws-api.toasttab.com/authentication/v1/authentication/login"
    ORDERS_URL = "https://ws-api.toasttab.com/orders/v2/ordersBulk"

    def __init__(self):
        super().__init__(
            name="toast",
            label="Toast",
            verified=False,
            needs=["client_id", "client_secret", "restaurant_guid"],
        )

    def _token(self, creds: dict) -> str:
        import requests
        try:
            r = requests.post(self.AUTH_URL, json={
                "clientId": creds["client_id"],
                "clientSecret": creds["client_secret"],
                "userAccessType": "TOAST_MACHINE_CLIENT",
            }, timeout=30)
            r.raise_for_status()
            return r.json()["token"]["accessToken"]
        except Exception as e:
            raise ConnectorError(f"Toast authentication failed: {e}")

    def fetch_orders(self, creds: dict, start: date, end: date) -> pd.DataFrame:
        self.validate(creds)
        import requests
        token = self._token(creds)
        headers = {"Authorization": f"Bearer {token}",
                   "Toast-Restaurant-External-ID": creds["restaurant_guid"]}
        frames, day = [], start
        while day <= end:                       # Toast queries one business date at a time
            try:
                r = requests.get(self.ORDERS_URL, headers=headers,
                                 params={"businessDate": day.strftime("%Y%m%d"),
                                         "pageSize": 100}, timeout=30)
                r.raise_for_status()
                frames.append(self.normalize(r.json()))
            except Exception as e:
                raise ConnectorError(f"Toast orders request failed for {day}: {e}")
            day += timedelta(days=1)
        return pd.concat(frames, ignore_index=True) if frames else self._empty()

    @staticmethod
    def normalize(orders: list) -> pd.DataFrame:
        rows = []
        for o in orders or []:
            oid = o.get("guid")
            when = o.get("openedDate") or o.get("businessDate")
            for chk in o.get("checks") or []:
                cust = chk.get("customer") or {}
                for sel in chk.get("selections") or []:
                    rows.append({
                        "date": when, "order_id": oid,
                        "customer_id": cust.get("guid") or cust.get("phone"),
                        "customer_name": " ".join(filter(None, [cust.get("firstName"), cust.get("lastName")])) or None,
                        "product": (sel.get("item") or {}).get("name") or sel.get("displayName"),
                        "category": (sel.get("salesCategory") or {}).get("name"),
                        "subcategory": (sel.get("itemGroup") or {}).get("name"),
                        "quantity": pd.to_numeric(sel.get("quantity", 1), errors="coerce"),
                        "amount": pd.to_numeric(sel.get("price", sel.get("preDiscountPrice")), errors="coerce"),
                    })
        df = pd.DataFrame(rows, columns=CANONICAL)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"], errors="coerce", format="mixed", utc=True).dt.tz_localize(None)
        return df


class MockConnector(Connector):
    """Credential-free connector that emits realistic POS-shaped payloads and
    runs them through the REAL adapters' normalize() functions.

    This is the whole point: it proves the plumbing end-to-end — fetch,
    normalize, map to canonical schema, feed analytics — without a single
    partner conversation. If the mock flows through cleanly, the only untested
    piece left is the live HTTP call itself.
    """

    def __init__(self, shape: str = "petpooja"):
        super().__init__(name=f"mock_{shape}", label=f"Mock {shape} feed",
                         verified=True, needs=[])
        self.shape = shape

    def fetch_orders(self, creds: dict, start: date, end: date) -> pd.DataFrame:
        payload = self.sample_payload(self.shape, start, end)
        if self.shape == "toast":
            return ToastConnector.normalize(payload)
        return PetPoojaConnector.normalize(payload)

    @staticmethod
    def sample_payload(shape: str, start: date, end: date) -> object:
        """Realistic payloads in each vendor's documented JSON shape."""
        import random
        random.seed(7)
        menu = [("Cappuccino", "Beverages", 180), ("Cold Coffee", "Beverages", 220),
                ("Masala Chai", "Beverages", 90), ("Veg Sandwich", "Food", 240),
                ("Chicken Sandwich", "Food", 300), ("Croissant", "Bakery", 150),
                ("Chocolate Brownie", "Desserts", 170)]
        days = max((end - start).days + 1, 1)
        if shape == "toast":
            orders = []
            for d in range(days):
                when = datetime.combine(start + timedelta(days=d), datetime.min.time())
                for n in range(random.randint(4, 12)):
                    sels = []
                    for item, cat, price in random.sample(menu, random.randint(1, 3)):
                        q = random.randint(1, 2)
                        sels.append({"item": {"name": item}, "salesCategory": {"name": cat},
                                     "itemGroup": {"name": cat}, "quantity": q, "price": price * q})
                    orders.append({
                        "guid": f"toast-{d}-{n}",
                        "openedDate": when.replace(hour=random.randint(8, 21)).isoformat() + "Z",
                        "checks": [{"customer": {"guid": f"cust-{random.randint(1, 40)}",
                                                 "firstName": "Guest", "lastName": str(random.randint(1, 40))},
                                    "selections": sels}],
                    })
            return orders
        # petpooja-shaped
        orders = []
        for d in range(days):
            when = start + timedelta(days=d)
            for n in range(random.randint(4, 12)):
                items = []
                for item, cat, price in random.sample(menu, random.randint(1, 3)):
                    q = random.randint(1, 2)
                    items.append({"name": item, "category": cat, "quantity": q,
                                  "final_total": price * q, "variation": ""})
                cid = random.randint(1, 40)
                orders.append({
                    "order_id": f"INV{d:03d}{n:02d}",
                    "order_date": f"{when.isoformat()} {random.randint(8, 21):02d}:15:00",
                    "customer": {"phone": f"90000000{cid:02d}", "name": f"Customer {cid}"},
                    "items": items,
                })
        return {"orders": orders}


REGISTRY: dict[str, Connector] = {
    "petpooja": PetPoojaConnector(),
    "toast": ToastConnector(),
    "mock_petpooja": MockConnector("petpooja"),
    "mock_toast": MockConnector("toast"),
}


def available() -> list[dict]:
    """What the UI shows in the 'Connect your POS' panel."""
    return [{"id": k, "label": c.label, "verified": c.verified, "needs": c.needs}
            for k, c in REGISTRY.items()]


def pull(connector_id: str, creds: dict, start: date, end: date) -> pd.DataFrame:
    c = REGISTRY.get(connector_id)
    if not c:
        raise ConnectorError(f"Unknown connector: {connector_id}")
    df = c.fetch_orders(creds or {}, start, end)
    if df.empty:
        raise ConnectorError("The POS returned no orders for that date range.")
    for col in CANONICAL:                      # guarantee the canonical shape
        if col not in df.columns:
            df[col] = None
    return df[CANONICAL]
