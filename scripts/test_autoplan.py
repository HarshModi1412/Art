"""
Automatic weekly social planning — trigger, occasions, existing plan, sales
signals, the weekly cap, Product Studio prompts, and the Approval-panel flow
(Approve / Details / Cancel, reel tasks, watermark-cleaned clip uploads).

Run: python3 scripts/test_autoplan.py
"""
import io
import os
import sys
import time
from datetime import date, datetime, timedelta

os.environ.setdefault("AUTOPLAN_SCHEDULER", "off")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from backend.core import autoplan, smart, social  # noqa: E402

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


def account(tag):
    email = f"{tag}{int(time.time() * 1000)}@t.co"
    tok = c.post("/api/register", json={"email": email, "password": "Test12345!"}).json()["token"]
    return email, {"Authorization": "Bearer " + tok, "X-Session-Id": tag}


def add_products(H, rows):
    for r in rows:
        c.post("/api/products/item", json=r, headers=H)


def sales(email, spec, end=date(2026, 9, 5)):
    """spec: {product: (recent_rev_per_week, prior_rev_per_week)}"""
    rows, n = [], 0
    for name, (recent, prior) in spec.items():
        for wk in range(8):
            rev = recent if wk < 4 else prior
            if rev <= 0:
                continue
            d = end - timedelta(days=wk * 7 + 1)
            n += 1
            rows.append({"date": pd.Timestamp(d), "order_id": f"o{n}", "customer_id": f"c{n % 7}",
                         "product": name, "amount": float(rev), "quantity": 1})
    smart.save_sales(email, pd.DataFrame(rows), {"files": ["t.csv"]})


FRI = datetime(2026, 9, 11, 15, 0)          # the day this was written: a Friday
MON = date(2026, 9, 14)                     # next week's Monday
check("reference Friday is a Friday", FRI.weekday() == 4)

# =========================================================================
print("\n== 1. the trigger: arm first, then Saturday, once per week ==")
# =========================================================================
e1, H1 = account("ap1")
add_products(H1, [{"name": "Silk Saree", "category": "Clothing", "price": 2500, "stock": 10}])
cfg = autoplan.get_config(e1)
check("on by default", cfg["enabled"] is True, cfg)
check("Saturday by default", cfg["day"] == 5 and cfg["day_name"] == "Saturday", cfg)
check("next week means the Monday after", autoplan.next_monday(FRI.date()) == MON)
check("a Sunday's next week is the very next day",
      autoplan.next_monday(date(2026, 9, 13)) == MON)

orig_now = autoplan.now_local
autoplan.now_local = lambda email="": FRI
try:
    check("a fresh account is armed, not fired, on first look", autoplan.due(e1) is None)
    st = autoplan._state(e1)
    check("and the arming time is recorded", bool(st.get("armed_at")), st)
    sat = datetime(2026, 9, 12, 9, 30)
    check("Saturday 9:30 → next week is due", autoplan.due(e1, sat) == MON,
          autoplan.due(e1, sat))
    check("Saturday 8:59 → not yet", autoplan.due(e1, datetime(2026, 9, 12, 8, 59)) is None)
    tue = datetime(2026, 9, 15, 11, 0)
    check("server slept through Saturday → catches up on Tuesday for the running week",
          autoplan.due(e1, tue) == MON, autoplan.due(e1, tue))
    check("the following Monday belongs to the NEXT Saturday's plan",
          autoplan.due(e1, datetime(2026, 9, 21, 8, 0)) == date(2026, 9, 21))
    autoplan.save_config(e1, {"day": 2, "hour": 7})
    check("the day can be changed (Wednesday 7am)",
          autoplan.get_config(e1)["day_name"] == "Wednesday")
    check("Wednesday 7:05 after arming → the following Monday is due",
          autoplan.due(e1, datetime(2026, 9, 16, 7, 5)) == date(2026, 9, 21))
    autoplan.save_config(e1, {"day": 5, "hour": 9})
    autoplan.now_local = lambda email="": sat
    r = autoplan.run_if_due(e1)
    check("run_if_due plans it", r and r.get("added") == 4, r and r.get("note"))
    check("and a second call does nothing — once per week", autoplan.run_if_due(e1) is None)
    autoplan.save_config(e1, {"enabled": False})
    check("switched off → never due", autoplan.due(e1, datetime(2026, 9, 19, 10, 0)) is None)
finally:
    autoplan.now_local = orig_now

# =========================================================================
print("\n== 2. occasions ==")
# =========================================================================
op = autoplan.opportunities(MON, "clothing")
names = [o["name"] for o in op]
check("Ganesh Chaturthi week is found", "Ganesh Chaturthi" in names, names)
check("festivals rank first", op[0]["kind"] in ("festival", "festival_soon"), op[0])
check("the weather season is always said", any(o["kind"] == "season" for o in op))
op2 = autoplan.opportunities(date(2026, 9, 28), "clothing")
check("a week before Navratri's run-up reads as live or starting soon",
      any(o["name"] == "Navratri" for o in op2), [o["name"] for o in op2])
check("salary week is spotted at the turn of the month",
      any(o["kind"] == "payday" for o in op2))
op3 = autoplan.opportunities(date(2026, 11, 2), "jewellery")
check("Dhanteras shows for a jewellery seller", any(o["name"] == "Dhanteras" for o in op3))
op4 = autoplan.opportunities(date(2026, 11, 2), "perfume")
check("but not for a perfume seller", not any(o["name"] == "Dhanteras" for o in op4))

# =========================================================================
print("\n== 3. sales signals ==")
# =========================================================================
e2, H2 = account("ap2")
add_products(H2, [
    {"name": "Bandhani Dupatta", "category": "Clothing", "price": 1200, "stock": 15},
    {"name": "Linen Kurta", "category": "Clothing", "price": 1800, "stock": 12},
    {"name": "Silk Lehenga", "category": "Clothing", "price": 6500, "stock": 6},
])
sales(e2, {"Bandhani Dupatta": (4000, 2000), "Linen Kurta": (500, 3000)})
cat2 = autoplan._full_catalogue(e2)
sig = autoplan.sales_signals(e2, cat2)
check("sales data is read", sig["has_data"], sig)
check("the rising product is a winner",
      [w["name"] for w in sig["winners"]][:1] == ["Bandhani Dupatta"], sig["winners"])
check("and labelled rising", sig["winners"][0]["label"] == "Rising", sig["winners"][0])
slow = {s["name"]: s["label"] for s in sig["strugglers"]}
check("the falling product is struggling", slow.get("Linen Kurta") == "Slowing", slow)
check("the in-stock product with no sales is struggling too",
      slow.get("Silk Lehenga") == "Not selling", slow)
check("anchored on the data's last day, not today", sig["anchor"] == "2026-09-04", sig["anchor"])

e3, H3 = account("ap3")
add_products(H3, [{"name": "Oud Attar", "category": "Perfume", "price": 900, "stock": 40},
                  {"name": "Rose Mist", "category": "Perfume", "price": 500, "stock": 3}])
sig3 = autoplan.sales_signals(e3, autoplan._full_catalogue(e3))
check("no sales data → falls back to stock, honestly labelled",
      not sig3["has_data"] and sig3["strugglers"][0]["name"] == "Oud Attar"
      and "no sales data" in sig3["strugglers"][0]["why"], sig3)

# =========================================================================
print("\n== 4. plan a week: cap, spread, arc, product choice, Studio prompts ==")
# =========================================================================
b = autoplan.plan_week(e2, MON, now=FRI)
posts = [p for p in social._posts(e2) if p.get("autoplan_week") == MON.isoformat()]
check("standard cadence → 4 posts", b["added"] == 4 and len(posts) == 4, b["note"])
days = [p["scheduled_at"][:10] for p in posts]
check("all inside Mon–Sun of next week",
      all(MON.isoformat() <= d <= (MON + timedelta(days=6)).isoformat() for d in days), days)
check("one post a day", len(set(days)) == 4, days)
wd = sorted(date.fromisoformat(d).weekday() for d in days)
check("on the four strongest reach days (Wed, Thu, Mon, Fri)", wd == [0, 2, 3, 4], wd)
check("every post is a draft waiting on the seller", all(p["state"] == "draft" for p in posts))
check("and says where it came from", all(p["source"] == "autoplan" for p in posts))
order = [p["beat"] for p in sorted(posts, key=lambda p: p["scheduled_at"])]
check("the arc runs in calendar order", order == ["tease", "reveal", "prove", "place"], order)
by_beat = {p["beat"]: p for p in posts}
check("the 'in a real life' beat goes to the winner",
      by_beat["place"]["product_name"] == "Bandhani Dupatta" and by_beat["place"]["signal"] == "winner",
      (by_beat["place"]["product_name"], by_beat["place"]["signal"]))
check("the 'prove' beat goes to a struggling product",
      by_beat["prove"]["signal"] == "struggling", by_beat["prove"]["signal"])
counts = pd.Series([p["product_name"] for p in posts]).value_counts()
check("no product gets more than two posts", counts.max() <= 2, counts.to_dict())
_seq = sorted(posts, key=lambda p: p["scheduled_at"])
check("the tease and the reveal are the same piece — the reveal shows what the tease hid",
      by_beat["tease"]["product_name"] == by_beat["reveal"]["product_name"],
      (by_beat["tease"]["product_name"], by_beat["reveal"]["product_name"]))
check("otherwise no product on back-to-back posts",
      all(a["product_name"] != b_["product_name"] for a, b_ in zip(_seq, _seq[1:])
          if not (a["beat"] == "tease" and b_["beat"] == "reveal")),
      [(p["beat"], p["product_name"]) for p in _seq])
check("the week opens on a product that needs a push",
      by_beat["tease"]["signal"] == "struggling", by_beat["tease"]["signal"])
check("every post says why this product", all(p["plan_reason"] for p in posts))
photo = [p for p in posts if p["format"] != "reel"]
reels = [p for p in posts if p["format"] == "reel"]
check("the week mixes photos and reels", photo and reels, [p["format"] for p in posts])
check("photo posts carry the Product Studio image prompt",
      all(p["image_prompt"] for p in photo), [p["image_prompt"][:40] for p in photo])
check("with where each part of it came from", all(p["prompt_sources"] for p in photo))
check("reels carry the paste-ready video prompt",
      all((p["script"] or {}).get("ai_prompt") for p in reels))
check("no picture is drawn at plan time (allowance saved for approved posts)",
      all(not p["image_url"] for p in posts))
check("the brief names the winners and strugglers",
      b["winners"] and b["strugglers"], (b["winners"], b["strugglers"]))
check("and the festival", any(o["name"] == "Ganesh Chaturthi" for o in b["opportunities"]))

b2 = autoplan.plan_week(e2, MON, now=FRI)
check("running again for a full week adds nothing", b2["added"] == 0, b2["note"])
check("and says so in words", "already has 4 posts" in b2["note"], b2["note"])

# existing posts count against the total
e4, H4 = account("ap4")
add_products(H4, [{"name": "Kundan Set", "category": "Jewellery", "price": 3500, "stock": 5},
                  {"name": "Jhumka", "category": "Jewellery", "price": 900, "stock": 20}])
rows = social._posts(e4)
for i, dd in enumerate((MON + timedelta(days=2), MON + timedelta(days=4))):
    rows.append({"id": f"manual{i}", "product_name": "Jhumka", "product_id": "",
                 "format": "carousel", "state": "scheduled", "beat": "",
                 "scheduled_at": f"{dd.isoformat()}T18:00"})
social._save_posts(e4, rows)
b4 = autoplan.plan_week(e4, MON, now=FRI)
check("2 of 4 already planned → exactly 2 added", b4["added"] == 2 and b4["existing"] == 2, b4)
wk4 = autoplan.existing_for_week(e4, MON)
check("the week now totals the cadence, not more", len(wk4) == 4, len(wk4))
used = {p["scheduled_at"][:10] for p in wk4}
check("and the new ones avoid the days already taken", len(used) == 4, used)
social.set_state(e4, [p for p in wk4 if p.get("source") == "autoplan"][0]["id"], "cancelled")
b5 = autoplan.plan_week(e4, MON, now=FRI)
check("a cancelled post frees its slot for a manual re-run", b5["added"] == 1, b5)
check("still never past the total", len(autoplan.existing_for_week(e4, MON)) == 4)

social.save_settings(e4, {"cadence": "survival"})
b6 = autoplan.plan_week(e4, MON, now=FRI)
check("more already planned than the cadence → nothing added, nothing removed",
      b6["added"] == 0 and len(autoplan.existing_for_week(e4, MON)) == 4, b6["note"])

late = datetime(2026, 9, 19, 10, 0)            # Saturday of the week itself
e5, H5 = account("ap5")
add_products(H5, [{"name": "Tote", "category": "Clothing", "price": 800, "stock": 9}])
b7 = autoplan.plan_week(e5, MON, now=late)
check("planning a week that has mostly gone never dates a post in the past",
      all(p["scheduled_at"] > late.isoformat() for p in social._posts(e5)),
      [p["scheduled_at"] for p in social._posts(e5)])
check("and says how many days were left", "still ahead" in b7["note"], b7["note"])

# =========================================================================
print("\n== 5. the Approval panel: Approve / Details / Cancel ==")
# =========================================================================
cards = social.pending_insight_cards(e2)
ids = [x["id"] for x in cards]
check("a header card for the week", f"autoplan_{MON.isoformat()}" in ids, ids)
check("and a card per post", sum(1 for i in ids if i.startswith("post_")) == 4, ids)
far = [x for x in cards if x["id"].startswith("post_")]
check("posts more than 7 days out still reach the panel (Sunday plan → following Sunday)",
      all(x["autoplan"] for x in far))
check("each carries its reason", all(x["plan_reason"] for x in far))
reel_card = next(x for x in far if x["kind"] == "reel")
check("the reel card says what approving does",
      "task" in reel_card["cta"].lower() and "Google Flow" in reel_card["needs_from_you"],
      reel_card)
dressed = smart.build_insights(e2)
head = next(x for x in dressed if x["id"].startswith("autoplan_"))
check("the week header is dressed by the Social Media Manager",
      head["manager"] == "social" and "planned" in head["headline"], head.get("headline"))
soc = [x for x in dressed if x["manager"] == "social"]
check("and leads its desk's cards", soc[0]["id"].startswith("autoplan_"), [x["id"] for x in soc][:3])

# =========================================================================
print("\n== 6. endpoints: settings, run now, approve, reel task, clip, schedule ==")
# =========================================================================
e6, H6 = account("ap6")
add_products(H6, [{"name": "Chanderi Kurta", "category": "Clothing", "price": 2200, "stock": 8},
                  {"name": "Mul Saree", "category": "Clothing", "price": 3100, "stock": 4}])
r = c.get("/api/social/autoplan", headers=H6)
check("status endpoint 200", r.status_code == 200, r.text[:200])
check("Saturday is the default there too", r.json()["day_name"] == "Saturday")
r = c.post("/api/social/autoplan/settings", json={"day": 6, "hour": 10}, headers=H6)
check("settings save (Sunday 10am)", r.json()["day_name"] == "Sunday" and r.json()["hour"] == 10,
      r.json())
r = c.post("/api/social/settings", json={"patch": {"auto_plan_day": 9}}, headers=H6)
check("an out-of-range day is folded back into the week",
      r.json()["auto_plan_day"] == 2, r.json().get("auto_plan_day"))

r0 = c.get("/api/smart/state", headers=H6)
tag0 = r0.headers.get("etag")
r = c.post("/api/social/autoplan/run-now", json={}, headers=H6)
check("run-now plans next week", r.status_code == 200 and r.json()["brief"]["added"] == 4,
      r.text[:300])
wk = r.json()["brief"]["week_start"]
r1 = c.get("/api/smart/state", headers={**H6, "If-None-Match": tag0 or ""})
check("the home screen is NOT answered 304 after a plan lands",
      r1.status_code == 200, r1.status_code)
ins = r1.json()["insights"]
check("the plan is in the Approval panel", any(i["id"] == f"autoplan_{wk}" for i in ins))
check("the home payload says when the next automatic plan is",
      bool((r1.json().get("autoplan") or {}).get("next_run")))

mine = [p for p in social._posts(e6) if p.get("autoplan_week") == wk]
img = next(p for p in mine if p["format"] != "reel")
reel = next(p for p in mine if p["format"] == "reel")

r = c.post("/api/social/approve-ready", json={"post_id": img["id"]}, headers=H6)
d = r.json()
check("approving a photo post succeeds", r.status_code == 200, r.text[:200])
check("with no image engine here, it is approved — not scheduled with an empty frame",
      d["post"]["state"] == "approved", d["post"]["state"])
check("the reason is reported", "image engine" in d["media_error"].lower(), d["media_error"])
check("and it goes on the task list instead of slipping out",
      d["task"] and d["task"]["kind"] == "photo", d["task"])

r = c.post("/api/social/approve-ready", json={"post_id": reel["id"]}, headers=H6)
d = r.json()
check("approving a reel succeeds", r.status_code == 200, r.text[:200])
check("it waits for its clip (approved, not scheduled)", d["post"]["state"] == "approved")
check("it hands back the video prompt", bool((d["script"] or {}).get("ai_prompt")))
t = d["task"]
check("a video task is created", t and t["kind"] == "video" and t["post_id"] == reel["id"], t)
check("with the whole flow as steps",
      [s["id"] for s in t["steps"]] == ["copy", "flow", "make", "upload", "schedule"], t["steps"])
check("and it sits at the TOP of the task list", d["tasks"][0]["id"] == t["id"],
      [x["text"] for x in d["tasks"]][:3])
r = c.post("/api/social/approve-ready", json={"post_id": reel["id"]}, headers=H6)
check("approving twice does not duplicate the task",
      sum(1 for x in r.json()["tasks"] if x.get("post_id") == reel["id"]) == 1)

r = c.post("/api/smart/tasks", json={"action": "progress", "task_id": t["id"], "step": "copy"},
           headers=H6)
check("step progress is remembered",
      "copy" in next(x for x in r.json()["tasks"] if x["id"] == t["id"])["steps_done"])

r = c.post("/api/social/schedule-ready", json={"post_id": reel["id"]}, headers=H6)
check("a reel with no clip cannot be scheduled", r.status_code == 400, r.status_code)

# a Flow-style clip: moving picture with a static white corner mark
import cv2  # noqa: E402
import tempfile  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

W, Hh, N = 480, 270, 40
yy, xx = np.mgrid[0:Hh, 0:W + 3 * N].astype(np.float32)
wide = np.clip(np.stack([80 + 70 * xx / W, 60 + 50 * yy / Hh,
                         70 + 25 * np.sin(xx / 9.0)], 2), 0, 255).astype(np.uint8)
tmp = tempfile.mkdtemp()
src = os.path.join(tmp, "flow.mp4")
vw = cv2.VideoWriter(src, cv2.VideoWriter_fourcc(*"mp4v"), 24, (W, Hh))
for i in range(N):
    im = Image.fromarray(wide[:, 3 * i:3 * i + W].copy()).convert("RGBA")
    lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(lay).text((W - 70, Hh - 34), "Veo", fill=(255, 255, 255, 170),
                             font=__import__("PIL.ImageFont", fromlist=["x"]).load_default(size=20))
    vw.write(cv2.cvtColor(np.asarray(Image.alpha_composite(im, lay).convert("RGB")),
                          cv2.COLOR_RGB2BGR))
vw.release()
with open(src, "rb") as fh:
    up = c.post("/api/site/image", files={"files": ("flow.mp4", fh.read(), "video/mp4")},
                headers={"Authorization": H6["Authorization"]})
check("the clip uploads", up.status_code == 200, up.text[:200])
raw_url = up.json()["url"]
r = c.post("/api/social/attach-video", json={"post_id": reel["id"], "url": raw_url}, headers=H6)
d = r.json()
check("attaching it runs the watermark remover", (d.get("watermark") or {}).get("checked"),
      d.get("watermark"))
check("the Flow mark is removed", (d.get("watermark") or {}).get("removed"), d.get("watermark"))
check("the post gets the CLEAN copy, the original upload is kept",
      d["video_url"] and d["video_url"] != raw_url, (d["video_url"], raw_url))
check("the task's upload step is ticked",
      "upload" in next(x for x in d["tasks"] if x["id"] == t["id"])["steps_done"])
check("the post still waits for the seller's 'Save & schedule'", d["state"] == "approved")

when = f"{(date.fromisoformat(wk) + timedelta(days=2)).isoformat()}T19:30"
r = c.post("/api/social/schedule-ready", json={"post_id": reel["id"], "scheduled_at": when},
           headers=H6)
check("save & schedule works once the clip is on", r.status_code == 200, r.text[:200])
check("it is scheduled at the time chosen",
      r.json()["post"]["state"] == "scheduled" and r.json()["post"]["scheduled_at"] == when,
      r.json()["post"])
check("and the task closes itself",
      next(x for x in r.json()["tasks"] if x["id"] == t["id"])["done"] is True)

left = [p for p in social._posts(e6) if p.get("autoplan_week") == wk and p["state"] == "draft"]
one = left[0]
r = c.post(f"/api/smart/insight/post_{one['id']}/decision", json={"decision": "cancel"}, headers=H6)
check("Cancel from the panel works", r.status_code == 200, r.text[:200])
check("the post is cancelled", social.get_post(e6, one["id"])["state"] == "cancelled")
cal = c.get("/api/social/month", headers=H6,
            params={"year": int(wk[:4]), "month": int(wk[5:7])}).json()
check("and hidden from the calendar",
      one["id"] not in [p["id"] for dd in cal["days"] for p in dd["posts"]])
check("and gone from the panel",
      f"post_{one['id']}" not in [i["id"] for i in r.json()["insights"]])

r = c.post(f"/api/smart/insight/autoplan_{wk}/decision", json={"decision": "cancel"}, headers=H6)
check("Cancel on the week header cancels what is left",
      not [p for p in social._posts(e6) if p.get("autoplan_week") == wk and p["state"] == "draft"])
check("and the header card goes away",
      not any(i["id"].startswith("autoplan_") for i in r.json()["insights"]))
cancelled_photo = social.get_post(e6, img["id"])
check("an already-approved post is not touched by the week's Cancel",
      cancelled_photo["state"] == "approved", cancelled_photo["state"])

r = c.post("/api/social/attach-image", json={"post_id": img["id"], "url": "/generated_images/x.png"},
           headers=H6)
r = c.post("/api/social/schedule-ready", json={"post_id": img["id"]}, headers=H6)
check("a photo post scheduled once its picture is added", r.json()["post"]["state"] == "scheduled")
check("closing its task too",
      all(x["done"] for x in r.json()["tasks"] if x.get("post_id") == img["id"]))

r = c.post("/api/social/autoplan/run-now", json={}, headers=H6)
check("run-now again fills the slots freed by Cancel, and only those",
      r.json()["brief"]["added"] == 2 and r.json()["brief"]["existing"] == 2, r.json()["brief"]["note"])

# approve the whole week from its header card
r = c.post(f"/api/smart/insight/autoplan_{wk}/decision", json={"decision": "approve"}, headers=H6)
res = r.json().get("results") or []
check("Approve on the header approves every waiting post", len(res) == 2, res)
check("each one through the approve-and-make-ready path",
      all(x["state"] in ("approved", "scheduled") for x in res), res)

r = c.post("/api/social/autoplan/run", headers={"X-Admin-Token": "nope"})
check("the cron endpoint is operator-only", r.status_code in (403, 503), r.status_code)

# =========================================================================
print("\n== 7. the frontend is wired for it ==")
# =========================================================================
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = open(os.path.join(ROOT, "Smart CafeX", "smart.js"), encoding="utf-8").read()
CSS = open(os.path.join(ROOT, "Smart CafeX", "smart.css"), encoding="utf-8").read()
check("post cards offer Approve / Details / Cancel", "data-cancel=" in JS and '"cancel"' in JS)
check("the task list is at the top of Home",
      JS.index('id="taskBox"') < JS.index('id="todayBox"'))
check("video tasks open the step-by-step popup", "openVideoTask" in JS)
check("with Google Flow in it", "labs.google/fx/tools/flow" in JS or "showVideoTools" in JS)
check("and a Save & schedule step", "/api/social/schedule-ready" in JS)
check("the setup lets the seller pick the day", "apDay" in JS and "/api/social/autoplan/settings" in JS)
check("and plan next week on demand", "/api/social/autoplan/run-now" in JS)
check("the old ReferenceError in approvePostReady is gone",
      "findPost ? findPost(postId)" not in JS)
check("styles exist for the new pieces", ".vt-steps2" in CSS and ".task-card" in CSS)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
