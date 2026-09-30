"""
Sign in with ChatGPT, and (when the seller allows it) their ChatGPT plan.

WHAT OPENAI OFFERS
------------------
Read from developers.openai.com/siwc on 30 September 2026:

  * Identity. OAuth 2.0 Authorization Code with PKCE and OpenID Connect against
    auth.openai.com. We receive a stable account id (`sub`), the name, the email
    address and the profile picture. Nothing else: no conversations, no memory,
    no billing details, no API key.
  * ChatGPT plan usage. Three more scopes (offline_access resource.invoke
    chatgpt.tokens.use.direct) and resource=https://api.openai.com/v1. When the
    seller grants them, the token response carries an access token that
    POST /v1/responses accepts in place of an API key, and the request counts
    against the usage included in THEIR ChatGPT Plus or Pro plan. That half
    lives in chatgpt_plan.py; this module only gets, keeps and renews the token.

WHAT IT NEEDS BEFORE IT RUNS
----------------------------
A client ID from OpenAI. For a paid, hosted app like this one that comes from
OpenAI's partner programme (openai.com/form/sign-in-with-chatgpt-interest), not
from a self-serve dashboard. Until CHATGPT_CLIENT_ID is set, configured() is
False: no button is drawn, no route does anything, and every AI call behaves
exactly as it did before this file existed.

  CHATGPT_CLIENT_ID        the client ID OpenAI issues (it starts with oaiapp_)
  CHATGPT_CLIENT_SECRET    only for a confidential client; sent as HTTP Basic
  CHATGPT_REDIRECT_URI     the exact callback registered with OpenAI, e.g.
                           https://onetapmanager.com/api/auth/chatgpt/callback
  CHATGPT_PLAN_USAGE       "on" (default) also asks for the plan scopes; "off"
                           is sign-in only, for a client approved for identity
  CHATGPT_FORCE_RECONSENT  "on" once OpenAI confirms force_reconsent for this
                           client; until then a re-ask uses prompt=consent

THE SECURITY RULES, AND WHERE EACH ONE IS KEPT
----------------------------------------------
  * state, nonce and the PKCE verifier are new for every attempt, held on the
    server, tied to this browser by an HttpOnly cookie, used once, and dead
    after ten minutes (begin / consume).
  * The code is exchanged here, on the server. No OpenAI code, token or verifier
    is ever handed to browser JavaScript.
  * The ID token is checked locally (verify_id_token): RS256 only, the signature
    against OpenAI's published keys, `iss` exactly the discovery issuer, `aud`
    our client ID, `exp` and `iat` within a minute, and `nonce` equal to the one
    this attempt sent.
  * Tokens are kept encrypted in secrets_store, never in the state document,
    never in a URL and never in a log line.
  * Linking follows the Google rules (google_auth.link_policy): an account made
    with a password is only joined to a ChatGPT identity once that password has
    been typed. An email match alone is how accounts get stolen.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
import time
import urllib.parse
from datetime import datetime, timezone

from backend.core import db, secrets_store, user_store

log = logging.getLogger("chatgpt_auth")

ISSUER_DEFAULT = "https://auth.openai.com"
# The resource the plan scopes are granted for, and the audience of the access
# token. It is also where chatgpt_plan.py sends the requests.
RESOURCE = "https://api.openai.com/v1"
IDENTITY_SCOPES = ("openid", "profile", "email")
PLAN_SCOPES = ("offline_access", "resource.invoke", "chatgpt.tokens.use.direct")
# The one scope that actually means "this app may spend my plan". A valid ID
# token without it is a sign-in and nothing more.
PLAN_SCOPE = "chatgpt.tokens.use.direct"

# Where a seller sees and changes what this app may use, when it resets, and
# whether apps may carry on with ChatGPT credits. OpenAI asks integrations to
# link here rather than to guess at any of it themselves.
MANAGE_USAGE_URL = "https://chatgpt.com/settings/usage"
# OpenAI's own explanation of using a ChatGPT plan in other apps.
HELP_URL = "https://help.openai.com/articles/20001542"

CONNECTOR = "chatgpt"               # secrets_store connection: the encrypted tokens
IDENTITY_KEY = "chatgpt_identity"   # user_store key: WHO the ChatGPT account is

CLOCK_SKEW = 60                     # seconds, both directions, as google_auth
TX_TTL = 600                        # an unfinished sign-in dies after ten minutes
TICKET_TTL = 180                    # the hand-off from callback to browser
REFRESH_MARGIN = 120                # renew an access token with two minutes left
_HTTP_TIMEOUT = 15

# Refresh failures that mean the renewable session is gone for good, from
# OpenAI's "Errors and recovery" page. Anything else is treated as a blip.
TERMINAL_REFRESH_ERRORS = {"invalid_grant", "invalid_refresh_token", "token_expired",
                           "refresh_token_expired", "refresh_token_invalidated",
                           "refresh_token_reused", "no_refresh_token"}


class SiwcError(ValueError):
    """A sign-in problem the seller can be told about. `code` is the short
    machine-readable reason the browser uses to pick its wording."""

    def __init__(self, message: str, code: str = "failed"):
        super().__init__(message)
        self.code = code


class TokenError(RuntimeError):
    """The token endpoint refused, or could not be reached. Carries the OAuth
    error code, never the token."""

    def __init__(self, code: str, detail: str = "", status: int = 0,
                 request_id: str = "", temporary: bool = False):
        super().__init__(f"{code}{': ' + detail if detail else ''}")
        self.code = code
        self.detail = detail
        self.status = status
        self.request_id = request_id
        self.temporary = temporary


# ---------------------------------------------------------------- config ----
def client_id() -> str:
    return (os.environ.get("CHATGPT_CLIENT_ID") or "").strip()


def client_secret() -> str:
    return (os.environ.get("CHATGPT_CLIENT_SECRET") or "").strip()


def configured() -> bool:
    """Whether the button should exist at all."""
    return bool(client_id())


def _flag(name: str, default: bool) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw not in ("0", "off", "false", "no")


def plan_usage_offered() -> bool:
    """Whether this server asks sellers to use their ChatGPT plan here.

    On by default, because using the seller's own plan is the reason this
    exists. A client ID that OpenAI approved for sign-in only must turn it off,
    or the authorization request asks for scopes the client may not have."""
    return configured() and _flag("CHATGPT_PLAN_USAGE", True)


def issuer() -> str:
    return (os.environ.get("CHATGPT_ISSUER") or ISSUER_DEFAULT).strip().rstrip("/")


def redirect_uri(base_url: str) -> str:
    """The callback OpenAI sends the browser back to. It has to match the one
    registered for the client EXACTLY, so production should pin it with
    CHATGPT_REDIRECT_URI rather than trust the request's own host."""
    fixed = (os.environ.get("CHATGPT_REDIRECT_URI") or "").strip()
    return fixed or f"{(base_url or '').rstrip('/')}/api/auth/chatgpt/callback"


def scopes() -> list[str]:
    out = list(IDENTITY_SCOPES)
    if plan_usage_offered():
        out += list(PLAN_SCOPES)
    return out


# ------------------------------------------------------------- discovery ----
# The production values OpenAI publishes, used only if the discovery document
# cannot be fetched, and only for the production issuer.
_DEFAULT_ENDPOINTS = {
    "issuer": ISSUER_DEFAULT,
    "authorization_endpoint": "https://auth.openai.com/api/accounts/authorize",
    "token_endpoint": "https://auth.openai.com/api/accounts/oauth/token",
    "jwks_uri": "https://auth.openai.com/.well-known/jwks.json",
    "revocation_endpoint": "https://auth.openai.com/api/accounts/oauth/revoke",
}
_DISC_TTL = 3600
_disc_lock = threading.Lock()
_disc: dict = {"at": 0.0, "ttl": _DISC_TTL, "doc": None}


def discovery() -> dict:
    """OpenAI's OpenID Connect discovery document, cached for an hour."""
    with _disc_lock:
        if _disc["doc"] and time.time() - _disc["at"] < _disc["ttl"]:
            return _disc["doc"]
    ttl = _DISC_TTL
    try:
        import requests
        r = requests.get(f"{issuer()}/.well-known/openid-configuration", timeout=8)
        r.raise_for_status()
        got = r.json() or {}
        # OpenID Connect Discovery section 4.3: the issuer a document names must
        # be the one it was fetched for, or the document is not to be used.
        if str(got.get("issuer") or "").rstrip("/") != issuer():
            raise ValueError("the discovery document names a different issuer")
        doc = {k: str(got.get(k) or "") for k in _DEFAULT_ENDPOINTS}
        doc["issuer"] = str(got["issuer"])      # verbatim, for the exact iss check
        for k in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
            if not doc[k].startswith("https://"):
                raise ValueError(f"the discovery document has no usable {k}")
    except Exception as e:  # noqa: BLE001
        if issuer() != ISSUER_DEFAULT:
            raise SiwcError("Could not reach the ChatGPT sign-in service. Try again "
                            "in a minute.", code="unavailable") from e
        log.warning("OpenAI discovery failed, using the published endpoints: %s", e)
        doc = dict(_DEFAULT_ENDPOINTS)
        ttl = 300                               # try the real document again soon
    with _disc_lock:
        _disc.update(at=time.time(), ttl=ttl, doc=doc)
    return doc


# ------------------------------------------------------------------ keys ----
_JWKS_TTL = 3600
_jwks_lock = threading.Lock()
_jwks: dict = {"at": 0.0, "tried": 0.0, "keys": {}}


def _b64(s: str) -> bytes:
    """base64url without padding, as every JWT field is written."""
    s = str(s or "")
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _fetch_jwks() -> dict:
    import requests
    r = requests.get(discovery()["jwks_uri"], timeout=8)
    r.raise_for_status()
    keys = {}
    for k in (r.json() or {}).get("keys", []):
        if k.get("kty") == "RSA" and k.get("kid") and k.get("use", "sig") == "sig":
            keys[k["kid"]] = k
    return keys


def _public_key(kid: str):
    """OpenAI's signing key for `kid`.

    An unknown key id is the normal sign that OpenAI rotated, so it forces a
    refetch, but at most once a minute: a stream of tokens with made-up key ids
    must not turn into a stream of requests to OpenAI."""
    global _jwks
    with _jwks_lock:
        keys = _jwks["keys"]
        stale = time.time() - _jwks["at"] >= _JWKS_TTL
        if (stale or kid not in keys) and (not keys or stale
                                           or time.time() - _jwks["tried"] > 60):
            try:
                keys = _fetch_jwks()
                _jwks = {"at": time.time(), "tried": time.time(), "keys": keys}
            except Exception as e:  # noqa: BLE001
                _jwks["tried"] = time.time()
                if not keys:
                    raise SiwcError("Could not reach OpenAI to check the sign-in. "
                                    "Try again in a minute.", code="unavailable") from e
        jwk = keys.get(kid)
    if not jwk:
        raise SiwcError("That sign-in was signed with a key OpenAI does not list.",
                        code="invalid_token")
    from cryptography.hazmat.primitives.asymmetric import rsa
    n = int.from_bytes(_b64(jwk["n"]), "big")
    e = int.from_bytes(_b64(jwk["e"]), "big")
    return rsa.RSAPublicNumbers(e, n).public_key()


def _jwt_payload_unverified(token: str) -> dict:
    """The claims of a JWT WITHOUT checking it. Only ever used to read the
    `scope` of our own access token when the token response left it out: it
    decides what we try, and OpenAI still decides what is allowed."""
    try:
        return json.loads(_b64(str(token or "").split(".")[1]))
    except Exception:  # noqa: BLE001
        return {}


def verify_id_token(id_token: str, nonce: str) -> dict:
    """The verified identity in an OpenAI ID token, or SiwcError."""
    if not configured():
        raise SiwcError("Sign in with ChatGPT is not set up on this server.",
                        code="not_configured")
    parts = str(id_token or "").split(".")
    if len(parts) != 3:
        raise SiwcError("OpenAI did not send back a valid sign-in.", code="invalid_token")
    head_b, body_b, sig_b = parts
    try:
        header = json.loads(_b64(head_b))
        claims = json.loads(_b64(body_b))
        signature = _b64(sig_b)
    except Exception:  # noqa: BLE001
        raise SiwcError("That sign-in token is malformed.", code="invalid_token")

    # The token does not get to choose how it is checked. OpenAI signs ID
    # tokens with RS256 only (its discovery document says so), and "none" or an
    # HMAC algorithm is how JWT verification gets bypassed.
    if header.get("alg") != "RS256":
        raise SiwcError("That sign-in used an unexpected signing algorithm.",
                        code="invalid_token")
    key = _public_key(str(header.get("kid") or ""))
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    try:
        key.verify(signature, f"{head_b}.{body_b}".encode("ascii"),
                   padding.PKCS1v15(), hashes.SHA256())
    except InvalidSignature:
        raise SiwcError("That sign-in could not be verified.", code="invalid_token")

    if claims.get("iss") != discovery()["issuer"]:
        raise SiwcError("That sign-in did not come from OpenAI.", code="invalid_token")

    # THE CHECK THAT MATTERS. A token minted for any other OpenAI app is a
    # perfectly valid OpenAI-signed JWT; only the audience says it is ours.
    aud = claims.get("aud")
    auds = aud if isinstance(aud, list) else [aud]
    if client_id() not in auds:
        raise SiwcError("That sign-in was issued for a different app.", code="invalid_token")
    if isinstance(aud, list) and len(aud) > 1 and claims.get("azp") != client_id():
        raise SiwcError("That sign-in was issued for a different app.", code="invalid_token")

    now = time.time()
    try:
        exp = float(claims.get("exp"))
        iat = float(claims.get("iat"))
    except (TypeError, ValueError):
        raise SiwcError("That sign-in has no valid timestamps.", code="invalid_token")
    if exp < now - CLOCK_SKEW:
        raise SiwcError("That sign-in has expired. Please try again.", code="expired")
    if iat > now + CLOCK_SKEW:
        raise SiwcError("That sign-in is dated in the future.", code="invalid_token")

    # Every attempt sends a nonce, so every token must carry the same one back.
    got_nonce = claims.get("nonce")
    if not nonce or not isinstance(got_nonce, str) or not hmac.compare_digest(got_nonce, nonce):
        raise SiwcError("That sign-in does not match this browser's request.",
                        code="invalid_token")

    sub = str(claims.get("sub") or "").strip()
    if not sub:
        raise SiwcError("OpenAI did not say which account this is.", code="invalid_token")
    return {"sub": sub,
            "email": str(claims.get("email") or "").strip().lower(),
            "email_verified": claims.get("email_verified") is True,
            "name": str(claims.get("name") or "").strip(),
            "picture": str(claims.get("picture") or "").strip()}


# ------------------------------------------------------ the attempt itself ----
_tx_lock = threading.Lock()
_tx: dict[str, dict] = {}          # browser cookie value -> one sign-in attempt
_tickets: dict[str, dict] = {}     # one-time hand-off from callback to browser


def _prune(store: dict) -> None:
    now = time.time()
    for k in [k for k, v in store.items() if v.get("expires", 0) <= now]:
        store.pop(k, None)


def pkce_pair() -> tuple[str, str]:
    """(verifier, S256 challenge). 86 characters of verifier, inside the 43 to
    128 that RFC 7636 allows; the challenge is base64url of its SHA-256 with no
    padding, which is what OpenAI asks for."""
    verifier = secrets.token_urlsafe(64)
    challenge = _b64u(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def begin(intent: str, redirect: str, email: str = "",
          reconsent: bool = False) -> tuple[str, str]:
    """Start one attempt. Returns (the value for the browser's HttpOnly cookie,
    the URL to send the browser to).

    `intent` is "signin" from the login screen, or "connect" from the Account
    tab of a seller who is already signed in, whose address comes from their
    verified session and nowhere else. `reconsent` asks OpenAI to show the
    permission screen again, for a seller who said no to their plan before and
    has now pressed the button to say yes."""
    if not configured():
        raise SiwcError("Sign in with ChatGPT is not set up on this server.",
                        code="not_configured")
    if intent not in ("signin", "connect"):
        raise ValueError("unknown intent")
    email = (email or "").strip().lower()
    if intent == "connect" and not email:
        raise ValueError("connect needs the signed-in account")
    doc = discovery()
    verifier, challenge = pkce_pair()
    tx = {"state": secrets.token_urlsafe(32), "nonce": secrets.token_urlsafe(32),
          "verifier": verifier, "redirect_uri": redirect, "intent": intent,
          "email": email, "scopes": scopes(), "expires": time.time() + TX_TTL}
    params = {"client_id": client_id(), "redirect_uri": redirect,
              "response_type": "code", "scope": " ".join(tx["scopes"]),
              "state": tx["state"], "nonce": tx["nonce"],
              "code_challenge": challenge, "code_challenge_method": "S256"}
    if PLAN_SCOPE in tx["scopes"]:
        params["resource"] = RESOURCE
    if reconsent:
        # OpenAI: force_reconsent only once they confirm it for the client;
        # the ordinary OAuth prompt=consent works before that.
        if _flag("CHATGPT_FORCE_RECONSENT", False):
            params["force_reconsent"] = "true"
        else:
            params["prompt"] = "consent"
    tx_id = secrets.token_urlsafe(32)
    with _tx_lock:
        _prune(_tx)
        _tx[tx_id] = tx
    query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    return tx_id, f"{doc['authorization_endpoint']}?{query}"


def consume(tx_id: str, state: str) -> dict:
    """The attempt this callback belongs to, removed so it can never be used
    twice. A missing, expired, reused or mismatched attempt ends the sign-in."""
    with _tx_lock:
        tx = _tx.pop(str(tx_id or ""), None)
    if not tx or tx["expires"] <= time.time():
        raise SiwcError("This sign-in took too long or was already used. Please "
                        "start again.", code="expired")
    if not state or not hmac.compare_digest(str(state), tx["state"]):
        raise SiwcError("This sign-in could not be verified. Please start again.",
                        code="state")
    return tx


def issue_ticket(kind: str, payload: dict) -> str:
    """A single-use code the browser trades for the result of a callback.

    The callback is a redirect, and the app keeps its session token in the
    browser, so the token cannot simply be set as a cookie on the way back.
    Putting it in the URL would leave a live session in the browser history;
    this short-lived, one-time ticket is all that travels, and it travels in
    the fragment, which is never sent to any server."""
    t = secrets.token_urlsafe(32)
    with _tx_lock:
        _prune(_tickets)
        _tickets[t] = {"kind": kind, "payload": payload, "tries": 0,
                       "expires": time.time() + TICKET_TTL}
    return t


def take_ticket(ticket: str) -> dict | None:
    """The ticket's record, removed so it works exactly once. None when it is
    unknown, used or expired. The caller branches on rec["kind"]."""
    with _tx_lock:
        rec = _tickets.pop(str(ticket or ""), None)
    if not rec or rec["expires"] <= time.time():
        return None
    return rec


def return_ticket(ticket: str, rec: dict) -> bool:
    """Put a link ticket back after a wrong password, a few times at most, so a
    typo does not send the seller round OpenAI again."""
    rec["tries"] = int(rec.get("tries") or 0) + 1
    if rec["tries"] >= 5 or rec["expires"] <= time.time():
        return False
    with _tx_lock:
        _tickets[str(ticket)] = rec
    return True


# ------------------------------------------------------------ token calls ----
def _form_component(value: str) -> str:
    """application/x-www-form-urlencoded, byte for byte what the browser's
    URLSearchParams writes. RFC 6749 section 2.3.1 has the client id and secret
    encoded this way BEFORE they become the Basic credentials."""
    out = []
    for b in str(value).encode("utf-8"):
        c = chr(b)
        if (b < 128 and c.isalnum()) or c in "*-._":
            out.append(c)
        elif c == " ":
            out.append("+")
        else:
            out.append("%%%02X" % b)
    return "".join(out)


def _client_auth() -> dict:
    """Headers for a confidential client. The secret goes only in the Basic
    header, never in the form body, as OpenAI's guide requires. A public client
    sends nothing extra."""
    sec = client_secret()
    if not sec:
        return {}
    raw = f"{_form_component(client_id())}:{_form_component(sec)}".encode("utf-8")
    return {"Authorization": "Basic " + base64.b64encode(raw).decode("ascii")}


def _token_request(form: dict) -> dict:
    import requests
    headers = {"Accept": "application/json",
               "Content-Type": "application/x-www-form-urlencoded", **_client_auth()}
    try:
        r = requests.post(discovery()["token_endpoint"], data=form, headers=headers,
                          timeout=_HTTP_TIMEOUT)
    except Exception as e:  # noqa: BLE001
        raise TokenError("network", type(e).__name__, temporary=True) from e
    rid = r.headers.get("openai-request-id") or r.headers.get("x-request-id") or ""
    if r.status_code == 200:
        try:
            data = r.json()
        except ValueError:
            raise TokenError("bad_response", "not JSON", status=200, request_id=rid)
        if not isinstance(data, dict):
            raise TokenError("bad_response", "not an object", status=200, request_id=rid)
        return data
    try:
        body = r.json() or {}
    except ValueError:
        body = {}
    err = body.get("error")
    if isinstance(err, dict):           # an OpenAI-shaped error object
        code = str(err.get("code") or err.get("type") or "")
        detail = str(err.get("message") or "")
    else:                               # the OAuth shape: error + error_description
        code = str(err or body.get("code") or "")
        detail = str(body.get("error_description") or "")
    raise TokenError(code or f"http_{r.status_code}", detail[:200], status=r.status_code,
                     request_id=rid, temporary=r.status_code >= 500)


def exchange_code(code: str, tx: dict) -> dict:
    """Trade the authorization code for tokens, with the verifier and the same
    redirect_uri (and resource) the attempt started with."""
    form = {"grant_type": "authorization_code", "code": code,
            "redirect_uri": tx["redirect_uri"], "client_id": client_id(),
            "code_verifier": tx["verifier"]}
    if PLAN_SCOPE in (tx.get("scopes") or []):
        form["resource"] = RESOURCE
    try:
        data = _token_request(form)
    except TokenError as e:
        log.warning("ChatGPT code exchange failed: %s (status %s, request %s)",
                    e.code, e.status, e.request_id)
        raise SiwcError("OpenAI did not accept this sign-in. Please try again.",
                        code="exchange_failed") from e
    if not isinstance(data.get("id_token"), str) or not data["id_token"]:
        raise SiwcError("OpenAI did not send back a sign-in token.", code="exchange_failed")
    return data


def granted_scopes(token_response: dict) -> set[str]:
    """What the seller actually agreed to. The token response's own `scope`
    decides, as OpenAI's guide says; the access token's claim is read only when
    the response leaves it out."""
    raw = (token_response or {}).get("scope")
    if isinstance(raw, list):
        items = [str(x) for x in raw]
    elif isinstance(raw, str):
        items = raw.split()
    else:
        items = []
    if not items and (token_response or {}).get("access_token"):
        items = str(_jwt_payload_unverified(token_response["access_token"])
                    .get("scope") or "").split()
    return {s for s in items if s}


def _num(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _abs_time(v, now: float) -> float:
    """`earliest_refresh_at` as a Unix time. OpenAI names the field without
    saying its unit, so seconds, milliseconds, a duration and an ISO string are
    all read rather than one of them silently becoming 1970."""
    if v in (None, ""):
        return 0.0
    if isinstance(v, (int, float)) or str(v).replace(".", "", 1).isdigit():
        x = float(v)
        if x > 1e12:
            x /= 1000.0
        if x < 1e9:
            x = now + x
        return x
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).replace(microsecond=0).isoformat()


# ------------------------------------------------------ keeping the tokens ----
# The newest credentials per account, in this process, for two minutes. Refresh
# tokens ROTATE: the old one dies the moment a new one is issued. Two threads
# (a request and the Monday planner, say) each reading the stored record and
# each refreshing with it would have the second one present a dead token, which
# OpenAI answers with refresh_token_reused, and that ends the session. The lock
# below makes them take turns and this copy makes the second one see the first
# one's result instead of the stale record its request already read.
_LIVE_TTL = 120
_live: dict[str, dict] = {}
_live_lock = threading.Lock()
_refresh_locks: dict[str, threading.Lock] = {}


def _norm(email: str) -> str:
    return (email or "").strip().lower()


def _lock_for(email: str) -> threading.Lock:
    with _live_lock:
        return _refresh_locks.setdefault(_norm(email), threading.Lock())


def _creds(email: str) -> dict | None:
    stored = secrets_store.get_credentials(email, CONNECTOR) or None
    with _live_lock:
        live = _live.get(_norm(email))
        if live and time.time() - live["_at"] > _LIVE_TTL:
            _live.pop(_norm(email), None)
            live = None
    if live and (not stored or live["creds"].get("saved_at", 0) >= stored.get("saved_at", 0)):
        return dict(live["creds"])
    return stored


def _store(email: str, creds: dict, sub: str = "") -> None:
    secrets_store.save_connection(email, CONNECTOR, creds,
                                  meta={"plan": True, "sub": sub or creds.get("sub", ""),
                                        "saved_at": _iso(creds.get("saved_at") or time.time())})
    with _live_lock:
        _live[_norm(email)] = {"creds": dict(creds), "_at": time.time()}


def _drop(email: str) -> None:
    secrets_store.delete_connection(email, CONNECTOR)
    with _live_lock:
        _live.pop(_norm(email), None)


def save_tokens(email: str, token_response: dict, ident: dict) -> bool:
    """Keep what lets this app use the seller's plan. True when the plan scope
    was granted and there is an access token to use it with.

    A sign-in WITHOUT the plan scope keeps nothing: the tokens would authorise
    nothing we do, and an older grant must not outlive a narrower new one."""
    granted = granted_scopes(token_response)
    access = str(token_response.get("access_token") or "")
    if PLAN_SCOPE not in granted or not access:
        _drop(email)
        return False
    now = time.time()
    creds = {"access_token": access,
             "refresh_token": str(token_response.get("refresh_token") or ""),
             "token_type": str(token_response.get("token_type") or "Bearer"),
             "expires_at": now + _num(token_response.get("expires_in"), 3600),
             "earliest_refresh_at": _abs_time(token_response.get("earliest_refresh_at"), now),
             "scopes": sorted(granted), "client_id": client_id(),
             "issuer": discovery()["issuer"], "sub": ident.get("sub", ""),
             "saved_at": now}
    _store(email, creds, ident.get("sub", ""))
    return True


def plan_connected(email: str) -> bool:
    """Tokens that carry the plan scope are on file. Cheap: it reads the
    unencrypted metadata beside the record, not the record itself."""
    meta = secrets_store.connection_meta(email, CONNECTOR) or {}
    return bool(meta.get("plan")) and secrets_store.is_connected(email, CONNECTOR)


def access_token(email: str, force_refresh: bool = False) -> str | None:
    """A live access token for this seller's plan, renewed when it is close to
    expiry. None when there is no plan connection. Raises TokenError when a
    renewal is refused or cannot be made."""
    creds = _creds(email)
    if not creds or not creds.get("access_token"):
        return None
    if not force_refresh and creds.get("expires_at", 0) - time.time() > REFRESH_MARGIN:
        return creds["access_token"]
    with _lock_for(email):
        seen_at = creds.get("saved_at", 0)
        creds = _creds(email)
        if not creds or not creds.get("access_token"):
            return None
        # Somebody else renewed it while we waited for the lock: use theirs.
        if creds.get("saved_at", 0) > seen_at and \
                creds.get("expires_at", 0) - time.time() > REFRESH_MARGIN:
            return creds["access_token"]
        if not force_refresh and creds.get("expires_at", 0) - time.time() > REFRESH_MARGIN:
            return creds["access_token"]
        # OpenAI says when a renewal is first allowed. Before that, a token that
        # still works is used as it is.
        if (creds.get("earliest_refresh_at") or 0) > time.time() and \
                creds.get("expires_at", 0) > time.time():
            return creds["access_token"]
        return _refresh(email, creds)["access_token"]


def _refresh(email: str, creds: dict) -> dict:
    """The standard OAuth refresh, keeping the grant (no `scope` sent) and
    storing the replacement refresh token together with the new access token."""
    rt = creds.get("refresh_token") or ""
    if not rt:
        mark_needs_reconnect(email, "no_refresh_token")
        raise TokenError("no_refresh_token")
    form = {"grant_type": "refresh_token", "client_id": creds.get("client_id") or client_id(),
            "refresh_token": rt}
    if PLAN_SCOPE in (creds.get("scopes") or []):
        form["resource"] = RESOURCE
    try:
        data = _token_request(form)
    except TokenError as e:
        if e.code in TERMINAL_REFRESH_ERRORS:
            # The renewable session is over. The tokens are useless now, so they
            # go; the identity stays, so signing in with ChatGPT still works and
            # the seller is simply asked to connect again.
            mark_needs_reconnect(email, e.code)
        else:
            log.warning("ChatGPT token refresh failed: %s (status %s, request %s)",
                        e.code, e.status, e.request_id)
        raise
    now = time.time()
    access = str(data.get("access_token") or "")
    if not access:
        raise TokenError("bad_response", "no access token in the refresh response")
    new = {**creds, "access_token": access,
           "refresh_token": str(data.get("refresh_token") or rt),
           "expires_at": now + _num(data.get("expires_in"), 3600),
           "earliest_refresh_at": _abs_time(data.get("earliest_refresh_at"), now),
           "saved_at": now}
    if data.get("scope"):
        new["scopes"] = sorted(granted_scopes(data))
    _store(email, new)
    return new


def revoke(creds: dict | None) -> bool | None:
    """End the renewable session at OpenAI. True when OpenAI confirmed it (an
    empty 200, which it also sends for a token that was already dead), None when
    it could not be confirmed. Network failures and 5xx are retried with a short
    backoff, as OpenAI asks."""
    rt = (creds or {}).get("refresh_token") or ""
    if not rt:
        return True
    try:
        url = discovery().get("revocation_endpoint") or ""
    except SiwcError:
        url = ""
    if not url:
        return None
    import requests
    form = {"token": rt, "token_type_hint": "refresh_token",
            "client_id": (creds or {}).get("client_id") or client_id()}
    headers = {"Content-Type": "application/x-www-form-urlencoded", **_client_auth()}
    for wait in (0.0, 0.6, 1.8):
        if wait:
            time.sleep(wait)
        try:
            r = requests.post(url, data=form, headers=headers, timeout=10)
        except Exception as e:  # noqa: BLE001
            log.info("ChatGPT revocation attempt failed: %s", type(e).__name__)
            continue
        if r.status_code == 200:
            return True
        if r.status_code < 500:
            log.warning("ChatGPT revocation refused: HTTP %s", r.status_code)
            return None
    return None


# --------------------------------------------------------------- identity ----
def identity(email: str) -> dict:
    return user_store.get_key(email, IDENTITY_KEY, {}) or {}


def remember(email: str, claims: dict) -> None:
    """Record which ChatGPT account this is, keyed on `sub`.

    `sub` and not the email address, for the reason google_auth gives: an
    address can change and a subject cannot."""
    prev = identity(email)
    same = prev.get("sub") == claims["sub"]
    if prev.get("sub") and not same:
        index_drop(prev["sub"])       # the old ChatGPT account no longer opens this one
    user_store.set_key(email, IDENTITY_KEY, {
        "provider": "chatgpt",
        "issuer": discovery()["issuer"],
        "client_id": client_id(),
        "sub": claims["sub"],
        "email": claims.get("email", ""),
        "name": claims.get("name", ""),
        "picture": claims.get("picture", ""),
        "linked_at": prev.get("linked_at") if same and prev.get("linked_at")
                     else _iso(time.time()),
        # The "You're using your ChatGPT plan" note is shown once per ChatGPT
        # account, not once per sign-in.
        "welcomed_at": prev.get("welcomed_at", "") if same else "",
        "needs_reconnect": "",
    })
    index_put(claims["sub"], email)


def mark_welcomed(email: str) -> None:
    ident = identity(email)
    if ident.get("sub") and not ident.get("welcomed_at"):
        ident["welcomed_at"] = _iso(time.time())
        user_store.set_key(email, IDENTITY_KEY, ident)


def mark_needs_reconnect(email: str, reason: str) -> None:
    """The plan connection stopped working for good: clear the tokens and say
    so on the Account tab. Signing in with ChatGPT keeps working."""
    _drop(email)
    ident = identity(email)
    if ident:
        ident["needs_reconnect"] = reason or "expired"
        user_store.set_key(email, IDENTITY_KEY, ident)


# ------------------------------------------------ which account is whose ----
# ChatGPT account -> One Tap Manager account, so "Continue with ChatGPT" on the
# login screen finds a seller who connected ChatGPT from the Account tab under a
# DIFFERENT address. Keyed on a hash of issuer, client and subject; the value is
# only the account's email. Supabase keeps it in app_config, one row per
# identity (so two sign-ins never overwrite each other); locally it is a JSON
# file beside the account data.
_index_lock = threading.Lock()


def _index_key(sub: str) -> str:
    return "siwc:" + hashlib.sha256(
        f"{issuer()}|{client_id()}|{sub}".encode("utf-8")).hexdigest()


def _index_path() -> str:
    return os.path.join(user_store.root(), "siwc_index.json")


def _read_index() -> dict:
    try:
        with open(_index_path(), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_index(data: dict) -> None:
    path = _index_path()
    tmp = f"{path}.{secrets.token_hex(4)}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    os.replace(tmp, path)


def index_get(sub: str) -> str | None:
    if not sub:
        return None
    key = _index_key(sub)
    if db.SUPABASE_ENABLED:
        row = db.fetch_one("app_config", {"key": key})
        return _norm((row or {}).get("value") or "") or None
    with _index_lock:
        return _norm(_read_index().get(key) or "") or None


def index_put(sub: str, email: str) -> None:
    key = _index_key(sub)
    if db.SUPABASE_ENABLED:
        db.upsert("app_config", {"key": key, "value": _norm(email)}, on_conflict="key")
        return
    with _index_lock:
        data = _read_index()
        data[key] = _norm(email)
        _write_index(data)


def index_drop(sub: str) -> None:
    if not sub:
        return
    key = _index_key(sub)
    if db.SUPABASE_ENABLED:
        try:
            db.delete("app_config", {"key": key})
        except Exception as e:  # noqa: BLE001 — a stale row only points at this account
            log.warning("could not drop a ChatGPT index row: %s", e)
        return
    with _index_lock:
        data = _read_index()
        if data.pop(key, None) is not None:
            _write_index(data)


# ---------------------------------------------------------- the whole link ----
def disconnect(email: str) -> dict:
    """Stop using the seller's ChatGPT plan: end the session at OpenAI, then
    forget the tokens here. The sign-in link stays, so a seller who signed up
    with ChatGPT is not locked out of their own shop by pressing this."""
    creds = _creds(email)
    confirmed = revoke(creds) if creds else True
    _drop(email)
    try:
        from backend.core import chatgpt_plan
        chatgpt_plan.clear_state(email)
    except Exception:  # noqa: BLE001
        pass
    return {"revoked": confirmed is True, "unconfirmed": confirmed is None}


def forget_account(email: str) -> None:
    """Account deletion: end the session at OpenAI, drop the tokens, the
    identity and the login index row. Best effort, and it never raises."""
    try:
        creds = _creds(email)
        if creds:
            revoke(creds)
    except Exception:  # noqa: BLE001
        pass
    try:
        _drop(email)
    except Exception:  # noqa: BLE001
        pass
    try:
        ident = identity(email)
        if ident.get("sub"):
            index_drop(ident["sub"])
        user_store.set_key(email, IDENTITY_KEY, {})
    except Exception:  # noqa: BLE001
        pass


def keep_through_reset(email: str) -> dict:
    """What Account -> Reset must put back: the sign-in link and the plan
    connection are part of the login, and Reset promises to keep the login."""
    conns = user_store.get_key(email, secrets_store._CONN_KEY, {}) or {}
    return {"identity": identity(email), "connection": conns.get(CONNECTOR)}


def restore_after_reset(email: str, kept: dict) -> None:
    if not kept:
        return
    if kept.get("identity"):
        user_store.set_key(email, IDENTITY_KEY, kept["identity"])
    if kept.get("connection"):
        conns = user_store.get_key(email, secrets_store._CONN_KEY, {}) or {}
        conns[CONNECTOR] = kept["connection"]
        user_store.set_key(email, secrets_store._CONN_KEY, conns)


def status(email: str) -> dict:
    """What the Account tab, the Social screen and the AI buttons may know.
    Never a token."""
    if not configured():
        return {"enabled": False}
    ident = identity(email)
    plan = plan_usage_offered() and plan_connected(email)
    from backend.core import chatgpt_plan
    st = chatgpt_plan.public_state(email)
    return {
        "enabled": True,
        "plan_offered": plan_usage_offered(),
        "linked": bool(ident.get("sub")),
        "email": ident.get("email", ""),
        "name": ident.get("name", ""),
        "picture": ident.get("picture", ""),
        "plan": plan,
        "needs_reconnect": bool(ident.get("needs_reconnect")) and not plan,
        "eligible": st.get("eligible"),
        "limit": st.get("limit") if plan else None,
        "paused_reason": st.get("paused_reason") if plan else "",
        "blocked": bool(st.get("blocked")) if plan else False,
        "welcome": bool(plan and not ident.get("welcomed_at")),
        # The model that last wrote for them, or the one that will.
        "model": st.get("model") or chatgpt_plan.preferred_model(),
        "manage_url": MANAGE_USAGE_URL,
        "help_url": HELP_URL,
    }
