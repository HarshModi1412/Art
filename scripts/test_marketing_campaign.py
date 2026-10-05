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
import io  # noqa: E402
fl = pd.read_csv(io.StringIO("Date,Mobile,Total\n2026-01-01,9876543210,10\n2026-01-02,,20\n"))
txf, _ = mapper.build_transactions(fl, mapper.suggest_mapping(fl))
check("a phone column with blanks (read as decimals) keeps the exact number, no '.0'",
      txf["customer_phone"].iloc[0] == "9876543210", repr(txf["customer_phone"].iloc[0]))

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

# A plain "Name" column, and a "Contact Details" phone column where one
# number is shared by several people (a seller's real test file): 20 people
# must stay 20 customers, not collapse into 5 phone numbers.
shared = pd.DataFrame({
    "Date": pd.date_range("2026-05-01", periods=40, freq="3D"),
    "Name": [f"{fn} {ln}" for fn, ln in zip(["Meera", "Ananya", "Vikram", "Neha", "Priya", "Aarav", "Rohan", "Isha",
                                             "Karan", "Divya"] * 4, ["Joshi", "Rao", "Singh", "K", "Nair", "Shah",
                                                                    "Mehta", "Kapoor", "Patel", "Menon"] * 4)],
    "Product": ["Face Serum", "Cotton Kurta", "Hair Oil", "Silk Scarf"] * 10,
    "Amount": [899, 899, 349, 1199] * 10,
    "Contact Details": [9328363656, 9818675867, 9510959997] * 13 + [9328363656],
})
ms2 = mapper.suggest_mapping(shared)
check("a plain 'Name' column is the customer's name", ms2.get("customer_name") == "Name", str(ms2))
check("the phone column is still the phone", ms2.get("customer_phone") == "Contact Details")
check("one number shared by several names: customers are told apart by name",
      not ms2.get("customer_id") and ms2.get("_id_note"), str(ms2))
txs, _ = mapper.build_transactions(shared, ms2)
check("so ten people stay ten customers", txs["customer_id"].nunique() == 10, str(txs["customer_id"].nunique()))
check("with their names and their phones",
      txs["customer_name"].iloc[0] == "Meera Joshi" and txs["customer_phone"].iloc[0] == "9328363656")
own = shared.assign(**{"Contact Details": [9000000000 + i % 10 for i in range(40)]})
mo = mapper.suggest_mapping(own)
check("one number per person: the phone stays the key (names can repeat)",
      mo.get("customer_id") == "Contact Details" and mo.get("customer_name") == "Name", str(mo))
txo, _ = mapper.build_transactions(own, mo)
check("and a numeric phone key is stored as text, never as a number",
      txo["customer_id"].map(type).eq(str).all() and txo["customer_id"].iloc[0] == "9000000000",
      str(txo["customer_id"].head(2).tolist()))
check("a 'Product name' column is never mistaken for a person",
      mapper.suggest_mapping(pd.DataFrame({"Date": ["2026-01-01"] * 3, "Product name": ["Kurta", "Saree", "Kurta"],
                                           "Amount": [1, 2, 3]})).get("customer_name") is None)

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
check("and a link that applies the code and names the campaign",
      f"/s/{HANDLE}?code={rows[0]['code']}&c={d['id']}" in msg, msg)
check("and the shop's name, in every message", all("Rang Studio" in x["message"] for x in rows), msg)
check("no placeholder is left unfilled", "{" not in msg and "}" not in msg, msg)
check("no café copy anywhere", not any(w in x["message"].lower() for x in rows
                                       for w in ("counter", "machine", "seat warm")))
check("no variant suffix pasted into a sentence",
      not any(", " in (x["product_display"] or "") for x in rows))
check("the product appears clean in the message",
      any(x["product_display"] and x["product_display"] in x["message"] for x in rows))
check("no picture provider means an upload request, not an error",
      d["image"]["needs_upload"] and d["image"]["reason"], str(d["image"]))

# --- not the same message for everyone
voices = [x["voice"] for x in rows]
check("every voice is used before any repeats", len(set(voices)) == min(len(cw.VOICES["winback"]), len(rows)),
      str(sorted(set(voices))))
check("and no two neighbours share one",
      all(voices[i] != voices[i + 1] for i in range(len(voices) - 1)))
firsts = {x["message"].split("\n\n")[1][:40] for x in rows}   # [0] is the founder's header
check("the messages genuinely read differently", len(firsts) >= min(8, len(rows)), str(len(firsts)))
check("subjects vary too", len({x["email_subject"] for x in rows}) >= min(5, len(rows)))
picks = [x for x in rows if x["pick_display"]]
check("customers get a suggestion from the shop's own buying patterns", len(picks) > 0)
from backend.core import campaign_writer as cw2  # noqa: E402
own = sample.groupby("customer_id")["product"].agg(lambda v: {cw2.clean_product_name(p) for p in v}).to_dict()
check("never something they already bought",
      all(x["pick_display"] not in own.get(x["customer_id"], set()) for x in picks))
check("and it appears in their message", all(x["pick_display"] in x["message"] for x in picks))
check("a missing product never leaves a hole in a sentence",
      not any("the  " in x["message"] or " the ." in x["message"] for x in rows))

# --- holdout: proof, not assumption
check("a tenth of the audience is held out to measure the effect",
      len(d["holdout"]) == round((len(rows) + len(d["holdout"])) * 0.1), str(len(d["holdout"])))
held = {h["customer_id"] for h in d["holdout"]}
check("held-out customers get no message and no code",
      not (held & {x["customer_id"] for x in rows})
      and not any(r_["customer_id"] in held for r_ in discounts.campaign_codes(SELLER, d["id"]).values()))

# --- one customer at a time: see it, fix their number, edit their words
row0 = rows[2]
r = c.post(f"/api/campaign/{d['id']}/update", headers=H,
           json={"row": {"customer_id": row0["customer_id"], "phone": "12"}})
check("a bad phone number is refused", r.status_code == 400 and "phone" in r.text.lower(), r.text[:200])
r = c.post(f"/api/campaign/{d['id']}/update", headers=H,
           json={"row": {"customer_id": row0["customer_id"], "phone": "+91 99887 76655",
                         "email": "New@Mail.com"}})
upd = next(x for x in r.json()["rows"] if x["customer_id"] == row0["customer_id"])
check("a phone and email can be added for one customer",
      r.status_code == 200 and upd["phone"] == "+919988776655" and upd["email"] == "new@mail.com",
      str(upd)[:200])
from backend.core import contacts as contacts_mod  # noqa: E402
check("and they are kept for the next campaign",
      contacts_mod.book(SELLER)[row0["customer_id"]]["phone"] == "+919988776655")
r = c.post(f"/api/campaign/{d['id']}/update", headers=H,
           json={"row": {"customer_id": row0["customer_id"], "message": "Hi, no code here"}})
check("an edit that drops the customer's code is refused",
      r.status_code == 400 and row0["code"] in r.text, r.text[:200])
mine = f"Hi there, just for you: {row0['code']} for {{offer}}."
r = c.post(f"/api/campaign/{d['id']}/update", headers=H,
           json={"row": {"customer_id": row0["customer_id"], "message": mine}})
upd = next(x for x in r.json()["rows"] if x["customer_id"] == row0["customer_id"])
others = [x for x in r.json()["rows"] if x["customer_id"] != row0["customer_id"]]
check("one customer's message can be rewritten",
      upd["message"].startswith("Hi there, just for you") and "₹200 off" in upd["message"], upd["message"])
check("without touching anyone else's", all(not x["message"].startswith("Hi there, just") for x in others))
r = c.post(f"/api/campaign/{d['id']}/update", headers=H,
           json={"row": {"customer_id": row0["customer_id"], "reset_message": True}})
upd = next(x for x in r.json()["rows"] if x["customer_id"] == row0["customer_id"])
check("and put back", not upd["message"].startswith("Hi there, just"))
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
check("nothing counts as sent until it is tapped", res["sent_now"] == 0
      and res["to_send"] == res["wa_links"] and "task list" in res["summary"], res["summary"])
check("tapping takes time, so WhatsApp goes to the 25 most valuable customers only",
      res["to_send"] == 25 and res["wa_later"] > 0, str((res["to_send"], res["wa_later"])))
wa_ids = [x["customer_id"] for x in res["results"] if x["wa_link"]]
by_val = {x["customer_id"]: x["monetary"] for x in d["rows"]}
others = [by_val[x["customer_id"]] for x in res["results"] if x["phone"] and not x["wa_link"]]
check("chosen by value: nobody left out spent more than anyone included",
      min(by_val[i] for i in wa_ids) >= max(others), "")
check("and the history shows it", n == 1)

# --- the tracker
code_t = res["results"][0]["code"]
r = c.post(f"/api/shop/{HANDLE}/visit", json={"code": code_t, "c": d["id"]})
c.post(f"/api/shop/{HANDLE}/visit", json={"code": code_t, "c": d["id"]})
c.post(f"/api/shop/{HANDLE}/visit", json={"code": "NOPE-11111"})
check("opening the link is recorded", r.status_code == 200
      and discounts._codes(SELLER)[code_t]["clicks"] == 2 and discounts._codes(SELLER)[code_t]["clicked_at"])
c.post(f"/api/shop/{HANDLE}/cart", json={"lines": [{"product_id": pid, "qty": 2}], "coupon": code_t})
check("using the code at checkout is recorded", discounts._codes(SELLER)[code_t].get("applied_at"))
r = c.post(f"/api/shop/{HANDLE}/order", json={"lines": [{"product_id": pid, "qty": 2}], "address": addr,
                                              "guest": True, "name": "Asha", "phone": "9000000001",
                                              "coupon": code_t})
check("and the order", r.status_code == 200, r.text[:200])
r = c.get(f"/api/campaign/{d['id']}/analysis", headers=H)
check("the analysis opens", r.status_code == 200, r.text[:200])
check("untapped links are not counted as sent", r.json()["kpis"]["reached"] == 0
      and len(r.json()["to_send"]) == r.json()["kpis"]["messaged"], str(r.json()["kpis"]))
tap_ids = [x["customer_id"] for x in res["results"][:3]]
for cid_ in tap_ids:
    rt = c.post(f"/api/campaign/{d['id']}/tapped", headers=H, json={"customer_id": cid_})
c.post(f"/api/campaign/{d['id']}/tapped", headers=H, json={"customer_id": tap_ids[0]})
check("each tap counts one customer as sent, once", rt.status_code == 200 and rt.json()["sent"] == 3,
      rt.text[:200])
r = c.post(f"/api/campaign/{d['id']}/tapped", headers=H, json={"customer_id": "nobody"})
check("a customer outside the campaign is refused", r.status_code == 400)
an = c.get(f"/api/campaign/{d['id']}/analysis", headers=H).json()
k = an["kpis"]
check("the results show exactly how many were sent", k["reached"] == 3 and k["messaged"] == res["to_send"],
      str(k))
check("and who is still waiting, with their link",
      len(an["to_send"]) == k["messaged"] - 3 and all(x["wa_link"] for x in an["to_send"]))
check("the diagnosis says how many are still to send",
      any("still waiting" in x for x in an["diagnosis"]), str(an["diagnosis"]))
hist = c.get("/api/campaign/state", headers=H).json()["history"][0]
check("the history shows the real count", hist["sent_count"] == 3 and hist["total"] == res["to_send"],
      str(hist)[:200])
check("the funnel narrows step by step",
      [f["n"] for f in an["funnel"]] == sorted([f["n"] for f in an["funnel"]], reverse=True), str(an["funnel"]))
check("one click, one code used, one order", k["clicked"] >= 1 and k["applied"] >= 1 and k["orders"] == 1, str(k))
check("with the money it brought", k["revenue"] == 2798 and k["discount"] == 200 and k["per_discount"] == 14.0, str(k))
check("it compares against the held-out group", k["holdout"] == len(d["holdout"]) and k["holdout_rate"] is not None)
check("and the ordering customer is at the top of the list", an["customers"][0]["ordered"])
check("it says what to do next", isinstance(an["diagnosis"], list) and an["diagnosis"], str(an["diagnosis"]))
st2 = c.get("/api/campaign/state", headers=H).json()
check("the history marks it as trackable", st2["history"][0]["tracked"])
check("seven campaign types, each sized from the data",
      [t["id"] for t in st2["types"]] == ["winback", "festival", "second_order", "cross_sell",
                                          "restock", "vip", "thank_you"]
      and all(isinstance(t["audience"], int) for t in st2["types"]), str(st2["types"])[:200])

# --- send mode: one customer at a time, and a task that keeps count
q = c.get(f"/api/campaign/{d['id']}/queue", headers=H).json()
check("send mode lists who is left, most valuable first",
      q["sent"] == 3 and len(q["remaining"]) == 22
      and [by_val[x["customer_id"]] for x in q["remaining"]] == sorted((by_val[x["customer_id"]] for x in q["remaining"]), reverse=True),
      str((q["sent"], len(q["remaining"]))))
check("each with their message ready to read", all(x["code"] in x["message"] for x in q["remaining"]))
tasks = c.get("/api/smart/state", headers=H).json().get("tasks") or smart.get_tasks(SELLER)
wt = next((t for t in smart.get_tasks(SELLER) if t.get("id") == f"wa_{d['id']}"), None)
check("the WhatsApp list is a task, with its progress", wt and wt["kind"] == "wa_send"
      and wt["sent"] == 3 and wt["total"] == 25 and not wt["done"], str(wt))
q = c.post(f"/api/campaign/{d['id']}/skip", headers=H, json={"customer_id": q["remaining"][0]["customer_id"]}).json()
wt = next(t for t in smart.get_tasks(SELLER) if t.get("id") == f"wa_{d['id']}")
check("skipping one leaves it out without counting it as sent", q["skipped"] == 1 and len(q["remaining"]) == 21
      and wt["sent"] == 3 and wt["total"] == 24, str(wt))
for x in q["remaining"]:
    c.post(f"/api/campaign/{d['id']}/tapped", headers=H, json={"customer_id": x["customer_id"]})
wt = next(t for t in smart.get_tasks(SELLER) if t.get("id") == f"wa_{d['id']}")
check("when nobody is left, the task ticks itself off", wt["done"] and wt["sent"] == 24, str(wt))

r = c.get("/api/campaign/nope/analysis", headers=H)
check("an unknown campaign is a 404", r.status_code == 404)
r = c.post(f"/api/campaign/{d['id']}/send", headers=H, json={"channels": ["whatsapp"]})
check("a campaign cannot be sent twice", r.status_code == 400, r.text[:200])

r = c.post("/api/campaign/build", headers=H, json={
    "reason": "winback", "offer": {"kind": "flat", "value": 100}})
check("only the customers actually sent to are held back by the cooldown",
      r.status_code == 200 and r.json()["held_back"] == wt["sent"], r.text[:200])
c.post(f"/api/campaign/{r.json()['id']}/discard", headers=H)

r = c.post("/api/campaign/build", headers=H, json={
    "reason": "festival", "occasion": "Diwali", "offer": {"kind": "percent", "value": 15}})
check("a festival campaign builds", r.status_code == 200, r.text[:300])
fd = r.json()
fsegs = {x["segment"] for x in fd["rows"]}
check("it reaches the best customers, not only the quiet ones",
      bool(fsegs & {"Champions", "Loyal / Potential"}), str(fsegs))
check("and names the festival", all("Diwali" in x["message"] for x in fd["rows"][:5]), fd["rows"][0]["message"])
check("with a percent offer", "15% off" in fd["rows"][0]["message"])
c.post(f"/api/campaign/{fd['id']}/discard", headers=H)

section("4b. Seven kinds of campaign")
from backend.core import campaign_writer as cw3  # noqa: E402
r = c.post("/api/campaign/build", headers=H, json={"reason": "vip", "offer": {"kind": "none"}})
check("a VIP campaign needs to say what the early access is to",
      r.status_code == 400 and "early access" in r.text, r.text[:200])
kinds = {
    "second_order": {"offer": {"kind": "flat", "value": 150}},
    "cross_sell": {"offer": {"kind": "percent", "value": 10}},
    "restock": {"offer": {"kind": "none"}},
    "vip": {"offer": {"kind": "none"}, "note": "our festive collection is live"},
    "thank_you": {"offer": {"kind": "none"}},
}
built = {}
for kind, extra in kinds.items():
    r = c.post("/api/campaign/build", headers=H, json={"reason": kind, **extra})
    ok_ = r.status_code == 200
    check(f"{kind}: builds", ok_, r.text[:200])
    if not ok_:
        continue
    dd = r.json()
    built[kind] = dd
    closes = {cw3.fill(v["close"], {"brand": "Rang Studio"}) for v in cw3.VOICES[kind]}
    wb_closes = {cw3.fill(v["close"], {"brand": "Rang Studio"}) for v in cw3.VOICES["winback"]} - closes
    check(f"{kind}: written in its own voices",
          all(any(cl in x["message"] for cl in closes) for x in dd["rows"])
          and not any(any(cl in x["message"] for cl in wb_closes) for x in dd["rows"])
          and len({x["voice"] for x in dd["rows"]}) == min(len(cw3.VOICES[kind]), len(dd["rows"])),
          dd["rows"][0]["message"])
    c.post(f"/api/campaign/{dd['id']}/discard", headers=H)

if "second_order" in built:
    so = built["second_order"]
    owners = sample.groupby("customer_id")["order_id"].nunique()
    check("second_order: only customers with exactly one order",
          all(owners.get(x["customer_id"], 0) == 1 for x in so["rows"]))
    check("second_order: talks about the next order", all("₹150 off" in x["message"] for x in so["rows"]))
if "cross_sell" in built:
    cs = built["cross_sell"]
    check("cross_sell: every message names the pair",
          all(x["product_display"] and x["pick_display"] and x["pick_display"] in x["message"]
              and x["product_display"] in x["message"] for x in cs["rows"]))
    check("cross_sell: and never suggests what they already have",
          all(x["pick_display"] not in own.get(x["customer_id"], set()) for x in cs["rows"]))
if "restock" in built:
    rs = built["restock"]
    check("restock: names the product that is due, with no discount and no code in sight",
          all(x["product_display"] in x["message"] and x["code"] not in x["message"].split("?")[0]
              and "off" not in x["message"].split("?")[0].lower().replace("office", "")
              for x in rs["rows"]), str([x["message"] for x in rs["rows"] if not (x["product_display"] in x["message"] and x["code"] not in x["message"].split("?")[0] and "off" not in x["message"].split("?")[0].lower().replace("office", ""))][:1]))
    check("restock: the link carries a quiet tracking code (ref=), not code=",
          all(f"ref={x['code']}" in x["message"] and "code=" not in x["message"] for x in rs["rows"]))
    ref = rs["rows"][0]["code"]
    cart = c.post(f"/api/shop/{HANDLE}/cart", json={"lines": [{"product_id": pid, "qty": 1}], "coupon": ref}).json()
    check("restock: the tracking code prices the cart at full price, without an error",
          cart["discount"] == 0 and cart["coupon"] == ref and not cart["coupon_error"]
          and cart["total"] == 1499, str({k_: cart.get(k_) for k_ in ("discount", "coupon", "coupon_error", "total")}))
if "vip" in built:
    check("vip: says what is new, from the seller's note",
          all("festive collection is live" in x["message"] for x in built["vip"]["rows"]))
if "thank_you" in built:
    ty = built["thank_you"]
    check("thank_you: asks for a review or a reply, no discount",
          all(("review" in x["message"].lower() or "reply" in x["message"].lower()) for x in ty["rows"]))

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

section("6b. WhatsApp in one button (Embedded Signup)")
check("off until the admin sets the Meta app up", not whatsapp.embedded_config()["available"])
try:
    whatsapp.complete_embedded(W, "code", "2072", "1061")
    check("refuses while switched off", False)
except whatsapp.WhatsAppError as e:
    check("refuses while switched off", "not switched on" in str(e), str(e))
os.environ.update(WHATSAPP_APP_ID="APP1", WHATSAPP_APP_SECRET="sec", WHATSAPP_CONFIG_ID="CFG1")
check("on once the three settings exist", whatsapp.embedded_config() == {
    "available": True, "app_id": "APP1", "config_id": "CFG1",
    "graph_version": whatsapp.GRAPH.rsplit("/", 1)[-1]})
got = []


def fake_get(url, params=None, timeout=None):
    got.append((url, params))
    return _Resp({"access_token": "BIZTOKEN"} if params.get("code") == "good" else
                 {"error": {"message": "code expired"}})


_Resp.content = b"x"
whatsapp.requests.get = fake_get
calls.clear()
try:
    whatsapp.complete_embedded(W, "stale", "2072", "1061")
    check("an expired code is explained", False)
except whatsapp.WhatsAppError as e:
    check("an expired code is explained", "30 seconds" in str(e), str(e))


def fake_request2(method, url, headers=None, timeout=None, **kw):
    calls.append((method, url, kw))
    if url.endswith("/2072/phone_numbers"):
        return _Resp({"data": [{"id": "1061", "display_phone_number": "+91 98765 43210"}]})
    if url.endswith("/register") or url.endswith("/subscribed_apps") or url.endswith("/smb_app_data"):
        return _Resp({"success": True})
    return fake_request(method, url, headers, timeout, **kw)


whatsapp.requests.request = fake_request2
s9 = whatsapp.complete_embedded(W, "good", "2072", "1061")
urls = [u.split("/v")[-1] for _, u, _ in calls]
check("the code is exchanged with the app secret", got[-1][1]["client_secret"] == "sec")
check("the app is subscribed to the seller's account", any(u.endswith("2072/subscribed_apps") for u in urls))
from backend.core import secrets_store  # noqa: E402
pin = (secrets_store.get_credentials(W, whatsapp.CONNECTOR + "_pin") or {}).get("pin", "")
check("the number is registered with a PIN, kept encrypted",
      any(u.endswith("1061/register") for u in urls) and len(pin) == 6 and pin.isdigit())
check("the template is submitted", s9["template_status"] in ("PENDING", "APPROVED"), str(s9))
check("connected through the popup", s9["connected"] and s9["via"] == "embedded")
calls.clear()
s10 = whatsapp.complete_embedded(W, "good", "2072", "", coexistence=True)
urls = [u for _, u, _ in calls]
check("keeping the WhatsApp Business app: the number id is looked up",
      any(u.endswith("2072/phone_numbers") for u in urls))
check("no re-registration (it would take the number off the app)",
      not any(u.endswith("/register") for u in urls))
check("both syncs Meta requires are requested",
      sum(1 for u in urls if u.endswith("1061/smb_app_data")) == 2)
check("and it says so", s10["coexistence"])
for k_ in ("WHATSAPP_APP_ID", "WHATSAPP_APP_SECRET", "WHATSAPP_CONFIG_ID"):
    os.environ.pop(k_, None)

section("10. Free or paid, the cost slider, batches of ten, delete")
import json as _json  # noqa: E402
from backend.core import campaign_engine as ce10, wa_twilio  # noqa: E402


def _build(reason, **kw):
    r_ = c.post("/api/campaign/build", headers=H, json={"reason": reason, **kw})
    assert r_.status_code == 200, r_.text[:300]
    return r_.json()


# --- free: batches of ten, at most five
b1 = _build("festival", occasion="Holi", offer={"kind": "percent", "value": 10})
r = c.post(f"/api/campaign/{b1['id']}/send", headers=H, json={"channels": ["whatsapp"], "wa_paid": True})
check("paid without Twilio says what to do, and sends nothing", r.status_code == 400 and "Twilio" in r.text
      and ce10.get_draft(SELLER, b1["id"])["state"] != "sent", r.text[:200])
r = c.post(f"/api/campaign/{b1['id']}/send", headers=H,
           json={"channels": ["whatsapp"], "wa_limit": 0, "wa_paid": False, "limit": 23})
res1 = r.json()
check("the slider limits who is in the campaign", r.status_code == 200 and len(res1["results"]) == 23,
      str(len(res1.get("results") or [])))
check("free WhatsApp never asks for more than 50 taps", res1["to_send"] <= ce10.FREE_MAX)
q1 = c.get(f"/api/campaign/{b1['id']}/queue", headers=H).json()
check("the list comes in batches of ten", q1["batch_size"] == 10 and q1["batch"] == 1
      and q1["batches"] == -(-q1["total"] // 10) and q1["batch_total"] == min(10, q1["total"]), str(q1)[:200])
first = [x for x in q1["remaining"] if x["batch"] == 1]
check("batch one is the ten most valuable", len(first) == min(10, q1["total"])
      and all(x["batch"] == 1 for x in q1["remaining"][:len(first)]))
for x in first:
    c.post(f"/api/campaign/{b1['id']}/tapped", headers=H, json={"customer_id": x["customer_id"]})
q1 = c.get(f"/api/campaign/{b1['id']}/queue", headers=H).json()
wt1 = next(t for t in smart.get_tasks(SELLER) if t.get("id") == f"wa_{b1['id']}")
if q1["total"] > 10:
    check("after batch one, batch two is next, and the task says so",
          q1["batch"] == 2 and q1["batch_sent"] == 0 and wt1["batch"] == 2 and wt1["batches"] == q1["batches"]
          and not wt1["done"], str(wt1))
    hist1 = next(h for h in c.get("/api/campaign/state", headers=H).json()["history"] if h.get("campaign_id") == b1["id"])
    check("the campaign is live after one batch", hist1["sent_count"] == 10)
    q1 = c.post(f"/api/campaign/{b1['id']}/finish", headers=H).json()
    wt1 = next(t for t in smart.get_tasks(SELLER) if t.get("id") == f"wa_{b1['id']}")
    check("finish here drops the rest and ticks the task off",
          not q1["remaining"] and q1["sent"] == 10 and wt1["done"], str(wt1))
else:
    check("(audience too small for a second batch)", True)

# --- delete
r = c.post("/api/campaign/delete", headers=H, json={"campaign_id": b1["id"]})
hist = c.get("/api/campaign/state", headers=H).json()["history"]
check("a campaign can be deleted", r.status_code == 200
      and not any(h.get("campaign_id") == b1["id"] for h in hist), r.text[:200])
check("with its results and its task", b1["id"] not in ce10._records(SELLER)
      and not any(t.get("id") == f"wa_{b1['id']}" for t in smart.get_tasks(SELLER)))
check("deleting again is a 404", c.post("/api/campaign/delete", headers=H,
                                        json={"campaign_id": b1["id"]}).status_code == 404)

# --- paid: the seller's own Twilio account
tw_calls, tw_state = [], {"approval": "unsubmitted"}


class _TwResp:
    def __init__(self, body, code=200):
        self._b, self.status_code = body, code
        self.content = b"x"

    def json(self):
        return self._b


def fake_twilio(method, url, auth=None, timeout=None, **kw):
    tw_calls.append((method, url, kw))
    if auth and auth[1] == "wrong-token-wrong-token":
        return _TwResp({"code": 20003, "message": "Authenticate"}, 401)
    if url.endswith(".json") and "/Accounts/" in url and method == "GET":
        return _TwResp({"friendly_name": "Rang Studio", "type": "Full"})
    if url.endswith("/Content") and method == "GET":
        return _TwResp({"contents": []})
    if url.endswith("/Content") and method == "POST":
        return _TwResp({"sid": "HXoffer" if "offer" in kw["json"]["friendly_name"] else "HXupdate"})
    if url.endswith("/ApprovalRequests") and method == "GET":
        return _TwResp({"whatsapp": {"status": tw_state["approval"]}})
    if url.endswith("/ApprovalRequests/whatsapp"):
        tw_state["approval"] = "pending"
        return _TwResp({})
    if url.endswith("/Messages.json"):
        return _TwResp({"sid": "SM" + secrets.token_hex(8)}, 201)
    return _TwResp({"message": "unexpected " + url}, 404)


wa_twilio.requests.request = fake_twilio
SID = "AC" + "a" * 32
r = c.post("/api/whatsapp/twilio", headers=H, json={"account_sid": "nope", "auth_token": "x" * 32,
                                                    "from_number": "+1 555 010 0000"})
check("a wrong Account SID is caught before calling Twilio", r.status_code == 400 and "AC" in r.text)
r = c.post("/api/whatsapp/twilio", headers=H, json={"account_sid": SID, "auth_token": "wrong-token-wrong-token",
                                                    "from_number": "+1 555 010 0000"})
check("Twilio refusing the token is said plainly", r.status_code == 400 and "Auth Token" in r.text, r.text[:200])
r = c.post("/api/whatsapp/twilio", headers=H, json={"account_sid": SID, "auth_token": "t" * 32,
                                                    "from_number": "+1 555 010 0000"})
w10 = r.json()
check("Twilio connects and both templates go to WhatsApp for approval",
      r.status_code == 200 and w10["twilio"]["connected"] and w10["twilio"]["offer_status"] == "pending"
      and w10["twilio"]["update_status"] == "pending", r.text[:300])
check("connecting makes paid the default, but not ready until approved",
      w10["send_pref"] == "paid" and not w10["paid_ready"])
check("the token is kept encrypted, never in the plain config",
      "t" * 32 not in _json.dumps(whatsapp._cfg(SELLER)))
b2 = _build("festival", occasion="Navratri", offer={"kind": "percent", "value": 10})
r = c.post(f"/api/campaign/{b2['id']}/send", headers=H, json={"channels": ["whatsapp"], "wa_paid": True})
check("while WhatsApp reviews the templates, paid is refused", r.status_code == 400)
tw_state["approval"] = "approved"
w10 = c.post("/api/whatsapp/twilio/refresh", headers=H).json()
check("once approved, paid is ready through Twilio", w10["paid_ready"] and w10["paid_via"] == "twilio", str(w10)[:200])
check("with a price per message for the cost estimate", w10["twilio"]["price_each"]["amount"] > 0)
tw_calls.clear()
r = c.post(f"/api/campaign/{b2['id']}/send", headers=H,
           json={"channels": ["whatsapp"], "wa_paid": True, "wa_limit": 0, "limit": 6})
res2 = r.json()
msgs = [kw["data"] for m_, u_, kw in tw_calls if u_.endswith("/Messages.json")]
with_phone = sum(1 for x in res2["results"] if x["phone"])
check("paid sends every message by itself, nothing to tap",
      r.status_code == 200 and res2["whatsapp_sent"] == with_phone == len(msgs) and res2["to_send"] == 0
      and res2["whatsapp_via"] == "twilio", str({k_: res2.get(k_) for k_ in ("whatsapp_sent", "to_send", "whatsapp_via", "wa_later")}) + str(len(msgs)) + str(with_phone) + str([x["error"] for x in res2["results"]]))
check("through the approved template, with each customer's own code",
      all(m_["ContentSid"] == "HXoffer" and m_["From"] == "whatsapp:+15550100000" for m_ in msgs)
      and {_json.loads(m_["ContentVariables"])["4"] for m_ in msgs}
      == {x["code"] for x in res2["results"] if x["whatsapp_sent"]}, str(msgs[:1])[:300])
check("the slider limit holds for paid too", len(res2["results"]) == 6)
check("no WhatsApp task for a paid campaign", not any(t.get("id") == f"wa_{b2['id']}" for t in smart.get_tasks(SELLER)))
r = c.post("/api/whatsapp/pref", headers=H, json={"pref": "free"})
check("the seller can switch the default back to free", r.json()["send_pref"] == "free")
r = c.post("/api/whatsapp/twilio", headers=H, json={"account_sid": SID, "auth_token": "t" * 32,
                                                    "from_number": "+1 415 523 8886"})
check("the Twilio Sandbox is ready at once (no templates)",
      r.json()["twilio"]["sandbox"] and r.json()["paid_ready"], r.text[:200])
tw_calls.clear()
wa_twilio.send(SELLER, "+91 98765 43210", ["a"], text="Hi Asha, your code is X1")
check("and sends the full personal message as text",
      tw_calls[-1][2]["data"].get("Body") == "Hi Asha, your code is X1" and "ContentSid" not in tw_calls[-1][2]["data"])
r = c.post("/api/whatsapp/twilio/disconnect", headers=H).json()
check("disconnecting Twilio goes back to free", not r["twilio"]["connected"] and r["send_pref"] == "free")

section("11. Founder's voice, picks from real behaviour, no-website chat link, download")
import io as _io  # noqa: E402
import re as _re  # noqa: E402
from backend.core import analytics as an11, campaign_engine as ce11, chatlink, founder_voices as fv  # noqa: E402

# --- fifty voices, every one complete
check("fifty founder-voice messages", sum(len(v) for v in fv.VOICES.values()) == 50)
full = {"name": "Asha", "product": "Linen Shirt", "pick": "Silk Scarf", "offer": "Rs 200 off",
        "code": "ASHA-1234", "expiry": "16 Oct", "link": "https://x.test/s/a", "brand": "Rang Studio",
        "occasion": "Diwali", "orders": "4", "chatlink": "https://x.test/w/t/ASHA-1234"}
leftover = [(k, f) for k, vs in fv.VOICES.items() for v in vs for f, t in v.items()
            if _re.search(r"\{[a-z]+\}", cw.fill(t, full))]
check("no voice leaves a {variable} unfilled", not leftover, str(leftover[:3]))
check("every voice has an offer line and a no-discount line",
      all(v.get("offer") and v.get("none") and v.get("open") and v.get("close") for vs in fv.VOICES.values() for v in vs))
check("offer lines always carry the code and the date",
      all("{code}" in v["offer"] and "{expiry}" in v["offer"] for vs in fv.VOICES.values() for v in vs))

# --- picks: people who bought the same, else the most-bought they don't own
t11 = pd.DataFrame([
    ("A", "Linen Shirt"), ("B", "Linen Shirt"), ("B", "Silk Scarf"), ("C", "Linen Shirt"), ("C", "Silk Scarf"),
    ("F", "Linen Shirt"), ("F", "Silk Scarf"), ("D", "Cotton Kurta"), ("E", "Cotton Kurta"),
    ("G", "Rare Vase"), ("K", "Brass Lamp"), ("K", "Linen Shirt"),
], columns=["customer_id", "product"])
t11["amount"] = 100
_rules = an11.association_rules
an11.association_rules = lambda *a, **k: {"rules": {}}     # co-buyers and best sellers only
prof = [{"customer_id": "A", "favorite_item": "Linen Shirt", "product_display": "Linen Shirt"},
        {"customer_id": "G", "favorite_item": "Rare Vase", "product_display": "Rare Vase"},
        {"customer_id": "K", "favorite_item": "Brass Lamp", "product_display": "Brass Lamp"}]
ce11._add_picks(t11, prof, {})
an11.association_rules = _rules
pa, pg, pk = prof
check("bought the Linen Shirt: suggested what other Linen Shirt buyers also bought",
      pa["pick_display"] == "Silk Scarf" and pa["pick_kind"] == "pair" and pa["pick_from"] == "Linen Shirt", str(pa))
check("nobody shares their purchase: the shop's most-bought product",
      pg["pick_display"] == "Linen Shirt" and pg["pick_kind"] == "best", str(pg))
check("already owns the most-bought one: the second most-bought",
      pk["pick_display"] == "Silk Scarf" and pk["pick_kind"] == "best", str(pk))

ctx11 = {"reason": "winback", "brand": "Rang Studio", "offer": {"kind": "flat", "value": 200},
         "offer_label": "Rs 200 off", "expiry_label": "16 Oct", "link": "https://x.test/s/rang",
         "campaign_id": "c1", "founder": ""}
row11 = {"customer_name": "Asha K", "product_display": "Linen Shirt", "pick_display": "Silk Scarf",
         "pick_kind": "pair", "pick_from": "Linen Shirt", "code": "ASHA-1234", "voice": 0, "frequency": 1}
m = cw.message_for(row11, ctx11)["message"]
check("signed by the founder, at the top", m.startswith("_A personal note from the founder of Rang Studio_"), m[:80])
check("names their product and says the suggestion comes from people who bought it",
      "Linen Shirt" in m and "Silk Scarf" in m and "bought the Linen Shirt" in m, m)
m = cw.message_for(row11, {**ctx11, "founder": "Harsh"})["message"]
check("with the founder's name when given", m.startswith("_A personal note from Harsh, founder of Rang Studio_")
      and m.rstrip().endswith("Harsh, Rang Studio"), m[-60:])
m = cw.message_for({**row11, "frequency": 7}, ctx11)["message"]
check("a regular hears how many times they ordered, and still their product", "7 times" in m and "Linen Shirt" in m, m)
m = cw.message_for({**row11, "pick_kind": "best", "pick_from": ""}, ctx11)["message"]
check("a best-seller suggestion is worded as one, never as 'people who bought'",
      "Silk Scarf" in m and "bought the Linen Shirt" not in m, m)
lens = [len(cw.message_for({**row11, "voice": i, "frequency": 5}, ctx11)["message"]) for i in range(12)]
check("short enough for a phone screen", max(lens) < 700, str(max(lens)))

# --- no website: reply with the code, and a tracked chat link
nos = {**ctx11, "link": "", "chat_prefix": "https://x.test/w/tok/"}
m = cw.message_for(row11, nos)
check("no website: asks them to reply with their code on WhatsApp",
      "*ASHA-1234*" in m["message"] and "reply" in m["message"].lower(), m["message"])
check("with a chat link that carries the code", "https://x.test/w/tok/ASHA-1234" in m["message"]
      and m["shop_link"] == "https://x.test/w/tok/ASHA-1234")
check("and no shop link that would go nowhere", "/s/" not in m["message"])
whatsapp.save_number(SELLER, "+91 98765 00000")
tok = chatlink.token(SELLER)
check("the shop token never shows the seller's email", SELLER.split("@")[0] not in tok and chatlink.seller_for(tok) == SELLER)
code11 = next(iter(discounts._codes(SELLER)))
before = int(discounts._codes(SELLER)[code11].get("clicks") or 0)
r = c.get(f"/w/{tok}/{code11}", follow_redirects=False)
check("the chat link opens WhatsApp with the shop, code typed",
      r.status_code == 302 and r.headers["location"].startswith("https://wa.me/919876500000?text=")
      and code11 in r.headers["location"], r.headers.get("location", "")[:120])
check("and counts as the customer opening the link",
      int(discounts._codes(SELLER)[code11].get("clicks") or 0) == before + 1)
check("a made-up shop token is a 404", c.get("/w/nope/X", follow_redirects=False).status_code == 404)
check("contact_ctx offers the chat link only without a website",
      ce11.contact_ctx(SELLER)["chat_prefix"] == "" if ce11.store_link(SELLER) else ce11.contact_ctx(SELLER)["chat_prefix"])

# --- founder name, saved from the draft, and the download
b11 = c.post("/api/campaign/build", headers=H, json={"reason": "festival", "occasion": "Lohri",
                                                      "offer": {"kind": "flat", "value": 100}}).json()
r = c.post(f"/api/campaign/{b11['id']}/update", headers=H, json={"founder": "Harsh"})
check("the seller signs with their name, and every message updates",
      r.status_code == 200 and r.json()["founder"] == "Harsh"
      and all(x["message"].startswith("_A personal note from Harsh") for x in r.json()["rows"]), r.text[:200])
r = c.get(f"/api/campaign/{b11['id']}/download", headers=H)
check("the campaign downloads as Excel", r.status_code == 200 and "spreadsheet" in r.headers["content-type"])
xl = pd.read_excel(_io.BytesIO(r.content))
check("with every customer's phone, code and exact message",
      len(xl) == len(b11["rows"]) and {"Customer", "Phone", "Email", "Code", "Message", "WhatsApp link", "Status"} <= set(xl.columns)
      and (xl["Code"].astype(str) == pd.Series([x["code"] for x in b11["rows"]])).all(), str(list(xl.columns)))
check("an unknown campaign is a 404", c.get("/api/campaign/nope/download", headers=H).status_code == 404)
c.post(f"/api/campaign/{b11['id']}/discard", headers=H)

print(f"\n{PASSED} passed, {FAILED} failed")
sys.exit(1 if FAILED else 0)
