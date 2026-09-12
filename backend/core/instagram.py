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

# Instagram's own OAuth + Graph endpoints (not graph.facebook.com / facebook.com).
#
# THE AUTHORIZE HOST IS www.instagram.com, NOT api.instagram.com. The
# api.instagram.com dialog belonged to the Basic Display API, which Meta shut
# down in September 2025; pointing a seller at it now sends them to a dead
# screen. The token endpoint stayed where it was.
OAUTH_DIALOG = "https://www.instagram.com/oauth/authorize"
OAUTH_TOKEN = "https://api.instagram.com/oauth/access_token"
GRAPH = "https://graph.instagram.com"

# Read the account, publish to it, and read its numbers. `manage_insights` was
# not available on Instagram Login at first, which used to be the one real
# reason to force sellers through a Facebook Page; it is available now, so the
# Page is not needed for anything this app does.
OAUTH_SCOPES = ("instagram_business_basic,"
                "instagram_business_content_publish,"
                "instagram_business_manage_insights")

PUBLISH_SCOPE = "instagram_business_content_publish"

_KEY = "instagram_creds"          # metadata only — never the token
_CONNECTOR = "instagram"          # encrypted credential store

# A long-lived token lasts 60 days and can be refreshed any time after it is
# 24 hours old. Refreshing at 50 days leaves ten days of slack for a seller
# whose shop is shut, or a server that was asleep.
TOKEN_TTL_DAYS = 60
REFRESH_AFTER_DAYS = 50


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
        # WHAT WAS ACTUALLY GRANTED. Scopes are baked into a token when it is
        # issued, and Instagram lets the seller untick permissions on the
        # consent screen. This field is the only place Meta ever tells us which
        # ones survived — the long-lived exchange below does not return it — so
        # if it is not captured here it can never be recovered, and "why will it
        # not post" becomes unanswerable.
        granted = str(d.get("permissions") or "")
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
                    "granted": granted,
                    "warning": "Could not get a long-lived token; using a short-lived one."}
        return {"ok": True, "access_token": d2.get("access_token") or short,
                "user_id": user_id, "granted": granted}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------
# Credentials
# ---------------------------------------------------------
# An Instagram access token IS the account: anyone holding it can post as the
# seller. It is kept encrypted, with the same Fernet key as every other
# third-party credential, and never written into the account's state document
# where a stray debug dump or a Supabase row export would carry it out. Only
# the harmless facts — which handle, when it was connected — live in plain
# state, because the UI reads them on every page.
def get_credentials(email: str) -> dict:
    from backend.core import secrets_store
    creds = dict(secrets_store.get_credentials(email, _CONNECTOR) or {})
    meta = user_store.get_key(email, _KEY, {}) or {}
    # Tokens saved by the version before this one are still in plain state.
    # Read them, so nobody is disconnected by the upgrade, and move them.
    if not creds.get("access_token") and meta.get("access_token"):
        creds = {"access_token": meta["access_token"],
                 "ig_user_id": str(meta.get("ig_user_id") or "")}
        try:
            save_credentials(email, creds["access_token"], creds["ig_user_id"],
                             meta.get("account_username"), meta.get("connected_at"))
        except Exception:  # noqa: BLE001 — reading must not fail on a write problem
            pass
    out = {**meta, **{k: v for k, v in creds.items() if v}}
    out.pop("_legacy", None)
    return out


def save_credentials(email: str, access_token: str, ig_user_id: str,
                     account_username: str | None = None,
                     connected_at: str | None = None,
                     granted: str | None = None) -> dict:
    from backend.core import secrets_store
    token = (access_token or "").strip()
    ig_id = str(ig_user_id or "").strip()
    secrets_store.save_connection(email, _CONNECTOR,
                                  {"access_token": token, "ig_user_id": ig_id},
                                  {"ig_user_id": ig_id})
    prev = user_store.get_key(email, _KEY, {}) or {}
    meta = {
        "ig_user_id": ig_id,
        "account_username": account_username,
        "connected_at": connected_at or _now_iso(),
        "token_at": _now_iso(),          # when THIS token was issued
        "expires_at": _plus_days(TOKEN_TTL_DAYS),
        # A refresh keeps the same grant, so the previous value stands unless a
        # fresh authorization tells us otherwise.
        "granted": (granted if granted is not None else prev.get("granted", "")),
    }
    user_store.set_key(email, _KEY, meta)
    return {**meta, "access_token": token}


def clear_credentials(email: str) -> None:
    from backend.core import secrets_store
    try:
        secrets_store.delete_connection(email, _CONNECTOR)
    except Exception:  # noqa: BLE001
        pass
    user_store.set_key(email, _KEY, {})


# ---------------------------------------------------------
# Keeping the connection alive
# ---------------------------------------------------------
# THE BUG THIS PREVENTS: a long-lived token dies after 60 days. A seller who
# connects Instagram, posts for a month and then has a quiet month comes back
# to an account that is silently disconnected — with no error, because nothing
# tried to post. They conclude the feature does not work.
def token_age_days(email: str) -> float | None:
    meta = user_store.get_key(email, _KEY, {}) or {}
    stamp = meta.get("token_at") or meta.get("connected_at")
    if not stamp:
        return None
    try:
        import pandas as pd
        return float((pd.Timestamp.now() - pd.Timestamp(stamp)).total_seconds() / 86400.0)
    except Exception:  # noqa: BLE001
        return None


def needs_refresh(email: str) -> bool:
    if not is_connected(email):
        return False
    age = token_age_days(email)
    return age is not None and age >= REFRESH_AFTER_DAYS


def refresh_token(email: str) -> dict:
    """Swap a long-lived token for a fresh 60 days. Safe to call any time the
    current token is over 24 hours old; a failure leaves the old one in place,
    because a token with a week left is worth more than no token."""
    creds = get_credentials(email)
    token = creds.get("access_token")
    if not token:
        return {"ok": False, "error": "Instagram is not connected."}
    try:
        r = requests.get(f"{GRAPH}/refresh_access_token",
                         params={"grant_type": "ig_refresh_token", "access_token": token},
                         timeout=15)
        d = _first(r.json())
        if d.get("error") or not d.get("access_token"):
            err = (d.get("error") or {}).get("message") if isinstance(d.get("error"), dict) else d.get("error")
            return {"ok": False, "error": err or "Instagram would not refresh the connection."}
        save_credentials(email, d["access_token"], creds.get("ig_user_id", ""),
                         creds.get("account_username"), creds.get("connected_at"))
        return {"ok": True, "expires_in": d.get("expires_in")}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


def refresh_if_due(email: str) -> dict | None:
    """Called wherever the app already touches Instagram. Cheap when not due."""
    if not needs_refresh(email):
        return None
    return refresh_token(email)


def _plus_days(n: int) -> str:
    import pandas as pd
    return (pd.Timestamp.now() + pd.Timedelta(days=n)).isoformat(timespec="seconds")


def is_connected(email: str) -> bool:
    c = get_credentials(email)
    return bool(c.get("access_token") and c.get("ig_user_id"))


def status(email: str) -> dict:
    """What the UI may show. Never the token."""
    c = get_credentials(email)
    age = token_age_days(email)
    # Rounded, not truncated: a token issued a second ago has 59.99999 days
    # left, and telling a seller "59 days" about a connection they made while
    # looking at the screen reads as a bug.
    days_left = None if age is None else max(0, int(round(TOKEN_TTL_DAYS - age)))
    return {
        "connected": is_connected(email),
        "ig_user_id": c.get("ig_user_id"),
        "account_username": c.get("account_username"),
        "connected_at": c.get("connected_at"),
        "expires_in_days": days_left,
        # Said plainly rather than left for the seller to work out from a date.
        "needs_attention": bool(days_left is not None and days_left <= 7),
        "granted": c.get("granted", ""),
        # None means "connected before we started recording this" — which is
        # not the same as "not granted", and must not be shown as a failure.
        "can_publish": (None if not c.get("granted")
                        else PUBLISH_SCOPE in str(c.get("granted"))),
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


# ---------------------------------------------------------
# Reels, and the check that says whether any of this will work
# ---------------------------------------------------------
# WHY REELS NEEDED THEIR OWN FUNCTION. `post_image` was the only publisher in
# this file, and the entire Social Media Manager is built around reels — the
# research it is based on says single images lost 22% of their reach year on
# year, so the planner deliberately produces reels and carousels. A seller
# could approve a reel, upload the clip, watch it appear on the calendar as
# "scheduled", and nothing would ever happen, because there was no code path
# that could publish a video.
#
# The flow is the same three steps as an image with one difference that
# matters: Instagram TRANSCODES the video, which takes time. A container is
# not publishable the instant it is created — it goes IN_PROGRESS, then
# FINISHED — so this polls, with a budget, instead of publishing optimistically
# and getting a confusing error back.
REEL_MIN_SECONDS = 3
REEL_MAX_SECONDS = 90          # longer is accepted but drops out of the Reels tab
REEL_MAX_BYTES = 100 * 1024 * 1024


def post_video(email: str, video_url: str, caption: str, cover_url: str = "",
               share_to_feed: bool = True, timeout: int = 60,
               poll_seconds: int = 300) -> dict:
    """Publish a reel. Returns {ok, media_id?, permalink?, error?}.

    `video_url` must be reachable over public HTTPS — Meta's servers fetch it
    themselves, there is no upload from here. This app serves media at
    /generated_images/<file> with no authentication, which is exactly what
    makes that work; if that route ever goes behind a login, every reel stops
    publishing and the error will come from Meta rather than from us."""
    creds = get_credentials(email)
    if not (creds.get("access_token") and creds.get("ig_user_id")):
        raise InstagramError("Instagram is not connected. Connect your account first.")
    token, ig_id = creds["access_token"], creds["ig_user_id"]

    payload = {"media_type": "REELS", "video_url": video_url, "caption": caption,
               "share_to_feed": "true" if share_to_feed else "false",
               "access_token": token}
    if cover_url:
        payload["cover_url"] = cover_url
    try:
        r = requests.post(f"{GRAPH}/{ig_id}/media", data=payload, timeout=timeout)
        d = r.json()
        if r.status_code != 200 or d.get("error"):
            return {"ok": False, "step": "create_media",
                    "error": (d.get("error") or {}).get("message") or r.text}
        creation_id = d.get("id")
        if not creation_id:
            return {"ok": False, "step": "create_media", "error": "No creation id returned"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "step": "create_media", "error": str(e)}

    # Transcoding. A 30-second clip is usually ready in under a minute; the
    # budget is generous because the alternative is a post that silently never
    # goes out. Backs off rather than hammering: a tight poll loop against a
    # rate-limited API is its own failure.
    waited, delay = 0, 5
    while waited < poll_seconds:
        time.sleep(delay)
        waited += delay
        delay = min(delay + 5, 20)
        try:
            s = requests.get(f"{GRAPH}/{creation_id}",
                             params={"fields": "status_code,status", "access_token": token},
                             timeout=20).json()
        except Exception:  # noqa: BLE001 — one bad poll is not a failed post
            continue
        code = s.get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            return {"ok": False, "step": "process_media",
                    "error": f"Instagram could not process the video ({code}). "
                             f"{s.get('status') or ''}".strip()}
    else:
        return {"ok": False, "step": "process_media",
                "error": "Instagram is still processing the video after "
                         f"{poll_seconds // 60} minutes. It may still publish — "
                         "check the account before trying again."}

    try:
        r = requests.post(f"{GRAPH}/{ig_id}/media_publish",
                          data={"creation_id": creation_id, "access_token": token},
                          timeout=timeout)
        d = r.json()
        if r.status_code != 200 or d.get("error"):
            return {"ok": False, "step": "publish",
                    "error": (d.get("error") or {}).get("message") or r.text}
        media_id = d.get("id")
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "step": "publish", "error": str(e)}

    permalink = None
    try:
        permalink = requests.get(f"{GRAPH}/{media_id}",
                                 params={"fields": "permalink", "access_token": token},
                                 timeout=15).json().get("permalink")
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "media_id": media_id, "permalink": permalink, "kind": "reel"}


def publish(email: str, kind: str, url: str, caption: str, cover_url: str = "") -> dict:
    """One door for both formats, so callers do not each decide what a reel is."""
    if str(kind or "").lower() in ("reel", "video"):
        return post_video(email, url, caption, cover_url=cover_url)
    return post_image(email, url, caption)


def preflight(email: str, probe_image_url: str) -> dict:
    """Answer "will this actually post?" without posting anything.

    WHY THIS EXISTS: connecting proves the LOGIN worked. It does not prove
    publishing will, and the three things that break publishing all fail
    silently until a real post is due at 7pm on a Saturday:

      * the seller unticked "publish content" on Instagram's permission screen
        (it is a checkbox, and people untick things they do not understand);
      * this server is not reachable from the public internet, so Meta cannot
        fetch the picture it is being asked to post;
      * the account is not eligible to publish through the API.

    Creating a media container exercises every one of those — Meta validates
    the token's scope AND fetches the image before it answers — and a container
    that is never published simply expires in 24 hours. So this is a real
    end-to-end test that leaves nothing on the seller's profile."""
    out = {"connected": False, "token_ok": False, "can_publish": False,
           "media_reachable": False, "error": "", "hint": "", "username": ""}
    creds = get_credentials(email)
    if not (creds.get("access_token") and creds.get("ig_user_id")):
        out["error"] = "Instagram is not connected."
        return out
    out["connected"] = True
    token, ig_id = creds["access_token"], creds["ig_user_id"]

    check = test_connection(token, ig_id)
    if not check.get("ok"):
        out["error"] = check.get("error", "The saved connection no longer works.")
        out["hint"] = "Disconnect and connect again — the access token has expired or been revoked."
        return out
    out["token_ok"] = True
    out["username"] = check.get("username", "")

    # What the seller actually granted, if we recorded it. Cheapest possible
    # answer and it needs no network call at all.
    meta = user_store.get_key(email, _KEY, {}) or {}
    grant = str(meta.get("granted") or "")
    if grant and PUBLISH_SCOPE not in grant:
        out["error"] = ("Permission to publish was not granted when this account "
                        "was connected.")
        out["hint"] = ("Disconnect below and connect again — and on Instagram's "
                       "permission screen leave every box ticked. Permissions are "
                       "fixed at the moment you connect, so they cannot be added "
                       "afterwards.")
        return out

    # The quota endpoint is part of the publishing surface, so it answers the
    # scope question without creating anything. A token missing the publish
    # permission gets an error here; one that has it gets a quota. This is the
    # cheap half of the test, and it separates "no permission" from "cannot
    # fetch the picture" — two problems with completely different fixes.
    try:
        q = requests.get(f"{GRAPH}/{ig_id}/content_publishing_limit",
                         params={"fields": "config,quota_usage", "access_token": token},
                         timeout=20).json()
        if (q.get("error") or {}).get("message"):
            msg = q["error"]["message"]
            out["error"] = msg
            out["hint"] = ("Instagram did not grant permission to publish. Disconnect "
                           "below, connect again, and keep every box ticked on "
                           "Instagram's permission screen. If it still fails, check "
                           "the account has accepted the tester invite at "
                           "instagram.com on a desktop browser.")
            return out
        usage = ((q.get("data") or [{}])[0] or {}).get("quota_usage")
        if usage is not None:
            out["quota_used"] = usage
        out["scope_ok"] = True
    except Exception:  # noqa: BLE001 — fall through to the real container test
        pass

    try:
        r = requests.post(f"{GRAPH}/{ig_id}/media",
                          data={"image_url": probe_image_url,
                                "caption": "", "access_token": token}, timeout=45)
        d = r.json()
    except Exception as e:  # noqa: BLE001
        out["error"] = f"Could not reach Instagram: {e}"
        return out

    if r.status_code == 200 and d.get("id"):
        # Deliberately NOT published. It expires by itself in 24 hours.
        out["can_publish"] = True
        out["media_reachable"] = True
        return out

    err = (d.get("error") or {})
    msg = err.get("message") or r.text
    out["error"] = err.get("error_user_msg") or msg
    sub = err.get("error_subcode")
    low = str(msg).lower()

    # Meta answers media problems with a number, not a sentence. These are the
    # ones that actually happen, each with the thing to change.
    SUBCODES = {
        2207052: "Instagram could not download the picture from this server. It has to be reachable on the public internet, over https, with no login and no bot protection in front of it.",
        2207003: "Instagram timed out downloading the picture. The server may be asleep — open the app once and try again.",
        2207005: "Instagram refused the image format. It accepts JPEG only, never PNG.",
        2207004: "The picture is larger than Instagram's 8 MB limit.",
        2207009: "The picture's shape is outside what Instagram accepts — it must be between 4:5 (tall) and 1.91:1 (wide).",
        36001: "The picture's resolution is outside what Instagram accepts.",
        2207042: "This account has hit Instagram's limit of 100 posts in 24 hours.",
        2207050: "Instagram has restricted this account. Open the Instagram app and clear anything it is asking for.",
        2207051: "Instagram blocked the request as suspected spam.",
    }
    if sub in SUBCODES:
        out["media_reachable"] = sub not in (2207052, 2207003)
        out["hint"] = SUBCODES[sub]
        return out
    # Meta's wording is not written for shop owners. Say what to do instead.
    if "permission" in low or "scope" in low or err.get("code") == 200:
        out["hint"] = ("Instagram did not grant permission to publish. Disconnect "
                       "below, connect again, and make sure every box on "
                       "Instagram's permission screen stays ticked.")
    elif "media" in low and ("fetch" in low or "download" in low or "url" in low):
        out["media_reachable"] = False
        out["hint"] = ("Instagram could not download the picture from this server. "
                       "It has to be reachable on the public internet over HTTPS — "
                       "check the app's address is public and not behind a password.")
    elif "not a business" in low or "professional" in low:
        out["hint"] = ("This Instagram account is not a Business or Creator "
                       "account. Instagram app → Settings → Account type and "
                       "tools → Switch to professional account.")
    else:
        out["hint"] = "Instagram refused the test. The message above is theirs, not ours."
    return out
