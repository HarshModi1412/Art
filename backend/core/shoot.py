"""
Product Studio's "Photo shoot": the seller taps through four questions and
gets a picture of their real product, free, on this server.

    1. What is it?        product type  -> how it rests (stand / flat / hang)
    2. Which design?      studio, marble, dark, wood, nature, festive, pastel
    3. With a person?     no / woman / man / just hands
    4. Which pose?        on the palm, wearing it, next to them
                          (only the poses that work for THIS product type)

Nothing is typed, so nothing is misread. Every answer maps onto the backdrop
library (backend/static/scenes/manifest.json) and the compositor
(composite.py). Options with no backdrop installed yet are reported as such,
so the screen never offers a shoot it cannot do.

The answers are saved on the product (material["shoot"]) when the seller
says "use this style", and the scheduled posts' free scene engine
(studio.scene_image) shoots that product the same way from then on.

WHAT A PERSON CAN AND CANNOT DO HERE
The person is in the backdrop photo, generated once; the product is placed
onto them. So: a product resting on a palm, a necklace at a neckline, an
earring at an earlobe, a product on the table in front of someone. NOT a
garment worn on a body: that needs the cloth to drape, which only a paid GPU
try-on model can do. Clothing types therefore offer no person poses.
"""
from __future__ import annotations

from backend.core import scenes

PRODUCT_TYPES = [
    {"id": "bottle",   "label": "Perfume or attar bottle",   "stage": "stand", "poses": ["palm", "beside"]},
    {"id": "jar",      "label": "Cream, jar or cosmetic",    "stage": "stand", "poses": ["palm", "beside"]},
    {"id": "candle",   "label": "Candle",                    "stage": "stand", "poses": ["palm", "beside"]},
    {"id": "box",      "label": "Box or packaged product",   "stage": "stand", "poses": ["palm", "beside"]},
    {"id": "bag",      "label": "Bag or purse",              "stage": "stand", "poses": ["beside"]},
    {"id": "shoes",    "label": "Shoes",                     "stage": "stand", "poses": ["beside"]},
    {"id": "decor",    "label": "Home decor or vase",        "stage": "stand", "poses": ["beside"]},
    {"id": "necklace", "label": "Necklace or pendant",       "stage": "flat",  "poses": ["neck", "palm"]},
    {"id": "earrings", "label": "Earrings",                  "stage": "flat",  "poses": ["ear", "palm"]},
    {"id": "ring",     "label": "Ring, bangle or bracelet",  "stage": "flat",  "poses": ["palm"]},
    {"id": "folded",   "label": "Clothing, folded or laid flat", "stage": "flat", "poses": []},
    {"id": "hanger",   "label": "Clothing on a hanger",      "stage": "hang",  "poses": []},
    {"id": "fabric",   "label": "Saree, dupatta or scarf",   "stage": "flat",  "poses": []},
    {"id": "other",    "label": "Something else",            "stage": "auto",  "poses": ["beside"]},
]
TYPES = {t["id"]: t for t in PRODUCT_TYPES}

PEOPLE = [
    {"id": "woman", "label": "Woman"},
    {"id": "man",   "label": "Man"},
    {"id": "hands", "label": "Just hands"},
]

POSES = {
    "palm":   {"label": "On the palm",        "hint": "Held out on an open hand",
               "people": ["woman", "man", "hands"]},
    "neck":   {"label": "Wearing it",         "hint": "At the neckline, face out of frame",
               "people": ["woman"]},
    "ear":    {"label": "Wearing it",         "hint": "One earring on the ear, face out of frame",
               "people": ["woman"]},
    "beside": {"label": "Next to them",       "hint": "On the table, the person softly behind",
               "people": ["woman", "man"]},
}

NO_PERSON_NOTE = {
    "folded": "Clothing is shown on its own: putting it ON a person needs a paid "
              "try-on AI, which this free shoot does not use.",
    "hanger": "Clothing is shown on its own: putting it ON a person needs a paid "
              "try-on AI, which this free shoot does not use.",
    "fabric": "Fabric is shown on its own: draping it on a person needs a paid "
              "try-on AI, which this free shoot does not use.",
}


def _stage(type_id: str) -> str:
    return (TYPES.get(type_id) or TYPES["other"])["stage"]


def _photos(stage: str, design: str = "", person: str = "") -> list[dict]:
    return [s for s in scenes.photo_scenes() if s["stage"] == stage
            and (s.get("person") or "") == person
            and (not design or s.get("design") == design)]


def _thumb(s: dict) -> str:
    return f"/static/scenes/{s['file'].name}"


def options(type_id: str = "") -> dict:
    """Everything the shoot screen shows, with what is actually ready.

    For a design: how many real photo backdrops exist for this product's
    stage, and one to preview. A design with none still works (stand and flat
    have drawn fallbacks) but is marked so the seller knows it is basic.
    For people and poses: only those this product type allows AND that have
    at least one backdrop installed."""
    t = TYPES.get(type_id)
    out = {"types": [{"id": x["id"], "label": x["label"]} for x in PRODUCT_TYPES],
           "type": type_id if t else "", "designs": [], "people": [],
           "library": {"installed": len(scenes.photo_scenes()), "total": len(scenes.manifest())}}
    if not t:
        return out
    stage = t["stage"] if t["stage"] != "auto" else "stand"
    for d in scenes.DESIGNS:
        ph = _photos(stage, d["id"])
        drawn = stage in ("stand", "flat")
        out["designs"].append({**d, "photos": len(ph), "ready": bool(ph) or drawn,
                               "basic": not ph, "thumb": _thumb(ph[0]) if ph else ""})
    people = []
    for pid in [p["id"] for p in PEOPLE]:
        poses = []
        for pose_id in t["poses"]:
            pose = POSES[pose_id]
            if pid not in pose["people"]:
                continue
            ph = _photos("stand" if pose_id == "beside" else pose_id, "", pid)
            if pose_id == "beside":
                ph = [s for s in ph if s.get("pose") == "beside"]
            poses.append({"id": pose_id, "label": pose["label"], "hint": pose["hint"],
                          "photos": len(ph), "thumb": _thumb(ph[0]) if ph else ""})
        if poses:
            label = next(p["label"] for p in PEOPLE if p["id"] == pid)
            people.append({"id": pid, "label": label, "poses": poses,
                           "ready": any(p["photos"] for p in poses)})
    out["people"] = people
    out["no_person_note"] = NO_PERSON_NOTE.get(type_id, "")
    return out


def clean_choice(choice: dict | None) -> dict:
    """A saved or submitted shoot choice, reduced to known values."""
    c = choice or {}
    t = c.get("type") if c.get("type") in TYPES else ""
    design = c.get("design") if c.get("design") in scenes.DESIGN_IDS + ["any"] else ""
    person = c.get("person") if c.get("person") in [p["id"] for p in PEOPLE] else ""
    pose = c.get("pose") if c.get("pose") in POSES else ""
    if t and pose and pose not in TYPES[t]["poses"]:
        pose = ""
    if pose and person not in POSES[pose]["people"]:
        person, pose = "", ""
    if not (person and pose):
        person, pose = "", ""
    return {"type": t, "design": design, "person": person, "pose": pose}


def composite_args(choice: dict, festive: bool = False) -> dict:
    """composite.make() keyword arguments for a shoot choice."""
    c = clean_choice(choice)
    stage = _stage(c["type"]) if c["type"] else ""
    design = c["design"]
    if festive and _photos(stage or "stand", "festive", c["person"]):
        design = "festive"           # a festival post in the festival's set
    return {"pose_override": "" if stage in ("", "auto") else stage,
            "design": "" if design == "any" else design,
            "person": c["person"], "person_pose": c["pose"]}
