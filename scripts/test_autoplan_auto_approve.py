"""
Guard for "don't ask me to approve the week's schedule, just do it".

A planned week used to wait in the Approval panel as drafts behind a weekly
header card. Now the planner approves its own posts in the background through
the same path as the Approve button: photo posts get their picture and are
scheduled, reels are approved with a clip task. The seller is only asked about
a post the worker could not finish.

Run: python3 scripts/test_autoplan_auto_approve.py
"""
import os
import sys
import time
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from backend import main  # noqa: E402
from backend.core import autoplan, localtime, smart, social, studio, user_store  # noqa: E402

PASS = FAIL = 0


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}{(' (' + str(extra) + ')') if extra else ''}")
    else:
        FAIL += 1
        print(f"  ✗ {label}  <-- {extra}")


drawn = []


def fake_picture(email, product_id, pillar, fmt, **k):
    drawn.append(product_id)
    return {"url": f"/media/fake{len(drawn)}.png", "prompt": "p"}


studio.generate_image_only = fake_picture
c = TestClient(main.app)


def account(tag):
    email = f"{tag}{int(time.time() * 1000)}@t.co"
    tok = c.post("/api/register", json={"email": email, "password": "Test12345!"}).json()["token"]
    return email, {"Authorization": "Bearer " + tok, "X-Session-Id": f"{tag}-{time.time_ns()}"}


def seed(email, week="2030-01-06"):
    now = localtime.now(email)
    at = lambda d: (now + timedelta(days=d)).replace(hour=11, minute=0, second=0,
                                                    microsecond=0).strftime("%Y-%m-%dT%H:%M:%S")
    base = {"source": "autoplan", "autoplan_week": week, "state": "draft",
            "product_id": "", "pillar": "detail"}
    user_store.set_key(email, social.POSTS_KEY, [
        {**base, "id": "photo1", "format": "image", "product_name": "Kurta", "scheduled_at": at(1)},
        {**base, "id": "photo2", "format": "carousel", "product_name": "Saree", "scheduled_at": at(2)},
        {**base, "id": "reel1", "format": "reel", "product_name": "Dupatta", "scheduled_at": at(3),
         "script": {"beats": [{"sec": "0-2", "shot": "hands on fabric", "on_screen_text": "x"}]}},
        {**base, "id": "gone", "format": "image", "product_name": "Old", "scheduled_at": at(-2)},
        {"id": "mine", "state": "draft", "format": "image", "product_id": "", "pillar": "detail",
         "product_name": "Hand-made", "scheduled_at": at(1)},
    ])


def states(email):
    return {p["id"]: p["state"] for p in social._posts(email)}


def wait_until(fn, secs=10):
    end = time.time() + secs
    while time.time() < end:
        if fn():
            return True
        time.sleep(0.1)
    return fn()


print("\n== 1. the panel does not ask about the planned week ==")
email, H = account("aa")
seed(email)
ids = [x["id"] for x in social.pending_insight_cards(email)]
check("no card for an auto-planned post", not any(i in ids for i in ("post_photo1", "post_photo2", "post_reel1")), ids)
check("no 'approve the week' header card", not any(i.startswith("autoplan_") for i in ids), ids)
check("a post the seller made by hand is still asked about", "post_mine" in ids, ids)
check("on by default", autoplan.get_config(email)["auto_approve"] is True)

print("\n== 2. the week approves itself ==")
r = autoplan.approve_waiting(email)
st = states(email)
check("all three upcoming posts approved", r["approved"] == 3 and r["failed"] == 0, r)
check("photo posts got a picture and are scheduled",
      st["photo1"] == "scheduled" and st["photo2"] == "scheduled", st)
check("the reel is approved, waiting for its clip", st["reel1"] == "approved", st)
check("and its clip is on the task list",
      any(t.get("post_id") == "reel1" and not t.get("done") for t in smart.get_tasks(email)))
check("a post whose day has gone is left alone (it is in the missed line)", st["gone"] == "draft", st)
check("a hand-made draft is not touched", st["mine"] == "draft", st)
check("one picture per photo post, no more", len(drawn) == 2, drawn)
check("running it again does nothing (nothing left waiting)",
      autoplan.approve_waiting(email) == {"approved": 0, "failed": 0})

print("\n== 3. opening the app finishes a week that was left waiting ==")
email2, H2 = account("ab")
seed(email2)
main.smart_state  # noqa: B018 — the endpoint below calls autoplan.kick
c.get("/api/smart/state", headers=H2)
ok = wait_until(lambda: states(email2)["photo1"] == "scheduled" and states(email2)["reel1"] == "approved", 40)
check("the home screen kicked the worker and it approved the week", ok, states(email2))

print("\n== 4. a post it cannot approve comes back to the panel ==")
email3, H3 = account("ac")
seed(email3)
real = autoplan._auto_approver


def flaky(e, pid):
    if pid == "photo2":
        raise RuntimeError("the picture service is down")
    return real(e, pid)


autoplan.set_auto_approver(flaky)
r = autoplan.approve_waiting(email3)
autoplan.set_auto_approver(real)
check("the rest of the week still went through", r == {"approved": 2, "failed": 1}, r)
post = social.get_post(email3, "photo2")
check("the failed post says why", "picture service" in (post.get(autoplan.AUTO_APPROVE_ERROR) or ""), post)
ids = [x["id"] for x in social.pending_insight_cards(email3)]
check("and it is a card in the panel again", "post_photo2" in ids, ids)
check("it is not retried behind the seller's back", autoplan.waiting_for_auto_approve(email3) == [])

print("\n== 5. the setting can turn it off ==")
email4, H4 = account("ad")
seed(email4)
r = c.post("/api/social/autoplan/settings", headers=H4, json={"auto_approve": False})
check("settings accept auto_approve", r.status_code == 200 and r.json().get("auto_approve") is False,
      r.status_code)
ids = [x["id"] for x in social.pending_insight_cards(email4)]
check("off: the planned posts are asked about again", "post_photo1" in ids, ids)
c.get("/api/smart/state", headers=H4)
time.sleep(1)
check("off: nothing is approved by itself", states(email4)["photo1"] == "draft", states(email4))

print("\n== 6. planning a week now starts the approval ==")
email5, H5 = account("ae")
for row in ({"name": "Chanderi Kurta", "category": "Clothing", "price": 2200, "stock": 8},
            {"name": "Mul Saree", "category": "Clothing", "price": 3100, "stock": 4}):
    c.post("/api/products/item", json=row, headers=H5)
nxt = autoplan.next_monday(localtime.now(email5).date())
brief = autoplan.run_for(email5, nxt, trigger="manual")
check("the plan says it is approving", brief.get("auto_approving", 0) > 0, brief.get("note"))
ok = wait_until(lambda: not autoplan.waiting_for_auto_approve(email5), 60)
mine = [p for p in social._posts(email5) if p.get("source") == "autoplan"]
check("and every planned post leaves draft by itself",
      ok and mine and all(p["state"] in ("scheduled", "approved") for p in mine),
      [(p["format"], p["state"]) for p in mine])

print("\n== 7. the worker and a tap at the same moment make one task, not two ==")
import threading  # noqa: E402

email6, _ = account("af")
seed(email6)
reel = social.get_post(email6, "reel1")


def ensure(delay):
    with user_store.request_scope():
        smart.get_tasks(email6)          # the request reads its state first...
        time.sleep(delay)                # ...then does slow work
        smart.ensure_post_task(email6, reel, "video")


# staggered, so the two tasks are made at clearly different times (Windows'
# clock is coarse enough that two at once could share a timestamp by luck)
ts = [threading.Thread(target=ensure, args=(d,)) for d in (0.2, 0.3)]
[t.start() for t in ts]
[t.join() for t in ts]
made = [t for t in smart.get_tasks(email6) if t.get("post_id") == "reel1"]
check("one 'make the reel' task", len(made) == 1, [t["text"] for t in made])

print("\n== 8. a slow background job does not undo an approval made meanwhile ==")
email7, _ = account("ag")
seed(email7)


def slow_planner():
    # what plan_week does: read the posts, spend a while writing captions,
    # then save the list with its own changes
    with user_store.job_scope():
        rows = social._posts(email7)
        time.sleep(0.4)
        rows.append({"id": "newweek", "state": "draft", "format": "image",
                     "product_name": "New", "scheduled_at": "2030-01-08T10:00:00"})
        social._save_posts(email7, rows)


t = threading.Thread(target=slow_planner)
t.start()
time.sleep(0.1)
with user_store.job_scope():
    social.set_state(email7, "photo1", "scheduled")   # approved while it ran
t.join()
st = states(email7)
check("the approval survived", st.get("photo1") == "scheduled", st)
check("and the planner's new post is there too", "newweek" in st, st)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
