"""The launch-readiness fixes from LAUNCH_PLAN.md, each held in place by a test.

Every section names the plan row it guards (R1 to R14, S3, S4, S8). They come
from walking the app as a brand-new seller before launch: a login page with no
way to sign up, a demo that was a cafe, error screens for things that were only
empty, an email setup with no link, and an Outlook path that could never work.

Run: python scripts/test_launch_readiness.py
"""
import io
import logging
import os
import re
import smtplib
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("LAUNCH_MODE", "true")

from fastapi.testclient import TestClient  # noqa: E402
from backend.main import app  # noqa: E402
from backend.core import ratelimit, seller_mail, smart, today  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SMART_JS = io.open(os.path.join(ROOT, "Smart CafeX", "smart.js"), encoding="utf-8").read()
SMART_HTML = io.open(os.path.join(ROOT, "Smart CafeX", "smart.html"), encoding="utf-8").read()
LANDING = io.open(os.path.join(ROOT, "backend", "static", "landing.html"), encoding="utf-8").read()
EM = "—"
BS = chr(92)

PASS = FAIL = 0


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        print(f"  ✗ {label}  <-- {extra}")


ratelimit.reset()
c = TestClient(app)
T = uuid.uuid4().hex[:8]


def account(tag):
    email = f"{tag}{T}@example.com"
    tok = c.post("/api/register", json={"email": email, "password": "pw123456"}).json()["token"]
    return email, {"Authorization": "Bearer " + tok, "X-Session-Id": tag + T}


# A stand-in mail server. Records every connection so a test can prove that a
# refused address never reached a socket at all.
CONNECTS = []


class FakeSMTP:
    fail_hosts = set()
    fail_with = None

    def __init__(self, host="", port=0, *a, **k):
        CONNECTS.append((host, port))
        self.host = host

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def ehlo(self):
        pass

    def starttls(self, **k):
        pass

    def login(self, user, password):
        if self.host in FakeSMTP.fail_hosts:
            raise FakeSMTP.fail_with or smtplib.SMTPAuthenticationError(535, b"bad credentials")

    def send_message(self, msg):
        pass


_real_smtp, _real_ssl = seller_mail.smtplib.SMTP, seller_mail.smtplib.SMTP_SSL
seller_mail.smtplib.SMTP = FakeSMTP
seller_mail.smtplib.SMTP_SSL = FakeSMTP

# ============================================================================
print("\n== R1: the email guide lives in Account, with a link per provider ==")
# ============================================================================
email, H = account("guide")
d = c.get("/api/mail/account", headers=H).json()
provs = {p["id"]: p for p in d.get("providers", [])}
check("the server sends the guide", {"gmail", "workspace", "yahoo", "zoho", "icloud",
                                     "rediffmail", "outlook", "other"} <= set(provs), list(provs))
check("and the domain map, so the browser needs no table of its own",
      d.get("domains", {}).get("gmail.com") == "gmail" and d["domains"].get("hotmail.com") == "outlook")
for pid in ("gmail", "workspace", "yahoo", "zoho", "icloud"):
    p = provs.get(pid, {})
    check(f"{pid}: a direct https link and at least three steps",
          str(p.get("link", "")).startswith("https://") and len(p.get("steps", [])) >= 3, p.get("link"))
check("Gmail links straight to the page Google hides from its own menus",
      provs["gmail"]["link"] == "https://myaccount.google.com/apppasswords")
check("and says 2-Step Verification comes first",
      "2-Step" in provs["gmail"]["prereq"]["label"])
check("the browser's duplicate host table is gone", "MAIL_HOSTS" not in SMART_JS)
check("Account draws the guide inline instead of opening a second modal",
      'id="accMailBox"' in SMART_JS and 'renderMailGuide("accMailBox")' in SMART_JS)
check("and the Suppliers button reuses the same renderer",
      "renderMailGuide(\"mailGuideModal\"" in SMART_JS)
check("no em dash in any guide text",
      not any(EM in str(v) for p in provs.values() for v in [p.get("note", "")] + p.get("steps", [])))

# ============================================================================
print("\n== R2: Outlook is told the truth, before any network call ==")
# ============================================================================
CONNECTS.clear()
r = c.post("/api/mail/account", headers=H, json={"address": f"shop{T}@outlook.com", "password": "anything"})
check("an Outlook address is refused", r.status_code == 400, r.status_code)
check("with the reason: Microsoft stopped allowing it in 2026",
      "Microsoft" in r.json().get("detail", "") and "2026" in r.json().get("detail", ""), r.text[:160])
check("and no mail server was contacted", CONNECTS == [], CONNECTS)
for dom in ("hotmail.com", "live.com"):
    check(f"{dom} too", seller_mail.guess(f"x@{dom}")["works"] is False)
check("a business domain on Microsoft 365 is refused by its server",
      c.post("/api/mail/account", headers=H, json={
          "address": f"po{T}@myshop.in", "password": "x", "host": "smtp.office365.com",
          "port": 587}).status_code == 400 and CONNECTS == [])
FakeSMTP.fail_hosts = {"smtp.mydomain.in"}
FakeSMTP.fail_with = smtplib.SMTPAuthenticationError(
    535, b"5.7.139 Authentication unsuccessful, basic authentication is disabled")
msg = seller_mail._friendly(FakeSMTP.fail_with, {"address": "a@mydomain.in", "host": "smtp.mydomain.in"})
check("Microsoft's 5.7.139 answer is translated into the same truth", "Microsoft" in msg, msg)
FakeSMTP.fail_hosts, FakeSMTP.fail_with = set(), None

# ============================================================================
print("\n== R3: Zoho, whichever region the account lives in ==")
# ============================================================================
check("zohomail.in goes to the Indian server", seller_mail.guess("a@zohomail.in")["host"] == "smtp.zoho.in")
check("zoho.com goes to the international one", seller_mail.guess("a@zoho.com")["host"] == "smtp.zoho.com")
CONNECTS.clear()
FakeSMTP.fail_hosts = {"smtp.zoho.in"}
e3, H3 = account("zoho")
r = c.post("/api/mail/account", headers=H3, json={"address": f"shop{T}@zohomail.in", "password": "ok"})
check("an account in the other region still connects", r.status_code == 200 and r.json().get("connected"), r.text[:160])
check("by trying the other Zoho server once", [h for h, _ in CONNECTS] == ["smtp.zoho.in", "smtp.zoho.com"], CONNECTS)
check("and that server is the one saved", r.json().get("host") == "smtp.zoho.com", r.json().get("host"))
CONNECTS.clear()
FakeSMTP.fail_hosts = {"smtp.gmail.com"}
c.post("/api/mail/account", headers=H3, json={"address": f"shop{T}@gmail.com", "password": "bad"})
check("a wrong Gmail password is never retried anywhere else", [h for h, _ in CONNECTS] == ["smtp.gmail.com"], CONNECTS)
FakeSMTP.fail_hosts = set()

# ============================================================================
print("\n== S3: the email form cannot reach internal addresses ==")
# ============================================================================
for host in ("127.0.0.1", "10.0.0.5", "192.168.1.10", "169.254.169.254", "::1"):
    CONNECTS.clear()
    r = c.post("/api/mail/account", headers=H, json={
        "address": f"po{T}@myshop.in", "password": "x", "host": host, "port": 587})
    check(f"{host} is refused before a socket opens",
          r.status_code == 400 and "public mail server" in r.json().get("detail", "") and CONNECTS == [],
          (r.status_code, r.text[:120], CONNECTS))
CONNECTS.clear()
r = c.post("/api/mail/account", headers=H, json={
    "address": f"po{T}@myshop.in", "password": "x", "host": "smtp.gmail.com", "port": 80})
check("a non-mail port is refused", r.status_code == 400 and "not a mail port" in r.json().get("detail", "") and CONNECTS == [])
ratelimit.reset()
_real_gai = seller_mail.socket.getaddrinfo
seller_mail.socket.getaddrinfo = lambda *a, **k: [(2, 1, 6, "", ("142.250.4.108", 587))]
CONNECTS.clear()
r = c.post("/api/mail/account", headers=H, json={
    "address": f"po{T}@myshop.in", "password": "ok", "host": "mail.myshop.in", "port": 587})
check("a real public server on the seller's own domain still connects",
      r.status_code == 200 and CONNECTS == [("mail.myshop.in", 587)], (r.status_code, r.text[:120], CONNECTS))
seller_mail.socket.getaddrinfo = _real_gai
check("the known provider servers need no DNS lookup",
      seller_mail._public_host_or_raise("smtp.gmail.com", 587) is None)
check("connecting is capped at 10 a minute", ratelimit.limit_for("/api/mail/account", "POST") == 10)
check("but opening the screen is not", ratelimit.limit_for("/api/mail/account", "GET") == ratelimit.DEFAULT_LIMIT)
check("a refused recipient is reported as that, not as unreachable (branch order)",
      "refused the address" in seller_mail._friendly(
          smtplib.SMTPRecipientsRefused({"x@y.z": (550, b"no")}), {"address": "a@gmail.com"}))

# ============================================================================
print("\n== S8: every connect attempt is logged, never the password ==")
# ============================================================================
records = []


class _Grab(logging.Handler):
    def emit(self, rec):
        records.append(rec.getMessage())


ratelimit.reset()
lg = logging.getLogger("backend.core.seller_mail")
lg.addHandler(_Grab())
lg.setLevel(logging.INFO)
secret = f"SECRET-{T}"
FakeSMTP.fail_hosts = {"smtp.gmail.com"}
c.post("/api/mail/account", headers=H, json={"address": f"log{T}@gmail.com", "password": secret})
FakeSMTP.fail_hosts = set()
c.post("/api/mail/account", headers=H, json={"address": f"log{T}@gmail.com", "password": secret})
check("a failed attempt is logged with provider and error type",
      any("provider=gmail" in m and "ok=False" in m and "SMTPAuthenticationError" in m for m in records), records[-3:])
check("a successful one too", any("provider=gmail" in m and "ok=True" in m for m in records), records[-3:])
check("the password appears in no log line", not any(secret in m for m in records))

seller_mail.smtplib.SMTP, seller_mail.smtplib.SMTP_SSL = _real_smtp, _real_ssl

# ============================================================================
print("\n== R4, R5: a new visitor can always sign up ==")
# ============================================================================
check("the app's login card links to signup", 'href="/?signup=1"' in SMART_HTML)
check("the landing page opens signup when asked", 'get("signup") === "1"' in LANDING)
check("and still loads with the flag", c.get("/?signup=1").status_code == 200)
check("the final landing button opens signup, not the login page",
      "onclick=\"openSignup('free')\">Open One Tap Manager free" in LANDING)

# ============================================================================
print("\n== R6, R12: the first screen for a seller with no data ==")
# ============================================================================
check("a seller with no data is welcomed, not welcomed back",
      '${hasData ? "Welcome back" : "Welcome"}' in SMART_JS)
body = SMART_JS[SMART_JS.index("function renderHome("):]
check("Today comes before the explainer while there is no data",
      body.index('${hasData ? guide : ""}') < body.index('id="todayBox"') < body.index('${hasData ? "" : guide}'))

# ============================================================================
print("\n== R7: the sample shop looks like the sellers it is for ==")
# ============================================================================
import pandas as pd  # noqa: E402

df = pd.read_csv(os.path.join(ROOT, "data", "sample_transactions.csv"))
prod = df["product"].str.lower()
check("clothing, jewellery and fragrance only", set(df["category"]) == {"Clothing", "Jewellery", "Fragrance"},
      sorted(set(df["category"])))
check("no cafe left in it", not any(prod.str.contains(w).any()
                                    for w in ("sandwich", "coffee", "croissant", "cheesecake", "latte")))
check("every amount is positive", (df["amount"] > 0).all())
check("an order never lists the same product twice", not df.duplicated(["order_id", "product"]).any())
orders = df.groupby("order_id").agg(cust=("customer_id", "first"))
per = orders.groupby("cust").size()
check("a real D2C shape: hundreds of orders, most customers buy once",
      len(orders) >= 300 and 0.2 <= (per > 1).mean() <= 0.5, (len(orders), round((per > 1).mean(), 2)))
check("enough kinds of product for sub-category analysis", df["subcategory"].nunique() >= 8)
check("the generator is committed, so the file can be rebuilt",
      os.path.exists(os.path.join(ROOT, "scripts", "make_sample_data.py")))

# ============================================================================
print("\n== S4, R8: sample data is honest about what it lights up ==")
# ============================================================================
e4, H4 = account("demo")
c.post("/api/demo", headers=H4)
items = today.build(e4, limit=0)
check("Today has real work after loading the sample", len(items) >= 1, items)
check("and not a chore about the sample's own product names",
      not any(i.get("id") == "products_unlinked" for i in items), [i.get("id") for i in items])
names = pd.DataFrame({"date": pd.to_datetime(["2026-09-01"] * 4), "order_id": ["A1", "A2", "A3", "A4"],
                      "customer_id": ["X1", "X2", "X3", "X4"], "customer_name": ["a", "b", "c", "d"],
                      "product": ["Mystery One", "Mystery Two", "Mystery Three", "Mystery Four"],
                      "category": ["x"] * 4, "subcategory": ["y"] * 4, "quantity": [1] * 4,
                      "amount": [100.0] * 4})
e5, H5 = account("real")
smart.save_sales(e5, names, {"source": "upload", "name": "my export"}, mode="replace")
check("the same warning still fires for a seller's own unlinked sales",
      any(i.get("id") == "products_unlinked" for i in today.build(e5, limit=0)))
for path, method in (("/api/smart/positioning?lang=en", "get"), ("/api/smart/complaints", "get"),
                     ("/api/smart/strategy/detect?lang=en", "post")):
    r = getattr(c, method)(path, headers=H4)
    check(f"{path.split('?')[0]} answers an empty state, not an error",
          r.status_code == 200 and r.json().get("needs") == "review", (r.status_code, r.text[:100]))
check("the app draws that as an empty state with an upload button",
      "fresh.needs === \"review\"" in SMART_JS and "data-needs-reviews" in SMART_JS)
check("and the sample toast no longer claims every module is live",
      "every module is live now" not in SMART_JS)

# ============================================================================
print("\n== R10: no generic post before the app knows the seller ==")
# ============================================================================
e6, H6 = account("fresh")
titles = [i.get("title", "") for i in (c.get("/api/smart/state", headers=H6).json().get("insights") or [])]
check("a brand-new seller gets no filler post suggestion",
      not any(t.startswith("Suggested post") for t in titles), titles)
c.post("/api/product-type", headers=H6, json={"product_type": "jewellery"})
titles = [i.get("title", "") for i in (c.get("/api/smart/state", headers=H6).json().get("insights") or [])]
check("once they say what they sell, the suggestion appears",
      any(t.startswith("Suggested post") for t in titles), titles)

# ============================================================================
print("\n== R9, R14: copy and icons follow Brand.md ==")
# ============================================================================
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from sweep_em_dashes import scan, _is_matcher_arg  # noqa: E402

# Copy only. A string passed to .split() and friends is matching text the
# server writes (task titles), not text a seller reads, and the sweep tool
# leaves exactly those alone. Same rule here, so the gate means "no em dash in
# copy" rather than "no em dash anywhere".
in_strings = sum(SMART_JS[a:b].count(EM) for k, a, b in scan(SMART_JS)
                 if k == "str" and not _is_matcher_arg(SMART_JS, a))
check("no em dash inside any copy string in smart.js (this fails the build if one returns)",
      in_strings == 0, in_strings)
check("and none written as the escape \\u2014 either, which the character scan cannot see",
      (BS + "u2014") not in SMART_JS)
check("the one delimiter that must stay an em dash is still there",
      'const cut = String(t.text || "").split(" ' + EM + ' ");' in SMART_JS)
visible = re.sub(r"<!--.*?-->|<style[\s\S]*?</style>|<script[\s\S]*?</script>", "", SMART_HTML, flags=re.S)
check("none in smart.html's visible text", EM not in visible)
emoji = re.compile("[\U0001F000-\U0001FAFF☀-➿]")
bad = []
for f in ("product_config", "commerce", "smart", "supply", "ad_analytics"):
    for m in re.finditer(r'"icon"\s*:\s*"([^"]*)"', io.open(os.path.join(ROOT, "backend", "core", f + ".py"),
                                                          encoding="utf-8").read()):
        if emoji.search(m.group(1)):
            bad.append((f, m.group(1)))
check("no emoji used as an icon anywhere the server sends one", not bad, bad)
types = c.get("/api/product-types").json()
check("product types carry stroke-icon names",
      all(re.fullmatch(r"[a-z][a-z0-9-]*", t.get("icon", "")) for t in (types if isinstance(types, list)
                                                                        else types.get("types", []))), types)
check("the app draws server icons through one helper", "function ico(" in SMART_JS)
check("the explainer names the real groups",
      "<b>Sell</b>" not in SMART_JS and "<b>Know what is happening</b>" in SMART_JS)

# ============================================================================
print("\n== R13: the builder can frame its own storefront ==")
# ============================================================================
h = c.get("/smart", headers={"host": "onetapmanager.com", "x-forwarded-proto": "https"}).headers
check("same-origin framing allowed, every other site refused",
      h.get("x-frame-options") == "SAMEORIGIN" and "frame-ancestors 'self'" in h.get("content-security-policy", ""),
      (h.get("x-frame-options"), h.get("content-security-policy")))

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
