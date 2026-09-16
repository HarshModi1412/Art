"""
The Account tab, backed in one place.

Everything the app asks a seller to set up once — where they are, where and in
what currency they sell, the address their mail goes out from, their Instagram,
their payment gateway, and (optionally) their own AI keys — is read and written
through here, so the Account screen is one call rather than six and there is one
place that knows what "set up" means.

Secrets never come back to the browser. For every credential the seller only
ever learns whether it is connected and its last four characters; the values
live encrypted in secrets_store, the same vault as the payment and mail keys.
"""
from __future__ import annotations

from backend.core import (currency, localtime, seller_mail, secrets_store,
                          store_payments, user_store)

# A seller can bring their own AI keys instead of the platform's shared ones.
# When present, these are preferred; when absent, the app's own keys are used.
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
    }
