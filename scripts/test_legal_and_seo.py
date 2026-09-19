"""
The legal pages, the consent gate, and the SEO that was actually broken.

Why each group of checks exists, because a test whose purpose is not written
down gets deleted by the next person who sees it go red:

  * Publishing a privacy policy and a user agreement is mandatory TODAY under
    SPDI Rule 4 and Rule 3(1)(a) of the IT Rules 2021. Not under the DPDP Act,
    whose substantive duties do not commence until around May 2027. Getting that
    distinction wrong in either direction is how a small operator either panics
    about the wrong thing or skips the thing that is already law.
  * A policy that names nobody is worse than no policy. So the pages refuse to
    claim completeness, and /api/admin/health refuses to call the deployment
    launch-ready, until a real operator is configured.
  * robots.txt advertised a sitemap that returned 404. That is a worse signal
    than no sitemap line at all and it is one of the reasons Google had nothing
    to show.
  * Google Analytics sets cookies, so it must not load before consent. Not
    because of Indian law, which has no cookie-banner rule, but because any EU
    or UK visitor brings the ePrivacy Directive with them.
  * Embedding Google Fonts sends a visitor's IP to Google before they have any
    say (LG Munchen I, 20 January 2022). The fix is trivial, so not doing it is
    indefensible.
  * The operator asked for no em dashes, no emoji icons and no purple in the
    visible product. Those are checked here as facts rather than promises.

Run: python3 scripts/test_legal_and_seo.py
"""
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from backend.main import app  # noqa: E402
from backend.core import legal, legal_html, sitebuilder, health  # noqa: E402
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


c = TestClient(app)
ROOT = pathlib.Path(__file__).resolve().parent.parent
LANDING = (ROOT / "backend/static/landing.html").read_text(encoding="utf-8")
STORE_HTML = (ROOT / "Smart CafeX/storefront/store.html").read_text(encoding="utf-8")
SMART_HTML = (ROOT / "Smart CafeX/smart.html").read_text(encoding="utf-8")
CONSENT_JS = (ROOT / "Smart CafeX/storefront/consent.js").read_text(encoding="utf-8")

# =========================================================================
print("\n== every document the law requires is published ==")
# =========================================================================
check("there is a legal hub", c.get("/legal").status_code == 200)
for slug, why in [
    ("privacy", "SPDI Rule 4 and IT Rules Rule 3(1)(a)"),
    ("terms", "IT Rules Rule 3(1)(a) requires a user agreement"),
    ("refunds", "E-commerce Rules Rule 4 and Rule 6"),
    ("cookies", "so what is stored can be checked"),
    ("acceptable-use", "IT Rules Rule 3(1)(a) rules and regulations"),
    ("grievance", "IT Rules Rule 3(2) requires a named officer"),
]:
    r = c.get(f"/legal/{slug}")
    check(f"/legal/{slug} is served ({why})", r.status_code == 200, r.status_code)
check("an unknown document 404s rather than rendering empty",
      c.get("/legal/not-a-document").status_code == 404)

# The old URL was public. Moving a published legal page without a redirect is how
# a link in somebody's email becomes a dead end.
for old, new in [("/privacy", "/legal/privacy"), ("/terms", "/legal/terms"),
                 ("/refunds", "/legal/refunds"), ("/cookies", "/legal/cookies")]:
    r = c.get(old, follow_redirects=False)
    check(f"{old} redirects permanently to {new}",
          r.status_code == 301 and r.headers.get("location") == new,
          f"{r.status_code} {r.headers.get('location')}")

# =========================================================================
print("\n== a policy that names nobody refuses to pretend otherwise ==")
# =========================================================================
for k, _, _ in legal.FIELDS:
    os.environ.pop(k, None)
import importlib  # noqa: E402
importlib.reload(legal)
importlib.reload(legal_html)

check("with nothing configured, the pages are not complete", legal.ready() is False)
check("and every required detail is itemised", len(legal.missing()) == len(legal.FIELDS))
check("each one says WHY it is needed",
      all(len(m["why"]) > 30 for m in legal.missing()))
_pg = legal_html.page("privacy")
check("the page says plainly that it is unfinished", "not finished" in _pg)
check("rather than printing a placeholder that looks like a name",
      "[" not in _pg.split("<main")[1][:2000] and "TODO" not in _pg)
check("and it must not be published in that state", "must not be published" in _pg)

_h = health.report()
check("health treats an unnamed operator as a BLOCKER, not a warning",
      any("cannot name who operates" in b for b in _h["blockers"]), _h["blockers"])

# Now configure it and confirm the pages become real.
os.environ.update({
    "LEGAL_NAME": "Test Proprietor", "BUSINESS_ADDRESS": "1 Test Road, Bengaluru 560001",
    "SUPPORT_EMAIL": "care@example.in", "SUPPORT_PHONE": "9876543210",
    "GRIEVANCE_NAME": "Test Proprietor", "GRIEVANCE_EMAIL": "grievance@example.in",
})
importlib.reload(legal)
importlib.reload(legal_html)
check("once configured, the pages are complete", legal.ready() is True)
_pg = legal_html.page("privacy")
check("and the operator is named on the page", "Test Proprietor" in _pg)
check("with the address the E-commerce Rules ask for", "1 Test Road" in _pg)
check("and a working email and phone", "care@example.in" in _pg and "9876543210" in _pg)
check("the unfinished warning is gone", "not finished" not in _pg)
check("health no longer blocks on it",
      not any("cannot name who operates" in b for b in health.report()["blockers"]))

# =========================================================================
print("\n== the things Indian law actually requires, on the page ==")
# =========================================================================
_priv = legal_html.page("privacy")
_terms = legal_html.page("terms")
_refund = legal_html.page("refunds")
_griev = legal_html.page("grievance")
_use = legal_html.page("acceptable-use")

check("the grievance officer is named, as Rule 3(2) requires",
      "Test Proprietor" in _griev)
check("with the 24 hour acknowledgement the 2026 amendment shortened it to",
      "24 hour" in _griev and str(legal.ACK_HOURS) == "24")
check("and the 7 day resolution",
      "7 days" in _griev and str(legal.RESOLVE_DAYS) == "7")
check("the strictest of the three overlapping clocks is the one promised",
      legal.ACK_HOURS == 24 and legal.RESOLVE_DAYS == 7)
check("cancellation is self-service, which the Dark Patterns Guidelines require",
      "same number of steps" in _refund or "same number of steps" in _terms)
check("and there is no cancellation charge, per Rule 4(8)",
      "no cancellation" in _refund.lower())
check("refunds state a concrete processing time, per Rule 4(10)",
      "working days" in _refund)
check("while unregistered, no GST is claimed and none is collected (s.32 CGST)",
      "Not registered under GST" in _priv and "GSTIN" not in _priv.split("<main")[1])
check("the AI output disclaimer says nobody reviewed it",
      "nobody reviews it" in _terms)
check("and that it may resemble other content",
      "originality" in _terms or "original" in _terms)
check("insights are called estimates, not advice",
      "not financial, tax, legal or business advice" in _terms)
check("liability is limited but NOT for fraud or injury, which would be void",
      "death or personal injury" in _terms and "fraud" in _terms)
check("and the Consumer Protection Act carve-out is explicit",
      "Consumer Protection Act" in _terms)
check("jurisdiction is named", "jurisdiction" in _terms)
check("but a consumer's own forum right is not pretended away",
      "consumer commission where you live" in _terms)
check("the retention periods in the terms match the privacy policy",
      str(legal.EXPORT_WINDOW_DAYS) in _terms and str(legal.EXPORT_WINDOW_DAYS) in _priv)
check("AI images must depict the real product, per E-commerce Rule 5(1)",
      "must show the thing you will actually ship" in _terms)
check("and the AI label may not be removed, per IT Rules Rule 3(3) (Feb 2026)",
      "must not remove the label" in _terms)
check("the prohibited-content list mirrors IT Rules Rule 3(1)(b)",
      all(w in _use for w in ("obscene", "impersonates", "unity, integrity")))
check("takedown timelines are stated honestly, including the 2 hour one",
      "three hours" in _use and "two hours" in _use)
check("CERT-In six hour reporting is disclosed in the privacy policy",
      "six hours" in _priv and "CERT-In" in _priv)
check("log retention matches the CERT-In 180 day requirement",
      legal.LOG_RETENTION_DAYS == 180 and "180" in _priv)
check("and the policy does NOT claim DPDP duties are live yet",
      "Digital Personal Data Protection" not in _priv
      or "2027" in _priv or "will" in _priv)
check("training AI on seller data is refused explicitly, not buried",
      "do not train artificial intelligence models on your data" in _priv)
check("sub-processors are named rather than described vaguely",
      all(n in _priv for n in ("Render", "Supabase", "Razorpay")))

# =========================================================================
print("\n== cookies: the honest answer, not the fashionable one ==")
# =========================================================================
os.environ.pop("GA4_MEASUREMENT_ID", None)
importlib.reload(legal)
importlib.reload(legal_html)
check("with no tracker configured, no banner is required", legal.consent_required() is False)
_ck = legal_html.page("cookies")
check("and the page says so plainly rather than hedging",
      "we do not set any cookies at all" in _ck)
check("it refuses to interrupt people for nothing",
      "permission for nothing" in _ck)
check("it states correctly that there is no Indian cookie law",
      "No Indian statute or rule requires a cookie banner" in _ck)
check("and names what DOES apply instead (Rule 4(9) pre-ticked boxes)",
      "pre-ticked" in _ck)
check("every item of storage is listed for the reader",
      len(legal.COOKIE_TABLE) >= 4 and "cx_token" in _ck)
check("browser storage is not mislabelled as a cookie",
      "Not a cookie" in _ck)

os.environ["GA4_MEASUREMENT_ID"] = "G-TEST" + _TAG[:4]
importlib.reload(legal)
importlib.reload(legal_html)
check("adding a tracker turns the requirement on by itself",
      legal.consent_required() is True)
_ck2 = legal_html.page("cookies")
check("and the page changes to match, rather than staying stale",
      "only runs if you allow it" in _ck2)
_cfg = c.get("/api/legal/config").json()
check("the frontend is told a banner is needed", _cfg["consent"]["required"] is True)
check("and which id to use once permission is given",
      _cfg["consent"]["analytics_id"].startswith("G-TEST"))

# The mechanism, not the promise.
check("analytics is injected by the consent script and nowhere else",
      "googletagmanager.com/gtag/js" in CONSENT_JS)
for name, page in (("landing", LANDING), ("app shell", SMART_HTML),
                   ("storefront", STORE_HTML)):
    check(f"{name} does not load a tracker directly",
          "googletagmanager" not in page and "gtag/js" not in page)
    check(f"{name} loads the consent gate", "/consent.js" in page)
check("Consent Mode v2 is set to denied BEFORE anything could read it",
      'gtag("consent", "default"' in CONSENT_JS
      and CONSENT_JS.index('"denied"') < CONSENT_JS.index("gtag/js"))
check("analytics_storage starts denied", 'analytics_storage: "denied"' in CONSENT_JS)
check("reject and accept are styled by ONE shared rule, so they cannot drift",
      ".cxc-b button{" in CONSENT_JS)
check("and both have the same minimum width, which is the equal-prominence point",
      "min-width:132px" in CONSENT_JS)
check("nothing is pre-ticked, because there are no checkboxes at all",
      "checkbox" not in CONSENT_JS.lower())
check("the decline button takes focus first",
      'getElementById("cxcNo").focus()' in CONSENT_JS)
check("what was consented to is recorded, with a timestamp and a version",
      all(k in CONSENT_JS for k in ("NOTICE_VERSION", "at: new Date", "categories")))
check("consent to an older notice does not count as consent to this one",
      "v.version !== NOTICE_VERSION" in CONSENT_JS)
check("withdrawal is always available from a persistent control",
      "Cookie settings" in CONSENT_JS)
check("and withdrawing actually deletes the cookies that were set",
      "clearAnalyticsCookies" in CONSENT_JS and "Max-Age=0" in CONSENT_JS)
check("the banner is a labelled dialog for a screen reader",
      'role", "dialog"' in CONSENT_JS and "aria-labelledby" in CONSENT_JS)

# =========================================================================
print("\n== Google Fonts: removed, not merely mentioned ==")
# =========================================================================
for name, page in (("landing", LANDING), ("app shell", SMART_HTML),
                   ("storefront", STORE_HTML)):
    check(f"{name} makes no request to a font CDN",
          "fonts.googleapis.com" not in page and "fonts.gstatic.com" not in page)
check("the landing page uses a system stack instead",
      "-apple-system" in LANDING and "BlinkMacSystemFont" in LANDING)
check("and says why, so nobody re-adds the CDN later",
      "System stacks, on purpose" in LANDING
      and "reaches a font CDN" in LANDING)
_legal_page = legal_html.page("terms")
check("the legal pages themselves load nothing external",
      "googleapis" not in _legal_page and "http" not in _legal_page.split("<style>")[1])

# =========================================================================
print("\n== the SEO that was broken ==")
# =========================================================================
_robots = c.get("/robots.txt")
check("robots.txt is served", _robots.status_code == 200)
_sm = c.get("/sitemap.xml")
check("and the sitemap it advertises now EXISTS (it used to 404)",
      _sm.status_code == 200, _sm.status_code)
check("the sitemap is valid xml with a urlset",
      _sm.text.startswith("<?xml") and "<urlset" in _sm.text)
check("it lists the home page and the legal pages",
      _sm.text.count("<loc>") >= 8 and "/legal/privacy" in _sm.text)
check("every entry carries a lastmod", _sm.text.count("<lastmod>") == _sm.text.count("<loc>"))
check("the signed-in app is disallowed, having nothing for a crawler",
      "Disallow: /smart" in _robots.text and "Disallow: /api/" in _robots.text)
check("the sitemap line points at the real sitemap",
      "/sitemap.xml" in _robots.text)

check("a favicon exists at both names browsers ask for",
      c.get("/favicon.svg").status_code == 200 and c.get("/favicon.ico").status_code == 200)
check("it is an svg, so one file covers every size",
      c.get("/favicon.svg").headers["content-type"].startswith("image/svg"))
for name, page in (("landing", LANDING), ("app shell", SMART_HTML),
                   ("storefront", STORE_HTML)):
    check(f"{name} declares the favicon", "favicon.svg" in page)

check("a legal page is indexable and canonical",
      'name="robots" content="index, follow"' in _legal_page
      and 'rel="canonical"' in _legal_page)
check("with exactly one h1", _legal_page.count("<h1") == 1)
check("and a meta description", 'name="description"' in _legal_page)
check("headings are h1 then h2, with no level skipped",
      "<h3" not in _legal_page)
check("there is a skip link for keyboard users", 'class="skip"' in _legal_page)

# =========================================================================
print("\n== a seller's shop gets its own legal pages, in its own name ==")
# =========================================================================
EM = f"shoplegal-{_TAG}@test.co"
_tok = c.post("/api/register", json={"email": EM, "password": "pw123456"}).json()["token"]
H = {"Authorization": "Bearer " + _tok, "X-Session-Id": "sl" + _TAG}

_opts = c.get("/api/site/legal-options", headers=H)
check("the seller is offered a fixed set of refund policies", _opts.status_code == 200)
_o = _opts.json()
check("four of them, so every common shape is covered", len(_o["choices"]) == 4)
check("not a free-text box, which is how a shop publishes something unenforceable",
      all(ch["id"] and ch["blurb"] for ch in _o["choices"]))
check("and the app lists what is still blank", len(_o["gaps"]) >= 4)

# The gate: a shop must not go live unable to say who runs it.
_site = {"brand": "Kaya Leather", "handle": f"kaya-{_TAG}"}
c.post("/api/site/save", headers=H, json={"site": _site})
_pub = c.post("/api/site/publish", headers=H, json={"published": True})
check("publishing is REFUSED while the legal details are blank",
      _pub.status_code >= 400, _pub.status_code)
check("and the refusal says exactly what is missing",
      "Still needed" in _pub.text, _pub.text[:120])
check("and that it is the law rather than our preference",
      "legal requirement" in _pub.text)

_site["trust"] = {"business_name": "Meera Rao",
                  "address": "12 MG Road, Bengaluru 560001",
                  "support_email": "hello@kaya.in", "support_phone": "9876543210",
                  "grievance_name": "Meera Rao", "refund_policy": "14day"}
c.post("/api/site/save", headers=H, json={"site": _site})
_pub = c.post("/api/site/publish", headers=H, json={"published": True})
check("once they are filled in, it publishes", _pub.status_code == 200, _pub.text[:120])

_handle = f"kaya-{_TAG}"
for slug in ("privacy", "terms", "refunds"):
    r = c.get(f"/s/{_handle}/legal/{slug}")
    check(f"the shop serves its own /legal/{slug}", r.status_code == 200, r.status_code)
check("an unknown shop document 404s",
      c.get(f"/s/{_handle}/legal/nonsense").status_code == 404)

_shop_refunds = c.get(f"/s/{_handle}/legal/refunds").text
check("the shop's policy names the SELLER, not us", "Meera Rao" in _shop_refunds)
check("and does not name us as the seller", "Test Proprietor" not in _shop_refunds)
check("the refund policy the seller CHOSE is the one published",
      "14 days" in _shop_refunds)
check("with exactly one h1", _shop_refunds.count("<h1") == 1)
check("and no external request on a shopper-facing legal page",
      "googleapis" not in _shop_refunds)

_scfg = c.get(f"/api/shop/{_handle}/legal").json()
check("the storefront is given the seller details Rule 5(4) makes us display",
      _scfg["seller"]["legal_name"] == "Meera Rao"
      and _scfg["seller"]["address"].startswith("12 MG Road"))
check("its three policy links", len(_scfg["documents"]) == 3)
check("the platform is identified too, so a shopper knows who hosts it",
      _scfg["platform"]["name"] == legal.PRODUCT_NAME)
check("and no gaps are reported once complete", _scfg["gaps"] == [])

_ssm = c.get(f"/s/{_handle}/sitemap.xml")
check("the shop's sitemap includes its legal pages",
      _ssm.status_code == 200 and _ssm.text.count("/legal/") == 3, _ssm.status_code)

check("an invalid refund choice falls back rather than publishing nonsense",
      sitebuilder._refund_id("whatever-i-typed") == "7day")
check("a valid one is honoured", sitebuilder._refund_id("exchange") == "exchange")

# =========================================================================
print("\n== the craft rules, checked as facts ==")
# =========================================================================
EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]")
_new_files = {
    "legal.py": (ROOT / "backend/core/legal.py").read_text(encoding="utf-8"),
    "legal_html.py": (ROOT / "backend/core/legal_html.py").read_text(encoding="utf-8"),
    "consent.js": CONSENT_JS,
}
for name, body in _new_files.items():
    check(f"{name} contains no em dashes", "—" not in body and "–" not in body)
    check(f"{name} contains no emoji", not EMOJI.search(body))

for slug in ("privacy", "terms", "refunds", "cookies", "acceptable-use", "grievance"):
    _p = legal_html.page(slug)
    check(f"the rendered {slug} page has no em dash", "—" not in _p)
    check(f"and no emoji", not EMOJI.search(_p))
check("nor does the legal hub", "—" not in legal_html.hub())
check("nor a shop's own policy page", "—" not in _shop_refunds)

check("no purple anywhere in the legal styling",
      not re.search(r"#6[dD]28[dD]9|purple|violet", legal_html._CSS))
check("no pill-shaped buttons in the consent bar",
      not re.search(r"border-radius:\s*(?:99+px|9999px|50px)", CONSENT_JS))
check("no fake metrics or invented reviews in any legal copy",
      not re.search(r"\b(?:5 star|thousands of|trusted by|[0-9,]+\+ (?:sellers|customers))\b",
                    " ".join(_new_files.values()), re.I))

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
