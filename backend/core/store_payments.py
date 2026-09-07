"""
Online payments on a seller's own storefront.

MODEL: each seller connects THEIR OWN Razorpay account.
--------------------------------------------------------
Money moves from the shopper straight into the seller's bank account. We never
hold it. That matters for more than convenience: collecting on someone else's
behalf and settling it later makes you a payment aggregator, which in India
means RBI licensing, KYC obligations and a settlement ledger. Seller-owned keys
sidestep all of it, and a seller who already sells online already has Razorpay.

Credentials live in `secrets_store` (Fernet-encrypted, same vault as the
marketplace connectors). The secret is never returned to the browser — the
settings screen only ever learns whether a key is present and what its last
four characters are.

PARTIAL COD
-----------
Cash on delivery is where Indian sellers lose money: Shipway's FY25 data puts
return-to-origin at 26% on COD against under 2% on prepaid. A small advance paid
online turns an idle order into a committed one, and it is the cheapest lever a
small seller has. So a store can require a flat advance — the seller sets the
rupee amount — with the balance collected in cash on delivery.

The advance is a real Razorpay payment against a real order. The order is only
created after the signature verifies, so an unpaid advance can never become an
order.
"""
from __future__ import annotations

import hashlib
import hmac
import logging

from backend.core import secrets_store

log = logging.getLogger("store_payments")

CONNECTOR = "razorpay_store"     # key under which a seller's gateway lives

try:
    import razorpay
except ImportError:                # the SDK is optional until a seller connects
    razorpay = None


# ---------------------------------------------------------------------------
# the seller's gateway
# ---------------------------------------------------------------------------
def get_keys(seller: str) -> dict | None:
    creds = secrets_store.get_credentials(seller, CONNECTOR) or None
    if not creds or not creds.get("key_id") or not creds.get("key_secret"):
        return None
    return creds


def connected(seller: str) -> bool:
    return get_keys(seller) is not None


def save_keys(seller: str, key_id: str, key_secret: str) -> dict:
    key_id = (key_id or "").strip()
    key_secret = (key_secret or "").strip()
    if not key_id or not key_secret:
        raise ValueError("Both the Key ID and the Key Secret are needed.")
    if not key_id.startswith("rzp_"):
        raise ValueError("A Razorpay Key ID starts with rzp_test_ or rzp_live_.")
    secrets_store.save_connection(
        seller, CONNECTOR, {"key_id": key_id, "key_secret": key_secret},
        meta={"key_id_last4": key_id[-4:], "mode": "live" if "_live_" in key_id else "test"})
    return status(seller)


def disconnect(seller: str) -> dict:
    secrets_store.delete_connection(seller, CONNECTOR)
    return status(seller)


def status(seller: str) -> dict:
    """What the settings screen may know. Never the secret."""
    keys = get_keys(seller)
    meta = secrets_store.connection_meta(seller, CONNECTOR) or {}
    return {
        "connected": bool(keys),
        "mode": meta.get("mode") or ("live" if keys and "_live_" in keys["key_id"] else "test"),
        "key_id_last4": meta.get("key_id_last4") or (keys["key_id"][-4:] if keys else ""),
        "sdk_installed": razorpay is not None,
        "detail": ("Shoppers pay into your own Razorpay account — we never hold your money."
                   if keys else
                   "Add your Razorpay keys and your store can take online payments."),
    }


def _client(seller: str):
    keys = get_keys(seller)
    if not keys:
        raise ValueError("This store has not connected a payment gateway yet.")
    if razorpay is None:
        raise RuntimeError("The razorpay package is not installed on the server. "
                           "Run: pip install razorpay")
    return razorpay.Client(auth=(keys["key_id"], keys["key_secret"])), keys


# ---------------------------------------------------------------------------
# what a shopper owes now
# ---------------------------------------------------------------------------
def split_due(commerce: dict, total: float, payment: str) -> dict:
    """How much is due online now, and how much stays for the delivery agent.

    Three shapes, all driven by the seller's own settings:
      prepaid  — everything online
      cod      — nothing online, if the store allows plain COD
      cod      — a flat advance online when the seller requires one
    """
    total = round(float(total or 0), 2)
    advance = round(float(commerce.get("cod_advance") or 0), 2)
    if payment == "prepaid":
        return {"online": total, "on_delivery": 0.0, "kind": "prepaid"}
    if advance > 0:
        advance = min(advance, total)          # never ask for more than the order
        return {"online": advance,
                "on_delivery": round(total - advance, 2),
                "kind": "cod_advance"}
    return {"online": 0.0, "on_delivery": total, "kind": "cod"}


def describe(commerce: dict) -> str:
    """The sentence a shopper reads next to the COD option."""
    advance = round(float(commerce.get("cod_advance") or 0), 2)
    if advance <= 0:
        return "Pay the courier in cash when your order arrives."
    return (f"Pay ₹{advance:,.0f} now to confirm, and the rest in cash when it "
            f"arrives. The advance is what stops us shipping orders that never "
            f"get collected.")


# ---------------------------------------------------------------------------
# taking the payment
# ---------------------------------------------------------------------------
def create_order(seller: str, amount: float, handle: str, note: str = "") -> dict:
    """A Razorpay order on the SELLER's account. Returns what the browser
    checkout needs — never the secret."""
    client, keys = _client(seller)
    paise = int(round(float(amount) * 100))
    if paise < 100:
        raise ValueError("The amount is too small to take online.")
    order = client.order.create({
        "amount": paise,
        "currency": "INR",
        "receipt": f"otm_{handle[:16]}_{int(paise)}",
        "notes": {"store": handle, "note": note[:120]},
    })
    return {
        "key_id": keys["key_id"],          # public by design
        "order_id": order["id"],
        "amount": paise,
        "currency": "INR",
    }


def verify(seller: str, order_id: str, payment_id: str, signature: str) -> bool:
    """Razorpay's HMAC check, against the seller's own secret.

    Done server-side on purpose: everything the browser sends is attacker
    controlled, so an order is only created after this returns True.
    """
    keys = get_keys(seller)
    if not keys or not (order_id and payment_id and signature):
        return False
    expected = hmac.new(keys["key_secret"].encode(),
                        f"{order_id}|{payment_id}".encode(),
                        hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
