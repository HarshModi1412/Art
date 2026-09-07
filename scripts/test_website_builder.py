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

print("\nALL CHECKS PASSED \u2713")
shutil.rmtree(TMP, ignore_errors=True)
