"""
Guard for the Sub-Category Analysis bug: storefront orders (the default sales
source now, not a CSV upload) never had a sub-category, and site_sales_frame()
used to fill that column with "" rather than leaving it empty. pandas'
.notna() reports "" as present, so _dimension_col() always picked the blank
sub-category column over category, and every seller whose sales came from
their own site saw one nameless bucket owning "100% of all your money"
instead of their real categories.

Two things have to both be true:
  1. A seller with ONLY storefront orders gets real category names, not a
     blank bucket.
  2. A seller who genuinely uploaded a file WITH sub-category data still gets
     it (the fallback must not swallow real sub-category data).

Run: python3 scripts/test_analytics_backend.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from backend.core import smart  # noqa: E402

PASS = FAIL = 0


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}{(' (' + str(extra) + ')') if extra else ''}")
    else:
        FAIL += 1
        print(f"  ✗ {label}  <-- {extra}")


c = TestClient(app)

print("\n== 1. storefront-only seller: real category names, not a blank bucket ==")

email = f"an{int(time.time() * 1000)}@t.co"
tok = c.post("/api/register", json={"email": email, "password": "Test12345!"}).json()["token"]
H = {"Authorization": "Bearer " + tok, "X-Session-Id": "an-sess"}

c.post("/api/products/item", json={"name": "Cotton Kurta", "category": "Clothing",
       "price": 999, "stock": 50}, headers=H)
pid = c.get("/api/products/state", headers=H).json()["products"][0]["id"]
c.post("/api/site/seed", headers=H)
handle = f"antest{int(time.time() * 1000) % 10**8}"
c.post("/api/site/save", json={"site": {"handle": handle, "brand": "AN Test"}}, headers=H)
c.post("/api/site/publish", json={"published": True}, headers=H)
r = c.post(f"/api/shop/{handle}/order", json={
    "lines": [{"product_id": pid, "qty": 2}],
    "address": {"name": "Buyer", "phone": "9876543210", "line1": "MG Road",
                "city": "Bengaluru", "pincode": "560001"},
    "payment": "cod", "guest": True, "name": "Buyer", "phone": "9876543210",
})
check("order placed", r.status_code == 200, r.text[:200])

d = c.get("/api/smart/state", headers=H).json()
check("account's Sales data is marked ready off one storefront order",
      (d.get("data", {}).get("sales") or {}).get("ready") is True)

r = c.get("/api/subcategory", headers=H)
body = r.json()
check("subcategory endpoint answers 200", r.status_code == 200, r.status_code)
check("it falls back to category, not the blank sub-category column",
      body.get("field") == "category", body.get("field"))
check("the value shown is the real category, not blank",
      body.get("all_values") == ["Clothing"], body.get("all_values"))
check("no nameless bucket in the insights text",
      body.get("insights") and "Clothing" in body["insights"][0]["text"]
      and body["insights"][0]["text"].count("  ") == 0,
      body.get("insights", [{}])[0].get("text"))

r = c.get("/api/analytics", headers=H)
check("Sales Analytics still answers 200 for the same account", r.status_code == 200, r.status_code)
check("and reports the real revenue", r.json().get("kpis", {}).get("revenue") == 1998.0,
      r.json().get("kpis"))

print("\n== 2. a genuine sub-category upload is not swallowed by the fallback ==")

email2 = f"mix{int(time.time() * 1000)}@t.co"
tok2 = c.post("/api/register", json={"email": email2, "password": "Test12345!"}).json()["token"]
H2 = {"Authorization": "Bearer " + tok2, "X-Session-Id": "mix-sess"}

rows = [{"date": f"2026-08-{(i % 28) + 1:02d}", "order_id": f"U{i}", "customer_id": f"c{i}",
         "customer_name": f"Cust {i}", "product": "Silk Saree", "category": "Clothing",
         "subcategory": "Saree", "quantity": 1, "amount": 2500} for i in range(10)]
df = pd.DataFrame(rows)
df["date"] = pd.to_datetime(df["date"])
smart.save_sales(email2, df, {"source": "upload", "filename": "past sales"}, mode="replace")

r = c.get("/api/subcategory", headers=H2)
body2 = r.json()
check("a real, mostly-populated sub-category column still wins the fallback",
      body2.get("field") == "subcategory", body2.get("field"))
check("and its actual value comes through", body2.get("all_values") == ["Saree"],
      body2.get("all_values"))

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
