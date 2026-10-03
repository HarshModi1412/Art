"""
Product reviews on the website, and reviews from platforms, in Review Analytics.

  1. Only a customer who bought the product can review it; one review per
     customer per product (writing again updates it).
  2. Visible reviews are part of the Review data as source "site", next to
     uploaded reviews, which are never touched by it. Hiding takes a review
     out of the product page AND the analysis.
  3. WooCommerce / Wix reviews come in with an orders pull, as their own
     source; Shopify / Amazon say plainly they have no reviews API.

Run: python scripts/test_store_reviews.py
"""
from __future__ import annotations

import os
import secrets
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["CAFEX_DATA_DIR"] = tempfile.mkdtemp(prefix="rev_")
os.environ.setdefault("LAUNCH_MODE", "true")
os.environ["AUTOPLAN_SCHEDULER"] = "off"

import pandas as pd  # noqa: E402

PASSED = FAILED = 0


def check(label, cond, extra=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  ✓ {label}")
    else:
        FAILED += 1
        print(f"  ✗ {label}" + (f"  [{extra}]" if extra else ""))


from fastapi.testclient import TestClient  # noqa: E402
from backend.main import app  # noqa: E402
from backend.core import commerce, smart  # noqa: E402

c = TestClient(app)
UQ = secrets.token_hex(3)
SELLER, HANDLE = f"rev{UQ}@shop.local", f"rev{UQ}"
H = {"Authorization": "Bearer " + c.post("/api/register", json={"email": SELLER, "password": "pw123456"}).json()["token"],
     "X-Session-Id": "rev-" + UQ}
pid = c.post("/api/products/item", headers=H, json={"name": "Mogra Attar", "category": "Fragrance",
                                                     "price": 549, "stock": 20, "track_stock": True}).json()["products"][0]["id"]
site = c.get("/api/site/state", headers=H).json()["site"]
site.update({"handle": HANDLE, "brand": "Rang Studio", "theme": "luxury"})
site["trust"].update({"business_name": "Rang Studio", "address": "1 MG Road, Pune 411001",
                      "support_email": "hi@rang.in", "support_phone": "9845000000", "grievance_name": "R"})
c.post("/api/site/save", headers=H, json={"site": site})
c.post("/api/site/publish", headers=H, json={"published": True})

# an uploaded review file already exists
smart.save_review(SELLER, pd.DataFrame({"review_text": ["Lovely smell, lasts all day", "Bottle leaked"],
                                        "stars": [5, 2]}), {})

print("\n== 1. only buyers review ==")
r = c.get(f"/api/shop/{HANDLE}/reviews?product_id={pid}")
check("anyone can read the reviews", r.status_code == 200 and r.json()["count"] == 0)
check("a visitor cannot write one", not r.json()["can_review"])
other = c.post(f"/api/shop/{HANDLE}/register", json={"email": f"x{UQ}@mail.com", "password": "pw123456",
                                                      "name": "Not Buyer"}).json()["token"]
r = c.post(f"/api/shop/{HANDLE}/reviews", headers={"X-Store-Token": other},
           json={"product_id": pid, "rating": 5, "text": "Great!"})
check("a signed-in customer who did not buy it is refused", r.status_code == 400 and "bought" in r.text, r.text)
addr = {"name": "Asha Kapoor", "phone": "9000000001", "line1": "1 First St", "city": "Pune",
        "state": "MH", "pincode": "411001"}
o = c.post(f"/api/shop/{HANDLE}/order", json={"lines": [{"product_id": pid, "qty": 1}], "address": addr,
                                              "guest": True, "name": "Asha Kapoor", "phone": "9000000001"}).json()
tok = o["token"]
r = c.get(f"/api/shop/{HANDLE}/reviews?product_id={pid}", headers={"X-Store-Token": tok})
check("after buying it, the form appears", r.json()["can_review"])
r = c.post(f"/api/shop/{HANDLE}/reviews", headers={"X-Store-Token": tok},
           json={"product_id": pid, "rating": 9, "text": "Lovely"})
check("a rating outside 1-5 is refused", r.status_code == 400)
r = c.post(f"/api/shop/{HANDLE}/reviews", headers={"X-Store-Token": tok},
           json={"product_id": pid, "rating": 4, "text": "Lovely jasmine notes, a little strong at first."})
d = r.json()
check("a buyer's review is posted", r.status_code == 200 and d["count"] == 1 and d["average"] == 4.0, r.text[:200])
check("shown with a short name and 'verified'", d["reviews"][0]["name"] == "Asha K." and d["reviews"][0]["verified"])
r = c.post(f"/api/shop/{HANDLE}/reviews", headers={"X-Store-Token": tok},
           json={"product_id": pid, "rating": 5, "text": "Grew on me. Now my favourite."})
check("writing again updates their review, it does not add a second",
      r.json()["count"] == 1 and r.json()["average"] == 5.0 and r.json()["mine"]["rating"] == 5)

print("\n== 2. part of Review Analytics ==")
rv = smart.load_review(SELLER)
check("website reviews are in the review data as 'site'",
      (rv["Source"] == "site").sum() == 1 and "Grew on me" in rv[rv["Source"] == "site"]["Review"].iloc[0], str(rv.tail(2)))
check("next to the uploaded ones, untouched", (rv["Source"] == "upload").sum() == 2)
check("in the same text column", rv["Review"].notna().all() and "review_text" not in rv.columns, list(rv.columns))
r = c.get("/api/smart/positioning?lang=en", headers=H)
src = {x["id"]: x["count"] for x in r.json().get("sources") or []}
check("Review Analytics says where its reviews came from", src == {"upload": 2, "site": 1}, str(src))
lst = c.get("/api/store/reviews", headers=H).json()["reviews"]
check("the seller sees them", len(lst) == 1 and lst[0]["product_name"] == "Mogra Attar")
c.post("/api/store/reviews/hide", headers=H, json={"id": lst[0]["id"], "hidden": True})
check("hiding takes it off the product page",
      c.get(f"/api/shop/{HANDLE}/reviews?product_id={pid}").json()["count"] == 0)
rv = smart.load_review(SELLER)
check("and out of the analysis", (rv["Source"] == "site").sum() == 0 and len(rv) == 2)
c.post("/api/store/reviews/hide", headers=H, json={"id": lst[0]["id"], "hidden": False})
check("showing it again puts it back", (smart.load_review(SELLER)["Source"] == "site").sum() == 1)
smart.save_review(SELLER, pd.DataFrame({"Review": ["Fresh upload"], "Rating": [3]}), {}, mode="replace")
rv = smart.load_review(SELLER)
check("re-uploading reviews replaces only the uploaded ones",
      (rv["Source"] == "upload").sum() == 1 and (rv["Source"] == "site").sum() == 1)

print("\n== 3. platforms ==")


class _R:
    def __init__(self, body, code=200):
        self._b, self.status_code, self.ok, self.text = body, code, code < 400, str(body)

    def json(self):
        return self._b


calls = []


def fake_get(url, auth=None, timeout=None, params=None):
    calls.append(url)
    if params and params.get("page", 1) > 1:
        return _R([])
    return _R([{"review": "<p>Great &amp; fast</p>", "rating": 5, "date_created": "2026-09-01T10:00:00",
                "product_name": "Linen Shirt", "reviewer": "Ravi"},
               {"review": "", "rating": 1}])


commerce.requests.get = fake_get
df = commerce.woocommerce_reviews({"store_url": "shop.example", "consumer_key": "k", "consumer_secret": "s"})
check("WooCommerce reviews are read, HTML stripped, empty ones skipped",
      len(df) == 1 and df["Review"].iloc[0] == "Great & fast" and df["Product"].iloc[0] == "Linen Shirt", str(df))


def fake_post(url, headers=None, timeout=None, json=None):
    return _R({"reviews": [{"content": {"title": "Nice", "body": "Good quality", "rating": 4},
                            "createdDate": "2026-09-02T00:00:00Z", "author": {"authorName": "Meera"}}]})


commerce.requests.post = fake_post
df = commerce.wix_reviews({"api_key": "k", "site_id": "s"})
check("Wix reviews are read", len(df) == 1 and df["Review"].iloc[0] == "Nice Good quality" and df["Rating"].iloc[0] == 4)
for conn in ("shopify", "amazon"):
    try:
        commerce.pull_reviews(conn, {})
        check(f"{conn}: says it has no reviews API", False)
    except commerce.CommerceError as e:
        check(f"{conn}: says it has no reviews API", str(e) == "not_supported")
smart.save_review(SELLER, pd.DataFrame(
    {"Review": ["From Woo"], "Rating": [5], "Date": ["2026-09-01"], "Product": ["X"], "Reviewer": ["Y"]}), {},
    source="woocommerce")
rv = smart.load_review(SELLER)
check("a platform's reviews are their own source",
      dict(rv["Source"].value_counts()) == {"upload": 1, "site": 1, "woocommerce": 1}, str(dict(rv["Source"].value_counts())))

print(f"\n{PASSED} passed, {FAILED} failed")
sys.exit(1 if FAILED else 0)
