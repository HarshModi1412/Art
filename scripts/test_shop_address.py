"""A shop's addresses: onetapmanager.com/<company>, /s/<handle>, and its own domain.

THE BUGS THIS GUARDS
--------------------
1. A seller saved their own domain, saw it in the form afterwards, and the
   domain still did not open their shop. The domain was stored in the site
   config in Supabase, but the domain -> handle map the router reads lived only
   in data/site_index.json, which Render does not keep across a redeploy. The
   section below that wipes the local index is that exact scenario.
2. The default address is onetapmanager.com/<company name>, not /s/<handle>:
   made from the company name, served at the root, canonical in that form, and
   never allowed to take over a route the app itself answers on.

Run: python3 scripts/test_shop_address.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import re, uuid, logging
os.environ.setdefault("LAUNCH_MODE", "true")
logging.disable(logging.CRITICAL)
from fastapi.testclient import TestClient
from backend.main import app
from backend.core import ratelimit, sitebuilder, db

ratelimit.reset()
c = TestClient(app)
T = uuid.uuid4().hex[:6]
ok = fail = 0


def check(label, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1; print(f"  ✓ {label}")
    else:
        fail += 1; print(f"  ✗ {label}  <-- {extra}")


def acct(tag):
    tok = c.post("/api/register", json={"email": f"{tag}{T}@t.co", "password": "pw123456"}).json()["token"]
    return {"Authorization": "Bearer " + tok, "X-Session-Id": tag + T}


H = acct("kora")
site = c.get("/api/site/state", headers=H).json()["site"]
brand = f"Kora Studio {T}"
site.update({"brand": brand, "custom_domain": f"kora{T}.com"})
site["trust"] = {**(site.get("trust") or {}), "business_name": "Meera Rao",
                 "address": "12 MG Road, Bengaluru 560001", "support_email": "hi@kora.in",
                 "support_phone": "9876543210", "grievance_name": "Meera Rao", "refund_policy": "7day"}
r = c.post("/api/site/save", headers=H, json={"site": site})
check("save succeeds", r.status_code == 200, r.text[:200])
s2 = c.get("/api/site/state", headers=H).json()["site"]
HANDLE = s2["handle"]
print("   handle =", HANDLE)
check("default address is made from the company name", HANDLE == sitebuilder.normalise_handle(brand), HANDLE)
check("custom domain is saved", s2["custom_domain"] == f"kora{T}.com", s2["custom_domain"])
c.post("/api/products/item", headers=H, json={"name": "Card Holder", "price": 1499, "stock": 5})
check("publishes", c.post("/api/site/publish", headers=H, json={"published": True}).status_code == 200)

print("\n== onetapmanager.com/<company> ==")
home = c.get(f"/{HANDLE}")
check("/<company> serves the shop", home.status_code == 200 and brand in home.text, home.status_code)
canon = re.search(r'rel="canonical" href="([^"]+)"', home.text).group(1)
check("its canonical is the short address", canon.endswith(f"/{HANDLE}"), canon)
check("links on it use the short form", f'href="/{HANDLE}/p/' in home.text)
check("trailing slash works too", c.get(f"/{HANDLE}/").status_code == 200)
pid = [p for p in c.get("/api/products/state", headers=H).json()["products"] if p["name"] == "Card Holder"][0]
slug = sitebuilder.product_slug(pid)
check("/<company>/p/<product> serves the product", c.get(f"/{HANDLE}/p/{slug}").status_code == 200)
check("/<company>/legal/privacy serves the policy", c.get(f"/{HANDLE}/legal/privacy").status_code == 200)
sm = c.get(f"/{HANDLE}/sitemap.xml")
check("/<company>/sitemap.xml exists", sm.status_code == 200)
locs = re.findall(r"<loc>([^<]+)</loc>", sm.text)
check("sitemap uses the short address", locs and all(f"/{HANDLE}" in u and "/s/" not in u for u in locs), locs[:2])
check("no URL in the sitemap 404s",
      all(c.get(u.replace("http://testserver", "")).status_code == 200 for u in locs))

print("\n== the old /s/ address keeps working ==")
old = c.get(f"/s/{HANDLE}")
check("/s/<company> still serves", old.status_code == 200)
check("its links keep the /s/ form", f'href="/s/{HANDLE}/p/' in old.text)
oc = re.search(r'rel="canonical" href="([^"]+)"', old.text).group(1)
check("and it points search engines at the short address", oc.endswith(f"/{HANDLE}") and "/s/" not in oc, oc)

print("\n== the app's own pages are never taken over ==")
check("/ is still the landing page", "run your shop the way a big brand" in c.get("/").text.lower())
check("/legal is still the platform legal hub", c.get("/legal").status_code == 200 and brand not in c.get("/legal").text)
check("/healthz untouched", c.get("/healthz").json().get("ok") is True)
check("unknown word 404s rather than erroring", c.get("/wp-admin").status_code == 404)
H2 = acct("thief")
s3 = c.get("/api/site/state", headers=H2).json()["site"]
s3.update({"brand": "Thief", "handle": "legal"})
check("a seller cannot claim a route name as their address",
      c.post("/api/site/save", headers=H2, json={"site": s3}).status_code == 400)
check("handle-check says a route name is taken",
      c.get("/api/site/handle-check?handle=healthz", headers=H2).json().get("available") is False)

print("\n== custom domain survives a wiped local index (the actual bug) ==")
check("routes by domain while the local file has it",
      brand in c.get("/", headers={"host": f"kora{T}.com"}).text)
# Simulate Render wiping site_index.json on redeploy, with Supabase holding the row.
idx = sitebuilder._read_index(); idx.get(sitebuilder.DOMAIN_KEY, {}).pop(f"kora{T}.com", None)
idx.get(sitebuilder.DOMAIN_KEY, {}).pop(f"www.kora{T}.com", None); sitebuilder._write_index(idx)
sitebuilder._domain_cache.clear()
real_enabled, real_fetch = db.SUPABASE_ENABLED, db.fetch_one
calls = []
def fake_fetch(table, match):
    calls.append((table, match))
    if table == "sites" and match.get("config->>custom_domain") == f"kora{T}.com":
        return {"handle": HANDLE, "email": f"kora{T}@t.co"}
    if table == "sites" and match.get("handle") == HANDLE:
        return {"handle": HANDLE, "email": f"kora{T}@t.co"}
    return None
db.SUPABASE_ENABLED, db.fetch_one = True, fake_fetch
sitebuilder.db.SUPABASE_ENABLED = True
try:
    check("resolves from Supabase after the file is gone",
          sitebuilder.resolve_domain(f"kora{T}.com") == HANDLE)
    sitebuilder._domain_cache.clear()
    check("the www form resolves too", sitebuilder.resolve_domain(f"www.kora{T}.com") == HANDLE)
    n = len(calls)   # www. was just resolved, so the bare domain is cached with it
    sitebuilder.resolve_domain(f"kora{T}.com"); sitebuilder.resolve_domain(f"www.kora{T}.com")
    check("repeat lookups are cached, both forms, not re-queried", len(calls) == n, len(calls) - n)
    calls.clear()
    os.environ["PUBLIC_BASE_URL"] = "https://onetapmanager.com"   # as set in production
    c.get("/", headers={"host": "onetapmanager.com", "x-forwarded-proto": "https"})
    c.get("/", headers={"host": "www.onetapmanager.com", "x-forwarded-proto": "https"})
    os.environ.pop("PUBLIC_BASE_URL", None)
    check("the landing page on our own host does no domain lookup",
          not any("config->>custom_domain" in m for _, m in calls), calls)
finally:
    db.SUPABASE_ENABLED, db.fetch_one = real_enabled, real_fetch
    sitebuilder.db.SUPABASE_ENABLED = real_enabled

print("\n== placeholder address upgrades to the company name ==")
H3 = acct("late")
s4 = c.get("/api/site/state", headers=H3).json()["site"]
c.post("/api/site/save", headers=H3, json={"site": s4})
h_before = c.get("/api/site/state", headers=H3).json()["site"]["handle"]
check("with no name yet it gets a placeholder", sitebuilder.is_placeholder_handle(h_before), h_before)
s5 = c.get("/api/site/state", headers=H3).json()["site"]; s5["brand"] = f"Late Bloom {T}"
c.post("/api/site/save", headers=H3, json={"site": s5})
h_after = c.get("/api/site/state", headers=H3).json()["site"]["handle"]
check("naming the company gives it the company's address", h_after == sitebuilder.normalise_handle(f"Late Bloom {T}"), h_after)

print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
