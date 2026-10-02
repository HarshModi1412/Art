"""
Guard for "Approve all only approves one at a time".

The seller pressed Approve all, every card left, and then all but one came
back; it took as many presses as there were posts. The browser sends the
approvals two at a time, each one spends seconds drawing a picture, and each
request saved the seller's WHOLE state from the copy it read when it started
(user_store memoises state per request). The last one to finish wrote every
other post back to draft. The same lost update hit tasks, decisions and any
key two requests touched at once.

Run: python3 scripts/test_concurrent_approve.py
"""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import main  # noqa: E402
from backend.core import social, studio, user_store  # noqa: E402

PASS = FAIL = 0


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}{(' (' + str(extra) + ')') if extra else ''}")
    else:
        FAIL += 1
        print(f"  ✗ {label}  <-- {extra}")


def as_request(fn, *a):
    """Run fn the way the server runs an endpoint: inside its own state scope."""
    with user_store.request_scope():
        return fn(*a)


def seed(email, n):
    posts = [{"id": f"p{i}", "state": "draft", "format": "image", "product_id": "",
              "product_name": f"Item {i}", "pillar": "detail",
              "scheduled_at": "2030-01-0%dT10:00:00" % (i + 1)} for i in range(n)]
    user_store.set_key(email, social.POSTS_KEY, posts)


def slow_picture(*a, **k):
    time.sleep(0.4)        # an AI picture on a small server takes seconds
    return {"url": f"/media/x{time.time_ns()}.png", "prompt": "p"}


studio.generate_image_only = slow_picture

print("\n== 1. two approvals at once both stick ==")
email = f"cc{int(time.time() * 1000)}@t.co"
seed(email, 2)
ts = [threading.Thread(target=as_request, args=(main._approve_post_ready, email, f"p{i}"))
      for i in range(2)]
[t.start() for t in ts]
[t.join() for t in ts]
states = {p["id"]: p.get("state") for p in social._posts(email)}
check("both posts are scheduled", all(s == "scheduled" for s in states.values()), states)
check("both kept their picture", all(p.get("image_url") for p in social._posts(email)))

print("\n== 2. Approve all on six, two lanes, like the browser does ==")
email = f"cc{int(time.time() * 1000) + 1}@t.co"
seed(email, 6)
queue = [f"p{i}" for i in range(6)]
lock = threading.Lock()


def lane():
    while True:
        with lock:
            if not queue:
                return
            pid = queue.pop(0)
        as_request(main._approve_post_ready, email, pid)


ts = [threading.Thread(target=lane) for _ in range(2)]
[t.start() for t in ts]
[t.join() for t in ts]
states = [p.get("state") for p in social._posts(email)]
check("all six are scheduled after one press", states.count("scheduled") == 6, states)

print("\n== 3. different keys written at once do not erase each other ==")
email = f"cc{int(time.time() * 1000) + 2}@t.co"
user_store.set_key(email, "a", 0)
user_store.set_key(email, "b", 0)


def slow_set(key):
    user_store.get_key(email, "a")   # the request reads state first...
    time.sleep(0.3)                  # ...does slow work...
    user_store.set_key(email, key, 1)  # ...then writes one key


ts = [threading.Thread(target=as_request, args=(slow_set, k)) for k in ("a", "b")]
[t.start() for t in ts]
[t.join() for t in ts]
st = user_store.load_state(email)
check("both writes survive", st.get("a") == 1 and st.get("b") == 1, {"a": st.get("a"), "b": st.get("b")})

print("\n== 4. a request still sees its own writes ==")
email = f"cc{int(time.time() * 1000) + 3}@t.co"


def own_write():
    user_store.set_key(email, "x", 5)
    return user_store.get_key(email, "x")


check("read-after-write inside one request", as_request(own_write) == 5)

print("\n== 5. the merge rules themselves ==")
M, X = user_store._merge_value, user_store._MISSING
check("nobody else wrote: ours wins outright", M([1], [2], [1]) == [2])
check("never read: ours wins (old behaviour)", M(X, {"a": 1}, {"b": 2}) == {"a": 1})
check("dict: each side keeps the sub-key it changed",
      M({"a": 0, "b": 0}, {"a": 1, "b": 0}, {"a": 0, "b": 2}) == {"a": 1, "b": 2})
check("dict: our delete sticks, their delete sticks",
      M({"a": 0, "b": 0}, {"b": 0}, {"a": 0}) == {})
base = [{"id": 1, "s": "d"}, {"id": 2, "s": "d"}]
check("records: each side keeps the record it changed",
      M(base, [{"id": 1, "s": "ok"}, {"id": 2, "s": "d"}],
        [{"id": 1, "s": "d"}, {"id": 2, "s": "ok"}]) == [{"id": 1, "s": "ok"}, {"id": 2, "s": "ok"}])
check("records: ours added, theirs added, both kept",
      [r["id"] for r in M(base, base + [{"id": 3}], base + [{"id": 4}])] == [1, 2, 4, 3])
check("records: a record we removed stays removed",
      [r["id"] for r in M(base, base[:1], base + [{"id": 4}])] == [1, 4])
check("not records (duplicate ids): last writer",
      M([{"id": 1}], [{"id": 1}, {"id": 1}], [{"id": 2}]) == [{"id": 1}, {"id": 1}])

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
