"""
Uploading a reel clip on the live server: what used to break, and what now
happens instead.

  * the watermark pass ran inside the web server and a 1080p reel took more
    memory than the host had — the server died, every seller saw a 502;
  * after that, the upload still ended in a 500 with only a reference number,
    which nobody without the admin token could look up.

Run: python3 scripts/test_upload_resilience.py
"""
import math
import os
import sys
import time

os.environ.setdefault("AUTOPLAN_SCHEDULER", "off")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from backend.core import errors, smart, social, user_store  # noqa: E402

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
email = f"up{int(time.time() * 1000)}@t.co"
tok = c.post("/api/register", json={"email": email, "password": "Test12345!"}).json()["token"]
H = {"Authorization": "Bearer " + tok, "X-Session-Id": "up"}
c.post("/api/products/item", headers=H, json={"name": "Gucci Bag", "category": "Bags",
                                              "price": 4999, "stock": 10})
week = c.post("/api/social/week", headers=H, json={}).json().get("posts") or []
reel = next((p for p in week if p.get("format") == "reel"), None)
if reel is None:                       # make one a reel so the test has one
    reel = week[0]
    social.update_post(email, reel["id"], {"format": "reel"})
r = c.post("/api/social/approve-ready", headers=H, json={"post_id": reel["id"], "generate": False})
check("an approved reel with its task", r.status_code == 200
      and any(t.get("post_id") == reel["id"] for t in smart.get_tasks(email)), r.text[:200])

# a tiny clip, stored the way the app stores uploads
clip = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 2048
up = c.post("/api/site/image", headers=H, files={"files": ("clip.mp4", clip, "video/mp4")})
url = up.json().get("url")
check("the upload is stored", up.status_code == 200 and url, up.text[:200])

print("\n== the clip is attached even when the bookkeeping after it fails ==")
_real = smart.task_progress


def _boom(*a, **k):
    raise RuntimeError("task store unavailable")


smart.task_progress = _boom
r = c.post("/api/social/attach-video", headers=H, json={"post_id": reel["id"], "url": url, "clean": False})
smart.task_progress = _real
check("attach answers 200", r.status_code == 200, r.text[:300])
check("and the clip is on the post", social.get_post(email, reel["id"]).get("video_url") == url)

print("\n== a real failure says where it happened ==")
_real_attach = social.attach_video


def _bad(*a, **k):
    return {}["no such key"]


social.attach_video = _bad
r = c.post("/api/social/attach-video", headers=H, json={"post_id": reel["id"], "url": url, "clean": False})
social.attach_video = _real_attach
d = r.json()
check("still a readable 500", r.status_code == 500 and "Something went wrong" in d.get("detail", ""), d)
check("naming the exception, the endpoint's line and the line it broke on",
      "KeyError at main.py:" in d.get("detail", "") and "→ test_upload_resilience.py:" in d.get("detail", "")
      and d.get("location", "").startswith("KeyError at main.py:"), d)
check("and nothing from the request itself", url not in d.get("detail", ""))

from backend.core import mapper  # noqa: E402
try:
    mapper.build_transactions(None, {})
except Exception as e:  # noqa: BLE001
    loc = errors.location(e)
check("a failure inside our code names the line", " at mapper.py:" in loc, loc)

print("\n== NaN / Infinity never reach Postgres ==")
dirty = {"a": float("nan"), "b": [1.5, float("inf"), {"c": -math.inf}], "d": np.float64(2.5),
         "e": np.int64(3), "f": np.float32("nan"), "g": "text", "h": None, "i": True}
clean = user_store._jsonb_safe(dirty)
check("NaN and ±Infinity become null, anywhere in the state",
      clean["a"] is None and clean["b"][1] is None and clean["b"][2]["c"] is None and clean["f"] is None, clean)
check("numpy numbers become plain ones, everything else is kept",
      clean["d"] == 2.5 and type(clean["d"]) is float and clean["e"] == 3 and type(clean["e"]) is int
      and clean["g"] == "text" and clean["h"] is None and clean["i"] is True, clean)
import json as _json  # noqa: E402
check("the result is valid JSON for JSONB", _json.dumps(clean, allow_nan=False))

JS = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "Smart CafeX", "smart.js"), encoding="utf-8").read()
check("the app retries the attach without cleaning when cleaning fails",
      "async function attachClip" in JS and "clean: false" in JS)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
