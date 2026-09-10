"""
Password reset — for sellers, and for shoppers on a seller's store.

A shopper who forgot their password used to be locked out of their own order
history for good, with no path back and no way for the seller to help. That is
what this fixes; sellers get the same flow because it is the same three moves.

How it works, deliberately boringly:

  * `request()` mints a random token, stores only its SHA-256 hash with an
    expiry, and mails the plaintext once. The store never holds anything that
    can be replayed if the state file leaks.
  * The reply to `request()` is identical whether or not the address exists —
    an unknown email must not tell an attacker it is unknown.
  * `consume()` verifies, deletes the record (single use), sets the new
    password and, for a shopper, revokes every live session on that store.

Tokens live in the per-account JSON state next to everything else: a seller's
own under `pw_resets`, and their shoppers' under `store_pw_resets`, keyed by
the token hash so a lookup never has to scan.
"""
from __future__ import annotations

import os

import hashlib
import secrets
import time

from backend.core import auth, messaging, user_store

SELLER_KEY = "pw_resets"
SHOPPER_KEY = "store_pw_resets"

TTL_SECONDS = 60 * 60          # one hour
_MAX_LIVE = 40                 # per account; oldest are trimmed


class ResetError(RuntimeError):
    pass


# Where a locked-out seller is told to write. Overridable so a reseller or a
# self-hosting seller can point it at their own inbox.
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL") or "support@onetapmanager.com"


def _hash(token: str) -> str:
    return hashlib.sha256((token or "").encode()).hexdigest()


def _now() -> int:
    return int(time.time())


def _load(owner: str, key: str) -> dict:
    rows = user_store.get_key(owner, key, {}) or {}
    if not isinstance(rows, dict):
        return {}
    live = {k: v for k, v in rows.items() if int(v.get("exp") or 0) > _now()}
    if len(live) > _MAX_LIVE:
        live = dict(sorted(live.items(), key=lambda kv: kv[1].get("exp") or 0)[-_MAX_LIVE:])
    return live


def _save(owner: str, key: str, rows: dict) -> None:
    user_store.set_key(owner, key, rows)


def _mint(owner: str, key: str, payload: dict) -> str:
    token = secrets.token_urlsafe(32)
    rows = _load(owner, key)
    rows[_hash(token)] = {**payload, "exp": _now() + TTL_SECONDS}
    _save(owner, key, rows)
    return token


def _claim(owner: str, key: str, token: str) -> dict:
    """Look the token up, delete it, return its payload. Single use by design."""
    rows = _load(owner, key)
    entry = rows.pop(_hash(token), None)
    _save(owner, key, rows)
    if not entry:
        raise ResetError("This reset link has expired or has already been used. "
                         "Ask for a new one.")
    return entry


# ---------------------------------------------------------------------------
# sellers
# ---------------------------------------------------------------------------
def request_seller(email: str, base_url: str) -> dict:
    """GATE 1 BLOCKER #4: this used to lie.

    With no SMTP_HOST configured, messaging.send() drops the mail into an
    in-memory outbox and returns happily. The seller was told "a reset link is
    on its way", waited, checked spam, and never got anything — locked out of
    an account holding their entire catalogue, with no way back in and no idea
    why. That is the worst failure in the product: not a feature that works
    badly, a feature that is a dead end while claiming to work.

    Whether this server can send email is a property of the SERVER, not of the
    account, so saying it plainly leaks nothing about who has an account — the
    answer is still identical whether or not the address exists.
    """
    email = (email or "").strip().lower()
    can_email = messaging.smtp_configured()
    users = auth.load_users() or {}
    if can_email and email and email in users:
        token = _mint(email, SELLER_KEY, {"email": email})
        messaging.send_password_reset(
            to_email=email,
            reset_url=f"{base_url.rstrip('/')}/reset?token={token}&email={email}",
        )
    if can_email:
        # identical answer either way — never confirm whether an address exists
        return {"ok": True, "email_ready": True,
                "message": "If that email has an account, a reset link is on its way. "
                           "It expires in an hour. Check your spam folder too."}
    return {"ok": False, "email_ready": False,
            "message": "This server cannot send email yet, so we cannot send you a "
                       "link — and we would rather say so than leave you waiting "
                       "for one that never arrives. Write to "
                       f"{SUPPORT_EMAIL} from this address and we will reset it "
                       "for you the same day. Nothing in your account is lost.",
            "support_email": SUPPORT_EMAIL}


def admin_reset_link(email: str, base_url: str) -> dict:
    """Mint a reset link for a seller who is locked out, for support to hand over.

    Gated behind ADMIN_TOKEN at the endpoint. This exists so that "we cannot
    send email yet" is an inconvenience rather than a lost account: the recovery
    path is real, someone runs it, and the seller is back in the same day.
    """
    email = (email or "").strip().lower()
    if email not in (auth.load_users() or {}):
        raise ResetError("No account with that email.")
    token = _mint(email, SELLER_KEY, {"email": email})
    return {"email": email, "expires_in_minutes": 60,
            "reset_url": f"{base_url.rstrip('/')}/reset?token={token}&email={email}"}


def reset_seller(email: str, token: str, password: str) -> dict:
    email = (email or "").strip().lower()
    if len(password or "") < 6:
        raise ResetError("Use a password of at least 6 characters.")
    _claim(email, SELLER_KEY, token)
    auth.set_password(email, password)
    return {"ok": True, "message": "Password changed. Log in with your new password."}


# ---------------------------------------------------------------------------
# shoppers on a seller's store
# ---------------------------------------------------------------------------
def request_shopper(seller: str, email: str, base_url: str, handle: str,
                    store_name: str = "") -> dict:
    from backend.core import storefront

    seller = (seller or "").strip().lower()
    email = (email or "").strip().lower()
    cust = next((c for c in storefront._customers(seller)
                 if (c.get("email") or "").strip().lower() == email), None)
    can_email = messaging.smtp_configured()
    if can_email and cust:
        token = _mint(seller, SHOPPER_KEY, {"customer_id": cust["id"], "email": email})
        messaging.send_password_reset(
            to_email=email,
            reset_url=f"{base_url.rstrip('/')}/s/{handle}?reset={token}",
            who=cust.get("name") or "",
            store_name=store_name or handle,
            phone=cust.get("phone") or "",
        )
    if can_email:
        return {"ok": True, "email_ready": True,
                "message": "If that email has an account on this store, a reset link is "
                           "on its way. It expires in an hour."}
    # A shopper cannot be told to email our support — this is the seller's shop,
    # so the seller is who can help, and they can see the customer in Orders.
    return {"ok": False, "email_ready": False,
            "message": f"{store_name or 'This store'} has not set up password emails yet. "
                       "Message the shop directly and they will sort it out for you — "
                       "or just check out as a guest, which needs no account."}


def reset_shopper(seller: str, token: str, password: str) -> dict:
    from backend.core import storefront

    seller = (seller or "").strip().lower()
    if len(password or "") < 6:
        raise ResetError("Use a password of at least 6 characters.")
    entry = _claim(seller, SHOPPER_KEY, token)
    cid = entry.get("customer_id")

    rows = storefront._customers(seller)
    cust = next((c for c in rows if c.get("id") == cid), None)
    if not cust:
        raise ResetError("That account no longer exists on this store.")
    cust["password"] = auth.hash_password(password)
    cust["password_set"] = True
    storefront._save_customers(seller, rows)

    # a reset invalidates every device that was signed in as this shopper
    sess = {t: v for t, v in storefront._sessions(seller).items()
            if v.get("customer_id") != cid}
    user_store.set_key(seller, storefront.SESSIONS_KEY, sess)

    return {"ok": True, "message": "Password changed. You can log in now.",
            "email": cust.get("email") or ""}
