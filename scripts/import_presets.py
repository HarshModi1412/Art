"""
Import the hand-generated backdrops from D:/Claude/Preset into the scene
library (backend/static/scenes/), one-off.

Each Preset image was generated from a prompt in docs/scene-library-prompts.md
but saved under the generator's own descriptive name. MAP below says which
template each one is, read by eye: its design (checked against the picture,
not just the prompt, so a "serious" set never carries playful colour), and
where the product attaches (anchor/box, fractions of the image). The second
take of a prompt becomes a variant "<id>-2" with its own anchor, so posts
rotate between them.

Rejected on review (not imported), see REJECTED: the four woman's-palm
images (hand raised upright like a wave, nothing can rest on it) and both
"holding it up" images (the hand is beside the face, so a hung garment covers
the face). Those templates carry a "redo" note in the prompt sheet.

Run: python scripts/import_presets.py [preset_dir]
"""
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCENES = ROOT / "backend" / "static" / "scenes"
SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "D:/Claude/Preset")

# preset index (sorted file order) -> (template id, design, anchor, box, extra)
MAP = {
    # stand: base point of the product on the surface
    21: ("stand-studio-1", "studio", (0.50, 0.86), (0.50, 0.46), {}),
    24: ("stand-studio-1", "studio", (0.50, 0.82), (0.50, 0.46), {}),
    8:  ("stand-studio-2", "studio", (0.50, 0.535), (0.46, 0.40), {}),
    14: ("stand-studio-2", "studio", (0.50, 0.505), (0.40, 0.38), {}),
    18: ("stand-marble-1", "marble", (0.50, 0.55), (0.50, 0.40), {}),
    23: ("stand-marble-1", "marble", (0.50, 0.575), (0.48, 0.40), {}),
    19: ("stand-marble-2", "marble", (0.50, 0.80), (0.48, 0.44), {"gloss": True}),
    50: ("stand-marble-2", "marble", (0.50, 0.77), (0.48, 0.44), {"gloss": True}),
    12: ("stand-dark-1", "dark", (0.50, 0.505), (0.48, 0.40), {"gloss": True}),
    13: ("stand-dark-1", "dark", (0.50, 0.53), (0.46, 0.40), {"gloss": True}),
    22: ("stand-dark-2", "dark", (0.50, 0.58), (0.42, 0.44), {"gloss": True}),
    57: ("stand-dark-2", "dark", (0.46, 0.62), (0.42, 0.44), {"gloss": True}),
    25: ("stand-wood-1", "wood", (0.56, 0.76), (0.48, 0.44), {}),
    83: ("stand-wood-1", "wood", (0.60, 0.72), (0.46, 0.44), {}),
    6:  ("stand-wood-2", "wood", (0.42, 0.74), (0.46, 0.44), {}),
    58: ("stand-wood-2", "wood", (0.42, 0.68), (0.42, 0.40), {"crop_bottom": 0.09}),
    29: ("stand-nature-1", "nature", (0.47, 0.63), (0.42, 0.40), {}),
    45: ("stand-nature-1", "nature", (0.47, 0.60), (0.42, 0.40), {}),
    54: ("stand-nature-2", "nature", (0.52, 0.55), (0.42, 0.40), {}),
    55: ("stand-nature-2", "nature", (0.44, 0.54), (0.42, 0.40), {}),
    9:  ("stand-festive-1", "festive", (0.50, 0.72), (0.40, 0.42), {"gloss": True}),
    10: ("stand-festive-1", "festive", (0.55, 0.72), (0.38, 0.42), {"gloss": True}),
    26: ("stand-festive-2", "festive", (0.42, 0.66), (0.42, 0.40), {}),
    27: ("stand-festive-2", "festive", (0.52, 0.66), (0.42, 0.40), {}),
    47: ("stand-pastel-1", "pastel", (0.50, 0.62), (0.42, 0.40), {}),
    48: ("stand-pastel-1", "pastel", (0.50, 0.615), (0.46, 0.40), {}),
    28: ("stand-pastel-2", "pastel", (0.50, 0.475), (0.46, 0.38), {}),
    44: ("stand-pastel-2", "pastel", (0.50, 0.485), (0.46, 0.38), {}),
    # flat: centre of the empty area
    20: ("flat-studio-1", "studio", (0.50, 0.52), (0.62, 0.42), {}),
    59: ("flat-studio-1", "studio", (0.50, 0.48), (0.62, 0.42), {}),
    0:  ("flat-studio-2", "studio", (0.50, 0.50), (0.62, 0.42), {}),
    1:  ("flat-studio-2", "studio", (0.50, 0.50), (0.62, 0.42), {}),
    42: ("flat-marble-1", "marble", (0.46, 0.55), (0.62, 0.42), {}),
    43: ("flat-marble-1", "marble", (0.46, 0.55), (0.62, 0.42), {}),
    2:  ("flat-dark-1", "dark", (0.50, 0.50), (0.62, 0.42), {}),
    3:  ("flat-dark-1", "dark", (0.50, 0.50), (0.62, 0.42), {}),
    17: ("flat-wood-1", "wood", (0.55, 0.40), (0.58, 0.40), {}),
    31: ("flat-wood-1", "wood", (0.55, 0.42), (0.58, 0.40), {}),
    52: ("flat-nature-1", "nature", (0.55, 0.50), (0.60, 0.42), {}),
    53: ("flat-nature-1", "nature", (0.48, 0.50), (0.60, 0.42), {}),
    51: ("flat-festive-1", "festive", (0.50, 0.40), (0.58, 0.36), {}),
    56: ("flat-festive-1", "festive", (0.55, 0.42), (0.54, 0.38), {}),
    46: ("flat-pastel-1", "pastel", (0.55, 0.58), (0.60, 0.42), {}),
    49: ("flat-pastel-1", "pastel", (0.45, 0.58), (0.60, 0.42), {}),
    # hang: the hook or rail the garment's hanger goes on
    4:  ("hang-studio-1", "studio", (0.48, 0.37), (0.58, 0.58), {}),
    5:  ("hang-studio-1", "studio", (0.50, 0.25), (0.58, 0.66), {}),
    81: ("hang-wood-1", "wood", (0.38, 0.245), (0.50, 0.62), {}),
    82: ("hang-wood-1", "wood", (0.38, 0.205), (0.50, 0.62), {}),
    15: ("hang-festive-1", "festive", (0.50, 0.29), (0.52, 0.62), {}),
    16: ("hang-festive-1", "festive", (0.50, 0.26), (0.52, 0.62), {}),
    # palm: where the product's base rests in the hand
    7:  ("palm-hands-1", "nature", (0.50, 0.53), (0.36, 0.28), {"person": "hands"}),
    30: ("palm-hands-1", "nature", (0.62, 0.57), (0.30, 0.25), {"person": "hands"}),
    35: ("palm-man-1", "studio", (0.60, 0.56), (0.26, 0.26), {"person": "man"}),
    36: ("palm-man-1", "studio", (0.50, 0.55), (0.28, 0.26), {"person": "man"}),
    # ear: the earlobe the earring hangs from
    66: ("ear-woman-1", "studio", (0.53, 0.455), (0.16, 0.24), {"person": "woman"}),
    68: ("ear-woman-1", "studio", (0.46, 0.42), (0.16, 0.24), {"person": "woman"}),
    61: ("ear-woman-2", "festive", (0.47, 0.485), (0.18, 0.26), {"person": "woman"}),
    # neck: centre of the neck where it meets the shoulders
    75: ("neck-woman-1", "studio", (0.50, 0.30), (0.54, 0.26), {"person": "woman"}),
    76: ("neck-woman-1", "studio", (0.50, 0.31), (0.54, 0.26), {"person": "woman"}),
    77: ("neck-woman-2", "festive", (0.48, 0.30), (0.50, 0.20), {"person": "woman"}),
    78: ("neck-woman-2", "festive", (0.48, 0.33), (0.48, 0.18), {"person": "woman"}),
    79: ("neck-woman-3", "studio", (0.52, 0.33), (0.50, 0.32), {"person": "woman"}),
    80: ("neck-woman-3", "wood", (0.50, 0.36), (0.50, 0.30), {"person": "woman"}),
    # next to a person: base point on the table in front of them
    69: ("beside-woman-1", "wood", (0.62, 0.82), (0.32, 0.30), {"person": "woman", "pose": "beside"}),
    70: ("beside-woman-2", "marble", (0.33, 0.67), (0.28, 0.28), {"person": "woman", "pose": "beside"}),
    71: ("beside-woman-2", "marble", (0.72, 0.65), (0.30, 0.28), {"person": "woman", "pose": "beside"}),
    38: ("beside-man-1", "wood", (0.45, 0.80), (0.32, 0.30), {"person": "man", "pose": "beside"}),
    39: ("beside-man-1", "wood", (0.55, 0.78), (0.32, 0.30), {"person": "man", "pose": "beside"}),
    32: ("beside-man-2", "dark", (0.50, 0.80), (0.32, 0.30), {"person": "man", "pose": "beside", "gloss": True}),
    33: ("beside-man-2", "dark", (0.50, 0.80), (0.32, 0.30), {"person": "man", "pose": "beside", "gloss": True}),
    # dress forms: centre of the shoulder line
    41: ("mannequin-woman-1", "studio", (0.50, 0.26), (0.46, 0.42), {"person": "mannequin"}),
    11: ("mannequin-woman-2", "festive", (0.49, 0.205), (0.50, 0.50), {"person": "mannequin"}),
    60: ("mannequin-man-1", "dark", (0.50, 0.28), (0.72, 0.48), {"person": "mannequin"}),
    # try-on models (3:4): no anchor, the try-on dresses the whole person
    73: ("model-woman-1", "studio", (0.5, 0.5), (1, 1), {"person": "woman"}),
    72: ("model-woman-2", "wood", (0.5, 0.5), (1, 1), {"person": "woman"}),
    74: ("model-woman-3", "nature", (0.5, 0.5), (1, 1), {"person": "woman"}),
    37: ("model-man-1", "studio", (0.5, 0.5), (1, 1), {"person": "man"}),
    40: ("model-man-2", "dark", (0.5, 0.5), (1, 1), {"person": "man"}),
}
PALM_REDO = ("Regenerate: the hand came out raised upright like a wave. It must be held "
             "out flat, palm facing UP, so a product can rest on it.")
HELD_REDO = ("Regenerate: the raised hand is right beside the face, so any garment hung "
             "from it covers the face. The arm must be held out to the SIDE at shoulder "
             "height, hand well away from the face, with the space below the hand empty.")
REJECTED = {62: ("palm-woman-2", PALM_REDO), 63: ("palm-woman-1", PALM_REDO),
            65: ("palm-woman-1", PALM_REDO), 67: ("palm-woman-2", PALM_REDO),
            64: ("held-woman-1", HELD_REDO), 34: ("held-man-1", HELD_REDO)}


def main() -> int:
    files = sorted(SRC.glob("*.jpg"))
    man_path = SCENES / "manifest.json"
    man = json.loads(man_path.read_text(encoding="utf-8"))
    base = {t["id"]: t for t in man["templates"] if not t.get("variant_of")}
    seen: dict = {}
    variants = []
    for i, f in enumerate(files):
        if i not in MAP:
            print(f"skip #{i} {f.name}" + (f" (rejected for {REJECTED[i][0]})" if i in REJECTED else ""))
            continue
        tid, design, anchor, box, extra = MAP[i]
        n = seen[tid] = seen.get(tid, 0) + 1
        out_id = tid if n == 1 else f"{tid}-{n}"
        img = Image.open(f).convert("RGB")
        if extra.get("crop_bottom"):
            img = img.crop((0, 0, img.width, int(img.height * (1 - extra["crop_bottom"]))))
        img.save(SCENES / f"{out_id}.jpg", quality=92)
        fields = {"design": design, "anchor": list(anchor), "box": list(box),
                  "source": f.name, "gloss": bool(extra.get("gloss", base[tid].get("gloss")))}
        if "person" in extra:
            fields["person"] = extra["person"]
        if n == 1:
            base[tid].update(fields)
        else:
            v = {k: v for k, v in base[tid].items() if k not in ("prompt",)}
            v.update(fields)
            v.update({"id": out_id, "variant_of": tid})
            variants.append(v)
    for tid, why in REJECTED.values():
        base[tid]["redo"] = why
    man["templates"] = list(base.values()) + variants
    man_path.write_text(json.dumps(man, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"imported {sum(seen.values())} images into {len(seen)} templates "
          f"({len(variants)} second takes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
