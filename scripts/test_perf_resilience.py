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
check("and it does not leak the traceback or the error's own text",
      "Traceback" not in str(detail) and "simulated failure" not in str(detail)
      and 'File "' not in str(detail), detail)
check("only where it broke — the type and the line — so a screenshot is enough to fix it",
      "RuntimeError at main.py:" in str(detail), detail)

print("\n== 4. the client can never render a blank error ==")

JS = io.open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "Smart CafeX", "smart.js"), encoding="utf-8").read()
CSS = io.open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "Smart CafeX", "smart.css"), encoding="utf-8").read()

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


# =========================================================================
print("\n== returning to the app does not reload the home screen ==")
# =========================================================================
# Switch to another app on a phone and come back, and the browser has usually
# thrown the page away — normal, and unpreventable. What IS preventable is
# showing a skeleton and four round trips on the way back. The last home
# screen is cached in the browser and painted immediately; the server is then
# asked whether anything changed, and answers 304 with no body when it has not.
import time as _t  # noqa: E402

import pandas as pd  # noqa: E402

from backend.core import smart  # noqa: E402

_e = f"warm{int(_t.time()*1000)}@t.co"
_tok = c.post("/api/register", json={"email": _e, "password": "Test12345!"}).json()["token"]
_H = {"Authorization": "Bearer " + _tok, "X-Session-Id": "warm"}

_r1 = c.get("/api/smart/state", headers=_H)
_tag = _r1.headers.get("etag", "")
check("the home payload carries an ETag", bool(_tag), dict(_r1.headers))
check("and is marked private, never cacheable by a shared proxy",
      "private" in (_r1.headers.get("cache-control") or ""),
      _r1.headers.get("cache-control"))

_r2 = c.get("/api/smart/state", headers={**_H, "If-None-Match": _tag})
check("an unchanged home screen answers 304", _r2.status_code == 304, _r2.status_code)
check("and sends no body at all — the whole point", len(_r2.content) == 0, len(_r2.content))
check("the 304 still carries the ETag so the browser keeps revalidating",
      _r2.headers.get("etag") == _tag, _r2.headers.get("etag"))

_r3 = c.get("/api/smart/state", headers={**_H, "If-None-Match": 'W/"not-the-tag"'})
check("a stale tag gets the real payload, not a 304",
      _r3.status_code == 200 and len(_r3.content) > 0, _r3.status_code)

# The ETag is the account's data fingerprint, so any real change must break it.
import datetime as _dt2  # noqa: E402
_df = pd.DataFrame([{"date": str(_dt2.date.today()), "order_id": "O1",
                     "customer_id": "C1", "customer_name": "A", "product": "X",
                     "category": "C", "quantity": 1, "amount": 100}])
_df["date"] = pd.to_datetime(_df["date"])
smart.save_sales(_e, _df, {"source": "upload", "filename": "s.xlsx"}, mode="replace")
_r4 = c.get("/api/smart/state", headers={**_H, "If-None-Match": _tag})
check("uploading data invalidates the cached copy immediately",
      _r4.status_code == 200, _r4.status_code)
check("and the new ETag is different", _r4.headers.get("etag") != _tag,
      _r4.headers.get("etag"))

# ---- the browser half ----
check("the app keeps a warm copy of the home screen", "WARM_KEY" in JS)
check("it is keyed to the signed-in account, so accounts never bleed",
      "c.email !== state.email" in JS)
check("it expires rather than showing something genuinely old",
      "WARM_MAX_AGE" in JS)
check("signing out takes the cached figures with it",
      JS.count("warmClear()") >= 3, JS.count("warmClear()"))
check("the home screen paints from cache before touching the network",
      "if (warm) paintHome(warm.state, warm.pt);" in JS)
check("and only repaints when something actually changed",
      "const changed = !warm" in JS)
check("a warm screen survives a failed refresh instead of becoming an error card",
      "Showing your last saved view" in JS)
check("every localStorage read is guarded — Safari private mode throws",
      "function warmRead" in JS and "catch (e) { return null; }" in JS)
check("Refresh deliberately bypasses the warm copy",
      "warmClear();" in JS.split("async function refreshCurrent")[1][:600])
check("icons are cached against the asset version, removing a cold-start hop",
      "ICON_KEY" in JS and "assetVersion()" in JS)
check("a warm start shows the shell without waiting on /api/me",
      "if (warmRead()) {" in JS)
check("but a 401 on that background check still signs the seller out",
      "api(\"/api/me\").catch((e) => { if (signedOut(e)) forget(); });" in JS)


# =========================================================================
print("\n== long jobs show motion, and modules stop reloading ==")
# =========================================================================
check("there is a busy overlay for long jobs", "function busyStart" in JS)
check("it is driven through one wrapper, so it always comes down",
      "async function withBusy" in JS and "finally { busyEnd(); }" in JS)
check("planning a week uses it", 'Planning ${n}' in JS)
check("generating a picture uses it", "Re-shooting your photo" in JS)
check("writing a shot list uses it", "Writing the shot list" in JS)
check("starting a campaign uses it", "Building the campaign" in JS)
check("reading the reference images uses it", "Reading your reference images" in JS)
check("it tells the seller they can carry on working",
      "Carry on using the app" in JS)
check("and that the work finishes on the server either way",
      "finishes whether you wait here or not" in JS)
# The first version of this said "go and do something else" from inside a
# full-screen scrim that blocked every way of doing it. The promise and the
# UI have to agree.
check("the indicator does NOT cover the screen",
      "position: fixed; inset: 0" not in CSS.split(".busy-back")[1][:200],
      CSS.split(".busy-back")[1][:120])
check("it does not dim or blur the app either",
      "backdrop-filter" not in CSS.split(".busy-back")[1][:200])
check("it sits clear of the toast corner",
      "left: 20px" in CSS.split(".busy-back")[1][:200])
check("and above the post editor, so it is visible during a generation",
      "z-index: 70" in CSS.split(".busy-back")[1][:200])
check("a finished plan does not yank the seller back to Social",
      'if (_currentModule === "social") await renderSocial();' in JS)
check("it tells them where to look instead",
      "open Social Media Manager to see it" in JS)
check("a picture landing after the editor closed does not throw",
      "const shotEl = $(\"smEdShot\");" in JS and "if (shotEl)" in JS)
check("nor does a clip landing after it closed",
      "const slotEl = $(\"smVidSlot\");" in JS and "if (slotEl)" in JS)
check("Plan cannot be double-pressed now that it no longer blocks the screen",
      "if (planBtns.some((b) => b.disabled)) return;" in JS)
check("the motion is CSS, not a timer a background tab would freeze",
      "@keyframes busyPulse" in CSS and "animation: busyPulse" in CSS)
check("reduced-motion still leaves something moving",
      "prefers-reduced-motion" in CSS.split("busyPulse")[-1][:400]
      or "busy-dots i { animation-duration" in CSS)

check("modules keep a warm copy too", "function warmModRead" in JS)
check("through one shared opener", "async function openCached" in JS)
check("Social, Products and Orders all use it", JS.count("openCached(") >= 4,
      JS.count("openCached("))
check("module caches share the account key with the home cache",
      "c.email !== state.email" in JS.split("function warmModRead")[1][:400])
check("any successful write drops every cached screen",
      "if (!retryable) { warmClear(); warmModClearAll(); }" in JS)
check("signing out clears the module caches too",
      JS.count("warmModClearAll()") >= 4, JS.count("warmModClearAll()"))
# The body of openCached, from its opening brace to the blank line that ends
# it. A fixed character count used to stand in for this and broke the moment a
# comment was added, which is a test failing for a reason that has nothing to
# do with the behaviour it is meant to protect.
_OPEN_CACHED = JS.split("async function openCached")[1].split("\n}\n")[0]

check("a failed refresh keeps the usable screen instead of an error card",
      _OPEN_CACHED.count("Showing your last saved view") == 1)

# ---- a reply that arrives after the seller has moved on ----
# THE BUG: every module fetch takes a moment, and a seller does not wait. Open
# Suppliers, tap Home before it lands, and the reply paints Suppliers back over
# the home page — the app undoing the tap. Caught by the throttled mobile
# walkthrough, not by anything here, so it is written down now.
check("a module that is no longer open does not paint over what is",
      "_currentModule === openedAs" in _OPEN_CACHED)
check("and the guard is checked after the fetch, not only before",
      _OPEN_CACHED.split("await fetcher()")[1][:200].count("stillHere()") >= 1)
check("the data is still cached even when it is not drawn",
      "warmModWrite(mod, fresh); return;" in _OPEN_CACHED.replace("\n", " ").replace("  ", " "))
check("an async render is awaited, or the two paints race",
      "await render(" in _OPEN_CACHED)
check("Home has the same guard", "_currentModule !== null" in JS.split("async function goHome")[1][:1400])
check("the slowest screen guards its second fetch too",
      '_currentModule !== "social"' in JS.split("async function renderSocial")[1][:1400])

# ---- the chart library is no longer on the critical path ----
HTML = io.open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "Smart CafeX", "smart.html"), encoding="utf-8").read()
check("Plotly is NOT a blocking script in the page head", "cdn.plot.ly/plotly" not in HTML.split("</head>")[0].replace("Plotly is NOT loaded here", ""))
check("but the connection to its CDN is warmed early", "preconnect" in HTML and "cdn.plot.ly" in HTML)
check("it is fetched on demand instead", "function ensurePlotly" in JS)
check("one download is shared by every chart on a screen", "_plotlyPromise" in JS)
check("a failed fetch can be retried rather than sticking",
      "_plotlyPromise = null" in JS.split("function ensurePlotly")[1][:700])
check("and it is warmed when the app is idle, not when a chart is needed",
      "requestIdleCallback" in JS.split("function warmPlotly")[1][:300])
check("a chart that outlives its screen is not drawn into a dead node",
      "const live = id ? $(id) : el;" in JS)

# ---- the app remembers which screen you were on ----
check("opening a module writes it into the URL", "history.pushState" in JS)
check("so a reload comes back to it", "deepLinkModule()" in JS.split("function showShell")[1][:400])
check("back and forward both work", 'addEventListener("popstate"' in JS)
check("and a route change that only reflects where we are is ignored",
      "deep === _currentModule" in JS)
check("scroll position survives leaving and returning", "function restoreScroll" in JS)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
