"""AI labelling, and the gate that stops us removing anybody else's label.

The rule being tested: the Information Technology (Intermediary Guidelines and
Digital Media Ethics Code) Amendment Rules 2026, in force since 20 February
2026. They bind any intermediary "offering computer resources enabling creation
or modification of synthetically generated information", which is what this
platform is. Two duties, and this file checks both as facts rather than as
comments in a docstring:

  1. AI-made pictures and clips must be clearly and prominently labelled, and
     must carry permanent metadata or a provenance identifier that traces the
     computer resource that made them.
  2. The platform must not enable the removal, suppression or modification of
     such a label.

The price of failing either is not a fine in the first instance. It is safe
harbour under section 79 of the IT Act, which is what stands between the
operator and personal liability for everything every seller posts through here.

There is a third thing tested, which is not in the rule but matters as much:
a clip the seller FILMED must not be labelled as AI. A false "AI generated"
stamp on a real photograph of a real product is a misleading claim about goods
under the Consumer Protection Act, and it is the mistake an over-eager
implementation of duty 1 makes.

Run: python3 scripts/test_ai_labelling.py
"""
import importlib
import io
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = FAIL = 0


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        print(f"  ✗ {label}  <-- {extra}")


os.environ.pop("WATERMARK_REMOVAL", None)
from backend.core import ailabel, watermark  # noqa: E402
importlib.reload(ailabel)
importlib.reload(watermark)

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402


def make_png(w=900, h=900, colour=(210, 180, 140)) -> bytes:
    """A plain warm rectangle, standing in for a generated product photo."""
    buf = io.BytesIO()
    Image.new("RGB", (w, h), colour).save(buf, format="PNG")
    return buf.getvalue()


def make_jpeg(w=800, h=800) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (40, 60, 90)).save(buf, format="JPEG", quality=92)
    return buf.getvalue()


# =========================================================================
print("\n== the label is drawn, and it is actually visible ==")
# =========================================================================
src = make_png()
out, rep = ailabel.label_image(src, engine="gemini", model="imagen-4")
check("a generated picture comes back labelled", rep["labelled"] is True, rep)
check("and the bytes changed, so something was really drawn", out != src)
check("the picture is not resized by labelling it",
      Image.open(io.BytesIO(out)).size == Image.open(io.BytesIO(src)).size)

before = np.asarray(Image.open(io.BytesIO(src)).convert("RGB")).astype(int)
after = np.asarray(Image.open(io.BytesIO(out)).convert("RGB")).astype(int)
diff = np.abs(after - before).sum(axis=2)
changed = diff > 12
check("pixels changed in the bottom-left corner, where the label goes",
      changed[-200:, :340].sum() > 400, changed[-200:, :340].sum())
check("and nowhere else, so the product itself is untouched",
      changed[:-220, :].sum() == 0 and changed[:, 400:].sum() == 0,
      f"top={changed[:-220, :].sum()} right={changed[:, 400:].sum()}")

# "Clearly and prominently" is not satisfied by grey-on-grey, so the contrast is
# computed rather than eyeballed. The worst case for a translucent plate is a
# pure WHITE picture behind it, so that is the case measured, using the WCAG
# formula. Anything at or above 4.5:1 is legible as body text; the label is bold
# and large, where 3:1 is the bar.
def _lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _ratio(a, b):
    def rl(rgb):
        r, g, bl = (_lin(x) for x in rgb)
        return 0.2126 * r + 0.7152 * g + 0.0722 * bl
    la, lb = rl(a), rl(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


white_bg, wrep_lab = ailabel.label_image(make_png(600, 600, (255, 255, 255)))
warr = np.asarray(Image.open(io.BytesIO(white_bg)).convert("RGB")).astype(int)
plate_px = warr[-120:, :240].reshape(-1, 3)
# The plate colour is the darkest thing in that corner; the text is the lightest.
darkest = tuple(int(x) for x in plate_px[plate_px.sum(axis=1).argmin()])
contrast = _ratio((255, 255, 255), darkest)
check("over a pure white photo, the worst case, the plate still darkens the corner",
      sum(darkest) / 3 < 110, darkest)
check(f"and white text on it clears 4.5:1 ({contrast:.1f}:1)", contrast >= 4.5,
      f"{contrast:.2f}:1 on {darkest}")
corner = after[-160:, :320]
check("there is white text on that plate", corner.max() > 220, corner.max())
h, w = changed.shape
lab_area = changed[-200:, :340].sum()
check("the label is big enough to see but does not take over the picture",
      0.001 < lab_area / (h * w) < 0.06, lab_area / (h * w))

# The size rule matters because a fixed 14px label on a 2048px render is a dot.
small, _ = ailabel.label_image(make_png(320, 320))
big, _ = ailabel.label_image(make_png(1600, 1600))


def label_height(labelled: bytes, plain: bytes) -> int:
    a = np.asarray(Image.open(io.BytesIO(labelled)).convert("RGB")).astype(int)
    b = np.asarray(Image.open(io.BytesIO(plain)).convert("RGB")).astype(int)
    rows = np.where(np.abs(a - b).sum(axis=2).sum(axis=1) > 0)[0]
    return int(rows.max() - rows.min() + 1) if len(rows) else 0


hs, hb = label_height(small, make_png(320, 320)), label_height(big, make_png(1600, 1600))
check("the label scales with the picture rather than being a fixed dot",
      hb > hs * 1.8, f"{hs}px on 320, {hb}px on 1600")
check("and it is never smaller than a legible size", hs >= 14, hs)

# =========================================================================
print("\n== the provenance metadata the rule asks for ==")
# =========================================================================
got = ailabel.read_provenance(out)
check("the record can be read back out of the PNG", bool(got), got)
check("it carries a unique identifier for this exact generation",
      len(got.get("gen_id", "")) >= 16, got.get("gen_id"))
check("which is the same id the caller was told",
      got.get("gen_id") == rep["gen_id"])
check("it names the engine that made the picture", got.get("engine") == "gemini")
check("and the model, so the computer resource is traceable",
      got.get("model") == "imagen-4")
check("it names this platform", got.get("platform") == ailabel.PLATFORM)
check("it is timestamped in UTC", got.get("created_utc", "").endswith("+00:00"))
check("and it states plainly that the file is AI made",
      "artificial intelligence" in got.get("notice", "").lower())
check("the notice cites the rule it is complying with",
      "Intermediary Guidelines" in got.get("notice", ""))

im = Image.open(io.BytesIO(out))
check("a human opening the file properties sees a plain-English line",
      "AI generated" in (im.info or {}).get("Description", ""))
check("and a machine-readable copy sits alongside it",
      "ai-provenance" in (im.info or {}))
check("two generations get two different identifiers",
      ailabel.label_image(src)[1]["gen_id"] != ailabel.label_image(src)[1]["gen_id"])

jpg_out, jrep = ailabel.label_image(make_jpeg(), engine="openai", model="gpt-image-1")
check("a JPEG is labelled too", jrep["labelled"] is True, jrep)
check("and stays a JPEG rather than being silently turned into a PNG",
      Image.open(io.BytesIO(jpg_out)).format == "JPEG")
check("with its record in EXIF, which is where a JPEG keeps one",
      jrep["metadata"] is True)
jgot = ailabel.read_provenance(jpg_out)
check("and that record reads back", jgot.get("engine") == "openai", jgot)

# =========================================================================
print("\n== labelling never costs the seller their picture ==")
# =========================================================================
bad, brep = ailabel.label_image(b"this is not an image at all")
check("rubbish in comes back unchanged rather than raising",
      bad == b"this is not an image at all")
check("and is reported as unlabelled, so a caller can refuse it",
      brep["labelled"] is False and brep["reason"])
check("a font is always found, so the label cannot silently fail to draw",
      ailabel._font(20) is not None)

# =========================================================================
print("\n== the remover is off, and cannot be reached by any route ==")
# =========================================================================
check("removal is off unless the deployment opts in",
      ailabel.removal_enabled() is False)
check("and the health report treats that as the compliant state",
      ailabel.compliance_state()["ok"] is True)

data, wrep = watermark.clean_image(make_png())
check("clean_image refuses and says it is the law",
      wrep.get("blocked_by_law") is True and wrep["removed"] is False)
check("returning the original bytes untouched", data == make_png())
check("the reason names the rule rather than looking like a bug",
      "20 February 2026" in wrep["reason"])
check("and tells the seller the lawful way to get a clean frame",
      "Media Watermark" in wrep["reason"])

vdata, vrep = watermark.clean_video_bytes(b"not really a video", "clip.mp4")
check("clean_video_bytes refuses as well",
      vrep.get("blocked_by_law") is True and vdata == b"not really a video")
murl = watermark.clean_media_url("/media/whatever.png", "a@b.in")
check("and so does the stored-media route",
      murl["report"].get("blocked_by_law") is True)

caps = watermark.capabilities()
check("the UI is told there is nothing to offer",
      caps["images"] is False and caps["videos"] is False)
check("so a seller is never shown a button that changes no pixel",
      caps.get("removal_enabled") is False)

# The gate has to be one function, or the next entry point forgets it.
import inspect  # noqa: E402
_src = inspect.getsource(watermark)
check("every public entry point goes through the one gate",
      _src.count("_removal_allowed()") >= 4, _src.count("_removal_allowed()"))
check("and the gate fails closed if the switch cannot be read",
      "return False" in _src.split("def _removal_allowed")[1][:400])

# =========================================================================
print("\n== switching it on is a launch blocker, not a preference ==")
# =========================================================================
os.environ["WATERMARK_REMOVAL"] = "on"
importlib.reload(ailabel)
check("the switch does work, so this is a decision and not a dead feature",
      ailabel.removal_enabled() is True)
check("but the compliance state turns false",
      ailabel.compliance_state()["ok"] is False)
check("and says how to undo it", "Unset WATERMARK_REMOVAL" in
      ailabel.compliance_state()["note"])

os.environ.update({
    "LEGAL_NAME": "T", "BUSINESS_ADDRESS": "A", "SUPPORT_EMAIL": "a@b.in",
    "SUPPORT_PHONE": "9", "GRIEVANCE_NAME": "T", "GRIEVANCE_EMAIL": "g@b.in"})
from backend.core import health, legal  # noqa: E402
importlib.reload(legal)
_h = health.report()
check("the health report BLOCKS the deployment while it is on",
      any("watermark remover is switched on" in b for b in _h["blockers"]),
      _h["blockers"])
check("and says it costs safe harbour, so the reason is not a mystery",
      any("safe harbour" in b for b in _h["blockers"]))
check("the state is reported in full, not only as a blocker line",
      _h["ai_label"]["removal_enabled"] is True)

os.environ.pop("WATERMARK_REMOVAL", None)
importlib.reload(ailabel)
check("switching it back off clears the blocker",
      not any("watermark remover" in b for b in health.report()["blockers"]))

# =========================================================================
print("\n== a clip the seller filmed is NOT labelled as AI ==")
# =========================================================================
from fastapi.testclient import TestClient  # noqa: E402
from backend.main import app  # noqa: E402
from backend.core import social  # noqa: E402
import uuid as _uuid  # noqa: E402

c = TestClient(app)
EM = f"ailabel-{_uuid.uuid4().hex[:8]}@test.co"
tok = c.post("/api/register", json={"email": EM, "password": "pw123456"}).json()["token"]
H = {"Authorization": "Bearer " + tok, "X-Session-Id": "ail"}

c.post("/api/products/item", headers=H,
       json={"name": "Leather wallet", "category": "Accessories", "price": 1499, "stock": 8})
plan = c.post("/api/social/week", headers=H, json={}).json()
posts = plan.get("posts") or c.get("/api/social", headers=H).json().get("posts") or []
reel = next((p for p in posts if p.get("format") == "reel"), posts[0] if posts else None)
check("there is a post to attach a clip to", reel is not None)

if reel:
    # Store a small file through the app's own upload so the media store has it.
    up = c.post("/api/site/image", headers=H,
                files={"files": ("clip.png", make_png(200, 200), "image/png")})
    url = (up.json() or {}).get("url") or (up.json() or {}).get("image_url")
    check("a file can be stored to attach", bool(url), up.text[:160])

    r = c.post("/api/social/attach-video", headers=H,
               json={"post_id": reel["id"], "url": url, "ai_generated": False})
    check("attaching a FILMED clip succeeds", r.status_code == 200, r.text[:160])
    j = r.json()
    check("and nothing labelled it as AI",
          not (j.get("ai_label") or {}).get("labelled"), j.get("ai_label"))
    check("the stored file is the one uploaded, not a re-encoded copy",
          j.get("video_url") == url)

    r = c.post("/api/social/attach-video", headers=H,
               json={"post_id": reel["id"], "url": url, "ai_generated": True})
    check("attaching an AI-MADE clip succeeds", r.status_code == 200, r.text[:160])
    j = r.json()
    lab = j.get("ai_label") or {}
    # An image standing in for a clip labels through the image path, which is the
    # honest outcome: the file is labelled, and no ffmpeg was needed for a PNG.
    check("and it was labelled", lab.get("labelled") is True, lab)
    check("with a traceable reference id", len(lab.get("gen_id", "")) >= 16)
    check("the labelled copy is saved under a new name",
          j.get("video_url") and j["video_url"] != url)
    check("and the original upload is kept, so a wrong answer can be undone",
          j.get("video_original_url") == url)

    post = social.get_post(EM, reel["id"])
    check("the label is recorded on the post, not just in the response",
          (post.get("video_ai_label") or {}).get("labelled") is True)
    check("so reopening the post a week later still says so",
          (post.get("video_ai_label") or {}).get("gen_id") == lab["gen_id"])

    # The old "still see a watermark" button must not lie.
    r = c.post("/api/social/reclean-video", headers=H,
               json={"post_id": reel["id"], "corner": "bottom-right"})
    check("the old remove-watermark route now refuses", r.status_code == 400, r.status_code)
    check("and explains the lawful alternative rather than failing blankly",
          "Media Watermark" in r.text and "Settings" in r.text, r.text[:200])
    check("naming the rule, so it does not read as a bug",
          "20 February 2026" in r.text)

# =========================================================================
print("\n== the UI cannot offer what the server refuses ==")
# =========================================================================
import pathlib  # noqa: E402
ROOT = pathlib.Path(__file__).resolve().parent.parent
JS = (ROOT / "Smart CafeX/smart.js").read_text(encoding="utf-8")
check("the four corner buttons are gone from the interface",
      "data-wmcorner" not in JS)
check("and the reclean endpoint is no longer called from anywhere",
      "reclean-video" not in JS)
check("the seller is told to switch Flow's own watermark off instead",
      "Media Watermark" in JS)
check("the reel upload declares the clip as AI made, since Flow made it",
      "attachClip(post.id, u, true)" in JS)
check("the post editor asks first, because a clip there could be either",
      "askClipOrigin" in JS)
check("and offers both answers plainly",
      "I filmed it myself" in JS and "An AI tool made it" in JS)
check("the seller's own uploaded photo is never labelled as AI",
      "would be a false claim about their own goods" in JS)

# =========================================================================
print("\n== studio hands back the label with the picture ==")
# =========================================================================
from backend.core import studio  # noqa: E402
_ssrc = inspect.getsource(studio)
check("the image path labels before it saves",
      "ailabel.label_image(content" in _ssrc)
check("and the label goes on AFTER the brand plate, so neither covers the other",
      _ssrc.index("_stamp_brand(content") < _ssrc.index("ailabel.label_image(content"))
check("the clip path labels too", "ailabel.label_video_bytes(data" in _ssrc)
check("and both report it to the caller", _ssrc.count('"ai_label": label_report') == 2)

# =========================================================================
print("\n== video labelling, where ffmpeg allows it ==")
# =========================================================================
ff = watermark.ffmpeg_exe()
if not ff:
    print("  (skipped: no ffmpeg on this machine)")
else:
    import tempfile
    d = tempfile.mkdtemp(prefix="ailab-test-")
    src_v, dst_v = os.path.join(d, "in.mp4"), os.path.join(d, "out.mp4")
    subprocess.run([ff, "-y", "-f", "lavfi", "-i", "color=c=teal:s=480x480:d=1",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", src_v],
                   capture_output=True, timeout=180)
    check("a test clip was made", os.path.exists(src_v) and os.path.getsize(src_v) > 0)
    vr = ailabel.label_video_file(src_v, dst_v, engine="flow", model="veo-3")
    check("the clip is labelled", vr["labelled"] is True, vr.get("reason"))
    check("and a real file comes out", os.path.getsize(dst_v) > 0)
    probe = subprocess.run([ff, "-i", dst_v], capture_output=True, timeout=60)
    err = (probe.stderr or b"").decode("utf-8", "replace")
    check("the provenance is written into the container's metadata",
          "ai_provenance" in err or "comment" in err.lower(), err[-200:])
    check("the clip is still H.264, so it plays in every browser", "h264" in err)
    check("and still 480x480, not re-framed", "480x480" in err)
    for f in (src_v, dst_v):
        try:
            os.unlink(f)
        except OSError:
            pass
    os.rmdir(d)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
