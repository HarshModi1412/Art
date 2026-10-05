"""
A tracked "chat with the shop on WhatsApp" link, for sellers with no website.

WHY
---
A campaign's link normally opens the seller's shop with the customer's code
already applied, and the open is the first step of the funnel. A seller with
no published website has nowhere to send that link, so the message would
carry a code and no way to use it, and the tracker would see nothing.

Instead the message says "reply with your code" and carries this link:

    https://<app>/w/<shop token>/<CODE>

Opening it stamps a click on the customer's code (discounts.track, the same
counter the website uses) and forwards to a WhatsApp chat with the seller's
own number, the text already typed: "Hi! I'd like to use my code PRIYA-7K2PQ".
So the seller gets the order in their chat, and the campaign results still
show who opened it.

The shop token is short and random (never the seller's email) and is kept in
a shared registry so the public route can find the seller from it.
"""
from __future__ import annotations

import secrets
from urllib.parse import quote

from backend.core import user_store

REGISTRY = "chat-links@system.local"   # a pseudo-account holding token -> seller
REG_KEY = "chat_tokens"
USER_KEY = "chat_token"


def token(email: str) -> str:
    """This seller's public shop token, made once."""
    t = user_store.get_key(email, USER_KEY) or ""
    if t:
        return t
    t = secrets.token_urlsafe(6).replace("-", "x").replace("_", "y")
    reg = dict(user_store.get_key(REGISTRY, REG_KEY, {}) or {})
    reg[t] = (email or "").strip().lower()
    user_store.set_key(REGISTRY, REG_KEY, reg)
    user_store.set_key(email, USER_KEY, t)
    return t


def seller_for(tok: str) -> str:
    reg = user_store.get_key(REGISTRY, REG_KEY, {}) or {}
    return reg.get(str(tok or "")) or ""


def url(email: str, code: str, base: str) -> str:
    return f"{base.rstrip('/')}/w/{token(email)}/{quote(str(code or ''))}"


def target(email: str, code: str) -> str:
    """Where the link lands: a WhatsApp chat with the seller, code typed."""
    from backend.core import brandname, whatsapp
    num = (whatsapp._cfg(email).get("number") or "")  # noqa: SLF001
    brand = brandname.name(email) if hasattr(brandname, "name") else ""
    text = f"Hi {brand}! I'd like to use my code {code}".replace("Hi !", "Hi!")
    if not num:
        return ""
    return f"https://wa.me/{num}?text={quote(text)}"
