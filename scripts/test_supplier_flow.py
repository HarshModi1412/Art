"""
The supplier module as a seller uses it:

  * Create a purchase order by picking items out of your own inventory,
    adding a quantity and terms, and sending it — no free-text retyping;
  * Approve sends the order (PDF attached) rather than showing a draft email;
  * every PO is tracked: mailed → replied → confirmed → received, and
    receiving one puts the quantities back into stock;
  * the signature image, if there is one, is on the PDF;
  * scheduling runs on the seller's own clock, chosen by country.

Run: python3 scripts/test_supplier_flow.py
"""
import os
import sys
import time
from datetime import date, datetime, timedelta

os.environ.setdefault("AUTOPLAN_SCHEDULER", "off")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from backend.core import autoplan, localtime, messaging, smart, supply  # noqa: E402

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
email = f"sup{int(time.time() * 1000)}@t.co"
H = {"Authorization": "Bearer " + c.post("/api/register", json={"email": email, "password": "Test12345!"}).json()["token"],
     "X-Session-Id": "sup"}
c.post("/api/products/item", headers=H, json={"name": "Kurta", "category": "Clothing", "price": 1499, "stock": 30})
c.post("/api/supply/item", headers=H, json={
    "name": "Cotton fabric", "unit_label": "m", "current_stock": 40, "lead_time_days": 5, "moq": 50,
    "unit_cost": 120, "supplier_name": "Sharma Textiles", "supplier_email": "orders@sharma.example",
    "supplier_phone": "+919800000000", "link_product": "Kurta", "qty_per_unit": 2.5})
c.post("/api/supply/item", headers=H, json={
    "name": "Buttons", "unit_label": "pcs", "current_stock": 900, "lead_time_days": 3, "moq": 100,
    "unit_cost": 2, "supplier_name": "Button House", "supplier_email": "hi@buttons.example",
    "link_product": "Kurta", "qty_per_unit": 6})

sent = []
_real_send = messaging._send_email


def _capture(to, subject, text, html=None, attachments=None, reply_to=None):
    sent.append({"to": to, "subject": subject, "text": text,
                 "attachments": attachments or [], "reply_to": reply_to})
    return True


print("\n== Create PO: pick from inventory, add a quantity, send ==")
st = c.get("/api/supply/state", headers=H).json()
fabric = next(x for x in st["inventory"] if x["name"] == "Cotton fabric")
check("the form has the inventory to choose from", len(st["inventory"]) == 2, [x["name"] for x in st["inventory"]])
check("and knows whether this server can send mail at all", "email_ready" in st, list(st)[:6])

messaging._send_email = _capture
os.environ["SMTP_HOST"] = "smtp.example"
r = c.post("/api/purchase-orders/manual", headers=H, json={
    "supplier": {"name": "Sharma Textiles", "email": "orders@sharma.example"},
    "lines": [{"inventory_id": fabric["id"], "order_qty": 200}],
    "terms": "50% advance, balance on delivery", "send": True})
messaging._send_email = _real_send
os.environ.pop("SMTP_HOST", None)
j = r.json()
check("it is created and sent in one step", r.status_code == 200 and (j.get("send") or {}).get("sent") is True, r.text[:300])
po = supply.get_po(email, j["po_number"])
line = (po.get("lines") or [{}])[0]
check("the line took the item's name, unit and rate from inventory",
      line.get("name") == "Cotton fabric" and line.get("unit_label") == "m"
      and line.get("unit_cost") == 120 and line.get("order_qty") == 200, line)
check("it stays linked to the inventory item, so receiving can post stock",
      line.get("inventory_id") == fabric["id"])
check("the terms are on the order", po.get("terms") == "50% advance, balance on delivery")
check("the email went to the supplier", sent and sent[-1]["to"] == "orders@sharma.example", sent[-1:] )
att = (sent[-1]["attachments"] or [None])[0]
check("with the purchase order attached as a PDF",
      att and att[0].endswith(".pdf") and att[1][:4] == b"%PDF" and att[2] == "application/pdf", att and att[0])
check("and the PO is tracked as mailed", po["status"] == "mailed", po["status"])

r = c.post("/api/purchase-orders/manual", headers=H, json={
    "supplier": {"name": "Button House", "email": "hi@buttons.example"},
    "lines": [{"inventory_id": next(x for x in st["inventory"] if x["name"] == "Buttons")["id"], "order_qty": 500}],
    "send": False})
draft_no = r.json().get("po_number")
check("saving as a draft does not email anybody",
      supply.get_po(email, draft_no)["status"] == "draft" and len(sent) == 1, supply.get_po(email, draft_no)["status"])

cards = [i for i in c.get("/api/smart/state", headers=H).json()["insights"] if str(i["id"]).startswith("po_")]
check("a hand-written draft waits in the Approval panel too, on its own card",
      any(i["id"] == f"po_{draft_no}" for i in cards), [i["id"] for i in cards])
check("and its card says Approve sends it to the supplier",
      all("Approve" in (i.get("cta") or "") for i in cards), [i.get("cta") for i in cards])

print("\n== every PO is tracked, and receiving one restocks ==")
n = j["po_number"]
check("a mailed order can be marked replied",
      c.post("/api/supply/po/move", headers=H, json={"po_number": n, "status": "replied"}).status_code == 200)
check("then confirmed",
      c.post("/api/supply/po/move", headers=H, json={"po_number": n, "status": "confirmed"}).status_code == 200)
before = supply._get_item(email, fabric["id"])["current_stock"]
r = c.post("/api/supply/po/move", headers=H, json={"po_number": n, "status": "received"})
after = supply._get_item(email, fabric["id"])["current_stock"]
check("and received — the 200 m land in stock", r.status_code == 200 and after == before + 200, (before, after))
check("a received order cannot be moved again",
      c.post("/api/supply/po/move", headers=H, json={"po_number": n, "status": "replied"}).status_code == 400)
check("and a draft cannot jump straight to received",
      c.post("/api/supply/po/move", headers=H, json={"po_number": draft_no, "status": "received"}).status_code == 400)
check("the old status names still read correctly",
      supply.po_status({"status": "sent"}) == "mailed" and supply.po_status({"status": "shipped"}) == "confirmed")
state = c.get("/api/supply/state", headers=H).json()
check("the page gets the track, so it can show what comes next",
      state["po_flow"]["next"]["mailed"] == ["replied", "confirmed", "received", "cancelled"], state.get("po_flow"))

print("\n== the signature on the purchase order ==")
import base64  # noqa: E402
plain_pdf = len(supply.po_pdf_bytes(email, supply.get_po(email, n), for_supplier=True)[1].getvalue())
tiny = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
up = c.post("/api/site/image", headers=H, files={"files": ("sign.png", tiny, "image/png")})
r = c.post("/api/supply/signature", headers=H, json={"url": up.json()["url"]})
check("the signature is saved on the account", r.status_code == 200 and r.json()["signature"]["url"], r.text[:200])
fname, buf = supply.po_pdf_bytes(email, supply.get_po(email, n), for_supplier=True)
pdf = buf.getvalue()
check("the PO still renders with it", pdf[:4] == b"%PDF" and len(pdf) > 1000, len(pdf))
check("the signature image is actually in it", len(pdf) > plain_pdf, (plain_pdf, len(pdf)))
c.post("/api/supply/signature", headers=H, json={"url": ""})
check("it can be removed again", not (supply.get_signature(email) or {}).get("url"))

print("\n== scheduling on the seller's clock, picked by country ==")
loc = c.get("/api/settings/locale", headers=H).json()
check("India is the default, and the list offers others",
      loc["country"] == "IN" and len(loc["options"]) > 20 and any(o["code"] == "AE" for o in loc["options"]), loc.get("country"))
r = c.post("/api/settings/locale", headers=H, json={"country": "AE"})
check("a country can be chosen", r.status_code == 200 and r.json()["tz"] == "Asia/Dubai", r.text[:200])
check("and it is described in the seller's words", "United Arab Emirates" in r.json()["label"], r.json().get("label"))
ist = localtime.now(email)
c.post("/api/settings/locale", headers=H, json={"country": "IN"})
check("the app's clock moves with it — Dubai is 1:30 behind India",
      abs((localtime.now(email) - ist) - timedelta(minutes=90)) < timedelta(minutes=2),
      (str(ist), str(localtime.now(email))))
check("the planner decides on that clock too",
      abs(autoplan.now_local(email) - localtime.now(email)) < timedelta(seconds=5))
check("a country nobody offers is refused",
      c.post("/api/settings/locale", headers=H, json={"country": "ZZ"}).status_code == 400)
ap = c.get("/api/social/autoplan/status", headers=H)
if ap.status_code == 200:
    check("the weekly planner screen names the zone", bool(ap.json().get("tz_label")), ap.json().get("tz_label"))

print("\n== the automatic side still works ==")
rows = [{"date": pd.Timestamp(date.today() - timedelta(days=i)), "order_id": f"o{i}",
         "customer_id": f"c{i % 5}", "product": "Kurta", "amount": 2998.0, "quantity": 2} for i in range(40)]
smart.save_sales(email, pd.DataFrame(rows), {"files": ["s.csv"]})
inv = {x["name"]: x for x in c.get("/api/supply/state", headers=H).json()["inventory"]}
check("days of supply are worked out from the sales", inv["Cotton fabric"]["dos"] is not None, inv["Cotton fabric"].get("dos"))
r = c.post("/api/supply/replenish/check", headers=H)
check("the stock check runs", r.status_code == 200, r.text[:200])
JS = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "Smart CafeX", "smart.js"), encoding="utf-8").read()
check("Create PO offers the inventory in a dropdown", "poItemOptions" in JS and "— pick an item —" in JS)
check("its button sends the order", 'id="poSave">' in JS and "Create &amp; send" in JS)
check("every PO is listed under where it has got to", "PO_GROUPS" in JS and "data-pomove" in JS)
check("approving from the list sends it", "data-posend" in JS and "approvePo(b.dataset.posend)" in JS)
check("the signature can be added from the Suppliers page", 'id="supSign"' in JS and "/api/supply/signature" in JS)
check("the country picker is in the setup", 'id="soCountry"' in JS and "/api/settings/locale" in JS)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
