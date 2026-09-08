"""
Guards for the two defects behind "the page just shows an empty box".

Both were invisible from the call sites, which is exactly why they need tests:

  1. Every user_store.load_state() is an HTTPS round trip when Supabase is
     configured. Reading one flag LOOKS free, so the modules read one flag at a
     time and a single home screen made ~48 of them. This asserts the
     per-request memo holds, so it stays at one.

  2. res.statusText is always "" over HTTP/2, which is what the host serves. An
     unhandled 500 returned text/plain, so the client had no `detail` either and
     built new Error(""). Every catch block in smart.js renders the message into
     a card -- hence a bordered box with nothing in it. This asserts the server
     always sends JSON with a sentence, and that the client always has a
     fallback of its own.

Run: python3 scripts/test_perf_resilience.py
"""
import io
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core import user_store          # noqa: E402

PASS = FAIL = 0


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}{(' (' + str(extra) + ')') if extra else ''}")
    else:
        FAIL += 1
        print(f"  ✗ {label}  <-- {extra}")


print("\n== 1. the memo collapses a request's reads into one ==")

_real = user_store._read_state
HITS = {"n": 0}


def counting(email):
    HITS["n"] += 1
    return _real(email)


user_store._read_state = counting

from fastapi.testclient import TestClient   # noqa: E402
from backend.main import app                # noqa: E402

c = TestClient(app)
email = f"perf{int(time.time() * 1000)}@t.co"
tok = c.post("/api/register", json={"email": email, "password": "Test12345!"}).json()["token"]
H = {"Authorization": "Bearer " + tok, "X-Session-Id": "perf-session"}

# The requests the home screen actually fires, plus the modules it warms.
HOME = ["/api/smart/state", "/api/product-type", "/api/channels", "/api/today",
        "/api/social/upcoming?days=5", "/api/commerce/status"]
WARM = ["/api/products/state", "/api/store/orders", "/api/site/state", "/api/supply/state"]

total = 0
for path in HOME + WARM:
    HITS["n"] = 0
    r = c.get(path, headers=H)
    check(f"{path} answers with one backend read", r.status_code == 200 and HITS["n"] == 1,
          f"http={r.status_code} reads={HITS['n']}")
    total += HITS["n"]

check("a home screen costs 10 account reads, not ~79", total == len(HOME + WARM), total)

print("\n== 2. the memo is scoped to the request, not to time ==")

with user_store.request_scope():
    HITS["n"] = 0
    user_store.load_state(email)
    user_store.load_state(email)
    user_store.load_state(email)
    check("three reads inside one scope hit the backend once", HITS["n"] == 1, HITS["n"])

HITS["n"] = 0
with user_store.request_scope():
    user_store.load_state(email)
with user_store.request_scope():
    user_store.load_state(email)
check("a new scope starts cold -- no stale value survives the request", HITS["n"] == 2, HITS["n"])

HITS["n"] = 0
user_store.load_state(email)
user_store.load_state(email)
check("outside any scope nothing is cached (CLI, jobs, tests)", HITS["n"] == 2, HITS["n"])

with user_store.request_scope():
    user_store.set_key(email, "_perf_probe", {"v": 1})
    back = user_store.get_key(email, "_perf_probe")
    check("a request sees its own writes through the memo", back == {"v": 1}, back)

with user_store.request_scope():
    check("and the write really persisted", user_store.get_key(email, "_perf_probe") == {"v": 1})

with user_store.request_scope():
    a = user_store.load_state(email)
    a["_scribble"] = True
    b = user_store.load_state(email)
    check("a caller mutating what it got back cannot poison the memo", "_scribble" not in b)

user_store._read_state = _real

print("\n== 3. a 500 is readable, not an empty box ==")

from backend.core import sitebuilder        # noqa: E402

_get_site = sitebuilder.get_site


def boom(*a, **k):
    raise RuntimeError("simulated failure, not a real one")


sitebuilder.get_site = boom
quiet = TestClient(app, raise_server_exceptions=False)
r = quiet.get("/api/channels", headers=H)
sitebuilder.get_site = _get_site

check("an unhandled error still answers 500", r.status_code == 500, r.status_code)
check("as JSON, not text/plain", r.headers.get("content-type", "").startswith("application/json"),
      r.headers.get("content-type"))
detail = (r.json() or {}).get("detail") if r.headers.get("content-type", "").startswith("application/json") else None
check("with a sentence the seller can read", bool(detail) and len(str(detail)) > 20, detail)
check("and it does not leak the traceback", "RuntimeError" not in str(detail), detail)

print("\n== 4. the client can never render a blank error ==")

JS = io.open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "Smart CafeX", "smart.js"), encoding="utf-8").read()

check("smart.js carries its own per-status wording", "const HTTP_MSG" in JS)
for code in ("500", "502", "503", "504", "401"):
    check(f"  including {code}", re.search(rf"\n\s*{code}:\s*\"", JS) is not None)
check("statusText is no longer the last resort",
      "HTTP_MSG[res.status]" in JS and "|| res.statusText ||" in JS)
check("there is a final fallback even for an unlisted status",
      "The server returned ${res.status}" in JS)

print("\n== 5. retries are safe ones only ==")

check("a retry set exists", "const RETRY_STATUS" in JS)
check("it covers the codes a waking host returns",
      all(x in JS.split("RETRY_STATUS = new Set(")[1].split(")")[0] for x in ("502", "503", "504")))
check("retrying is gated on the request being a read",
      re.search(r"retryable\s*=\s*!opts\.method\s*\|\|\s*opts\.method\.toUpperCase\(\)\s*===\s*\"GET\"", JS)
      is not None)
check("both the network path and the status path honour that gate",
      JS.count("retryable && attempt < RETRY_MAX") == 2)
check("and it stops rather than looping", "RETRY_MAX = 2" in JS)

print("\n== 6. the strip that was showing empty now retries itself ==")

check("the platforms strip shows a skeleton while it loads",
      'strip.innerHTML = skeleton("cards")' in JS)
check("and a retryable failure instead of a bare card",
      "strip.innerHTML = failed(e.message, renderChannels)" in JS)
check("no catch block renders an unguarded empty message into the strip",
      'strip.innerHTML = `<div class="card">${esc(e.message)}</div>`' not in JS)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
