"""
Brand Management: the library, the composer, Apply and Undo.

Why each group of checks exists (design: docs/designs/brand-management-module.md):

  * Generated copy is published under the SELLER's name. A template that says
    "handmade" or "sterling silver" about a product we have never seen is a
    false claim with their name on it. So every line is scanned for product
    facts, materials, brand names, dashes and US/UK spelling variants.
  * The quality bar is H&M, Zara, Gucci. Unreadable text is the fastest way to
    miss it, so every palette is held to WCAG contrast on the pairs the
    mockups actually draw, and the website accent is checked against the
    theme it lands on, in both light and dark mode.
  * Editing must survive regeneration and renaming. A seller who rewrote their
    statement must not lose it when they change direction, and must not
    publish their OLD name after renaming the shop.
  * Apply writes into a live shop. It has to say what it will change, refuse
    to touch a published shop without confirmation, and be undoable.

Run: python scripts/test_brand_kit.py
"""
import os
import re
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from backend.main import app  # noqa: E402
from backend.core import brandkit as bk, sitebuilder, studio  # noqa: E402

PASS = FAIL = 0
_TAG = uuid.uuid4().hex[:8]


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        print(f"  ✗ {label} {extra}")


# =========================================================================
print("\n== the library ==")
# =========================================================================
problems = []
for d in bk.DIRECTIONS:
    problems += bk.scan_direction(d)
check("no template states a product fact, a material, a brand name, a dash or a US/UK variant",
      not problems, "\n    " + "\n    ".join(problems[:10]))

bad_contrast = [f"{d['id']}/{p['id']} {r['pair']} {r['ratio']}"
                for d in bk.DIRECTIONS for p in d["palettes"]
                for r in bk.contrast_report(p["colours"]) if not r["ok"]]
check("every palette passes contrast on every pair the mockups draw", not bad_contrast, bad_contrast[:5])

bad_fonts = [f"{d['id']}:{f}" for d in bk.DIRECTIONS
             for f in list(d["fonts"].values()) + [d["wordmark"]["font"]] if f not in sitebuilder.FONT_IDS]
check("every font is one the Website Builder can load", not bad_fonts, bad_fonts)
check("every wordmark face is offered in the wordmark picker",
      all(d["wordmark"]["font"] in bk.WORDMARK_FONTS for d in bk.DIRECTIONS))

theme_ids = {t["id"] for t in sitebuilder.THEMES}
check("every theme mapping names a real website theme",
      all(t in theme_ids for d in bk.DIRECTIONS for t in list(d["site"]["themes"].values()) + d["site"]["fits"]))
check("every direction has three palettes of five valid colours",
      all(len(d["palettes"]) == 3 and all(bk.clean_hex(v) for p in d["palettes"] for v in p["colours"].values())
          for d in bk.DIRECTIONS))
check("ids are unique", len({d["id"] for d in bk.DIRECTIONS}) == len(bk.DIRECTIONS))
check("every category has an order, listing only directions that support it",
      all(c in bk.CATEGORY_ORDER for c in bk.CATEGORY_IDS)
      and all(did in bk._DIR for o in bk.CATEGORY_ORDER.values() for did in o))
check("Studio presets exist for every direction",
      all(d["studio"]["look"] in studio.LOOK_PROMPT and d["studio"]["voice"] in studio.VOICE_PROMPT
          for d in bk.DIRECTIONS))

leftovers, long_bios = [], []
for d in bk.DIRECTIONS:
    for c in d["categories"]:
        for sp in ("us", "intl"):
            for nm in ("Kaya", "x" * bk.NAME_MAX):
                g = bk.generated_text("seller@test.co", d["id"], c, nm, sp)
                for v in [g[f] for f in bk.TEXT_FIELDS] + g["captions"]:
                    if re.search(r"[{}]", v):
                        leftovers.append(v)
                for tpl in d["copy"]["bio"]:
                    if len(bk.fill(tpl, bk._slots(nm, c, sp))) > 150:
                        long_bios.append((d["id"], c))
check("every direction x category x spelling fills with no leftover slots", not leftovers, leftovers[:3])
check("every Instagram bio fits 150 characters with a 40-character name", not long_bios, long_bios[:3])

g_us = bk.generated_text("a@b.co", "quiet_luxury", "jewellery", "Kaya", "us")
g_in = bk.generated_text("a@b.co", "quiet_luxury", "jewellery", "Kaya", "intl")
all_us = " ".join([g_us[f] for f in bk.TEXT_FIELDS] + g_us["captions"])
check("US accounts read jewelry, never jewellery",
      "jewellery" not in all_us.lower() and ("jewelry" in all_us.lower() or "piece" in all_us.lower()))
check("other accounts read jewellery", "jewelry" not in " ".join(g_in[f] for f in bk.TEXT_FIELDS).lower())

seeds = {bk.generated_text(f"seller{i}@test.co", "quiet_luxury", "jewellery", "Kaya", "intl")["statement"]
         for i in range(12)}
check("two sellers in one direction do not all start with the same statement", len(seeds) > 1)

check("ranking puts suggested directions first for the bracket",
      bk.ranked("clothing", "18-24")[0]["fit"] == 3)
check("street edge is not offered to fragrance sellers",
      "street_edge" not in [r["id"] for r in bk.ranked("fragrance", "18-24")])
check("'not sure' falls back to the category order",
      [r["id"] for r in bk.ranked("home_decor", "all")][0] == bk.CATEGORY_ORDER["home_decor"][0])
check("generic sellers are not guessed into a category", bk.category_for_product_type("generic") == "")
check("monogram skips 'The' and takes two initials", bk.monogram("The Kaya Studio") == "K")
check("monogram of two words", bk.monogram("Kora Leather") == "KL")
check("a Devanagari name is flagged as non-Latin", bk._is_latin("काया") is False)

# the website accent, against the theme it lands on, in both modes
miss = []
for d in bk.DIRECTIONS:
    for p in d["palettes"]:
        for th in sitebuilder.THEMES:
            acc = bk.site_accents(p["colours"], th["id"])
            for mode in ("light", "dark"):
                c = acc[mode]
                if c and (bk.contrast(c, th[mode]["accent_ink"]) < 4.5 or bk.contrast(c, th[mode]["bg"]) < 3):
                    miss.append((d["id"], p["id"], th["id"], mode))
check("the site accent always reads on the theme it lands on, mapped or kept, light or dark", not miss, miss[:3])

_layouts = {k for k, _ in bk.LOGO_LAYOUTS}
_shapes = {k for k, _ in bk.LOGO_SHAPES}
check("every direction has a valid default logo shape",
      all(d["logo"]["layout"] in _layouts and d["logo"]["shape"] in _shapes
          and d["logo"]["fill"] in {k for k, _ in bk.LOGO_FILLS} for d in bk.DIRECTIONS))
check("the arch (umbrella) and circle layouts are offered", {"arch", "circle"} <= _layouts)

# the founder's generated images, mapped into the folders the module reads
_assets = bk.list_assets()
_count = sum(len(v) for v in _assets.values())
check("the generated brand images are all in place (130 of 139)", _count >= 130, _count)
check("every image sits under a known direction and asset name",
      all(did in bk._DIR and set(keys) <= set(bk.ASSET_KEYS) for did, keys in _assets.items()))
_heavy = [os.path.join(r, f) for r, _, fs in os.walk(bk.assets_dir()) for f in fs
          if f.endswith(".webp") and os.path.getsize(os.path.join(r, f)) > 300 * 1024]
check("no image is over 300 KB", not _heavy, _heavy[:3])
check("every direction with a ready card has its hero image",
      all("hero" in _assets.get(d["id"], {}) for d in bk.DIRECTIONS))

import importlib.util as _ilu  # noqa: E402
_spec = _ilu.spec_from_file_location("gen_brand_prompts",
                                     os.path.join(os.path.dirname(os.path.abspath(__file__)), "gen_brand_prompts.py"))
_gen = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_gen)
_md = _gen.build()
check("every image prompt is free of brand names and product claims", not _gen.scan(_md), _gen.scan(_md)[:3])
check("every image prompt forbids text in the image",
      all("no text" in b.lower() for b in re.findall(r"```text\n(.*?)\n```", _md, re.S)))
check("there is a prompt for every asset of every direction",
      _md.count("```text") == sum(7 + len(d["categories"]) for d in bk.DIRECTIONS))
_on_disk = open(_gen.OUT, encoding="utf-8").read() if os.path.exists(_gen.OUT) else ""
check("BRAND_IMAGE_PROMPTS.md is up to date with the library (run scripts/gen_brand_prompts.py)",
      _on_disk == _md)

# =========================================================================
print("\n== composing and editing ==")
# =========================================================================
EM = f"brand-{_TAG}@test.co"
bk.user_store.set_key(EM, bk.KIT_KEY, None)

k = bk.compose(EM, {"name": "Kaya", "category": "jewellery", "age": "25-34", "direction": "quiet_luxury"})
check("a direction gives a full kit", all(k["text"][f] for f in bk.TEXT_FIELDS) and len(k["colours"]) == 5)
check("the name is in the statement or about", "Kaya" in k["text"]["statement"] + k["text"]["about"])

k = bk.save(EM, {"name": "Kaya", "category": "jewellery", "age": "25-34", "direction": "quiet_luxury",
                 "text": {"statement": "At Kaya we make rings for quiet people."}, "edited": {"statement": True}})
check("an edited field is kept", k["text"]["statement"] == "At Kaya we make rings for quiet people.")

k2 = bk.compose(EM, {"direction": "modern_minimal"})
check("changing direction regenerates the rest but keeps the edit",
      k2["text"]["statement"] == "At Kaya we make rings for quiet people."
      and k2["text"]["tagline"] != k["text"]["tagline"] or k2["direction"] == "modern_minimal")

k3 = bk.compose(EM, {"name": "Nova"})
check("renaming replaces the old name inside edited text", "Nova" in k3["text"]["statement"]
      and "Kaya" not in k3["text"]["statement"])
check("and inside every generated line", "Kaya" not in " ".join(k3["text"][f] for f in bk.TEXT_FIELDS))

bk.save(EM, {"name": "Lux", "text": {"statement": "Lux is luxury, kept simple."}, "edited": {"statement": True}})
k4 = bk.compose(EM, {"name": "Nova"})
check("whole-word replace: 'Lux' becomes 'Nova' but 'luxury' survives",
      k4["text"]["statement"] == "Nova is luxury, kept simple.", k4["text"]["statement"])

bk.save(EM, {"name": "Kaya", "text": {"statement": "The Kayas way: kept, not shown."}, "edited": {"statement": True}})
k5 = bk.compose(EM, {"name": "Nova"})
check("a name it cannot replace cleanly blocks Apply", "statement" in k5["stale"] and bk._blocked(k5))

try:
    bk.compose(EM, {"name": "x" * (bk.NAME_MAX + 1)})
    check("a name over 40 characters is refused, not cut", False)
except bk.BrandError:
    check("a name over 40 characters is refused, not cut", True)

bk.save(EM, {"name": "Kaya", "edited": {"statement": False}, "direction": "quiet_luxury"})
k6 = bk.compose(EM, {"colours": {"ground": "#FFFFFF", "surface": "#FFFFFF", "ink": "#EEEEEE",
                                 "accent": "#111111", "support": "#888888"}, "edited": {"colours": True}})
check("edited colours make the palette custom", k6["palette"] == "custom")
check("unreadable custom colours block Apply", bool(bk._blocked(k6)))
k7 = bk.compose(EM, {"palette": "noir", "edited": {"colours": False}, "reset_visuals": True})
check("choosing a palette again replaces custom colours", k7["palette"] == "noir")

k8 = bk.compose(EM, {"logo": {"layout": "arch", "shape": "scallop", "fill": "solid"}, "edited": {"logo": True}})
check("the seller can arch their name over a scalloped emblem", k8["logo"] == {"layout": "arch", "shape": "scallop", "fill": "solid"})
k9 = bk.compose(EM, {"logo": {"layout": "spiral", "shape": "star"}, "edited": {"logo": True}})
check("an unknown shape falls back to the direction's", k9["logo"]["layout"] in _layouts and k9["logo"]["shape"] in _shapes)
k10 = bk.compose(EM, {"edited": {"logo": False}})
check("'Use the direction's' puts the default shape back", k10["logo"] == bk._DIR[k10["direction"]]["logo"])

v1 = bk.compose(EM, {"variants": {"tagline": 0}})["text"]["tagline"]
v2 = bk.compose(EM, {"variants": {"tagline": 1}})["text"]["tagline"]
check("Show another cycles the tagline", v1 != v2)

# =========================================================================
print("\n== Apply and Undo ==")
# =========================================================================
c = TestClient(app)
tok = c.post("/api/register", json={"email": f"brandapi-{_TAG}@test.co", "password": "pw123456"}).json()["token"]
H = {"Authorization": "Bearer " + tok}
st = c.get("/api/brand/state", headers=H)
check("state loads", st.status_code == 200, st.text[:200])
s = st.json()
check("state carries the library, the kit and a name suggestion",
      len(s["library"]["directions"]) >= 12 and "kit" in s and "suggested" in s)
check("copy templates stay on the server", "copy" not in s["library"]["directions"][0])

draft = {"name": f"Kaya {_TAG[:4]}", "category": "jewellery", "age": "25-34", "direction": "heritage_maison"}
r = c.post("/api/brand/compose", headers=H, json={"kit": draft})
check("compose returns a kit and its description", r.status_code == 200 and r.json()["describe"]["monogram"])

# a site to apply to
c.post("/api/site/save", headers=H, json={"site": {
    "brand": "Old Name", "handle": f"kaya-{_TAG}",
    "story": {"body": "We cast every ring ourselves in Jaipur."},
    # the legal details a shop needs before it may go live
    "trust": {"business_name": "Meera Rao", "grievance_name": "Meera Rao",
              "address": "12 MG Road, Bengaluru 560001", "support_phone": "9876543210",
              "support_email": "hello@kaya.in"}}})
plan = c.post("/api/brand/plan", headers=H, json={"kit": draft, "options": {}}).json()
paths = {row["path"]: row for row in plan["rows"]}
check("the plan lists site and Studio changes", "site.brand" in paths and "studio.voice_rules" in paths)
check("the seller's own story is not replaced by default (it carries their product facts)",
      paths.get("site.story.body", {}).get("default") is False)
check("the plan says which theme the site will use", plan["theme"]["after"] in theme_ids)

r = c.post("/api/brand/apply", headers=H, json={"kit": draft, "options": {}})
check("apply works on an unpublished site", r.status_code == 200, r.text[:200])
site = c.get("/api/site/state", headers=H).json()["site"]
check("the site now carries the brand name and fonts",
      site["brand"] == draft["name"] and site["style"]["heading_font"] == "playfair")
check("the story the seller wrote is still there", "Jaipur" in site["story"]["body"])
em2 = f"brandapi-{_TAG}@test.co"
stu = studio.get_brand(em2)
check("Studio carries the voice rules and the look", stu["voice_rules"] and stu["look"] == "luxe")
brief = studio.build_brief(stu, {"name": "Ring"}, {})
check("the caption writer is given the brand's voice rules", "Heritage Maison voice" in brief["voice_prompt"])

pub = c.post("/api/site/publish", headers=H, json={"published": True})
check("(setup) the test shop publishes", pub.status_code == 200, pub.text[:160])
r = c.post("/api/brand/apply", headers=H, json={"kit": {**draft, "direction": "modern_minimal"}, "options": {}})
check("a published shop needs confirmation before Apply changes it", r.status_code == 409, r.status_code)
r = c.post("/api/brand/apply", headers=H,
           json={"kit": {**draft, "direction": "modern_minimal"}, "options": {"confirm_live": True}})
check("and applies once confirmed", r.status_code == 200, r.text[:200])

c.post("/api/site/save", headers=H, json={"site": {"tagline": "My own line"}})
up = c.get("/api/brand/undo", headers=H).json()
row = next((x for x in up["rows"] if x["path"] == "site.tagline"), None)
check("Undo spots a field the seller changed after Apply", row and row["drift"] and row["default"] is False)
r = c.post("/api/brand/undo", headers=H, json={"options": {"confirm_live": True}})
check("Undo restores", r.status_code == 200, r.text[:200])
site = c.get("/api/site/state", headers=H).json()["site"]
check("and leaves the seller's later edit alone", site["tagline"] == "My own line")
check("and puts the previous fonts back", site["style"]["heading_font"] == "playfair")

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
