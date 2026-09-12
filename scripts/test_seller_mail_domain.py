"""
Three things a seller asked for, and the reasons they matter:

  * a purchase order has to come from THEIR email, not the app's, or the
    supplier treats it as spam and nobody rings to confirm;
  * an order already sent has to be cancellable — with the supplier told, or
    they keep making it and bill for it;
  * their shop has to answer on their own domain, not only on /s/<handle>.

Plus the reel prompt: no app layout, no burnt-in text, and a week of reels
that are not all the same kind of film.

Run: python3 scripts/test_seller_mail_domain.py
"""
import os
import sys
import time

os.environ.setdefault("AUTOPLAN_SCHEDULER", "off")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from backend.core import (messaging, replenish, seller_mail, sitebuilder,  # noqa: E402
                          social, supply)

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
email = f"own{int(time.time() * 1000)}@t.co"
H = {"Authorization": "Bearer " + c.post("/api/register", json={"email": email, "password": "Test12345!"}).json()["token"],
     "X-Session-Id": "own"}

print("\n== the order comes from the seller's own address ==")
r = c.get("/api/mail/account", headers=H).json()
check("nothing connected to begin with", r["connected"] is False, r)
check("and the app knows where a gmail address sends from",
      seller_mail.guess("harsh@gmail.com")["host"] == "smtp.gmail.com"
      and seller_mail.guess("harsh@gmail.com")["port"] == 587, seller_mail.guess("harsh@gmail.com"))
check("a business domain gets a sensible guess, marked as a guess",
      seller_mail.guess("po@korastudio.in") == {**seller_mail.guess("po@korastudio.in"),
                                                "host": "smtp.korastudio.in", "known": False})

sent_as = []


class _FakeSMTP:
    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def ehlo(self):
        pass

    def starttls(self, **k):
        pass

    def login(self, user, password):
        if password != "app-password-ok":
            import smtplib
            raise smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted")

    def send_message(self, msg):
        sent_as.append({"from": msg["From"], "to": msg["To"], "subject": msg["Subject"],
                        "atts": [p.get_filename() for p in msg.iter_attachments()]})


_real = seller_mail.smtplib.SMTP
seller_mail.smtplib.SMTP = _FakeSMTP
r = c.post("/api/mail/account", headers=H,
           json={"address": "kora@gmail.com", "password": "wrong", "display_name": "Kora Studio"})
check("a wrong password is refused, in the seller's words",
      r.status_code == 400 and "app password" in r.json()["detail"].lower(), r.text[:200])
check("and nothing is saved", c.get("/api/mail/account", headers=H).json()["connected"] is False)
r = c.post("/api/mail/account", headers=H,
           json={"address": "kora@gmail.com", "password": "app-password-ok", "display_name": "Kora Studio"})
check("the right password connects it", r.status_code == 200 and r.json()["connected"], r.text[:200])
check("…after a real test message to themselves",
      sent_as and sent_as[-1]["to"] == "kora@gmail.com", sent_as[-1:])
check("the password is never handed back", "password" not in r.json(), list(r.json()))

# an order, sent from that account
c.post("/api/products/item", headers=H, json={"name": "Kurta", "category": "Clothing", "price": 999, "stock": 10})
inv = c.post("/api/supply/item", headers=H, json={
    "name": "Cotton fabric", "unit_label": "m", "current_stock": 20, "lead_time_days": 5, "moq": 50,
    "unit_cost": 120, "supplier_name": "Sharma Textiles", "supplier_email": "orders@sharma.example",
    "link_product": "Kurta", "qty_per_unit": 2}).json()
fab = next(x for x in inv["inventory"] if x["name"] == "Cotton fabric")
r = c.post("/api/purchase-orders/manual", headers=H, json={
    "supplier": {"name": "Sharma Textiles", "email": "orders@sharma.example"},
    "lines": [{"inventory_id": fab["id"], "order_qty": 100}], "send": True})
j = r.json()
check("the PO goes out", (j.get("send") or {}).get("sent") is True, r.text[:300])
check("from the seller's address, not the app's",
      "kora@gmail.com" in (sent_as[-1]["from"] or "") and (j["send"].get("from") == "kora@gmail.com"),
      (sent_as[-1]["from"], j["send"].get("from")))
check("with their shop's name on it, and the PO attached",
      "Kora Studio" in sent_as[-1]["from"] and any(str(a).endswith(".pdf") for a in sent_as[-1]["atts"]),
      sent_as[-1])
check("no server mailbox was needed for any of it", not messaging.smtp_configured())

print("\n== cancelling an order that is already out ==")
n = j["po_number"]
before = len(sent_as)
r = c.post("/api/supply/po/cancel", headers=H, json={"po_number": n, "tell_supplier": True,
                                                     "note": "festival stock covered"})
d = r.json()
check("it is cancelled", r.status_code == 200 and supply.get_po(email, n)["status"] == "cancelled", r.text[:200])
check("and the supplier is told, in writing",
      d["told_supplier"]["sent"] is True and len(sent_as) == before + 1
      and sent_as[-1]["to"] == "orders@sharma.example", d.get("told_supplier"))
check("the note quotes the PO number so they can find it",
      n in (sent_as[-1]["subject"] or ""), sent_as[-1]["subject"])
check("the history says the supplier was told",
      any("told" in (h.get("note") or "") for h in supply.get_po(email, n)["history"]),
      supply.get_po(email, n)["history"][-1:])
r2 = c.post("/api/purchase-orders/manual", headers=H, json={
    "supplier": {"name": "Sharma Textiles", "email": "orders@sharma.example"},
    "lines": [{"inventory_id": fab["id"], "order_qty": 60}], "send": False})
before = len(sent_as)
c.post("/api/supply/po/cancel", headers=H, json={"po_number": r2.json()["po_number"], "tell_supplier": True})
check("a draft nobody has seen is cancelled quietly — no email",
      len(sent_as) == before, sent_as[-1:])
seller_mail.smtplib.SMTP = _real
c.delete("/api/mail/account", headers=H)
check("it can be disconnected again", c.get("/api/mail/account", headers=H).json()["connected"] is False)

print("\n== the seller's own domain ==")
DOMAIN = f"kora{int(time.time())}.com"          # fresh each run: the index is shared
site = c.get("/api/site/state", headers=H).json()["site"]
site.update({"handle": f"kora{int(time.time())}"[:20], "brand": "Kora Studio",
             "custom_domain": f"https://{DOMAIN.upper()}/shop"})
r = c.post("/api/site/save", headers=H, json={"site": site})
saved = r.json().get("site") or {}
check("a domain is cleaned up before it is saved", saved.get("custom_domain") == DOMAIN,
      saved.get("custom_domain"))
check("and it resolves to this shop", sitebuilder.resolve_domain(DOMAIN) == saved["handle"])
check("www too, because customers type it", sitebuilder.resolve_domain("www." + DOMAIN) == saved["handle"])
r = c.get("/", headers={"host": DOMAIN})
check("a request on that domain serves the shop, not the landing page",
      r.status_code == 200 and "__STORE_HANDLE__" in r.text and saved["handle"] in r.text,
      r.status_code)
r = c.get("/", headers={"host": "testserver"})
check("the app's own address still serves the app", r.status_code == 200 and "__STORE_HANDLE__" not in r.text)
r = c.get("/api/site/state", headers={**H, "host": DOMAIN})
check("the API keeps working on a shop domain", r.status_code == 200, r.status_code)
check("nonsense is refused", c.post("/api/site/save", headers=H,
                                    json={"site": {**site, "custom_domain": "not a domain"}}).status_code == 400)
other = f"two{int(time.time() * 1000)}@t.co"
H2 = {"Authorization": "Bearer " + c.post("/api/register", json={"email": other, "password": "Test12345!"}).json()["token"],
      "X-Session-Id": "two"}
s2 = c.get("/api/site/state", headers=H2).json()["site"]
s2.update({"handle": f"two{int(time.time())}"[:20], "brand": "Two", "custom_domain": DOMAIN})
check("and a domain already in use here cannot be stolen",
      c.post("/api/site/save", headers=H2, json={"site": s2}).status_code == 400)
chk = c.get("/api/site/domain-check?domain=example.invalid", headers=H).json()
check("the checker says what is wrong, not just 'no'", chk["ok"] is False and "resolve" in chk["message"], chk)

print("\n== the reel prompt ==")
s = social.get_settings(email)
sc = {"beats": [{"sec": "0-2", "shot": "Fold the kurta", "on_screen_text": "Hand block print"},
                {"sec": "2-5", "shot": "Wrap it in tissue", "on_screen_text": "Packed today"},
                {"sec": "5-8", "shot": "Close the box", "on_screen_text": "Ships tomorrow"},
                {"sec": "8-12", "shot": "A fourth shot for filming", "on_screen_text": "x"}],
      "voiceover": ""}
p = social.build_video_prompt(sc, {"name": "Indigo Kurta", "category": "clothing"}, s, None,
                              "detail", "", "", "packing")
check("no platform layout is asked for", "Instagram" not in p and "phone frame" in p, p[:120])
check("and no text is burnt into the video",
      "TEXT: none" in p and "Hand block print" not in p, [l for l in p.splitlines() if "TEXT" in l])
check("it asks for a clip a video AI can actually make", "8 seconds" in p and "45 seconds" not in p,
      [l for l in p.splitlines() if "econds" in l])
check("only the shots that fit are in it", "A fourth shot for filming" not in p)
check("the style is named so two reels differ", "STYLE: packing an order" in p,
      [l for l in p.splitlines() if l.startswith("STYLE")])
styles = {social._reel_style(n, p_, "") for n in ("Kurta", "Bag", "Dupatta", "Ring", "Saree", "Perfume")
          for p_ in ("new", "proof", "care")}
check("a week of reels is not all the same kind", len(styles) >= 4, styles)
check("every style says how to shoot it",
      all(v.get("brief") and v.get("pace") for v in social.REEL_STYLES.values()))
sysmsg = social._script_system(s, "making")
check("and the script itself is written for that style",
      "how it is made" in sysmsg and "burnt into the footage" in sysmsg, sysmsg[:200])

JS = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "Smart CafeX", "smart.js"), encoding="utf-8").read()
check("the app has the screen to connect an email", "openMailAccount" in JS and "/api/mail/account" in JS)
check("and the cancel flow offers to tell the supplier",
      "async function cancelPo" in JS and "/api/supply/po/cancel" in JS and "cpTell" in JS)
check("the site builder asks for the domain and shows the DNS records",
      'id="siteDomain"' in JS and "CNAME" in JS and "domain-check" in JS)
STORE = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "Smart CafeX", "storefront", "store.js"), encoding="utf-8").read()
check("the storefront reads its handle from the page on a custom domain",
      "__STORE_HANDLE__" in STORE)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
