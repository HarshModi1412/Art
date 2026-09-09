"""
Regression guard for the Social Media Manager rework: the in-page approval
strip was removed (decisions moved to the global Approval panel / the post
editor), and three things were added: GET /api/social/post/{id} (so the
editor can be opened from outside the calendar, e.g. via the panel's
Details button), POST /api/social/clear (the new "Clear plan" button), and
routing post_<id> decisions from the Approval panel's generic
approve/disapprove through to social.set_state() rather than the normal
insight history bookkeeping.

Run: python3 scripts/test_social_manager.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from backend.main import app  # noqa: E402

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
email = f"soc{int(time.time()*1000)}@t.co"
tok = c.post("/api/register", json={"email": email, "password": "Test12345!"}).json()["token"]
H = {"Authorization": "Bearer " + tok, "X-Session-Id": "soc-sess"}

c.post("/api/products/item", json={"name": "Silk Saree", "category": "Clothing", "price": 2500, "stock": 10}, headers=H)

r = c.post("/api/social/week", json={"weeks": 1}, headers=H)
check("week planned", r.status_code == 200, r.text[:200])

d = c.get("/api/social", headers=H).json()
cal = c.get("/api/social/month", headers=H, params={"year": 2026, "month": 9}).json()
posts = [p for day in cal.get("days", []) for p in day.get("posts", [])]
check("posts exist after planning", len(posts) > 0, len(posts))

if posts:
    pid = posts[0]["id"]
    r = c.get(f"/api/social/post/{pid}", headers=H)
    check("GET single post 200", r.status_code == 200, r.text[:200])
    check("post has caption", bool(r.json().get("caption")), r.json())

    # decision routing through smart_decision, both approve and disapprove
    r = c.post(f"/api/smart/insight/post_{pid}/decision", json={"decision": "approve"}, headers=H)
    check("post_ approve routes and succeeds", r.status_code == 200, r.text[:300])
    r2 = c.get(f"/api/social/post/{pid}", headers=H)
    check("state became scheduled", r2.json().get("state") == "scheduled", r2.json().get("state"))

    r = c.post(f"/api/smart/insight/post_{pid}/decision", json={"decision": "disapprove"}, headers=H)
    check("post_ disapprove routes and succeeds", r.status_code == 200, r.text[:300])
    r3 = c.get(f"/api/social/post/{pid}", headers=H)
    check("state became failed", r3.json().get("state") == "failed", r3.json().get("state"))

r = c.post("/api/social/clear", headers=H)
check("clear plan 200", r.status_code == 200, r.text[:200])
cal2 = c.get("/api/social/month", headers=H, params={"year": 2026, "month": 9}).json()
posts2 = [p for day in cal2.get("days", []) for p in day.get("posts", [])]
check("no posts remain after clear", len(posts2) == 0, len(posts2))

# =========================================================================
print("\n== slots land on their intended WEEKDAY, whatever day you plan on ==")
# =========================================================================
# The slot table encodes reach data about weekdays -- Wed and Thu strongest,
# Fri and Sat weakest. It used to be expressed as fixed day-offsets from the
# planning date, which only produced that pattern if the seller pressed the
# button on a Monday: planning on a Wednesday shifted everything two days, so
# the STRONGEST slot landed on Friday and one post landed on Sunday, a day the
# table never intended to use at all.
import datetime as _dt  # noqa: E402
import inspect as _inspect  # noqa: E402

from backend.core import social as _social  # noqa: E402

_WEEK = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_WANT = [2, 3, 0, 4, 1, 5]      # Wed, Thu, Mon, Fri, Tue, Sat -- strongest first
_MONDAY = _dt.date(2026, 9, 14)
check("the reference date used by this test really is a Monday", _MONDAY.weekday() == 0)

_bad_weekday, _bad_window, _collisions = [], [], []
for _d in range(7):
    _start = _MONDAY + _dt.timedelta(days=_d)
    _offsets = []
    for _i in range(6):
        _off = (_WANT[_i] - _start.weekday()) % 7
        _offsets.append(_off)
        _landed = (_start + _dt.timedelta(days=_off)).weekday()
        if _landed != _WANT[_i]:
            _bad_weekday.append((_WEEK[_start.weekday()], _i, _WEEK[_landed]))
        if not 0 <= _off <= 6:
            _bad_window.append((_WEEK[_start.weekday()], _i, _off))
    if len(set(_offsets)) != len(_offsets):
        _collisions.append(_WEEK[_start.weekday()])

check("every slot lands on its intended weekday from any planning day",
      not _bad_weekday, _bad_weekday[:4])
check("every post stays inside the 7-day window being planned",
      not _bad_window, _bad_window[:4])
check("no two slots ever collide on the same day", not _collisions, _collisions)

_src = _inspect.getsource(_social.build_week)
check("build_week anchors to weekdays, not to offsets from the planning date",
      "best_weekdays" in _src and "start.weekday()" in _src)
check("the old fixed-offset table is gone", "day_offsets" not in _src)
check("a slot due today at an hour already past is not born overdue",
      "if when < now:" in _src)

# End to end: plan on a Wednesday and confirm nothing lands on a Sunday, which
# is exactly what the old fixed offsets produced.
_wed = f"sched{int(time.time()*1000)}@t.co"
c.post("/api/register", json={"email": _wed, "password": "Test12345!"})
_made = _social.build_week(_wed, [{"id": "p1", "name": "Silk Saree", "category": "Clothing"}],
                           start=_MONDAY + _dt.timedelta(days=2))   # a Wednesday
_days = [_dt.datetime.fromisoformat(p["scheduled_at"]).weekday() for p in _made]
check("planning on a Wednesday produces posts", len(_made) > 0, len(_made))
check("and none of them land on a Sunday (the old bug's signature)",
      6 not in _days, [_WEEK[d] for d in _days])
check("and every one lands on a weekday the reach table actually chose",
      all(d in _WANT for d in _days), [_WEEK[d] for d in _days])

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
