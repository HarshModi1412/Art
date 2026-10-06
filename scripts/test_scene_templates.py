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
# The feature ships switched off (scenes.enabled); these tests exercise it.
os.environ["FREE_SCENES"] = "on"

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
img, lay = scenes.render(next(s for s in scenes.all_scenes() if not s["photo"] and s["stage"] == "stand"),
                         1080, 1920, seed=3)
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

print("\nswitched off by default")
os.environ["FREE_SCENES"] = "off"
check("off: the scene engine is not offered for pictures",
      "scene" not in [e["id"] for e in studio.image_engines(True)])
check("off: nor for clips", "scene" not in [e["id"] for e in studio.video_engines()])
try:
    studio.image_engine("scene", for_reshoot=True)
    check("off: asking for it by name is refused", False, "no error")
except ValueError:
    check("off: asking for it by name is refused", True)
os.environ["FREE_SCENES"] = "on"

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

print("\ninstalled backdrop library")
lib = scenes.photo_scenes()
check("the generated backdrops are installed", len(lib) >= 40, len(lib))
check("every installed backdrop has an image file that opens",
      all(Image.open(s["file"]).size[0] >= 700 for s in lib))
check("no rejected image slipped in (palm-woman, held are marked redo)",
      not any(s["id"].startswith(("palm-woman", "held-")) for s in lib))
for look in ("clean", "warm", "luxe", "editorial"):
    picks = {scenes.choose(st, look, seed=k)["id"] for st in ("stand", "flat") for k in range(25)}
    designs = {d for s in scenes.all_scenes() if s["id"] in picks for d in s["designs"]}
    check(f"a '{look}' brand left to choose never gets pastel or festive",
          not designs & {"pastel", "festive"}, sorted(designs))
    check("... and only designs that suit it", designs <= set(scenes.LOOK_DESIGNS[look]),
          sorted(designs))
bright = {d for k in range(30) for d in scenes.choose("stand", "bright", seed=k)["designs"]}
check("a 'bright' brand can get pastel", "pastel" in bright, sorted(bright))
check("choosing pastel yourself is honoured",
      "pastel" in scenes.choose("stand", "luxe", design="pastel")["designs"])
check("a festival post gets a festive set",
      "festive" in scenes.choose("stand", "luxe", festive=True, seed=1)["designs"])
nk = {scenes.choose("neck", "luxe", seed=k, person="woman", design="dark")["id"] for k in range(10)}
check("a pose with no exact design falls back to the nearest tone, not to festive",
      not any("festive" in s["designs"] for s in scenes.all_scenes() if s["id"] in nk), nk)
placed = []
for s in lib:
    st = s["stage"]
    if st == "model":
        continue
    use, ov, pp = {"stand": (cut_b, "stand", "beside" if s.get("pose") == "beside" else ""),
                   "palm": (cut_b, "stand", "palm"), "flat": (cut_n, "flat", ""),
                   "neck": (cut_n, "flat", "neck"), "ear": (cut_n, "flat", "ear"),
                   "hang": (cut_b, "hang", ""), "mannequin": (cut_b, "hang", "mannequin")}[st]
    r = composite.make(b"", seed=1, cut=use, scene_id=s["id"], pose_override=ov,
                       person=(s.get("person") or "") if pp else "", person_pose=pp)
    x0, y0, x1, y1 = r["layers"]["product_box"]
    placed.append(r["scene"] == s["id"] and x0 >= -2 and y0 >= -2 and x1 <= 1082 and y1 <= 1352)
check("every installed backdrop takes a product, fully inside a 4:5 post", all(placed),
      f"{sum(placed)}/{len(placed)}")

print("\nphoto shoot: tap-only choices")
from backend.core import shoot  # noqa: E402
import json  # noqa: E402
from pathlib import Path  # noqa: E402
man = json.loads((scenes.PHOTO_DIR / "manifest.json").read_text(encoding="utf-8"))
ids = [t["id"] for t in man["templates"]]
check("every manifest entry has a unique id", len(ids) == len(set(ids)))
check("every entry has a prompt, an anchor, a box and a known mode",
      all((t.get("prompt") or t.get("variant_of")) and len(t["anchor"]) == 2 and len(t["box"]) == 2
          and t["mode"] in ("base", "center", "top", "fit", "tryon") for t in man["templates"]))
check("every design has stand and flat backdrops listed",
      all(any(t["stage"] == st and t["design"] == d and not t.get("person") for t in man["templates"])
          for d in scenes.DESIGN_IDS for st in ("stand", "flat")))
check("a pose the product type does not allow is dropped",
      shoot.clean_choice({"type": "bag", "person": "woman", "pose": "neck"})["pose"] == "")
check("a person nobody poses as there is dropped",
      shoot.clean_choice({"type": "necklace", "person": "man", "pose": "neck"})["person"] == "")
check("a valid choice survives", shoot.clean_choice(
    {"type": "earrings", "design": "festive", "person": "woman", "pose": "ear"})
    == {"type": "earrings", "design": "festive", "person": "woman", "pose": "ear"})
check("product type sets how it rests",
      shoot.composite_args({"type": "hanger"})["pose_override"] == "hang"
      and shoot.composite_args({"type": "necklace"})["pose_override"] == "flat")

# Stand-in backdrops (flat colour, anchors from the manifest) to check that
# each person pose and the hanger attach the product at the right point.
tmp = Path(tempfile.mkdtemp())
(tmp / "manifest.json").write_text(json.dumps(man), encoding="utf-8")
for tid in ("neck-woman-1", "ear-woman-1", "palm-woman-1", "hang-studio-1"):
    Image.new("RGB", (1080, 1920), (200, 170, 150)).save(tmp / f"{tid}.jpg")
scenes.PHOTO_DIR, scenes.MANIFEST = tmp, tmp / "manifest.json"
o = shoot.options("earrings")
check("options only offer installed people and poses",
      [p["id"] for p in o["people"] if p["ready"]] == ["woman"], [(p["id"], p["ready"]) for p in o["people"]])
check("and say how much of the library is installed", o["library"]["installed"] == 4, o["library"])
by = {t["id"]: t for t in man["templates"]}
for tid, ch, cut_use in [
        ("neck-woman-1", {"type": "necklace", "person": "woman", "pose": "neck"}, cut_n),
        ("ear-woman-1", {"type": "earrings", "person": "woman", "pose": "ear"}, cut_n),
        ("hang-studio-1", {"type": "hanger"}, cut_b)]:
    for size in ("post", "reel"):
        r = composite.make(b"", size=size, seed=2, cut=cut_use, **shoot.composite_args(ch))
        x0, y0, x1, y1 = r["layers"]["product_box"]
        ax, ay = r["layout"]["floor"]
        W_, H_ = r["image"].size
        check(f"{tid} ({size}): the product's top hangs from the anchor, all in frame",
              r["scene"] == tid and abs(y0 - ay) <= 2 and x0 <= ax <= x1 and y0 >= 0 and y1 <= H_,
              (r["scene"], (x0, y0, x1, y1), (round(ax), round(ay)), (W_, H_)))
r = composite.make(b"", seed=2, cut=cut_b, **shoot.composite_args(
    {"type": "bottle", "person": "woman", "pose": "palm"}))
check("a bottle stands on the palm", r["scene"] == "palm-woman-1"
      and abs(r["layers"]["product_box"][3] - r["layout"]["floor"][1]) <= 2)
try:
    composite.make(b"", seed=2, cut=cut_b, **shoot.composite_args(
        {"type": "bottle", "person": "man", "pose": "beside"}))
    check("a person pose with no backdrop yet is refused, not faked", False, "no error")
except ValueError as e:
    check("a person pose with no backdrop yet is refused, not faked", "no backdrop" in str(e), str(e))

print("\nclothing with people")
check("clothing types offer wearing it, a dress form and holding it up",
      all(set(shoot.TYPES[t]["poses"]) == {"wear", "mannequin", "held"} for t in ("folded", "hanger")))
check("sarees get no person (nothing free drapes them)", shoot.TYPES["fabric"]["poses"] == [])
check("the mannequin is its own 'person'", shoot.clean_choice(
    {"type": "hanger", "person": "mannequin", "pose": "mannequin"})["pose"] == "mannequin")
hooked = Image.new("RGBA", (300, 400), (0, 0, 0, 0))
dh = ImageDraw.Draw(hooked)
dh.rectangle([145, 0, 155, 60], fill=(120, 120, 120, 255))       # the hook
dh.rectangle([20, 60, 280, 400], fill=(30, 60, 160, 255))        # the garment
check("a hanger's hook is trimmed off before the dress form", composite.trim_hook(hooked).size[1] <= 342,
      composite.trim_hook(hooked).size)
for tid in ("mannequin-woman-1", "held-woman-1", "model-woman-1"):
    Image.new("RGB", (1080, 1920), (220, 214, 204)).save(tmp / f"{tid}.jpg")
garment_photo = photo(lambda d: (d.rectangle([250, 300, 650, 900], fill=(30, 60, 160)),
                                 d.rectangle([150, 300, 250, 500], fill=(30, 60, 160)),
                                 d.rectangle([650, 300, 750, 500], fill=(30, 60, 160))))
cut_g = cutout.cut(garment_photo)
r = composite.make(b"", seed=3, cut=cut_g, **shoot.composite_args(
    {"type": "hanger", "person": "mannequin", "pose": "mannequin"}))
x0, y0, x1, y1 = r["layers"]["product_box"]
check("on a dress form the garment's top sits on the shoulders, sized to them",
      r["scene"] == "mannequin-woman-1" and abs(y0 - r["layout"]["floor"][1]) <= 2
      and abs((x1 - x0) - r["layout"]["box"][0]) <= 3, ((x0, y0, x1, y1), r["layout"]["box"]))
r = composite.make(b"", seed=3, cut=cut_g, **shoot.composite_args(
    {"type": "hanger", "person": "woman", "pose": "held"}))
check("held up, it hangs from the model's hand", r["scene"] == "held-woman-1"
      and abs(r["layers"]["product_box"][1] - r["layout"]["floor"][1]) <= 2)

from backend.core import tryon, user_store  # noqa: E402
calls = {"n": 0}
def fake_wear(garment, model_path, description=""):
    calls["n"] += 1
    return Image.new("RGB", (768, 1024), (30, 60, 160))
tryon.wear = fake_wear
store = {}
user_store.get_key = lambda e, k, d=None: store.get(k, d)
user_store.set_key = lambda e, k, v: store.__setitem__(k, v)
media.read = lambda name: (saved[name], "image/png") if name in saved else None
wear = {"type": "hanger", "design": "studio", "person": "woman", "pose": "wear"}
gref = (garment_photo, "image/jpeg")
m1 = studio._scene(brief, None, gref, "post", choice=wear, email="s@t.co", strict=True)
check("wearing it goes to the try-on and comes back post-sized",
      m1.get("tryon") and m1["image"].size == (1080, 1350) and m1["ai_made"], m1.get("scene"))
studio._scene(brief, None, gref, "reel", choice=wear, email="s@t.co", strict=True)
check("the same garment on the same model is tried on once, then reused", calls["n"] == 1, calls)
check("and the note tells the seller to check the garment", "check" in studio._scene_note(m1))
def broken(*a, **k):
    raise RuntimeError("The free try-on has used up today's GPU allowance.")
tryon.wear = broken
other = (photo(lambda d: d.rectangle([250, 300, 650, 900], fill=(160, 30, 60))), "image/jpeg")
fb = studio._scene(brief, None, other, "post", choice=wear, email="s@t.co")
check("a scheduled post falls back to the garment without a person when try-on fails",
      not fb.get("tryon") and fb["scene"] not in ("model-woman-1",), fb["scene"])
try:
    studio._scene(brief, None, other, "post", choice=wear, email="s@t.co", strict=True)
    check("a preview says why instead", False, "no error")
except ValueError as e:
    check("a preview says why instead", "allowance" in str(e), str(e))

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
