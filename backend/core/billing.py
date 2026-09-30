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
from datetime import datetime, timedelta, timezone

import pandas as pd

from backend.core import auth, currency, db, pricing, user_store

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


# ---------------- the account's billing record ----------------
# One small record per account in user_store, so it needs no table migration:
#   trial_started_at  when the 7-day trial began (written at signup)
#   currency          "USD" or "INR", fixed at signup from where they signed up
#   paid_until        end of the month they last paid for
#   payments          the last few payments, with the currency they were in
BILLING_KEY = "billing_account"
PAID_PERIOD_DAYS = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _parse(s) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(s))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _record(email: str) -> dict:
    rec = user_store.get_key(email, BILLING_KEY, {}) or {}
    return rec if isinstance(rec, dict) else {}


def _save_record(email: str, rec: dict) -> None:
    user_store.set_key(email, BILLING_KEY, rec)


def start_trial(email: str, currency_code: str | None = None,
                region_code: str | None = None) -> dict:
    """Write the trial start date and billing currency, once.

    Called at signup, before the account is handed back, so every new account
    has its start date on record from its first second. Calling it again never
    moves the date: a trial cannot be restarted."""
    rec = _record(email)
    changed = False
    if not rec.get("trial_started_at"):
        rec["trial_started_at"] = _iso(_now())
        changed = True
    if not rec.get("currency"):
        rec["currency"] = "INR" if str(currency_code).upper() == "INR" else "USD"
        changed = True
    if region_code and not rec.get("signup_region"):
        rec["signup_region"] = str(region_code).lower()
        changed = True
    if changed:
        _save_record(email, rec)
    return rec


def billing_currency(email: str) -> str:
    """The currency this account is billed in. Set at signup; USD if missing."""
    return "INR" if str(_record(email).get("currency")).upper() == "INR" else "USD"


def trial_info(email: str) -> dict:
    """Where the 7-day trial stands. An account from before the trial existed
    gets its start date now, so it has 7 days from today rather than none."""
    rec = _record(email)
    started = _parse(rec.get("trial_started_at"))
    if started is None:
        rec = start_trial(email)
        started = _parse(rec.get("trial_started_at")) or _now()
    ends = started + timedelta(days=pricing.TRIAL_DAYS)
    left = ends - _now()
    return {
        "started_at": _iso(started),
        "ends_at": _iso(ends),
        "active": left.total_seconds() > 0,
        # rounded up, so the last afternoon reads "1 day left", not "0"
        "days_left": max(0, -(-int(left.total_seconds()) // 86400)),
        "days": pricing.TRIAL_DAYS,
    }


def paid_until(email: str) -> datetime | None:
    return _parse(_record(email).get("paid_until"))


def _extend_paid(email: str, product_id: str, amount: float, ccy: str,
                 order_id: str, payment_id: str) -> None:
    """A paid month starts now, or where the current paid month ends if that
    is later, so paying early never loses days."""
    rec = _record(email)
    base = max(_now(), _parse(rec.get("paid_until")) or _now())
    rec["paid_until"] = _iso(base + timedelta(days=PAID_PERIOD_DAYS))
    pays = list(rec.get("payments") or [])[-23:]
    pays.append({"product": product_id, "amount": amount, "currency": ccy,
                 "order_id": order_id, "payment_id": payment_id, "at": _iso(_now())})
    rec["payments"] = pays
    rec.pop("cancelled_at", None)
    _save_record(email, rec)
    _lock_cache.pop(email, None)


# ---------------- plans ----------------
def get_plan(email: str) -> str:
    """The stored tier: 'free' (trial or lapsed), 'pro' or 'promax'. Legacy
    rows normalise in pricing.normalize_plan."""
    return pricing.normalize_plan(auth.get_plan(email))


def set_plan(email: str, plan: str) -> None:
    auth.set_plan(email, pricing.normalize_plan(plan))


def paid_active(email: str) -> bool:
    """A paid tier whose month has not run out. A paid row from before
    paid_until existed gets one month from now, once."""
    if get_plan(email) not in pricing.PAID_PLANS:
        return False
    until = paid_until(email)
    if until is None:
        rec = _record(email)
        rec["paid_until"] = _iso(_now() + timedelta(days=PAID_PERIOD_DAYS))
        _save_record(email, rec)
        return True
    return until > _now()


def effective_plan(email: str) -> str:
    """What the account may use right now: 'promax' in launch mode or a live
    trial, the paid tier while its month lasts, else 'free' (locked)."""
    if pricing.launch_mode():
        return "promax"
    if paid_active(email):
        return get_plan(email)
    if trial_info(email)["active"]:
        return "promax"
    return "free"


def is_locked(email: str) -> bool:
    """Trial over and nothing paid: the app shows the plan picker only."""
    return effective_plan(email) == "free"


# The request gate in main.py asks on every API call, so the answer is kept for
# a minute. A payment clears it at once (_extend_paid), so a seller who has just
# paid is never locked out by a stale entry.
_LOCK_TTL = 60.0
_lock_cache: dict[str, tuple[float, bool]] = {}


def is_locked_cached(email: str) -> bool:
    import time
    now = time.monotonic()
    hit = _lock_cache.get(email)
    if hit and now - hit[0] < _LOCK_TTL:
        return hit[1]
    locked = is_locked(email)
    if len(_lock_cache) > 5000:
        _lock_cache.clear()
    _lock_cache[email] = (now, locked)
    return locked


def is_unlimited(email: str) -> bool:
    return effective_plan(email) in pricing.PAID_PLANS


def cancel_subscription(email: str) -> dict:
    """Stop the subscription. Nothing renews on its own (a paid month is paid
    for from the app, not charged automatically), so cancelling means the
    current month runs to its end and is not renewed. The plan is kept until
    then, and the data is kept after."""
    was = get_plan(email)
    if was not in pricing.PAID_PLANS:
        return {"ok": True, "plan": was, "was": was,
                "message": "You are not on a paid plan, so there is nothing to cancel."}
    rec = _record(email)
    rec["cancelled_at"] = _iso(_now())
    _save_record(email, rec)
    until = paid_until(email)
    ends = until.strftime("%B %d, %Y").replace(" 0", " ") if until else "the end of this month"
    try:
        from backend.core import errors
        errors.record(RuntimeError("subscription cancelled"), where=f"billing.cancel:{email}")
    except Exception:  # noqa: BLE001 — never fail a cancellation over a log line
        pass
    return {"ok": True, "plan": was, "was": was,
            "message": f"Cancelled. {pricing.get_plan(was)['name']} stays on until {ends} "
                       f"and will not renew. Your data is kept."}


def plan_summary(email: str) -> dict:
    """Everything the UI needs to render entitlements without a second call."""
    pid = get_plan(email)
    eff = effective_plan(email)
    ccy = billing_currency(email)
    plan = pricing.get_plan(pid)
    until = paid_until(email)
    return {
        "plan": pid,
        "plan_name": plan["name"],
        "effective_plan": eff,
        "locked": eff == "free",
        "currency": ccy,
        "price": pricing.price(plan, ccy),
        "price_inr": plan["price_inr"],
        "trial": trial_info(email),
        "paid_until": _iso(until) if until else None,
        "cancelled": bool(_record(email).get("cancelled_at")),
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
def record_purchase(email: str, product_id: str, order_id: str = "", payment_id: str = "",
                    ccy: str = "INR") -> None:
    product = pricing.get_product(product_id)
    if not product:
        raise ValueError(f"Unknown product: {product_id}")
    # amount_inr is only true for a rupee payment. A dollar payment records 0
    # here; its real amount and currency are in the account's billing record
    # (_extend_paid), so this table needs no migration.
    amount_inr = int(product["price_inr"]) if str(ccy).upper() == "INR" else 0

    if db.SUPABASE_ENABLED:
        db.insert("purchases", {
            "email": email, "product": product_id,
            "credits_total": int(product["credits"]), "credits_used": 0,
            "amount_inr": amount_inr,
            "order_id": order_id, "payment_id": payment_id,
        })
        return

    df = _read_ledger()
    df = pd.concat([df, pd.DataFrame([{
        "email": email, "product": product_id,
        "credits_total": product["credits"], "credits_used": 0,
        "amount_inr": amount_inr,
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
    """Does this seller have access — by tier (or live trial), or by credits?"""
    if pricing.plan_allows(effective_plan(email), feature):
        return True
    cost = pricing.credits_for(feature)
    return bool(cost) and credit_pool(email) >= cost


def check_and_consume(email: str, product_id: str) -> bool:
    """Gate for a paid action. True if it may proceed — spending credits only
    when the seller's tier does not already include it."""
    if pricing.plan_allows(effective_plan(email), product_id):
        return True
    cost = pricing.credits_for(product_id)
    if not cost:
        return False
    return spend_credits(email, cost)


def paywall(feature: str, email: str | None = None) -> dict:
    """The 402 body: what they hit, and the plan that includes it, priced in
    the seller's own billing currency."""
    plan = pricing.upgrade_target(feature)
    ccy = billing_currency(email) if email else "USD"
    locked = bool(email) and is_locked(email)
    if locked:
        # Trial over: offer Pro, the cheapest way back in, whatever they hit.
        plan = pricing.PLANS["pro"]
    label = pricing.price_label(plan, ccy) if plan else ""
    if locked:
        msg = (f"Your {pricing.TRIAL_DAYS}-day free trial has ended. Pick Pro ({label} a month) "
               f"or Pro Max ({pricing.price_label(pricing.PLANS['promax'], ccy)} a month) "
               f"to keep going. Your data is all still here.")
    elif plan:
        msg = f"{plan['name']} at {label} a month includes this."
    else:
        msg = "This action needs a paid plan."
    return {
        "code": "trial_ended" if locked else "paywall",
        "product": feature,
        "upgrade_to": plan["id"] if plan else None,
        "upgrade_name": plan["name"] if plan else None,
        "upgrade_price": pricing.price(plan, ccy) if plan else None,
        "upgrade_price_label": label or None,
        "upgrade_price_inr": plan["price_inr"] if plan else None,
        "currency": ccy,
        "credits_needed": None,
        "message": msg,
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
    ccy = billing_currency(email)
    if is_pack and ccy != "INR":
        raise ValueError("Credit packs are sold in rupees only for now.")
    price_now = float(pricing.price(product, ccy))
    if not gateway_configured():
        raise RuntimeError(
            "Payment gateway not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET "
            "environment variables (get keys from dashboard.razorpay.com)."
        )
    if razorpay is None:
        raise RuntimeError("razorpay package not installed. Run: pip install razorpay")

    # Smallest unit of the billing currency: paise, or cents. Charging in USD
    # needs International Payments switched on in the Razorpay dashboard.
    amount_minor = max(100, currency.minor_units(price_now, ccy))
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
            "amount": amount_minor,
            "currency": ccy,
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
        "amount": price_now,
        "currency": ccy,
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
        "amount": amount_minor,
        "currency": ccy,
        "name": f"One Tap Manager — {product['name']}",
        "description": f"{product['name']} — {pricing.price_label(product, ccy)}"
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

        ccy = str(rec.get("currency") or "INR").upper()
        if product_id in pricing.PLANS or product_id in pricing.PLAN_ALIASES:
            set_plan(email, product_id)
            _extend_paid(email, pricing.normalize_plan(product_id),
                         float(rec.get("amount") or 0), ccy, order_id, payment_id)
        record_purchase(email, product_id, order_id, payment_id, ccy)
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
