"""End-to-end check of the Website Builder loop.

Runs the whole thing against a throwaway data directory, so it never touches
real accounts or orders:

    python scripts/test_website_builder.py

Covers: seller signup, products with storefront fields, the list-on-site
toggle, themes and handle uniqueness, save/publish, the owner-only preview,
shopper accounts, server-side cart pricing (stock clamping, shipping threshold,
inclusive GST), placing an order, stock deduction, the idempotent sales mirror,
order status changes, the Listed Platforms toggles, and every page route.
"""
import os, sys, tempfile, shutil, json, secrets
UQ = secrets.token_hex(3)
SELLER = f"seller-{UQ}@test.com"
SELLER2 = f"seller2-{UQ}@test.com"
BUYER = f"buyer-{UQ}@test.com"
HANDLE = f"aureva-{UQ}"

TMP = tempfile.mkdtemp(prefix="cafex_e2e_")
os.environ["CAFEX_DATA_DIR"] = TMP
os.environ.setdefault("LAUNCH_MODE", "true")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from backend.main import app

c = TestClient(app)
ok = lambda m: print("  ✓", m)
def must(cond, msg, extra=""):
    if not cond:
        print("  ✗", msg, extra); sys.exit(1)
    ok(msg)

print("\n== 1. seller account ==")
r = c.post("/api/register", json={"email": SELLER, "password": "pw123456"})
must(r.status_code == 200, f"register seller ({r.status_code})", r.text[:200])
tok = r.json().get("token")
if not tok:
    r = c.post("/api/login", json={"email": SELLER, "password": "pw123456"})
    tok = r.json()["token"]
H = {"Authorization": "Bearer " + tok, "X-Session-Id": "e2e-" + UQ}

print("\n== 2. products with storefront fields ==")
p1 = c.post("/api/products/item", headers=H, json={
    "name": "Midnight Oud 50ml", "category": "Fragrance", "price": 1499, "mrp": 1999,
    "unit_cost": 500, "description": "Small-batch oud.", "image_url": "/generated_images/x.png",
    "images": ["/a.png", "/b.png"], "highlights": ["100% natural", "Ships in 24h"],
    "stock": 5, "track_stock": True, "unit_label": "bottle"})
must(p1.status_code == 200, f"create product 1 ({p1.status_code})", p1.text[:300])
prods = p1.json()["products"]
must(prods[0]["listed"] is True, "listed defaults to on")
must(prods[0]["mrp"] == 1999 and prods[0]["stock"] == 5, "storefront fields persisted")

p2 = c.post("/api/products/item", headers=H, json={"name": "Amber Musk 30ml", "category": "Fragrance",
                                                   "price": 899, "stock": 0, "track_stock": True})
must(p2.status_code == 200, "create product 2 (out of stock)")
pid1 = [p for p in p2.json()["products"] if p["name"].startswith("Midnight")][0]["id"]
pid2 = [p for p in p2.json()["products"] if p["name"].startswith("Amber")][0]["id"]

r = c.post("/api/products/listed", headers=H, json={"id": pid2, "listed": False})
must(r.status_code == 200 and not [p for p in r.json()["products"] if p["id"] == pid2][0]["listed"],
     "list-on-site toggle turns a product off")
c.post("/api/products/listed", headers=H, json={"id": pid2, "listed": True})

print("\n== 3. site state, themes, handle ==")
r = c.get("/api/site/state", headers=H)
must(r.status_code == 200, f"site state ({r.status_code})", r.text[:300])
st = r.json()
must(len(st["themes"]) == 8, f"8 themes offered (got {len(st['themes'])})")
must(len(st["fonts"]) >= 18, f"{len(st['fonts'])} fonts offered")
must(st["counts"]["listed"] == 2, f"2 products listed (got {st['counts']['listed']})")

r = c.get(f"/api/site/handle-check?handle={HANDLE}", headers=H)
must(r.json()["available"] is True, "chosen handle is available")
r = c.get("/api/site/handle-check?handle=admin", headers=H)
must(r.json()["available"] is False, "reserved handle refused")

print("\n== 4. save + publish ==")
site = st["site"]
site.update({"handle": HANDLE, "brand": "Aureva", "tagline": "Small-batch perfume", "theme": "luxury"})
site["commerce"].update({"shipping_fee": 49, "free_shipping_above": 2000, "gst_percent": 18, "gst_inclusive": True})
site["hero"].update({"heading": "Scent that stays", "sub": "Bottled in Bengaluru."})
site["style"].update({"heading_font": "playfair", "accent": "#8a6f43", "motion": "full"})
r = c.post("/api/site/save", headers=H, json={"site": site})
must(r.status_code == 200, f"save site ({r.status_code})", r.text[:400])
saved = r.json()["site"]
must(saved["theme"] == "luxury" and saved["handle"] == HANDLE, "theme + handle saved")
must(r.json()["resolved"]["heading_font"]["id"] == "playfair", "font override resolves")
must(r.json()["resolved"]["light"]["accent"] == "#8a6f43", "accent override resolves")
must("hscroll" in r.json()["resolved"]["motion"], "luxury motion includes horizontal rails")

r = c.get(f"/api/shop/{HANDLE}/site")
must(r.status_code == 404, "unpublished site is not public")
r = c.get(f"/api/shop/{HANDLE}/site", headers={"X-Preview-Token": tok})
must(r.status_code == 200, "owner preview works while unpublished")

r = c.post("/api/site/publish", headers=H, json={"published": True})
must(r.status_code == 200 and r.json()["site"]["published"], "publish")
r = c.get(f"/api/shop/{HANDLE}/site")
must(r.status_code == 200, "site is public once published")
pub = r.json()
must(len(pub["products"]) == 2, f"2 products on the storefront (got {len(pub['products'])})")
must("unit_cost" not in pub["products"][0] and "sku" not in pub["products"][0], "cost + SKU never leak")
must(pub["products"][0]["in_stock"] != pub["products"][1]["in_stock"], "stock state differs per product")

print("\n== 5. shopper account ==")
r = c.post(f"/api/shop/{HANDLE}/order", json={"lines": [{"product_id": pid1, "qty": 1}]})
must(r.status_code == 401, "ordering without an account is refused")
r = c.post(f"/api/shop/{HANDLE}/register", json={"email": BUYER, "password": "shop123", "name": "Riya", "phone": "9876543210"})
must(r.status_code == 200, f"shopper signup ({r.status_code})", r.text[:300])
stok = r.json()["token"]
SH = {"X-Store-Token": stok}
r = c.post(f"/api/shop/{HANDLE}/register", json={"email": BUYER, "password": "shop123"})
must(r.status_code == 400, "duplicate shopper email refused")
r = c.post(f"/api/shop/{HANDLE}/login", json={"email": BUYER, "password": "wrong"})
must(r.status_code == 401, "wrong password refused")

print("\n== 6. cart pricing ==")
r = c.post(f"/api/shop/{HANDLE}/cart", json={"lines": [{"product_id": pid1, "qty": 2}, {"product_id": pid2, "qty": 1}]})
pc = r.json()
must(pc["subtotal"] == 2998.0, f"subtotal excludes the sold-out item (got {pc['subtotal']})")
must(any(i["reason"] == "out_of_stock" for i in pc["issues"]), "sold-out item reported back")
must(pc["shipping"] == 0.0, "free shipping above the threshold")
must(round(pc["tax"], 2) == round(2998 - 2998 / 1.18, 2), "GST shown as an inclusive component")
must(pc["total"] == 2998.0, "inclusive GST is not added twice")

r = c.post(f"/api/shop/{HANDLE}/cart", json={"lines": [{"product_id": pid1, "qty": 1}]})
must(r.json()["shipping"] == 49.0, "shipping charged below the threshold")
r = c.post(f"/api/shop/{HANDLE}/cart", json={"lines": [{"product_id": pid1, "qty": 99}]})
must(r.json()["items"][0]["qty"] == 5, "quantity clamped to available stock")

print("\n== 7. order -> stock -> sales ==")
addr = {"name": "Riya", "phone": "9876543210", "line1": "12 MG Road", "city": "Bengaluru",
        "state": "KA", "pincode": "560001"}
r = c.post(f"/api/shop/{HANDLE}/order", headers=SH, json={"lines": [{"product_id": pid1, "qty": 2}], "address": addr, "payment": "cod"})
must(r.status_code == 200, f"place order ({r.status_code})", r.text[:400])
order = r.json()["order"]
must(order["total"] == 2998.0, f"order total (got {order['total']})")
must(order["status"] == "new", "order starts as new")

r = c.get("/api/products/state", headers=H)
stock = [p for p in r.json()["products"] if p["id"] == pid1][0]["stock"]
must(stock == 3, f"stock deducted 5 -> 3 (got {stock})")

r = c.get("/api/analytics", headers=H)
must(r.status_code == 200, f"analytics reads the site sale ({r.status_code})", r.text[:200])
r = c.get("/api/smart/state", headers=H)
sales = r.json()["data"]["sales"]
must(sales["ready"] and sales["rows"] == 1, f"1 sales row from the site (got {sales.get('rows')})")

r = c.post(f"/api/shop/{HANDLE}/order", headers=SH, json={"lines": [{"product_id": pid1, "qty": 1}], "address": addr})
must(r.status_code == 200, "second order")
r = c.get("/api/smart/state", headers=H)
must(r.json()["data"]["sales"]["rows"] == 2, "sales rebuild stays idempotent (2 rows, not 3)")

print("\n== 8. seller order management ==")
r = c.get("/api/store/orders", headers=H)
must(r.status_code == 200 and len(r.json()["orders"]) == 2, "seller sees both orders")
must(r.json()["stats"]["revenue"] == 2998.0 + 1548.0, f"revenue stats incl. shipping (got {r.json()['stats']['revenue']})")
top = r.json()["orders"][0]
oid, oqty = top["id"], sum(i["qty"] for i in top["items"])
r = c.post("/api/store/orders/status", headers=H, json={"order_id": oid, "status": "cancelled"})
must(r.status_code == 200, "cancel an order")
r = c.get("/api/products/state", headers=H)
stock = [p for p in r.json()["products"] if p["id"] == pid1][0]["stock"]
must(stock == 2 + oqty, f"cancelling returns its {oqty} unit(s) of stock (got {stock})")
must(r.json()["products"] and True, "catalogue still reads")
r = c.get("/api/smart/state", headers=H)
must(r.json()["data"]["sales"]["rows"] == 1, "cancelled order drops out of sales")

r = c.get("/api/store/customers", headers=H)
must(r.json()["customers"][0]["email"] == BUYER, "customer list")
r = c.get("/api/store/orders/export", headers=H)
must(r.status_code == 200 and "order_no" in r.text, "CSV export")

print("\n== 9. listed platforms ==")
r = c.get("/api/channels", headers=H)
ch = {x["id"]: x for x in r.json()["channels"]}
must(set(ch) == {"site", "shopify", "amazon", "flipkart", "myntra"}, f"5 channels (got {sorted(ch)})")
must(ch["site"]["status"] == "live" and ch["site"]["enabled"], "my site is live and counted")
must(ch["flipkart"]["status"] == "soon" and ch["myntra"]["status"] == "soon", "Flipkart + Myntra say yet to come")
must(ch["flipkart"]["detail"] == "Yet to come", "'Yet to come' copy present")
r = c.post("/api/channels/toggle", headers=H, json={"channel": "site", "enabled": False})
must(r.status_code == 200, "toggle my site off")
r = c.get("/api/smart/state", headers=H)
must(not r.json()["data"]["sales"]["ready"] or r.json()["data"]["sales"]["rows"] == 0,
     "site sales excluded from insights when toggled off")
c.post("/api/channels/toggle", headers=H, json={"channel": "site", "enabled": True})
r = c.get("/api/smart/state", headers=H)
must(r.json()["data"]["sales"]["rows"] == 1, "toggling back restores the sale")
r = c.post("/api/channels/toggle", headers=H, json={"channel": "flipkart", "enabled": True})
must(r.status_code == 400, "cannot toggle a marketplace that isn't live")

print("\n== 10. pages render ==")
for path in [f"/s/{HANDLE}", "/smart", "/app", "/"]:
    r = c.get(path)
    must(r.status_code == 200, f"GET {path}")
r = c.get("/s/nobody-here")
must(r.status_code == 404, "unknown handle 404s")

print("\n== 11. handle uniqueness across sellers ==")
c.post("/api/register", json={"email": SELLER2, "password": "pw123456"})
t2 = c.post("/api/login", json={"email": SELLER2, "password": "pw123456"}).json()["token"]
H2 = {"Authorization": "Bearer " + t2, "X-Session-Id": "e2e2-" + UQ}
s2 = c.get("/api/site/state", headers=H2).json()["site"]
s2.update({"handle": HANDLE, "brand": "Copycat"})
r = c.post("/api/site/save", headers=H2, json={"site": s2})
must(r.status_code == 400, "a taken handle is refused")

print("\nALL CHECKS PASSED ✓")
shutil.rmtree(TMP, ignore_errors=True)
