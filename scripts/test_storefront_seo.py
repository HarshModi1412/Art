"""The SEO of the shops this app builds FOR sellers, and domain readiness.

WHY THIS IS A SEPARATE FILE FROM THE APP'S OWN SEO
--------------------------------------------------
The instruction was "do this for my web app and the custom web app you create
for sellers also", and the second half is the harder one. A seller's shop is a
one-page app: everything a shopper reads is drawn by JavaScript after load, so
the HTML a crawler is first handed is an empty div and a spinner.

Google will usually render the JavaScript eventually. Every other crawler that
matters to an Indian seller does not render at all: WhatsApp's link preview,
which is where most of these links are actually shared, Facebook's, and Bing's.
So the shop's name, its products, its prices and its policy links are put into
the HTML itself, server side, and this file checks that they are really there
with JavaScript switched off.

The second half is domain readiness. The app used to build every absolute URL
from `request.url.scheme`, which behind Render's TLS terminator is "http" on
every request to an https-only site. That put `http://` in every canonical tag
and every og:url, which is a page telling Google its canonical version is a
different URL from the one being crawled, and it is one of the ordinary reasons
a site does not appear in search. Nothing logged it. See backend/core/publicurl.py.

Run: python3 scripts/test_storefront_seo.py
"""
import json
import os
import re
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("LAUNCH_MODE", "true")

from fastapi.testclient import TestClient  # noqa: E402
from backend.main import app  # noqa: E402
from backend.core import publicurl, sitebuilder  # noqa: E402

PASS = FAIL = 0


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        print(f"  ✗ {label}  <-- {extra}")


class Headers(dict):
    """Something with the .get a real Headers object has."""
    def get(self, k, d=""):
        return dict.get(self, k, d)


c = TestClient(app)
T = uuid.uuid4().hex[:8]
EM = f"ssseo-{T}@test.co"
HANDLE = f"kaya{T}"

tok = c.post("/api/register", json={"email": EM, "password": "pw123456"}).json()["token"]
H = {"Authorization": "Bearer " + tok, "X-Session-Id": "ss" + T}

c.post("/api/products/item", headers=H, json={
    "name": "Kaya Card Holder", "category": "Wallets", "price": 1499, "stock": 12,
    "description": "Full grain leather, hand stitched in Chennai."})
c.post("/api/products/item", headers=H, json={
    "name": "Everyday Belt", "category": "Belts", "price": 2199, "stock": 0,
    "description": "Brass buckle, 35mm."})
cat = c.get("/api/products/state", headers=H).json()["products"]
# By name, not by position: the catalogue is not returned in insertion order, and
# a test that depends on that order fails for a reason that has nothing to do
# with what it is testing.
CARD = next(p for p in cat if p["name"] == "Kaya Card Holder")
PID = CARD["id"]

site = c.get("/api/site/state", headers=H).json()["site"]
site.update({"handle": HANDLE, "brand": "Kaya Leather",
             "tagline": "Hand-stitched wallets from Chennai"})
site["trust"] = {**(site.get("trust") or {}),
                 "business_name": "Meera Rao",
                 "address": "12 MG Road, Bengaluru 560001",
                 "support_email": "hi@kaya.in", "support_phone": "9876543210",
                 "grievance_name": "Meera Rao", "refund_policy": "7day"}
c.post("/api/site/save", headers=H, json={"site": site})

# =========================================================================
print("\n== an unpublished shop must never be indexed ==")
# =========================================================================
# It is reachable by its owner with a preview token. A half-built shop appearing
# in a search result is a bad first impression that outlives the launch.
_pre = c.get(f"/s/{HANDLE}")
if _pre.status_code == 200:
    check("a preview of an unpublished shop says noindex",
          'content="noindex, nofollow"' in _pre.text)
else:
    check("an unpublished shop is not served at all", _pre.status_code == 404)

r = c.post("/api/site/publish", headers=H, json={"published": True})
check("the shop publishes once its details are filled in", r.status_code == 200, r.text[:120])

SHOP = c.get(f"/s/{HANDLE}").text
check("and a published shop says index", 'content="index, follow"' in SHOP)

# =========================================================================
print("\n== a crawler that cannot run JavaScript still sees a shop ==")
# =========================================================================
check("the shop's name is in the HTML itself", "Kaya Leather" in SHOP)
check("as the page's one h1", SHOP.count("<h1") == 1)
check("its tagline too", "Hand-stitched wallets" in SHOP)
check("every product is named", all(p["name"] in SHOP for p in cat),
      [p["name"] for p in cat if p["name"] not in SHOP])
check("with a price", "1,499" in SHOP and "2,199" in SHOP)
check("and a real link to its own page",
      SHOP.count('href="/s/%s/p/' % HANDLE) >= 2)
check("the policy pages are linked, so a crawler can reach them",
      all(f"/s/{HANDLE}/legal/{s}" in SHOP for s in ("privacy", "terms", "refunds")))
check("the fallback is a real element the app can remove",
      'id="seoFallback"' in SHOP)
STORE_JS = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "Smart CafeX/storefront/store.js"), encoding="utf-8").read()
check("and the app does remove it once it paints",
      'el("seoFallback")' in STORE_JS and "_seo.remove()" in STORE_JS)
STORE_CSS = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "Smart CafeX/storefront/store.css"), encoding="utf-8").read()
check("it is not hidden with display:none, which would be cloaking",
      "#seoFallback" in STORE_CSS and "display: none" not in
      STORE_CSS.split("#seoFallback")[1][:400])

# =========================================================================
print("\n== structured data, built from the seller's own catalogue ==")
# =========================================================================
_ld = re.search(r'application/ld\+json">(.*?)</script>', SHOP, re.S)
check("the shop page carries structured data", bool(_ld))
graph = json.loads(_ld.group(1))["@graph"]
types = [n["@type"] for n in graph]
check("it declares the shop as a Store", "Store" in types, types)
check("and lists the catalogue, which JavaScript would otherwise hide",
      "ItemList" in types, types)
store = next(n for n in graph if n["@type"] == "Store")
check("the shop is named", store["name"] == "Kaya Leather")
check("with the address the seller entered", "12 MG Road" in str(store.get("address")))
check("their phone and email", store.get("telephone") == "9876543210"
      and store.get("email") == "hi@kaya.in")
check("and their legal name where it differs from the brand",
      store.get("legalName") == "Meera Rao")
check("no invented rating", "aggregateRating" not in _ld.group(1))
check("and no invented reviews", '"Review"' not in _ld.group(1))
items = next(n for n in graph if n["@type"] == "ItemList")
check("every product is in the list", items["numberOfItems"] == len(cat))

PP = c.get(f"/s/{HANDLE}/p/{PID}").text
pld = json.loads(re.search(r'application/ld\+json">(.*?)</script>', PP, re.S).group(1))["@graph"]
ptypes = [n["@type"] for n in pld]
check("a product page declares a Product", "Product" in ptypes, ptypes)
check("with a breadcrumb, so the result shows a path not a raw URL",
      "BreadcrumbList" in ptypes)
prod = next(n for n in pld if n["@type"] == "Product")
check("the product is named", prod["name"] == "Kaya Card Holder")
check("with the seller's own description", "Full grain leather" in prod.get("description", ""))
check("and the brand", prod["brand"]["name"] == "Kaya Leather")
check("the offer carries the real price", prod["offers"]["price"] == "1499.00")
check("in rupees", prod["offers"]["priceCurrency"] == "INR")
check("and says it is in stock, because it is",
      prod["offers"]["availability"].endswith("InStock"))

# The out-of-stock one must say so. Claiming availability you do not have is a
# misleading description of goods, not just bad schema.
OOS = next(p for p in cat if p["name"] == "Everyday Belt")
oos_page = c.get(f"/s/{HANDLE}/p/{OOS['id']}").text
oos = next(n for n in json.loads(
    re.search(r'application/ld\+json">(.*?)</script>', oos_page, re.S).group(1)
)["@graph"] if n["@type"] == "Product")
check("a sold-out product says OutOfStock rather than claiming otherwise",
      oos["offers"]["availability"].endswith("OutOfStock"))

# A product with no price must have no offer at all, rather than an invented one.
c.post("/api/products/item", headers=H, json={"name": "Made to order tote", "stock": 3})
noprice = next(p for p in c.get("/api/products/state", headers=H).json()["products"]
               if p["name"] == "Made to order tote")
np_page = c.get(f"/s/{HANDLE}/p/{noprice['id']}").text
np = next(n for n in json.loads(
    re.search(r'application/ld\+json">(.*?)</script>', np_page, re.S).group(1)
)["@graph"] if n["@type"] == "Product")
check("a product with no price gets no offer, rather than a made-up one",
      "offers" not in np, np.get("offers"))

# =========================================================================
print("\n== readable addresses ==")
# =========================================================================
check("a product's slug reads as what it is",
      sitebuilder.product_slug({"name": "Kaya Card Holder", "id": "abc123"})
      == "kaya-card-holder-abc123")
check("punctuation and double spaces collapse",
      sitebuilder.product_slug({"name": "Wallet  &  Belt Set!!", "id": "ef56"})
      == "wallet-belt-set-ef56")
check("a name that transliterates to nothing keeps the bare id",
      sitebuilder.product_slug({"name": "सादा बटुआ", "id": "ab12"}) == "ab12")
check("the id comes back out of the slug",
      sitebuilder.product_id_from_slug("kaya-card-holder-abc123") == "abc123")
check("a bare id still resolves, so old shared links never break",
      sitebuilder.product_id_from_slug("abc123") == "abc123")
check("and so does a slug whose name is out of date after a rename",
      sitebuilder.product_id_from_slug("some-old-name-abc123") == "abc123")

slug = sitebuilder.product_slug(CARD)
check("the readable URL serves the same page",
      c.get(f"/s/{HANDLE}/p/{slug}").status_code == 200)
check("and the bare id still does too",
      c.get(f"/s/{HANDLE}/p/{PID}").status_code == 200)
check("both name the readable one as canonical, so there is one page not two",
      re.search(r'rel="canonical" href="([^"]+)"', PP).group(1).endswith(slug),
      re.search(r'rel="canonical" href="([^"]+)"', PP).group(1))
check("the sitemap uses the readable form",
      slug in c.get(f"/s/{HANDLE}/sitemap.xml").text)

# =========================================================================
print("\n== the shop's sitemap ==")
# =========================================================================
sm = c.get(f"/s/{HANDLE}/sitemap.xml")
check("it exists", sm.status_code == 200)
check("it lists the shop, every product and the three legal pages",
      sm.text.count("<loc>") == 1 + len(c.get("/api/products/state", headers=H)
                                        .json()["products"]) + 3,
      sm.text.count("<loc>"))
check("no URL in it 404s",
      all(c.get(u.replace("http://testserver", "")).status_code == 200
          for u in re.findall(r"<loc>([^<]+)</loc>", sm.text)),
      [u for u in re.findall(r"<loc>([^<]+)</loc>", sm.text)
       if c.get(u.replace("http://testserver", "")).status_code != 200])

# =========================================================================
print("\n== the link preview, which is where these are really shared ==")
# =========================================================================
check("a product page has its own title", "<title>Kaya Card Holder" in PP)
check("using a pipe rather than an em dash", "|" in
      re.search(r"<title>(.*?)</title>", PP).group(1))
check("a description", 'name="description"' in PP)
check("Open Graph tags, which is what WhatsApp reads",
      all(f'property="og:{k}"' in PP for k in ("title", "description", "url")))
check("and a Twitter card", 'name="twitter:card"' in PP)
check("the shop's own page has its own title, not the product's",
      "Kaya Leather" in re.search(r"<title>(.*?)</title>", SHOP).group(1))

# =========================================================================
print("\n== https and the day a custom domain is connected ==")
# =========================================================================
check("a public host is https even when the proxy sends no header",
      publicurl.base_url("smart-helper-c3oy.onrender.com", "http", Headers())
      == "https://smart-helper-c3oy.onrender.com")
check("the request's own scheme is ignored for a public host, which is the bug",
      "https://" in publicurl.base_url("example.in", "http", Headers()))
check("a proxy that says https is believed",
      publicurl.base_url("example.in", "http",
                         Headers({"x-forwarded-proto": "https"})).startswith("https"))
check("a proxy that says http is believed too, so a local proxy still works",
      publicurl.base_url("example.in", "http",
                         Headers({"x-forwarded-proto": "http"})).startswith("http:"))
check("localhost stays http, so development is not broken",
      publicurl.base_url("127.0.0.1:8000", "http", Headers())
      == "http://127.0.0.1:8000")
check("a forwarded host is used when a proxy rewrites it",
      publicurl.base_url("internal:10000", "http",
                         Headers({"x-forwarded-host": "shop.kaya.in",
                                  "x-forwarded-proto": "https"}))
      == "https://shop.kaya.in")

os.environ["PUBLIC_BASE_URL"] = "onetapmanager.in"
import importlib  # noqa: E402
importlib.reload(publicurl)
check("one environment variable moves the whole app to a new domain",
      publicurl.base_url("anything", "http", Headers()) == "https://onetapmanager.in")
check("and it does not need the scheme typing out",
      publicurl.configured() == "https://onetapmanager.in")
os.environ.pop("PUBLIC_BASE_URL")
importlib.reload(publicurl)

check("a plain http request is redirected",
      publicurl.should_redirect_to_https("example.in",
                                         Headers({"x-forwarded-proto": "http"})) is True)
check("but NEVER on the strength of the request's own scheme, which would loop "
      "forever behind a TLS terminator and take every shop down with it",
      publicurl.should_redirect_to_https("example.in", Headers()) is False)
check("and never on localhost",
      publicurl.should_redirect_to_https("localhost", Headers({"x-forwarded-proto": "http"}))
      is False)

_r = c.get("/", headers={"host": "example.in", "x-forwarded-proto": "http"},
           follow_redirects=False)
check("the app really does redirect, end to end", _r.status_code == 301, _r.status_code)
check("to the same URL on https", _r.headers.get("location", "").startswith("https://"),
      _r.headers.get("location"))
_ok = c.get("/", headers={"host": "example.in", "x-forwarded-proto": "https"})
check("an https request is served, with HSTS on it",
      _ok.status_code == 200 and "max-age=" in _ok.headers.get("Strict-Transport-Security", ""),
      _ok.headers.get("Strict-Transport-Security"))
check("HSTS does not claim anything about subdomains we do not control",
      "includeSubDomains" not in _ok.headers.get("Strict-Transport-Security", ""))

# The landing page's own absolute URLs follow the host, so a canonical tag can
# never be left pointing at the old address after a move. That is the classic way
# a site vanishes from search the week it gets its real domain.
_land = c.get("/", headers={"host": "onetapmanager.in", "x-forwarded-proto": "https"}).text
check("the landing page has no hardcoded hostname left", "__BASE_URL__" not in _land)
check("its canonical follows the host it was served on",
      re.search(r'rel="canonical" href="([^"]+)"', _land).group(1)
      == "https://onetapmanager.in/")
check("and so does its social card",
      "https://onetapmanager.in/og-image.png" in _land)
check("and the identifiers in its structured data",
      _land.count("https://onetapmanager.in/#org") >= 2)

_sm = c.get("/sitemap.xml", headers={"host": "onetapmanager.in",
                                     "x-forwarded-proto": "https"}).text
check("the app's sitemap follows it too",
      "https://onetapmanager.in/" in _sm and "onrender" not in _sm)
_rb = c.get("/robots.txt", headers={"host": "onetapmanager.in",
                                    "x-forwarded-proto": "https"}).text
check("and robots.txt points at the sitemap on the new domain",
      "https://onetapmanager.in/sitemap.xml" in _rb, _rb[-80:])

# A seller's own domain is a separate thing, and must NOT be rewritten to ours.
_shop_on_own = c.get("/", headers={"host": f"{HANDLE}.example.in",
                                   "x-forwarded-proto": "https"})
check("a request on an unknown host still serves the app rather than failing",
      _shop_on_own.status_code == 200)

# =========================================================================
print("\n== proving the site is ours, and where to report a hole ==")
# =========================================================================
# Search Console shows nothing at all about a site until ownership is proved.
# Two ways that need no DNS access: a file at a path Google names, or a meta tag.
# The file survives a domain move, so it is the one the checklist leads with.
check("with nothing configured, the verification path 404s",
      c.get("/googleanything.html").status_code == 404)
os.environ["GOOGLE_SITE_VERIFICATION"] = "abc123def456"
check("once set, Google's file is served at the exact path it asks for",
      c.get("/googleabc123def456.html").status_code == 200)
check("with the content Google looks for",
      "google-site-verification: googleabc123def456.html"
      in c.get("/googleabc123def456.html").text)
check("a wrong token still 404s, so the value cannot be probed for",
      c.get("/googlewrong.html").status_code == 404)
check("the value is taken as pasted, prefix and suffix and all",
      (lambda: (os.environ.__setitem__("GOOGLE_SITE_VERIFICATION",
                                       "googleabc123def456.html"),
                c.get("/googleabc123def456.html").status_code)[1])() == 200)
os.environ.pop("GOOGLE_SITE_VERIFICATION", None)

os.environ["SUPPORT_EMAIL"] = "care@example.in"
import importlib as _il  # noqa: E402
from backend.core import legal as _legal  # noqa: E402
_il.reload(_legal)
_sec = c.get("/.well-known/security.txt")
check("security.txt is published at the path RFC 9116 specifies",
      _sec.status_code == 200)
check("and at the one people actually try first",
      c.get("/security.txt").status_code == 200)
check("it names a real contact", "mailto:care@example.in" in _sec.text)
check("and carries an expiry, which the RFC requires", "Expires:" in _sec.text)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
