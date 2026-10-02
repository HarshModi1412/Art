"""
Guard for the "we missed N posts" line in the Approval panel.

A week planned on the 1st and opened on the 4th used to show the 1st-3rd as
"Overdue" cards to approve, on top of the posts that could still go out.
Approving them could not post them (the publisher will not post more than
GRACE_HOURS late). Now they are one dismissable line, and only posts that can
still go out are offered.

Run: python3 scripts/test_missed_posts.py
"""
import os
import sys
import time
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from backend import main  # noqa: E402
from backend.core import localtime, publisher, social, user_store  # noqa: E402

PASS = FAIL = 0


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}{(' (' + str(extra) + ')') if extra else ''}")
    else:
        FAIL += 1
        print(f"  ✗ {label}  <-- {extra}")


c = TestClient(main.app)
email = f"mp{int(time.time() * 1000)}@t.co"
tok = c.post("/api/register", json={"email": email, "password": "Test12345!"}).json()["token"]
H = {"Authorization": "Bearer " + tok, "X-Session-Id": f"mp-{time.time_ns()}"}
now = localtime.now(email)


def post(pid, when, **extra):
    return {"id": pid, "state": "draft", "format": "image", "product_id": "",
            "product_name": f"Kurta {pid}", "pillar": "detail",
            "scheduled_at": when.strftime("%Y-%m-%dT%H:%M:%S"), **extra}


def day(d, hour=11):
    return (now + timedelta(days=d)).replace(hour=hour, minute=0, second=0, microsecond=0)


def ids(cards):
    return [x["id"] for x in cards]


print("\n== 1. planned on the 1st, opened on the 4th ==")
user_store.set_key(email, social.POSTS_KEY, [
    post("old", day(-20)),                      # older than the lookback
    post("m1", day(-3)), post("m2", day(-2)), post("m3", day(-1)),
    post("f1", day(1)), post("f2", day(2)),
])
cards = social.pending_insight_cards(email)
notice = [x for x in cards if x.get("notice")]
check("one notice line, not a card per missed post", len(notice) == 1, ids(cards))
check("it counts the three from this week", notice and notice[0]["missed"] == 3, notice)
check("it says so in words", notice and notice[0]["title"] == "We missed 3 posts")
check("a month-old draft is not mentioned", "post_old" not in ids(cards))
check("missed posts are not offered for approval",
      not any(i in ids(cards) for i in ("post_m1", "post_m2", "post_m3")))
check("upcoming posts are", "post_f1" in ids(cards) and "post_f2" in ids(cards))
check("the notice comes first", cards and cards[0].get("notice"))

print("\n== 2. today's posts ==")
late_today = now - timedelta(hours=publisher.GRACE_HOURS + 1)
soon_late = now - timedelta(hours=1)
rows = social._posts(email)
if late_today.date() == now.date():
    rows.append(post("t_late", late_today))
rows.append(post("t_recent", soon_late))
user_store.set_key(email, social.POSTS_KEY, rows)
cards = social.pending_insight_cards(email)
check("an hour late today is still a card (it would still go out)",
      "post_t_recent" in ids(cards) or soon_late.date() != now.date())
if late_today.date() == now.date():
    check("past the publisher's grace today joins the missed line",
          "post_t_late" not in ids(cards))

print("\n== 3. the panel through the API ==")
r = c.get("/api/smart/state", headers=H).json()
panel = r.get("insights") or []
nid = next((x["id"] for x in panel if x.get("notice")), None)
check("the notice reaches the panel", nid is not None, ids(panel))
dressed = next((x for x in panel if x.get("notice")), {})
check("dressed as the Social Media Manager, with its own words",
      dressed.get("manager") == "social" and dressed.get("headline", "").startswith("We missed"),
      dressed.get("headline"))
tag1 = c.get("/api/smart/state", headers=H).headers.get("etag")
r = c.post(f"/api/smart/insight/{nid}/decision", headers=H, json={"decision": "disapprove"})
check("dismissing it succeeds", r.status_code == 200, r.status_code)
panel = c.get("/api/smart/state", headers=H).json().get("insights") or []
check("and it stays gone", not any(x.get("notice") for x in panel), ids(panel))
tag2 = c.get("/api/smart/state", headers=H).headers.get("etag")
check("the home screen's ETag changes, so a reload cannot repaint the old line", tag1 != tag2)
hist = c.get("/api/smart/history", headers=H).json()
check("a dismissed notice does not clutter History",
      not any(str(h.get("id", "")).startswith("missed_") for h in hist.get("dismissed", [])))

print("\n== 4. a new miss brings the line back ==")
rows = social._posts(email)
rows.append(post("m4", day(-1, hour=15)))
user_store.set_key(email, social.POSTS_KEY, rows)
panel = c.get("/api/smart/state", headers=H).json().get("insights") or []
n2 = next((x for x in panel if x.get("notice")), None)
check("the line is back with the new count", n2 is not None and n2["id"] != nid, n2 and n2["id"])

print("\n== 5. approving the week never touches a missed post ==")
email2 = f"mp{int(time.time() * 1000) + 7}@t.co"
tok2 = c.post("/api/register", json={"email": email2, "password": "Test12345!"}).json()["token"]
H2 = {"Authorization": "Bearer " + tok2, "X-Session-Id": f"mp2-{time.time_ns()}"}
wk = "2030-01-06"
user_store.set_key(email2, social.POSTS_KEY, [
    post("wm", day(-1), source="autoplan", autoplan_week=wk),
    post("wf", day(1), source="autoplan", autoplan_week=wk),
])
c.post(f"/api/smart/insight/autoplan_{wk}/decision", headers=H2, json={"decision": "approve"})
st = {p["id"]: p["state"] for p in social._posts(email2)}
check("the upcoming post was approved", st.get("wf") in ("approved", "scheduled"), st)
check("the missed one was left alone", st.get("wm") == "draft", st)
summary = [x for x in social.pending_insight_cards(email2) if x.get("summary")]
check("the week's header no longer counts the missed post", not summary, summary)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
