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
import threading
from datetime import datetime

import pandas as pd

from backend.core import auth, db, pricing, user_store

try:
    import razorpay
except ImportError:
    razorpay = None

PURCHASES_FILE = os.path.join(auth.BASE_DIR, "purchases.csv")
_PURCHASE_COLS = ["email", "product", "credits_total", "credits_used",
                  "amount_inr", "order_id", "payment_id", "created"]

# order_id -> (email, product_id) for orders awaiting payment verification.
# Short-lived (one checkout round-trip); kept in memory intentionally.
_PENDING_KEY = "billing_pending_orders"
_pending_lock = threading.Lock()


def _pending_for(email: str) -> dict:
    """Pending checkout records belong to the buyer and must survive a restart.

    Keeping this only in process memory made a completed Razorpay signature
    reusable after a restart: the client could choose a different product when
    no matching pending entry was found.  The record is deliberately stored
    with the account, not trusted from the browser.
    """
    rows = user_store.get_key(email, _PENDING_KEY, {}) or {}
    return rows if isinstance(rows, dict) else {}


def _save_pending(email: str, rows: dict) -> None:
    user_store.set_key(email, _PENDING_KEY, rows)


# ---------------- plans ----------------
def get_plan(email: str) -> str:
    """'free' | 'pro' (displayed as Max). Legacy 'chain' rows normalise to pro;
    legacy 'semipro' rows normalise to free — that tier's feature set now
    lives in Free permanently."""
    return pricing.normalize_plan(auth.get_plan(email))


def set_plan(email: str, plan: str) -> None:
    auth.set_plan(email, pricing.normalize_plan(plan))


def is_unlimited(email: str) -> bool:
    return get_plan(email) == "pro"


def plan_summary(email: str) -> dict:
    """Everything the UI needs to render entitlements without a second call."""
    pid = get_plan(email)
    plan = pricing.get_plan(pid)
    return {
        "plan": pid,
        "plan_name": plan["name"],
        "price_inr": plan["price_inr"],
        "limits": plan["limits"],
        "credits": credit_pool(email),
        "launch_mode": pricing.launch_mode(),
    }


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


# ---------------- the usage plan: one shared credit pool ----------------
# Credits bought in any pack land in one pool. A gated action either comes with
# the seller's tier, or costs credits from the pool — never both, and never a
# cut of their sales.
def credit_pool(email: str) -> int:
    return sum(credit_balance(email, pack_id) for pack_id in pricing.CREDIT_PACKS)


def spend_credits(email: str, n: int) -> bool:
    """Spend n credits from the pool, oldest pack first. All-or-nothing."""
    n = int(n)
    if n <= 0:
        return True
    if credit_pool(email) < n:
        return False
    for pack_id in pricing.CREDIT_PACKS:
        while n > 0 and credit_balance(email, pack_id) > 0:
            if not consume_credit(email, pack_id):
                break
            n -= 1
        if n <= 0:
            return True
    return n <= 0


# ---------------- entitlement checks (the actual gates) ----------------
def can_use_free(feature_or_product: str) -> bool:
    """True when no gate applies at all: launch mode, or a free-forever feature."""
    return pricing.launch_mode() or feature_or_product in pricing.FREE_FOREVER


def can_use(email: str, feature: str) -> bool:
    """Does this seller have access — by tier, or by credits they hold?"""
    if pricing.plan_allows(get_plan(email), feature):
        return True
    cost = pricing.credits_for(feature)
    return bool(cost) and credit_pool(email) >= cost


def check_and_consume(email: str, product_id: str) -> bool:
    """Gate for a paid action. True if it may proceed — spending credits only
    when the seller's tier does not already include it."""
    if pricing.plan_allows(get_plan(email), product_id):
        return True
    cost = pricing.credits_for(product_id)
    if not cost:
        return False
    return spend_credits(email, cost)


def paywall(feature: str) -> dict:
    """The 402 body: what they hit, and the two honest ways past it."""
    plan = pricing.upgrade_target(feature)
    cost = pricing.credits_for(feature)
    return {
        "code": "paywall",
        "product": feature,
        "upgrade_to": plan["id"] if plan else None,
        "upgrade_name": plan["name"] if plan else None,
        "upgrade_price_inr": plan["price_inr"] if plan else None,
        "credits_needed": cost or None,
        "message": (
            f"{plan['name']} at ₹{plan['price_inr']}/month includes this, or spend "
            f"{cost} credit{'s' if cost != 1 else ''} from a pack — no monthly commitment."
            if plan and cost else
            (f"{plan['name']} at ₹{plan['price_inr']}/month includes this."
             if plan else "This action needs a paid plan.")
        ),
    }


# ---------------- razorpay ----------------
def _rzp_creds() -> tuple[str, str]:
    """The platform Razorpay key id + secret from the environment, cleaned of
    the stray whitespace or surrounding quotes a dashboard paste sometimes
    leaves behind. Either of those is invisible in the Render UI but makes the
    key wrong on the wire, and Razorpay answers 'Authentication failed' — the
    same 401 as a genuinely mismatched pair, so we rule this one out here."""
    def clean(v: str | None) -> str:
        v = (v or "").strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1].strip()
        return v
    return clean(os.environ.get("RAZORPAY_KEY_ID")), clean(os.environ.get("RAZORPAY_KEY_SECRET"))


def gateway_configured() -> bool:
    kid, ksec = _rzp_creds()
    return bool(kid and ksec)


def create_order(email: str, product_id: str) -> dict:
    """Create a Razorpay order for any catalog product.

    Credit packs are a real, paid top-up and always go through Razorpay — even
    during launch. Launch mode keeps the FEATURES free, not the credits a seller
    chooses to stockpile, so a pack purchase never short-circuits to "free".
    Subscriptions (the Max tier) stay free while launch mode is on, because the
    tier's features are already unlocked for everyone then."""
    product = pricing.get_product(product_id)
    if not product:
        raise ValueError("Unknown product")
    is_pack = product_id in pricing.CREDIT_PACKS
    if pricing.launch_mode() and not is_pack:
        return {"launch_free": True, "product": product_id}
    if not gateway_configured():
        raise RuntimeError(
            "Payment gateway not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET "
            "environment variables (get keys from dashboard.razorpay.com)."
        )
    if razorpay is None:
        raise RuntimeError("razorpay package not installed. Run: pip install razorpay")

    amount_paise = max(100, int(round(float(product["price_inr"]) * 100)))
    # Razorpay receipts cap at 40 characters and validate most reliably as plain
    # alphanumerics — the raw email (with @ and .) is neither and can trip a 400,
    # so build a short, safe reference. The email still travels in `notes`, which
    # is where verification reads it back.
    tag = "".join(ch for ch in f"{product_id}{email}" if ch.isalnum())
    receipt = ("otm" + tag)[:40]
    key_id, key_secret = _rzp_creds()
    client = razorpay.Client(auth=(key_id, key_secret))
    try:
        order = client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt,
            "notes": {"email": email, "product": product_id},
        })
    except Exception as e:  # noqa: BLE001 — surface Razorpay's own reason, not a 500
        try:
            from backend.core import errors
            errors.record(e, where="razorpay order.create")
        except Exception:  # noqa: BLE001
            pass
        detail = ""
        # razorpay errors carry the API description; dig it out when present.
        for attr in ("error", "args"):
            val = getattr(e, attr, None)
            if val:
                detail = str(val)
                break
        raise RuntimeError(
            "The payment gateway rejected the order"
            + (f": {detail or e}" if (detail or str(e)) else ".")
            + " Check that the Razorpay keys on the server are valid and the "
              "account can accept payments."
        ) from e
    pending = _pending_for(email)
    pending[order["id"]] = {
        "product": product_id,
        "created": datetime.now().isoformat(),
    }
    # Keep this small even if somebody abandons many checkouts.
    if len(pending) > 30:
        keep = sorted(pending.items(), key=lambda x: x[1].get("created", ""))[-30:]
        pending = dict(keep)
    _save_pending(email, pending)
    return {
        "key_id": key_id,
        "order_id": order["id"],
        "amount": amount_paise,
        "currency": "INR",
        "name": f"One Tap Manager — {product['name']}",
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

    # Never accept the product from the browser.  A signature proves that a
    # Razorpay payment exists, not what the caller wants to receive for it.
    # Requiring and consuming the server-side checkout record also makes a
    # payment id single-use.
    with _pending_lock:
        pending = _pending_for(email)
        rec = pending.get(order_id)
        if not isinstance(rec, dict):
            return None
        product_id = str(rec.get("product") or "")
        if not pricing.get_product(product_id):
            return None
        pending.pop(order_id, None)
        _save_pending(email, pending)

        if product_id in pricing.PLANS or product_id in pricing.PLAN_ALIASES:
            set_plan(email, product_id)
        record_purchase(email, product_id, order_id, payment_id)
        return product_id


def purge_account(email: str) -> None:
    """Delete this account's whole purchase ledger — every pack and every
    credit balance it holds. Only for account deletion; Reset deliberately does
    NOT call this, so purchased credits survive a reset."""
    if db.SUPABASE_ENABLED:
        try:
            db.delete("purchases", {"email": email})
        except Exception:  # noqa: BLE001
            pass
        return
    df = _read_ledger()
    if df.empty:
        return
    keep = df[df["email"].astype(str).str.strip().str.lower()
              != (email or "").strip().lower()]
    _write_ledger(keep)
