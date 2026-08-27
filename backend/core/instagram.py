"""
Instagram Graph API integration — REAL, not a mock.

Uses Meta's **"Instagram API with Instagram Login"** (aka Business Login for
Instagram), NOT the older Facebook Login for Business flow. The difference
matters: this flow does NOT require the seller to have (or link) a Facebook
Page — they just need their Instagram account switched to Business or
Creator in the Instagram app. Login happens directly against Instagram's own
OAuth endpoints (api.instagram.com), not facebook.com.

The seller connects by clicking "Connect Instagram" in Smart mode, which
sends them to Instagram's OAuth screen. On approval we exchange the code for
a short-lived token, then a 60-day long-lived token, and Instagram's own
token-exchange response already tells us their numeric user id — no separate
"find my Facebook Pages" step needed.

Posting an image is a two-step Graph API dance:
  1. POST /{ig-user-id}/media          with image_url + caption -> creation_id
  2. POST /{ig-user-id}/media_publish  with creation_id         -> media_id

The image MUST be publicly reachable over HTTPS for Meta to fetch it — the
content generator saves generated images under /generated_images/... so this
backend can serve them via a public URL.

Meta app dashboard setup (once, by the platform admin — not per seller):
  1. Add the "Instagram" product to the app (NOT "Facebook Login").
  2. Business Login for Instagram > Settings > add the OAuth redirect URI:
       https://<your-domain>/api/instagram/oauth/callback
  3. Set env vars META_APP_ID / META_APP_SECRET to this app's Instagram App ID/Secret
     (shown on the Instagram product's setup page — may differ from the
     Facebook App ID shown in Settings > Basic).
  4. App Review is still required to publish for real (non-tester) sellers —
     request instagram_business_basic + instagram_business_content_publish.

Docs: https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login
"""
from __future__ import annotations

import time
from typing import Any

import requests

from backend.core import user_store

# Instagram's own OAuth + Graph endpoints (not graph.facebook.com / facebook.com)
OAUTH_DIALOG = "https://api.instagram.com/oauth/authorize"
OAUTH_TOKEN = "https://api.instagram.com/oauth/access_token"
GRAPH = "https://graph.instagram.com"

# The two scopes needed to read the account + publish content. Instagram
# Login introduced these `instagram_business_*` scope names, replacing the
# old `instagram_content_publish` used by the Facebook Login flow.
OAUTH_SCOPES = "instagram_business_basic,instagram_business_content_publish"

_KEY = "instagram_creds"


# ---------------------------------------------------------
# OAuth helpers
# ---------------------------------------------------------
def oauth_configured() -> bool:
    """True when the platform admin has set the Meta app env vars — then the
    OAuth flow is available. Otherwise the UI falls back to paste-token."""
    import os
    return bool(os.environ.get("META_APP_ID") and os.environ.get("META_APP_SECRET"))


def oauth_config() -> dict:
    import os
    return {
        "app_id": os.environ.get("META_APP_ID", ""),
        "app_secret": os.environ.get("META_APP_SECRET", ""),
        # if unset, main.py derives it from the incoming request
        "redirect_url": os.environ.get("META_REDIRECT_URL", ""),
    }


def build_login_url(redirect_url: str, state: str) -> str:
    import os
    from urllib.parse import urlencode
    q = urlencode({
        "client_id": os.environ.get("META_APP_ID", ""),
        "redirect_uri": redirect_url,
        "scope": OAUTH_SCOPES,
        "response_type": "code",
        "state": state,
    })
    return f"{OAUTH_DIALOG}?{q}"


def _first(data: Any) -> dict:
    """Instagram's OAuth endpoints have, at various times, returned either a
    plain object or a one-item list — normalize to a dict defensively."""
    if isinstance(data, list):
        return data[0] if data else {}
    return data or {}


def exchange_code(code: str, redirect_url: str) -> dict:
    """Trade the ?code= from Instagram's callback for a short-lived user
    token (Instagram's response also includes the numeric user_id — no
    separate Facebook Pages lookup needed), then swap for a 60-day
    long-lived token. Returns {ok, access_token?, user_id?, error?}."""
    cfg = oauth_config()
    try:
        r = requests.post(OAUTH_TOKEN, data={
            "client_id": cfg["app_id"], "client_secret": cfg["app_secret"],
            "grant_type": "authorization_code",
            "redirect_uri": redirect_url, "code": code,
        }, timeout=15)
        d = _first(r.json())
        if d.get("error_type") or d.get("error"):
            return {"ok": False, "error": d.get("error_message") or d.get("error_type")
                                          or str(d.get("error"))}
        short = d.get("access_token")
        user_id = d.get("user_id")
        if not short:
            return {"ok": False, "error": "Instagram returned no short-lived token."}

        # exchange for long-lived (60 day) token
        r2 = requests.get(f"{GRAPH}/access_token", params={
            "grant_type": "ig_exchange_token",
            "client_secret": cfg["app_secret"], "access_token": short,
        }, timeout=15)
        d2 = _first(r2.json())
        if d2.get("error"):
            # long-lived exchange failing shouldn't block the connection —
            # fall back to the short-lived token (still works for ~1 hour,
            # better than erroring the whole flow out).
            return {"ok": True, "access_token": short, "user_id": user_id,
                    "warning": "Could not get a long-lived token; using a short-lived one."}
        return {"ok": True, "access_token": d2.get("access_token") or short, "user_id": user_id}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------
# Credentials
# ---------------------------------------------------------
def get_credentials(email: str) -> dict:
    return user_store.get_key(email, _KEY, {}) or {}


def save_credentials(email: str, access_token: str, ig_user_id: str,
                     account_username: str | None = None) -> dict:
    creds = {
        "access_token": access_token.strip(),
        "ig_user_id": str(ig_user_id).strip(),
        "account_username": account_username,
        "connected_at": _now_iso(),
    }
    user_store.set_key(email, _KEY, creds)
    return creds


def clear_credentials(email: str) -> None:
    user_store.set_key(email, _KEY, {})


def is_connected(email: str) -> bool:
    c = get_credentials(email)
    return bool(c.get("access_token") and c.get("ig_user_id"))


def status(email: str) -> dict:
    c = get_credentials(email)
    return {
        "connected": is_connected(email),
        "ig_user_id": c.get("ig_user_id"),
        "account_username": c.get("account_username"),
        "connected_at": c.get("connected_at"),
    }


# ---------------------------------------------------------
# Graph API calls
# ---------------------------------------------------------
class InstagramError(Exception):
    pass


def test_connection(access_token: str, ig_user_id: str) -> dict:
    """Ping the account so the frontend can show a real-time "OK" or the
    error Meta returns. Returns {ok, username?, error?}."""
    try:
        r = requests.get(f"{GRAPH}/{ig_user_id}",
                         params={"fields": "id,username,name", "access_token": access_token},
                         timeout=15)
        data = r.json()
        if r.status_code != 200 or data.get("error"):
            err = (data.get("error") or {}).get("message") or r.text
            return {"ok": False, "error": err}
        return {"ok": True, "id": data.get("id"), "username": data.get("username"),
                "name": data.get("name")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def post_image(email: str, image_url: str, caption: str, timeout: int = 60) -> dict:
    """Publish a single-image post to the connected Instagram Business
    account. Returns {ok, media_id?, permalink?, error?}."""
    creds = get_credentials(email)
    if not (creds.get("access_token") and creds.get("ig_user_id")):
        raise InstagramError("Instagram is not connected. Connect your account first.")
    token = creds["access_token"]
    ig_id = creds["ig_user_id"]

    # 1) create container
    try:
        r = requests.post(f"{GRAPH}/{ig_id}/media",
                          data={"image_url": image_url, "caption": caption,
                                "access_token": token}, timeout=timeout)
        d = r.json()
        if r.status_code != 200 or d.get("error"):
            err = (d.get("error") or {}).get("message") or r.text
            return {"ok": False, "step": "create_media", "error": err}
        creation_id = d.get("id")
        if not creation_id:
            return {"ok": False, "step": "create_media", "error": "No creation id returned"}
    except Exception as e:
        return {"ok": False, "step": "create_media", "error": str(e)}

    # 2) some large images take a few seconds to process. Poll status briefly.
    for _ in range(6):
        try:
            s = requests.get(f"{GRAPH}/{creation_id}",
                             params={"fields": "status_code", "access_token": token},
                             timeout=15).json()
            if s.get("status_code") == "FINISHED":
                break
            if s.get("status_code") in ("ERROR", "EXPIRED"):
                return {"ok": False, "step": "process_media",
                        "error": f"Media processing failed: {s.get('status_code')}"}
        except Exception:
            pass
        time.sleep(2)

    # 3) publish
    try:
        r = requests.post(f"{GRAPH}/{ig_id}/media_publish",
                          data={"creation_id": creation_id, "access_token": token},
                          timeout=timeout)
        d = r.json()
        if r.status_code != 200 or d.get("error"):
            err = (d.get("error") or {}).get("message") or r.text
            return {"ok": False, "step": "publish", "error": err}
        media_id = d.get("id")
    except Exception as e:
        return {"ok": False, "step": "publish", "error": str(e)}

    # 4) permalink (nice to show back)
    permalink = None
    try:
        r = requests.get(f"{GRAPH}/{media_id}",
                         params={"fields": "permalink,timestamp", "access_token": token},
                         timeout=15).json()
        permalink = r.get("permalink")
    except Exception:
        pass

    return {"ok": True, "media_id": media_id, "permalink": permalink}


def _now_iso() -> str:
    import pandas as pd
    return pd.Timestamp.now().isoformat(timespec="seconds")
