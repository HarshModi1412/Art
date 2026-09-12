"""
Raw-material replenishment: days of supply, the 1.2 × lead-time rule, DOQ
(MOQ → EOQ), the order-placement trigger, the drafted PO, and approving it
(AI-written email with the PO PDF attached). Plus the content writer's
endpoints.

Run: python3 scripts/test_replenish.py
"""
import math
import os
import sys
import time
from datetime import date, timedelta

os.environ.setdefault("AUTOPLAN_SCHEDULER", "off")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from backend.core import messaging, replenish, smart, supply, writer  # noqa: E402

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

# =========================================================================
print("\n== 1. DOQ: MOQ first, EOQ only once the seller's costs and a month exist ==")
# =========================================================================
d = supply.doq_for(5, 50, None, None, 40, 5)
check("no ordering/holding cost → the supplier's MOQ", d["doq"] == 50 and d["doq_basis"] == "moq", d)
check("and it says what is missing", "ordering cost" in d["eoq_missing"] and "holding cost" in d["eoq_missing"])
d = supply.doq_for(5, 50, 500, 10, 20, 5)
check("costs in but only 20 days of sales → still the MOQ", d["doq_basis"] == "moq" and not d["eoq_ready"], d)
d = supply.doq_for(5, 50, 500, 10, 40, 5)
annual = 5 * 30 * 12
eoq = math.sqrt(2 * annual * 500 / 10)
check("a month of sales: monthly consumption × 12 is the annual demand", d["annual_demand"] == annual, d)
check("EOQ = √(2DS/H)", d["doq_eoq"] == round(eoq), (d["doq_eoq"], eoq))
check("EOQ > MOQ → DOQ is the EOQ", d["doq"] == math.ceil(eoq) and d["doq_basis"] == "eoq", d)
d = supply.doq_for(5, 1000, 500, 10, 40, 5)
check("EOQ < MOQ → DOQ is the MOQ", d["doq"] == 1000 and d["doq_basis"] == "moq", d)
d = supply.doq_for(5, 1000, 500, 10, 40, 5, override=300)
check("the seller's own DOQ always wins", d["doq"] == 300 and d["doq_basis"] == "yours", d)
d = supply.doq_for(5, 0, None, None, 40, 5)
check("no MOQ at all → enough to cover the lead time + 20%", d["doq"] == math.ceil(5 * 5 * 1.2)
      and d["doq_basis"] == "cover", d)

# =========================================================================
print("\n== 2. Add item: product picked from Product Management, link saved ==")
# =========================================================================
email = f"rep{int(time.time() * 1000)}@t.co"
tok = c.post("/api/register", json={"email": email, "password": "Test12345!"}).json()["token"]
H = {"Authorization": "Bearer " + tok, "X-Session-Id": "rep"}
c.post("/api/products/item", headers=H, json={"name": "Cotton Kurta", "category": "Clothing",
                                              "price": 1499, "stock": 40})
st = c.get("/api/supply/state", headers=H).json()
check("the Add Item picker gets Product Management's products",
      [p["name"] for p in st["catalog"]] == ["Cotton Kurta"], st.get("catalog"))

r = c.post("/api/supply/item", headers=H, json={
    "name": "Cotton fabric", "unit_label": "m", "current_stock": 10, "lead_time_days": 5,
    "moq": 50, "unit_cost": 120, "supplier_name": "Sharma Textiles",
    "supplier_email": "orders@sharma.example", "supplier_phone": "+919800000000",
    "link_product": "Cotton Kurta", "qty_per_unit": 2.5})
check("item saved", r.status_code == 200, r.text[:200])
r = c.post("/api/supply/item", headers=H, json={
    "name": "Buttons", "unit_label": "pcs", "current_stock": 500, "lead_time_days": 3,
    "moq": 100, "supplier_name": "Button House", "supplier_email": "hi@buttons.example",
    "link_product": "Cotton Kurta", "qty_per_unit": 6})
maps = r.json()["maps"]
check("and linked to the product with the quantity one unit uses",
      sorted((m["product"], m["qty_per_unit"]) for m in maps)
      == [("Cotton Kurta", 2.5), ("Cotton Kurta", 6.0)], maps)

# 40 days of sales, 2 kurtas a day
end = date(2026, 9, 10)
rows = [{"date": pd.Timestamp(end - timedelta(days=i)), "order_id": f"o{i}", "customer_id": f"c{i % 9}",
         "product": "Cotton Kurta", "amount": 2998.0, "quantity": 2} for i in range(40)]
smart.save_sales(email, pd.DataFrame(rows), {"files": ["s.csv"]})

# =========================================================================
print("\n== 3. DOS and the 1.2 × lead-time rule, per raw material ==")
# =========================================================================
inv = {r["name"]: r for r in c.get("/api/supply/state", headers=H).json()["inventory"]}
fab, btn = inv["Cotton fabric"], inv["Buttons"]
check("product sales become raw-material consumption (2/day × 2.5 m = 5 m/day)",
      fab["avg_daily_consumption"] == 5.0, fab["avg_daily_consumption"])
check("DOS = current stock ÷ daily consumption (10 ÷ 5 = 2 days)", fab["dos"] == 2.0, fab["dos"])
check("threshold is 1.2 × lead time (6 days)", fab["dos_threshold"] == 6.0, fab["dos_threshold"])
check("2 < 6 → fabric needs a PO", fab["needs_po"] is True)
check("buttons: 500 ÷ 12 ≈ 41.7 days ≥ 3.6 → fine", btn["dos"] == 41.7 and btn["needs_po"] is False,
      (btn["dos"], btn["needs_po"]))
check("the lead time shown is the item's own", fab["effective_lead_time_days"] == 5)
check("linked products are listed on the item", fab["linked_products"] == ["Cotton Kurta"])
check("DOQ starts at the MOQ (no costs entered yet)", fab["doq"] == 50 and fab["doq_basis"] == "moq", fab)
check("the reason explains it in plain words", "lasts about 2 days" in fab["reason"]
      and "supplier's minimum" in fab["reason"], fab["reason"])

# the seller enters ordering + holding cost → EOQ takes over
fab_up = {k: fab[k] for k in ("id", "name", "unit_label", "current_stock", "lead_time_days", "moq",
                              "unit_cost", "supplier_name", "supplier_email", "supplier_phone")}
fab_up.update({"ordering_cost": 500, "holding_cost": 10})
inv = {r["name"]: r for r in c.post("/api/supply/item", headers=H, json=fab_up).json()["inventory"]}
fab = inv["Cotton fabric"]
exp = math.ceil(math.sqrt(2 * 5 * 30 * 12 * 500 / 10))
check("with S, H and 40 days of sales: DOQ = EOQ (above the MOQ)",
      fab["doq"] == exp and fab["doq_basis"] == "eoq", (fab["doq"], exp, fab["doq_basis"]))
r = c.post("/api/supply/doq", headers=H, json={"id": fab["id"], "doq": 300})
fab = {x["name"]: x for x in r.json()["inventory"]}["Cotton fabric"]
check("the seller can change the DOQ", fab["doq"] == 300 and fab["doq_basis"] == "yours", fab["doq"])
r = c.post("/api/supply/doq", headers=H, json={"id": fab["id"], "doq": None})
fab = {x["name"]: x for x in r.json()["inventory"]}["Cotton fabric"]
check("and clear it back to the worked-out one", fab["doq"] == exp and fab["doq_basis"] == "eoq")

# =========================================================================
print("\n== 4. an order placed → check → draft PO for the supplier ==")
# =========================================================================
HANDLE = f"rep{int(time.time())}"
pid = c.get("/api/products/state", headers=H).json()["products"][0]["id"]
site = c.get("/api/site/state", headers=H).json()["site"]
site.update({"handle": HANDLE, "brand": "Kora Studio"})
c.post("/api/site/save", headers=H, json={"site": site})
c.post("/api/site/publish", headers=H, json={"published": True})
r = c.post(f"/api/shop/{HANDLE}/order", json={
    "lines": [{"product_id": pid, "qty": 1}],
    "address": {"name": "Asha", "phone": "9000000009", "line1": "4 MG Road",
                "city": "Pune", "state": "MH", "pincode": "411001"},
    "guest": True, "name": "Asha", "phone": "9000000009"})
check("the shopper's order goes through", r.status_code == 200, r.text[:300])
pos = supply.get_purchase_orders(email)
drafts = [p for p in pos if p.get("status") == "draft"]
check("the order triggered a draft PO", len(drafts) == 1, [(p["po_number"], p["status"]) for p in pos])
po = drafts[0]
check("for the fabric only (buttons are fine)", [l["name"] for l in po["lines"]] == ["Cotton fabric"])
check("at the DOQ", po["lines"][0]["order_qty"] == exp, po["lines"][0]["order_qty"])
check("addressed to the supplier on file",
      po["supplier"]["email"] == "orders@sharma.example" and po["supplier"]["name"] == "Sharma Textiles")
check("the stock the order used came off the raw material first",
      supply._get_item(email, fab["id"])["current_stock"] == 7.5)
check("and the note says which order raised it", "ORD-" in (po.get("note") or ""), po.get("note"))

r = c.post(f"/api/shop/{HANDLE}/order", json={
    "lines": [{"product_id": pid, "qty": 1}],
    "address": {"name": "Asha", "phone": "9000000009", "line1": "4 MG Road",
                "city": "Pune", "state": "MH", "pincode": "411001"},
    "guest": True, "name": "Asha", "phone": "9000000009"})
drafts2 = [p for p in supply.get_purchase_orders(email) if p.get("status") == "draft"]
check("a second order does not raise a second PO for what is already on order",
      len(drafts2) == 1, len(drafts2))
check("the DOQ table was saved on the account", fab["id"] in replenish.doq_table(email))
st2 = c.get("/api/supply/state", headers=H).json()
fab_row = next((r for r in st2["inventory"] if r["id"] == fab["id"]), {})
check("the table marks it on order", fab_row.get("on_order") is True, fab_row.get("on_order"))
check("'time to buy more' leaves out what is already on order",
      all(r["id"] != fab["id"] for r in st2["suggestions"]) and st2["n_on_order"] >= 1,
      ([r["name"] for r in st2["suggestions"]], st2.get("n_on_order")))

# every other way an order arrives re-checks stock too
from backend.core import storefront  # noqa: E402
n_log = len(replenish.recent_log(email, 100))
sales_cols = list(smart.load_sales(email).columns)
row = {c_: "" for c_ in sales_cols}
row.update({"date": date.today().isoformat(), "amount": "1499", "quantity": "1"})
for k in ("product", "item", "Product", "item_name"):
    if k in row:
        row[k] = "Cotton Kurta"
r = c.post("/api/smart/records/add", headers=H, json={"kind": "sales", "rows": [row]})
check("sales added by hand go through", r.status_code == 200, r.text[:200])
lg = replenish.recent_log(email, 100)
check("…and re-check every raw material against the DOS rule",
      len(lg) > n_log and lg[0]["trigger"] == "sales" and "by hand" in lg[0]["ref"], lg[:1])
MAIN = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "backend", "main.py"), encoding="utf-8").read()
check("uploads, past-sales uploads and orders pulled from a connected store re-check too",
      MAIN.count("replenish.after_sales(") >= 6 and 'f"orders pulled from {body.connector}"' in MAIN)
ords = storefront.get_orders(email)
o = ords[-1]
storefront.set_status(email, o["id"], "cancelled")
n_log = len(replenish.recent_log(email, 100))
storefront.set_status(email, o["id"], "new")
lg = replenish.recent_log(email, 100)
check("a cancelled order put back takes its stock again — and is checked like a new order",
      len(lg) > n_log and lg[0]["trigger"] == "restored" and lg[0]["ref"] == o["order_no"], lg[:1])
check("nothing already on order is ordered twice by these checks",
      len([p for p in supply.get_purchase_orders(email) if p.get("status") == "draft"]) == 1)

# =========================================================================
print("\n== 5. Approval panel: Approve / Details / Cancel ==")
# =========================================================================
ins = c.get("/api/smart/state", headers=H).json()["insights"]
card = next((i for i in ins if i["id"] == f"po_{po['po_number']}"), None)
check("the draft PO is a card in the Approval panel", card is not None, [i["id"] for i in ins])
check("from the Supply Chain Manager", card and card["manager"] == "supply")
check("whose button says it will email the supplier", card and "email" in card["cta"].lower())
check("the running-low card does not list what is already ordered",
      not any(i["id"] == "reorder" for i in ins))

r = c.get(f"/api/supply/po/{po['po_number']}/detail", headers=H)
det = r.json()
check("Details returns the lines with each item's DOS and how its DOQ was worked out",
      det["po"]["lines"][0]["now"]["dos"] is not None and det["po"]["lines"][0]["now"]["doq_basis"] == "eoq",
      det["po"]["lines"][0].get("now"))
check("and the email the content writer drafted",
      det["email"]["subject"] and po["po_number"] in det["email"]["body"], det["email"])
check("addressed to the supplier", det["email"]["to"] == "orders@sharma.example")
r = c.post(f"/api/supply/po/{po['po_number']}/lines", headers=H,
           json={"qty": {fab["id"]: 400}})
check("quantities can be changed before sending", r.json()["po"]["lines"][0]["order_qty"] == 400)
r = c.post(f"/api/supply/po/{po['po_number']}/email", headers=H,
           json={"subject": "PO for fabric", "body": "Dear Sharma ji, please find our PO attached."})
check("the email can be edited", r.json()["email"]["subject"] == "PO for fabric")

# capture the send instead of hitting a real SMTP server
sent = {}


def fake_send(to, subject, text, html="", attachments=None, reply_to=""):
    sent.update(to=to, subject=subject, text=text, attachments=attachments, reply_to=reply_to)
    return True


orig = messaging._send_email
messaging._send_email = fake_send
try:
    r = c.post(f"/api/smart/insight/po_{po['po_number']}/decision", headers=H,
               json={"decision": "approve"})
finally:
    messaging._send_email = orig
res = r.json().get("send") or {}
check("Approve sends it", r.status_code == 200 and res.get("sent") is True, r.text[:300])
check("to the supplier's address", sent.get("to") == "orders@sharma.example")
check("with the email as edited", sent.get("subject") == "PO for fabric" and "Sharma ji" in sent.get("text", ""))
att = (sent.get("attachments") or [None])[0]
check("with the PO attached as a PDF",
      att and att[0].endswith(".pdf") and att[1][:4] == b"%PDF" and att[2] == "application/pdf", att and att[0])
check("replies come back to the seller", sent.get("reply_to") == email)
check("the PO is now tracked as mailed", supply.get_po(email, po["po_number"])["status"] == "mailed")
check("and leaves the Approval panel",
      not any(i["id"] == f"po_{po['po_number']}" for i in r.json()["insights"]))

# no SMTP configured → approved, not sent, with PDF + mailto fallback
supply.set_po_status(email, po["po_number"], "received")   # stock arrives
fab_now = supply._get_item(email, fab["id"])
check("receiving the PO adds the stock back", fab_now["current_stock"] > 300, fab_now["current_stock"])
fab_now = dict(fab_now); fab_now["current_stock"] = 1
supply.upsert_item(email, fab_now)
res = replenish.check(email, trigger="manual")
check("a manual check drafts a new PO once stock is low again", len(res["created"]) == 1, res)
n2 = res["created"][0]
os.environ.pop("SMTP_HOST", None)
r = c.post(f"/api/supply/po/{n2}/approve", headers=H, json={})
d2 = r.json()
check("with no mail server the approval still counts", d2["status"] == "open" and d2["sent"] is False, d2)
check("and says why", "not set up" in d2["reason"], d2["reason"])
check("handing back the PDF and a ready mailto", d2["pdf_url"].endswith("supplier=1")
      and d2["mailto"].startswith("mailto:orders@sharma.example"))
pdf = c.get(d2["pdf_url"], headers=H)
check("the supplier copy of the PDF renders", pdf.status_code == 200 and pdf.content[:4] == b"%PDF")

res = replenish.check(email, trigger="manual")
check("an 'open' PO still counts as on order — no duplicate", res["created"] == [], res)
r = c.post(f"/api/smart/insight/po_{n2}/decision", headers=H, json={"decision": "cancel"})
check("Cancel cancels the PO", supply.get_po(email, n2)["status"] == "cancelled")

# supplier with no email
c.post("/api/supply/item", headers=H, json={
    "name": "Thread", "unit_label": "spool", "current_stock": 1, "lead_time_days": 4,
    "moq": 20, "supplier_name": "Local Market", "link_product": "Cotton Kurta", "qty_per_unit": 1})
res = replenish.check(email, trigger="manual")
cards = replenish.insight_cards(email)
tcard = next((x for x in cards if x["supplier_name"] == "Local Market"), None)
check("a supplier with no email still gets a draft", tcard is not None, cards)
check("and the card says it will hand over the PDF instead", tcard and "download" in tcard["cta"].lower())

# =========================================================================
print("\n== 6. the content writer ==")
# =========================================================================
r = c.post("/api/ai/write", headers=H, json={"kind": "product_description", "label": "Description",
                                             "context": {"name": "Cotton Kurta", "category": "Clothing",
                                                         "materials": "handloom cotton"}})
j = r.json()
check("/api/ai/write answers", r.status_code == 200 and j.get("text"), r.text[:200])
check("with no AI configured here it says so, and hands the brief to the browser",
      j["provider"] == "template" and j["prompt"]["user"] and j["meta"]["browser_puter"] is True, j.get("meta"))
check("the template uses only what it was told", "handloom cotton" in j["text"], j["text"])
for kind in ("product_highlights", "hero_sub", "story"):
    t = writer.write_field(email, kind, context={"name": "Cotton Kurta"})["text"]
    check(f"with no AI, the '{kind}' starting draft claims nothing the seller did not say",
          not any(w in t.lower() for w in ("by hand", "across india", "ships from", "small batch")), t)
t = writer.write_field(email, "product_highlights", context={"name": "Kurta", "materials": "linen"})["text"]
check("…and leaves [gaps] to fill where a fact is missing", "Made of linen" in t and "[" in t, t)
for kind in ("site_brief", "product_materials", "product_for", "product_occasions", "hashtags",
             "brand_palette", "brand_avoid", "voiceover"):
    check(f"the writer knows the '{kind}' field", kind in writer.FIELD_KINDS)
r = c.post("/api/ai/site-copy", headers=H, json={"brief": "Handloom kurtas from Pune, cut small-batch for people who hate fast fashion."})
sc = r.json()
check("site copy from a one-line brief", r.status_code == 200 and sc["copy"].get("hero_heading"), r.text[:200])
check("site copy refuses an empty brief", c.post("/api/ai/site-copy", headers=H, json={"brief": ""}).status_code == 400)
r = c.post("/api/ai/product-copy", headers=H, json={"product": {"name": "Cotton Kurta", "category": "Clothing"}})
check("product copy returns a description and key points",
      r.status_code == 200 and r.json()["description"] and r.json()["highlights"], r.text[:200])

# with a provider that answers, the writer's rules and brand context go with it
from backend.core import aiprovider  # noqa: E402
seen = {}


def fake_gen(system, user, **kw):
    seen.update(system=system, user=user, kw=kw)
    if "Return JSON only" in user and "hero_heading" in user:
        return {"text": '{"hero_heading": "Cut slow, worn long", "hero_sub": "Handloom kurtas from Pune.", '
                        '"highlights": [{"title": "Handloom", "text": "Woven on pit looms"}], "tagline": "x"}',
                "provider": "puter", "free": False, "error": ""}
    return {"text": "Here is your text: \"Woven in Pune.\"", "provider": "puter", "free": False, "error": ""}


orig_gen = aiprovider.generate
aiprovider.generate = fake_gen
try:
    j = writer.write_field(email, "tagline", "Tagline")
    s2 = writer.site_copy(email, "Handloom kurtas from Pune")
    e2 = writer.po_email(email, supply.get_po(email, n2))
finally:
    aiprovider.generate = orig_gen
check("the writer asks for the copy model (role=writer)", seen["kw"].get("role") == "writer", seen["kw"])
check("the brand's rules travel in the system prompt", "Never invent a price" in seen["system"])
check("preambles and wrapping quotes are stripped", j["text"] == "Woven in Pune.", j["text"])
check("site copy comes back as fields", s2["copy"]["hero_heading"] == "Cut slow, worn long"
      and s2["copy"]["highlights"][0]["title"] == "Handloom", s2["copy"])
check("the supplier email is private work", seen["kw"].get("sensitivity") == "private")

# Puter is first in the provider chain when configured
os.environ["PUTER_AUTH_TOKEN"] = "test-token"
try:
    names = [p.name for p in aiprovider._order("public")]
    st = aiprovider.status()
finally:
    os.environ.pop("PUTER_AUTH_TOKEN", None)
check("Puter leads the chain when its token is set", names[:1] == ["puter"], names)
check("and is reported as the active writer", st["active"] == "puter", st["active"])
p = next(x for x in aiprovider.PROVIDERS if x.name == "puter")
check("on Puter's OpenAI-compatible endpoint", p.base_url == "https://api.puter.com/puterai/openai/v1")
check("with a stronger model for copy", p.model_for("writer") != p.model_for(""))

# =========================================================================
print("\n== 7. the frontend is wired for it ==")
# =========================================================================
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = open(os.path.join(ROOT, "Smart CafeX", "smart.js"), encoding="utf-8").read()
CSS = open(os.path.join(ROOT, "Smart CafeX", "smart.css"), encoding="utf-8").read()
_a = JS.index("const inv = _supplyView === \"inventory\";")
_sup_view = JS[_a:JS.index("moduleShell(_supplyView === \"inventory\"", _a)]
_suppliers_branch = _sup_view[_sup_view.index("` : `"):]
check("Add item is in Inventory only, not in Suppliers", 'id="supAdd"' not in _suppliers_branch.split("${sugSection}")[0])
check("the inventory table shows DOS, lead time, the 1.2× line and an editable DOQ",
      "data-doq=" in JS and "Order below" in JS and ">DOS<" in JS)
check("a 'Check stock now' button runs the same check an order does",
      "/api/supply/replenish/check" in JS)
check("both add forms step through with Next/Back and submit on the last step",
      "function wizardify" in JS and JS.count("wizardify(") >= 3 and "Next: " in JS)
check("Add Item picks the product from Product Management, name stays editable",
      'id="sfProd"' in JS and "_supplyData.catalog" in JS and 'nm.dataset.auto = "1"' in JS)
check("drafted POs open in a Details view with the email editable",
      "function openPoDetail" in JS and 'id="poMsg"' in JS and "/email/rewrite" in JS)
check("the Inventory page shows the item table (DOS, lead time, DOQ) — not only the Suppliers page",
      "const body = head + `" in JS and JS.index("const head = inv ?") < JS.index('<table class="sup-table">\n        <thead><tr>\n          <th>Item</th>'))
check("'Draft purchase orders' in the buy-more section runs the same check → draft → approve path",
      '$("supGenPo").onclick = async' in JS and JS.index('$("supGenPo").onclick = async') < JS.index("async function supplyGeneratePo"))
check("Add item refuses a second item with the same name",
      "You already have" in JS and "What each product uses" in JS)
check("approving sends through the backend, with a PDF + mail-app fallback",
      "function approvePo" in JS and "r.mailto" in JS)
check("purchase-order cards get Approve / Details / Cancel",
      'String(i.id).startsWith("po_")' in JS)
check("✨ on text fields everywhere, wired as screens render",
      "MutationObserver" in JS and JS.count('data-ai="') >= 22)
for fid in ("siteBrief", "stMat", "stWho", "stOcc", "sbPal", "sbAvoid", "sbTags", "ccTags", "smVoiceover"):
    i0 = JS.find(f'id="{fid}"')
    check(f"#{fid} has the AI helper", i0 > 0 and "data-ai=" in JS[i0:i0 + 220], JS[i0:i0 + 120])
check("the website gets written from the seller's brief",
      'id="siteBrief"' in JS and "/api/ai/site-copy" in JS and "function writeWholeSite" in JS)
check("product description and key points in one tap", "/api/ai/product-copy" in JS)
check("puter.js is the browser fallback", "https://js.puter.com/v2/" in JS and "puter.ai" in JS)
check("styles exist for the new pieces", ".ai-btn" in CSS and ".ai-pop" in CSS and ".po-st" in CSS
      and ".pf-tab.done" in CSS)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
