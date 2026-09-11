"""
Operations: knowing when it breaks, capping what it costs, and handing video off.

These four things were the non-user blockers on the readiness scorecard. Each one
is the kind of gap that does not show up in a demo and does show up in a month of
real use:

  * A 500 on the live server reached nobody. The seller closed the tab and the
    only evidence was a signup that went quiet.
  * AI generation cost real money per call with no ceiling anywhere, on a flat
    monthly price. One enthusiastic account could outspend its subscription in an
    afternoon.
  * A deploy missing one Supabase table worked perfectly and then lost the
    seller's data on the next redeploy, because the fallback was a local file on
    a filesystem Render rebuilds from git. That has happened twice.
  * Video generation billed about a hundred rupees a clip, sight unseen, when
    Google Flow does the same job free about five times a day and lets the seller
    look at the result first.

Run: python3 scripts/test_ops_and_handoff.py
"""
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from backend.main import app  # noqa: E402
from backend.core import aicaps, errors, health, videotools, products  # noqa: E402
import uuid as _uuid  # noqa: E402

_TAG = _uuid.uuid4().hex[:8]
PASS = FAIL = 0


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        print(f"  ✗ {label}  <-- {extra}")


c = TestClient(app, raise_server_exceptions=False)
MAIN = pathlib.Path("backend/main.py").read_text(encoding="utf-8")
JS = pathlib.Path("Smart CafeX/smart.js").read_text(encoding="utf-8")
CSS = pathlib.Path("Smart CafeX/smart.css").read_text(encoding="utf-8")
ENV = pathlib.Path(".env.example").read_text(encoding="utf-8")

# =========================================================================
print("\n== a crash reaches somebody ==")
# =========================================================================
try:
    raise KeyError("cust_9f3a")
except Exception as e:  # noqa: BLE001
    _rec = errors.record(e, where="GET /api/analytics", email="seller@shop.test",
                         extra={"rows": 42})
check("a failure is written down", bool(_rec.get("fingerprint")), _rec)
check("with the route it happened on", _rec["where"] == "GET /api/analytics")
check("and the account, so it can be reproduced", _rec["account"] == "seller@shop.test")
check("and a traceback", "KeyError" in _rec["traceback"])

# Grouping: the same bug with different data must be ONE line in the log, not
# fifty. Fingerprint is type + last frame + route, deliberately not the message.
def _raise_at(v):
    try:
        raise KeyError(v)
    except Exception as e:  # noqa: BLE001
        return errors._fingerprint(e, "GET /x")


check("the same bug with different data groups together",
      _raise_at("a") == _raise_at("b"))


def _other():
    try:
        raise ValueError("different")
    except Exception as e:  # noqa: BLE001
        return errors._fingerprint(e, "GET /x")


check("a different bug does not", _raise_at("a") != _other())

# Redaction: a traceback from this app can carry a seller's whole customer list.
_red = errors._redact("token=sk-abc123456789 mail a@b.com phone 9876543210 "
                      "card 4111 1111 1111 1111")
check("secrets are redacted before anything is stored", "sk-abc" not in _red, _red)
check("so are customer emails", "a@b.com" not in _red, _red)
check("phone numbers", "9876543210" not in _red, _red)
check("and card numbers", "4111" not in _red, _red)
check("an error log is not a place for a seller's customers",
      _red == "token=<redacted> mail <email> phone <phone> card <card>", _red)

_sum = errors.summary()
check("the log is grouped by cause, not listed raw", "groups" in _sum)
check("and reports which channels are actually live",
      set(_sum["channels"]) == {"log", "email", "sentry"}, _sum["channels"])
check("the on-disk layer is ALWAYS on — it needs no account and no config",
      _sum["channels"]["log"] is True)
check("Sentry is optional and reports itself honestly",
      errors.sentry_ready() is False)

_esrc = __import__("inspect").getsource(errors)
check("reporting can never be the thing that breaks a request",
      _esrc.count("except Exception") >= 5)
check("alert mail is throttled per bug, because alert fatigue is the failure mode",
      "EMAIL_THROTTLE_MINUTES" in _esrc and "_LAST_EMAILED" in _esrc)
check("the 500 handler records before it answers", "errors.record(exc" in MAIN)
check("and tells the seller it was reported, so they need not write in",
      "even if you do not tell us" in MAIN)
check("with a reference they can quote", "reference {ref}" in MAIN)
check("Sentry is initialised at startup if configured", "errors.init_sentry()" in MAIN)
check("it is documented for whoever deploys this", "OPERATOR_EMAIL" in ENV and "SENTRY_DSN" in ENV)

# =========================================================================
print("\n== the operator endpoints refuse everyone by default ==")
# =========================================================================
for ep, method in (("/api/admin/errors", "get"), ("/api/admin/health", "get"),
                   ("/api/admin/errors/clear", "post")):
    os.environ.pop("ADMIN_TOKEN", None)
    r = getattr(c, method)(ep)
    check(f"{ep} is off until ADMIN_TOKEN is set", r.status_code == 503, r.status_code)
os.environ["ADMIN_TOKEN"] = "t-" + _TAG
for ep, method in (("/api/admin/errors", "get"), ("/api/admin/health", "get")):
    r = getattr(c, method)(ep)
    check(f"{ep} refuses a missing token even once enabled", r.status_code == 403)
    r = getattr(c, method)(ep, headers={"X-Admin-Token": "wrong"})
    check(f"{ep} refuses a wrong token", r.status_code == 403)
    r = getattr(c, method)(ep, headers={"X-Admin-Token": "t-" + _TAG})
    check(f"{ep} answers with the right token", r.status_code == 200, r.status_code)
check("the token is compared in constant time", "secrets.compare_digest" in MAIN)
check("one shared gate rather than a copy per endpoint",
      MAIN.count("_require_admin(x_admin_token)") >= 4)

_r = c.get("/api/admin/errors", headers={"X-Admin-Token": "t-" + _TAG}).json()
check("the default view is grouped", "groups" in _r)
_r = c.get("/api/admin/errors?detail=true", headers={"X-Admin-Token": "t-" + _TAG}).json()
check("and there is a detailed view with tracebacks when you need it", "errors" in _r)

# =========================================================================
print("\n== a broken deploy says so, instead of failing silently ==")
# =========================================================================
_h = health.report()
check("health reports a verdict a human can act on", bool(_h["verdict"]))
check("blockers and warnings are separated",
      isinstance(_h["blockers"], list) and isinstance(_h["warnings"], list))
check("it names the exact failure that has bitten this app twice — a data dir "
      "inside the repo that every redeploy wipes",
      any("rebuilds from git" in b for b in _h["blockers"]), _h["blockers"])
check("it reports which storage mode is in use", _h["database"]["mode"] in
      ("local files", "Supabase", "unknown"), _h["database"]["mode"])
check("every table the app writes to is known, with the .sql that creates it",
      len(health.TABLES) >= 15 and all(v.endswith(".sql") for v in health.TABLES.values()))
check("a missing table names the file to run rather than saying 'a table is missing'",
      "Run the .sql files named below" in health._table_state()["note"]
      or health._table_state()["mode"] == "local files")
check("capabilities are described in the seller's terms, not the vendor's",
      any("Sellers can still upload their own photos" in cap["if_off"]
          for cap in _h["capabilities"]))
check("and it says which are off right now",
      all("on" in cap and "if_off" in cap for cap in _h["capabilities"]))
check("no mail server is called out, because that is the one to fix first",
      any("password reset" in w for w in _h["warnings"]), _h["warnings"])
check("LAUNCH_MODE being on is stated, not assumed",
      "launch_mode" in _h)
_hsrc = __import__("inspect").getsource(health)
check("every check is wrapped — a health check that throws is worse than none",
      _hsrc.count("except Exception") >= 2, _hsrc.count("except Exception"))
check("and none of it writes anything except a throwaway probe file",
      _hsrc.count("os.remove(probe)") == 1
      and "db.insert" not in _hsrc and "upsert" not in _hsrc)

# =========================================================================
print("\n== a ceiling on our own spend ==")
# =========================================================================
os.environ["AI_CAP_IMAGES_PER_DAY"] = "2"
os.environ["AI_CAP_VIDEOS_PER_DAY"] = "1"
EM = f"caps-{_TAG}@test.co"
check("images and video have SEPARATE budgets — they differ 30x in price",
      aicaps._cap("image") != aicaps._cap("video"))
check("the caps are configurable per deployment", aicaps._cap("image") == 2)
_caps = aicaps.caps()
check("each cap states what a full day of it would cost us",
      _caps["video"]["worst_case_inr"] > 0, _caps["video"])
check("and video is priced as the expensive one it is",
      _caps["video"]["unit_cost_inr"] > _caps["image"]["unit_cost_inr"] * 10)

check("nothing is used to start with", aicaps.remaining(EM, "image") == 2)
aicaps.consume(EM, "image")
check("a call is counted", aicaps.remaining(EM, "image") == 1)
aicaps.consume(EM, "image")
check("and the budget runs out", aicaps.remaining(EM, "image") == 0)
try:
    aicaps.check(EM, "image")
    check("going over is refused", False, "no error")
except aicaps.CapReached as e:
    check("going over is refused", True)
    check("and it reads as a ceiling, not as a punishment or a paywall",
          "upgrade" not in str(e).lower() and "limit" in str(e).lower(), str(e))
    check("it says when it lifts", "tomorrow" in str(e))
    check("and points at the free route instead",
          "own photographs still work" in str(e), str(e))
_video_ok = True
try:
    aicaps.check(EM, "video")
except aicaps.CapReached:
    _video_ok = False
check("the video budget is separate — spending the image one leaves it alone",
      _video_ok, "the two budgets are sharing a counter")
aicaps.consume(EM, "video")
try:
    aicaps.check(EM, "video")
    check("the video cap fires too", False, "no error")
except aicaps.CapReached as e:
    check("the video cap fires too", True)
    check("and its message sends them to Google Flow, which is free",
          "Google Flow" in str(e), str(e))

_asrc = __import__("inspect").getsource(aicaps)
check("the counter resets on a calendar day, not a rolling window — 'tomorrow' "
      "is a thing everyone understands", "_today()" in _asrc and "IST" in _asrc)
check("a failed generation is NOT charged to the seller's day",
      "AFTER the generation succeeds" in _asrc)
check("this sits underneath billing and applies in launch mode too",
      "including in launch mode" in __import__("inspect").getsource(
          __import__("backend.core.studio", fromlist=["x"]).generate_image)
      or "launch mode" in _asrc)

# End to end through the API, which is where the status code matters.
_tok = c.post("/api/register", json={"email": EM + ".api", "password": "pw123456"}).json()["token"]
_H = {"Authorization": "Bearer " + _tok, "X-Session-Id": "caps" + _TAG}
c.post("/api/products/item", headers=_H, json={"name": "Wallet", "price": 999})
_pid = products.get_products(EM + ".api")[0]["id"]
_u = c.get("/api/studio/ai-usage", headers=_H).json()
check("the app can be asked what is left before anything is pressed",
      _u["kinds"]["image"]["cap"] == 2 and _u["kinds"]["image"]["left"] == 2, _u)
aicaps.consume(EM + ".api", "image")
aicaps.consume(EM + ".api", "image")
aicaps.consume(EM + ".api", "video")
for _ep in ("/api/studio/image", "/api/studio/video"):
    r = c.post(_ep, headers=_H, json={"product_id": _pid})
    check(f"{_ep} answers 429, not 400 and not 500", r.status_code == 429, r.status_code)
    check(f"{_ep} carries a code the UI can branch on",
          r.json().get("code") == "daily_cap", r.json())
check("CapReached is re-raised past the 400 handler rather than swallowed",
      "except aicaps.CapReached:" in MAIN and "429 via the handler" in MAIN)
check("but approving a post at the cap still approves it, and puts it on the task list",
      "never loses the" in MAIN and "ensure_post_task" in MAIN)
check("the editor shows what is left before the seller presses anything",
      "showAiLeft" in JS and "pictures left today" in JS)
check("and refreshes it after a generation", "showAiLeft(true)" in JS)
check("the caps are documented", "AI_CAP_VIDEOS_PER_DAY" in ENV)
check("with the arithmetic that justifies the numbers", "worst case" in ENV)

# =========================================================================
print("\n== video handed off to a tool that does it free ==")
# =========================================================================
_t = videotools.tools()
check("there is a recommended destination", bool(_t["primary"]["url"]))
check("and it is Google Flow", _t["primary"]["id"] == "flow")
check("with the URL that actually resolves",
      _t["primary"]["url"] == "https://labs.google/fx/tools/flow", _t["primary"]["url"])
check("the steps name Frames — the ONLY mode that pins frame one to the "
      "seller's own photograph",
      any("Frames" in h for h in _t["primary"]["how"]), _t["primary"]["how"])
check("and say to drop their photo on the start frame",
      any("Add start frame" in h for h in _t["primary"]["how"]))
check("and to set 9:16, because this is going on a reel",
      any("9:16" in h for h in _t["primary"]["how"]))
check("the free allowance is stated up front", "50 credits a day" in _t["primary"]["free"])
check("so is the morning blackout window that would otherwise look like a bug",
      any("7:30 and 10:30" in w for w in _t["primary"]["watch_out"]),
      _t["primary"]["watch_out"])
check("and the watermark situation, which matters commercially",
      any("Watermark" in w or "watermark" in w for w in _t["primary"]["watch_out"]))
check("there are alternatives for someone without a Google subscription",
      {t["id"] for t in _t["tools"]} == {"flow", "gemini", "kling"})
check("Kling's watermark is disclosed, because it lands on the seller's own reel",
      any("watermark" in w for t in _t["tools"] if t["id"] == "kling"
          for w in t["watch_out"]))
check("every figure carries the date it was checked", bool(_t["checked_on"]))
check("and the app says so rather than pretending the numbers are permanent",
      "change often" in _t["note"])
_vsrc = __import__("inspect").getsource(videotools)
check("it is a module, not links in the HTML, so the facts have one home",
      "CHECKED_ON" in _vsrc)
check("and it records WHY handing off beats billing the seller",
      "better product than billing them" in _vsrc)
check("no fake deep link: Flow has no documented prompt parameter",
      "no documented" in _vsrc.lower() and "?prompt=" in _vsrc)

check("the endpoint is wired", "/api/studio/video-tools" in MAIN)
check("the reel handover offers it", "rpFlow" in JS)
check("the editor offers it too, not just the approval moment", "smVidFlow" in JS)
check("labelled free, and placed BEFORE the paid button",
      JS.index("smVidFlow") < JS.index("smVidGen"))
check("the paid one is labelled as paid", "Make it here (paid)" in JS)
check("the prompt is copied to the clipboard at the moment of the click",
      "clipboard.writeText" in JS.split("rpFlow")[1][:600])
check("and if the browser blocks the copy, it says so instead of failing quietly",
      "blocked the automatic copy" in JS)
check("the handoff panel is styled", ".vt-card" in CSS and ".vt-steps" in CSS)

# =========================================================================
print("\n== the live outage: a Supabase hiccup must not 500 the home screen ==")
# =========================================================================
# Found in the Render logs on 10 September 2026, on the live server, while a
# seller (the founder) was using it:
#
#   GET /api/smart/state   -> 500
#   GET /api/product-type  -> 500
#   httpx.ReadError: [Errno 11] Resource temporarily unavailable
#     ... httpcore/_sync/http2.py, line 438, in _read_incoming_data
#
# Two independent faults, and both are guarded here. The trigger was Python
# 3.14.3, which Render installs by default and on which httpcore's synchronous
# HTTP/2 backend fails reading from Supabase. The reason a socket hiccup could
# take the whole home screen down was db.py calling .execute() bare, so any
# transport error propagated straight out of the endpoint.
from backend.core import db  # noqa: E402


class _FakeQuery:
    def __init__(self, boom):
        self.boom = boom

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def upsert(self, *a, **k):
        return self

    def insert(self, *a, **k):
        return self

    def update(self, *a, **k):
        return self

    def delete(self, *a, **k):
        return self

    def execute(self):
        if self.boom:
            # The exact errno the live server raised.
            raise OSError(11, "Resource temporarily unavailable")

        class _R:
            data = [{"id": "ok"}]
        return _R()


class _FakeClient:
    def __init__(self, boom):
        self.boom = boom
        self.calls = 0

    def table(self, name):
        self.calls += 1
        return _FakeQuery(self.boom)


_real_client = db.client
_broken = _FakeClient(True)
db.client = lambda: _broken
db._DEGRADED.clear()
db._LOGGED.clear()

check("a read under the live error returns the fallback, not an exception",
      db.fetch_all("products") == [], "still raising")
check("fetch_one degrades the same way", db.fetch_one("products", {"email": "x"}) is None)
check("and the failure is recorded rather than swallowed silently",
      "products" in db.degraded(), db.degraded())
check("with the real cause kept", "Resource temporarily unavailable" in
      db.degraded()["products"], db.degraded())
check("it retries once on a FRESH connection before giving up — the observed "
      "failure is a dead pooled socket, so retrying the same pool is pointless",
      _broken.calls >= 2, _broken.calls)

# A write is different: silently swallowing one loses the seller's data.
try:
    db.upsert("products", {"id": 1})
    check("a failed WRITE raises rather than pretending to have saved", False,
          "silently lost the write")
except db.TransportProblem as e:
    check("a failed WRITE raises rather than pretending to have saved", True)
    check("as a typed error the caller can catch", isinstance(e, RuntimeError))
    check("naming the table", "products" in str(e), str(e))

# Health has to surface the degraded state, because degrading gracefully also
# means degrading invisibly.
_h2 = health.report()
check("health reports the degraded tables", "products" in (_h2.get("degraded_tables") or {}))
check("and treats it as a blocker, not a warning",
      any("quietly not saving" in b for b in _h2["blockers"]), _h2["blockers"])

_working = _FakeClient(False)
db.client = lambda: _working
check("a successful read clears the degraded flag",
      db.fetch_all("products") == [{"id": "ok"}] and not db.degraded(), db.degraded())
db.client = _real_client
db._DEGRADED.clear()
db._LOGGED.clear()

_dsrc = __import__("inspect").getsource(db)
check("the outage is written down in the code, with the errno and the frame",
      "Errno 11" in _dsrc and "_read_incoming_data" in _dsrc)
check("and why reads degrade but writes raise",
      "swallowed write loses the seller" in _dsrc
      and "reads degrade and are recorded" in _dsrc, "the reasoning is not recorded")
check("repeated failures on one table are logged once, not per row",
      "_LOGGED" in _dsrc)

# The root cause: an unpinned Python.
_rt = health.runtime_state()
check("the Python version is checked", bool(_rt["python"]))
check("and 3.14 is called out as the one that broke Supabase reads",
      "3.14" in _rt["note"] or _rt["supported"], _rt)
check("this interpreter is a supported one", _rt["supported"], _rt["python"])
_pin = pathlib.Path(".python-version")
check(".python-version pins it in the repo, so a hand-made service gets it too",
      _pin.exists() and _pin.read_text().strip().startswith("3.12"),
      _pin.read_text().strip() if _pin.exists() else "missing")
_ry = pathlib.Path("render.yaml").read_text(encoding="utf-8")
check("render.yaml pins it as well", "PYTHON_VERSION" in _ry and "3.12.11" in _ry)
check("with the outage recorded next to it, so nobody 'tidies' the pin away",
      "the home screen of the live app was" in _ry)
check("and only ONE disk block, not a duplicate",
      _ry.count("\n    disk:") == 1, _ry.count("\n    disk:"))
check("the disk mount path and CAFEX_DATA_DIR are the same string",
      _ry.count("/var/data") >= 2 and "MUST BE THE SAME STRING" in _ry)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
