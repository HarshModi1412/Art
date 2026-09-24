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
import json
import re
import secrets

from backend.core import secrets_store, user_store

log = logging.getLogger("store_payments")

CONNECTOR = "razorpay_store"     # key under which a seller's gateway lives
_INTENTS_KEY = "store_payment_intents"

try:
    import razorpay
except ImportError:                # the SDK is optional until a seller connects
    razorpay = None


# ---------------------------------------------------------------------------
# Which gateways a seller can connect, and what each one takes.
#
# One seller, one active gateway at a time (the storefront checkout can only run
# one flow). A US or UK seller connects Stripe or PayPal; an Indian seller keeps
# Razorpay. Money always lands in the SELLER's own account on their own keys —
# we never hold it — so this is not us becoming a payment aggregator.
#
# The credentials live in secrets_store (Fernet-encrypted), keyed per connector.
# The active choice is a plain per-account flag.
# ---------------------------------------------------------------------------
PROVIDER_META = {
    "razorpay": {
        "id": "razorpay", "label": "Razorpay", "connector": "razorpay_store",
        "currencies": ["INR"],
        "fields": [
            {"key": "key_id", "label": "Key ID", "secret": False, "hint": "starts with rzp_"},
            {"key": "key_secret", "label": "Key Secret", "secret": True, "hint": ""},
        ],
        "help": "For India. dashboard.razorpay.com -> Settings -> API Keys.",
    },
    "stripe": {
        "id": "stripe", "label": "Stripe", "connector": "stripe_store",
        "currencies": ["USD", "GBP", "EUR", "INR"],
        "fields": [
            {"key": "secret_key", "label": "Secret key", "secret": True, "hint": "starts with sk_"},
            {"key": "publishable_key", "label": "Publishable key", "secret": False, "hint": "starts with pk_"},
        ],
        "help": "For the US, UK and Europe. dashboard.stripe.com -> Developers -> API keys.",
    },
    "paypal": {
        "id": "paypal", "label": "PayPal", "connector": "paypal_store",
        "currencies": ["USD", "GBP", "EUR"],
        "fields": [
            {"key": "client_id", "label": "Client ID", "secret": False, "hint": ""},
            {"key": "client_secret", "label": "Secret", "secret": True, "hint": ""},
        ],
        "help": "Worldwide. developer.paypal.com -> Apps & Credentials -> your app.",
    },
}
_PROVIDER_KEY = "store_payment_provider"


def provider(seller: str) -> str:
    """The gateway the storefront checkout uses for this seller.

    The seller's explicit choice if they made one and it is connected; else the
    one gateway that IS connected; else Razorpay, the historical default."""
    chosen = str(user_store.get_key(seller, _PROVIDER_KEY, "") or "").lower()
    if chosen in PROVIDER_META and _provider_connected(seller, chosen):
        return chosen
    for pid in PROVIDER_META:
        if _provider_connected(seller, pid):
            return pid
    return "razorpay"


def set_provider(seller: str, pid: str) -> dict:
    pid = str(pid or "").lower()
    if pid not in PROVIDER_META:
        raise ValueError("Pick a payment gateway from the list.")
    user_store.set_key(seller, _PROVIDER_KEY, pid)
    return provider_status(seller)


def _provider_connected(seller: str, pid: str) -> bool:
    meta = PROVIDER_META.get(pid)
    if not meta:
        return False
    creds = secrets_store.get_credentials(seller, meta["connector"]) or {}
    return all(creds.get(f["key"]) for f in meta["fields"])


def _last4(s: str) -> str:
    s = str(s or "")
    return s[-4:] if len(s) >= 4 else s


def save_stripe_keys(seller: str, secret_key: str, publishable_key: str) -> dict:
    sk = (secret_key or "").strip()
    pk = (publishable_key or "").strip()
    if not sk or not pk:
        raise ValueError("Both the secret key and the publishable key are needed.")
    if not sk.startswith("sk_"):
        raise ValueError("A Stripe secret key starts with sk_test_ or sk_live_.")
    if not pk.startswith("pk_"):
        raise ValueError("A Stripe publishable key starts with pk_test_ or pk_live_.")
    secrets_store.save_connection(
        seller, PROVIDER_META["stripe"]["connector"],
        {"secret_key": sk, "publishable_key": pk},
        meta={"last4": _last4(pk), "mode": "live" if "_live_" in sk else "test"})
    user_store.set_key(seller, _PROVIDER_KEY, "stripe")
    return provider_status(seller)


def save_paypal_keys(seller: str, client_id: str, client_secret: str) -> dict:
    cid = (client_id or "").strip()
    csec = (client_secret or "").strip()
    if not cid or not csec:
        raise ValueError("Both the Client ID and the Secret are needed.")
    if len(cid) < 20:
        raise ValueError("That Client ID looks too short — copy the whole value from PayPal.")
    secrets_store.save_connection(
        seller, PROVIDER_META["paypal"]["connector"],
        {"client_id": cid, "client_secret": csec},
        meta={"last4": _last4(cid)})
    user_store.set_key(seller, _PROVIDER_KEY, "paypal")
    return provider_status(seller)


def disconnect_provider(seller: str, pid: str) -> dict:
    pid = str(pid or "").lower()
    meta = PROVIDER_META.get(pid)
    if meta:
        secrets_store.delete_connection(seller, meta["connector"])
        if str(user_store.get_key(seller, _PROVIDER_KEY, "") or "") == pid:
            user_store.set_key(seller, _PROVIDER_KEY, "")
    return provider_status(seller)


def provider_status(seller: str) -> dict:
    """Everything the Account tab needs to show the payment section: each
    gateway's connected state and last-four, the active one, and the currencies
    each supports. Never a secret."""
    active = provider(seller)
    out = {}
    for pid, meta in PROVIDER_META.items():
        m = secrets_store.connection_meta(seller, meta["connector"]) or {}
        out[pid] = {
            "id": pid, "label": meta["label"],
            "connected": _provider_connected(seller, pid),
            "mode": m.get("mode", ""),
            "last4": m.get("last4", ""),
            "currencies": meta["currencies"],
            "fields": meta["fields"],
            "help": meta["help"],
        }
    return {
        "active": active,
        "active_label": PROVIDER_META[active]["label"],
        "providers": out,
        "sdk": {"razorpay": razorpay is not None},
        # The live card capture for Stripe and PayPal is wired separately and
        # must be tested with the seller's own test keys before go-live; the
        # Account tab surfaces this so nobody assumes an untested charge path.
        "charge_ready": {"razorpay": True, "stripe": False, "paypal": False},
    }


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
    if payment == "upi":
        # Paid to the seller's own UPI ID, outside any gateway: nothing is
        # collected online by us and nothing is left for the courier.
        return {"online": 0.0, "on_delivery": 0.0, "kind": "upi", "upi": total}
    if advance > 0:
        advance = min(advance, total)          # never ask for more than the order
        return {"online": advance,
                "on_delivery": round(total - advance, 2),
                "kind": "cod_advance"}
    return {"online": 0.0, "on_delivery": total, "kind": "cod"}


# ---------------------------------------------------------------------------
# UPI straight to the seller's own UPI ID
# ---------------------------------------------------------------------------
# How a seller who sells in DMs is paid today: the customer pays their UPI ID
# and sends a screenshot. No gateway, no KYC, no keys. The shop takes the order
# at once with payment "to check", and the SELLER marks it paid after seeing
# the money in their own UPI app. The shopper can never mark it paid, and we
# never touch the money, so this stays as far from payment aggregation as the
# seller-owned Razorpay keys do.
UPI_RE = re.compile(r"^[a-zA-Z0-9._-]{2,256}@[a-zA-Z][a-zA-Z0-9]{1,63}$")


def clean_upi(raw: str) -> str:
    """A UPI ID as typed, tidied: no spaces, lower-case handle. "" if invalid."""
    v = re.sub(r"\s+", "", str(raw or ""))
    if not UPI_RE.match(v):
        return ""
    name, _, bank = v.partition("@")
    return f"{name}@{bank.lower()}"


def upi_ready(commerce: dict) -> bool:
    """UPI is offered only in rupees, only when switched on, with a real ID."""
    c = commerce or {}
    return (bool(c.get("upi_enabled")) and bool(clean_upi(c.get("upi_id")))
            and str(c.get("currency") or "INR").upper() == "INR")


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
def create_order(seller: str, amount: float, handle: str, note: str = "",
                 intent: dict | None = None) -> dict:
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
    intents = user_store.get_key(seller, _INTENTS_KEY, {}) or {}
    if not isinstance(intents, dict):
        intents = {}
    intents[order["id"]] = {
        "amount": paise,
        "fingerprint": str((intent or {}).get("fingerprint") or ""),
        "payment": str((intent or {}).get("payment") or ""),
        "created": __import__("time").time(),
        "payment_id": "",
    }
    # Abandoned checkouts are harmless, but never let them grow forever.
    if len(intents) > 50:
        intents = dict(sorted(intents.items(), key=lambda x: x[1].get("created", 0))[-50:])
    user_store.set_key(seller, _INTENTS_KEY, intents)
    return {
        "key_id": keys["key_id"],          # public by design
        "order_id": order["id"],
        "amount": paise,
        "currency": "INR",
    }


def verify(seller: str, order_id: str, payment_id: str, signature: str,
           amount: float, fingerprint: str, payment: str) -> bool:
    """Razorpay's HMAC check, against the seller's own secret.

    Done server-side on purpose: everything the browser sends is attacker
    controlled, so an order is only created after this returns True.
    """
    keys = get_keys(seller)
    if not keys or not (order_id and payment_id and signature):
        return False
    intents = user_store.get_key(seller, _INTENTS_KEY, {}) or {}
    intent = intents.get(order_id) if isinstance(intents, dict) else None
    expected_paise = int(round(float(amount) * 100))
    if (not isinstance(intent, dict) or intent.get("amount") != expected_paise
            or intent.get("fingerprint") != fingerprint
            or intent.get("payment") != payment):
        return False
    # A verified payment can be retried after an address-validation failure,
    # but cannot be swapped for a different Razorpay payment or a different cart.
    if intent.get("payment_id") and intent.get("payment_id") != payment_id:
        return False
    expected = hmac.new(keys["key_secret"].encode(),
                        f"{order_id}|{payment_id}".encode(),
                        hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return False
    intent["payment_id"] = payment_id
    intents[order_id] = intent
    user_store.set_key(seller, _INTENTS_KEY, intents)
    return True


def consume_verified(seller: str, order_id: str, payment_id: str) -> None:
    """Make a verified payment single-use after its order was saved."""
    intents = user_store.get_key(seller, _INTENTS_KEY, {}) or {}
    if not isinstance(intents, dict):
        return
    intent = intents.get(order_id) or {}
    if intent.get("payment_id") == payment_id:
        intents.pop(order_id, None)
        user_store.set_key(seller, _INTENTS_KEY, intents)
