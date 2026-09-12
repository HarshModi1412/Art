"""
The live deployment runs on Supabase; every other test runs on local JSON
files, where a table has no columns to get wrong. This one runs the app
against scripts/fake_supabase.py — fixed columns from supabase/schema.sql,
no NaN — and walks the paths that write to real tables.

It exists because "Draft the purchase orders" failed on the live site with
TransportProblem at db.py:201 (reference 89abbe75f0e1): purchase orders had
grown fields the `purchase_orders` table has no columns for, and PostgREST
refuses the whole row.

Run: python3 scripts/test_supabase_mode.py
"""
import os
import sys
import time
from datetime import date, timedelta

os.environ.setdefault("AUTOPLAN_SCHEDULER", "off")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from backend.core import db, messaging, replenish, smart, supply  # noqa: E402
from scripts.fake_supabase import APIError, install  # noqa: E402

PASS = FAIL = 0


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        print(f"  ✗ {label}  <-- {extra}")


fake = install()
c = TestClient(app, raise_server_exceptions=False)

print("\n== the fake refuses what Postgres refuses ==")
try:
    fake.table("purchase_orders").insert({"id": "x", "email": "a", "po_number": "x", "note": "hi"}).execute()
    refused = False
except APIError:
    refused = True
check("an unknown column is refused, like PostgREST (PGRST204)", refused)
try:
    fake.table("user_state").upsert({"email": "a", "state": {"v": float("nan")}}).execute()
    refused = False
except APIError:
    refused = True
check("NaN is refused, like Postgres JSONB", refused)
check("…but the app's own write path cleans NaN before it gets there",
      db.upsert("user_state", {"email": "nan@t.co", "state": {"v": float("nan")}}, on_conflict="email") is not None
      and fake.tables["user_state"][-1]["state"]["v"] is None)

print("\n== an account on the live setup ==")
email = f"live{int(time.time() * 1000)}@t.co"
r = c.post("/api/register", json={"email": email, "password": "Test12345!"})
check("register", r.status_code == 200, r.text[:200])
H = {"Authorization": "Bearer " + r.json().get("token", ""), "X-Session-Id": "live"}
r = c.post("/api/products/item", headers=H, json={"name": "Gucci Bag", "category": "Bags",
                                                  "price": 4999, "stock": 20})
check("add a product", r.status_code == 200, r.text[:200])
r = c.post("/api/supply/item", headers=H, json={
    "name": "Leather", "unit_label": "sqft", "current_stock": 10, "lead_time_days": 5, "moq": 50,
    "unit_cost": 90, "supplier_name": "Kanpur Leathers", "supplier_email": "po@kanpur.example",
    "supplier_phone": "+919811111111", "link_product": "Gucci Bag", "qty_per_unit": 2.5})
check("add a raw material linked to it", r.status_code == 200, r.text[:200])
r = c.post("/api/supply/item", headers=H, json={
    "name": "Zip", "unit_label": "pcs", "current_stock": 4, "lead_time_days": 4, "moq": 100,
    "supplier_name": "Zip Co", "supplier_email": "hi@zip.example", "link_product": "Gucci Bag",
    "qty_per_unit": 1})
check("and another from a second supplier", r.status_code == 200, r.text[:200])
end = date.today()
rows = [{"date": pd.Timestamp(end - timedelta(days=i)), "order_id": f"o{i}", "customer_id": f"c{i % 7}",
         "product": "Gucci Bag", "amount": 9998.0, "quantity": 2} for i in range(40)]
smart.save_sales(email, pd.DataFrame(rows), {"files": ["s.csv"]})
inv = {x["name"]: x for x in c.get("/api/supply/state", headers=H).json()["inventory"]}
check("both are below 1.2 × lead time", inv["Leather"]["needs_po"] and inv["Zip"]["needs_po"],
      {k: (v["dos"], v["dos_threshold"]) for k, v in inv.items()})

print("\n== 'Draft the purchase orders' — the button that failed live ==")
r = c.post("/api/smart/insight/reorder/decision", headers=H, json={"decision": "approve"})
check("answers 200, not TransportProblem", r.status_code == 200, r.text[:400])
pos = supply.get_purchase_orders(email)
check("one draft PO per supplier", sorted(p["supplier"]["name"] for p in pos if p["status"] == "draft")
      == ["Kanpur Leathers", "Zip Co"], [(p.get("po_number"), p.get("status"), p.get("supplier")) for p in pos])
row = next(x for x in fake.tables["purchase_orders"] if x["email"] == email)
check("the table row holds only the table's columns", set(row) <= fake.cols["purchase_orders"], sorted(row))
lp = next(p for p in pos if p["supplier"]["name"] == "Kanpur Leathers")
check("…and the rest of the PO comes back with it (supplier, note, history, source)",
      lp["supplier"]["email"] == "po@kanpur.example" and lp.get("note") and lp.get("history")
      and lp.get("source") == "auto", lp)

print("\n== the rest of the PO's life, on the live setup ==")
n = lp["po_number"]
r = c.get(f"/api/supply/po/{n}/detail", headers=H)
check("Details opens", r.status_code == 200, r.text[:300])
r = c.post(f"/api/supply/po/{n}/lines", headers=H,
           json={"qty": {lp["lines"][0]["inventory_id"]: 120}})
check("quantities can be changed", r.status_code == 200
      and supply.get_po(email, n)["lines"][0]["order_qty"] == 120, r.text[:300])
r = c.post(f"/api/supply/po/{n}/email", headers=H, json={"subject": "PO", "body": "Hello", "to": "po@kanpur.example"})
check("the email can be edited", r.status_code == 200, r.text[:300])
sent = {}
orig = messaging._send_email
messaging._send_email = lambda to, subject, text, html=None, attachments=None, reply_to=None: sent.update(to=to) or True
os.environ["SMTP_HOST"] = "smtp.example"
try:
    r = c.post(f"/api/smart/insight/po_{n}/decision", headers=H, json={"decision": "approve"})
finally:
    messaging._send_email = orig
    os.environ.pop("SMTP_HOST", None)
check("Approve sends it", r.status_code == 200 and sent.get("to") == "po@kanpur.example", r.text[:300])
got = supply.get_po(email, n)
check("…and it is marked sent, history and all", got["status"] == "sent" and len(got.get("history") or []) >= 2, got)
zp = next(p for p in pos if p["supplier"]["name"] == "Zip Co")
r = c.post(f"/api/smart/insight/po_{zp['po_number']}/decision", headers=H, json={"decision": "disapprove"})
check("Cancel works", r.status_code == 200 and supply.get_po(email, zp["po_number"])["status"] == "cancelled",
      r.text[:300])
before = supply._get_item(email, lp["lines"][0]["inventory_id"])["current_stock"]
r = c.post("/api/purchase-orders/status", headers=H, json={"po_number": n, "status": "received"})
after = supply._get_item(email, lp["lines"][0]["inventory_id"])["current_stock"]
check("receiving it works and puts the ordered stock back",
      r.status_code == 200 and after == before + 120, (r.status_code, before, after))
r = c.post("/api/purchase-orders/manual", headers=H, json={
    "supplier": {"name": "Zip Co", "email": "hi@zip.example"}, "expected_on": "2026-10-01",
    "terms": "50% advance", "note": "rush", "lines": [{"name": "Zip", "order_qty": 200, "unit_cost": 3}]})
check("a hand-made PO saves too (it had the same problem)", r.status_code == 200, r.text[:300])
m = supply.get_po(email, r.json().get("po_number", ""))
check("…with its terms and note", m and m.get("terms") == "50% advance" and m.get("note") == "rush", m)
r = c.get("/api/supply/state", headers=H)
check("the Suppliers page loads", r.status_code == 200 and r.json()["purchase_orders"], r.text[:200])
r = c.post("/api/supply/replenish/check", headers=H)
check("Check stock now works", r.status_code == 200, r.text[:300])
check("nothing the app wrote was refused", not db.degraded(), db.degraded())

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
