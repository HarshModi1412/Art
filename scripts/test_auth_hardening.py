"""
Tests for the sign-in path: password hashing cost, login throttling, and
Google ID token verification.

Every one of these is a test of something that FAILS SILENTLY in production if
it is wrong. A password hash at the wrong cost still logs people in; a login
guard that never trips still works for honest users; a Google token check that
skips the audience still signs the right person in, every single time, while
also signing in anyone in the world who asks. None of that shows up in a manual
click-through, which is exactly why it is written down here.

Run: python scripts/test_auth_hardening.py
"""
from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

_TMP = tempfile.mkdtemp(prefix="authtest_")
os.environ["CAFEX_DATA_DIR"] = _TMP
os.environ.setdefault("CS_SECRET_KEY", "")

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


# ============================================================ password hashing
from backend.core import auth  # noqa: E402

section("Password hashing")

h = auth.hash_password("correct horse battery staple")
check("new hashes carry their cost", h.startswith("pbkdf2$600000$"), h[:24])
check("correct password verifies", auth.verify_password("correct horse battery staple", h))
check("wrong password does not", not auth.verify_password("Correct horse battery staple", h))
check("empty password does not", not auth.verify_password("", h))
check("a fresh hash needs no rehash", not auth.needs_rehash(h))

# Two hashes of the same password must differ — that is the salt doing its job.
check("salted: same password hashes differently",
      auth.hash_password("abc") != auth.hash_password("abc"))

# The cost really is what the string claims.
t0 = time.perf_counter()
auth.verify_password("correct horse battery staple", h)
dt = time.perf_counter() - t0
check("600k iterations actually run (>=120ms here)", dt > 0.12, f"{dt*1000:.0f}ms")

section("Old password rows still work")

# The format before the cost was written into the string. Anyone who has not
# logged in since the change has one of these, and locking them out would be
# far worse than the weak hash it replaces.
import hashlib  # noqa: E402
salt = "a" * 32
old_digest = hashlib.pbkdf2_hmac("sha256", b"hunter2", bytes.fromhex(salt), 100_000).hex()
old = f"pbkdf2${salt}${old_digest}"
check("pre-2026 hash verifies", auth.verify_password("hunter2", old))
check("pre-2026 hash rejects a wrong password", not auth.verify_password("hunter3", old))
check("pre-2026 hash is flagged for rehash", auth.needs_rehash(old))

check("plaintext row (v1) still verifies", auth.verify_password("plain", "plain"))
check("plaintext row is flagged for rehash", auth.needs_rehash("plain"))
check("garbage never verifies", not auth.verify_password("x", "pbkdf2$nonsense"))
check("garbage is flagged for rehash", auth.needs_rehash("pbkdf2$nonsense"))
check("a hash at a HIGHER cost is left alone",
      not auth.needs_rehash(f"pbkdf2$900000${salt}${old_digest}"))

section("A weak row is upgraded on a correct login")

users_csv = os.path.join(_TMP, "user.csv")
with open(users_csv, "w", encoding="utf-8") as f:
    f.write("email,password,plan\n")
    f.write(f"old@shop.test,{old},free\n")
    f.write("plain@shop.test,letmein,free\n")
auth.USERS_FILE = users_csv
auth.BASE_DIR = _TMP

tok = auth.login("old@shop.test", "hunter2")
check("old-format account logs in", bool(tok))
stored = auth.load_users().get("old@shop.test", "")
check("and its row is now at the new cost", stored.startswith("pbkdf2$600000$"), stored[:20])
check("and the same password still works after the upgrade",
      auth.verify_password("hunter2", stored))
check("and the upgrade did not change the password",
      not auth.verify_password("something else", stored))

auth.login("plain@shop.test", "letmein")
plain_stored = auth.load_users().get("plain@shop.test", "")
check("plaintext row is hashed on login", plain_stored.startswith("pbkdf2$600000$"))
check("plaintext is gone from the file", "letmein" not in open(users_csv, encoding="utf-8").read())

check("a wrong password returns no token", auth.login("old@shop.test", "nope") is None)
check("an unknown account returns no token", auth.login("ghost@shop.test", "x") is None)

section("Sessions")

t1 = auth.start_session("old@shop.test")
t2 = auth.start_session("old@shop.test")
check("each session gets its own token", t1 != t2)
check("tokens are long enough to be unguessable", len(t1) >= 40, str(len(t1)))
check("a token resolves to its account", auth.user_from_token(t1) == "old@shop.test")
check("an invented token resolves to nobody", auth.user_from_token("not-a-token") is None)
check("no token resolves to nobody", auth.user_from_token(None) is None)
auth.logout(t1)
check("logout kills that session", auth.user_from_token(t1) is None)
check("and leaves the other one alone", auth.user_from_token(t2) == "old@shop.test")

# =============================================================== login guard
from backend.core import loginguard  # noqa: E402

section("Login throttling")

loginguard.reset()
ok, wait = loginguard.check("seller@shop.test", "1.2.3.4")
check("a first attempt is free", ok and wait == 0, f"wait={wait}")

for _ in range(3):
    loginguard.failed("seller@shop.test", "1.2.3.4")
ok, wait = loginguard.check("seller@shop.test", "1.2.3.4")
check("three failures cost a delay", ok and wait >= 1, f"wait={wait}")

prev = wait
for _ in range(2):
    loginguard.failed("seller@shop.test", "1.2.3.4")
ok, wait2 = loginguard.check("seller@shop.test", "1.2.3.4")
check("the delay grows with each failure", wait2 > prev, f"{prev} -> {wait2}")

for _ in range(20):
    loginguard.failed("seller@shop.test", "1.2.3.4")
ok, wait3 = loginguard.check("seller@shop.test", "1.2.3.4")
check("enough failures stop the attempt entirely", not ok)
check("and say how long the pause is", wait3 > 60, f"{wait3}")

# The lock must not spread to an innocent account from a different address.
ok2, _ = loginguard.check("other@shop.test", "9.9.9.9")
check("another account from another address is unaffected", ok2)

loginguard.reset()
loginguard.failed("s2@shop.test", "5.5.5.5")
loginguard.failed("s2@shop.test", "5.5.5.5")
loginguard.failed("s2@shop.test", "5.5.5.5")
loginguard.succeeded("s2@shop.test", "5.5.5.5")
ok3, wait4 = loginguard.check("s2@shop.test", "5.5.5.5")
check("a correct password clears the account's delay", ok3 and wait4 == 0, f"wait={wait4}")

# One valid login must not launder the address it came from: otherwise an
# attacker who owns one account resets their own counter between guesses.
loginguard.reset()
for i in range(loginguard.IP_LOCK_AFTER + 1):
    loginguard.failed(f"victim{i}@shop.test", "6.6.6.6")
ok4, _ = loginguard.check("fresh@shop.test", "6.6.6.6")
check("spreading guesses over many accounts still trips the address limit", not ok4)

loginguard.reset()
for i in range(loginguard.IP_LOCK_AFTER + 1):
    loginguard.failed(f"v{i}@shop.test", "7.7.7.7")
loginguard.succeeded("v0@shop.test", "7.7.7.7")
ok5, _ = loginguard.check("v99@shop.test", "7.7.7.7")
check("one good login does not clear the address's record", not ok5)


class _Req:
    def __init__(self, headers, host=""):
        self.headers = headers
        self.client = type("c", (), {"host": host})() if host else None


check("client ip: the proxy's entry wins, not the client's claim",
      loginguard.client_ip(_Req({"x-forwarded-for": "1.1.1.1, 203.0.113.9"})) == "203.0.113.9")
check("client ip: falls back to the socket",
      loginguard.client_ip(_Req({}, "198.51.100.4")) == "198.51.100.4")
check("client ip: never raises with nothing to go on",
      loginguard.client_ip(_Req({})) == "")

loginguard.reset()

# ============================================================== google sign-in
from backend.core import google_auth  # noqa: E402
from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import padding, rsa  # noqa: E402

section("Google ID token verification")

CLIENT_ID = "123456.apps.googleusercontent.com"
os.environ["GOOGLE_CLIENT_ID"] = CLIENT_ID

_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def make_token(claims=None, alg="RS256", kid="k1", key=None, tamper=False):
    body = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "10987654321",
        "email": "Seller@Gmail.com",
        "email_verified": True,
        "name": "Kora Studio",
        "iat": int(time.time()) - 5,
        "exp": int(time.time()) + 3600,
    }
    body.update(claims or {})
    head = _b64u(json.dumps({"alg": alg, "kid": kid, "typ": "JWT"}).encode())
    payload = _b64u(json.dumps(body).encode())
    signing = f"{head}.{payload}".encode()
    sig = (key or _key).sign(signing, padding.PKCS1v15(), hashes.SHA256())
    if tamper:
        sig = bytes([sig[0] ^ 0xFF]) + sig[1:]
    return f"{head}.{payload}.{_b64u(sig)}"


# Stand in for Google's published keys.
google_auth._certs = {"at": time.time(), "keys": {}}
_real_public_key = google_auth._public_key
google_auth._public_key = lambda kid: (_key.public_key() if kid == "k1"
                                       else (_ for _ in ()).throw(
                                           ValueError("Google signed this with a key we do not recognise.")))


def rejects(label, token, expect="", nonce=""):
    try:
        google_auth.verify(token, nonce)
    except ValueError as e:
        check(label, (expect.lower() in str(e).lower()) if expect else True, str(e))
        return
    check(label, False, "it was ACCEPTED")


claims = google_auth.verify(make_token())
check("a good token verifies", claims["sub"] == "10987654321")
check("the email is normalised to lower case", claims["email"] == "seller@gmail.com", claims["email"])
check("the name comes through", claims["name"] == "Kora Studio")

rejects("a token for ANOTHER app is refused", make_token({"aud": "999.apps.googleusercontent.com"}), "different app")
rejects("a token from another issuer is refused", make_token({"iss": "https://evil.example"}), "did not come from Google")
rejects("a tampered signature is refused", make_token(tamper=True), "could not be verified")
rejects("a token signed by someone else's key is refused", make_token(key=_other_key), "could not be verified")
rejects("alg:none is refused", make_token(alg="none"), "algorithm")
rejects("alg:HS256 is refused", make_token(alg="HS256"), "algorithm")
rejects("an unknown key id is refused", make_token(kid="unknown"), "recognise")
rejects("an expired token is refused", make_token({"exp": int(time.time()) - 3600}), "expired")
rejects("a token dated in the future is refused", make_token({"iat": int(time.time()) + 9999}), "future")
rejects("an unverified email is refused", make_token({"email_verified": False}), "not verified")
rejects("a token with no email is refused", make_token({"email": ""}), "email")
rejects("nonsense is refused", "not.a.token")
rejects("an empty credential is refused", "")
rejects("two segments are refused", "aaa.bbb")

# The payload can be swapped for another valid-looking one; the signature is
# what stops it, and this proves the signature is actually checked against the
# payload rather than only parsed.
good = make_token()
head, _, sig = good.split(".")
evil_payload = _b64u(json.dumps({
    "iss": "https://accounts.google.com", "aud": CLIENT_ID, "sub": "1",
    "email": "victim@gmail.com", "email_verified": True,
    "iat": int(time.time()), "exp": int(time.time()) + 3600}).encode())
rejects("a swapped payload is refused", f"{head}.{evil_payload}.{sig}", "could not be verified")

section("Google nonce")

check("a matching nonce passes",
      google_auth.verify(make_token({"nonce": "abc123"}), "abc123")["sub"] == "10987654321")
rejects("a mismatched nonce is refused", make_token({"nonce": "abc123"}), "match", nonce="zzz")
rejects("a missing nonce is refused when one was expected", make_token(), "match", nonce="abc123")
check("no nonce expected means no nonce check",
      google_auth.verify(make_token({"nonce": "whatever"}))["sub"] == "10987654321")

section("Google sign-in must be switched on")

os.environ["GOOGLE_CLIENT_ID"] = ""
check("configured() is false without a client id", not google_auth.configured())
rejects("and verification refuses outright", make_token(), "not set up")
os.environ["GOOGLE_CLIENT_ID"] = CLIENT_ID
check("configured() is true with one", google_auth.configured())

section("Account linking")

# THE ATTACK: someone registers victim@gmail.com with a password they choose.
# The victim later signs in with Google. If the address alone decided it, the
# victim would be handed the attacker's account — and the attacker keeps the
# password. This is CVE-2026-53516.
check("an unlinked password account must prove itself first",
      google_auth.link_policy("victim@gmail.com", "pbkdf2$600000$aa$bb", False) == "verify")
check("an already-linked account signs straight in",
      google_auth.link_policy("victim@gmail.com", "pbkdf2$600000$aa$bb", True) == "sign_in")
check("an address with no account here is created",
      google_auth.link_policy("new@gmail.com", None, False) == "create")

google_auth._public_key = _real_public_key

print(f"\n{PASSED} passed, {FAILED} failed")
sys.exit(1 if FAILED else 0)
