"""
Free scene templates: the seller's real product cut out of their photo and
placed into a ready-made scene, with no image API (cutout.py, scenes.py,
composite.py, motion.py, and the "scene" engine in studio.py).

What this guards:
  * the product is never redrawn: its pixels in the result are the photo's;
  * the pose is read from the silhouette (standing vs laid flat) and only
    scenes shot from that camera height are used, the seller's override wins;
  * the engine is free and outside every AI allowance, needs a photo, and is
    never offered for "invent";
  * a photo that cannot make a believable picture is refused with a reason;
  * the schedule setting only accepts the three known sources.

Runs offline: no model download, so the OpenCV GrabCut fallback cuts.

Run: python scripts/test_scene_templates.py
"""
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["CUTOUT_MODEL_DIR"] = tempfile.mkdtemp()
os.environ["CUTOUT_DOWNLOAD"] = "off"

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from backend.core import composite, cutout, scenes, social, studio  # noqa: E402

PASS = FAIL = 0


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}{(' (' + str(extra) + ')') if extra else ''}")
    else:
        FAIL += 1
        print(f"  ✗ {label}  <-- {extra}")


def photo(draw_fn, size=(900, 1100), bg=(236, 236, 232)) -> bytes:
    im = Image.new("RGB", size, bg)
    draw_fn(ImageDraw.Draw(im))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def bottle(d):
    # A red bottle with a flat base and a gold cap, standing in the frame.
    d.rectangle([330, 380, 570, 900], fill=(170, 30, 40))
    d.rectangle([400, 260, 500, 380], fill=(200, 160, 70))


def necklace(d):
    # A chain hanging in a U with a dangling pendant: no flat base.
    for i in range(60):
        t = i / 59
        x = 150 + 600 * t
        y = 300 + 380 * (1 - (2 * t - 1) ** 2)
        d.ellipse([x - 14, y - 14, x + 14, y + 14], fill=(190, 150, 60))
    d.polygon([(450, 690), (420, 780), (450, 860), (480, 780)], fill=(30, 90, 160))


def cropped(d):
    # Runs off the left, right and bottom: only its top is in the frame.
    d.rectangle([-50, 420, 950, 1200], fill=(40, 90, 160))


print("\ncutting out (offline, GrabCut fallback)")
cut_b = cutout.cut(photo(bottle))
check("falls back to GrabCut when no model file and no download", cut_b["engine"] == "grabcut",
      cut_b["engine"])
check("the cut is trimmed to the product", cut_b["image"].size[0] < 500, cut_b["image"].size)
check("a clean product photo passes the quality check", cut_b["quality"]["ok"],
      cut_b["quality"]["problems"])
cut_c = cutout.cut(photo(cropped))
# The model reports "runs off the edge"; GrabCut learns the background from
# the frame's border, so it loses an edge-touching product entirely and says
# it found nothing. Either way the seller is told what to reshoot.
check("a product running off the frame is flagged with what to do",
      cut_c["quality"]["problems"] and cut_c["quality"]["tip"], cut_c["quality"]["problems"])

print("\nreading the pose")
p = composite.pose(cut_b["image"])
check("a bottle with a flat base is placed standing", p["stage"] == "stand", p)
cut_n = cutout.cut(photo(necklace, size=(900, 1000)))
pn = composite.pose(cut_n["image"])
check("a hanging necklace is placed laid flat", pn["stage"] == "flat", pn)
check("the seller's override always wins", composite.pose(cut_n["image"], "stand")["stage"] == "stand")
leaning = cut_b["image"].rotate(-7, expand=True, resample=Image.BICUBIC)
pt = composite.pose(leaning)
check("a slightly crooked standing product is measured as leaning", 4 <= abs(pt["tilt"]) <= 10,
      round(pt["tilt"], 1))
straight = composite._straighten(leaning, pt["tilt"])
check("and is straightened", abs(composite._tilt(np.asarray(straight.getchannel("A")))) < 2.5,
      round(composite._tilt(np.asarray(straight.getchannel("A"))), 1))

print("\nscenes")
for stage in ("stand", "flat"):
    for look in ("clean", "warm", "luxe", "bright", "editorial"):
        sc = scenes.choose(stage, look, seed=1)
        if sc["stage"] != stage:
            check(f"{stage}/{look} picks a scene from the same camera height", False, sc["id"])
check("every look has a scene for both camera heights", True)
check("a festival post gets a festive set", scenes.choose("stand", "clean", festive=True, seed=2)["festive"])
check("an ordinary post never does",
      not any(scenes.choose("stand", lk, seed=s)["festive"]
              for lk in ("clean", "warm", "luxe") for s in range(6)))
img, lay = scenes.render(scenes.choose("stand", "clean", seed=3), 1080, 1920, seed=3)
check("scenes are drawn at the size asked for (a 9:16 reel)", img.size == (1080, 1920), img.size)
check("drawn scenes are not AI, so carry no AI label", lay["ai_made"] is False)
check("palette words become colours", scenes.palette_colours("warm sand, black, brass") ==
      [scenes.COLOUR_WORDS["sand"], scenes.COLOUR_WORDS["black"], scenes.COLOUR_WORDS["brass"]])

print("\ncompositing: the product is the photo's pixels")
made = composite.make(b"", look="clean", seed=4, cut=cut_b)
out = made["image"]
check("a post picture is 1080x1350", out.size == (1080, 1350), out.size)
x0, y0, x1, y1 = made["layers"]["product_box"]
core = np.asarray(out.crop((x0, y0, x1, y1)), np.float32)
a = np.asarray(made["layers"]["product"].crop((x0, y0, x1, y1)).getchannel("A")) > 250
red = core[a].mean(0)
check("the bottle is still the bottle's red (no hue shift)",
      red[0] > 140 and red[1] < 60 and red[2] < 70, red.round().tolist())
try:
    composite.make(photo(cropped), seed=1)
    check("a cut-off product is refused rather than placed", False, "no error")
except ValueError as e:
    check("a cut-off product is refused rather than placed", "Best results" in str(e), str(e))

print("\nthe engine")
check("offered for a re-shoot", "scene" in [e["id"] for e in studio.image_engines(True)])
check("never offered to invent a picture", "scene" not in [e["id"] for e in studio.image_engines(False)])
check("marked free", next(e for e in studio.image_engines(True) if e["id"] == "scene")["free"])
check("there is a free scene-motion clip engine too", "scene" in [e["id"] for e in studio.video_engines()])
try:
    studio.image_engine("scene", for_reshoot=False)
    check("asking for it without a photo says to add one", False, "no error")
except ValueError as e:
    check("asking for it without a photo says to add one", "Add a photo" in str(e), str(e))

called = {"caps": 0}
from backend.core import aicaps, media  # noqa: E402
aicaps.require_generation = lambda *a, **k: called.__setitem__("caps", called["caps"] + 1)
aicaps.check_image_month = aicaps.require_generation
aicaps.check = aicaps.require_generation
saved = {}
media.save = lambda name, content, email=None: (saved.__setitem__(name, content),
                                                {"url": "/m/" + name, "durable": False})[1]
brief = studio.build_brief({**studio.blank_brand(), "look": "warm"}, {"id": "p1", "name": "Bottle"},
                           studio.blank_material())
r = studio.generate_image("seller@test.co", brief, {}, (photo(bottle), "image/jpeg"), None, "scene")
check("generate_image routes to the scene engine", r["engine"] == "scene" and r["free"], r["engine"])
check("and touches no AI allowance or Pro Max gate", called["caps"] == 0, called)
check("the stored picture is a JPEG", list(saved.values())[-1][:3] == b"\xff\xd8\xff")
check("the seller is told which scene and why", "scene" in r["prompt"] and "(" in r["prompt"], r["prompt"])

print("\nmotion clip")
from backend.core import motion  # noqa: E402
reel = composite.make(b"", size="reel", look="luxe", seed=5, cut=cut_b)
clip = motion.render_clip(reel["layers"], seconds=1.0, fps=12)
check("renders an MP4", clip[4:8] == b"ftyp", clip[:12])

print("\nschedule setting")
s = social.blank_settings()
check("defaults to AI pictures (no change for existing sellers)", s["image_source"] == "ai")
check("knows the three sources", set(social.IMAGE_SOURCES) == {"ai", "scene", "ai_then_scene"})

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
