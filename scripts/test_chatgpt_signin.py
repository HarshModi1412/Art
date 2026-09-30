"""
Tests for Sign in with ChatGPT and AI writing on the seller's own ChatGPT plan.

What is being protected, and why each one fails SILENTLY if it breaks:

  * The ID-token checks. A sign-in that skips the audience, the nonce or the
    signature still signs the right person in every time, and also anyone else
    who asks. Nothing in a click-through shows it.
  * The request contract. OpenAI's plan route refuses temperature,
    max_output_tokens and a system-role message, and only accepts store:false +
    stream:true. Sending any of them would make every plan request fail and
    every caption quietly fall back to our own AI, on our bill.
  * The limit handling. Treating an ordinary throttle as "your plan is spent"
    sends a seller to buy credits they do not need; treating a spent plan as a
    blip hammers OpenAI on every caption.
  * The fallback. With nobody waiting (the cron, the Monday planner) a spent
    plan must never stop a week being planned.

OpenAI is never contacted: every HTTP call is answered by the fakes below.

Run: python scripts/test_chatgpt_signin.py
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import tempfile
import threading
import time
import urllib.parse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

_TMP = tempfile.mkdtemp(prefix="siwctest_")
os.environ["CAFEX_DATA_DIR"] = _TMP
os.environ["AUTOPLAN_SCHEDULER"] = "off"
os.environ.setdefault("CS_SECRET_KEY", "")
for k in ("CHATGPT_CLIENT_ID", "CHATGPT_CLIENT_SECRET", "CHATGPT_REDIRECT_URI",
          "CHATGPT_PLAN_USAGE", "CHATGPT_FORCE_RECONSENT", "CHATGPT_PLAN_MODEL",
          "CHATGPT_PLAN_REASONING", "CHATGPT_ISSUER", "PUTER_AUTH_TOKEN", "CF_API_TOKEN",
          "CF_ACCOUNT_ID", "GROQ_API_KEY", "GEMINI_API_KEY", "HF_API_TOKEN", "OPENAI_API_KEY",
          "LAUNCH_MODE"):
    os.environ.pop(k, None)

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


# ------------------------------------------------------------ fake OpenAI ----
import requests  # noqa: E402

_real_get, _real_post = requests.get, requests.post
CALLS: list[dict] = []
ROUTES: dict = {}


class FakeResp:
    def __init__(self, status=200, body=None, headers=None, chunks=None, text=None):
        self.status_code = status
        self._body = body
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}
        self._chunks = chunks or []
        self.text = text if text is not None else (json.dumps(body) if body is not None else "")

    def json(self):
        if self._body is None:
            raise ValueError("no JSON")
        return self._body

    def iter_content(self, chunk_size=None):
        yield from self._chunks

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _route(method, url, **kw):
    CALLS.append({"method": method, "url": url, **kw})
    best = None
    for (m, prefix), handler in ROUTES.items():
        if m == method and url.startswith(prefix) and (best is None or len(prefix) > len(best[0])):
            best = (prefix, handler)
    if not best:
        raise AssertionError(f"unexpected {method} {url}")
    return best[1](url=url, **kw)


def fake_get(url, headers=None, timeout=None, **kw):
    return _route("GET", url, headers=headers or {}, **kw)


def fake_post(url, data=None, json=None, headers=None, timeout=None, stream=False, **kw):
    # A copy, as the real requests serialises the body at call time: a later
    # change to the same dict must not rewrite what was already "sent".
    import copy
    return _route("POST", url, data=copy.deepcopy(data), json=copy.deepcopy(json),
                  headers=dict(headers or {}), stream=stream, **kw)


requests.get, requests.post = fake_get, fake_post


def calls(method, prefix):
    return [c for c in CALLS if c["method"] == method and c["url"].startswith(prefix)]


def sse(events, ensure_ascii=True) -> bytes:
    out = b""
    for ev in events:
        out += (f"event: {ev['type']}\n"
                f"data: {json.dumps(ev, ensure_ascii=ensure_ascii)}\n\n").encode("utf-8")
    return out


def chunked(b: bytes, n: int = 7) -> list[bytes]:
    return [b[i:i + n] for i in range(0, len(b), n)]


def stream_of(text: str, n: int = 5, ensure_ascii=True) -> FakeResp:
    parts = [text[i:i + n] for i in range(0, len(text), n)] or [""]
    evs = [{"type": "response.created", "response": {"id": "r1"}}]
    evs += [{"type": "response.output_text.delta", "delta": p} for p in parts]
    evs.append({"type": "response.completed", "response": {
        "id": "r1", "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}]}})
    return FakeResp(200, chunks=chunked(sse(evs, ensure_ascii)), headers={"x-request-id": "req_1"})


# ------------------------------------------------------------ signing keys ----
from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402,F401
from cryptography.hazmat.primitives.asymmetric import padding, rsa  # noqa: E402

_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
CLIENT = "oaiapp_testclient"
ISS = "https://auth.openai.com"


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def id_token(claims=None, alg="RS256", kid="k1", key=None, drop=()):
    now = int(time.time())
    base = {"iss": ISS, "aud": CLIENT, "sub": "user_abc", "email": "seller@example.com",
            "email_verified": True, "name": "Asha", "picture": "https://x/p.png",
            "iat": now, "exp": now + 600, "nonce": "n-1"}
    base.update(claims or {})
    for d in drop:
        base.pop(d, None)
    head = b64u(json.dumps({"alg": alg, "kid": kid, "typ": "JWT"}).encode())
    body = b64u(json.dumps(base).encode())
    sig = (key or _key).sign(f"{head}.{body}".encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{head}.{body}.{b64u(sig)}"


def access_jwt(scope="chatgpt.tokens.use.direct email offline_access openid profile resource.invoke"):
    body = b64u(json.dumps({"scope": scope, "aud": "https://api.openai.com/v1"}).encode())
    return f"{b64u(b'{}')}.{body}.sig"


# ================================================================ off ====
from backend.core import aiprovider, chatgpt_auth, chatgpt_plan  # noqa: E402

section("Nothing happens until a client ID is set")
check("configured() is false without CHATGPT_CLIENT_ID", not chatgpt_auth.configured())
check("and the plan is not offered", not chatgpt_auth.plan_usage_offered())
check("status says disabled and nothing else", chatgpt_auth.status("a@b.co") == {"enabled": False})
res = aiprovider.generate("sys", "user", sensitivity="public", fallback="TEMPLATE",
                          email="someone@example.com")
check("writing for a seller falls through to the chain unchanged",
      res["text"] == "TEMPLATE" and res["provider"] == "template", res)
check("and OpenAI was never called", not CALLS, CALLS)

# ============================================================== config ====
os.environ["CHATGPT_CLIENT_ID"] = CLIENT
chatgpt_auth._disc.update(at=time.time(), ttl=3600, doc=dict(chatgpt_auth._DEFAULT_ENDPOINTS))
_real_public_key = chatgpt_auth._public_key
chatgpt_auth._public_key = lambda kid: (_key.public_key() if kid == "k1" else _real_public_key(kid))

section("The authorization request")
check("configured() with a client ID", chatgpt_auth.configured())
check("the plan is offered by default", chatgpt_auth.plan_usage_offered())
tx_id, url = chatgpt_auth.begin("signin", "https://shop.example/api/auth/chatgpt/callback")
u = urllib.parse.urlparse(url)
q = dict(urllib.parse.parse_qsl(u.query))
tx = chatgpt_auth._tx[tx_id]
check("goes to OpenAI's authorize endpoint",
      f"{u.scheme}://{u.netloc}{u.path}" == "https://auth.openai.com/api/accounts/authorize", url)
check("with our client id", q.get("client_id") == CLIENT)
check("response_type is code", q.get("response_type") == "code")
check("identity AND plan scopes are asked for",
      q.get("scope", "").split() == ["openid", "profile", "email", "offline_access",
                                     "resource.invoke", "chatgpt.tokens.use.direct"], q.get("scope"))
check("the plan resource is named", q.get("resource") == "https://api.openai.com/v1")
check("PKCE is S256", q.get("code_challenge_method") == "S256")
check("the challenge is base64url(sha256(verifier)) without padding",
      q.get("code_challenge") == b64u(hashlib.sha256(tx["verifier"].encode()).digest())
      and "=" not in q.get("code_challenge", ""))
check("the verifier is 43 to 128 characters", 43 <= len(tx["verifier"]) <= 128, len(tx["verifier"]))
check("state and nonce are sent and kept", q.get("state") == tx["state"] and q.get("nonce") == tx["nonce"])
check("the verifier itself never goes to OpenAI", tx["verifier"] not in url)
check("spaces are %20, not +", "scope=openid%20profile" in url)
tx_id2, url2 = chatgpt_auth.begin("signin", "https://shop.example/cb")
check("every attempt gets fresh state, nonce and verifier",
      chatgpt_auth._tx[tx_id2]["state"] != tx["state"]
      and chatgpt_auth._tx[tx_id2]["nonce"] != tx["nonce"]
      and chatgpt_auth._tx[tx_id2]["verifier"] != tx["verifier"])

_, url3 = chatgpt_auth.begin("signin", "https://shop.example/cb", reconsent=True)
check("a re-ask uses prompt=consent by default", "prompt=consent" in url3 and "force_reconsent" not in url3)
os.environ["CHATGPT_FORCE_RECONSENT"] = "on"
_, url4 = chatgpt_auth.begin("signin", "https://shop.example/cb", reconsent=True)
check("and force_reconsent once OpenAI confirms it", "force_reconsent=true" in url4 and "prompt=" not in url4)
os.environ.pop("CHATGPT_FORCE_RECONSENT")

os.environ["CHATGPT_PLAN_USAGE"] = "off"
_, url5 = chatgpt_auth.begin("signin", "https://shop.example/cb")
q5 = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url5).query))
check("sign-in only asks for identity alone", q5.get("scope") == "openid profile email", q5.get("scope"))
check("and names no resource", "resource" not in q5)
os.environ.pop("CHATGPT_PLAN_USAGE")

section("The callback is matched to its attempt")


def rejects_consume(label, tid, state, code):
    try:
        chatgpt_auth.consume(tid, state)
        check(label, False, "accepted")
    except chatgpt_auth.SiwcError as e:
        check(label, e.code == code, e.code)


tid, _ = chatgpt_auth.begin("signin", "https://shop.example/cb")
st = chatgpt_auth._tx[tid]["state"]
rejects_consume("a wrong state is refused", tid, "not-the-state", "state")
rejects_consume("and the attempt is gone after one try", tid, st, "expired")
tid, _ = chatgpt_auth.begin("signin", "https://shop.example/cb")
st = chatgpt_auth._tx[tid]["state"]
check("the right state is accepted once", chatgpt_auth.consume(tid, st)["state"] == st)
rejects_consume("a replay is refused", tid, st, "expired")
rejects_consume("no cookie at all is refused", "", st, "expired")
tid, _ = chatgpt_auth.begin("signin", "https://shop.example/cb")
chatgpt_auth._tx[tid]["expires"] = time.time() - 1
rejects_consume("an expired attempt is refused", tid, chatgpt_auth._tx[tid]["state"], "expired")

section("ID token verification")


def rejects_token(label, token, nonce="n-1", code="invalid_token"):
    try:
        chatgpt_auth.verify_id_token(token, nonce)
        check(label, False, "accepted")
    except chatgpt_auth.SiwcError as e:
        check(label, e.code == code, f"{e.code}: {e}")


claims = chatgpt_auth.verify_id_token(id_token(), "n-1")
check("a good token verifies", claims["sub"] == "user_abc" and claims["email"] == "seller@example.com")
check("the email's verification comes through", claims["email_verified"] is True)
rejects_token("a token for ANOTHER OpenAI app is refused", id_token({"aud": "oaiapp_other"}))
rejects_token("a list audience without us is refused", id_token({"aud": ["oaiapp_other"]}))
rejects_token("a list audience with us but a different azp is refused",
              id_token({"aud": [CLIENT, "oaiapp_other"], "azp": "oaiapp_other"}))
check("a list audience with us and azp us passes",
      chatgpt_auth.verify_id_token(id_token({"aud": [CLIENT, "x"], "azp": CLIENT}), "n-1")["sub"])
rejects_token("another issuer is refused", id_token({"iss": "https://evil.example"}))
rejects_token("an issuer with a trailing slash is refused (exact match)", id_token({"iss": ISS + "/"}))
rejects_token("an expired token is refused",
              id_token({"exp": int(time.time()) - 3600, "iat": int(time.time()) - 7200}), code="expired")
rejects_token("a token dated in the future is refused", id_token({"iat": int(time.time()) + 3600}))
rejects_token("a wrong nonce is refused", id_token(), nonce="other")
rejects_token("a missing nonce in the token is refused", id_token(drop=("nonce",)))
rejects_token("no expected nonce at all is refused", id_token(), nonce="")
rejects_token("alg none is refused", id_token(alg="none"))
rejects_token("HS256 is refused", id_token(alg="HS256"))
rejects_token("a signature from another key is refused", id_token(key=_other))
h, b, s = id_token().split(".")
evil = b64u(json.dumps({"iss": ISS, "aud": CLIENT, "sub": "victim", "nonce": "n-1",
                        "iat": int(time.time()), "exp": int(time.time()) + 600}).encode())
rejects_token("a swapped payload is refused", f"{h}.{evil}.{s}")
rejects_token("no subject is refused", id_token(drop=("sub",)))
rejects_token("garbage is refused", "not.a.jwt")
check("an unverified email is reported as such",
      chatgpt_auth.verify_id_token(id_token({"email_verified": False}), "n-1")["email_verified"] is False)
check("a missing email_verified counts as unverified",
      chatgpt_auth.verify_id_token(id_token(drop=("email_verified",)), "n-1")["email_verified"] is False)

section("Token exchange")
TOKEN_URL = "https://auth.openai.com/api/accounts/oauth/token"
ROUTES[("POST", TOKEN_URL)] = lambda **kw: FakeResp(200, {
    "id_token": id_token(), "access_token": access_jwt(), "refresh_token": "rt-1",
    "token_type": "Bearer", "expires_in": 3600,
    "scope": "chatgpt.tokens.use.direct email offline_access openid profile resource.invoke"})
tid, _ = chatgpt_auth.begin("signin", "https://shop.example/api/auth/chatgpt/callback")
t = chatgpt_auth.consume(tid, chatgpt_auth._tx[tid]["state"])
CALLS.clear()
data = chatgpt_auth.exchange_code("the-code", t)
form = calls("POST", TOKEN_URL)[0]["data"]
check("the grant is authorization_code", form.get("grant_type") == "authorization_code")
check("with the code, verifier, redirect and client",
      form.get("code") == "the-code" and form.get("code_verifier") == t["verifier"]
      and form.get("redirect_uri") == t["redirect_uri"] and form.get("client_id") == CLIENT)
check("and the same resource as the authorization", form.get("resource") == "https://api.openai.com/v1")
check("a public client sends no secret anywhere",
      "client_secret" not in form and "authorization" not in {k.lower() for k in calls("POST", TOKEN_URL)[0]["headers"]})
check("the ID token comes back", data["id_token"].count(".") == 2)

os.environ["CHATGPT_CLIENT_SECRET"] = "s3c r3t/+=~*"
CALLS.clear()
tid, _ = chatgpt_auth.begin("signin", "https://shop.example/cb")
chatgpt_auth.exchange_code("c", chatgpt_auth.consume(tid, chatgpt_auth._tx[tid]["state"]))
hdrs = calls("POST", TOKEN_URL)[0]["headers"]
basic = base64.b64decode(hdrs.get("Authorization", "Basic ").split(" ", 1)[1]).decode()
check("a confidential client sends HTTP Basic", hdrs.get("Authorization", "").startswith("Basic "))
check("form-encoded first, exactly as URLSearchParams would",
      basic == f"{CLIENT}:s3c+r3t%2F%2B%3D%7E*", basic)
check("and never in the form body", "client_secret" not in calls("POST", TOKEN_URL)[0]["data"])
os.environ.pop("CHATGPT_CLIENT_SECRET")

ROUTES[("POST", TOKEN_URL)] = lambda **kw: FakeResp(400, {"error": "invalid_grant"})
tid, _ = chatgpt_auth.begin("signin", "https://shop.example/cb")
try:
    chatgpt_auth.exchange_code("c", chatgpt_auth.consume(tid, chatgpt_auth._tx[tid]["state"]))
    check("a refused exchange raises", False)
except chatgpt_auth.SiwcError as e:
    check("a refused exchange becomes a plain sign-in failure", e.code == "exchange_failed")

section("Granted scopes decide plan use")
check("read from the token response",
      "chatgpt.tokens.use.direct" in chatgpt_auth.granted_scopes({"scope": "openid chatgpt.tokens.use.direct"}))
check("or from the access token when the response leaves it out",
      "chatgpt.tokens.use.direct" in chatgpt_auth.granted_scopes({"access_token": access_jwt()}))
check("a declined plan is a sign-in only",
      "chatgpt.tokens.use.direct" not in chatgpt_auth.granted_scopes(
          {"scope": "openid profile email", "access_token": access_jwt("openid profile email")}))

from backend.core import secrets_store, user_store  # noqa: E402

S1 = "keeper@example.com"
ident = {"sub": "user_keeper"}
check("tokens are kept when the plan was granted",
      chatgpt_auth.save_tokens(S1, {"access_token": access_jwt(), "refresh_token": "rt-a",
                                    "expires_in": 3600, "scope": "openid chatgpt.tokens.use.direct"}, ident))
raw_state = json.dumps(user_store.load_state(S1))
check("and never in plain text in the account's state", "rt-a" not in raw_state and access_jwt() not in raw_state)
check("plan_connected reads the metadata", chatgpt_auth.plan_connected(S1))
check("nothing is kept when the plan was declined",
      not chatgpt_auth.save_tokens(S1, {"access_token": access_jwt("openid"), "scope": "openid"}, ident))
check("and a declined re-grant drops the old tokens", not chatgpt_auth.plan_connected(S1))

section("Refreshing: rotation, and one refresh at a time")
chatgpt_auth.save_tokens(S1, {"access_token": "old-access", "refresh_token": "rt-1", "expires_in": 3600,
                              "scope": "chatgpt.tokens.use.direct offline_access"}, ident)
check("a fresh token is used as it is", chatgpt_auth.access_token(S1) == "old-access")
cr = secrets_store.get_credentials(S1, chatgpt_auth.CONNECTOR)
cr["expires_at"] = time.time() + 30
secrets_store.save_connection(S1, chatgpt_auth.CONNECTOR, cr, meta={"plan": True, "sub": "user_keeper"})
chatgpt_auth._live.clear()
_seq = {"n": 0}
_gate = threading.Event()


def _refresh_route(**kw):
    _seq["n"] += 1
    _gate.wait(0.3)            # hold the first refresh open while the second thread arrives
    return FakeResp(200, {"access_token": f"new-access-{_seq['n']}", "refresh_token": f"rt-{_seq['n'] + 1}",
                          "expires_in": 3600, "token_type": "Bearer"})


ROUTES[("POST", TOKEN_URL)] = _refresh_route
CALLS.clear()
out = []
th = [threading.Thread(target=lambda: out.append(chatgpt_auth.access_token(S1))) for _ in range(2)]
[x.start() for x in th]
[x.join() for x in th]
form = calls("POST", TOKEN_URL)[0]["data"] if calls("POST", TOKEN_URL) else {}
check("two threads near expiry make exactly one refresh", len(calls("POST", TOKEN_URL)) == 1,
      len(calls("POST", TOKEN_URL)))
check("and both get the new token", out == ["new-access-1", "new-access-1"], out)
check("the refresh grant keeps the grant: no scope sent, the resource is",
      form.get("grant_type") == "refresh_token" and "scope" not in form
      and form.get("resource") == "https://api.openai.com/v1" and form.get("refresh_token") == "rt-1")
check("the rotated refresh token is the one stored",
      secrets_store.get_credentials(S1, chatgpt_auth.CONNECTOR)["refresh_token"] == "rt-2")

cr = secrets_store.get_credentials(S1, chatgpt_auth.CONNECTOR)
cr["expires_at"] = time.time() + 10
cr["saved_at"] = time.time() + 1
secrets_store.save_connection(S1, chatgpt_auth.CONNECTOR, cr, meta={"plan": True, "sub": "user_keeper"})
chatgpt_auth._live.clear()
ROUTES[("POST", TOKEN_URL)] = lambda **kw: FakeResp(503, {"error": "temporarily_unavailable"})
try:
    chatgpt_auth.access_token(S1)
    check("a 503 on refresh raises", False)
except chatgpt_auth.TokenError as e:
    check("a 503 on refresh is temporary", e.temporary)
check("and keeps the tokens", chatgpt_auth.plan_connected(S1))

user_store.set_key(S1, chatgpt_auth.IDENTITY_KEY, {"sub": "user_keeper", "email": "k@x.co"})
ROUTES[("POST", TOKEN_URL)] = lambda **kw: FakeResp(400, {"error": "refresh_token_reused"})
try:
    chatgpt_auth.access_token(S1)
except chatgpt_auth.TokenError as e:
    check("a reused refresh token is terminal", e.code == "refresh_token_reused")
check("which drops the tokens", not chatgpt_auth.plan_connected(S1))
check("keeps the sign-in identity", chatgpt_auth.identity(S1).get("sub") == "user_keeper")
check("and asks the seller to reconnect", chatgpt_auth.identity(S1).get("needs_reconnect") == "refresh_token_reused")

section("earliest_refresh_at is read whatever its unit")
now = 1_790_000_000.0
check("seconds", chatgpt_auth._abs_time(1_790_000_100, now) == 1_790_000_100)
check("milliseconds", chatgpt_auth._abs_time(1_790_000_100_000, now) == 1_790_000_100)
check("a duration", chatgpt_auth._abs_time(300, now) == now + 300)
check("an ISO time", abs(chatgpt_auth._abs_time("2026-09-21T00:00:00Z", now) - 1_789_948_800) < 1)
check("nothing", chatgpt_auth._abs_time(None, now) == 0)

# ======================================================== the plan itself ====
section("A request on the seller's plan")
S2 = "writer@example.com"
chatgpt_auth.save_tokens(S2, {"access_token": "acc-2", "refresh_token": "rt-2", "expires_in": 3600,
                              "scope": "chatgpt.tokens.use.direct offline_access"}, {"sub": "user_writer"})
chatgpt_plan.clear_state(S2)
MODELS = "https://api.openai.com/v1/models"
RESP = "https://api.openai.com/v1/responses"
ROUTES[("GET", MODELS)] = lambda **kw: FakeResp(200, {"models": [
    {"slug": "gpt-6.1-sol", "display_name": "GPT-6.1 Sol", "visibility": "list"},
    {"slug": "gpt-6-luna", "display_name": "GPT-6 Luna", "visibility": "list"},
    {"slug": "hidden-model", "display_name": "Hidden", "visibility": "hide"}]})
ROUTES[("POST", RESP)] = lambda **kw: stream_of("A caption, written for you.")
CALLS.clear()
check("ready() once the plan is connected", chatgpt_plan.ready(S2))
out = chatgpt_plan.run(S2, "You write captions.", "Write one.")
body = calls("POST", RESP)[0]["json"]
hdr = calls("POST", RESP)[0]["headers"]
check("the text is the streamed deltas", out["text"] == "A caption, written for you.", out)
check("the efficient model is chosen", body.get("model") == "gpt-6-luna" and out["model"] == "gpt-6-luna")
check("the seller's own token is the bearer", hdr.get("Authorization") == "Bearer acc-2")
check("store is false and stream is true", body.get("store") is False and body.get("stream") is True)
check("the system prompt goes in instructions", body.get("instructions") == "You write captions.")
check("input is an array of user messages, no system role",
      isinstance(body.get("input"), list) and all(m.get("role") != "system" for m in body["input"]))
check("low reasoning effort", body.get("reasoning") == {"effort": "low"})
banned = {"temperature", "max_output_tokens", "max_tool_calls", "metadata", "user", "truncation",
          "previous_response_id", "background", "conversation", "prompt", "safety_identifier",
          "top_p", "top_logprobs", "moderation", "prompt_cache_retention", "tools"}
check("none of the fields OpenAI refuses on this route are sent", not (banned & set(body)), set(body) & banned)
check("hidden models are not in the catalogue",
      [m["slug"] for m in chatgpt_plan.models(S2)] == ["gpt-6.1-sol", "gpt-6-luna"])

chatgpt_plan.forget_models(S2)
ROUTES[("GET", MODELS)] = lambda **kw: FakeResp(200, {"models": [
    {"slug": "gpt-6.1-sol", "visibility": "list"}, {"slug": "gpt-5.4-mini", "visibility": "list"}]})
CALLS.clear()
chatgpt_plan.run(S2, "", "x")
check("without Luna, the cheap listed model is used, not the flagship",
      calls("POST", RESP)[0]["json"]["model"] == "gpt-5.4-mini")
check("and no empty instructions are sent", "instructions" not in calls("POST", RESP)[0]["json"])
chatgpt_plan.forget_models(S2)
ROUTES[("GET", MODELS)] = lambda **kw: FakeResp(200, {"models": [{"slug": "gpt-6-luna", "visibility": "list"}]})

section("Reading the event stream")
tricky = "Line one still line one \u0085 and café ✓ done"
ROUTES[("POST", RESP)] = lambda **kw: stream_of(tricky, n=3, ensure_ascii=False)
check("U+2028, U+0085 and multibyte text survive, even split across chunks",
      chatgpt_plan.run(S2, "", "x")["text"] == tricky)
ROUTES[("POST", RESP)] = lambda **kw: FakeResp(200, chunks=chunked(
    b": keep-alive\n\n" + sse([{"type": "response.output_text.delta", "delta": "Hi"},
                               {"type": "response.completed", "response": {}}]).replace(b"\n", b"\r\n"), 4))
check("CRLF line endings and comments are handled", chatgpt_plan.run(S2, "", "x")["text"] == "Hi")
ROUTES[("POST", RESP)] = lambda **kw: FakeResp(200, chunks=[sse([
    {"type": "response.output_text.delta", "delta": "half a capt"}])])
try:
    chatgpt_plan.run(S2, "", "x")
    check("a stream that stops before completed is refused", False)
except chatgpt_plan.Unavailable as e:
    check("a stream that stops before response.completed is not a success", True)
ROUTES[("POST", RESP)] = lambda **kw: FakeResp(200, chunks=[sse([
    {"type": "response.output_text.delta", "delta": "x"},
    {"type": "response.incomplete", "response": {"incomplete_details": {"reason": "content_filter"}}}])])
try:
    chatgpt_plan.run(S2, "", "x")
    check("response.incomplete is refused", False)
except chatgpt_plan.Unavailable:
    check("response.incomplete is not a success", True)
ROUTES[("POST", RESP)] = lambda **kw: FakeResp(200, chunks=[sse([
    {"type": "response.completed", "response": {"output": [
        {"type": "message", "content": [{"type": "output_text", "text": "From the final object"}]}]}}])])
check("text is taken from the completed response when no deltas came",
      chatgpt_plan.run(S2, "", "x")["text"] == "From the final object")

section("Usage limits")
chatgpt_plan.clear_state(S2)
ROUTES[("POST", RESP)] = lambda **kw: FakeResp(
    429, {"error": {"code": "subscription_sharing_usage_limit_exceeded", "message": "limit"}},
    headers={"Retry-After": "120", "x-request-id": "req_lim"})
try:
    chatgpt_plan.run(S2, "", "x")
    check("a usage limit raises LimitReached", False)
except chatgpt_plan.LimitReached as e:
    check("a usage limit raises LimitReached", True)
    check("with OpenAI's Retry-After", e.retry_after == 120, e.retry_after)
    check("and the manage-usage link for the screen",
          e.public()["manage_url"] == "https://chatgpt.com/settings/usage")
paused = chatgpt_plan._state(S2).get("paused_until", 0) - time.time()
check("plan requests pause for as long as OpenAI said", 110 < paused <= 120, paused)
CALLS.clear()
try:
    chatgpt_plan.run(S2, "", "x")
except chatgpt_plan.LimitReached as e:
    check("while paused, the limit is raised at once", e.code == "paused")
check("without another request to OpenAI", not calls("POST", RESP))
check("a pause does not stop ready(): a waiting person must see the limit screen",
      chatgpt_plan.ready(S2))
check("Account shows the pause", chatgpt_auth.status(S2)["limit"] is not None)
chatgpt_plan.retry_now(S2)
check("Try again lifts it", chatgpt_plan._state(S2).get("paused_until") is None)

ROUTES[("POST", RESP)] = lambda **kw: FakeResp(200, chunks=[sse([
    {"type": "response.output_text.delta", "delta": "partial"},
    {"type": "response.failed", "response": {"error": {
        "code": "subscription_sharing_usage_limit_exceeded", "message": "ran out"}}}])])
try:
    chatgpt_plan.run(S2, "", "x")
    check("a limit inside the stream raises", False)
except chatgpt_plan.LimitReached as e:
    check("a limit that arrives half way through the stream is a limit too", e.retry_after is None)
check("and pauses for the default ten minutes without a Retry-After",
      590 < chatgpt_plan._state(S2).get("paused_until", 0) - time.time() <= 600)
chatgpt_plan.retry_now(S2)

ROUTES[("POST", RESP)] = lambda **kw: FakeResp(429, {"error": {"code": "rate_limit_exceeded"}})
try:
    chatgpt_plan.run(S2, "", "x")
except chatgpt_plan.LimitReached:
    check("an ordinary 429 is NOT a spent plan", False)
except chatgpt_plan.Unavailable as e:
    check("an ordinary 429 is temporary trouble, not a spent plan", e.reason == "temporary")
check("which backs off for a moment", not chatgpt_plan.ready(S2))
chatgpt_plan.retry_now(S2)

ROUTES[("POST", RESP)] = lambda **kw: FakeResp(503, {"error": {"code": "subscription_sharing_usage_unavailable"}})
try:
    chatgpt_plan.run(S2, "", "x")
except chatgpt_plan.Unavailable as e:
    check("usage that cannot be checked is temporary", e.reason == "temporary")
check("and the tokens are kept", chatgpt_auth.plan_connected(S2))
chatgpt_plan.retry_now(S2)

ROUTES[("POST", RESP)] = lambda **kw: FakeResp(403, {"error": {"code": "subscription_sharing_user_not_eligible"}})
try:
    chatgpt_plan.run(S2, "", "x")
except chatgpt_plan.Unavailable as e:
    check("a free ChatGPT account is not eligible", e.reason == "not_eligible")
check("and is not asked again on every caption", not chatgpt_plan.ready(S2))
check("Account says so", chatgpt_auth.status(S2)["eligible"] is False)
chatgpt_plan.retry_now(S2)
check("until the seller presses Try again", chatgpt_plan.ready(S2))

section("Recovering from what can be recovered")
_n = {"i": 0}


def _reasoning_then_ok(json=None, **kw):
    _n["i"] += 1
    if "reasoning" in json:
        return FakeResp(400, {"error": {"code": "unsupported_parameter", "param": "reasoning.effort"}})
    return stream_of("ok without reasoning")


ROUTES[("POST", RESP)] = _reasoning_then_ok
CALLS.clear()
check("a model that refuses the reasoning setting gets the request again without it",
      chatgpt_plan.run(S2, "", "x")["text"] == "ok without reasoning" and _n["i"] == 2)
bodies = [c["json"] for c in calls("POST", RESP)]
check("and it is a DIFFERENT body, not the same one again", "reasoning" in bodies[0] and "reasoning" not in bodies[1])

_n["i"] = 0


def _401_then_ok(headers=None, **kw):
    _n["i"] += 1
    if headers.get("Authorization") == "Bearer acc-2":
        return FakeResp(401, {"detail": "The required signed identity was not accepted."})
    return stream_of("after a refresh")


ROUTES[("POST", RESP)] = _401_then_ok
ROUTES[("POST", TOKEN_URL)] = lambda **kw: FakeResp(200, {"access_token": "acc-2b", "refresh_token": "rt-2b",
                                                          "expires_in": 3600})
check("a 401 refreshes the token once and tries again",
      chatgpt_plan.run(S2, "", "x")["text"] == "after a refresh")
ROUTES[("POST", RESP)] = lambda **kw: FakeResp(401, {"error": {"code": "subscription_sharing_invalid_user"}})
try:
    chatgpt_plan.run(S2, "", "x")
except chatgpt_plan.Unavailable as e:
    check("a 401 that survives a refresh stops using the plan for a while", e.reason == "rejected")
check("without throwing the tokens away (not proof it is dead)", chatgpt_auth.plan_connected(S2))
check("and without hammering OpenAI", not chatgpt_plan.ready(S2))
chatgpt_plan.retry_now(S2)

# ================================================== routing in aiprovider ====
section("aiprovider: the seller's plan first, the chain as fallback")
ROUTES[("POST", RESP)] = lambda **kw: stream_of("Soft light — and a clean line.")
res = aiprovider.generate("sys", "user", sensitivity="private", fallback="TEMPLATE", email=S2)
check("writing for a connected seller uses their plan", res["provider"] == "chatgpt" and res.get("plan"), res)
check("the house style still applies (no em dash)", "—" not in res["text"] and res["text"], res["text"])
res = aiprovider.generate("sys", "user", sensitivity="public", fallback="TEMPLATE")
check("no email, no plan: the chain as before", res["provider"] == "template")
with aiprovider.request_context(interactive=True, route="app"):
    res = aiprovider.generate("sys", "user", sensitivity="public", fallback="TEMPLATE", email=S2)
check("X-AI-Route: app skips the plan for that request", res["provider"] == "template")

ROUTES[("POST", RESP)] = lambda **kw: FakeResp(
    429, {"error": {"code": "subscription_sharing_usage_limit_exceeded"}})
with aiprovider.request_context(interactive=True):
    try:
        aiprovider.generate("sys", "user", sensitivity="public", fallback="TEMPLATE", email=S2)
        check("with a person waiting, a spent plan raises", False)
    except chatgpt_plan.LimitReached:
        check("with a person waiting, a spent plan shows the limit screen", True)
res = aiprovider.generate("sys", "user", sensitivity="public", fallback="TEMPLATE", email=S2)
check("with nobody waiting (the planner), the chain writes instead", res["provider"] == "template", res)
chatgpt_plan.retry_now(S2)

ROUTES[("POST", RESP)] = lambda **kw: stream_of("A gold jhumka with three pearl drops.")
CALLS.clear()
d = aiprovider.describe_image(b"\x89PNG fake", "image/png", system="describe", user="look",
                              email=S2)
content = calls("POST", RESP)[0]["json"]["input"][0]["content"]
check("a photo is read on the plan with image input", d["provider"] == "chatgpt"
      and content[1]["type"] == "input_image" and content[1]["image_url"].startswith("data:image/png;base64,"))
check("the brand aesthetic never uses the plan (it passes no email)",
      "email=" not in open(os.path.join(os.path.dirname(__file__), "..", "backend", "core", "studio.py"),
                           encoding="utf-8").read().split("def read_aesthetic")[1].split("\ndef ")[0])

section("The image engine never claims to be the ChatGPT plan")
from backend.core import studio  # noqa: E402
check("OpenAI's image engine is not labelled ChatGPT",
      studio.IMAGE_ENGINES[0]["id"] == "openai" and "ChatGPT" not in studio.IMAGE_ENGINES[0]["label"])

# ================================================================ the app ====
section("The app: sign in, connect, link, limits")
from fastapi.testclient import TestClient  # noqa: E402
from backend import main as m  # noqa: E402
from backend.core import ratelimit  # noqa: E402

c = TestClient(m.app)
ratelimit.reset()
p = c.get("/api/auth/providers").json()
check("the login card is told ChatGPT is on", p["chatgpt"]["enabled"] and p["chatgpt"]["plan_usage"])
check("no client secret or client id is sent to the browser",
      CLIENT not in json.dumps(p["chatgpt"]))


def start(intent="signin", token=None):
    h = {"Authorization": "Bearer " + token} if token else {}
    r = c.post("/api/auth/chatgpt/start", json={"intent": intent}, headers=h)
    return r


def finish_callback(claims=None, scope="chatgpt.tokens.use.direct email offline_access openid profile resource.invoke"):
    tid = c.cookies.get("cx_siwc")
    txr = chatgpt_auth._tx.get(tid)
    base = {"nonce": txr["nonce"]}
    base.update(claims or {})
    ROUTES[("POST", TOKEN_URL)] = lambda **kw: FakeResp(200, {
        "id_token": id_token(base), "access_token": access_jwt(scope), "refresh_token": "rt-app",
        "expires_in": 3600, "scope": scope})
    return c.get("/api/auth/chatgpt/callback", params={"code": "code-1", "state": txr["state"]},
                 follow_redirects=False)


def frag(r):
    loc = r.headers.get("location", "")
    return dict(urllib.parse.parse_qsl(loc.split("#", 1)[1])) if "#" in loc else {}


r = start()
setc = r.headers.get("set-cookie", "")
check("start answers with OpenAI's URL", r.status_code == 200 and r.json()["url"].startswith(
    "https://auth.openai.com/api/accounts/authorize?"), r.text[:200])
check("and a cookie that JavaScript cannot read, only for these routes",
      "cx_siwc=" in setc and "HttpOnly" in setc and "Path=/api/auth/chatgpt" in setc
      and "samesite=lax" in setc.lower(), setc)
q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(r.json()["url"]).query))
check("the callback is this app's own route", q["redirect_uri"] == "http://testserver/api/auth/chatgpt/callback")

r = finish_callback({"sub": "sub-new", "email": "newseller@example.com"})
f = frag(r)
check("a callback lands back in the workspace", r.status_code == 303
      and r.headers["location"].startswith("/smart#"), r.headers.get("location"))
check("with a one-time ticket, never a session token or an OpenAI token",
      "cx_chatgpt" in f and "rt-app" not in r.headers["location"] and "token" not in f)
check("and the attempt's cookie is cleared", "cx_siwc=" in r.headers.get("set-cookie", "")
      and ("Max-Age=0" in r.headers.get("set-cookie", "") or "expires=" in r.headers.get("set-cookie", "").lower()))
d = c.post("/api/auth/chatgpt/finish", json={"ticket": f["cx_chatgpt"]}).json()
check("the ticket becomes a session", d.get("email") == "newseller@example.com" and d.get("token"))
check("for a brand new account", d.get("new_account") is True)
check("whose writing is on their ChatGPT plan", d["chatgpt"]["plan"] and d["chatgpt"]["welcome"])
check("the session works", c.get("/api/me", headers={"Authorization": "Bearer " + d["token"]}).status_code == 200)
check("a ticket works once", c.post("/api/auth/chatgpt/finish", json={"ticket": f["cx_chatgpt"]}).status_code == 400)
from backend.core import legal  # noqa: E402
check("the terms agreement is recorded for the new account",
      any(x.get("source") == "chatgpt" for x in legal.consents_for("newseller@example.com")))
TOK_NEW = d["token"]

ratelimit.reset()
start()
r = finish_callback({"sub": "sub-new", "email": "changed-address@example.com"})
d2 = c.post("/api/auth/chatgpt/finish", json={"ticket": frag(r)["cx_chatgpt"]}).json()
check("the same ChatGPT account signs in to the same shop even if its email changed",
      d2.get("email") == "newseller@example.com" and d2.get("new_account") is False, d2)

ratelimit.reset()
start()
tid = c.cookies.get("cx_siwc")
r = c.get("/api/auth/chatgpt/callback", params={"state": chatgpt_auth._tx[tid]["state"],
                                                "error": "access_denied"}, follow_redirects=False)
check("pressing cancel at OpenAI comes back as access_denied",
      frag(r).get("cx_chatgpt_error") == "access_denied")
start()
r = c.get("/api/auth/chatgpt/callback", params={"state": "forged", "error": "access_denied"},
          follow_redirects=False)
check("an error with a forged state is treated as a failed attempt, not trusted",
      frag(r).get("cx_chatgpt_error") == "state")
c.cookies.clear()
r = c.get("/api/auth/chatgpt/callback", params={"code": "x", "state": "y"}, follow_redirects=False)
check("a callback from another browser (no cookie) is refused", frag(r).get("cx_chatgpt_error") == "expired")

ratelimit.reset()
start()
r = finish_callback({"sub": "sub-unverified", "email": "unverified@example.com", "email_verified": False})
check("an unverified address creates nothing", frag(r).get("cx_chatgpt_error") == "email_unverified")

section("An existing password account must prove itself")
ratelimit.reset()
reg = c.post("/api/register", json={"email": "victim@example.com", "password": "Correct-Horse-1"}).json()
start()
r = finish_callback({"sub": "sub-attacker", "email": "victim@example.com"})
f = frag(r)
check("a matching email alone does NOT sign in", "cx_chatgpt_link" in f and "cx_chatgpt" not in f, f)
r = c.post("/api/auth/chatgpt/finish", json={"ticket": f["cx_chatgpt_link"]})
check("no password, no entry", r.status_code == 401)
r = c.post("/api/auth/chatgpt/finish", json={"ticket": f["cx_chatgpt_link"], "password": "wrong-one"})
check("a wrong password, no entry", r.status_code == 401)
check("and no identity was linked", not chatgpt_auth.identity("victim@example.com").get("sub"))
r = c.post("/api/auth/chatgpt/finish", json={"ticket": f["cx_chatgpt_link"], "password": "Correct-Horse-1"})
check("the right password links it", r.status_code == 200 and r.json()["email"] == "victim@example.com", r.text[:200])
check("and records the ChatGPT identity", chatgpt_auth.identity("victim@example.com").get("sub") == "sub-attacker")

section("Connecting from Account")
ratelimit.reset()
tok = c.post("/api/register", json={"email": "googler@example.com", "password": "Pw-123456"}).json()["token"]
check("connect needs a signed-in seller", start("connect").status_code == 401)
r = start("connect", tok)
check("connect starts for a signed-in seller", r.status_code == 200)
r = finish_callback({"sub": "sub-googler", "email": "someone-else@gmail.com"})
check("a different ChatGPT address still connects to THIS account",
      frag(r).get("cx_chatgpt") == "connected" and frag(r).get("plan") == "1", frag(r))
st = c.get("/api/account/chatgpt", headers={"Authorization": "Bearer " + tok}).json()
check("Account shows the plan in use", st["plan"] and st["email"] == "someone-else@gmail.com")
ratelimit.reset()
start()
r = finish_callback({"sub": "sub-googler", "email": "someone-else@gmail.com"})
d = c.post("/api/auth/chatgpt/finish", json={"ticket": frag(r)["cx_chatgpt"]}).json()
check("and later, Continue with ChatGPT on the login card opens that same account",
      d.get("email") == "googler@example.com", d)
tok2 = c.post("/api/register", json={"email": "other@example.com", "password": "Pw-123456"}).json()["token"]
ratelimit.reset()
start("connect", tok2)
r = finish_callback({"sub": "sub-googler", "email": "someone-else@gmail.com"})
check("one ChatGPT account cannot be moved onto a second shop silently",
      frag(r).get("cx_chatgpt_error") == "linked_elsewhere")
ratelimit.reset()
start("connect", tok2)
r = finish_callback({"sub": "sub-declined", "email": "d@example.com"}, scope="openid profile email")
check("declining the plan at OpenAI is a sign-in only", frag(r).get("plan") == "0")
check("so nothing is kept to spend", not chatgpt_auth.plan_connected("other@example.com"))

section("Writing on the plan, from the app")
H = {"Authorization": "Bearer " + tok}
ROUTES[("POST", RESP)] = lambda **kw: stream_of("Hand-blocked in Sanganer.")
from backend.core import credits  # noqa: E402
before = credits.monthly_used("googler@example.com")
r = c.post("/api/ai/write", json={"kind": "tagline"}, headers=H).json()
check("a Write with AI field is written on the seller's plan", r.get("provider") == "chatgpt", r)
check("and does not spend their app credits", credits.monthly_used("googler@example.com") == before)
ROUTES[("POST", RESP)] = lambda **kw: FakeResp(
    429, {"error": {"code": "subscription_sharing_usage_limit_exceeded"}}, headers={"Retry-After": "60"})
r = c.post("/api/ai/write", json={"kind": "tagline"}, headers=H)
check("at the limit the browser gets a 429 with its own code",
      r.status_code == 429 and r.json().get("code") == "chatgpt_limit", r.text[:300])
check("carrying the manage-usage link and OpenAI's wait",
      r.json()["chatgpt"]["manage_url"] == "https://chatgpt.com/settings/usage"
      and r.json()["chatgpt"]["retry_after"] == 60)
r = c.post("/api/ai/write", json={"kind": "tagline"}, headers={**H, "X-AI-Route": "app"})
check("'Use One Tap Manager AI this time' writes without the plan",
      r.status_code == 200 and r.json().get("provider") != "chatgpt", r.text[:200])
r = c.post("/api/account/chatgpt/retry", headers=H)
check("Try again lifts the pause", r.status_code == 200 and not r.json()["chatgpt"]["limit"])

section("The cron is never 'a person waiting'")
os.environ["ADMIN_TOKEN"] = "adm"
seen = {}
_real_run_due = m.autoplan.run_due
m.autoplan.run_due = lambda: seen.setdefault("interactive", aiprovider._interactive()) or {}
_real_pub = m.publisher.run_due
m.publisher.run_due = lambda: {}
_real_wb = m.winback_auto.run_due
m.winback_auto.run_due = lambda: {}
c.post("/api/admin/tick", headers={"X-Admin-Token": "adm"})
check("the planner's cron runs with nobody waiting, so a spent plan falls back",
      seen.get("interactive") is False, seen)
m.autoplan.run_due, m.publisher.run_due, m.winback_auto.run_due = _real_run_due, _real_pub, _real_wb


@m.app.get("/api/_test_interactive")
def _probe():
    return {"interactive": aiprovider._interactive()}


check("an ordinary request is a person waiting", c.get("/api/_test_interactive").json()["interactive"] is True)

section("Stopping, resetting and deleting")
REVOKE = "https://auth.openai.com/api/accounts/oauth/revoke"
ROUTES[("POST", REVOKE)] = lambda **kw: FakeResp(200, text="")
CALLS.clear()
r = c.post("/api/account/chatgpt/disconnect", headers=H).json()
rv = calls("POST", REVOKE)
check("Stop using my plan revokes the session at OpenAI", r.get("revoked") is True and len(rv) == 1)
check("with the refresh token and its hint", rv and rv[0]["data"].get("token_type_hint") == "refresh_token"
      and rv[0]["data"].get("token"))
check("drops the tokens", not chatgpt_auth.plan_connected("googler@example.com"))
check("but keeps the sign-in", chatgpt_auth.identity("googler@example.com").get("sub") == "sub-googler")
ROUTES[("POST", REVOKE)] = lambda **kw: FakeResp(503)
_sleep = time.sleep
time.sleep = lambda s: None
chatgpt_auth.save_tokens("googler@example.com", {"access_token": "a", "refresh_token": "r", "expires_in": 3600,
                                                 "scope": "chatgpt.tokens.use.direct"}, {"sub": "sub-googler"})
CALLS.clear()
r = c.post("/api/account/chatgpt/disconnect", headers=H).json()
time.sleep = _sleep
check("a failing revocation is retried with backoff", len(calls("POST", REVOKE)) == 3)
check("and reported as unconfirmed, not as done", r.get("unconfirmed") is True and r.get("revoked") is False)

chatgpt_auth.save_tokens("googler@example.com", {"access_token": "a", "refresh_token": "r", "expires_in": 3600,
                                                 "scope": "chatgpt.tokens.use.direct"}, {"sub": "sub-googler"})
c.post("/api/account/reset", headers=H)
check("Reset keeps the ChatGPT sign-in", chatgpt_auth.identity("googler@example.com").get("sub") == "sub-googler")
check("and the plan connection", chatgpt_auth.plan_connected("googler@example.com"))
ROUTES[("POST", REVOKE)] = lambda **kw: FakeResp(200, text="")
CALLS.clear()
c.delete("/api/account/delete", headers=H)
check("Delete revokes the session at OpenAI", len(calls("POST", REVOKE)) == 1)
check("and drops the login index", chatgpt_auth.index_get("sub-googler") is None)

section("The pages")
ROOT = os.path.join(os.path.dirname(__file__), "..")
HTML = open(os.path.join(ROOT, "Smart CafeX", "smart.html"), encoding="utf-8").read()
JS = open(os.path.join(ROOT, "Smart CafeX", "smart.js"), encoding="utf-8").read()
check("the login card has the Continue with ChatGPT button", 'id="siwcBtn"' in HTML
      and "Continue with ChatGPT" in HTML)
check("with OpenAI's own logo path", 'd="M11.8102 19.1625C11.2327' in HTML)
check("hidden until the server says it is on", 'id="siwcBox" class="siwc-box" hidden' in HTML)
check("the browser shows the limit screen for chatgpt_limit", 'data.code === "chatgpt_limit"' in JS)
check("and repeats a request with X-AI-Route: app only when asked", '"X-AI-Route": "app"' in JS)
check("the retry gate the perf test relies on is untouched",
      JS.count("retryable && attempt < RETRY_MAX") == 2)
check("Manage usage goes to ChatGPT's usage settings", "https://chatgpt.com/settings/usage" in JS)
check("the fragment is removed as soon as it is read", "history.replaceState(null, \"\", location.pathname" in JS)

requests.get, requests.post = _real_get, _real_post
chatgpt_auth._public_key = _real_public_key

print(f"\n{PASSED} passed, {FAILED} failed")
sys.exit(1 if FAILED else 0)
