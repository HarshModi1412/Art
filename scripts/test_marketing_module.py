"""
Regression guard for the Marketing module: win-back campaigns used to be
reachable only through an Approval-panel card the insight engine generated
on its own schedule, so a seller checking on it between those moments had
nowhere to go. The Marketing module (Home tile "Marketing") calls the same
endpoints directly, any time, whether or not an insight card exists right
now.

Covers the two states the module has to render sanely: a fresh account with
no sales data yet (the winback endpoint 400s -- the module shows an
explainer, not a crash), and an account with genuine at-risk customers (the
list, the proof-of-results line, and the campaign-history line all resolve).

Run: python3 scripts/test_marketing_module.py
"""
import datetime
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
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        print(f"  ✗ {label}  <-- {extra}")


c = TestClient(app)

print("\n== 1. fresh account, no sales data yet ==")
email = f"mkfresh{int(time.time() * 1000)}@t.co"
tok = c.post("/api/register", json={"email": email, "password": "Test12345!"}).json()["token"]
H = {"Authorization": "Bearer " + tok, "X-Session-Id": "mk-sess"}

r = c.post("/api/rfm/winback", headers=H)
check("winback endpoint 400s cleanly -- the module catches this and explains, not a crash",
      r.status_code == 400, r.status_code)
r2 = c.get("/api/rfm/winback/proof", headers=H)
check("proof endpoint still 200s with no data (module hides the proof line)",
      r2.status_code == 200, r2.text[:200])
r3 = c.get("/api/rfm/winback/sends", headers=H)
check("campaign-history endpoint still 200s with no data",
      r3.status_code == 200 and r3.json().get("sends") == [], r3.json())

print("\n== 2. account with genuine at-risk customers ==")
email2 = f"mkrisk{int(time.time() * 1000)}@t.co"
tok2 = c.post("/api/register", json={"email": email2, "password": "Test12345!"}).json()["token"]
H2 = {"Authorization": "Bearer " + tok2, "X-Session-Id": "mk-sess2"}

# Repeat customers whose last order was 90+ days ago -> RFM "At Risk" segment.
old = datetime.date.today() - datetime.timedelta(days=120)
rows = [{"date": (old - datetime.timedelta(days=j * 20)).isoformat(),
         "order_id": f"W{i}-{j}", "customer_id": f"cust{i}", "customer_name": f"Customer {i}",
         "product": "Silk Saree", "category": "Clothing", "subcategory": "Saree",
         "quantity": 1, "amount": 2000}
        for i in range(6) for j in range(3)]
df = pd.DataFrame(rows)
df["date"] = pd.to_datetime(df["date"])
smart.save_sales(email2, df, {"source": "upload", "filename": "past sales"}, mode="replace")

r = c.post("/api/rfm/winback", headers=H2)
check("winback endpoint 200s once there's order history", r.status_code == 200, r.text[:300])
customers = r.json().get("customers", [])
check("at least one at-risk customer comes back -- this is what the module lists",
      len(customers) > 0, len(customers))

r2 = c.get("/api/rfm/winback/proof", headers=H2)
check("proof endpoint 200s", r2.status_code == 200, r2.json())

r3 = c.get("/api/rfm/winback/sends", headers=H2)
check("campaign-history endpoint 200s, empty for a fresh account",
      r3.status_code == 200 and r3.json().get("sends") == [], r3.json())

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
