"""
Tests for connecting an Instagram account: where the seller is sent, how the
token is stored, and how it is kept alive.

WHY EACH OF THESE EXISTS
  * The authorize URL. Meta shut the Basic Display dialog down in September
    2025. A wrong host here is a dead page for every seller who clicks
    Connect, and nothing in this repo would have noticed.
  * Where the token lives. An Instagram access token is the account — whoever
    holds it posts as the seller. It moved from the account's plain state
    document into the encrypted credential store, and a test is the only thing
    that stops it drifting back.
  * Refresh. Long-lived tokens die at 60 days. A seller with a quiet month
    comes back to a connection that failed with no error, because nothing
    tried to use it. The refresh has to be due BEFORE the expiry, not after.

Run: python scripts/test_instagram_connect.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["CAFEX_DATA_DIR"] = tempfile.mkdtemp(prefix="igtest_")

PASSED = 0
FAILED = 0


def check(label, cond, extra=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
    else:
        FAILED += 1
        print(f"  FAIL: {label}" + (f"  [{extra}]" if extra else ""))


def section(t):
    print(f"\n{t}")


from backend.core import instagram, user_store  # noqa: E402

EMAIL = "seller@shop.test"

section("Where the seller is sent")

os.environ["META_APP_ID"] = "APP123"
os.environ["META_APP_SECRET"] = "shhh"
check("configured once the app id and secret are set", instagram.oauth_configured())

url = instagram.build_login_url("https://shop.test/api/instagram/oauth/callback", "st4te")
u = urlparse(url)
q = parse_qs(u.query)
check("the dialog is on www.instagram.com, not the dead Basic Display host",
      u.netloc == "www.instagram.com", u.netloc)
check("no part of the flow touches facebook.com", "facebook.com" not in url)
check("the app id is sent", q.get("client_id") == ["APP123"])
check("the redirect is sent whole",
      q.get("redirect_uri") == ["https://shop.test/api/instagram/oauth/callback"])
check("state is passed through (CSRF)", q.get("state") == ["st4te"])
check("an authorization code is what we ask for", q.get("response_type") == ["code"])

scopes = (q.get("scope") or [""])[0].split(",")
check("asks to read the account", "instagram_business_basic" in scopes)
check("asks to publish", "instagram_business_content_publish" in scopes)
check("asks for insights — the reason the old flow needed a Facebook Page",
      "instagram_business_manage_insights" in scopes)
check("asks for nothing else — every extra scope is a review rejection",
      len(scopes) == 3, str(scopes))

os.environ["META_APP_ID"] = ""
check("not configured without an app id", not instagram.oauth_configured())
os.environ["META_APP_ID"] = "APP123"

section("The token is encrypted at rest")

instagram.save_credentials(EMAIL, "IGQVJtoken-secret-value", "17841400000000001", "korastudio")
check("it reads back", instagram.get_credentials(EMAIL)["access_token"] == "IGQVJtoken-secret-value")
check("connected", instagram.is_connected(EMAIL))

plain = user_store.get_key(EMAIL, "instagram_creds", {}) or {}
check("the token is NOT in the account's plain state", "access_token" not in plain, str(list(plain)))
check("but the handle is, so the UI can show it", plain.get("account_username") == "korastudio")

blob = str(user_store.get_key(EMAIL, "commerce_connections", {}) or {})
check("and the stored blob does not contain the token in the clear",
      "IGQVJtoken-secret-value" not in blob)

st = instagram.status(EMAIL)
check("status says connected", st["connected"])
check("status never returns the token", "access_token" not in st, str(list(st)))
check("status names the handle", st["account_username"] == "korastudio")
check("status says how long the connection has left",
      st["expires_in_days"] == instagram.TOKEN_TTL_DAYS, str(st["expires_in_days"]))
check("a fresh connection needs no attention", not st["needs_attention"])

section("A token saved by the old version still works")

instagram.clear_credentials(EMAIL)
user_store.set_key(EMAIL, "instagram_creds", {
    "access_token": "OLD-PLAINTEXT-TOKEN", "ig_user_id": "1784100009",
    "account_username": "oldshop", "connected_at": "2026-01-01T00:00:00"})
c = instagram.get_credentials(EMAIL)
check("the old plaintext token is found", c.get("access_token") == "OLD-PLAINTEXT-TOKEN")
check("and the handle survives", c.get("account_username") == "oldshop")
moved = user_store.get_key(EMAIL, "instagram_creds", {}) or {}
check("and it is moved out of plain state on the way past",
      "access_token" not in moved, str(list(moved)))
check("and still reads back after the move",
      instagram.get_credentials(EMAIL)["access_token"] == "OLD-PLAINTEXT-TOKEN")

section("Refreshing before it dies")

instagram.clear_credentials(EMAIL)
check("nothing to refresh when not connected", not instagram.needs_refresh(EMAIL))

instagram.save_credentials(EMAIL, "tok", "1784100001", "korastudio")
check("a token issued today is not due", not instagram.needs_refresh(EMAIL))
age = instagram.token_age_days(EMAIL)
check("its age reads as about zero", age is not None and age < 0.01, str(age))

import pandas as pd  # noqa: E402


def age_the_token(days):
    meta = user_store.get_key(EMAIL, "instagram_creds", {}) or {}
    meta["token_at"] = (pd.Timestamp.now() - pd.Timedelta(days=days)).isoformat(timespec="seconds")
    user_store.set_key(EMAIL, "instagram_creds", meta)


age_the_token(49)
check("at 49 days it is not due yet", not instagram.needs_refresh(EMAIL))
age_the_token(51)
check("at 51 days it is due", instagram.needs_refresh(EMAIL))
check("which is with 9 days still to run, not after it has expired",
      instagram.TOKEN_TTL_DAYS - instagram.REFRESH_AFTER_DAYS >= 7,
      f"{instagram.TOKEN_TTL_DAYS - instagram.REFRESH_AFTER_DAYS} days of slack")

age_the_token(55)
st = instagram.status(EMAIL)
check("status warns when under a week is left", st["needs_attention"], str(st))
check("and says how many days", st["expires_in_days"] == 5, str(st["expires_in_days"]))


class _Resp:
    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


_calls = []


def _fake_get(url, params=None, timeout=None, **kw):
    _calls.append((url, params or {}))
    if url.endswith("/refresh_access_token"):
        return _Resp({"access_token": "NEW-TOKEN", "expires_in": 5184000})
    return _Resp({})


real_get = instagram.requests.get
instagram.requests.get = _fake_get
r = instagram.refresh_token(EMAIL)
check("the refresh succeeds", r.get("ok"), str(r))
check("it uses the ig_refresh_token grant",
      _calls and _calls[-1][1].get("grant_type") == "ig_refresh_token", str(_calls[-1:]))
check("it sends the CURRENT token, not the app secret",
      _calls[-1][1].get("access_token") == "tok" and "client_secret" not in _calls[-1][1])
check("the new token replaces the old one",
      instagram.get_credentials(EMAIL)["access_token"] == "NEW-TOKEN")
check("the clock restarts", not instagram.needs_refresh(EMAIL))
check("and the handle is not lost in the swap",
      instagram.get_credentials(EMAIL).get("account_username") == "korastudio")


def _failing_get(url, params=None, timeout=None, **kw):
    return _Resp({"error": {"message": "Instagram is having a moment"}})


instagram.requests.get = _failing_get
age_the_token(55)
before = instagram.get_credentials(EMAIL)["access_token"]
r2 = instagram.refresh_token(EMAIL)
check("a failed refresh reports why", not r2.get("ok") and "moment" in str(r2.get("error")), str(r2))
check("and does NOT throw away the token that still has days left",
      instagram.get_credentials(EMAIL)["access_token"] == before)
check("and still says connected", instagram.is_connected(EMAIL))

instagram.requests.get = real_get

check("refresh_if_due does nothing when it is not due",
      (instagram.save_credentials(EMAIL, "t2", "1784100001", "korastudio"),
       instagram.refresh_if_due(EMAIL))[1] is None)

section("Disconnecting")

instagram.clear_credentials(EMAIL)
check("no longer connected", not instagram.is_connected(EMAIL))
check("no token remains", not (instagram.get_credentials(EMAIL) or {}).get("access_token"))
check("status agrees", not instagram.status(EMAIL)["connected"])

print(f"\n{PASSED} passed, {FAILED} failed")
sys.exit(1 if FAILED else 0)
