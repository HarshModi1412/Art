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
JS = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "Smart CafeX", "smart.js"), encoding="utf-8").read()
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

print("\n== 'Still see a watermark? Show us where' ==")
import cv2  # noqa: E402
import tempfile  # noqa: E402
Wv, Hv = 720, 1280
yy, xx = np.mgrid[0:Hv, 0:Wv].astype(np.float32)
sz, mg = int(Wv * 0.045), int(Wv * 0.035)
cx, cy = Wv - mg - sz // 2, Hv - mg - sz // 2
spark = ((np.abs(xx - cx) / (sz / 2)) ** 0.7 + (np.abs(yy - cy) / (sz / 2)) ** 0.7) <= 1.0
bg = np.clip(np.stack([90 + 60 * xx / Wv, 70 + 40 * yy / Hv, 60 + 30 * np.sin(xx / 37.0)], axis=2), 0, 255)
fr = bg.copy()
fr[spark] = fr[spark] * 0.65 + 255 * 0.35                  # faint: the automatic pass leaves it
fr = fr.astype(np.uint8)
tmpd = tempfile.mkdtemp()
vp = os.path.join(tmpd, "faint.mp4")
vw = cv2.VideoWriter(vp, cv2.VideoWriter_fourcc(*"mp4v"), 24, (Wv, Hv))
for _ in range(30):
    vw.write(cv2.cvtColor(fr, cv2.COLOR_RGB2BGR))
vw.release()
up = c.post("/api/site/image", headers=H, files={"files": ("faint.mp4", open(vp, "rb").read(), "video/mp4")})
orig_url = up.json()["url"]
# This section used to prove that pointing at a corner rubbed a faint mark out.
# On 15 September 2026 that feature was switched off: the IT Rules as amended on
# 20 February 2026 forbid a platform offering AI generation from enabling the
# removal of an AI label, and the cost of breaking that is safe harbour under
# section 79 of the IT Act. What is checked now is that the refusal is HONEST,
# because a button that reports success and changes nothing is the worse failure.
r = c.post("/api/social/attach-video", headers=H,
           json={"post_id": reel["id"], "url": orig_url, "ai_generated": True})
post = social.get_post(email, reel["id"])
check("the post remembers the original upload",
      post.get("video_original_url") == orig_url, post.get("video_original_url"))
check("and that the AI label went on, with its reference id",
      (post.get("video_ai_label") or {}).get("labelled") is True
      and len((post.get("video_ai_label") or {}).get("gen_id") or "") >= 16,
      post.get("video_ai_label"))
labelled_url = r.json()["video_url"]
check("the post carries the labelled copy, the original kept",
      labelled_url != orig_url and post.get("video_original_url") == orig_url)

r = c.post("/api/social/reclean-video", headers=H,
           json={"post_id": reel["id"], "corner": "bottom-right"})
check("asking us to remove another tool's mark is refused outright",
      r.status_code == 400, r.status_code)
check("the refusal names the rule, so it does not read as a bug",
      "20 February 2026" in r.text)
check("and tells the seller how to get the clean frame legitimately",
      "Media Watermark" in r.text and "Settings" in r.text, r.text[:160])
check("the clip on the post is untouched by the refusal",
      social.get_post(email, reel["id"])["video_url"] == labelled_url)
check("the corner buttons are gone from the interface entirely",
      "data-wmcorner" not in JS and "/api/social/reclean-video" not in JS)
check("and the instruction to switch Flow's own mark off is there instead",
      JS.count('wmFixRow("') == 2 and "Media Watermark" in JS)

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

check("the app retries the attach without cleaning when cleaning fails",
      "async function attachClip" in JS and "clean: false" in JS)

print("\n== a phone photo is made fit to serve ==")
# A seller uploads what came off their phone: around 4000px and several
# megabytes. It used to be stored and served exactly as it arrived, to every
# shopper, on a mobile connection, for a card displayed 400px wide. That is the
# single largest thing on a storefront's loading time, and the shopper pays for
# it in data as well as in waiting.
import io as _io  # noqa: E402
from PIL import Image as _Image  # noqa: E402
from backend.core import media as _media  # noqa: E402

_arr = np.random.default_rng(11).integers(0, 255, (2400, 3200, 3)).astype("uint8")
_buf = _io.BytesIO()
_Image.fromarray(_arr).save(_buf, format="JPEG", quality=95)
_raw = _buf.getvalue()
check("the test photo really is a big one", len(_raw) > 3 * 1024 * 1024,
      f"{len(_raw) // 1024}KB")

_up = c.post("/api/site/image", headers=H,
             files={"files": ("phone.jpg", _raw, "image/jpeg")})
check("it uploads", _up.status_code == 200, _up.text[:120])
_j = _up.json()
_comp = _j.get("compression") or {}
check("and is reported as shrunk, so the seller is not left wondering",
      _comp.get("bytes", 0) < _comp.get("original_bytes", 1), _comp)
check("to under a megabyte", _comp.get("bytes", 10**9) < 1024 * 1024,
      f"{_comp.get('bytes', 0) // 1024}KB")
check("with the reason in plain numbers", "KB to " in _comp.get("reason", ""),
      _comp.get("reason"))

_served = c.get(_j["url"])
check("what a shopper downloads is the small one", len(_served.content) < 1024 * 1024,
      f"{len(_served.content) // 1024}KB")
check("and it is still the right picture, at a sane size",
      max(_Image.open(_io.BytesIO(_served.content)).size) == 1600,
      _Image.open(_io.BytesIO(_served.content)).size)

# What it must NOT do, which matters as much.
_small = _io.BytesIO()
_Image.new("RGB", (300, 300), (200, 170, 130)).save(_small, format="JPEG", quality=90)
_, _, _r = _media.compress_upload(_small.getvalue(), "small.jpg")
check("a small photo is left exactly as it is", "already small" in _r["reason"])
_png = _io.BytesIO()
_Image.new("RGBA", (2000, 2000), (10, 20, 30, 255)).save(_png, format="PNG")
_o, _n, _r = _media.compress_upload(_png.getvalue(), "logo.png")
check("a logo with transparency stays a PNG, because flattening it onto white "
      "is a visible defect on a dark theme", _n.endswith(".png"))
check("a GIF is never touched, since it may be animated",
      _media.compress_upload(b"GIF89a...", "a.gif")[2]["reason"].startswith("left as it is"))
check("nor an SVG, which is text",
      _media.compress_upload(b"<svg/>", "a.svg")[2]["reason"].startswith("left as it is"))
_bad, _, _r = _media.compress_upload(b"not an image at all", "x.jpg")
check("a file it cannot read is stored as it came, never lost",
      _bad == b"not an image at all" and "could not process" in _r["reason"])
_vid = _media.compress_upload(b"\x00\x00\x00 ftypmp42", "clip.mp4")
check("and a video is left to the video path", _vid[2]["reason"] == "video, not touched here")

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
