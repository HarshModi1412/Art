"""
Scene templates: the sets a seller's real product is placed into.

THE IDEA
--------
An AI re-shoot redraws the product, so the product in the post drifts from the
product that ships. Here nothing is redrawn: backend/core/cutout.py cuts the
real product out of the seller's photo, and backend/core/composite.py stands
it in one of these scenes with a shadow that agrees with the scene's light.
The product's pixels are the seller's pixels. No image API is called.

THE CAMERA PROBLEM, AND WHY EVERY SCENE HAS A `stage`
-----------------------------------------------------
A cut-out keeps the angle it was photographed from. A perfume bottle shot from
the front cannot be put on a table seen from above, and a necklace laid flat
and shot from above cannot stand on a podium. Nothing free can re-pose a
product (that needs a 3-D model or a GPU), so instead each scene declares the
camera it was "shot" with and the product only goes into scenes that match:

  * "stand" — camera at the product's height looking across a surface. For
    things that stand up: bottles, jars, boxes, bags, shoes, candles.
  * "flat"  — camera straight down onto a surface. For things that lie flat or
    hang: necklaces, earrings, folded clothes, scarves, flat-lays.

composite.pose() decides which one a photo is; the seller can override it per
product in Product Studio.

TWO KINDS OF SCENE
------------------
1. DRAWN scenes (below). Painted with numpy at whatever size is asked for, so a
   4:5 post and a 9:16 reel get a real layout each, not a crop. Not AI, so a
   picture made only from these needs no "AI generated" label.
2. PHOTO scenes: any image dropped into backend/static/scenes/ with a JSON
   file of the same name beside it. This is where a pre-generated, once-only
   AI backdrop goes (an empty marble podium, an empty Diwali table). The JSON:

     {"label": "Marble podium", "stage": "stand",
      "looks": ["clean", "luxe"], "festive": false,
      "ai_made": true,                 # true -> the picture gets the AI label
      "floor": [0.5, 0.74],            # where the product's base sits (x, y)
      "box": [0.42, 0.50],             # biggest the product may be (w, h)
      "light": [-1, -1],               # where the light comes FROM
      "gloss": false}                  # shiny surface -> faint reflection

   For a "flat" scene, "floor" is the centre of the product instead. The
   empty scene must be generated WITHOUT a product in it, with the space
   for one left clear.
"""
from __future__ import annotations

import json
import logging
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

log = logging.getLogger("scenes")

PHOTO_DIR = Path(__file__).resolve().parents[1] / "static" / "scenes"

# --------------------------------------------------------------- colour

# Enough to read the palette a seller types into the brand profile ("warm
# sand, black, brass"). Unknown words are skipped, not guessed at.
COLOUR_WORDS = {
    "white": (238, 236, 232), "ivory": (240, 234, 218), "cream": (238, 228, 205),
    "beige": (222, 205, 180), "sand": (214, 192, 160), "nude": (220, 190, 170),
    "blush": (232, 196, 192), "pink": (236, 170, 185), "rose": (210, 140, 150),
    "peach": (244, 190, 160), "coral": (238, 128, 108), "red": (176, 40, 44),
    "maroon": (110, 28, 40), "wine": (100, 30, 48), "burgundy": (98, 26, 42),
    "orange": (232, 120, 48), "rust": (170, 80, 45), "terracotta": (190, 100, 70),
    "mustard": (212, 160, 40), "yellow": (240, 200, 70), "gold": (200, 160, 80),
    "brass": (181, 146, 72), "olive": (120, 120, 70), "sage": (160, 178, 150),
    "green": (60, 120, 80), "emerald": (20, 100, 70), "mint": (180, 225, 200),
    "teal": (30, 110, 115), "turquoise": (60, 180, 180), "blue": (50, 90, 160),
    "navy": (30, 40, 70), "indigo": (50, 50, 110), "sky": (160, 200, 235),
    "lavender": (190, 175, 225), "lilac": (200, 170, 210), "purple": (100, 50, 120),
    "plum": (90, 40, 70), "brown": (110, 75, 50), "chocolate": (80, 50, 35),
    "tan": (200, 160, 120), "wood": (150, 105, 70), "walnut": (100, 70, 45),
    "grey": (150, 150, 150), "gray": (150, 150, 150), "charcoal": (55, 55, 58),
    "silver": (192, 192, 196), "black": (24, 24, 26), "stone": (176, 170, 160),
}


def palette_colours(text: str) -> list[tuple[int, int, int]]:
    words = "".join(c if c.isalpha() else " " for c in (text or "").lower()).split()
    return [COLOUR_WORDS[w] for w in words if w in COLOUR_WORDS]


def _mix(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def _lum(c) -> float:
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


# --------------------------------------------------------------- painting

def _vgrad(w, h, stops):
    """Vertical gradient through [(pos 0..1, (r,g,b)), ...]."""
    ys = np.linspace(0, 1, h)[:, None]
    pos = np.array([p for p, _ in stops])
    cols = np.array([c for _, c in stops], dtype=np.float32)
    out = np.empty((h, 1, 3), np.float32)
    for ch in range(3):
        out[:, :, ch] = np.interp(ys, pos, cols[:, ch])
    return np.repeat(out, w, axis=1)


def _noise(w, h, cells, rng, stretch=(1.0, 1.0)):
    """Smooth value noise in 0..1: a small random grid scaled up bicubically.
    `stretch` > 1 elongates the grain along that axis (wood, brushed metal)."""
    gw = max(2, int(cells / stretch[0]))
    gh = max(2, int(cells * h / max(w, 1) / stretch[1]))
    g = (rng.random((gh, gw)) * 255).astype(np.uint8)
    im = Image.fromarray(g).resize((w, h), Image.BICUBIC)
    return np.asarray(im, np.float32) / 255.0


def _fractal(w, h, rng, base=4, octaves=4, stretch=(1.0, 1.0)):
    out, amp, tot = np.zeros((h, w), np.float32), 1.0, 0.0
    for o in range(octaves):
        out += _noise(w, h, base * 2 ** o, rng, stretch) * amp
        tot += amp
        amp *= 0.5
    return out / tot


def _radial(w, h, cx, cy, r):
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2) / max(r, 1)
    return np.clip(1 - d, 0, 1) ** 2


def _finish(arr, rng, grain=3.0, vignette=0.18):
    h, w = arr.shape[:2]
    if vignette:
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        d = np.sqrt(((xs - w / 2) / (w / 2)) ** 2 + ((ys - h / 2) / (h / 2)) ** 2)
        arr = arr * (1 - vignette * np.clip(d - 0.55, 0, 1)[:, :, None])
    if grain:
        # Fine grain stops the smooth gradients banding on a phone screen and
        # makes the set read as photographed rather than drawn.
        arr = arr + rng.normal(0, grain, (h, w, 1)).astype(np.float32)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def _light_pool(arr, cx, cy, r, strength):
    pool = _radial(arr.shape[1], arr.shape[0], cx, cy, r)[:, :, None]
    return arr + (255 - arr) * pool * strength


# --------------------------------------------------------------- drawn scenes
# Each returns (RGB image, layout). Layout coordinates are pixels:
#   floor (x, y): where the product's base sits (stand) / its centre (flat)
#   box (w, h):   the biggest the product may be drawn
#   light (dx, dy): where the light comes FROM (shadows fall the other way)
#   gloss: a shiny surface, so the product gets a faint reflection

def _sweep(w, h, rng, c, *, horizon=0.66, podium=False, base=None):
    """A seamless paper sweep: wall tone fading into a slightly lighter floor,
    with a pool of light behind the product. The workhorse studio set."""
    wall_top = _mix(c, (0, 0, 0), 0.16)
    wall = c
    floor = _mix(c, (255, 255, 255), 0.10)
    arr = _vgrad(w, h, [(0, wall_top), (horizon - 0.08, wall),
                        (horizon + 0.06, floor), (1, _mix(floor, (0, 0, 0), 0.06))])
    arr = _light_pool(arr, w * 0.5, h * (horizon - 0.12), w * 0.75, 0.22)
    floor_y = h * (horizon + 0.12)
    layout = {"floor": (w * 0.5, floor_y), "box": (w * 0.56, h * 0.50),
              "light": (-1.0, -1.0), "gloss": False}
    img = _finish(arr, rng)
    if podium:
        img, layout = _podium(img, rng, w, h, base or _mix(c, (255, 255, 255), 0.35),
                              floor_y, layout)
    return img, layout


def _podium(img, rng, w, h, col, floor_y, layout):
    """A cylinder plinth the product stands on. Its top ellipse becomes the new
    floor, and its own shading follows the same top-left light."""
    pw = w * 0.52
    ph = h * 0.16
    ex = pw / 2
    ey = pw * 0.09
    cx = w * 0.5
    bottom = floor_y + ey * 0.6
    top = bottom - ph
    body = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    arr = np.zeros((h, w, 4), np.float32)
    xs = np.arange(w, dtype=np.float32)
    # Horizontal shading across the cylinder: lit from the left.
    t = np.clip((xs - (cx - ex)) / (2 * ex), 0, 1)
    shade = 1.06 - 0.28 * t ** 1.3
    for ch in range(3):
        arr[:, :, ch] = np.clip(col[ch] * shade, 0, 255)[None, :]
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.rectangle([cx - ex, top, cx + ex, bottom], fill=255)
    md.ellipse([cx - ex, bottom - ey, cx + ex, bottom + ey], fill=255)
    arr[:, :, 3] = np.asarray(mask, np.float32)
    body = Image.fromarray(arr.astype(np.uint8), "RGBA")
    # Contact shadow of the plinth on the floor.
    sh = Image.new("L", (w, h), 0)
    ImageDraw.Draw(sh).ellipse([cx - ex * 1.08, bottom - ey * 0.9, cx + ex * 1.18, bottom + ey * 1.4],
                               fill=110)
    sh = sh.filter(ImageFilter.GaussianBlur(max(4, w * 0.012)))
    base = img.convert("RGBA")
    base = Image.composite(Image.new("RGBA", (w, h), (0, 0, 0, 255)), base,
                           sh.point(lambda v: int(v * 0.55)))
    base.alpha_composite(body)
    top_col = _mix(col, (255, 255, 255), 0.18)
    tl = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(tl).ellipse([cx - ex, top - ey, cx + ex, top + ey], fill=top_col + (255,))
    base.alpha_composite(tl)
    layout = {**layout, "floor": (cx, top), "box": (pw * 0.92, h * 0.46),
              "podium": True}
    return base.convert("RGB"), layout


def _table(w, h, rng, wall, wood, *, horizon=0.62, gloss=False):
    """A wall and a wooden table top: the 'warm and handmade' set."""
    arr = _vgrad(w, h, [(0, _mix(wall, (0, 0, 0), 0.12)), (horizon, wall), (1, wall)])
    arr = _light_pool(arr, w * 0.38, h * 0.30, w * 0.8, 0.25)
    top = int(h * horizon)
    grain = _fractal(w, h - top, rng, base=3, octaves=4, stretch=(14.0, 1.0))
    streak = 0.75 + 0.5 * grain
    t = np.linspace(0, 1, h - top)[:, None]
    wood_arr = np.empty((h - top, w, 3), np.float32)
    for ch in range(3):
        wood_arr[:, :, ch] = wood[ch] * streak * (0.82 + 0.25 * t)
    arr[top:] = wood_arr
    # A soft dark line where the table meets the wall.
    arr[max(0, top - 2):top + 3] *= 0.8
    img = _finish(arr, rng)
    return img, {"floor": (w * 0.5, top + (h - top) * 0.42),
                 "box": (w * 0.54, h * 0.50), "light": (-1.0, -1.0), "gloss": gloss}


def _arch(w, h, rng, bg, arch, floor):
    """Colour blocking: a flat wall, an arch behind the product, a floor band."""
    arr = _vgrad(w, h, [(0, bg), (1, _mix(bg, (0, 0, 0), 0.08))])
    img = _finish(arr, rng, grain=2.0, vignette=0.08).convert("RGBA")
    d = ImageDraw.Draw(img)
    aw = w * 0.62
    ax0, ax1 = (w - aw) / 2, (w + aw) / 2
    fy = h * 0.74
    d.rectangle([ax0, h * 0.30 + aw / 2, ax1, fy], fill=arch)
    d.ellipse([ax0, h * 0.30, ax1, h * 0.30 + aw], fill=arch)
    d.rectangle([0, fy, w, h], fill=floor)
    img = img.convert("RGB")
    return img, {"floor": (w * 0.5, fy + (h - fy) * 0.35), "box": (w * 0.5, h * 0.48),
                 "light": (-1.0, -1.0), "gloss": False}


def _bokeh(img, rng, n, colours, area, size):
    """Out-of-focus lights: festive without drawing anything that could clash
    with the product."""
    w, h = img.size
    # The empty layer is the lights' own colour at zero opacity, not black:
    # Pillow blurs RGBA without premultiplying, so a black empty layer bleeds
    # a dark ring into every soft edge.
    layer = Image.new("RGBA", (w, h), colours[0] + (0,))
    d = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = area
    for _ in range(n):
        r = size * (0.4 + rng.random())
        x = x0 + rng.random() * (x1 - x0)
        y = y0 + rng.random() * (y1 - y0)
        col = colours[int(rng.integers(len(colours)))]
        d.ellipse([x - r, y - r, x + r, y + r], fill=col + (int(60 + rng.random() * 90),))
    layer = layer.filter(ImageFilter.GaussianBlur(size * 0.18))
    out = img.convert("RGBA")
    out.alpha_composite(layer)
    return out.convert("RGB")


def _petals(img, rng, n, area, size, avoid=None):
    """Scattered marigold petals for festival sets, kept out of the product's spot."""
    w, h = img.size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cols = [(240, 140, 20), (250, 175, 30), (230, 110, 20), (200, 40, 50)]
    x0, y0, x1, y1 = area
    placed = 0
    for _ in range(n * 6):
        if placed >= n:
            break
        x = x0 + rng.random() * (x1 - x0)
        y = y0 + rng.random() * (y1 - y0)
        if avoid and avoid[0] < x < avoid[2] and avoid[1] < y < avoid[3]:
            continue
        r = size * (0.6 + rng.random() * 0.8)
        petal = Image.new("RGBA", (int(r * 2.4), int(r * 1.4)), (0, 0, 0, 0))
        col = cols[int(rng.integers(len(cols)))]
        ImageDraw.Draw(petal).ellipse([0, 0, petal.width - 1, petal.height - 1], fill=col + (235,))
        petal = petal.rotate(float(rng.random() * 360), expand=True, resample=Image.BICUBIC)
        sh = Image.new("RGBA", petal.size, (0, 0, 0, 0))
        sh.putalpha(petal.getchannel("A").point(lambda v: int(v * 0.35)))
        layer.alpha_composite(sh.filter(ImageFilter.GaussianBlur(2)),
                              (int(x + 3), int(y + 4)))
        layer.alpha_composite(petal, (int(x), int(y)))
        placed += 1
    out = img.convert("RGBA")
    out.alpha_composite(layer)
    return out.convert("RGB")


def _marble(w, h, rng, base, vein):
    # Ridged noise: the creases where smooth noise crosses its midpoint become
    # thin wandering veins, which is how real marble reads. Blurred a touch so
    # they sit under a polished surface rather than on top of it.
    n = _fractal(w, h, rng, base=2, octaves=6, stretch=(1.6, 1.0))
    veins = (1 - np.abs(2 * n - 1)) ** 18
    fine = (1 - np.abs(2 * _fractal(w, h, rng, base=4, octaves=5) - 1)) ** 30
    veins = np.clip(veins + fine * 0.5, 0, 1)
    veins = np.asarray(Image.fromarray((veins * 255).astype(np.uint8))
                       .filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255
    soft = _fractal(w, h, rng, base=2, octaves=3)
    arr = np.empty((h, w, 3), np.float32)
    for ch in range(3):
        arr[:, :, ch] = (base[ch] * (0.95 + 0.07 * soft) * (1 - veins * 0.35)
                         + vein[ch] * veins * 0.35)
    return arr


def _flat_surface(w, h, rng, kind, c):
    if kind == "linen":
        fine = _fractal(w, h, rng, base=80, octaves=2, stretch=(1.0, 6.0)) * 0.5 + \
               _fractal(w, h, rng, base=80, octaves=2, stretch=(6.0, 1.0)) * 0.5
        soft = _fractal(w, h, rng, base=3, octaves=3)
        arr = np.empty((h, w, 3), np.float32)
        for ch in range(3):
            arr[:, :, ch] = c[ch] * (0.90 + 0.10 * fine) * (0.95 + 0.08 * soft)
    elif kind == "marble":
        arr = _marble(w, h, rng, c, (120, 120, 124))
    elif kind == "velvet":
        sheen = _fractal(w, h, rng, base=2, octaves=4)
        arr = np.empty((h, w, 3), np.float32)
        for ch in range(3):
            arr[:, :, ch] = c[ch] * (0.65 + 0.6 * sheen)
    else:  # paper
        soft = _fractal(w, h, rng, base=2, octaves=2)
        arr = np.empty((h, w, 3), np.float32)
        for ch in range(3):
            arr[:, :, ch] = c[ch] * (0.96 + 0.06 * soft)
    # Window light falling across the flat-lay from the top-left.
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    fall = 1.06 - 0.16 * ((xs / w) * 0.5 + (ys / h) * 0.5)
    return arr * fall[:, :, None]


def _flat(w, h, rng, kind, c, festive=False):
    arr = _flat_surface(w, h, rng, kind, c)
    img = _finish(arr, rng, grain=2.5, vignette=0.12)
    layout = {"floor": (w * 0.5, h * 0.5), "box": (w * 0.66, h * 0.58),
              "light": (-1.0, -1.0), "gloss": False}
    if kind == "paper":
        # One large soft shape off to the side so the frame is not a flat fill.
        tone = _mix(c, (255, 255, 255), 0.25)
        layer = Image.new("RGBA", (w, h), tone + (0,))
        r = w * 0.42
        ImageDraw.Draw(layer).ellipse([w * 0.62 - r, h * 0.18 - r, w * 0.62 + r, h * 0.18 + r],
                                      fill=tone + (150,))
        img = img.convert("RGBA")
        img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(w * 0.01)))
        img = img.convert("RGB")
    if festive:
        avoid = (w * 0.16, h * 0.18, w * 0.84, h * 0.82)
        img = _petals(img, rng, 26, (0, 0, w, h), w * 0.018, avoid=avoid)
        img = _bokeh(img, rng, 10, [(255, 200, 110), (255, 225, 160)],
                     (0, 0, w, h * 0.2), w * 0.03)
    return img, layout


# Defaults per look when the seller's palette names no colours we know.
LOOK_COLOURS = {
    "clean": [(232, 229, 224), (214, 220, 222), (236, 226, 214)],
    "warm": [(226, 210, 188), (214, 196, 170), (232, 214, 196)],
    "luxe": [(38, 34, 36), (30, 36, 40), (48, 30, 34)],
    "bright": [(244, 182, 160), (170, 210, 236), (246, 214, 110)],
    "editorial": [(196, 186, 176), (150, 160, 166), (210, 196, 190)],
}


def _pick_colour(rng, look, palette):
    if palette:
        c = palette[int(rng.integers(len(palette)))]
        # A near-black palette colour is only a set for a dark look. In a light
        # look it would swallow the product, so lift it into a tint instead.
        if look not in ("luxe",) and _lum(c) < 90:
            c = _mix(c, (240, 236, 230), 0.82)
        if look == "luxe" and _lum(c) > 120:
            c = _mix(c, (20, 20, 22), 0.75)
        return c
    opts = LOOK_COLOURS.get(look) or LOOK_COLOURS["clean"]
    return opts[int(rng.integers(len(opts)))]


def _draw_studio(w, h, rng, look, pal):
    return _sweep(w, h, rng, _pick_colour(rng, look, pal))


def _draw_podium(w, h, rng, look, pal):
    c = _pick_colour(rng, look, pal)
    base = _mix(c, (255, 255, 255), 0.4) if _lum(c) < 140 else _mix(c, (0, 0, 0), 0.10)
    img, lay = _sweep(w, h, rng, c, podium=True, base=base)
    return img, {**lay, "gloss": look == "luxe"}


def _draw_table(w, h, rng, look, pal):
    wall = _pick_colour(rng, "warm" if look not in ("luxe",) else look, pal)
    wood = (150, 105, 70) if look != "luxe" else (70, 48, 34)
    return _table(w, h, rng, wall, wood, gloss=look == "luxe")


def _draw_dark(w, h, rng, look, pal):
    c = _pick_colour(rng, "luxe", pal)
    arr = _vgrad(w, h, [(0, _mix(c, (0, 0, 0), 0.4)), (0.6, c), (1, _mix(c, (0, 0, 0), 0.3))])
    # Rim of light behind the product: the classic low-key perfume shot.
    arr = _light_pool(arr, w * 0.5, h * 0.48, w * 0.55, 0.30)
    top = int(h * 0.70)
    stone = _fractal(w, h - top, rng, base=5, octaves=4)
    arr[top:] = arr[top:] * (0.55 + 0.35 * stone[:, :, None])
    img = _finish(arr, rng, grain=3.5, vignette=0.30)
    return img, {"floor": (w * 0.5, top + (h - top) * 0.32), "box": (w * 0.5, h * 0.52),
                 "light": (-0.6, -1.0), "gloss": True}


def _draw_arch(w, h, rng, look, pal):
    a = _pick_colour(rng, "bright", pal)
    b = _pick_colour(rng, "bright", pal)
    if a == b:
        b = _mix(a, (255, 255, 255), 0.45)
    return _arch(w, h, rng, a, b, _mix(a, (0, 0, 0), 0.12))


def _draw_festive(w, h, rng, look, pal):
    c = (60, 22, 26) if look in ("luxe", "editorial") else (92, 40, 24)
    arr = _vgrad(w, h, [(0, _mix(c, (0, 0, 0), 0.5)), (0.65, c), (1, _mix(c, (0, 0, 0), 0.4))])
    arr = _light_pool(arr, w * 0.5, h * 0.50, w * 0.6, 0.28)
    top = int(h * 0.70)
    grain = _fractal(w, h - top, rng, base=3, octaves=4, stretch=(12.0, 1.0))
    arr[top:] = arr[top:] * (0.55 + 0.35 * grain[:, :, None])
    img = _finish(arr, rng, grain=3.0, vignette=0.28)
    img = _bokeh(img, rng, 26, [(255, 190, 90), (255, 215, 140), (255, 160, 70)],
                 (0, 0, w, h * 0.6), w * 0.045)
    floor_y = top + (h - top) * 0.32
    img = _petals(img, rng, 14, (0, floor_y - h * 0.02, w, h),
                  w * 0.02, avoid=(w * 0.24, 0, w * 0.76, h))
    return img, {"floor": (w * 0.5, floor_y), "box": (w * 0.5, h * 0.50),
                 "light": (-0.4, -1.0), "gloss": True}


def _flat_drawer(kind, festive=False):
    def draw(w, h, rng, look, pal):
        if kind == "velvet":
            c = _pick_colour(rng, "luxe", pal)
            c = _mix(c, (90, 20, 40), 0.35) if festive else c
        elif kind == "marble":
            c = (232, 230, 226) if look != "luxe" else (70, 70, 74)
        else:
            c = _pick_colour(rng, look if kind != "linen" else "warm", pal)
        return _flat(w, h, rng, kind, c, festive=festive)
    return draw


DRAWN = [
    {"id": "studio",   "label": "Studio sweep",       "stage": "stand",
     "looks": ["clean", "editorial", "warm", "bright"], "festive": False, "draw": _draw_studio},
    {"id": "podium",   "label": "Podium",             "stage": "stand",
     "looks": ["clean", "luxe", "bright", "editorial"], "festive": False, "draw": _draw_podium},
    {"id": "table",    "label": "Wooden table",       "stage": "stand",
     "looks": ["warm", "editorial"], "festive": False, "draw": _draw_table},
    {"id": "dark",     "label": "Low-key stone",      "stage": "stand",
     "looks": ["luxe", "editorial"], "festive": False, "draw": _draw_dark},
    {"id": "arch",     "label": "Colour block arch",  "stage": "stand",
     "looks": ["bright"], "festive": False, "draw": _draw_arch},
    {"id": "festive",  "label": "Festive lights",     "stage": "stand",
     "looks": ["clean", "warm", "luxe", "bright", "editorial"], "festive": True,
     "draw": _draw_festive},
    {"id": "flat-linen",  "label": "Linen flat-lay",   "stage": "flat",
     "looks": ["warm", "clean", "editorial"], "festive": False, "draw": _flat_drawer("linen")},
    {"id": "flat-marble", "label": "Marble flat-lay",  "stage": "flat",
     "looks": ["clean", "luxe", "editorial"], "festive": False, "draw": _flat_drawer("marble")},
    {"id": "flat-paper",  "label": "Paper flat-lay",   "stage": "flat",
     "looks": ["bright", "clean"], "festive": False, "draw": _flat_drawer("paper")},
    {"id": "flat-velvet", "label": "Velvet flat-lay",  "stage": "flat",
     "looks": ["luxe", "editorial"], "festive": False, "draw": _flat_drawer("velvet")},
    {"id": "flat-festive", "label": "Festive flat-lay", "stage": "flat",
     "looks": ["clean", "warm", "luxe", "bright", "editorial"], "festive": True,
     "draw": _flat_drawer("velvet", festive=True)},
]


# --------------------------------------------------------------- photo scenes

def _photo_scenes() -> list[dict]:
    out = []
    if not PHOTO_DIR.is_dir():
        return out
    for meta in sorted(PHOTO_DIR.glob("*.json")):
        try:
            spec = json.loads(meta.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001 — one bad file must not hide the rest
            log.warning("scene %s unreadable: %s", meta.name, e)
            continue
        img = next((p for p in (meta.with_suffix(ext) for ext in (".jpg", ".jpeg", ".png", ".webp"))
                    if p.exists()), None)
        if not img or spec.get("stage") not in ("stand", "flat"):
            continue
        out.append({"id": "photo-" + meta.stem, "label": spec.get("label") or meta.stem,
                    "stage": spec["stage"], "looks": spec.get("looks") or list(LOOK_COLOURS),
                    "festive": bool(spec.get("festive")), "ai_made": bool(spec.get("ai_made", True)),
                    "file": img, "spec": spec})
    return out


def _render_photo(scene: dict, w: int, h: int):
    spec = scene["spec"]
    src = Image.open(scene["file"]).convert("RGB")
    sw, sh = src.size
    # Cover-crop to the asked-for frame, keeping the product's spot in view.
    s = max(w / sw, h / sh)
    nw, nh = int(round(sw * s)), int(round(sh * s))
    fx, fy = spec.get("floor") or [0.5, 0.7]
    ox = int(min(max(fx * nw - w / 2, 0), nw - w))
    oy = int(min(max(fy * nh - h * 0.62, 0), nh - h))
    img = src.resize((nw, nh), Image.LANCZOS).crop((ox, oy, ox + w, oy + h))
    bx, by = spec.get("box") or [0.45, 0.5]
    return img, {"floor": (fx * nw - ox, fy * nh - oy), "box": (bx * nw, by * nh),
                 "light": tuple(spec.get("light") or (-1.0, -1.0)),
                 "gloss": bool(spec.get("gloss"))}


# --------------------------------------------------------------- choosing

def all_scenes() -> list[dict]:
    return [{**s, "ai_made": False} for s in DRAWN] + _photo_scenes()


def choose(stage: str, look: str = "clean", festive: bool = False,
           seed: int | None = None, exclude: tuple = ()) -> dict:
    """Pick a scene that matches the product's camera angle first, then the
    brand's look, then whether this is a festival post. Photo scenes win ties
    because a real backdrop beats a drawn one when one exists."""
    rng = random.Random(seed)
    pool = [s for s in all_scenes() if s["stage"] == stage and s["id"] not in exclude]
    if not pool:
        pool = [s for s in all_scenes() if s["stage"] == stage]

    def score(s):
        return ((3 if look in s["looks"] else 0)
                + (4 if festive and s["festive"] else 0)
                - (5 if s["festive"] and not festive else 0)
                + (1 if s["id"].startswith("photo-") else 0)
                + rng.random())
    return max(pool, key=score)


def render(scene: dict, w: int, h: int, look: str = "clean",
           palette: str = "", seed: int = 0) -> tuple[Image.Image, dict]:
    """The empty set at w x h, and where a product goes in it."""
    if scene.get("file"):
        img, lay = _render_photo(scene, w, h)
    else:
        rng = np.random.default_rng(seed)
        img, lay = scene["draw"](w, h, rng, look, palette_colours(palette))
    return img, {**lay, "stage": scene["stage"], "scene": scene["id"],
                 "label": scene["label"], "ai_made": bool(scene.get("ai_made"))}
