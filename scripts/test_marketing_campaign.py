"""
Tests for the Marketing Campaign pipeline, end to end.

What a seller is promised, and what each section proves:

  1. Mapping asks for customer phone and email, and finds them even when the
     phone column is also the customer ID.
  2. The favourite product reads like a product ("Chikankari Kurta"), never a
     variant suffix or a SKU.
  3. One offer for everyone, and every code is real: issued per customer,
     single use, expiring, honoured at checkout, given back on cancellation.
  4. A campaign is built from the seller's own sales: the right audience for
     the reason, a message per customer with their code and a link that
     applies it, and an honest send report.
  5. The picture allowance: two a month outside paid Pro Max, and an upload
     request (not an error) when no picture can be made.
  6. WhatsApp: tap-to-send with just a number, and a template payload Meta
     will accept for automatic sending.

Run: python scripts/test_marketing_campaign.py
"""
from __future__ import annotations

import os
import secrets
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["CAFEX_DATA_DIR"] = tempfile.mkdtemp(prefix="mktcmp_")
os.environ.setdefault("LAUNCH_MODE", "true")
os.environ["AUTOPLAN_SCHEDULER"] = "off"
# No AI or picture provider: the hand-written copy and the upload request are
# what is under test, and nothing here may spend money.
for k in ("OPENAI_API_KEY", "CF_API_TOKEN", "CF_ACCOUNT_ID", "GROQ_API_KEY", "GEMINI_API_KEY",
          "PUTER_AUTH_TOKEN", "HF_TOKEN", "SMTP_HOST"):
    os.environ.pop(k, None)

import pandas as pd  # noqa: E402

PASSED = 0
FAILED = 0


def check(label, cond, extra=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  ✓ {label}")
    else:
        FAILED += 1
        print(f"  ✗ {label}" + (f"  [{extra}]" if extra else ""))


def section(t):
    print(f"\n== {t} ==")


from backend.core import (campaign_image, campaign_writer as cw, discounts, mapper,  # noqa: E402
                          smart, whatsapp)

# =========================================================================
section("1. Mapping asks for phone and email")
raw = pd.DataFrame({
    "Bill Date": ["2026-06-01", "2026-06-02", "2026-06-03"],
    "Mobile": ["98765 43210", "+91 9123456780", "9000011111"],
    "Customer Name": ["Asha K", "Ravi M", "Neha P"],
    "Item Name": ["Chikankari Kurta, White", "Mogra Attar, 6 ml", "Linen Shirt - Blue / XL"],
    "Email ID": ["asha@mail.com", "", "neha@mail.com"],
    "Total Amount": [1499, 549, 999],
})
m = mapper.suggest_mapping(raw)
check("the phone column is found", m.get("customer_phone") == "Mobile", str(m))
check("the email column is found", m.get("customer_email") == "Email ID", str(m))
check("and the phone column still identifies the customer", m.get("customer_id") == "Mobile", str(m))
tx, _ = mapper.build_transactions(raw, m)
check("both contact columns survive into the sales data",
      {"customer_phone", "customer_email", "customer_id"} <= set(tx.columns), str(list(tx.columns)))
check("an empty email is left empty, not stored as ''",
      pd.isna(tx["customer_email"].iloc[1]), repr(tx["customer_email"].iloc[1]))
check("the roles reach the mapping screen", "customer_phone" in mapper.ROLE_KEYWORDS)

no_contacts = raw.drop(columns=["Mobile", "Email ID"]).assign(Cust=["C1", "C2", "C3"])
m2 = mapper.suggest_mapping(no_contacts)
check("a file without them maps fine, they are optional",
      not m2.get("customer_phone") and not m2.get("customer_email") and m2.get("amount"))
tx2, _ = mapper.build_transactions(no_contacts, m2)
check("and builds without contact columns", "customer_phone" not in tx2.columns)

shop = pd.DataFrame({"Name": ["#1001"], "Created at": ["2026-06-01"], "Lineitem name": ["Tee"],
                     "Lineitem quantity": [1], "Lineitem price": [500], "Billing Name": ["A B"],
                     "Email": ["a@b.com"], "Billing Phone": ["+1 415 555 0100"]})
ms = mapper.suggest_mapping(shop)
check("a Shopify export brings its email and phone too",
      ms.get("customer_email") == "Email" and ms.get("customer_phone") == "Billing Phone", str(ms))

# =========================================================================
section("2. The product reads like a product")
names = {"sku10023": "Block Print Kurta"}
cases = {
    "Chikankari Kurta, White": "Chikankari Kurta",
    "Mogra Attar, 6 ml": "Mogra Attar",
    "Linen Shirt - Blue / XL": "Linen Shirt",
    "Co-ord Set": "Co-ord Set",
    "SKU10023": "Block Print Kurta",
    "SKU-99881": "",
    "—": "",
    "nan": "",
}
for raw_name, want in cases.items():
    got = cw.clean_product_name(raw_name, names)
    check(f"{raw_name!r} -> {want!r}", got == want, repr(got))
check("first names only", cw.first_name("Sana D.") == "Sana" and cw.first_name("CUST0007") == "")

# =========================================================================
section("3. Codes are real")
S = "codes@shop.local"
for bad, why in (({"kind": "percent", "value": 95}, "90"), ({"kind": "flat", "value": 0}, "above zero"),
                 ({"kind": "flat", "value": 500, "min_order": 400}, "smaller")):
    try:
        discounts.clean_offer(bad)
        check(f"refuses {bad}", False)
    except discounts.DiscountError as e:
        check(f"refuses {bad}", why in str(e), str(e))
check("labels a flat offer", discounts.offer_label({"kind": "flat", "value": 200, "min_order": 999}, "₹")
      == "₹200 off on orders above ₹999")
check("labels a percent offer", discounts.offer_label({"kind": "percent", "value": 15}, "$") == "15% off")

custs = [{"customer_id": f"C{i}", "customer_name": n} for i, n in enumerate(["Asha K", "Ravi", "", "Asha P"])]
codes = discounts.issue(S, "camp1", custs, {"kind": "flat", "value": 200, "min_order": 999})
allc = [r["code"] for r in codes.values()]
check("one code per customer", len(allc) == 4 and len(set(allc)) == 4, str(allc))
check("named after the customer", codes["C0"]["code"].startswith("ASHA-"), codes["C0"]["code"])
check("and a fallback prefix when there is no name", codes["C2"]["code"].startswith("OFFER-"))
again = discounts.issue(S, "camp1", custs[:1], {"kind": "flat", "value": 200, "min_order": 999})
check("re-issuing the same campaign returns the same code", again["C0"]["code"] == codes["C0"]["code"])

code = codes["C1"]["code"]
try:
    discounts.check(S, code, 500)
    check("below the minimum it is refused", False)
except discounts.DiscountError as e:
    check("below the minimum it is refused", "999" in str(e), str(e))
check("above it, it takes the flat amount", discounts.check(S, code.lower(), 1500)["amount"] == 200)
discounts.redeem(S, code, 1500, "ORD-1", 1349)
try:
    discounts.check(S, code, 1500)
    check("it works exactly once", False)
except discounts.DiscountError as e:
    check("it works exactly once", "already been used" in str(e), str(e))
discounts.release(S, code, "ORD-2")
check("releasing for a different order does nothing", discounts._codes(S)[code]["redeemed_at"])
discounts.release(S, code, "ORD-1")
check("a cancelled order gives the code back", discounts.check(S, code, 1500)["amount"] == 200)

pc = discounts.issue(S, "camp2", [{"customer_id": "X", "customer_name": "Zed"}],
                     {"kind": "percent", "value": 10})["X"]["code"]
check("a percent code takes its share", discounts.check(S, pc, 1234)["amount"] == 123.4)
rows = discounts._codes(S)
rows[pc] = {**rows[pc], "valid_until": "2020-01-01"}
from backend.core import user_store  # noqa: E402
user_store.set_key(S, discounts.KEY, rows)
try:
    discounts.check(S, pc, 1000)
    check("an expired code is refused", False)
except discounts.DiscountError as e:
    check("an expired code is refused", "expired" in str(e), str(e))
try:
    discounts.check(S, "NOPE-12345", 1000)
    check("a made-up code is refused", False)
except discounts.DiscountError as e:
    check("a made-up code is refused", "not valid" in str(e), str(e))
st = discounts.campaign_stats(S, "camp1")
check("campaign stats count what was issued", st["issued"] == 4 and st["redeemed"] == 0, str(st))

# =========================================================================
section("4. A campaign, end to end through the API")
from fastapi.testclient import TestClient  # noqa: E402
from backend.main import app  # noqa: E402

c = TestClient(app)
UQ = secrets.token_hex(3)
SELLER, HANDLE = f"seller{UQ}@shop.local", f"rang{UQ}"
r = c.post("/api/register", json={"email": SELLER, "password": "pw123456"})
check("seller registers", r.status_code == 200, r.text[:200])
H = {"Authorization": "Bearer " + r.json()["token"], "X-Session-Id": "mc-" + UQ}

p = c.post("/api/products/item", headers=H, json={
    "name": "Chikankari Kurta", "category": "Clothing", "price": 1499, "stock": 50, "track_stock": True})
pid = p.json()["products"][0]["id"]
site = c.get("/api/site/state", headers=H).json()["site"]
site.update({"handle": HANDLE, "brand": "Rang Studio", "tagline": "Handmade", "theme": "luxury"})
site["commerce"].update({"shipping_fee": 0, "gst_percent": 0})
site["trust"].update({"business_name": "Rang Studio", "address": "1 MG Road, Pune 411001",
                      "support_email": "hi@rang.in", "support_phone": "9845000000",
                      "grievance_name": "R"})
check("site saves", c.post("/api/site/save", headers=H, json={"site": site}).status_code == 200)
check("site publishes", c.post("/api/site/publish", headers=H, json={"published": True}).status_code == 200)

sample = pd.read_csv(os.path.join(os.path.dirname(__file__), "..", "data", "sample_transactions.csv"),
                     parse_dates=["date"])
ids = sorted(sample["customer_id"].unique())
phone = {cid: f"98{i:08d}" for i, cid in enumerate(ids)}
mail = {cid: (f"buyer{i}@mail.test" if i % 2 else None) for i, cid in enumerate(ids)}
sample["customer_phone"] = sample["customer_id"].map(phone)
sample["customer_email"] = sample["customer_id"].map(mail)
smart.save_sales(SELLER, sample, {"files": "sample"})

r = c.get("/api/campaign/state", headers=H)
check("the screen opens", r.status_code == 200, r.text[:200])
st = r.json()
check("it knows how many customers can be reached",
      st["coverage"]["phone"] == len(ids) and st["coverage"]["email"] > 0, str(st["coverage"]))
check("no draft yet", st["draft"] is None)

r = c.post("/api/campaign/build", headers=H, json={"reason": "winback",
                                                   "offer": {"kind": "percent", "value": 95}})
check("an impossible offer is refused before anything is built", r.status_code == 400, r.text[:200])

r = c.post("/api/campaign/build", headers=H, json={
    "reason": "winback", "offer": {"kind": "flat", "value": 200, "min_order": 2000}})
check("a win-back campaign builds", r.status_code == 200, r.text[:300])
d = r.json()
rows = d["rows"]
check("it has customers in it", len(rows) > 0, str(d.get("counts")))
check("everyone has their own code", len({x["code"] for x in rows}) == len(rows))
check("and the codes exist at checkout",
      all(x["code"] in discounts._codes(SELLER) for x in rows))
segs = {x["segment"] for x in rows}
check("win-back reaches quiet customers only", segs <= {"At Risk", "Hibernating"}, str(segs))
msg = rows[0]["message"]
check("the message carries the customer's code", rows[0]["code"] in msg, msg)
check("and the offer", "₹200 off" in msg, msg)
check("and a link that applies the code", f"/s/{HANDLE}?code={rows[0]['code']}" in msg, msg)
check("and the shop's name", "Rang Studio" in msg, msg)
check("no placeholder is left unfilled", "{" not in msg and "}" not in msg, msg)
check("no café copy anywhere", not any(w in x["message"].lower() for x in rows
                                       for w in ("counter", "machine", "seat warm")))
check("no variant suffix pasted into a sentence",
      not any(", " in (x["product_display"] or "") for x in rows))
check("the product appears clean in the message",
      any(x["product_display"] and x["product_display"] in x["message"] for x in rows))
check("no picture provider means an upload request, not an error",
      d["image"]["needs_upload"] and d["image"]["reason"], str(d["image"]))
check("the copy fell back to the hand-written templates", d["copy"]["source"] == "template")

r = c.post(f"/api/campaign/{d['id']}/update", headers=H, json={"whatsapp": "Hi {name}, no code here"})
check("an edit that drops the code is refused", r.status_code == 400, r.text[:200])
r = c.post(f"/api/campaign/{d['id']}/update", headers=H, json={
    "whatsapp": "Hello {name}! {brand} misses you. {offer} with *{code}* till {expiry}. Loved the {product}?\n\n{link}"})
check("a valid edit is saved and re-fills every message",
      r.status_code == 200 and all(x["message"].startswith("Hello ") for x in r.json()["rows"]), r.text[:200])
drop = rows[0]["customer_id"]
r = c.post(f"/api/campaign/{d['id']}/update", headers=H, json={"remove": [drop]})
check("a customer can be left out", r.status_code == 200 and drop not in {x["customer_id"] for x in r.json()["rows"]})
png = (b"\x89PNG\r\n\x1a\n" + b"0" * 64)
r = c.post(f"/api/campaign/{d['id']}/image/upload", headers=H,
           files={"file": ("pic.png", png, "image/png")})
check("the seller's own picture can be uploaded", r.status_code == 200 and r.json()["image"]["url"], r.text[:200])

# --- the code at checkout
code = d["rows"][1]["code"]
r = c.post(f"/api/shop/{HANDLE}/cart", json={"lines": [{"product_id": pid, "qty": 1}], "coupon": code})
cart = r.json()
check("a code under the minimum is explained, the cart still prices",
      cart["discount"] == 0 and "2,000" in cart["coupon_error"] and cart["total"] == 1499,
      str({k: cart.get(k) for k in ("subtotal", "discount", "coupon_error", "total", "shipping", "tax")}))
r = c.post(f"/api/shop/{HANDLE}/cart", json={"lines": [{"product_id": pid, "qty": 2}], "coupon": code.lower()})
cart = r.json()
check("above it, the discount comes off the total",
      cart["discount"] == 200 and cart["total"] == 2798 and cart["coupon"] == code, str(cart)[:300])
addr = {"name": "Asha", "phone": "9000000001", "line1": "1 First St", "city": "Pune",
        "state": "MH", "pincode": "411001"}
r = c.post(f"/api/shop/{HANDLE}/order", json={"lines": [{"product_id": pid, "qty": 2}], "address": addr,
                                              "guest": True, "name": "Asha", "phone": "9000000001",
                                              "coupon": code})
check("an order with the code is placed at the discounted total",
      r.status_code == 200 and r.json()["order"]["total"] == 2798 and r.json()["order"]["coupon"] == code,
      r.text[:300])
order = r.json()["order"]
r = c.post(f"/api/shop/{HANDLE}/order", json={"lines": [{"product_id": pid, "qty": 2}], "address": addr,
                                              "guest": True, "name": "Asha", "phone": "9000000001",
                                              "coupon": code})
check("the same code cannot be used twice", r.status_code == 400 and "used" in r.text, r.text[:200])
r = c.post(f"/api/shop/{HANDLE}/cart", json={"lines": [{"product_id": pid, "qty": 1}], "coupon": "FAKE-ABCDE"})
check("a made-up code never blocks the cart", r.status_code == 200 and r.json()["total"] == 1499)
stats = discounts.campaign_stats(SELLER, d["id"])
check("the redeemed code is counted for the campaign",
      stats["redeemed"] == 1 and stats["revenue"] == 2798, str(stats))
r = c.post("/api/store/orders/status", headers=H, json={"order_id": order["id"], "status": "cancelled"})
check("cancelling the order", r.status_code == 200, r.text[:200])
check("gives the customer their code back", discounts.check(SELLER, code, 2000)["amount"] == 200)

# --- sending
r = c.post(f"/api/campaign/{d['id']}/send", headers=H, json={"channels": ["whatsapp", "email"]})
check("the campaign sends", r.status_code == 200, r.text[:300])
res = r.json()
n = len(c.get("/api/campaign/state", headers=H).json()["history"][0:1])
check("WhatsApp without a connection becomes tap-to-send links",
      res["wa_links"] > 0 and all(x["wa_link"].startswith("https://wa.me/91") for x in res["results"] if x["wa_link"]),
      str(res)[:300])
check("the tap-to-send message carries the code",
      all(x["code"] in x["message"] for x in res["results"]))
check("with no mail server nothing is claimed as emailed", res["email_sent"] == 0)
check("it is recorded as pending until the seller confirms", res["pending_campaign_id"])
check("and the history shows it", n == 1)
r = c.post(f"/api/campaign/{d['id']}/send", headers=H, json={"channels": ["whatsapp"]})
check("a campaign cannot be sent twice", r.status_code == 400, r.text[:200])

r = c.post("/api/campaign/build", headers=H, json={
    "reason": "winback", "offer": {"kind": "flat", "value": 100}})
check("everyone just contacted is held back by the cooldown",
      r.status_code == 400 or r.json()["held_back"] > 0, r.text[:200])

r = c.post("/api/campaign/build", headers=H, json={
    "reason": "festival", "occasion": "Diwali", "offer": {"kind": "percent", "value": 15}})
check("a festival campaign builds", r.status_code == 200, r.text[:300])
fd = r.json()
fsegs = {x["segment"] for x in fd["rows"]}
check("it reaches the best customers, not only the quiet ones",
      bool(fsegs & {"Champions", "Loyal / Potential"}), str(fsegs))
check("and names the festival", all("Diwali" in x["message"] for x in fd["rows"][:5]), fd["rows"][0]["message"])
check("with a percent offer", "15% off" in fd["rows"][0]["message"])
while True:
    open_draft = c.get("/api/campaign/state", headers=H).json()["draft"]
    if not open_draft:
        break
    r = c.post(f"/api/campaign/{open_draft['id']}/discard", headers=H)
    if r.status_code != 200:
        break
check("drafts can be discarded", r.status_code == 200
      and c.get("/api/campaign/state", headers=H).json()["draft"] is None)
check("and a discarded draft's codes stop existing for nobody: they simply expire unused",
      fd["rows"][0]["code"] in discounts._codes(SELLER))

# =========================================================================
section("5. Pictures: two a month, then ask for one")
E2 = "pics@shop.local"
a = campaign_image.allowance(E2)
check("outside paid Pro Max the allowance is two a month", a["cap"] == 2 and a["left"] == 2, str(a))
try:
    campaign_image.generate(E2, {"sells": "kurtas"})
    check("no OpenAI key means an upload request", False)
except campaign_image.NeedsUpload as e:
    check("no OpenAI key means an upload request", "photo" in str(e), str(e))
user_store.set_key(E2, campaign_image.KEY, {"month": campaign_image._month(), "used": 2})
os.environ["OPENAI_API_KEY"] = "sk-test-not-used"
try:
    campaign_image.generate(E2, {"sells": "kurtas"})
    check("the third picture in a month is refused before any call", False)
except campaign_image.NeedsUpload as e:
    check("the third picture in a month is refused before any call", "2 campaign" in str(e), str(e))
os.environ.pop("OPENAI_API_KEY", None)
check("the prompt shows the offer headline exactly",
      '"₹200 OFF"' in campaign_image.prompt_for({"sells": "kurtas", "offer_short": "₹200 OFF"}))
try:
    campaign_image.save_upload(E2, b"GIF89a", "image/gif")
    check("only real picture types are accepted", False)
except ValueError:
    check("only real picture types are accepted", True)

# =========================================================================
section("6. WhatsApp")
W = "wa@shop.local"
check("off until a number is saved", whatsapp.status(W)["mode"] == "off")
try:
    whatsapp.save_number(W, "12345")
    check("a short number is refused", False)
except whatsapp.WhatsAppError:
    check("a short number is refused", True)
s6 = whatsapp.save_number(W, "98765 43210")
check("a bare Indian mobile gets its country code", s6["number"] == "919876543210", s6["number"])
check("with a number it is tap-to-send", s6["mode"] == "tap")

tp = whatsapp.template_payload("t", "HANDLE")
body = next(x for x in tp["components"] if x["type"] == "BODY")["text"]
import re  # noqa: E402
nums = re.findall(r"\{\{(\d+)\}\}", body)
check("the template uses variables 1-7 in order", nums == [str(i) for i in range(1, 8)], str(nums))
check("and never starts or ends on one (Meta rejects that)",
      not body.lstrip().startswith("{{") and not body.rstrip().endswith("}}"))
check("with a picture header and an opt-out footer",
      tp["components"][0]["format"] == "IMAGE" and tp["components"][-1]["type"] == "FOOTER")
check("and an example for every variable", len(tp["components"][1]["example"]["body_text"][0]) == 7)
check("parameters lose their newlines", whatsapp._param("a\nb\t c") == "a b c")

calls = []


class _Resp:
    def __init__(self, body, code=200):
        self._b, self.status_code = body, code

    def json(self):
        return self._b


def fake_request(method, url, headers=None, timeout=None, **kw):
    calls.append((method, url, kw))
    if url.endswith("/1061") and method == "GET":
        return _Resp({"display_phone_number": "+91 98765 43210", "verified_name": "Rang Studio"})
    if url.endswith("/app"):
        return _Resp({"id": "APP1"})
    if url.endswith("/APP1/uploads"):
        return _Resp({"id": "upload:XYZ"})
    if url.endswith("/upload:XYZ"):
        return _Resp({"h": "HANDLE123"})
    if url.endswith("/message_templates") and method == "GET":
        return _Resp({"data": [{"name": whatsapp.TEMPLATE_NAME, "status": "APPROVED"}]} if len(calls) > 6 else {"data": []})
    if url.endswith("/message_templates") and method == "POST":
        return _Resp({"id": "T1", "status": "PENDING"})
    if url.endswith("/1061/messages"):
        return _Resp({"messages": [{"id": "wamid.1"}]})
    return _Resp({"error": {"message": "unexpected " + url}}, 400)


whatsapp.requests.request = fake_request
s7 = whatsapp.connect(W, "1061", "2072", "EAAtoken")
check("connecting checks the number with Meta", s7["display_number"] == "+91 98765 43210", str(s7))
check("and submits the template with a picture header", s7["template_header"]
      and s7["template_status"] == "PENDING", str(s7))
check("until Meta approves, it is still tap-to-send", s7["mode"] == "waiting" and not whatsapp.live(W))
s8 = whatsapp.refresh(W)
check("once approved, sending is automatic", s8["mode"] == "auto" and whatsapp.live(W), str(s8))
mid = whatsapp.send_campaign_message(W, "9876543210", ["Asha", "Rang", "line\nbreak", "ASHA-XXXXX",
                                                       "₹200 off", "16 Oct", "https://x"], "https://img/p.png")
sent = calls[-1][2]["json"]
check("a message goes out on the approved template", mid == "wamid.1" and sent["template"]["name"] == whatsapp.TEMPLATE_NAME)
check("to the full international number", sent["to"] == "919876543210", sent["to"])
check("with the picture", sent["template"]["components"][0]["parameters"][0]["image"]["link"] == "https://img/p.png")
check("and no newline in any parameter",
      all("\n" not in p_["text"] for p_ in sent["template"]["components"][1]["parameters"]))
check("the token is never shown back", "EAAtoken" not in str(whatsapp.status(W)))
whatsapp.disconnect(W)
check("disconnecting keeps the number for tap-to-send", whatsapp.status(W)["mode"] == "tap")

print(f"\n{PASSED} passed, {FAILED} failed")
sys.exit(1 if FAILED else 0)
