"""
Sign in with Google.

WHY THIS EXISTS
---------------
A seller who has just found this app is asked, before they see anything, to
invent a password and remember it. Most of them reuse one they already use
elsewhere, some of them never come back, and every one of them becomes a
password we now have to store, reset and defend. "Continue with Google" removes
all three problems for the majority of Indian D2C sellers, who are on Gmail
already.

The password login stays. Google is an additional door, not a replacement —
an account that can only be reached through a third party is an account the
seller loses when that third party decides they are a bot.

HOW THE TOKEN IS CHECKED
  The browser gets a signed JWT (an "ID token") from Google and posts it here.
  Verifying it is local: Google publishes its signing keys, we check the
  signature against them and then check the claims. There is no call to Google
  on the login path, so a Google outage does not become our outage beyond the
  button itself.

  Verified here, in this order:
    * header alg is RS256 and names a key id we can find (never "none", never
      an algorithm the token itself gets to choose from a wider set);
    * signature against that key;
    * `iss` is Google;
    * `aud` is OUR client id. THIS IS THE ONE THAT MATTERS. A token minted for
      any other Google app is a perfectly valid Google-signed JWT — without
      this check, anyone running any Google OAuth app can sign in as anyone;
    * `exp` / `iat` within a small clock skew;
    * `email_verified` is true;
    * `nonce` matches the one we issued, if we issued one.

  NO DEPENDENCY on google-auth, deliberately: the check is a signature and six
  comparisons, all of which `cryptography` already does, and a login path is a
  bad place to add a library that cannot be exercised by this repo's tests.

ACCOUNT LINKING, AND THE ATTACK IT AVOIDS
  See `link_policy()`. The short version: an existing local account is only
  joined to a Google identity when BOTH sides are verified. Joining on a
  matching email alone is pre-account hijacking — an attacker registers
  victim@gmail.com with a password they choose, waits, and inherits the account
  the moment the real owner signs in with Google. That is CVE-2026-53516, and
  it is the default behaviour of a surprising amount of shipped code.
"""
from __future__ import annotations

import base64
import json
import os
import threading
import time

from backend.core import user_store

ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
CLOCK_SKEW = 60           # seconds, both directions
_CERTS_TTL = 3600         # Google rotates slowly; an hour is conservative

IDENTITY_KEY = "google_identity"


def client_id() -> str:
    return (os.environ.get("GOOGLE_CLIENT_ID") or "").strip()


def configured() -> bool:
    """Whether the button should be shown at all."""
    return bool(client_id())


# ---------------------------------------------------------------- key cache --
_certs_lock = threading.Lock()
_certs: dict = {"at": 0.0, "keys": {}}


def _fetch_certs() -> dict:
    import requests
    r = requests.get(CERTS_URL, timeout=8)
    r.raise_for_status()
    keys = {}
    for k in (r.json() or {}).get("keys", []):
        if k.get("kty") == "RSA" and k.get("kid"):
            keys[k["kid"]] = k
    return keys


def _public_key(kid: str):
    """Google's signing key for `kid`, refetching once if it is unknown.

    A key id we have never seen is the normal signal that Google rotated, so it
    forces one refresh — but only one, or an attacker could make us hammer
    Google by sending tokens with random kids."""
    global _certs
    with _certs_lock:
        fresh = time.time() - _certs["at"] < _CERTS_TTL
        keys = _certs["keys"]
        if not fresh or kid not in keys:
            try:
                keys = _fetch_certs()
                _certs = {"at": time.time(), "keys": keys}
            except Exception as e:  # noqa: BLE001
                if not keys:
                    raise ValueError(f"Could not reach Google to check the sign-in: {e}")
        jwk = keys.get(kid)
    if not jwk:
        raise ValueError("Google signed this with a key we do not recognise.")

    from cryptography.hazmat.primitives.asymmetric import rsa
    n = int.from_bytes(_b64(jwk["n"]), "big")
    e = int.from_bytes(_b64(jwk["e"]), "big")
    return rsa.RSAPublicNumbers(e, n).public_key()


def _b64(s: str) -> bytes:
    """base64url without padding, as every JWT field is written."""
    s = str(s or "")
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


# ------------------------------------------------------------- verification --
def verify(credential: str, nonce: str = "") -> dict:
    """Return the claims of a valid Google ID token, or raise ValueError."""
    if not configured():
        raise ValueError("Google sign-in is not set up on this server.")
    parts = str(credential or "").split(".")
    if len(parts) != 3:
        raise ValueError("That is not a Google sign-in token.")
    head_b, body_b, sig_b = parts

    try:
        header = json.loads(_b64(head_b))
        claims = json.loads(_b64(body_b))
        signature = _b64(sig_b)
    except Exception:  # noqa: BLE001
        raise ValueError("That sign-in token is malformed.")

    # The token does not get to pick the algorithm. "none" and the HMAC family
    # are how JWT verification is bypassed; only RS256 is accepted.
    if header.get("alg") != "RS256":
        raise ValueError("Unexpected signing algorithm.")

    key = _public_key(header.get("kid", ""))
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    try:
        key.verify(signature, f"{head_b}.{body_b}".encode(),
                   padding.PKCS1v15(), hashes.SHA256())
    except InvalidSignature:
        raise ValueError("That sign-in could not be verified.")

    if claims.get("iss") not in ISSUERS:
        raise ValueError("That token did not come from Google.")

    # aud may be a single value; Google sends a string. Compared exactly.
    if claims.get("aud") != client_id():
        raise ValueError("That sign-in was issued for a different app.")

    now = time.time()
    try:
        exp = float(claims.get("exp", 0))
        iat = float(claims.get("iat", 0))
    except (TypeError, ValueError):
        raise ValueError("That sign-in token has no valid timestamps.")
    if exp < now - CLOCK_SKEW:
        raise ValueError("That sign-in has expired. Please try again.")
    if iat > now + CLOCK_SKEW:
        raise ValueError("That sign-in is dated in the future.")

    if not claims.get("email"):
        raise ValueError("Google did not share an email address.")
    # Consumer Gmail is always verified; Workspace accounts need not be, and an
    # unverified address is exactly what makes linking unsafe.
    if not claims.get("email_verified"):
        raise ValueError("Google has not verified that email address.")

    if nonce and claims.get("nonce") != nonce:
        raise ValueError("That sign-in does not match this browser's request.")

    return {"sub": str(claims.get("sub") or ""),
            "email": str(claims["email"]).strip().lower(),
            "name": str(claims.get("name") or "").strip(),
            "picture": str(claims.get("picture") or "").strip()}


# ------------------------------------------------------------------ linking --
def link_policy(google_email: str, existing_password_hash: str | None,
                existing_is_google: bool) -> str:
    """What may be done with a verified Google identity. One of:

        "sign_in"  the account is already this Google identity's
        "link"     safe to attach: the local account proves the same owner
        "create"   no such account here yet
        "verify"   an account exists that we CANNOT prove belongs to this
                   person, so make them prove it with their password first

    The "verify" branch is the whole point. An account created by password
    signup is not proof that whoever created it owns the mailbox — anyone can
    type any address into a signup form. Attaching a Google identity to it
    because the strings match hands the attacker's account to the victim, and
    the attacker keeps the password.
    """
    if existing_is_google:
        return "sign_in"
    if existing_password_hash is None:
        return "create"
    return "verify"


def identity(email: str) -> dict:
    return user_store.get_key(email, IDENTITY_KEY, {}) or {}


def remember(email: str, claims: dict) -> None:
    """Record which Google account this is, keyed on `sub`.

    `sub` and not the email address: Google says the email on an account can
    change and `sub` cannot, so an address is a lookup hint and `sub` is the
    identity."""
    user_store.set_key(email, IDENTITY_KEY, {
        "provider": "google",
        "sub": claims.get("sub", ""),
        "email": claims.get("email", ""),
        "name": claims.get("name", ""),
        "linked_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
    })


def forget(email: str) -> None:
    user_store.set_key(email, IDENTITY_KEY, {})
