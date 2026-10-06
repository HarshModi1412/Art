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
]


def have(tid: str) -> str:
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        if (SCENES / f"{tid}{ext}").exists():
            return f"{tid}{ext}"
    return ""


def main() -> int:
    m = json.loads((SCENES / "manifest.json").read_text(encoding="utf-8"))
    rows = m["templates"]
    done = [t for t in rows if have(t["id"])]
    lines = [
        "# Scene backdrop library: prompts",
        "",
        "Generate each image **once**, in any image tool, and save it into "
        "`backend/static/scenes/` with **exactly** the file name shown (`.jpg`, `.png` or "
        "`.webp` all work). After that, every scene picture the app makes is free.",
        "",
        "**Settings for every image:** vertical **9:16**, the highest resolution your tool "
        "offers (1080 x 1920 or more). Photorealistic.",
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
            mark = "done" if have(t["id"]) else "to do"
            lines += [f"### `{t['id']}.jpg` ({mark})", "", "```", f"{t['prompt']} {m['suffix']}", "```", ""]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(done)}/{len(rows)} backdrops saved. Prompt sheet: {OUT.relative_to(ROOT)}")
    missing = [t["id"] for t in rows if not have(t["id"])]
    if missing:
        print("still to generate:", ", ".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
