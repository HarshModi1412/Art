"""Bring the founder's generated brand images into the app.

The images were made from BRAND_IMAGE_PROMPTS.md and saved under the names
the image tool chose ("Hands_resting_on_stone_surface_<timestamp>.jpg"). This
maps each one, by its timestamp, to a direction and an asset, cleans it and
writes it where the Brand Management module looks:

    Smart CafeX/brand-assets/<direction>/<asset>.webp

What "clean" means depends on the asset:

  * photos (post-bg, story-bg, hero, packaging, mood-*): the image tool's
    sparkle watermark is painted out, the picture is resized and saved as WebP
    under 300 KB.
  * texture: made a light greyscale, so the module can multiply it over any
    background colour.
  * pattern and motif: turned into a STENCIL (black with an alpha channel).
    The module paints the stencil in the seller's own accent colour, so a
    pattern made in Stone still matches a seller who picked Noir or edited a
    swatch.

Run: python scripts/import_brand_images.py ["D:/Claude/Brand Image"] [--only=texture]
"""
import os
import re
import sys

import cv2
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, "Smart CafeX", "brand-assets")
_args = [a for a in sys.argv[1:] if not a.startswith("--only=")]
ONLY = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--only=")), "")
SRC = _args[0] if _args else os.path.join(os.path.dirname(ROOT), "Brand Image")
MAX_BYTES = 300 * 1024

# timestamp in the file name -> (direction, asset). Read from contact sheets of
# all 133 files; three near-duplicates are left out on purpose (093539 a second
# Heritage Maison perfume shot, 094143 the Soft Romantic pattern again, 094016
# the Calm & Airy story again).
MAP = {
    # Quiet Luxury
    "093424": ("quiet_luxury", "texture"), "093427": ("quiet_luxury", "mood-jewellery"),
    "093429": ("quiet_luxury", "mood-fragrance"), "093433": ("quiet_luxury", "packaging"),
    "093434": ("quiet_luxury", "hero"), "093437": ("quiet_luxury", "story-bg"),
    "093439": ("quiet_luxury", "mood-home_decor"), "093441": ("quiet_luxury", "mood-clothing"),
    "093447": ("quiet_luxury", "post-bg"), "093449": ("quiet_luxury", "motif"),
    "093451": ("quiet_luxury", "pattern"),
    # Heritage Maison
    "093454": ("heritage_maison", "hero"), "093456": ("heritage_maison", "motif"),
    "093458": ("heritage_maison", "texture"), "093503": ("heritage_maison", "packaging"),
    "093505": ("heritage_maison", "story-bg"), "093507": ("heritage_maison", "mood-clothing"),
    "093510": ("heritage_maison", "mood-home_decor"), "093514": ("heritage_maison", "mood-jewellery"),
    "093519": ("heritage_maison", "pattern"), "093524": ("heritage_maison", "post-bg"),
    "093526": ("heritage_maison", "mood-fragrance"),
    # Modern Minimal (no texture was generated)
    "093529": ("modern_minimal", "mood-clothing"), "093531": ("modern_minimal", "motif"),
    "093541": ("modern_minimal", "mood-jewellery"), "093544": ("modern_minimal", "hero"),
    "093548": ("modern_minimal", "mood-fragrance"), "093553": ("modern_minimal", "story-bg"),
    "093555": ("modern_minimal", "pattern"), "093557": ("modern_minimal", "post-bg"),
    "093600": ("modern_minimal", "mood-home_decor"), "093602": ("modern_minimal", "packaging"),
    # Everyday Bright (no pattern was generated)
    "093606": ("everyday_bright", "motif"), "093608": ("everyday_bright", "packaging"),
    "093610": ("everyday_bright", "hero"), "093612": ("everyday_bright", "mood-jewellery"),
    "093615": ("everyday_bright", "mood-clothing"), "093617": ("everyday_bright", "mood-fragrance"),
    "093621": ("everyday_bright", "texture"), "093623": ("everyday_bright", "story-bg"),
    "093627": ("everyday_bright", "post-bg"), "093630": ("everyday_bright", "mood-home_decor"),
    # Playful Pop
    "093634": ("playful_pop", "texture"), "093639": ("playful_pop", "story-bg"),
    "093647": ("playful_pop", "hero"), "093702": ("playful_pop", "mood-home_decor"),
    "093704": ("playful_pop", "mood-clothing"), "093712": ("playful_pop", "post-bg"),
    "093751": ("playful_pop", "motif"), "093754": ("playful_pop", "packaging"),
    "093756": ("playful_pop", "pattern"), "093758": ("playful_pop", "mood-jewellery"),
    "093804": ("playful_pop", "mood-fragrance"),
    # Street Edge
    "093633": ("street_edge", "pattern"), "093636": ("street_edge", "motif"),
    "093645": ("street_edge", "texture"), "093654": ("street_edge", "hero"),
    "093658": ("street_edge", "packaging"), "093710": ("street_edge", "mood-clothing"),
    "093740": ("street_edge", "mood-jewellery"), "093749": ("street_edge", "post-bg"),
    "093802": ("street_edge", "story-bg"),
    # Soft Romantic
    "093403": ("soft_romantic", "pattern"), "093649": ("soft_romantic", "texture"),
    "093652": ("soft_romantic", "hero"), "093700": ("soft_romantic", "story-bg"),
    "093706": ("soft_romantic", "post-bg"), "093806": ("soft_romantic", "mood-jewellery"),
    "093814": ("soft_romantic", "motif"), "093859": ("soft_romantic", "mood-clothing"),
    "093906": ("soft_romantic", "mood-fragrance"), "093916": ("soft_romantic", "mood-home_decor"),
    "093924": ("soft_romantic", "packaging"),
    # Artisan Earth
    "093809": ("artisan_earth", "post-bg"), "093816": ("artisan_earth", "mood-home_decor"),
    "093822": ("artisan_earth", "pattern"), "093826": ("artisan_earth", "hero"),
    "093833": ("artisan_earth", "packaging"), "093855": ("artisan_earth", "texture"),
    "093857": ("artisan_earth", "mood-jewellery"), "093909": ("artisan_earth", "story-bg"),
    "093912": ("artisan_earth", "mood-clothing"), "093918": ("artisan_earth", "mood-fragrance"),
    "093919": ("artisan_earth", "motif"),
    # Modern Heritage
    "093800": ("modern_heritage", "pattern"), "093811": ("modern_heritage", "hero"),
    "093819": ("modern_heritage", "texture"), "093829": ("modern_heritage", "story-bg"),
    "093902": ("modern_heritage", "packaging"), "093905": ("modern_heritage", "post-bg"),
    "093928": ("modern_heritage", "motif"), "093935": ("modern_heritage", "mood-home_decor"),
    "093946": ("modern_heritage", "mood-fragrance"), "093950": ("modern_heritage", "mood-jewellery"),
    "093958": ("modern_heritage", "mood-clothing"),
    # Apothecary
    "093933": ("apothecary", "pattern"), "093938": ("apothecary", "packaging"),
    "093939": ("apothecary", "mood-home_decor"), "093944": ("apothecary", "hero"),
    "093949": ("apothecary", "story-bg"), "093955": ("apothecary", "mood-fragrance"),
    "093956": ("apothecary", "motif"), "094008": ("apothecary", "post-bg"),
    "094141": ("apothecary", "texture"),
    # Calm & Airy (pattern, motif and the four moods were not generated)
    "093926": ("calm_airy", "texture"), "093942": ("calm_airy", "post-bg"),
    "093952": ("calm_airy", "hero"), "094001": ("calm_airy", "packaging"),
    "094010": ("calm_airy", "story-bg"),
    # Bold Maximal
    "094025": ("bold_maximal", "pattern"), "094030": ("bold_maximal", "mood-fragrance"),
    "094033": ("bold_maximal", "packaging"), "094040": ("bold_maximal", "texture"),
    "094053": ("bold_maximal", "hero"), "094107": ("bold_maximal", "mood-clothing"),
    "094110": ("bold_maximal", "mood-home_decor"), "094120": ("bold_maximal", "post-bg"),
    "094124": ("bold_maximal", "motif"), "094133": ("bold_maximal", "story-bg"),
    "094139": ("bold_maximal", "mood-jewellery"),
    # Classic Timeless (no pattern was generated)
    "094020": ("classic_timeless", "mood-home_decor"), "094035": ("classic_timeless", "mood-jewellery"),
    "094037": ("classic_timeless", "motif"), "094042": ("classic_timeless", "story-bg"),
    "094044": ("classic_timeless", "hero"), "094047": ("classic_timeless", "packaging"),
    "094049": ("classic_timeless", "texture"), "094116": ("classic_timeless", "mood-clothing"),
    "094128": ("classic_timeless", "mood-fragrance"), "094136": ("classic_timeless", "post-bg"),
}
SKIPPED = {"093539", "094143", "094016"}
MAX_SIDE = {"hero": 1600, "story-bg": 1376, "post-bg": 1400, "packaging": 1200,
            "texture": 1024, "pattern": 1024, "motif": 768}


def unwatermark(rgb: np.ndarray) -> np.ndarray:
    """Paint out the image tool's sparkle: a soft four-point star about 98 px
    in from the bottom-right corner on every size it produces."""
    h, w = rgb.shape[:2]
    cx, cy = w - 98, h - 98
    mask = np.zeros((h, w), np.uint8)
    pts = []
    for k in range(8):
        r = 36 if k % 2 == 0 else 11
        a = -np.pi / 2 + k * np.pi / 4
        pts.append((cx + r * np.cos(a), cy + r * np.sin(a)))
    cv2.fillPoly(mask, [np.array(pts, np.int32)], 255)
    mask = cv2.dilate(mask, np.ones((7, 7), np.uint8))
    return cv2.inpaint(rgb, mask, 9, cv2.INPAINT_TELEA)


def fit(img: Image.Image, side: int) -> Image.Image:
    img = img.copy()
    img.thumbnail((side, side), Image.LANCZOS)
    return img


def save_webp(img: Image.Image, path: str) -> int:
    """Under 300 KB: lower the quality first, then the size. A dense stencil
    keeps its alpha losslessly, so for those only a smaller tile helps."""
    while True:
        for q in (82, 76, 70, 62, 54, 46):
            img.save(path, "WEBP", quality=q, method=6)
            if os.path.getsize(path) <= MAX_BYTES:
                return os.path.getsize(path)
        if max(img.size) <= 512:
            return os.path.getsize(path)
        img = img.resize((int(img.width * 0.85), int(img.height * 0.85)), Image.LANCZOS)


def texture(rgb: np.ndarray) -> Image.Image:
    """Light greyscale: 0..1 detail mapped onto 217..255, so multiplying it
    over a background colour adds a fine grain without darkening the colour
    or competing with the logo set on top of it."""
    g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    lo, hi = np.percentile(g, 2), np.percentile(g, 98)
    n = np.clip((g - lo) / max(1.0, hi - lo), 0, 1)
    out = 255 - (1 - n) * 38
    return Image.fromarray(out.astype(np.uint8), "L").convert("RGB")


def stencil(rgb: np.ndarray, kind: str) -> Image.Image:
    """Black with alpha. For a pattern the ink is the dark parts; for a motif
    it is whatever differs from the plain background around the edges."""
    if kind == "pattern":
        g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
        lo, hi = np.percentile(g, 1), np.percentile(g, 99)
        dark = 1 - np.clip((g - lo) / max(1.0, hi - lo), 0, 1)
        alpha = np.clip((dark - 0.08) / 0.8, 0, 1)
    else:
        h, w = rgb.shape[:2]
        e = 12
        border = np.concatenate([rgb[:e].reshape(-1, 3), rgb[-e:].reshape(-1, 3),
                                 rgb[:, :e].reshape(-1, 3), rgb[:, -e:].reshape(-1, 3)])
        bg = np.median(border, axis=0)
        dist = np.sqrt(((rgb.astype(np.float32) - bg) ** 2).sum(axis=2))
        alpha = np.clip((dist - 18) / 60, 0, 1)
    a = (alpha * 255).astype(np.uint8)
    out = np.zeros((*a.shape, 4), np.uint8)
    out[..., 3] = a
    return Image.fromarray(out, "RGBA")


def main() -> None:
    if not os.path.isdir(SRC):
        sys.exit(f"No folder at {SRC}")
    files = {}
    for f in os.listdir(SRC):
        m = re.search(r"_\d{8}(\d{6})\.(jpe?g|png|webp)$", f, re.I)
        if m:
            files[m.group(1)] = f
    done, missing_src = [], []
    for ts, (did, asset) in MAP.items():
        if ONLY and asset != ONLY:
            continue
        f = files.get(ts)
        if not f:
            missing_src.append(ts)
            continue
        rgb = np.array(Image.open(os.path.join(SRC, f)).convert("RGB"))
        rgb = unwatermark(rgb)
        if asset == "texture":
            img = texture(rgb)
        elif asset in ("pattern", "motif"):
            img = stencil(rgb, asset)
        else:
            img = Image.fromarray(rgb)
        img = fit(img, MAX_SIDE.get(asset, 1400))
        os.makedirs(os.path.join(DEST, did), exist_ok=True)
        for old in os.listdir(os.path.join(DEST, did)):
            if os.path.splitext(old)[0] == asset:
                os.remove(os.path.join(DEST, did, old))
        path = os.path.join(DEST, did, asset + ".webp")
        size = save_webp(img, path)
        done.append((did, asset, img.size, size // 1024))
    for did in sorted({d for d, _ in MAP.values()}):
        keep = os.path.join(DEST, did, ".gitkeep")
        if os.path.exists(keep) and len(os.listdir(os.path.join(DEST, did))) > 1:
            os.remove(keep)
    unused = sorted(set(files) - set(MAP) - SKIPPED)
    print(f"Wrote {len(done)} images to {DEST}")
    print(f"Largest: {max(done, key=lambda r: r[3])}")
    if missing_src:
        print("Mapped but not found:", missing_src)
    if unused:
        print("Found but not mapped:", unused)


if __name__ == "__main__":
    main()
