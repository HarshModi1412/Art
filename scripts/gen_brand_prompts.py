"""Write BRAND_IMAGE_PROMPTS.md from the Brand Management library.

Every prompt is built from backend/core/brandkit.py, so the colours, light and
mood in a prompt are the ones the app shows for that direction. Change a
palette there, run this again, and the prompts follow.

Two rules every prompt carries:
  * No text of any kind. The brand name is typeset by the app, never drawn by
    the image model (models misspell; a misspelt logo is the home-grown look
    the module exists to remove).
  * No brand names. "In the spirit of" references stay in the app's UI.

Run: python scripts/gen_brand_prompts.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core import brandkit as bk  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "BRAND_IMAGE_PROMPTS.md")

NO_TEXT = ("Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or "
           "signatures anywhere in the image. No people's faces.")

# Per direction: a surface for the tileable texture, a motif for the repeat
# pattern, and a shape for the decorative motif. Kept here, not in the app
# library, because only image generation uses them.
EXTRA = {
    "quiet_luxury":    ("fine lime plaster wall", "very fine, widely spaced pinstripe lines",
                        "a single thin arch outline"),
    "heritage_maison": ("silk damask fabric", "small symmetrical medallion damask",
                        "an ornate symmetrical crest shape without any letters"),
    "modern_minimal":  ("smooth heavyweight matte paper", "thin precise grid lines",
                        "a single bold geometric square rotated slightly"),
    "everyday_bright": ("fine cotton canvas", "simple evenly spaced polka dots",
                        "a cheerful rounded star shape"),
    "playful_pop":     ("glossy terrazzo with large chips", "playful squiggles and soft blobs",
                        "a chunky wavy flower shape"),
    "street_edge":     ("rough poured concrete", "halftone dots fading into diagonal stripes",
                        "a sharp angular lightning bolt shape"),
    "soft_romantic":   ("crushed silk", "tiny scattered flowers and dots",
                        "a delicate looping ribbon bow"),
    "artisan_earth":   ("rough rag paper with visible fibres", "loose drawn leaf and seed shapes",
                        "a rounded pebble shape with a soft inner ring"),
    "modern_heritage": ("block printed cotton", "block print paisley and small florals",
                        "a lotus-like symmetrical flower shape"),
    "apothecary":      ("kraft paper", "a fine dotted grid like a lab notebook page",
                        "a simple botanical sprig drawn with a single line"),
    "calm_airy":       ("rice paper with long fibres", "loose brush-stroke circles",
                        "a single open brush circle"),
    "bold_maximal":    ("crushed velvet", "lush leaves, fruit and birds",
                        "a dramatic sunburst"),
    "classic_timeless": ("herringbone wool", "small regular foulard diamonds",
                         "a laurel wreath without any letters inside"),
}

MOOD = {
    "jewellery": "a pair of hands resting on the surface, wearing a simple ring and a fine chain, cropped at the wrists",
    "clothing": "a softly folded garment and a garment on a plain hanger, no labels or tags visible",
    "fragrance": "an unlabelled glass perfume bottle with a plain cap, with one or two small props",
    "home_decor": "a quiet corner of a room with a vase, a few books with blank spines and a draped throw",
}

ASSETS = [
    # key, size, aspect, what it is for, greyscale?
    ("post-bg", "1080 × 1350", "4:5 portrait", "Background for feed posts. Text sits in the lower 40%.", False),
    ("story-bg", "1080 × 1920", "9:16 portrait", "Background for Instagram stories. Name at the top, text at the bottom.", False),
    ("hero", "2400 × 1350", "16:9 landscape", "Website hero and the direction card. The name sits in the centre.", False),
    ("texture", "2048 × 2048", "1:1 square", "Tileable surface. Tinted to any palette by the app.", True),
    ("pattern", "2048 × 2048", "1:1 square", "Seamless repeat for packaging and posts. Tinted by the app.", True),
    ("packaging", "1600 × 1600", "1:1 square", "Packaging inspiration. Shown as a picture only, never printed on.", False),
    ("motif", "1024 × 1024", "1:1 square", "Decoration only. Never use it as a logo or monogram.", False),
]


def _palette_line(p: dict) -> str:
    c = p["colours"]
    return (f"Colour palette ({p['name']}): background {c['ground']}, panels {c['surface']}, "
            f"deep tone {c['ink']}, accent {c['accent']}, support {c['support']}.")


def prompts_for(d: dict) -> list[dict]:
    p = d["palettes"][0]
    c = p["colours"]
    style = d["prompt_style"]
    tex, pat, motif = EXTRA[d["id"]]
    pal = _palette_line(p)
    out = [
        {"key": "post-bg", "prompt":
            f"{style}. Abstract background for a social media post, portrait 4:5, no product. "
            f"Keep the lower 40% of the frame calm, plain and evenly lit in {c['ground']} with nothing in it; "
            f"place soft shapes, surfaces and shadows in the upper 60%. {pal} {NO_TEXT}"},
        {"key": "story-bg", "prompt":
            f"{style}. Abstract vertical background, portrait 9:16, no product. Keep the top 15% and the "
            f"bottom 35% calm and plain in {c['ground']}; put the visual interest in the middle. {pal} {NO_TEXT}"},
        {"key": "hero", "prompt":
            f"{style}. Wide website hero background, landscape 16:9, no product. Leave the centre third calm "
            f"and empty so a name can sit on it; let surfaces, light and shadow fill the edges. {pal} {NO_TEXT}"},
        {"key": "texture", "prompt":
            f"Seamless tileable texture of {tex}, photographed flat and straight on, even shadowless light, "
            f"black and white only (greyscale), medium contrast, square 1:1, edges that tile without seams. "
            f"No objects. {NO_TEXT}"},
        {"key": "pattern", "prompt":
            f"Seamless repeating pattern of {pat}, flat graphic design, black and white only (greyscale), "
            f"evenly spaced, square 1:1, edges that tile without seams, refined and balanced. {NO_TEXT}"},
        {"key": "packaging", "prompt":
            f"{style}. Product packaging set shot front-on and centred: a rigid gift box with its lid beside it, "
            f"a paper shopping bag, folded tissue paper and a small swing tag on a string. Every item is "
            f"completely blank and unprinted, in tones of {c['ground']} and {c['accent']} with {c['support']} details, "
            f"on a {c['surface']} surface. {pal} {NO_TEXT}"},
        {"key": "motif", "prompt":
            f"{motif}, flat vector-style graphic, a single colour {c['accent']} on a plain {c['ground']} "
            f"background, centred with a generous margin, crisp clean edges, square 1:1. Nothing that looks "
            f"like a letter or a number. {NO_TEXT}"},
    ]
    for cat in d["categories"]:
        out.append({"key": f"mood-{cat}", "prompt":
            f"{style}. Lifestyle photograph, portrait 4:5: {MOOD[cat]}. "
            f"{bk.fill(d['imagery'][1], bk._slots('', cat, 'intl'))} {pal} {NO_TEXT}"})
    return out


def build() -> str:
    lines = [
        "# Brand image prompts",
        "",
        "Generated from `backend/core/brandkit.py` by `scripts/gen_brand_prompts.py`. Do not edit by hand:",
        "change the library and run the script again.",
        "",
        "## How to use this",
        "",
        "1. Pick a direction below. Generate each image with ChatGPT (or any image model) by pasting the prompt as it is.",
        "2. ChatGPT makes 1024 × 1024, 1024 × 1536 or 1536 × 1024. Generate at the closest shape, then crop and resize to the size in the table (a free tool such as squoosh.app does both and saves WebP).",
        "3. Save each file as `<name>.webp` (or `.jpg`) in `Smart CafeX/brand-assets/<direction id>/`, for example `Smart CafeX/brand-assets/quiet_luxury/post-bg.webp`. Keep each file under 300 KB.",
        "4. Commit the files. The Brand Management module finds them by name on its next load; anything missing is drawn from the palette instead, so you can add images one at a time.",
        "",
        "**The rules every prompt already carries:**",
        "",
        "- **No text in any image.** The app sets the seller's name in real type on top. If an image comes back with letters, signs or labels in it, generate it again.",
        "- **No brand names.** The \"in the spirit of\" names you see in the app are guidance for sellers only.",
        "- **Colours come from the direction's first palette.** The app only shows these photographs while a seller uses that palette; on the other palettes it draws the backgrounds itself, so nothing clashes.",
        "- **`texture` and `pattern` are black and white.** The app tints them to whatever colours the seller picks.",
        "- **`motif` is decoration**, never a logo. Every seller in a direction shares it.",
        "",
        "| File | Size | Shape | What the app uses it for |",
        "|---|---|---|---|",
    ]
    for key, size, shape, use, _grey in ASSETS:
        lines.append(f"| `{key}` | {size} | {shape} | {use} |")
    lines.append(f"| `mood-<category>` | 1200 × 1500 | 4:5 portrait | The photography section of the brand book, one per category the direction supports. |")
    lines += ["", "## Directions", ""]
    for d in bk.DIRECTIONS:
        lines.append(f"- [{d['name']}](#{d['id'].replace('_', '-')}) (`{d['id']}`)")
    for d in bk.DIRECTIONS:
        p = d["palettes"][0]
        lines += [
            "",
            f"<a id=\"{d['id'].replace('_', '-')}\"></a>",
            f"## {d['name']}",
            "",
            f"Folder: `Smart CafeX/brand-assets/{d['id']}/`  ",
            f"{d['essence']}  ",
            f"Categories: {', '.join(d['categories'])}",
            "",
            "| Role | Colour |",
            "|---|---|",
        ]
        for role, label in (("ground", "Background"), ("surface", "Panels"), ("ink", "Deep tone"),
                            ("accent", "Accent"), ("support", "Support")):
            lines.append(f"| {label} | `{p['colours'][role]}` |")
        for item in prompts_for(d):
            lines += ["", f"**`{item['key']}`**", "", "```text", item["prompt"], "```"]
    return "\n".join(lines) + "\n"


def scan(md: str) -> list[str]:
    """Brand names and product claims must never reach an image prompt."""
    problems = []
    blocks = re.findall(r"```text\n(.*?)\n```", md, re.S)
    spirit = {s.split(" (")[0] for d in bk.DIRECTIONS for s in d["spirit"]}
    for b in blocks:
        b = re.sub(r"#[0-9A-Fa-f]{6}", "", b)     # colour codes are not claims
        for s in spirit:
            if s.lower() in b.lower():
                problems.append(f"brand name {s}: {b[:80]}")
        for w in bk.CLAIM_WORDS:
            if re.search(w, b, re.I):
                problems.append(f"claim /{w}/: {b[:80]}")
    return problems


if __name__ == "__main__":
    md = build()
    bad = scan(md)
    if bad:
        print("Refusing to write prompts:\n  " + "\n  ".join(bad[:20]))
        sys.exit(1)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(md)
    root = bk.assets_dir()
    for d in bk.DIRECTIONS:
        folder = os.path.join(root, d["id"])
        os.makedirs(folder, exist_ok=True)
        keep = os.path.join(folder, ".gitkeep")
        if not os.listdir(folder):
            open(keep, "w").close()
    n = md.count("```text")
    print(f"Wrote {OUT} with {n} prompts for {len(bk.DIRECTIONS)} directions; folders ready in {root}")
