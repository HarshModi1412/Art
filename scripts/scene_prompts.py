"""
Write the prompt sheet for the scene backdrop library, and say which images
are already in place.

The backdrops are generated ONCE, by hand, in any image tool, from these
prompts, and saved as backend/static/scenes/<id>.jpg. After that every scene
picture the app makes is free. The list lives in
backend/static/scenes/manifest.json; this only formats it.

Run: python scripts/scene_prompts.py      (writes docs/scene-library-prompts.md)
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENES = ROOT / "backend" / "static" / "scenes"
OUT = ROOT / "docs" / "scene-library-prompts.md"

GROUPS = [
    ("stand", "", "Standing products (bottles, jars, boxes, bags, shoes, decor)"),
    ("flat", "", "Flat-lays, camera overhead (jewellery, folded clothes, fabric)"),
    ("hang", "", "Hanging (clothes on a hanger)"),
    ("palm", "", "Person: product on a palm"),
    ("neck", "", "Person: wearing a necklace"),
    ("ear", "", "Person: wearing earrings"),
    ("beside", "", "Person: in the background, product on the table in front"),
    ("mannequin", "", "Clothing: on a dress form"),
    ("held", "", "Clothing: a model holding it up by the hanger"),
    ("model", "", "Clothing: models for the AI try-on (3:4, not 9:16)"),
]

# Try-on model photos are 3:4 and show a whole person; the backdrop suffix
# (an empty spot, 9:16) does not fit them.
MODEL_SUFFIX = ("Photorealistic fashion catalogue photography, sharp focus, vertical 3:4 frame. "
                "Nothing in the hands, no bag, no jewellery, no jacket over the top. "
                "No text, no logo, no watermark.")


def have(tid: str) -> str:
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        if (SCENES / f"{tid}{ext}").exists():
            return f"{tid}{ext}"
    return ""


def main() -> int:
    m = json.loads((SCENES / "manifest.json").read_text(encoding="utf-8"))
    variants = [t for t in m["templates"] if t.get("variant_of")]
    rows = [t for t in m["templates"] if not t.get("variant_of")]
    takes = {t["id"]: 1 if have(t["id"]) else 0 for t in rows}
    for v in variants:
        if have(v["id"]):
            takes[v["variant_of"]] = takes.get(v["variant_of"], 0) + 1
    done = [t for t in rows if have(t["id"]) and not t.get("redo")]
    lines = [
        "# Scene backdrop library: prompts",
        "",
        "Generate each image **once**, in any image tool, and save it into "
        "`backend/static/scenes/` with **exactly** the file name shown (`.jpg`, `.png` or "
        "`.webp` all work). After that, every scene picture the app makes is free.",
        "",
        "**Settings:** vertical **9:16** (the try-on models at the end are **3:4**), the "
        "highest resolution your tool offers. Photorealistic.",
        "",
        "**Check before saving:** the empty spot (podium top, table centre, palm, neckline, "
        "earlobe, hook) must really be empty. If the tool put a bottle or a necklace there, "
        "generate again. People's faces should be out of frame where the prompt says so.",
        "",
        f"**Progress:** {len(done)} of {len(rows)} saved.",
        "",
    ]
    for stage, _, title in GROUPS:
        group = [t for t in rows if (t.get("pose") == "beside") == (stage == "beside")
                 and (t["stage"] == stage or stage == "beside")]
        if not group:
            continue
        lines += [f"## {title}", ""]
        for t in group:
            n = takes.get(t["id"], 0)
            mark = ("REDO" if t.get("redo") else
                    f"done, {n} take{'s' if n != 1 else ''}" if n else "to do")
            suffix = MODEL_SUFFIX if t.get("aspect") == "3:4" else m["suffix"]
            lines += [f"### `{t['id']}.jpg` ({mark}, {t.get('aspect', '9:16')})", ""]
            if t.get("redo"):
                lines += [f"> **{t['redo']}**", ""]
            lines += ["```", f"{t['prompt']} {suffix}", "```", ""]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(done)}/{len(rows)} backdrops saved. Prompt sheet: {OUT.relative_to(ROOT)}")
    missing = [t["id"] for t in rows if not have(t["id"]) or t.get("redo")]
    if missing:
        print("still to generate or redo:", ", ".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
