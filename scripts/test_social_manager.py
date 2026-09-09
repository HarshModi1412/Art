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

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
