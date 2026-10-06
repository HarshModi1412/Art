"""
Put the seller's real product into a scene: free, on this server, no AI.

    photo --cutout.cut()--> product on transparency
          --pose()-------> does it stand up, or lie flat? is it tilted?
          --scenes.choose/render()--> a set shot from the matching camera height
          --place()------> scaled, shadowed, colour-matched, composited

WHAT IS AND IS NOT CHANGED ON THE PRODUCT
-----------------------------------------
Its pixels are the photo's pixels. Two things are allowed to touch them, both
small and both the kind of thing a photographer does in the edit:
  * a straightening rotation of up to 12 degrees, when a standing product was
    shot slightly crooked (pose());
  * a gentle colour-temperature match to the set, capped at a few percent per
    channel, so a cool white-balance photo does not sit in a warm room looking
    pasted (_harmonise()). Hue is never shifted: a red saree stays that red.

THE ANGLE PROBLEM
-----------------
The product keeps the camera angle it was photographed with, and nothing free
can change that. So the scene is chosen to match the photo, not the other way
round: pose() reads the cut-out's silhouette. A flat, solid base means it was
standing ("stand" scenes, camera at its height). A ragged or hanging bottom
edge, or a wide flat shape, means it was laid out ("flat" scenes, camera
overhead). When pose() guesses wrong the seller sets it once per product in
Product Studio, and that answer always wins.

What this cannot do, and says so rather than faking: put a garment ON a
person, turn a product to show another side, or put it in a hand from a photo
that was not taken in a hand. Those need a GPU try-on or 3-D model.
"""
from __future__ import annotations

import io
import logging
import math

import numpy as np
from PIL import Image, ImageFilter

from backend.core import scenes

log = logging.getLogger("composite")

SIZES = {"post": (1080, 1350), "square": (1080, 1080), "reel": (1080, 1920)}


# --------------------------------------------------------------- pose

def _base_stats(alpha: np.ndarray) -> dict:
    fg = alpha > 127
    h, w = fg.shape
    rows = np.where(fg.any(axis=1))[0]
    if not len(rows):
        return {"ratio": 0.0, "cx": w / 2, "width": 0}
    bottom = rows[-1]
    band = fg[max(0, bottom - max(2, int(h * 0.03))):bottom + 1]
    cols = np.where(band.any(axis=0))[0]
    filled = band.any(axis=0)
    # The widest unbroken run of the base. A bottle's base is one run; a pair
    # of earrings or a dangling pendant is several thin ones.
    best, run, best_end = 0, 0, 0
    for i, v in enumerate(filled):
        run = run + 1 if v else 0
        if run > best:
            best, best_end = run, i
    xs_any = np.where(fg.any(axis=0))[0]
    width_all = int(xs_any[-1] - xs_any[0] + 1) if len(xs_any) else 1
    return {"ratio": best / max(width_all, 1),
            "cx": float(best_end - best / 2) if best else (cols.mean() if len(cols) else w / 2),
            "width": best}


def _tilt(alpha: np.ndarray) -> float:
    """Degrees the product's long axis leans from vertical (+ = leans right)."""
    ys, xs = np.where(alpha > 127)
    if len(xs) < 50:
        return 0.0
    xs = xs - xs.mean()
    ys = ys - ys.mean()
    cov = np.cov(np.vstack([xs, ys]))
    vals, vecs = np.linalg.eigh(cov)
    vx, vy = vecs[:, int(np.argmax(vals))]
    if vy < 0:
        vx, vy = -vx, -vy
    return math.degrees(math.atan2(vx, vy))


def pose(cut: Image.Image, override: str = "") -> dict:
    """{"stage": "stand"|"flat", "tilt": degrees, "why": str}."""
    alpha = np.asarray(cut.getchannel("A"))
    h, w = alpha.shape
    base = _base_stats(alpha)
    tall = h / max(w, 1)
    tilt = _tilt(alpha) if tall >= 1.25 else 0.0
    if override in ("stand", "flat"):
        return {"stage": override, "tilt": tilt if override == "stand" else 0.0,
                "why": "from the product type you picked", "base": base}
    if base["ratio"] >= 0.30 and tall >= 0.55:
        return {"stage": "stand", "tilt": tilt, "base": base,
                "why": "it has a flat base to stand on"}
    return {"stage": "flat", "tilt": 0.0, "base": base,
            "why": ("its bottom edge hangs or is uneven"
                    if tall >= 0.55 else "it is wide and flat")}


def _straighten(cut: Image.Image, tilt: float) -> Image.Image:
    # Only small leans are a crooked photo. A big one is probably the product's
    # real shape (a slanted bottle, a bag with a strap), so it is left alone.
    if 1.5 <= abs(tilt) <= 12:
        cut = cut.rotate(-tilt, resample=Image.BICUBIC, expand=True)
        box = cut.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
        if box:
            cut = cut.crop(box)
    return cut


# --------------------------------------------------------------- colour

def _harmonise(cut: Image.Image, scene: Image.Image, at: tuple, strength=0.15) -> Image.Image:
    """Nudge the product's white balance toward the set's, never its hue.

    Per-channel gains from the ratio of the set's colour cast to the product's,
    applied at `strength` and capped at +-6%: enough that a daylight photo does
    not glow blue in a candle-lit set, not enough to change what colour the
    product is."""
    arr = np.asarray(cut, np.float32)
    a = arr[:, :, 3] > 200
    if a.sum() < 100:
        return cut
    x, y = at
    sw, sh = scene.size
    r = int(min(sw, sh) * 0.25)
    patch = np.asarray(scene.crop((max(0, int(x - r)), max(0, int(y - r)),
                                   min(sw, int(x + r)), min(sh, int(y + r)))), np.float32)
    s_mean = patch.reshape(-1, 3).mean(0)
    p_mean = arr[:, :, :3][a].mean(0)
    s_cast = s_mean / max(s_mean.mean(), 1)
    p_cast = p_mean / max(p_mean.mean(), 1)
    gain = 1 + np.clip((s_cast / np.maximum(p_cast, 1e-3) - 1) * strength, -0.06, 0.06)
    arr[:, :, :3] = np.clip(arr[:, :, :3] * gain, 0, 255)
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


# --------------------------------------------------------------- shadows

def _shadow_layer(size, alpha: Image.Image, at, blur, opacity):
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    a = alpha.point(lambda v: int(v * opacity))
    sh = Image.new("RGBA", alpha.size, (0, 0, 0, 0))
    sh.putalpha(a)
    layer.alpha_composite(sh, (int(at[0]), int(at[1])))
    return layer.filter(ImageFilter.GaussianBlur(blur)) if blur > 0 else layer


def _cast_shadow(size, alpha: Image.Image, base_x, floor_y, light, strength=0.30):
    """The product's silhouette laid back on the floor, away from the light:
    squashed to a third of its height and sheared sideways, darkest where it
    touches the product and fading with distance, like a real soft-box shadow."""
    w, h = alpha.size
    sh_h = max(1, int(h * 0.32))
    flat = alpha.resize((w, sh_h), Image.BILINEAR)
    fade = np.linspace(0.35, 1.0, sh_h)[:, None]     # far end faint, near end dark
    flat = Image.fromarray((np.asarray(flat, np.float32) * fade * strength).astype(np.uint8))
    # The far (top) row slides `shift` px sideways, the row on the floor none.
    # Light from the left (light[0] < 0) throws the shadow to the right.
    shift = -light[0] * 0.55 * sh_h
    o = min(0.0, shift)
    out_w = int(w + abs(shift)) + 2
    # AFFINE maps each OUTPUT pixel back to the input: x_in = x + o - shift*(1 - y/sh_h)
    sheared = flat.transform((out_w, sh_h), Image.AFFINE,
                             (1, shift / sh_h, o - shift, 0, 1, 0), resample=Image.BILINEAR)
    blk = Image.new("RGBA", sheared.size, (0, 0, 0, 0))
    blk.putalpha(sheared)
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    layer.alpha_composite(blk, (int(base_x - w / 2 + o), int(floor_y - sh_h + 2)))
    return layer.filter(ImageFilter.GaussianBlur(max(3, h * 0.025)))


def _contact_shadow(size, base_x, floor_y, base_w):
    from PIL import ImageDraw
    layer = Image.new("L", size, 0)
    ew, eh = base_w * 0.62, max(3, base_w * 0.07)
    ImageDraw.Draw(layer).ellipse([base_x - ew, floor_y - eh * 0.6,
                                   base_x + ew, floor_y + eh], fill=150)
    layer = layer.filter(ImageFilter.GaussianBlur(max(2, base_w * 0.035)))
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    out.putalpha(layer)
    return out


def _reflection(size, cut: Image.Image, at, strength=0.16):
    """A faint mirror image on a glossy surface, fading out quickly."""
    w, h = cut.size
    flip = cut.transpose(Image.FLIP_TOP_BOTTOM)
    rh = int(h * 0.35)
    flip = flip.crop((0, 0, w, rh))
    a = np.asarray(flip.getchannel("A"), np.float32)
    a *= np.linspace(strength, 0, rh)[:, None]
    flip.putalpha(Image.fromarray(a.astype(np.uint8)))
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    layer.alpha_composite(flip, (int(at[0]), int(at[1])))
    return layer.filter(ImageFilter.GaussianBlur(1.5))


# --------------------------------------------------------------- realism

def _match_exposure(cut: Image.Image, scene: Image.Image, at: tuple, strength=0.25) -> Image.Image:
    """Pull the product's brightness part of the way toward the set's.

    A product shot in bright daylight dropped into a dark luxury set glows like
    a sticker; the same product a touch darker reads as lit by that set. Capped
    to -18%/+10% so a white bottle stays white and a black one stays black."""
    arr = np.asarray(cut, np.float32)
    a = arr[:, :, 3] > 200
    if a.sum() < 100:
        return cut
    x, y = at
    sw, sh = scene.size
    r = int(min(sw, sh) * 0.3)
    patch = np.asarray(scene.crop((max(0, int(x - r)), max(0, int(y - r)),
                                   min(sw, int(x + r)), min(sh, int(y + r)))).convert("L"), np.float32)
    s_l = float(patch.mean())
    p_l = float((arr[:, :, :3][a] @ np.array([0.299, 0.587, 0.114], np.float32)).mean())
    gain = float(np.clip((max(s_l, 1) / max(p_l, 1)) ** strength, 0.82, 1.10))
    arr[:, :, :3] = np.clip(arr[:, :, :3] * gain, 0, 255)
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def _light_wrap(cut: Image.Image, scene: Image.Image, at: tuple, amount=0.30) -> Image.Image:
    """Let a little of the set's light spill over the product's outline.

    Real light bends round an object's edge, so its rim picks up the colour
    behind it. A cut-out has a perfectly clean rim, which is the single
    biggest tell of a composite. Only the outermost few pixels change."""
    import cv2
    w, h = cut.size
    x, y = int(at[0]), int(at[1])
    bg = scene.crop((x, y, x + w, y + h)).convert("RGB")
    if bg.size != cut.size:
        return cut
    bg = np.asarray(bg.filter(ImageFilter.GaussianBlur(max(2, min(w, h) * 0.02))), np.float32)
    arr = np.asarray(cut, np.float32)
    alpha = arr[:, :, 3] / 255.0
    inner = cv2.erode((alpha * 255).astype(np.uint8), np.ones((5, 5), np.uint8),
                      iterations=max(1, int(min(w, h) * 0.006))).astype(np.float32) / 255
    rim = np.clip(alpha - inner, 0, 1)[:, :, None] * amount
    arr[:, :, :3] = arr[:, :, :3] * (1 - rim) + bg * rim
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")


def one_piece(cut: Image.Image) -> Image.Image:
    """The biggest single piece of a cut-out: one earring from a photo of the
    pair, which is what goes on one ear."""
    import cv2
    a = (np.asarray(cut.getchannel("A")) > 127).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(a, 8)
    if n <= 2:
        return cut
    areas = stats[1:, cv2.CC_STAT_AREA]
    order = np.argsort(areas)[::-1]
    if areas[order[1]] < areas[order[0]] * 0.35:
        return cut             # one main piece with crumbs: already a single item
    i = order[0] + 1
    x, y, w, h = (stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_TOP],
                  stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT])
    keep = np.asarray(cut, np.uint8).copy()
    keep[:, :, 3] = np.where(labels == i, keep[:, :, 3], 0)
    return Image.fromarray(keep, "RGBA").crop((x, y, x + w, y + h))


def _top_cx(alpha: np.ndarray) -> float:
    """Horizontal centre of the product's top edge: where a hanger hook or a
    necklace's clasp ends are."""
    rows = np.where((alpha > 127).any(axis=1))[0]
    if not len(rows):
        return alpha.shape[1] / 2
    band = alpha[rows[0]:rows[0] + max(2, int(alpha.shape[0] * 0.06))] > 127
    xs = np.where(band.any(axis=0))[0]
    return float((xs[0] + xs[-1]) / 2) if len(xs) else alpha.shape[1] / 2


# --------------------------------------------------------------- placing

def place(scene_img: Image.Image, layout: dict, cut: Image.Image,
          stage: str, seed: int = 0) -> dict:
    """Composite the product into the set. Returns the layers separately as
    well as flattened, because the motion clip moves them independently.

    layout["mode"] says which point of the product sits on the anchor:
      base   — it stands there (tables, podiums, a palm): cast + contact shadow
      center — it lies there (flat-lays): soft drop shadow straight down
      top    — it hangs from there (a hook, a neckline, an earlobe)"""
    W, H = scene_img.size
    bw, bh = layout["box"]
    fx, fy = layout["floor"]
    light = layout.get("light") or (-1.0, -1.0)
    mode = layout.get("mode") or ("base" if stage == "stand" else "center")
    if mode == "center":
        rng = np.random.default_rng(seed)
        # A flat-lay is arranged by hand, never perfectly square to the frame.
        cut = cut.rotate(float(rng.uniform(-7, 7)), resample=Image.BICUBIC, expand=True)
        box = cut.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
        if box:
            cut = cut.crop(box)
    pw, ph = cut.size
    # Never blow a small photo up past 1.6x: soft pixels give a composite away
    # faster than anything else.
    s = min(bw / pw, bh / ph, 1.6)
    cut = cut.resize((max(1, int(pw * s)), max(1, int(ph * s))), Image.LANCZOS)
    pw, ph = cut.size
    a_np = np.asarray(cut.getchannel("A"))

    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if mode == "base":
        base = _base_stats(a_np)
        x, y = int(fx - base["cx"]), int(fy - ph)
        centre = (fx, fy - ph / 2)
    elif mode == "top":
        x, y = int(fx - _top_cx(a_np)), int(fy)
        centre = (fx, fy + ph / 2)
    else:
        x, y = int(fx - pw / 2), int(fy - ph / 2)
        centre = (fx, fy)

    cut = _harmonise(cut, scene_img, centre)
    cut = _match_exposure(cut, scene_img, centre)
    cut = _light_wrap(cut, scene_img, (x, y))
    a = cut.getchannel("A")

    if mode == "base":
        small = stage == "palm"
        shadow.alpha_composite(_cast_shadow((W, H), a, fx, fy, light,
                                            strength=0.18 if small else 0.30))
        shadow.alpha_composite(_contact_shadow((W, H), fx, fy, max(base["width"], pw * 0.3)))
        if layout.get("gloss"):
            shadow.alpha_composite(_reflection((W, H), cut, (x, fy)))
    elif mode == "top":
        # Hanging against a wall or lying on skin: the shadow falls a little
        # below and away from the light, close for jewellery, further for a
        # garment that hangs off the wall on its hanger.
        far = 0.035 if stage == "hang" else 0.012
        off = (-light[0] * pw * far, -light[1] * ph * far + ph * far)
        shadow.alpha_composite(_shadow_layer((W, H), a, (x + off[0], y + off[1]),
                                             max(3, min(pw, ph) * (0.04 if stage == "hang" else 0.015)),
                                             0.38 if stage == "hang" else 0.45))
    else:
        off = (-light[0] * pw * 0.025, -light[1] * ph * 0.025)
        shadow.alpha_composite(_shadow_layer((W, H), a, (x + off[0], y + off[1]),
                                             max(4, min(pw, ph) * 0.03), 0.42))
        shadow.alpha_composite(_shadow_layer((W, H), a, (x + 1, y + 2), 2, 0.35))

    product = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    product.alpha_composite(cut, (x, y))
    out = scene_img.convert("RGBA")
    out.alpha_composite(shadow)
    out.alpha_composite(product)
    anchor = (fx, fy) if mode == "base" else (centre[0], centre[1])
    return {"image": out.convert("RGB"), "background": scene_img, "shadow": shadow,
            "product": product, "anchor": anchor, "product_box": (x, y, x + pw, y + ph)}


# Which backdrop stage each person pose uses.
POSE_STAGE = {"palm": "palm", "neck": "neck", "ear": "ear", "beside": "stand"}


def make(photo: bytes, *, size: str = "post", look: str = "clean", palette: str = "",
         festive: bool = False, pose_override: str = "", seed: int = 0,
         scene_id: str = "", cut: dict | None = None, design: str = "",
         person: str = "", person_pose: str = "") -> dict:
    """The whole job: cut, read the pose, choose a set, place. Returns
    {"image": PIL RGB, "layers": {...}, "scene", "pose", "quality", ...}.

    pose_override is the product's own resting pose ("stand", "flat", "hang"),
    from the product type the seller picked. person + person_pose ask for a
    backdrop with a person in it (see POSE_STAGE).

    Raises ValueError with a seller-readable reason when the photo cannot make
    a believable picture (product not found, cut off at the frame edge), or
    when no backdrop exists yet for the person and pose asked for."""
    from backend.core import cutout
    cut = cut or cutout.cut(photo)
    q = cut["quality"]
    blocking = [p for p in q["problems"]
                if "could not" in p or "runs off" in p]
    if blocking:
        raise ValueError(" ".join(blocking) + " " + q.get("tip", ""))
    if pose_override == "hang":
        p = {"stage": "hang", "tilt": 0.0, "why": "it hangs on a hanger"}
    else:
        p = pose(cut["image"], pose_override)
    product = _straighten(cut["image"], p["tilt"]) if p["stage"] == "stand" else cut["image"]
    stage = p["stage"]
    if person and person_pose:
        stage = POSE_STAGE.get(person_pose, stage)
        if person_pose == "ear":
            product = one_piece(product)
    W, H = SIZES.get(size, SIZES["post"])
    scene = next((s for s in scenes.all_scenes() if s["id"] == scene_id), None) \
        or scenes.choose(stage, look, festive, seed=seed, design=design,
                         person=person if person_pose else "")
    if person and person_pose and (scene["stage"] != stage or (scene.get("person") or "") != person):
        raise ValueError("There is no backdrop with that person and pose yet. "
                         "Pick another, or a design without a person.")
    bg, layout = scenes.render(scene, W, H, look=look, palette=palette, seed=seed)
    if person_pose == "palm" and p["stage"] == "flat":
        # Jewellery photographed flat lies ON the palm, so it is centred a
        # little above the palm's base point rather than stood up on it.
        layout = {**layout, "mode": "center",
                  "floor": (layout["floor"][0], layout["floor"][1] - layout["box"][1] * 0.25)}
    placed = place(bg, layout, product, stage, seed=seed)
    return {"image": placed["image"], "layers": placed, "layout": layout,
            "scene": scene["id"], "scene_label": scene["label"],
            "ai_made": bool(layout.get("ai_made")), "photo_backdrop": bool(layout.get("photo")),
            "pose": {k: v for k, v in p.items() if k != "base"},
            "quality": q, "cutout_engine": cut["engine"]}


def to_jpeg(img: Image.Image, quality: int = 92) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
    return buf.getvalue()
