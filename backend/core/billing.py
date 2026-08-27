"""
Billing — à-la-carte purchases + Chain subscription + Razorpay gateway.

Purchases are recorded as a ledger: each row is one purchase with a credit
balance (e.g. winback_campaign grants 1 use, ai_topup grants 10). The only
monthly plan is "chain"; legacy "pro" accounts are treated as chain.

Storage backend is pluggable (see backend/core/db.py):
  * Supabase configured -> the ledger lives in the `purchases` table.
  * Otherwise            -> data/purchases.csv (original behaviour).

While pricing.launch_mode() is on, nothing here gates anything.

Razorpay credentials: RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET.
"""
import hashlib
import hmac
import os
from datetime import datetime

import pandas as pd

from backend.core import auth, db, pricing

try:
    import razorpay
except ImportError:
    razorpay = None

PURCHASES_FILE = os.path.join(auth.BASE_DIR, "purchases.csv")
_PURCHASE_COLS = ["email", "product", "credits_total", "credits_used",
                  "amount_inr", "order_id", "payment_id", "created"]

# order_id -> (email, product_id) for orders awaiting payment verification.
# Short-lived (one checkout round-trip); kept in memory intentionally.
_pending_orders: dict[str, tuple[str, str]] = {}


# ---------------- plans ----------------
def get_plan(email: str) -> str:
    """'free' or 'chain'. Legacy 'pro' accounts count as chain."""
    plan = auth.get_plan(email)
    return "chain" if plan in ("pro", "chain") else "free"


def set_plan(email: str, plan: str) -> None:
    auth.set_plan(email, plan)


def is_unlimited(email: str) -> bool:
    return get_plan(email) == "chain"


# ---------------- purchase ledger (local CSV mode) ----------------
def _read_ledger() -> pd.DataFrame:
    if not os.path.exists(PURCHASES_FILE):
        os.makedirs(os.path.dirname(PURCHASES_FILE), exist_ok=True)
        df = pd.DataFrame(columns=_PURCHASE_COLS)
        df.to_csv(PURCHASES_FILE, index=False)
        return df
    return pd.read_csv(PURCHASES_FILE)


def _write_ledger(df: pd.DataFrame) -> None:
    df.to_csv(PURCHASES_FILE, index=False)


# ---------------- purchase ledger (public API) ----------------
def record_purchase(email: str, product_id: str, order_id: str = "", payment_id: str = "") -> None:
    product = pricing.get_product(product_id)
    if not product:
        raise ValueError(f"Unknown product: {product_id}")

    if db.SUPABASE_ENABLED:
        db.insert("purchases", {
            "email": email, "product": product_id,
            "credits_total": int(product["credits"]), "credits_used": 0,
            "amount_inr": int(product["price_inr"]),
            "order_id": order_id, "payment_id": payment_id,
        })
        return

    df = _read_ledger()
    df = pd.concat([df, pd.DataFrame([{
        "email": email, "product": product_id,
        "credits_total": product["credits"], "credits_used": 0,
        "amount_inr": product["price_inr"],
        "order_id": order_id, "payment_id": payment_id,
        "created": datetime.now().isoformat(),
    }])], ignore_index=True)
    _write_ledger(df)


def credit_balance(email: str, product_id: str) -> int:
    """Unused credits this user holds for a product."""
    if db.SUPABASE_ENABLED:
        rows = db.fetch_all("purchases", {"email": email, "product": product_id})
        return int(sum(max(0, int(r.get("credits_total", 0)) - int(r.get("credits_used", 0)))
                       for r in rows))

    df = _read_ledger()
    if df.empty:
        return 0
    rows = df[(df["email"] == email) & (df["product"] == product_id)]
    if rows.empty:
        return 0
    return int((rows["credits_total"] - rows["credits_used"]).clip(lower=0).sum())


def consume_credit(email: str, product_id: str) -> bool:
    """Spend one credit (oldest purchase first). False if none available."""
    if db.SUPABASE_ENABLED:
        c = db.client()
        res = (c.table("purchases").select("*")
               .eq("email", email).eq("product", product_id)
               .order("created", desc=False).execute())
        for row in (res.data or []):
            if int(row.get("credits_used", 0)) < int(row.get("credits_total", 0)):
                c.table("purchases").update(
                    {"credits_used": int(row.get("credits_used", 0)) + 1}
                ).eq("id", row["id"]).execute()
                return True
        return False

    df = _read_ledger()
    if df.empty:
        return False
    mask = (df["email"] == email) & (df["product"] == product_id) & \
           (df["credits_used"] < df["credits_total"])
    idx = df[mask].index
    if len(idx) == 0:
        return False
    df.loc[idx[0], "credits_used"] = int(df.loc[idx[0], "credits_used"]) + 1
    _write_ledger(df)
    return True


# ---------------- entitlement checks (the actual gates) ----------------
def can_use_free(feature_or_product: str) -> bool:
    """True when no gate applies at all: launch mode, or a free-forever feature."""
    return pricing.launch_mode() or feature_or_product in pricing.FREE_FOREVER


def check_and_consume(email: str, product_id: str) -> bool:
    """Gate for one-shot paid features (winback_campaign, positioning_report).
    Returns True if the action may proceed (and burns a credit when one is due)."""
    if pricing.launch_mode() or is_unlimited(email):
        return True
    return consume_credit(email, product_id)


# ---------------- razorpay ----------------
def gateway_configured() -> bool:
    return bool(os.environ.get("RAZORPAY_KEY_ID") and os.environ.get("RAZORPAY_KEY_SECRET"))


def create_order(email: str, product_id: str) -> dict:
    """Create a Razorpay order for any catalog product."""
    product = pricing.get_product(product_id)
    if not product:
        raise ValueError("Unknown product")
    if pricing.launch_mode():
        return {"launch_free": True, "product": product_id}
    if not gateway_configured():
        raise RuntimeError(
            "Payment gateway not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET "
            "environment variables (get keys from dashboard.razorpay.com)."
        )
    if razorpay is None:
        raise RuntimeError("razorpay package not installed. Run: pip install razorpay")

    amount_paise = product["price_inr"] * 100
    client = razorpay.Client(auth=(os.environ["RAZORPAY_KEY_ID"], os.environ["RAZORPAY_KEY_SECRET"]))
    order = client.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "receipt": f"cx_{product_id[:12]}_{email[:20]}",
        "notes": {"email": email, "product": product_id},
    })
    _pending_orders[order["id"]] = (email, product_id)
    return {
        "key_id": os.environ["RAZORPAY_KEY_ID"],
        "order_id": order["id"],
        "amount": amount_paise,
        "currency": "INR",
        "name": f"Cafe_X — {product['name']}",
        "description": f"{product['name']} — ₹{product['price_inr']}"
                       + ("/month" if product["kind"] == "subscription" else ""),
        "product": product_id,
    }


def verify_payment(email: str, order_id: str, payment_id: str, signature: str,
                   product_id: str | None = None) -> str | None:
    """Verify Razorpay's HMAC signature. On success grant the purchase and
    return the product_id granted; None on failure."""
    secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
    expected = hmac.new(
        secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return None

    pending = _pending_orders.pop(order_id, None)
    if pending:
        email, product_id = pending
    if not product_id or not pricing.get_product(product_id):
        return None

    if product_id == "chain_monthly":
        set_plan(email, "chain")
    record_purchase(email, product_id, order_id, payment_id)
    return product_id
