"""The first-run journey and UPI checkout, end to end.

Runs against a throwaway data directory, so it never touches real accounts:

    python scripts/test_onboarding.py      (prints "N passed, M failed")

Design: docs/designs/first-run-journey.md. What is checked is what the design
promises: a step is done only when the real data says so (and stops being done
when the data goes); every skip is exactly one task, which ticks itself when
the step is done; parts put the next part on the task list; the paths can be
switched; and a UPI order is "to check" until the seller says the money came.
"""
import os
import re
import secrets
import sys
import tempfile

TMP = tempfile.mkdtemp(prefix="cafex_ob_")
os.environ["CAFEX_DATA_DIR"] = TMP
os.environ.setdefault("LAUNCH_MODE", "true")
os.environ.setdefault("AUTOPLAN_SCHEDULER", "off")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from backend import main  # noqa: E402
from backend.core import onboarding, smart, store_payments, user_store  # noqa: E402

c = TestClient(main.app)
passed = failed = 0
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name}  <-- {detail}")


def signup(tag):
    em = f"{tag}-{secrets.token_hex(3)}@test.co"
    r = c.post("/api/register", json={"email": em, "password": "pw123456!", "plan": "free"})
    assert r.status_code == 200, r.text
    return em, {"Authorization": "Bearer " + r.json()["token"], "X-Session-Id": "ob-" + em}


def act(H, action, **kw):
    return c.post("/api/onboarding", headers=H, json={"action": action, **kw})


def save(H, what, body=None):
    return c.post(f"/api/onboarding/save/{what}", headers=H, json=body or {})


def step(j, sid):
    for p in j["parts"]:
        for s in p["steps"]:
            if s["id"] == sid:
                return s
    return None


def open_tasks(H):
    return [t for t in c.get("/api/smart/state", headers=H).json()["tasks"] if not t.get("done")]


print("\n== a new account gets the journey, an old one does not ==")
em, H = signup("new")
j = c.get("/api/onboarding", headers=H).json()
check("sign-up creates the record", j["has_record"])
check("it is a new account (the welcome opens itself)", j["new_account"])
check("no path until the seller answers", j["path"] is None and not j["active"])
state = c.get("/api/smart/state", headers=H).json()
check("the home payload carries the journey", "onboarding" in state and state["onboarding"]["has_record"])
legacy = "legacy-" + secrets.token_hex(3) + "@test.co"
check("an account with no record is not new", onboarding.progress(legacy)["new_account"] is False)
check("and not active", onboarding.progress(legacy)["active"] is False)
check("starting creates a record that is not 'new'",
      onboarding.act(legacy, "start")["new_account"] is False and onboarding.get_record(legacy))
j = act(H, "welcomed").json()
check("welcomed once, never pops up again", j["new_account"] is False)
check("an unknown action is refused", act(H, "explode").status_code == 400)

print("\n== the create path: done only when the data says so ==")
j = act(H, "choose_path", path="create").json()
check("create path has 4 steps in Part 1", [s["id"] for s in j["parts"][0]["steps"]]
      == ["shop", "products", "site", "payment"])
check("the next step is naming the shop", j["next"] == {"part": 1, "step": "shop"})
check("a default product type does not count as chosen", step(j, "shop")["done"] is False)
r = save(H, "shop", {"name": "A", "product_type": "clothes"})
check("a one-letter name is refused in plain words", r.status_code == 400 and "name" in r.json()["detail"])
j = save(H, "shop", {"name": "Priya Kurtis", "product_type": "clothes"}).json()
check("shop is done once named and typed", step(j, "shop")["done"])
check("the name lands on the site brand", j["facts"]["shop_name"] == "Priya Kurtis")
pids = []
for i, (n, pr) in enumerate([("Kurta", 799), ("Dupatta", 549)]):
    pids.append(c.post("/api/products/item", headers=H, json={
        "name": n, "price": pr, "listed": True, "track_stock": False}).json()["products"][-1]["id"])
j = act(H, "sync").json()
check("2 products is not 3", step(j, "products")["done"] is False)
c.post("/api/products/item", headers=H, json={"name": "Co-ord set", "price": 1899, "listed": True, "track_stock": False})
j = act(H, "sync").json()
check("3 products is done", step(j, "products")["done"])
prods = c.get("/api/products/state", headers=H).json()["products"]
c.post("/api/products/item/delete", headers=H, json={"id": prods[0]["id"]})
j = act(H, "sync").json()
check("deleting one makes it not done again (live, not frozen)", step(j, "products")["done"] is False)
c.post("/api/products/item", headers=H, json={"name": prods[0]["name"], "price": 700, "listed": True, "track_stock": False})

print("\n== skip: one task per step, and it ticks itself ==")
j = act(H, "skip", step="site").json()
check("skip records the step", step(j, "site")["skipped"])
tasks = [t for t in j["tasks"] if t.get("ob") == "step:site"]
check("skip makes exactly one task", len(tasks) == 1, tasks)
check("the task is in the seller's words", tasks and "online" in tasks[0]["text"].lower())
j = act(H, "skip", step="site").json()
check("skipping again reuses the open task",
      len([t for t in j["tasks"] if t.get("ob") == "step:site"]) == 1)
check("a skipped step is not done", step(j, "site")["done"] is False)
check("the journey moves past it", j["next"]["step"] == "payment")

print("\n== the website: address, WhatsApp, the law's details, delivery, publish ==")
check("publish is refused while the legal details are missing",
      save(H, "publish").status_code == 400)
r = save(H, "site", {"handle": "ab"})
check("a 2-letter address is refused", r.status_code == 400)
other, H2 = signup("other")
save(H2, "shop", {"name": "Taken Shop", "product_type": "generic"})
save(H2, "site", {"handle": f"taken-{em[:6]}"})
r = save(H, "site", {"handle": f"taken-{em[:6]}"})
check("an address another shop has is refused", r.status_code == 400 and "taken" in r.json()["detail"].lower())
check("a 9-digit WhatsApp is refused", save(H, "site", {"whatsapp": "98765 4321"}).status_code == 400)
check("a +91 number is accepted", save(H, "site", {"whatsapp": "+91 98765 43210"}).status_code == 200)
check("a missing address is refused", save(H, "site", {"legal_name": "Priya Sharma", "address": "x"}).status_code == 400)
j = save(H, "site", {"theme": "fashion", "handle": f"priya-{secrets.token_hex(2)}",
                     "legal_name": "Priya Sharma", "address": "12 MG Road, Jaipur 302001",
                     "delivery_fee": 40}).json()
site = main.sitebuilder.get_site(em)
check("the look is saved", site["theme"] == "fashion")
check("WhatsApp saved as +91", site["contact"]["whatsapp"] == "+919876543210")
check("the law's details are filled", not main.sitebuilder.legal_gaps(site), main.sitebuilder.legal_gaps(site))
check("a per-order fee means every order pays it",
      site["commerce"]["shipping_fee"] == 40 and site["commerce"]["free_shipping_above"] == 0)
check("an unknown look is refused", save(H, "site", {"theme": "nope"}).status_code == 400)
j = save(H, "publish").json()
check("publish works once the details are there", step(j, "site")["done"] and j["facts"]["published"])
check("the site's skip task ticked itself",
      not [t for t in open_tasks(H) if t.get("ob") == "step:site"])

print("\n== payment: the seller's own UPI ID ==")
for raw, want in [("priya@okaxis", "priya@okaxis"), (" Priya.S@OkHDFCbank ", "Priya.S@okhdfcbank"),
                  ("priya", ""), ("@okaxis", ""), ("pri ya@ok", "priya@ok"), ("a@1bank", "")]:
    check(f"clean_upi({raw!r})", store_payments.clean_upi(raw) == want, store_payments.clean_upi(raw))
r = save(H, "payment", {"upi_id": "not an id"})
check("a bad UPI ID is refused with an example", r.status_code == 400 and "name@okaxis" in r.json()["detail"])
j = save(H, "payment", {"upi_id": "priya@okaxis"}).json()
check("payment is done", step(j, "payment")["done"])
c_ = main.sitebuilder.get_site(em)["commerce"]
check("UPI is switched on and COD left alone", c_["upi_enabled"] and c_["cod_enabled"])
check("Part 1 is finished", j["parts"][0]["finished"])
check("its finish screen is waiting", 1 in j["unseen_done"])
check("Part 2 went on the task list",
      len([t for t in j["tasks"] if t.get("ob") == "part:2" and not t.get("done")]) == 1)
j = act(H, "seen_part_done", part=1).json()
check("once seen, the finish screen does not repeat", 1 not in j["unseen_done"])
check("Parts 2 and 3 are both open now", j["parts"][1]["unlocked"] and j["parts"][2]["unlocked"])

print("\n== UPI works only in rupees ==")
usd, HU = signup("usd")
s_ = main.sitebuilder.get_site(usd); s_["commerce"]["currency"] = "USD"; main.sitebuilder.save_site(usd, s_)
check("a dollar shop is told UPI needs rupees",
      "rupees" in save(HU, "payment", {"upi_id": "asha@okaxis"}).json().get("detail", ""))
check("and can switch to rupees on the spot",
      save(HU, "payment", {"upi_id": "asha@okaxis", "rupees": True}).status_code == 200
      and main.sitebuilder.get_site(usd)["commerce"]["currency"] == "INR")
s_ = main.sitebuilder.get_site(usd); s_["commerce"]["currency"] = "USD"; main.sitebuilder.save_site(usd, s_)
check("UPI is never offered in dollars", store_payments.upi_ready(main.sitebuilder.get_site(usd)["commerce"]) is False)

print("\n== a shopper pays by UPI; the seller checks ==")
h = main.sitebuilder.get_site(em)["handle"]
prod = [p for p in c.get("/api/products/state", headers=H).json()["products"] if p["name"] == "Kurta"][0]
cart = c.post(f"/api/shop/{h}/cart", json={"lines": [{"product_id": prod["id"], "qty": 1}]}).json()
check("the cart offers UPI", cart["upi_enabled"] and cart["upi_id"] == "priya@okaxis")
check("nothing is collected online by us", cart["due"]["upi"]["online"] == 0)
order_body = {"lines": [{"product_id": prod["id"], "qty": 1}], "payment": "upi", "guest": True,
              "name": "Asha", "phone": "9876500000",
              "address": {"name": "Asha", "phone": "9876500000", "line1": "1 Street", "city": "Jaipur", "pincode": "302001"}}
o = c.post(f"/api/shop/{h}/order", json=order_body).json()["order"]
check("the order is placed at once", o["payment"] == "upi")
check("and waits for the seller's check", o["payment_status"] == "to_check")
check("the amount due is the total", o["upi_due"] == o["total"])
check("a shopper cannot confirm it (no seller token)",
      c.post("/api/orders/upi", json={"order_id": o["id"], "received": True}).status_code in (401, 403))
r = c.post("/api/orders/upi", headers=H, json={"order_id": o["id"], "received": True}).json()
check("'Money received' marks it paid", r["order"]["payment_status"] == "paid")
check("a second answer is refused",
      c.post("/api/orders/upi", headers=H, json={"order_id": o["id"], "received": False}).status_code == 400)
o2 = c.post(f"/api/shop/{h}/order", json=order_body).json()["order"]
r = c.post("/api/orders/upi", headers=H, json={"order_id": o2["id"], "received": False}).json()
check("'Not received' cancels the order", r["order"]["status"] == "cancelled")
check("with a reason", r["order"].get("cancel_reason") == "Payment not received")
cod = c.post(f"/api/shop/{h}/order", json={**order_body, "payment": "cod"}).json()["order"]
check("a COD order cannot be answered as UPI",
      c.post("/api/orders/upi", headers=H, json={"order_id": cod["id"], "received": True}).status_code == 400)
s_ = main.sitebuilder.get_site(em); s_["commerce"]["upi_enabled"] = False; main.sitebuilder.save_site(em, s_)
check("with UPI off, a UPI order is refused",
      c.post(f"/api/shop/{h}/order", json=order_body).status_code == 400)
s_ = main.sitebuilder.get_site(em); s_["commerce"]["upi_enabled"] = True; main.sitebuilder.save_site(em, s_)
s_ = main.sitebuilder.get_site(em); s_["commerce"]["upi_id"] = "garbage"; s_["commerce"]["upi_enabled"] = True
main.sitebuilder.save_site(em, s_)
check("a switch with no valid ID behind it goes off",
      main.sitebuilder.get_site(em)["commerce"]["upi_enabled"] is False)
save(H, "payment", {"upi_id": "priya@okaxis"})

print("\n== Part 2 and Part 3 ==")
j = act(H, "open_part", part=2).json()
check("opening Part 2 is recorded", j["parts"][1]["opened"])
c.post("/api/studio/brand", headers=H, json={"patch": {"about": "Hand-block printed kurtas."}})
j = act(H, "sync").json()
check("brand is done from Studio's own data", step(j, "brand")["done"])
check("photos are not done with no product photos", step(j, "photos")["done"] is False)
for p in c.get("/api/products/state", headers=H).json()["products"][:3]:
    save(H, "photo", {"product_id": p["id"], "url": f"/generated_images/{p['id']}.jpg"})
j = act(H, "sync").json()
check("3 products with a photo is done", step(j, "photos")["done"])
check("a photo for a missing product is refused",
      save(H, "photo", {"product_id": "nope", "url": "/x.jpg"}).status_code == 400)
for sid in ("style", "instagram"):
    j = act(H, "skip", step=sid).json()
check("Part 2 finishes by skipping the rest", j["parts"][1]["finished"])
check("Part 2's task ticked itself",
      not [t for t in open_tasks(H) if t.get("ob") == "part:2"])
check("Part 3 went on the task list",
      len([t for t in open_tasks(H) if t.get("ob") == "part:3"]) == 1)
r = save(H, "stock", {"supplier": {"name": "S", "days": 7}, "counts": {}})
check("a one-letter supplier is refused", r.status_code == 400)
r = save(H, "stock", {"supplier": {"name": "Sharma Textiles", "days": 0}, "counts": {}})
check("0 delivery days is refused", r.status_code == 400)
counts = {p["id"]: 10 + i for i, p in enumerate(c.get("/api/products/state", headers=H).json()["products"])}
j = save(H, "stock", {"supplier": {"name": "Sharma Textiles", "phone": "9812345678", "days": 7},
                      "counts": counts}).json()
check("suppliers is done", step(j, "suppliers")["done"])
check("stock is done", step(j, "stock")["done"])
sup = c.get("/api/supply/suppliers", headers=H).json()["suppliers"]
check("Supply lists the supplier with its delivery days",
      sup and sup[0]["name"] == "Sharma Textiles" and sup[0]["lead_time_days"] == 7)
maps = main.supply.get_maps(em)
check("each product is linked to its stock item (reorder can see sales)", len(maps) >= 3, maps)
pr = c.get("/api/products/state", headers=H).json()["products"]
check("stock counts land on the products, now tracked",
      all(p["track_stock"] is not False for p in pr) and sorted(p["stock"] for p in pr)[0] >= 10)
check("the whole journey is finished", j["finished"])
check("skipped steps are still listed", sorted(j["skipped_left"]) == ["instagram", "style"])

print("\n== a task the seller deleted is their choice ==")
tid = [t for t in open_tasks(H) if t.get("ob") == "step:style"][0]["id"]
c.post("/api/smart/tasks", headers=H, json={"action": "delete", "task_id": tid})
j = act(H, "sync").json()
check("sync does not bring it back", not [t for t in j["tasks"] if t.get("ob") == "step:style"])
check("and the step still shows as not done", step(j, "style")["done"] is False and "style" in j["skipped_left"])

print("\n== the connect path, and switching ==")
cn, HC = signup("conn")
j = act(HC, "choose_path", path="connect").json()
check("connect path has 2 steps in Part 1", [s["id"] for s in j["parts"][0]["steps"]] == ["connect", "catalogue"])
j = act(HC, "skip", step="connect").json()
check("the connect skip is a task", [t for t in j["tasks"] if t.get("ob") == "step:connect"])
j = act(HC, "choose_path", path="create").json()
check("switching to create removes the connect task",
      not [t for t in j["tasks"] if t.get("ob") == "step:connect" and not t.get("done")])
check("and the connect skip", "connect" not in (onboarding.get_record(cn) or {}).get("skipped", {}))
check("the create steps take over", j["next"]["step"] == "shop")
user_store.set_key(cn, "smart_data", {"sales": {"rows": 3}})
j = act(HC, "choose_path", path="connect").json()
check("a sales file counts as connected", step(j, "connect")["done"])
check("importing with no names in sales makes nothing", save(HC, "import").status_code == 200)

print("\n== language, dismiss, and the home ETag ==")
j = act(H, "set_lang", lang="hi").json()
check("Hindi is saved", j["lang"] == "hi")
check("an unknown language is refused", act(H, "set_lang", lang="fr").status_code == 400)
j = act(H, "skip", step="payment").json()
check("skipping a done step makes no task",
      not [t for t in j["tasks"] if t.get("ob") == "step:payment"] and "payment" not in j["skipped_left"])
act(HC, "set_lang", lang="hi")
j = act(HC, "skip", step="catalogue").json()
check("a task made in Hindi is in Hindi",
      any(t.get("ob") == "step:catalogue" and re.search(r"[ऀ-ॿ]", t["text"]) for t in j["tasks"]))
j = act(H, "dismiss").json()
check("dismiss hides it", j["dismissed"] and not j["active"])
j = act(H, "undismiss").json()
check("undismiss brings it back", not j["dismissed"])
fp1 = main._home_fingerprint(em)
act(H, "dismiss")
check("dismissing changes the home fingerprint", main._home_fingerprint(em) != fp1)

print("\n== the page loads it, in both languages ==")
html = open(os.path.join(ROOT, "Smart CafeX", "smart.html"), encoding="utf-8").read()
check("journey.js loads before smart.js",
      html.index("journey.js") < html.index("smart.js?"))
check("journey.css is linked", "journey.css" in html)
js = open(os.path.join(ROOT, "Smart CafeX", "journey.js"), encoding="utf-8").read()
hi_block = js.split("hi: {")[1].split("\n  },\n};")[0]
en_keys = set(re.findall(r'(\w+): "', js.split("en: {")[1].split("hi: {")[0]))
hi_keys = set(re.findall(r'(\w+): "', hi_block))
check("every English string has a Hindi one", not (en_keys - hi_keys), sorted(en_keys - hi_keys))
check("no em dash in the journey's words", "—" not in js.split("/* ---------------------------------------------------------- state")[0])
for sid in onboarding.STEP_IDS:
    check(f"step {sid} has a screen and a task text",
          f"{sid}:" in js.split("const STEP_SCREEN")[1].split("};")[0] and sid in onboarding.TASK_TEXT["en"])

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
