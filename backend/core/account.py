"""
The Account tab, backed in one place.

Everything the app asks a seller to set up once — where they are, where and in
what currency they sell, the address their mail goes out from, their Instagram,
their payment gateway, their ChatGPT plan and (optionally) their own AI keys —
is read and written through here, so the Account screen is one call rather than
six and there is one place that knows what "set up" means.

Secrets never come back to the browser. For every credential the seller only
ever learns whether it is connected and its last four characters; the values
live encrypted in secrets_store, the same vault as the payment and mail keys.
"""
from __future__ import annotations

from backend.core import (currency, localtime, seller_mail, secrets_store,
                          store_payments, user_store)

# A seller can bring their own AI keys instead of the platform's shared ones.
# When present, these are preferred; when absent, the app's own keys are used.
#
# The OpenAI key is for PICTURES only now. Writing runs on the seller's ChatGPT
# plan through Sign in with ChatGPT (chatgpt_auth.py), which needs no key at
# all; OpenAI does not allow image generation on a ChatGPT plan, so a seller who
# wants their own bill for pictures still needs an API key for that part.
AI_CONNECTORS = {"openai": "ai_openai", "gemini": "ai_gemini"}


def ai_key(email: str, provider: str) -> str | None:
    """The seller's own key for this AI provider, or None to use the shared one."""
    conn = AI_CONNECTORS.get(str(provider or "").lower())
    if not conn:
        return None
    creds = secrets_store.get_credentials(email, conn) or {}
    return (creds.get("api_key") or "").strip() or None


def save_ai_key(email: str, provider: str, api_key: str) -> dict:
    provider = str(provider or "").lower()
    if provider not in AI_CONNECTORS:
        raise ValueError("Unknown AI provider.")
    api_key = (api_key or "").strip()
    if not api_key:
        raise ValueError("Paste your API key.")
    if provider == "openai" and not api_key.startswith("sk-"):
        raise ValueError("An OpenAI API key starts with sk-.")
    secrets_store.save_connection(email, AI_CONNECTORS[provider],
                                  {"api_key": api_key},
                                  meta={"last4": api_key[-4:]})
    return ai_status(email)


def remove_ai_key(email: str, provider: str) -> dict:
    conn = AI_CONNECTORS.get(str(provider or "").lower())
    if conn:
        secrets_store.delete_connection(email, conn)
    return ai_status(email)


def ai_status(email: str) -> dict:
    out = {}
    for pid, conn in AI_CONNECTORS.items():
        m = secrets_store.connection_meta(email, conn) or {}
        out[pid] = {"connected": secrets_store.is_connected(email, conn),
                    "last4": m.get("last4", "")}
    return out


def _instagram_status(email: str) -> dict:
    try:
        from backend.core import instagram
        st = instagram.status(email)
        return {"connected": bool(st.get("connected")),
                "username": st.get("account_username") or st.get("username") or "",
                "oauth_available": instagram.oauth_configured()}
    except Exception:  # noqa: BLE001 — the Account tab must render even if IG is down
        return {"connected": False, "username": "", "oauth_available": False}


def summary(email: str) -> dict:
    """One payload for the whole Account tab."""
    loc = localtime.get(email)
    return {
        "email": email,
        # where they are, where and in what currency they sell
        "market": {
            "country": loc["country"],
            "country_name": loc["country_name"],
            "selling_country": loc["selling_country"],
            "selling_country_name": loc["selling_country_name"],
            "currency": loc["currency"],
            "currency_symbol": loc["currency_symbol"],
            "charges_tax": loc["charges_tax"],
            "tz_label": localtime.label(email),
        },
        "countries": localtime.options(),
        "currencies": currency.options(),
        # the address their purchase orders and mail go out from
        "sender_email": seller_mail.status(email),
        # their social login
        "instagram": _instagram_status(email),
        # their storefront payment gateway (Razorpay / Stripe / PayPal)
        "payments": store_payments.provider_status(email),
        # their own AI keys, optional
        "ai_keys": ai_status(email),
        # Sign in with ChatGPT, and whether their writing runs on their plan
        "chatgpt": _chatgpt_status(email),
        # the credit balance they watch and can top up: this month's grant plus
        # any packs they bought, and what each generation spends.
        "credits": _credits_status(email),
        # their subscription tier + what upgrading to Max (premium) unlocks.
        "plan": _plan_status(email),
    }


def _plan_status(email: str) -> dict:
    """Current tier, where the 7-day trial stands, and both paid plans priced
    in the seller's billing currency, so the Account tab renders in one call."""
    try:
        from backend.core import billing, pricing
        summary = billing.plan_summary(email)
        ccy = summary["currency"]
        pid = summary["plan"]
        chatgpt = pricing.chatgpt_plan_line()
        offers = [{
            "product": p["id"],
            "name": p["name"],
            "price": pricing.price(p, ccy),
            "price_label": pricing.price_label(p, ccy),
            "price_inr": p["price_inr"],
            "period": p["period"],
            "tagline": p["tagline"],
            "includes": p["includes"],
            # OpenAI asks partner apps to show, on the plan comparison, which of
            # their plans let a seller use their ChatGPT plan: every paid one.
            "chatgpt_plan": chatgpt,
            "current": p["id"] == pid and billing.paid_active(email),
        } for p in (pricing.PLANS["pro"], pricing.PLANS["promax"])]
        return {
            "id": pid,
            "name": pricing.get_plan(pid)["name"],
            "effective": summary["effective_plan"],
            "is_paid": billing.paid_active(email),
            "is_pro": billing.paid_active(email),
            "locked": summary["locked"],
            "trial": summary["trial"],
            "paid_until": summary["paid_until"],
            "cancelled": summary["cancelled"],
            "currency": ccy,
            "launch_mode": pricing.launch_mode(),
            "offers": offers,
            # the older single-offer shape, kept for any screen still reading it
            "upgrade": offers[1],
        }
    except Exception:  # noqa: BLE001 — the tab must render even if pricing is off
        return {"id": "free", "name": "Free trial", "is_pro": False, "offers": []}


def _chatgpt_status(email: str) -> dict:
    """The ChatGPT card. Lazily imported and fenced, like the others: a problem
    reaching OpenAI must not blank the Account tab."""
    try:
        from backend.core import chatgpt_auth
        return chatgpt_auth.status(email)
    except Exception:  # noqa: BLE001
        return {"enabled": False}


def _credits_status(email: str) -> dict:
    """The Credits card payload. Imported lazily so the Account tab still
    renders if the billing stack is misconfigured on a given deployment."""
    try:
        from backend.core import credits
        return credits.status(email)
    except Exception:  # noqa: BLE001 — a missing meter must not blank the tab
        return {"enabled": False}


# ---------------------------------------------------------------------------
# Reset and delete — the two irreversible actions at the bottom of the tab.
# ---------------------------------------------------------------------------
# Per-account rows keyed by email that live in their own tables (Supabase mode).
# In local/JSON mode all of these live inside user_store's per-account state and
# are cleared when it is purged, so this sweep is a no-op there.
_PER_EMAIL_TABLES = ["feedback", "inventory", "product_inventory_map",
                     "inventory_waste", "purchase_orders", "products",
                     "product_aliases", "sites"]


def _sweep_tables(email: str, tables) -> None:
    from backend.core import db
    if not db.SUPABASE_ENABLED:
        return
    for t in tables:
        try:
            db.delete(t, {"email": email})
        except Exception:  # noqa: BLE001 — best effort, keep going
            pass


def reset(email: str) -> dict:
    """Start over: wipe settings, storefront, products, tasks and every uploaded
    file — but keep the login and any purchased credits. The seller stays signed
    in and lands on an empty workspace."""
    from backend.core import cache, chatgpt_auth, google_auth
    _sweep_tables(email, _PER_EMAIL_TABLES)
    # The sign-in links are part of the login, which Reset promises to keep.
    # Without this, a seller who signed up with Google or ChatGPT was asked for
    # a password they never set the next time they pressed that button.
    kept_chatgpt = chatgpt_auth.keep_through_reset(email)
    kept_google = google_auth.identity(email)
    user_store.purge(email)          # per-account state + all stored DataFrames
    chatgpt_auth.restore_after_reset(email, kept_chatgpt)
    if kept_google:
        user_store.set_key(email, google_auth.IDENTITY_KEY, kept_google)
    try:
        cache.clear(email)
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "reset": True}


def delete(email: str) -> dict:
    """Remove the account and everything belonging to it — settings, storefront,
    products, data, purchase ledger, sessions and the login itself. Irreversible;
    the caller signs the seller out afterwards because the session is now gone."""
    from backend.core import auth, billing, cache, chatgpt_auth
    _sweep_tables(email, _PER_EMAIL_TABLES)
    try:
        billing.purge_account(email)     # the purchase / credit ledger
    except Exception:  # noqa: BLE001
        pass
    # End this app's use of their ChatGPT plan at OpenAI and drop the sign-in
    # link, before the state that holds the tokens is gone. Never raises.
    chatgpt_auth.forget_account(email)
    user_store.purge(email)
    try:
        auth.delete_account(email)       # users + sessions + usage logs
    except Exception:  # noqa: BLE001
        pass
    try:
        cache.clear(email)
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "deleted": True}
