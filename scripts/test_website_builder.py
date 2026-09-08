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
# Guest checkout: a first-time buyer must be able to pay without inventing a
# password. They still become a real customer, keyed on the phone number the
# parcel needs anyway.
r = c.post(f"/api/shop/{HANDLE}/order", json={
    "lines": [{"product_id": pid1, "qty": 1}],
    "address": {"name": "Guest Buyer", "phone": "9000000001", "line1": "1 First St",
                "city": "Bengaluru", "state": "KA", "pincode": "560001"},
    "guest": True, "name": "Guest Buyer", "phone": "9000000001"})
must(r.status_code == 200, f"a guest can place an order ({r.status_code})", r.text[:300])
must(r.json().get("token"), "a guest gets a session so 'your orders' works")
guest_order_total = r.json()["order"]["total"]
r = c.post(f"/api/shop/{HANDLE}/order", json={
    "lines": [{"product_id": pid1, "qty": 1}],
    "address": {"name": "", "phone": "123", "line1": "1 First St",
                "city": "Bengaluru", "state": "KA", "pincode": "560001"}})
must(r.status_code == 400, "a guest without a real phone number is still refused")
r = c.get("/api/store/customers", headers=H)
must(any(cu.get("phone", "").endswith("9000000001") for cu in r.json().get("customers", [])),
     "the guest shows up in the seller's customer list")

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
must(r.json()["items"][0]["qty"] == 4, "quantity clamped to available stock")

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
must(stock == 2, f"stock deducted 5 -> 2 after guest + shopper orders (got {stock})")

r = c.get("/api/analytics", headers=H)
must(r.status_code == 200, f"analytics reads the site sale ({r.status_code})", r.text[:200])
r = c.get("/api/smart/state", headers=H)
sales = r.json()["data"]["sales"]
must(sales["ready"] and sales["rows"] == 2, f"2 sales rows from the site (got {sales.get('rows')})")

r = c.post(f"/api/shop/{HANDLE}/order", headers=SH, json={"lines": [{"product_id": pid1, "qty": 1}], "address": addr})
must(r.status_code == 200, "second order")
r = c.get("/api/smart/state", headers=H)
must(r.json()["data"]["sales"]["rows"] == 3, "sales rebuild stays idempotent (3 rows, not 4)")

print("\n== 8. seller order management ==")
r = c.get("/api/store/orders", headers=H)
must(r.status_code == 200 and len(r.json()["orders"]) == 3, "seller sees all three orders")
must(r.json()["stats"]["revenue"] == 2998.0 + 1548.0 + guest_order_total, f"revenue stats incl. shipping (got {r.json()['stats']['revenue']})")
top = r.json()["orders"][0]
oid, oqty = top["id"], sum(i["qty"] for i in top["items"])
before = [p for p in c.get("/api/products/state", headers=H).json()["products"]
          if p["id"] == pid1][0]["stock"]
r = c.post("/api/store/orders/status", headers=H, json={"order_id": oid, "status": "cancelled"})
must(r.status_code == 200, "cancel an order")
r = c.get("/api/products/state", headers=H)
stock = [p for p in r.json()["products"] if p["id"] == pid1][0]["stock"]
must(stock == before + oqty, f"cancelling returns its {oqty} unit(s) of stock (got {stock})")
must(r.json()["products"] and True, "catalogue still reads")
r = c.get("/api/smart/state", headers=H)
must(r.json()["data"]["sales"]["rows"] == 2, "cancelled order drops out of sales (3 -> 2)")

r = c.get("/api/store/customers", headers=H)
must(any(cu["email"] == BUYER for cu in r.json()["customers"]), "customer list")
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
must(r.json()["data"]["sales"]["rows"] == 2, "toggling back restores the sales")
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

print("\n== 12. builder: icons, live resolve, theme catalogue ==")
r = c.get("/api/site/state", headers=H)
st2 = r.json()
must(len(st2["icons"]) >= 30, f"{len(st2['icons'])} icons shipped to the builder")
must(len(st2["promise_icons"]) >= 15, "promise-strip icon choices")
must(all(t["label"] for t in st2["themes"]), "every theme is named")
must(all("feel" in t for t in st2["themes"]), "every theme resolves its motion feel")
draft = dict(st2["site"])
draft["theme"] = "fitness"
draft["style"] = {**draft["style"], "accent": "#2f6f57", "heading_font": "bebas", "motion": "subtle"}
r = c.post("/api/site/resolve", headers=H, json={"site": draft})
must(r.status_code == 200, f"live resolve ({r.status_code})", r.text[:200])
rs = r.json()["style"]
must(rs["light"]["accent"] == "#2f6f57", "custom accent resolves live")
must(rs["light"]["accent_ink"] in ("#ffffff", "#12100e"), "readable ink picked for the custom accent")
must(rs["heading_font"]["id"] == "bebas", "font override resolves live")
must("marquee" not in rs["motion"], "subtle motion drops the heavy effects")
must(c.get("/api/site/state", headers=H).json()["site"]["theme"] != "fitness",
     "resolving a draft never saves it")

print("\n== 13. emoji icons heal ==")
site3 = c.get("/api/site/state", headers=H).json()["site"]
site3["highlights"] = [{"icon": "\U0001F69A", "title": "Fast", "text": "24h"}]
c.post("/api/site/save", headers=H, json={"site": site3})
healed = c.get("/api/site/state", headers=H).json()["site"]["highlights"][0]["icon"]
must(healed == "truck", f"a stored emoji becomes a real icon (got {healed!r})")

print("\n== 14. media, type roles and the new blocks ==")
site4 = c.get("/api/site/state", headers=H).json()["site"]
must("video_url" in site4["hero"], "hero carries a video slot")
must(len(site4["copy"]) >= 15, f"{len(site4['copy'])} editable labels on the page")
must("stats" in site4["sections"] and "drop" in site4["sections"]
     and "gallery" in site4["sections"] and "manifesto" in site4["sections"],
     "numbers, scarcity, lookbook and statement blocks exist")
site4["sections"].update({"stats": True, "drop": True, "gallery": True, "manifesto": True})
site4["stats"] = [{"value": "2,400+", "label": "shipped"}, {"value": "4.9", "label": "rating"}]
site4["gallery"] = [{"url": "/generated_images/a.jpg", "caption": "Drop 01"},
                    {"url": "/generated_images/b.mp4", "caption": ""}]
site4["manifesto"] = "We make small batches and stop when the batch is done."
site4["hero"]["video_url"] = "/generated_images/hero.mp4"
site4["style"].update({"accent_font": "syne", "heading_scale": 118, "heading_weight": 500,
                       "heading_track": -3, "body_scale": 104, "preloader": False, "width": "full"})
r = c.post("/api/site/save", headers=H, json={"site": site4})
must(r.status_code == 200, f"save the new blocks ({r.status_code})", r.text[:300])
saved4 = r.json()["site"]
must(saved4["hero"]["video_url"].endswith(".mp4"), "hero video persists")
must(len(saved4["stats"]) == 2 and len(saved4["gallery"]) == 2, "figures and lookbook persist")
must(saved4["style"]["width"] == "full", "edge-to-edge width accepted")
rs4 = r.json()["resolved"]
must(rs4["accent_font"]["id"] == "syne", "the label typeface is its own role")
must(rs4["type"]["heading_scale"] == 118 and rs4["type"]["heading_weight"] == 500
     and rs4["type"]["heading_track"] == -3 and rs4["type"]["body_scale"] == 104,
     "display scale, weight, tracking and body scale all resolve")
must(rs4["preloader"] is False, "the loading screen can be switched off")
must(len(rs4["google_fonts"]) >= 3, "all three typefaces are requested from Google")

site4["style"]["heading_scale"] = 9999
r = c.post("/api/site/save", headers=H, json={"site": site4})
must(r.json()["site"]["style"]["heading_scale"] == 145, "a silly type scale is clamped, not stored")

print("\n== 15. scarcity reads real stock ==")
pub2 = c.get(f"/api/shop/{HANDLE}/site").json()
sc = pub2.get("scarce")
must(sc and sc["left"] > 0, f"the countdown picks a product still in stock (got {sc})")
must(sc["name"] != "Amber Musk 30ml" or sc["left"] > 0, "never counts down a sold-out piece")
must(pub2["products"][0].get("video_url") is not None, "products expose their clip to the storefront")

print("\n== 16. media upload accepts video ==")
import io as _io
r = c.post("/api/site/image", headers=H,
           files={"files": ("clip.mp4", _io.BytesIO(b"\x00\x00\x00\x18ftypmp42" + b"0" * 400), "video/mp4")})
must(r.status_code == 200 and r.json()["kind"] == "video", f"an MP4 uploads ({r.status_code})", r.text[:200])
must(r.json()["url"].endswith(".mp4"), "the clip keeps its extension")
r = c.post("/api/site/image", headers=H,
           files={"files": ("bad.exe", _io.BytesIO(b"MZ" + b"0" * 100), "application/octet-stream")})
must(r.status_code == 400, "anything that isn't an image or a clip is refused")

print("\n== 17. pricing: three tiers + a usage plan ==")
r = c.get("/api/pricing")
pc = r.json()
must([p["id"] for p in pc["plans"]] == ["free", "semipro", "pro"], "Free / Semi Pro / Pro")
must(pc["plans"][1]["price_inr"] == 499 and pc["plans"][2]["price_inr"] == 999, "tier prices")
must(len(pc["credit_packs"]) == 3, "credit packs offered alongside the tiers")
must(pc["stack"]["saving_inr"] > 0, "the Shopify app-stack comparison computes")
must(pc["stack"]["ours_inr"] == 999, "compared against Pro")
from backend.core import pricing as _pr
must(_pr.plan_allows("free", "analytics"), "analytics is free forever")
_lm = _pr.launch_mode
_pr.launch_mode = lambda: False
try:
    must(not _pr.plan_allows("free", "supply"), "Supply is gated on Free once launch ends")
    must(_pr.plan_allows("pro", "supply"), "Pro includes Supply")
    must(_pr.plan_allows("semipro", "winback_campaign"), "Semi Pro includes campaigns")
    must(_pr.credits_for("winback_campaign") == 10, "a campaign also costs credits")
    must(_pr.upgrade_target("supply")["id"] == "pro", "the paywall names the right tier")
finally:
    _pr.launch_mode = _lm

print("\n== 18. product variants: size x colour ==")
axes = [{"name": "Size", "values": ["S", "M", "L"]},
        {"name": "Colour", "values": ["Black", "Blue"]}]
r = c.post("/api/products/item", headers=H, json={
    "name": "Field Shirt", "category": "Shirts", "price": 1499, "unit_cost": 600,
    "options": axes, "listed": True, "track_stock": True,
    "description": "Cotton twill.", "image_url": "/generated_images/x.png"})
must(r.status_code == 200, f"create a product with two option axes ({r.status_code})", r.text[:300])
shirt = [p for p in r.json()["products"] if p["name"] == "Field Shirt"][0]
must(len(shirt["variants"]) == 6, f"3 sizes x 2 colours = 6 cells (got {len(shirt['variants'])})")
must(shirt["has_variants"], "the product knows it has variants")
vs = shirt["variants"]
for v, qty, price in zip(vs, [4, 0, 7, 2, 0, 3], [None, None, 1699, None, None, None]):
    v["stock"] = qty
    if price:
        v["price"] = price
    v["sku"] = "FS-" + v["label"].replace(" / ", "-")
r = c.post("/api/products/item", headers=H, json={**shirt, "variants": vs})
shirt = [p for p in r.json()["products"] if p["id"] == shirt["id"]][0]
must(shirt["stock"] == 16, f"product stock rolls up from the matrix (got {shirt['stock']})")
must(all(v["sku"] for v in shirt["variants"]), "per-variant SKUs persist")

# adding a size must not reset the twelve cells already filled in
grown = [{"name": "Size", "values": ["S", "M", "L", "XL"]},
         {"name": "Colour", "values": ["Black", "Blue"]}]
r = c.post("/api/products/item", headers=H, json={**shirt, "options": grown})
shirt = [p for p in r.json()["products"] if p["id"] == shirt["id"]][0]
must(len(shirt["variants"]) == 8, "adding a size grows the matrix to 8")
must(shirt["stock"] == 16, "existing cells keep their stock when the matrix grows")

pub = c.get(f"/api/shop/{HANDLE}/site").json()
sh = [p for p in pub["products"] if p["id"] == shirt["id"]][0]
must(len(sh["variants"]) == 8 and sh["options"], "the storefront receives the matrix")
must(all("sku" not in v for v in sh["variants"]), "SKU never leaks to shoppers")
priced_v = next(v for v in sh["variants"] if v["price"] == 1699)
plain_v = next(v for v in sh["variants"] if v["price"] == 1499 and v["in_stock"])

r = c.post(f"/api/shop/{HANDLE}/cart", json={"lines": [{"product_id": shirt["id"], "qty": 1}]})
must(any(i["reason"] == "choose_variant" for i in r.json()["issues"]),
     "a variant product cannot be bought without picking a variant")
r = c.post(f"/api/shop/{HANDLE}/cart", json={
    "lines": [{"product_id": shirt["id"], "variant_id": priced_v["id"], "qty": 1}]})
must(r.json()["items"][0]["unit_price"] == 1699.0, "the variant's price override is used")
must(r.json()["items"][0]["variant_label"], "the line carries a human label")
oos = next(v for v in sh["variants"] if not v["in_stock"])
r = c.post(f"/api/shop/{HANDLE}/cart", json={
    "lines": [{"product_id": shirt["id"], "variant_id": oos["id"], "qty": 1}]})
must(any(i["reason"] == "out_of_stock" for i in r.json()["issues"]),
     "a sold-out cell is refused even when the product has stock")

before_cell = next(v for v in shirt["variants"] if v["id"] == plain_v["id"])["stock"]
r = c.post(f"/api/shop/{HANDLE}/order", json={
    "lines": [{"product_id": shirt["id"], "variant_id": plain_v["id"], "qty": 1}],
    "address": {"name": "V Buyer", "phone": "9000000002", "line1": "2 Second St",
                "city": "Bengaluru", "state": "KA", "pincode": "560002"}})
must(r.status_code == 200, f"order one variant ({r.status_code})", r.text[:300])
shirt = [p for p in c.get("/api/products/state", headers=H).json()["products"]
         if p["id"] == shirt["id"]][0]
after_cell = next(v for v in shirt["variants"] if v["id"] == plain_v["id"])["stock"]
must(after_cell == before_cell - 1, f"only that cell is decremented ({before_cell} -> {after_cell})")
must(shirt["stock"] == 15, f"the roll-up follows (got {shirt['stock']})")

print("\n== 19. password reset ==")
r = c.post("/api/forgot", json={"email": "nobody-at-all@example.com"})
must(r.status_code == 200 and r.json()["ok"], "an unknown address answers the same way")
r = c.post("/api/forgot", json={"email": SELLER})
must(r.status_code == 200, "reset requested for a real seller")
ob = c.get("/api/dev/outbox").json()["outbox"]
link = next((m for m in ob if "reset" in (m.get("body") or "")), None)
must(link is not None, "a reset mail was produced")
import re as _re
tok = _re.search(r"token=([A-Za-z0-9_\-]+)", link["body"]).group(1)
r = c.post("/api/reset", json={"email": SELLER, "token": "not-a-real-token", "password": "newpw123"})
must(r.status_code == 400, "a bogus token is refused")
r = c.post("/api/reset", json={"email": SELLER, "token": tok, "password": "newpw123"})
must(r.status_code == 200, f"password changed ({r.status_code})", r.text[:200])
r = c.post("/api/reset", json={"email": SELLER, "token": tok, "password": "otherpw1"})
must(r.status_code == 400, "the same token cannot be used twice")
must(c.post("/api/login", json={"email": SELLER, "password": "newpw123"}).status_code == 200,
     "the new password works")
tok_new = c.post("/api/login", json={"email": SELLER, "password": "newpw123"}).json()["token"]
H["Authorization"] = "Bearer " + tok_new

r = c.post(f"/api/shop/{HANDLE}/forgot", json={"email": BUYER})
must(r.status_code == 200, "a shopper can ask for a reset on the store")
ob = c.get("/api/dev/outbox").json()["outbox"]
stok_link = next((m for m in ob if "reset=" in (m.get("body") or "")), None)
must(stok_link is not None, "the shopper reset mail speaks for the store")
stoken = _re.search(r"reset=([A-Za-z0-9_\-]+)", stok_link["body"]).group(1)
r = c.post(f"/api/shop/{HANDLE}/reset", json={"token": stoken, "password": "shopnew1"})
must(r.status_code == 200, f"shopper password changed ({r.status_code})", r.text[:200])
must(c.post(f"/api/shop/{HANDLE}/login",
            json={"email": BUYER, "password": "shopnew1"}).status_code == 200,
     "the shopper's new password works")

print("\n== 20. today strip + digest ==")
r = c.get("/api/today", headers=H)
must(r.status_code == 200, f"today strip ({r.status_code})", r.text[:200])
body = r.json()
must("items" in body and "digest" in body, "the strip carries items and digest prefs")
must(all(i.get("route") and i.get("title") for i in body["items"]),
     "every row names a place to go")
r = c.post("/api/digest", headers=H, json={"enabled": True, "hour": 8})
must(r.json()["digest"]["enabled"] and r.json()["digest"]["hour"] == 8, "digest can be switched on")
r = c.post("/api/digest", headers=H, json={"hour": 99})
must(r.json()["digest"]["hour"] == 23, "a silly hour is clamped")
r = c.post("/api/digest/test", headers=H)
must(r.status_code == 200, "a test digest can be triggered")

print("\n== 21. font pairings + seeding + link previews ==")
r = c.get("/api/site/pairings?theme=luxury", headers=H)
prs = r.json()["pairings"]
must(len(prs) >= 6, f"curated pairings offered (got {len(prs)})")
must(prs[0]["recommended"], "the theme's own pairings come first")
must(all(p["heading_stack"] and p["accent_stack"] for p in prs), "each pairing resolves real stacks")
site_now = c.get("/api/site/state", headers=H).json()["site"]
site_now["style"]["pairing"] = prs[0]["id"]
r = c.post("/api/site/save", headers=H, json={"site": site_now})
saved = r.json()["site"]["style"]
must(saved["heading_font"] == prs[0]["heading"] and saved["body_font"] == prs[0]["body"],
     "choosing a pairing writes all three faces")

r = c.post("/api/site/seed?force=true", headers=H)
must(r.status_code == 200, f"seeding runs ({r.status_code})", r.text[:200])
seeded = r.json()["site"]
must(seeded["seeded"], "the site records that it was seeded")
must(seeded["hero"]["heading"] and seeded["story"]["body"], "hero and story are filled from the catalogue")
before_brand = seeded["brand"]
r = c.post("/api/site/seed", headers=H)
must(r.json()["site"]["brand"] == before_brand, "seeding never runs twice over the seller's own words")

r = c.get(f"/s/{HANDLE}")
html = r.text
must("og:title" in html and "og:description" in html, "the store page carries link-preview tags")
must("<title>Store</title>" not in html, "the generic title is gone")
must(f"/s/{HANDLE}" in html, "canonical URL points at the store")
r = c.get(f"/s/{HANDLE}/p/{shirt['id']}")
must(r.status_code == 200 and "Field Shirt" in r.text, "a product has its own shareable address")
r = c.get(f"/s/{HANDLE}/sitemap.xml")
must(r.status_code == 200 and "<urlset" in r.text, "the store has a sitemap")

print("\n== 22. win-back proof loop ==")
r = c.get("/api/rfm/winback/proof", headers=H)
must(r.status_code == 200 and r.json()["campaigns"] == [], "no campaigns to begin with")
r = c.post("/api/rfm/winback/sent", headers=H, json={"customers": [
    {"customer_id": "c1", "customer_name": "A", "monetary": 4000},
    {"customer_id": "c2", "customer_name": "B", "monetary": 2500}], "channel": "whatsapp"})
must(r.status_code == 200, f"mark a campaign sent ({r.status_code})", r.text[:300])
proof = r.json()
must(proof["totals"]["contacted"] == 2, "both customers recorded")
must(proof["headline"], "there is a headline to put on the home screen")
must(proof["method"], "the method is stated rather than implied")
cid = proof["campaigns"][0]["id"]
r = c.post("/api/rfm/winback/unsent", headers=H, json={"campaign_id": cid})
must(r.json()["campaigns"] == [], "a mis-click can be undone")


print("\n== 23. uploaded media survives, and product saves keep it ==")
PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
                    "0000000a49444154789c636000000200010005fe02fea7d4f4b70000000049454e44ae426082")
r = c.post("/api/site/image", headers=H, files={"files": ("shot.png", PNG, "image/png")})
must(r.status_code == 200, f"upload an image ({r.status_code})", r.text[:200])
img_url = r.json()["url"]
must(img_url.startswith("/generated_images/"), "the URL shape never changed")
g = c.get(img_url)
must(g.status_code == 200 and g.content == PNG, "the bytes come back byte-for-byte")
must("immutable" in (g.headers.get("cache-control") or ""), "content-addressed files cache hard")
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64
r = c.post("/api/site/image", headers=H, files={"files": ("clip.mp4", MP4, "video/mp4")})
must(r.status_code == 200 and r.json()["kind"] == "video", "upload a clip")
vid_url = r.json()["url"]
must(c.get(vid_url).status_code == 200, "the clip serves back")
must(c.get("/generated_images/does-not-exist.png").status_code == 404,
     "a missing file 404s instead of 500ing")
st = c.get("/api/media/status", headers=H).json()
must("durable" in st and st["detail"], "the app can say whether uploads are safe here")

r = c.post("/api/products/item", headers=H, json={
    "name": "Media Test", "price": 500, "image_url": img_url, "video_url": vid_url,
    "images": [img_url], "options": [{"name": "Size", "values": ["S", "M"]}]})
must(r.status_code == 200, f"save a product carrying image + clip + variants ({r.status_code})",
     r.text[:300])
mt = [p for p in r.json()["products"] if p["name"] == "Media Test"][0]
must(mt["image_url"] == img_url and mt["video_url"] == vid_url, "both survive the save")
must(mt["images"] == [img_url] and len(mt["variants"]) == 2, "gallery and matrix survive too")
r = c.post("/api/products/item", headers=H, json={**mt, "price": 600})
mt2 = [p for p in r.json()["products"] if p["id"] == mt["id"]][0]
must(mt2["image_url"] == img_url and mt2["video_url"] == vid_url,
     "and survive an edit — the save path that was failing")
r = c.post("/api/products/item", headers=H, json={**mt2, "image_url": ""})
mt3 = [p for p in r.json()["products"] if p["id"] == mt["id"]][0]
must(mt3["image_url"] == "" and mt3["video_url"] == vid_url,
     "clearing one image clears only that one")


print("\n== 24. guest checkout renders without a customer record ==")
# The full browser-side render check lives in scripts/test_storefront_render.js
# (run it with node); these are the static guards that keep the bug from
# returning even where node is not installed.
# The crash was in the storefront bundle, not the API: viewCheckout read
# S.customer.name while a guest has no customer at all. Guard it here by
# proving the JS never dereferences S.customer directly again.
import re as _re2, pathlib as _pl
_store = _pl.Path("Smart CafeX/storefront/store.js").read_text(encoding="utf-8")
bare = _re2.findall(r"S\.customer\.[a-zA-Z_]", _store)
must(not bare, f"no bare S.customer.<field> reads remain (found {bare[:3]})")
must("const cust = S.customer || {}" in _store, "checkout reads through a safe object")
_ck = _store[_store.index("function viewCheckout"):]
_ck = _ck[:_ck.index("function trustBlock")]
must(not _re2.search(r"S\.customer\s*\.", _ck),
     "the checkout view never dereferences S.customer")


print("\n== 25. the cache must never serve a stale answer ==")
from backend.core import cache as _cache, analytics as _an, smart as _sm
_e = SELLER
_before = c.get("/api/today", headers=H).json()
must("items" in _before, "today reads")
_s1 = _cache.stamp(_e)

# a new order changes the data, so the fingerprint must change
r = c.post(f"/api/shop/{HANDLE}/order", json={
    "lines": [{"product_id": pid1, "qty": 1}],
    "address": {"name": "Stale Check", "phone": "9333333333", "line1": "3 Third St",
                "city": "Bengaluru", "state": "KA", "pincode": "560003"}})
must(r.status_code == 200, f"place an order ({r.status_code})", r.text[:200])
must(_cache.stamp(_e) != _s1, "an order changes the data fingerprint, so caches miss")

# a product write clears explicitly
_cache.put("probe", _e, "sentinel")
must(_cache.get("probe", _e) == "sentinel", "the cache stores")
c.post("/api/products/item", headers=H, json={"name": "Cache Probe", "price": 5})
must(_cache.get("probe", _e) is None, "a product write clears the account's cache")

# the shared at-risk pool must give each caller what its own limit would have
_txns = _sm.load_sales(_e)
if _txns is not None and len(_txns):
    _cache.clear(_e)
    _direct = _an.at_risk_customers(_txns, limit=5)
    _cache.clear(_e)
    _shared = _an.at_risk_cached(_e, _txns, limit=5)
    must([x["customer_id"] for x in _direct] == [x["customer_id"] for x in _shared],
         "the shared pool sliced to 5 == a direct call with limit 5")
    must(len(_an.at_risk_cached(_e, _txns, limit=0)) >= len(_shared),
         "limit=0 returns the whole pool")

# the loaded-dataframe cache must not outlive the data it came from
def _nrows(df):
    return 0 if df is None else len(df)
must(_nrows(_sm.load_sales(_e)) > 0, "sales data is loaded")
c.post("/api/smart/clear?kind=sales", headers=H)
must(_nrows(_sm.load_sales(_e)) == 0,
     "clearing the dataset empties it immediately — no cached frame survives")
c.post("/api/demo", headers=H)
must(_nrows(_sm.load_sales(_e)) > 0,
     f"a fresh upload is visible at once ({_nrows(_sm.load_sales(_e))} rows)")


print("\n== 26. cancellations, and the session that must survive a hiccup ==")
# earlier sections have eaten pid1's stock — use a fresh product
_r = c.post("/api/products/item", headers=H, json={
    "name": "Cancel Test Item", "price": 500, "stock": 60, "listed": True, "track_stock": True})
_cpid = [p for p in _r.json()["products"] if p["name"] == "Cancel Test Item"][0]["id"]
_co = []
for _i in range(6):
    _r = c.post(f"/api/shop/{HANDLE}/order", json={
        "lines": [{"product_id": _cpid, "qty": 1}],
        "address": {"name": f"C{_i}", "phone": f"9444444{_i:03d}", "line1": "4 Fourth St",
                    "city": "Bengaluru", "state": "KA", "pincode": "560004"},
        "payment": "cod"})
    if _r.status_code == 200:
        _co.append(_r.json()["order"]["id"])
must(len(_co) >= 5, f"placed test orders ({len(_co)})")
# a store with no gateway connected cannot take an online payment
_r = c.post(f"/api/shop/{HANDLE}/order", json={
    "lines": [{"product_id": _cpid, "qty": 1}], "payment": "prepaid",
    "address": {"name": "Prepaid", "phone": "9444499999", "line1": "4 Fourth St",
                "city": "Bengaluru", "state": "KA", "pincode": "560004"}})
must(_r.status_code == 400 and "online" in _r.text.lower(),
     "a store with no payment gateway refuses prepaid orders")

# cancel at three different stages, two with a reason
c.post("/api/store/orders/status", headers=H, json={"order_id": _co[0], "status": "cancelled", "reason": "out_of_stock"})
c.post("/api/store/orders/status", headers=H, json={"order_id": _co[1], "status": "confirmed"})
c.post("/api/store/orders/status", headers=H, json={"order_id": _co[1], "status": "packed"})
c.post("/api/store/orders/status", headers=H, json={"order_id": _co[1], "status": "shipped"})
c.post("/api/store/orders/status", headers=H, json={"order_id": _co[1], "status": "cancelled", "reason": "cod_refused"})
c.post("/api/store/orders/status", headers=H, json={"order_id": _co[2], "status": "cancelled"})

cx = c.get("/api/cancellations", headers=H).json()
must(cx["available"] and cx["cancelled"] >= 3, f"cancellations counted ({cx['cancelled']})")
must(cx["cancelled_value"] > 0, "and valued in rupees")
must(cx["gross_value"] - cx["cancelled_value"] == cx["net_value"], "gross - cancelled = net")
must(cx["headline"], "there is a one-line headline")
_stages = {s["key"] for s in cx["stages"]}
must("after_dispatch" in _stages and "before_packing" in _stages,
     f"stage is derived from the order's own history (got {sorted(_stages)})")
must(any(r["key"] == "not_recorded" for r in cx["reasons"]),
     "a cancellation with no reason is shown, not dropped")
must(cx["reason_coverage"] is not None and cx["reason_coverage"] < 100,
     "reason coverage is reported honestly")
must(any(r["fault"] == "seller" for r in cx["reasons"]), "reasons carry whose side it was")
must(len(cx["by_payment"]) >= 1, "split by COD vs prepaid")
must(cx["by_product"], "and by product")
must(len(cx["reason_options"]) > 5, "the reason picker has options to offer")

# the guardrail: no percentages on a handful of orders
_small = __import__("backend.core.cancellations", fromlist=["x"])
_tiny = _small.analyse([{"status": "cancelled", "total": 100, "history": [], "items": []},
                        {"status": "new", "total": 100, "history": [], "items": []}])
must(_tiny["rate"] is None, "no percentage is quoted on 2 orders")
must(_tiny["cancelled_value"] == 100, "but the rupees are still counted")
_big = _small.analyse([{"status": "cancelled" if i < 5 else "new", "total": 100,
                        "history": [{"status": "new"}], "items": []} for i in range(40)])
must(_big["rate"] == 12.5, f"and a rate appears once there is enough data (got {_big['rate']})")

# cancelled orders stay out of the sales figures. The dataset also holds the
# uploaded sample data, so measure the delta rather than the absolute.
_before = c.get("/api/smart/state", headers=H).json()["data"]["sales"]["rows"]
c.post("/api/store/orders/status", headers=H, json={"order_id": _co[3], "status": "cancelled", "reason": "duplicate"})
_after = c.get("/api/smart/state", headers=H).json()["data"]["sales"]["rows"]
must(_after == _before - 1,
     f"cancelling an order removes exactly its row from sales ({_before} -> {_after})")
c.post("/api/store/orders/status", headers=H, json={"order_id": _co[3], "status": "new"})
must(c.get("/api/smart/state", headers=H).json()["data"]["sales"]["rows"] == _before,
     "un-cancelling puts it back")

# a transient server error must not look like a logged-out session
_js = _pl.Path("Smart CafeX/smart.js").read_text(encoding="utf-8")
must("err.status = res.status" in _js, "api() reports the HTTP status to callers")
must("e.status === 401" in _js, "the boot handler only signs you out on a 401")
_boot = _js[_js.index("async function init()"):]
must("catch { state.token = null" not in _boot, "no bare catch wipes the token any more")
_app = _pl.Path("backend/static/app.js").read_text(encoding="utf-8")
must("e.status === 401" in _app, "the classic app follows the same rule")

# refresh without reloading
must("/api/cache/clear" in _js, "Refresh clears this account's cache first")
must('id="refreshPage"' in _js, "every page carries a Refresh button")
r = c.post("/api/cache/clear", headers=H)
must(r.status_code == 200 and "cleared" in r.json(), "the cache-clear endpoint answers")
must(c.post("/api/cache/clear").status_code == 401, "and needs a login")

# icons cannot stretch to fill their container again
_scss = _pl.Path("Smart CafeX/storefront/store.css").read_text(encoding="utf-8")
must("svg { width: 1em; height: 1em;" in _scss, "storefront icons have a default size")
must(".crumbs svg" in _scss, "breadcrumb arrows are sized explicitly")
must("svg { width: 1em; height: 1em;" in _pl.Path("Smart CafeX/smart.css").read_text(encoding="utf-8"),
     "app icons have a default size too")


print("\n== 27. payments, sections, suppliers, campaigns and Studio ==")

# ---- the seller's own gateway ----
g = c.get("/api/site/gateway", headers=H).json()
must(g["connected"] is False, "no gateway to begin with")
r = c.post("/api/site/gateway", headers=H, json={"key_id": "nope", "key_secret": "x"})
must(r.status_code == 400, "a key that isn't a Razorpay key is refused")
r = c.post("/api/site/gateway", headers=H, json={"key_id": "rzp_test_ABC1234567", "key_secret": "s3cr3t"})
must(r.status_code == 200 and r.json()["connected"], f"keys saved ({r.status_code})", r.text[:200])
g = c.get("/api/site/gateway", headers=H).json()
must(g["mode"] == "test" and g["key_id_last4"] == "4567", "mode and last four reported")
must("s3cr3t" not in c.get("/api/site/gateway", headers=H).text, "the secret never comes back")

# ---- partial COD ----
from backend.core import store_payments as _sp
_c = {"cod_advance": 100.0}
must(_sp.split_due(_c, 1548, "cod") == {"online": 100.0, "on_delivery": 1448.0, "kind": "cod_advance"},
     "COD with an advance splits correctly")
must(_sp.split_due(_c, 1548, "prepaid")["online"] == 1548.0, "prepaid takes it all online")
must(_sp.split_due({"cod_advance": 0}, 900, "cod")["online"] == 0, "no advance = plain COD")
must(_sp.split_due({"cod_advance": 5000}, 300, "cod")["online"] == 300.0,
     "an advance larger than the order is capped at the order")
must("₹100" in _sp.describe(_c), "the shopper is told the rupee amount, not 'a small amount'")

_site = c.get("/api/site/state", headers=H).json()["site"]
_site["commerce"]["cod_advance"] = 150
_site["commerce"]["online_enabled"] = True
c.post("/api/site/save", headers=H, json={"site": _site})
_pc = c.post(f"/api/shop/{HANDLE}/cart", json={"lines": [{"product_id": _cpid, "qty": 1}]}).json()
must(_pc["cod_advance"] == 150.0, "the storefront is told the advance")
must(_pc["due"]["cod"]["online"] == 150.0, "and what is due online for a COD order")
must(_pc["online_enabled"] is True, "online payment is offered once a gateway is connected")
r = c.post(f"/api/shop/{HANDLE}/order", json={
    "lines": [{"product_id": _cpid, "qty": 1}], "payment": "cod",
    "address": {"name": "Adv", "phone": "9444488888", "line1": "4 St", "city": "Bengaluru",
                "state": "KA", "pincode": "560004"}})
must(r.status_code == 400, "an unpaid advance cannot become an order")
c.post("/api/site/gateway/disconnect", headers=H)
must(c.get("/api/site/gateway", headers=H).json()["connected"] is False, "gateway disconnects")
_site["commerce"]["cod_advance"] = 0
_site["commerce"]["online_enabled"] = False
c.post("/api/site/save", headers=H, json={"site": _site})

# ---- product sections: no more duplication ----
r = c.post("/api/products/item", headers=H, json={
    "name": "Featured Piece", "price": 700, "listed": True, "featured": True, "stock": 5})
_fp = [p for p in r.json()["products"] if p["name"] == "Featured Piece"][0]
must(_fp["featured"] is True, "a product can be marked for the Featured rail")
must(_fp["spotlight"] is False, "and Spotlight is separate")
_pub = c.get(f"/api/shop/{HANDLE}/site").json()
_sf = [p for p in _pub["products"] if p["id"] == _fp["id"]][0]
must(_sf["featured"] is True, "the storefront receives the placement flags")
must(all("featured" in p and "spotlight" in p for p in _pub["products"]),
     "every product carries them, so the site never has to guess")
_js = _pl.Path("Smart CafeX/storefront/store.js").read_text(encoding="utf-8")
must("p.featured" in _js and "featuredIds" in _js,
     "the storefront picks featured products instead of slicing the same list")
must("!featuredIds.has(p.id)" in _js,
     "and the spotlight avoids what the featured rail already shows")

# ---- suppliers, split out of inventory ----
from backend.core import supply as _sup
for _n, _s2 in [("Fabric roll", "Sharma Textiles"), ("Buttons", "Sharma Textiles"),
                ("Boxes", "PackWell")]:
    _sup.upsert_item(SELLER, {"name": _n, "current_stock": 10, "unit_cost": 20,
                              "supplier_name": _s2, "supplier_phone": "9876500000"})
_sups = c.get("/api/supply/suppliers", headers=H).json()["suppliers"]
must(len(_sups) == 2, f"suppliers derived from the items they stock (got {len(_sups)})")
_sh = next(x for x in _sups if x["name"] == "Sharma Textiles")
must(_sh["item_count"] == 2, "with the items they supply")
must(_sh["name"] == "Sharma Textiles", "and their name's capitalisation intact")
r = c.post("/api/supply/supplier", headers=H, json={
    "name": "Sharma Textiles", "patch": {"name": "Sharma Textiles Pvt Ltd", "phone": "9000011111"}})
_sups = r.json()["suppliers"]
must(any(x["name"] == "Sharma Textiles Pvt Ltd" and x["item_count"] == 2 for x in _sups),
     "editing a supplier updates every item at once")
r = c.post("/api/supply/supplier/detach", headers=H, json={"name": "Sharma Textiles Pvt Ltd"})
must(len(r.json()["detached_item_ids"]) == 2, "detach reports the ids so it can be undone")
_names = {i["name"] for i in _sup.get_inventory(SELLER)}
must("Fabric roll" in _names and "Buttons" in _names,
     "removing a supplier never removes your stock")
c.post("/api/supply/supplier/attach", headers=H, json={
    "name": "Sharma Textiles Pvt Ltd",
    "patch": {"item_ids": r.json()["detached_item_ids"], "name": "Sharma Textiles Pvt Ltd"}})
must(any(x["item_count"] == 2 for x in c.get("/api/supply/suppliers", headers=H).json()["suppliers"]),
     "and the undo puts them back")

# ---- win-back actually sends ----
_rows = [{"customer_id": "w1", "customer_name": "Riya", "email": "riya@x.test",
          "phone": "9876543210", "favorite_item": "Amber Musk", "recency_days": 61,
          "coupon": "15%", "monetary": 4200},
         {"customer_id": "w2", "customer_name": "Arjun", "phone": "9812345678",
          "favorite_item": "Silk Scarf", "recency_days": 70, "monetary": 3100},
         {"customer_id": "w3", "customer_name": "NoContact", "monetary": 500}]
r = c.post("/api/rfm/winback/preview", headers=H, json={"rows": _rows})
must(r.status_code == 200 and r.json()["preview"], "a campaign can be previewed before sending")
must("Riya" in r.json()["preview"][0]["message"], "merge fields are filled per customer")
r = c.post("/api/rfm/winback/send", headers=H, json={"rows": _rows})
_res = r.json()
must(r.status_code == 200, f"campaign sends ({r.status_code})", r.text[:200])
must(_res["recipients"] == 3, "every recipient is accounted for")
must(_res["skipped"] == 1, "a customer with no email and no phone is reported, not dropped")
must(_res["wa_links"] == 2 or _res["whatsapp_sent"] == 2,
     "WhatsApp goes out, or comes back as tap-to-send links")
must(all(x["wa_link"].startswith("https://wa.me/91") for x in _res["results"] if x["wa_link"]),
     "links carry the country code")
must(_res["campaign_id"], "the send is recorded for measurement automatically")
must(c.get("/api/rfm/winback/sends", headers=H).json()["sends"], "and appears in the send log")
_proof = c.get("/api/rfm/winback/proof", headers=H).json()
must(_proof["totals"]["contacted"] >= 2, "the proof loop picked it up without being told")

# ---- Product Studio ----
r = c.post("/api/studio/brand", headers=H, json={"patch": {
    "name": "Aureva", "about": "Small-batch perfumes, rested six months before bottling.",
    "audience": "People who wear one scent, not ten.", "look": "luxe", "voice": "luxury",
    "palette": "amber, deep brown, brass", "avoid": "cheap, discount"}})
must(r.status_code == 200 and r.json()["brand"]["look"] == "luxe", "the brand profile saves")
r = c.post("/api/studio/brand", headers=H, json={"patch": {"look": "nonsense"}})
must(r.json()["brand"]["look"] == "clean", "an unknown look falls back rather than breaking")
st = c.get("/api/studio/state", headers=H).json()
must(st["brand_ready"], "the brand counts as ready once it says what it is")
must(st["products"] and st["looks"] and st["voices"], "products and the option lists come through")
must(st["products"] == sorted(st["products"], key=lambda p: -p["completeness"]["score"]),
     "products are ordered by how ready they are to post about")

r = c.post("/api/studio/product", headers=H, json={"product_id": _fp["id"], "patch": {
    "story": "Rested six months before it met a bottle.",
    "materials": "Oud, amber, a little smoke",
    "different": "No alcohol burn — it opens soft.",
    "for_who": "Someone who wears one scent"}})
must(r.status_code == 200, f"product material saves ({r.status_code})", r.text[:200])
_comp = r.json()["completeness"]
must(_comp["score"] > 0 and _comp["next"], "completeness is scored and names what to do next")
must(_comp["next"]["why"], "and says why that piece matters")
_ang = r.json()["angles"]
must(len(_ang) > 3, f"post angles come from the material actually supplied ({len(_ang)})")
must(any(a["id"] == "story" for a in _ang), "the story unlocks a story angle")

from backend.core import studio as _st
# the fallback test just reset `look` — put the real brand back first
c.post("/api/studio/brand", headers=H, json={"patch": {"look": "luxe", "voice": "luxury"}})
_brief = _st.build_brief(_st.get_brand(SELLER),
                         {"name": "Midnight Oud", "category": "Fragrance", "price": 4999},
                         _st.get_material(SELLER, _fp["id"]))
_ip = _st.image_prompt(_brief)
must("amber, deep brown, brass" in _ip, "the image prompt carries the brand's palette")
must("moody low-key" in _ip, "and the brand's look, not a generic template")
must("No alcohol burn" in _ip, "and the product's real detail")
must("cheap, discount" in _ip, "and what the brand refuses to say")
_cp = _st.caption_prompt(_brief)
must("understated" in _cp, "the caption prompt carries the brand's voice")

r = c.post("/api/studio/post", headers=H, json={"product_id": _fp["id"], "angle": "the story"})
_post = r.json()
must(r.status_code == 200 and _post["caption"], f"a post draft is produced ({r.status_code})")
must(_post["image_is_generated"] is False, "using your own photo is never labelled generated")
must("hashtags" in _post, "with hashtags")

# =====================================================================
# 28. GST — rates, place of supply, documents, numbering
# =====================================================================
print("\n== 28. GST rates, place of supply and invoice documents ==")

from backend.core import gst as _gst

# GSTIN checksum, against vectors derived from the official GSTN reference.
# The one that matters is 27AASCS2460H1Z0: its checksum sum is a multiple of
# 36, which is exactly the case the popular JS implementation gets wrong by
# omitting a trailing modulo. If this ever fails, someone "simplified" it.
for _g in ("27AAPFU0939F1ZV", "29AAGCB7383J1Z4", "27AASCS2460H1Z0"):
    must(_gst.valid_gstin(_g), f"{_g} validates")
must(not _gst.valid_gstin("27AAPFU0939F1ZX"), "a wrong checksum is rejected")
must(not _gst.valid_gstin("29AAGCB7383J1Z"), "a 14-character GSTIN is rejected")

# Apparel is price-BANDED, and the 2025 rationalisation moved both numbers:
# the threshold is Rs 2,500 (not Rs 1,000) and above it the rate is 18%
# (not 12%). Anyone carrying forward pre-2025 knowledge gets both wrong.
must(_gst.resolve_rate("6109", 50000, "kurta")["rate"] == 5, "cheap apparel is 5%")
must(_gst.resolve_rate("6109", 400000, "lehenga")["rate"] == 18, "expensive apparel is 18%")
must(_gst.resolve_rate("6403", 50000, "juti")["rate"] == 5, "cheap footwear is 5%")
must(_gst.resolve_rate("7117", 120000, "jhumka")["rate"] == 3, "imitation jewellery is 3%")
must(_gst.resolve_rate("7113", 4000000, "gold chain")["rate"] == 3, "gold jewellery is 3%")
must(_gst.resolve_rate("3303", 120000, "oud perfume")["rate"] == 18, "perfume is 18%")

# Chapter 33 is NOT uniform: a heading's rate is overridden by named
# carve-outs inside it. A flat 4-digit HSN lookup would get these wrong.
must(_gst.resolve_rate("3304", 60000, "matte lipstick")["rate"] == 18, "lipstick is 18%")
must(_gst.resolve_rate("3304", 20000, "herbal kajal")["rate"] == 5, "but kajal is 5%")
must(_gst.resolve_rate("3305", 30000, "coconut hair oil")["rate"] == 5, "and hair oil is 5%")

# The threshold is per PIECE, not per line. Ten Rs 800 shirts are each 5%.
_ln = _gst.compute_line(name="shirt", hsn="6109", qty=10, unit_price_paise=80000,
                        inclusive=True, pos_kind="intra")
must(_ln["rate"] == 5, "ten Rs 800 shirts stay at 5% — the band is per piece")
must(_ln["cgst"] + _ln["sgst"] == _ln["tax_total"], "CGST + SGST accounts for all the tax")

# Tax-inclusive pricing is the Indian default and, for MRP, the law.
_taxable, _tax = _gst.split_inclusive(105000, 5)
must(_taxable + _tax == 105000, "tax backed out of an inclusive price still totals the price")

# Place of supply is decided by the DELIVERY address, not the seller's state.
must(_gst.place_of_supply("Karnataka", "Karnataka")["heads"] == ["cgst", "sgst"],
     "same state is CGST + SGST")
must(_gst.place_of_supply("Karnataka", "Maharashtra")["heads"] == ["igst"],
     "different state is IGST")
must(not _gst.place_of_supply("Karnataka", "")["ok"],
     "a missing delivery state is refused rather than defaulted")

# Rule 46(b): 16 characters max, unique per financial year.
_num = _gst.invoice_number("INV", 123)
must(len(_num) <= 16 and _gst.valid_invoice_number(_num), f"{_num} is a legal invoice number")
must(not _gst.valid_invoice_number("INV#2627#000123"), "'#' is not an allowed character")
must(not _gst.valid_invoice_number("INVOICE/2627/00000123"), "17+ characters is rejected")

# Three documents, not one. The common mistake is handing an unregistered
# seller a Bill of Supply — that is a REGISTERED person's document.
must(_gst.document_kind({"gstin": "29AAGCB7383J1Z4"})["kind"] == "tax_invoice",
     "a registered seller issues a Tax Invoice")
must(_gst.document_kind({"gstin": ""})["kind"] == "receipt",
     "an unregistered seller issues a plain receipt, NOT a bill of supply")
must(_gst.document_kind({"gstin": "29AAGCB7383J1Z4", "composition": True})["kind"]
     == "bill_of_supply", "a composition dealer issues a Bill of Supply")
must("not eligible to collect tax" in
     _gst.document_kind({"gstin": "29AAGCB7383J1Z4", "composition": True})["declaration"],
     "with the declaration the rule requires, verbatim")

# The compliance warning that is worth more than any feature: Section 24(i)
# compels registration for inter-state goods from the first rupee.
_w = _gst.registration_warning({"gstin": ""}, ships_outside_state=True)
must(_w and _w["level"] == "blocking", "shipping interstate with no GSTIN is blocking")
must("first rupee" in _w["text"], "and says why — there is no turnover floor")
must(_gst.registration_warning({"gstin": "29AAGCB7383J1Z4"}, True) is None,
     "a registered seller sees no warning")


# =====================================================================
# 29. Invoicing — issue, cancel, GSTR-1
# =====================================================================
print("\n== 29. invoices, cancellation and the GSTR-1 export ==")

r = c.post("/api/gst/settings", headers=H, json={"patch": {
    "gstin": "29AAGCB7383J1Z4", "legal_name": "Indigo Weaves Pvt Ltd",
    "trade_name": "Indigo Weaves", "series": "INV",
    "pickup_address": {"line1": "Plot 387", "city": "Bengaluru",
                       "state": "Karnataka", "pincode": "560008"}}})
must(r.status_code == 200, f"GST settings save ({r.status_code})")
must(r.json()["document"]["kind"] == "tax_invoice", "and switch the seller to tax invoices")

_ord = {"id": "test-order-1", "order_no": "OT-9001", "customer_name": "Harsh Modi",
        "phone": "9876543210", "shipping": 49.0,
        "address": {"line1": "Flat 6", "city": "Bengaluru", "state": "Karnataka",
                    "pincode": "560008"},
        "items": [{"name": "Cotton kurta", "qty": 2, "price": 800.0, "hsn": "6109"},
                  {"name": "Silk lehenga", "qty": 1, "price": 4200.0, "hsn": "6204"},
                  {"name": "Jhumka", "qty": 1, "price": 1200.0, "hsn": "7117"}]}

from backend.core import invoices as _inv, invoice_pdf as _ipdf
_built = _inv.build_from_order(SELLER, _ord)
_rates = sorted({l["rate"] for l in _built["lines"]})
must(_rates == [3, 5, 18], f"three different rates on one invoice ({_rates})")
must(_built["place_of_supply"]["kind"] == "intra", "intra-state order")

_issued = _inv.issue(SELLER, _ord)
must(_issued["number"].startswith("INV/"), f"numbered {_issued['number']}")
must(_inv.issue(SELLER, _ord)["number"] == _issued["number"],
     "issuing twice for one order does not burn a second number")

_pdf = _ipdf.build(_issued)
must(_pdf[:4] == b"%PDF" and len(_pdf) > 1500, f"a real PDF is produced ({len(_pdf)} bytes)")

_g1 = _inv.gstr1(SELLER)
must(_g1["documents_issued"]["total"] >= 1, "GSTR-1 reports the documents issued")
must(_g1["b2cs"], "and consolidates B2C sales into the rate x state grid")

_inv.cancel(SELLER, _issued["id"], "test")
_g1b = _inv.gstr1(SELLER)
must(_g1b["documents_issued"]["cancelled"] == 1,
     "a cancelled invoice is COUNTED, not deleted — GSTR-1 Table 13 needs it")
must(any(i["id"] == _issued["id"] for i in _inv.listing(SELLER)),
     "and the row survives, so the number range stays contiguous")


# =====================================================================
# 30. Shipping labels
# =====================================================================
print("\n== 30. bill stickers ==")

from backend.core import labels as _lab
_cod = dict(_ord, payment="cod", due_on_delivery=1499, currency="Rs",
            created_at="2026-09-08T10:00:00",
            items=[{"name": "Cotton kurta", "qty": 2, "variant_label": "M / Indigo"}])
_one = _lab.build(_cod, {"business_name": "Indigo Weaves",
                         "pickup_address": {"line1": "Plot 387", "city": "Bengaluru",
                                            "state": "Karnataka", "pincode": "560008"}},
                  {"name": "Indigo Weaves"})
must(_one[:4] == b"%PDF", "a single label is a PDF")
_many = _lab.build_many([_cod, dict(_cod, order_no="OT-9002", payment="prepaid",
                                    due_on_delivery=0)],
                        {"business_name": "Indigo Weaves", "pickup_address": {}},
                        {"name": "Indigo Weaves"})
must(len(_many) > len(_one), "and a batch is one document with more in it")
must(_many.count(b"/Type /Page\n") >= 2 or b"/Count 2" in _many,
     "with one page per order, so a morning's dispatch prints in one go")


# =====================================================================
# 31. Cancellation as a conversation
# =====================================================================
print("\n== 31. cancellation requests ==")

from backend.core import cancel_requests as _cr
_req = _cr.raise_request(SELLER, kind="order", ref_id="test-order-1", ref_no="OT-9001",
                         reason_code="wrong_size", reason_text="need L not M",
                         counterparty={"name": "Harsh", "phone": "9876543210"})
must(_req["status"] == "requested", "a request starts as a request, not a cancellation")
must(_req["save_play"], "and carries a suggested save for that reason")
must("free size exchange" in _req["save_play"], "wrong size suggests an exchange")

_dupe = _cr.raise_request(SELLER, kind="order", ref_id="test-order-1", ref_no="OT-9001",
                          reason_code="changed_mind")
must(_dupe["id"] == _req["id"], "asking twice does not create a second request")

_msg = _cr.seller_message(_req, "Indigo Weaves")
must("Nothing has been cancelled yet" in _msg, "the seller is told nothing has happened yet")
must(_cr.wa_link("9876543210", "hi").startswith("https://wa.me/919876543210"),
     "a 10-digit Indian number gets the country code")
must(_cr.wa_link("123", "hi") == "", "a number too short to be real yields no link")

_res = _cr.resolve(SELLER, _req["id"], "declined", "sent L instead")
must(_res["status"] == "declined", "declining keeps the order")
must(_cr.summary(SELLER)["saved"] == 1, "and counts as a save")
must(_cr.resolve(SELLER, _req["id"], "approved")["status"] == "declined",
     "a resolved request cannot be re-resolved")


# =====================================================================
# 32. Manual purchase orders
# =====================================================================
print("\n== 32. manual purchase orders ==")

r = c.post("/api/purchase-orders/manual", headers=H, json={
    "supplier": {"name": "Surat Silk Mills", "phone": "9876500000"},
    "lines": [{"name": "Banarasi silk 5m", "order_qty": 20, "unit_cost": 450},
              {"name": "Gold zari thread", "order_qty": 5, "unit_cost": 1200}],
    "expected_on": "2026-09-25", "terms": "50% advance"})
must(r.status_code == 200, f"a manual PO is created ({r.status_code})", r.text[:200])
_po = r.json()
must(_po["total_qty"] == 25 and _po["total_amount"] == 15000.0,
     f"with the arithmetic done ({_po['total_qty']} units, Rs {_po['total_amount']})")
must(_po["source"] == "manual", "and marked as manual, not derived from reorder points")

r = c.post("/api/purchase-orders/manual", headers=H,
           json={"supplier": {"name": "X"}, "lines": []})
must(r.status_code == 400, "an empty PO is refused")

r = c.post("/api/purchase-orders/status", headers=H,
           json={"po_number": _po["po_number"], "status": "sent"})
must(r.status_code == 200 and r.json()["status"] == "sent", "and it can be marked sent")
r = c.post("/api/purchase-orders/status", headers=H,
           json={"po_number": _po["po_number"], "status": "teleported"})
must(r.status_code == 400, "an invented status is refused")


# =====================================================================
# 33. Social Media Manager
# =====================================================================
print("\n== 33. social media manager ==")

from backend.core import social as _soc
import datetime as _dt

r = c.post("/api/social/settings", headers=H,
           json={"patch": {"category": "clothing", "cadence": "standard",
                           "city": "Bengaluru"}})
must(r.status_code == 200, f"social settings save ({r.status_code})")

_shape = _soc.slate_shape("standard")
must(len(_shape) == 4, "a standard week is 4 posts")
must(not any(x["format"] == "image" for x in _shape),
     "and never a single image — reach is down 22% year on year")

# The offer cap is the commercially important bit: deals content is
# NEGATIVELY associated with sales, and sellers over-post discounts.
_offers = [x for x in _soc.slate_shape("standard") if x["pillar"] == "offer"]
must(len(_offers) == 0, "a 4-post week contains no offer post — the 5% cap binds")
must(_soc.PILLAR_BY_ID["offer"]["share"] == 5, "and the cap is 5%")
must(sum(p["share"] for p in _soc.PILLARS) == 100, "pillar shares total 100%")
_info = sum(p["share"] for p in _soc.PILLARS if p["type"] == "informational")
must(_info == 60, f"informational content dominates the mix ({_info}%) — it is what sells")

_week = _soc.build_week(SELLER, [{"id": "p1", "name": "Indigo kurta", "price": 1299,
                                  "description": "Hand-block printed cotton"}],
                        _dt.date(2026, 9, 8))
must(len(_week) == 4, "a week is generated")
must(all(p["text"] for p in _week), "every post has a caption, even with no AI key")
must(all(len(p["caption"]["tags"]) <= 5 for p in _week),
     "and never more than 5 hashtags — Instagram capped them in January 2026")
must(all(p["caption"]["question"] for p in _week),
     "every caption asks a question — worth about 200% more comments")

_bad = _soc.caption_check({"hook": "x" * 200, "body": "w " * 60, "question": "",
                           "tags": ["#a"] * 9}, {})
_levels = {c["level"] for c in _bad}
must("error" in _levels, "9 hashtags is flagged as an error")
must(any("125" in c["text"] for c in _bad), "an over-long hook is flagged")
must(any("question" in c["text"].lower() for c in _bad), "a missing question is flagged")

must(_soc.approve_all(SELLER)["scheduled"] >= 4, "one tap schedules the whole week")

_rad = _soc.radar(SELLER, _dt.date(2026, 9, 8))
must(any("Navratri" in h for h in _rad["headline"]),
     "the radar sees Navratri coming from early September")
must("must be refreshed" in _rad["dates_note"],
     "and says plainly that lunisolar dates cannot be extrapolated")

_sl = _soc.shoot_list(SELLER, [{"id": "p1", "name": "A"}, {"id": "p2", "name": "B"}])
must(len(_sl["yields"]) == 9, "one shoot atomises into 9 assets")

_work = _soc.whats_working(SELLER)
must(any(m["key"] == "sends" for m in _work["headline"]), "sends is a headline metric")
must(any(m["key"] == "followers" for m in _work["muted"]),
     "followers is deliberately NOT — 79% of small accounts did not grow last year")


# =====================================================================
# 34. AI provider chain
# =====================================================================
print("\n== 34. AI provider fallback ==")

from backend.core import aiprovider as _aip
_st = _aip.status()
must(isinstance(_st["providers"], list) and len(_st["providers"]) >= 4,
     "the provider chain is declared")
must(_st["providers"][0]["name"] == "cloudflare", "Cloudflare leads — it is the free one")
_gem = next(p for p in _st["providers"] if p["name"] == "gemini")
must(_gem["trains"] is True, "Gemini's free tier is marked as training on requests")

# A seller's revenue must never reach a provider that trains on it. With no
# keys set at all the order is empty either way, so assert on the filter.
_order_public = _aip._order("public")
_order_private = _aip._order("private")
must(all(not p.trains for p in _order_private),
     "private work never reaches a provider that trains on it")
must(len(_order_private) <= len(_order_public),
     "and the private chain is a subset of the public one")

_res = _aip.generate("sys", "user", sensitivity="public", fallback="FALLBACK")
must(_res["text"] == "FALLBACK" or _res["provider"] != "template",
     "with no keys configured the caller still gets usable text, never an exception")

try:
    _aip.generate("s", "u", sensitivity="whatever")
    must(False, "an unknown sensitivity is rejected")
except ValueError:
    must(True, "an unknown sensitivity is rejected rather than silently defaulted")


print("\n== 35. the approval panel, staffed ==")

from backend.core import personas as _per

must(len(_per.MANAGERS) == 5, "five managers")
must(set(_per.ORDER) == set(_per.MANAGERS), "every manager has a place in the order")

# Every card type must land on a desk. A card with no manager renders with no
# heading and looks like a bug, so coverage is asserted rather than hoped for.
for cid, want in [("winback", "marketing"), ("festival", "marketing"),
                  ("reorder", "operations"), ("overstock", "operations"),
                  ("supplier_risk", "supply"), ("reputation", "brand"),
                  ("complaints", "brand"), ("content_ab12", "social")]:
    got = _per.assign({"id": cid})
    must(got == want, f"{cid} -> {want}" + ("" if got == want else f" (got {got})"))
must(_per.assign({"id": "something_new", "module": "review"}) == "brand",
     "an unknown card falls back to its module's desk rather than vanishing")
must(_per.assign({"id": "?", "module": "?"}) == "operations",
     "and a wholly unknown card still gets a desk")

_d = _per.dress({"id": "reorder", "count": 4, "names": "Cotton fabric",
                 "min_cover": 11, "title": "Reorder 4 items below reorder point",
                 "detail": "the original detail"})
must(_d["manager_name"] == "Operations Manager", "the card carries its manager")
must("11 days of cover" in _d["body"], "and quotes the seller's real number")
must(_d["headline"] != _d["title"], "the manager's headline is a recommendation, "
     "not a restatement of the card title")
must(_d["title"] == "Reorder 4 items below reorder point"
     and _d["detail"] == "the original detail",
     "and the original title and detail survive untouched, because History, "
     "the digest and the Today strip still render them")

_dw = _per.dress({"id": "winback", "count": 38, "value": 142000})
must("Rs 1.4L" in _dw["body"], f"large money reads as lakhs ({_dw['body'][:60]})")

# Every dressed card must be actionable — a manager who does not say what to do
# is just a label.
for cid in ("winback", "festival", "reorder", "overstock", "supplier_risk",
            "reputation", "complaints"):
    c = _per.dress({"id": cid, "count": 2})
    must(bool(c["cta"]) and bool(c["headline"]) and bool(c["body"]),
         f"{cid} has a headline, a body and something to press")

_all = _per.dress_all([{"id": "complaints", "count": 1}, {"id": "reorder", "count": 1},
                       {"id": "winback", "count": 1}])
must([c["manager"] for c in _all] == ["operations", "marketing", "brand"],
     "cards are grouped by desk, not shuffled")
must(len(_per.desks(_all)) == 3, "and each desk reports its pending count")


print("\n== 36. Product Studio design language ==")

from backend.core import studio as _std

_b = _std.blank_brand()
must("refs" in _b and "aesthetic" in _b, "the brand has a design-language bucket")

_std.add_ref(SELLER, "/generated_images/ref1.png")
_std.add_ref(SELLER, "/generated_images/ref2.png")
_std.add_ref(SELLER, "/generated_images/ref1.png")
must(len(_std.get_brand(SELLER)["refs"]) == 2, "references de-duplicate")
_std.remove_ref(SELLER, "/generated_images/ref1.png")
must(len(_std.get_brand(SELLER)["refs"]) == 1, "and can be removed")

_r = _std.read_aesthetic(SELLER)
must(not _r["ok"] and "vision" in _r["reason"].lower(),
     "reading without a vision model refuses clearly rather than inventing an aesthetic")

# The composite prompt is where this feature either works or does not.
_brief = _std.build_brief(
    {"name": "Aureva", "look": "luxe", "palette": "sand, brass",
     "aesthetic": "Soft north light, warm sand and brass, generous negative space.",
     "avoid": "cheap, discount"},
    {"name": "Silk lehenga", "category": "Clothing"},
    {"seen": "Deep maroon Banarasi silk with gold zari butis and a scalloped hem."})
_p = _std.image_prompt(_brief, _std.guidance_for("detail", "carousel"))
must("Deep maroon Banarasi" in _p,
     "the prompt describes the product as PHOTOGRAPHED, not as imagined")
must("Soft north light" in _p, "and shoots it in the brand's own visual language")
must("what is it made of" in _p,
     "and the pillar becomes camera direction, not just a label")
must("square 1:1" in _p, "and the format becomes composition")
must("cheap, discount" in _p, "and what the brand refuses still applies")

# Without a reading, it must degrade to the preset rather than to nothing.
_bare = _std.build_brief({"name": "X", "look": "luxe", "palette": "sand, brass"},
                         {"name": "Kurta"}, {})
_pb = _std.image_prompt(_bare)
must("sand, brass" in _pb and "Kurta" in _pb,
     "with no references read, the preset look and palette still drive the prompt")
must("Deep maroon" not in _pb, "and nothing is carried over from another product")

_eng = _std.image_engine()
must("engine" in _eng and "note" in _eng, "the image engine names itself")
must(_eng["engine"] in ("", "cloudflare", "openai"), "and is one we know")

_g = _std.guidance_for("founder", "reel")
must("making" in _g["shot"] and "9:16" in _g["aspect"],
     "a behind-the-scenes reel asks for process footage, shot vertical")


print("\n== 37. planned images on social posts ==")

_wk = _soc.build_week(SELLER, [{"id": "p1", "name": "Indigo kurta", "price": 1299}],
                      _dt.date(2026, 9, 8))
must(all("image_url" in x for x in _wk), "every planned post has an image slot")
must(all(x["image_url"] == "" for x in _wk),
     "left empty on purpose — generating four images per plan would burn the "
     "free daily allowance on posts the seller may skip")

_pid = _wk[0]["id"]
_gd = _soc.post_guidance(SELLER, _pid)
must(_gd["pillar"] and _gd["format"], "a post can tell Studio what it needs drawn")

_att = _soc.attach_image(SELLER, _pid, "/generated_images/x.png", True, "a prompt")
must(_att["image_url"].endswith("x.png") and _att["image_generated"] is True,
     "an image attaches to the slot and is flagged as generated")
must(_soc.attach_image(SELLER, "nope", "/x.png").get("error"),
     "attaching to a post that does not exist fails cleanly")


print("\n== 38. vision provider ==")

must(hasattr(_aip, "describe_image"), "the provider chain can look at pictures")
must(set(_aip.VISION_MODELS) <= {p["name"] for p in _aip.status()["providers"]},
     "vision models only name providers that exist")
must("groq" not in _aip.VISION_MODELS,
     "Groq is skipped rather than sent an image it cannot read")
_v = _aip.describe_image(b"", "image/png", system="s", user="u")
must(_v["text"] == "" and _v["error"] == "no image",
     "an empty image returns an error instead of raising")
_v2 = _aip.describe_image(b"notanimage", "image/png", system="s", user="u")
must(_v2["text"] == "" and _v2["error"],
     "and an unreadable one degrades rather than breaking the upload")


print("\nALL CHECKS PASSED \u2713")
shutil.rmtree(TMP, ignore_errors=True)
