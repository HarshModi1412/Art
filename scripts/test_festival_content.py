"""
Regression guard for the festival-aware content system.

The bug this defends against: a Ganesh Chaturthi post's generated photo
looked like an ordinary product shot with a festival name in the caption
next to it -- nothing in the image pipeline knew a festival was involved at
all. Three separate things were wrong, and this file covers the fix for
each:

  1. studio.guidance_for()/image_prompt() never received the festival, so
     the AI image prompt had no colours, motifs, or festive direction --
     fixed by threading `occasion_key` (the playbook.FESTIVALS slug) from
     the post all the way through to prompt construction, scaled by the
     brand's own look (FESTIVE_INTENSITY).
  2. image_prompt() literally said "no text, no logo, no watermark", so
     every generated photo was brandless -- fixed with a deterministic
     Pillow overlay (_stamp_brand) that never touches the model.
  3. Reel-format posts got an image-generation button that made no sense
     (there is no single photograph that IS a video) and no way to plan
     what to film -- fixed with write_reel_script(), eagerly generated at
     plan time exactly like captions, plus an on-demand regenerate-script
     endpoint to backfill reels planned before this feature existed.

Run: python3 scripts/test_festival_content.py
"""
import io
import os
import pathlib
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from backend.main import app  # noqa: E402
import pandas as pd  # noqa: E402
from backend.core import studio, social, playbook  # noqa: E402

PASS = FAIL = 0


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        print(f"  ✗ {label}  <-- {extra}")


c = TestClient(app)

# =========================================================================
print("\n== 1. guidance_for() / image_prompt(): festival threading ==")
# =========================================================================
g = studio.guidance_for("new", "carousel", "ganesh_chaturthi", "warm")
check("guidance carries the festival name", g.get("festival") == "Ganesh Chaturthi", g)
check("guidance carries festival colours from playbook.py",
      bool(g.get("festival_colours")), g)
check("guidance carries festival motifs from playbook.py",
      bool(g.get("festival_motifs")), g)
check("guidance carries a brand-look-scaled festive intensity",
      bool(g.get("festive_intensity")), g)

pb_data = playbook.FESTIVALS.get("ganesh_chaturthi", {})
check("colours actually come from playbook.FESTIVALS, not invented",
      set(g["festival_colours"]) <= set(pb_data.get("colours", [])), g["festival_colours"])
check("motifs actually come from playbook.FESTIVALS, not invented",
      set(g["festival_motifs"]) <= set(pb_data.get("motifs", [])), g["festival_motifs"])

brief = studio.build_brief({"name": "Test Brand", "look": "warm"},
                           {"name": "Wallet", "category": "accessories"}, {})
p = studio.image_prompt(brief, g)
check("prompt mentions the festival by name", "Ganesh Chaturthi" in p, p)
check("prompt carries at least one festival colour", g["festival_colours"][0] in p, p)
check("prompt carries at least one festival motif", g["festival_motifs"][0] in p, p)

g_none = studio.guidance_for("new", "carousel", "", "warm")
check("no occasion_key -> no festival leakage into guidance", "festival" not in g_none, g_none)
p_none = studio.image_prompt(brief, g_none)
check("no occasion_key -> prompt has no festival mention", "Ganesh Chaturthi" not in p_none, p_none)

# Brand-look scaling: two different looks should not produce identical
# festive-intensity instructions -- that's the whole point of scaling by look.
g_luxe = studio.guidance_for("new", "carousel", "ganesh_chaturthi", "luxe")
g_bright = studio.guidance_for("new", "carousel", "ganesh_chaturthi", "bright")
check("festive_intensity differs across brand looks (luxe vs bright)",
      g_luxe["festive_intensity"] != g_bright["festive_intensity"],
      (g_luxe["festive_intensity"], g_bright["festive_intensity"]))
check("every brand look in studio.LOOKS has a festive-intensity mapping",
      all(look["id"] in studio.FESTIVE_INTENSITY for look in studio.LOOKS),
      [l["id"] for l in studio.LOOKS if l["id"] not in studio.FESTIVE_INTENSITY])

# Unknown occasion_key should degrade gracefully, not crash.
g_bad = studio.guidance_for("new", "carousel", "not_a_real_festival", "warm")
check("unknown occasion_key does not crash and adds no festival",
      "festival" not in g_bad, g_bad)

# =========================================================================
print("\n== 1b. a re-shoot must PRESERVE the product's own brand marking ==")
# =========================================================================
# The reference photo of the Women Wallet carries the maker's name embossed on
# it. A blanket "no text, no logo" told the model to wipe it, so the re-shoot
# came back as an unbranded wallet -- the seller's own product looking like a
# generic copy of itself.
p_ref = studio.image_prompt(brief, g, has_reference=True)
p_new = studio.image_prompt(brief, g, has_reference=False)

check("a re-shoot is told to keep the product's own markings",
      "exactly as it is in the reference" in p_ref, p_ref[-320:])
check("and it names brand name, logo and lettering specifically",
      all(w in p_ref for w in ("brand name", "logo", "lettering")), p_ref[-320:])
check("and it asks for the same spelling and placement",
      "same spelling" in p_ref and "same placement" in p_ref, p_ref[-320:])
check("a re-shoot NEVER carries the blanket 'no logo' instruction again",
      "No text, no logo" not in p_ref, p_ref[-320:])
check("but a re-shoot still refuses to ADD text of its own",
      "not add any new text, logo or watermark" in p_ref, p_ref[-320:])
check("an invented picture keeps the blanket no-logo rule (nothing to preserve)",
      "No text, no logo, no watermark" in p_new, p_new[-200:])
check("the two paths genuinely differ", p_ref != p_new)

_gen_src = __import__("inspect").getsource(studio.generate_image)
check("generate_image passes has_reference through from the reference argument",
      "has_reference=bool(reference)" in _gen_src)
check("no image path suppresses text/watermark outright any more",
      "extra items, text, " not in _gen_src)
check("brand preservation now rides in the prompt itself, on every engine",
      all(w in p_ref for w in ("brand name", "logo", "lettering")), p_ref[-320:])
check("the corner stamp is skipped on a re-shoot (brand would show twice)",
      "if not from_ref:" in _gen_src and "_stamp_brand(content" in _gen_src)

# =========================================================================
print("\n== 2. _stamp_brand(): deterministic brand visibility (invented shots) ==")
# =========================================================================
from PIL import Image  # noqa: E402

img = Image.new("RGB", (1024, 1024), (120, 30, 40))
buf = io.BytesIO()
img.save(buf, format="PNG")
raw = buf.getvalue()

stamped = studio._stamp_brand(raw, "Test Brand")
check("stamping produces a larger (non-identical) file", stamped != raw and len(stamped) > 0)
out_img = Image.open(io.BytesIO(stamped)).convert("RGB")
check("stamped image keeps the original dimensions", out_img.size == (1024, 1024), out_img.size)

corner = out_img.getpixel((1024 - 40, 1024 - 25))
check("bottom-right corner now shows the dark brand plate, not raw background",
      corner != (120, 30, 40), corner)

diff_count = sum(1 for x in range(900, 1024, 4) for y in range(900, 1024, 4)
                 if out_img.getpixel((x, y)) != (120, 30, 40))
check("a meaningful area of the bottom-right corner changed",
      diff_count > 20, diff_count)

check("empty brand name is a safe no-op", studio._stamp_brand(raw, "") == raw)
check("whitespace-only brand name is a safe no-op", studio._stamp_brand(raw, "   ") == raw)
check("garbage bytes never raise -- a cosmetic failure must not break generation",
      studio._stamp_brand(b"not a real image", "Test Brand") == b"not a real image")

# =========================================================================
print("\n== 3. write_reel_script(): shot lists for reel posts ==")
# =========================================================================
product = {"name": "Ganesh Chaturthi Wallet", "category": "accessories"}
occasion = {"name": "Ganesh Chaturthi", "days_away": 5}
script = social.write_reel_script("scripttest@t.co", product, "new", occasion=occasion)
check("script has a beats list", isinstance(script.get("beats"), list) and len(script["beats"]) > 0, script)
check("script has 4-6 beats (filmable, not a novel)", 4 <= len(script["beats"]) <= 6, len(script["beats"]))
for b in script["beats"]:
    check(f"beat has sec/shot/on_screen_text keys ({b})",
          all(k in b for k in ("sec", "shot", "on_screen_text")), b)
check("script has a caption_hint", "caption_hint" in script, script)
check("script records how it was generated", "generated_by" in script, script)

# Fallback path must never crash and must stay festival-aware.
fb = social._fallback_script(product, occasion)
check("fallback script also produces beats", len(fb.get("beats", [])) > 0, fb)
check("fallback script mentions the festival somewhere in its beats",
      any("Ganesh Chaturthi" in (b.get("shot", "") + b.get("on_screen_text", ""))
          for b in fb["beats"]),
      fb["beats"])
check("fallback script is marked template-generated", fb.get("generated_by") == "template", fb)

no_occ_fb = social._fallback_script(product, None)
check("fallback script with no occasion still works", len(no_occ_fb.get("beats", [])) > 0, no_occ_fb)

# =========================================================================
print("\n== 4. build_week(): occasion_key + script threading into real posts ==")
# =========================================================================
email = f"fest{int(time.time() * 1000)}@t.co"
tok = c.post("/api/register", json={"email": email, "password": "Test12345!"}).json()["token"]
H = {"Authorization": "Bearer " + tok, "X-Session-Id": "fest-sess"}

c.post("/api/products/item", json={"name": "Ganesh Wallet", "category": "Accessories",
                                   "price": 899, "stock": 20}, headers=H)
c.post("/api/social/settings", json={"category": "accessories"}, headers=H)

r = c.post("/api/social/week", json={"weeks": 1}, headers=H)
check("week planning still succeeds with the new fields wired in", r.status_code == 200, r.text[:200])

posts = social.week(email)
check("posts were created", len(posts) > 0, len(posts))
check("every post has an occasion_key field (even if empty)",
      all("occasion_key" in p for p in posts), [p.get("occasion_key") for p in posts])
check("every post has a script field (even if None for non-reels)",
      all("script" in p for p in posts), [p.get("script") for p in posts])
reel_posts = [p for p in posts if p.get("format") == "reel"]
non_reel_posts = [p for p in posts if p.get("format") != "reel"]
if reel_posts:
    check("reel posts get a real script, not null",
          all(p.get("script") for p in reel_posts),
          [(p["id"], p.get("script")) for p in reel_posts])
if non_reel_posts:
    check("non-reel posts get no script (image posts don't need one)",
          all(p.get("script") is None for p in non_reel_posts),
          [(p["id"], p.get("script")) for p in non_reel_posts])

# =========================================================================
print("\n== 5. start_campaign(): occasion_key + script threading in festival beats ==")
# =========================================================================
social.clear_plan(email)
r = c.post("/api/social/campaign", json={"festival": "ganesh_chaturthi"}, headers=H)
if r.status_code == 200:
    camp = r.json()
    made = camp.get("posts", [])
    check("campaign created at least one post", len(made) > 0, camp)
    check("every campaign post carries occasion_key = the festival's playbook slug",
          all(p.get("occasion_key") == "ganesh_chaturthi" for p in made),
          [p.get("occasion_key") for p in made])
    camp_reels = [p for p in made if p.get("format") == "reel"]
    camp_non_reels = [p for p in made if p.get("format") != "reel"]
    if camp_reels:
        check("campaign reel beats get a script",
              all(p.get("script") for p in camp_reels),
              [(p["id"], p.get("script")) for p in camp_reels])
    if camp_non_reels:
        check("campaign non-reel beats get no script",
              all(p.get("script") is None for p in camp_non_reels),
              [(p["id"], p.get("script")) for p in camp_non_reels])
else:
    # Ganesh Chaturthi's 2026 date may have already passed the campaign
    # window by the time this runs -- that's a valid "error" response, not
    # a bug, so just record it rather than failing the whole suite.
    check("campaign endpoint responded (may legitimately be out of window)",
          r.status_code in (200, 400), r.text[:300])

# =========================================================================
print("\n== 6. /api/studio/image: occasion_key resolved from post_id ==")
# =========================================================================
social.clear_plan(email)
c.post("/api/social/week", json={"weeks": 1}, headers=H)
posts2 = social.week(email)
festival_posts = [p for p in posts2 if p.get("occasion_key")]
if festival_posts:
    pid = festival_posts[0]["id"]
    r = c.post("/api/studio/image", json={"product_id": festival_posts[0].get("product_id") or "x",
                                          "post_id": pid, "use_reference": False}, headers=H)
    # No AI keys configured in this sandbox -- a clean 400 ("no image engine
    # configured") is the expected, correct behaviour here; a 500 would mean
    # the occasion_key resolution itself crashed, which is the real bug this
    # guards against.
    check("occasion_key resolution from post_id does not crash the endpoint",
          r.status_code in (200, 400), r.text[:300])
else:
    print("  (no festival-tagged post landed in this plan -- skipping, not a failure)")

# =========================================================================
print("\n== 7. update_post(): script patch handling ==")
# =========================================================================
social.clear_plan(email)
c.post("/api/social/week", json={"weeks": 1}, headers=H)
any_post = social.week(email)
if any_post:
    pid = any_post[0]["id"]
    patch = {"script": {"beats": [
        {"sec": "0-3", "shot": "Wide shot of the shop counter", "on_screen_text": "Ganesh Chaturthi is here"},
        {"sec": "3-8", "shot": "Close up on the wallet", "on_screen_text": ""},
        {"sec": "extra-long-value-that-should-be-clipped-well-beyond-twenty-chars", "shot": "x", "on_screen_text": "y"},
    ], "voiceover": "A short voiceover line.", "caption_hint": "Tag a friend who needs this."}}
    updated = social.update_post(email, pid, patch)
    check("update_post accepts a script patch", "script" in updated, updated.get("script"))
    check("script beats are capped and stored", len(updated["script"]["beats"]) <= 8, updated["script"]["beats"])
    check("sec field is bounds-clipped to 20 chars",
          len(updated["script"]["beats"][2]["sec"]) <= 20, updated["script"]["beats"][2]["sec"])
    check("empty beats (no shot, no on_screen_text) are filtered out",
          all(b.get("shot") or b.get("on_screen_text") for b in updated["script"]["beats"]),
          updated["script"]["beats"])
    check("voiceover stored", updated["script"]["voiceover"] == "A short voiceover line.", updated["script"])
    check("caption_hint stored", updated["script"]["caption_hint"] == "Tag a friend who needs this.", updated["script"])

    r = c.post("/api/social/post", json={"post_id": pid, "patch": {
        "script": {"beats": [{"sec": "0-3", "shot": "New shot", "on_screen_text": ""}],
                   "voiceover": "", "caption_hint": ""}}}, headers=H)
    check("script patch also works through the real /api/social/post endpoint",
          r.status_code == 200 and r.json().get("script", {}).get("beats"),
          r.text[:300])

# =========================================================================
print("\n== 8. /api/social/regenerate-script: manual regen + reel-only gate ==")
# =========================================================================
social.clear_plan(email)
c.post("/api/social/week", json={"weeks": 1}, headers=H)
posts3 = social.week(email)
reels3 = [p for p in posts3 if p.get("format") == "reel"]
non_reels3 = [p for p in posts3 if p.get("format") != "reel"]

if reels3:
    rid = reels3[0]["id"]
    r = c.post("/api/social/regenerate-script", json={"post_id": rid}, headers=H)
    check("regenerate-script succeeds for a real reel post", r.status_code == 200, r.text[:300])
    check("regenerated post keeps a script with beats",
          len(r.json().get("script", {}).get("beats", [])) > 0, r.json())

if non_reels3:
    nid = non_reels3[0]["id"]
    r = c.post("/api/social/regenerate-script", json={"post_id": nid}, headers=H)
    check("regenerate-script 400s for a non-reel post (image posts don't get a script)",
          r.status_code == 400, r.text[:300])

r = c.post("/api/social/regenerate-script", json={"post_id": "not-a-real-id"}, headers=H)
check("regenerate-script 404s for an unknown post_id", r.status_code == 404, r.text[:300])

# Backfill scenario: a reel planned before this feature existed has a null
# script. Simulate that directly and confirm the endpoint fills it in.
if reels3:
    rid2 = reels3[0]["id"]
    rows = social._posts(email)
    for row in rows:
        if row["id"] == rid2:
            row["script"] = None
    social._save_posts(email, rows)
    check("simulated pre-feature reel now has a null script",
          social.get_post(email, rid2).get("script") is None)
    r = c.post("/api/social/regenerate-script", json={"post_id": rid2}, headers=H)
    check("regenerate-script backfills a null script on an old reel post",
          r.status_code == 200 and len(r.json().get("script", {}).get("beats", [])) > 0,
          r.text[:300])

# =========================================================================
print("\n== 9. frontend: reel/image split wiring in the post editor ==")
# =========================================================================
# No headless DOM in this test suite -- test_website_builder.py and
# test_perf_resilience.py already establish string-level assertions against
# smart.js as this codebase's way of guarding frontend wiring, so this
# section follows the same pattern for the new script editor.
_js = pathlib.Path("Smart CafeX/smart.js").read_text(encoding="utf-8")
check("openSocialEditor branches on format === \"reel\"",
      'const isReel = post.format === "reel"' in _js)
check("reel posts get a distinct script block instead of .sm-ed-top",
      "sm-ed-script-block" in _js)
check("non-reel posts still get the Re-shoot button", '"smGenRef"' in _js)
check("non-reel posts still get the Invent button", '"smGenNew"' in _js)
check("reel posts never render the Re-shoot/Invent image buttons",
      "isReel ? `" in _js and "sm-ed-imgacts" in _js)
check("a script-editing section renders for reel posts",
      "function renderScriptSection" in _js)
check("beat rows are individually editable", "function renderBeatRows" in _js)
check("beats can be added", '"smAddBeat"' in _js and "_smScript.beats.push" in _js)
check("beats can be removed", "_smScript.beats.splice" in _js)
check("an empty/pre-feature reel offers Generate script",
      '"smGenScript"' in _js and "No shot list yet" in _js)
check("a filled-in reel offers Regenerate script", '"smRegenScript"' in _js)
check("script regeneration calls the backfill endpoint",
      "/api/social/regenerate-script" in _js)
check("Save builds a script patch only for reel posts",
      "if (isReel) {" in _js and "patch.script" in _js)
check("voiceover is editable", '"smVoiceover"' in _js)

_css = pathlib.Path("Smart CafeX/smart.css").read_text(encoding="utf-8")
check("the script block has its own CSS", ".sm-ed-script-block" in _css)
check("beat rows have their own CSS", ".sm-beat-row" in _css)
check("beat rows collapse to one column on a phone (mobile regression guard)",
      ".sm-beat-row { grid-template-columns: 1fr; }" in _css)


# =========================================================================
print("\n== 10. the week is a STORY, not six interchangeable slots ==")
# =========================================================================
# The complaint this guards: a planned week used to be N independent slots, so
# every post looked and read the same and the seller got no help at all.
_e = f"story{int(time.time() * 1000)}@t.co"
_tok = c.post("/api/register", json={"email": _e, "password": "Test12345!"}).json()["token"]
_H = {"Authorization": "Bearer " + _tok, "X-Session-Id": "story"}
c.post("/api/products/item", json={"name": "Women Wallet", "category": "Accessories",
                                   "price": 2499, "stock": 10}, headers=_H)
c.post("/api/social/settings", json={"patch": {"category": "clothing", "cadence": "growth"}},
       headers=_H)
c.post("/api/social/week", json={"weeks": 1}, headers=_H)
_ps = social.week(_e)

check("a week gets planned", len(_ps) >= 4, len(_ps))
check("every post knows its beat in the arc", all(p.get("beat") for p in _ps),
      [p.get("beat") for p in _ps])
check("every post knows what KIND of photograph it is",
      all(p.get("archetype") and p.get("shot_type") for p in _ps),
      [(p.get("archetype"), p.get("shot_type")) for p in _ps])
check("every post carries the week's named theme",
      all(p.get("theme") for p in _ps), [p.get("theme") for p in _ps])
check("the whole week shares ONE theme",
      len({p["theme"] for p in _ps}) == 1, {p.get("theme") for p in _ps})

_ARC = ["tease", "reveal", "prove", "place", "close"]
_rank = [_ARC.index(p["beat"]) for p in _ps]
check("the arc runs in calendar order — tease really does go out first",
      _rank == sorted(_rank), [p["beat"] for p in _ps])

_arch = [p["archetype"] for p in _ps]
check("no two consecutive posts share an archetype",
      all(_arch[i] != _arch[i + 1] for i in range(len(_arch) - 1)), _arch)
check("the week uses several different kinds of photograph",
      len({p["shot_type"] for p in _ps}) >= 3, {p["shot_type"] for p in _ps})

_hooks = [p["caption"]["hook"] for p in _ps]
check("every hook in the week is different — even with NO AI reachable",
      len(set(_hooks)) == len(_hooks), _hooks)
_bodies = [p["caption"]["body"] for p in _ps]
check("and the bodies differ too", len(set(_bodies)) == len(_bodies), _bodies)
check("the tease does not give away the price",
      not any("Rs" in p["caption"]["hook"] for p in _ps if p["archetype"] == "tease"),
      [p["caption"]["hook"] for p in _ps if p["archetype"] == "tease"])

# =========================================================================
print("\n== 11. reel scripts are paste-ready AI prompts ==")
# =========================================================================
_reels = [p for p in _ps if p["format"] == "reel"]
check("the week contains reels", len(_reels) > 0, len(_reels))
if _reels:
    _sc = _reels[0]["script"]
    _pr = _sc.get("ai_prompt", "")
    check("a reel carries a paste-ready prompt", bool(_pr), list(_sc))
    for _needle in ("SUBJECT:", "SHOT SEQUENCE:", "CAMERA:", "DURATION:",
                    "ASPECT RATIO:", "ON-SCREEN TEXT:", "DO NOT:"):
        check(f"the prompt has a {_needle.rstrip(':')} section", _needle in _pr, _pr[:160])
    check("the prompt names the actual product", "Women Wallet" in _pr, _pr[:200])
    check("the prompt carries the week's story", "STORY:" in _pr, _pr[:300])
    check("the prompt forbids changing the brand marking",
          "brand name" in _pr and "logo" in _pr, _pr[-260:])
    check("the prompt asks for 9:16 vertical", "9:16" in _pr, _pr[-400:])
    check("every filmed beat reaches the prompt",
          all((b.get("shot") or "")[:18] in _pr for b in _sc.get("beats", [])),
          _pr[:400])

    # Editing a beat must rewrite the prompt, not leave a stale one behind.
    _rid = _reels[0]["id"]
    social.update_post(_e, _rid, {"script": {
        "beats": [{"sec": "0-4", "shot": "Slide the wallet out of a coat pocket",
                   "on_screen_text": "Pocket sized"}],
        "voiceover": "", "caption_hint": ""}})
    _after = social.get_post(_e, _rid)["script"]["ai_prompt"]
    check("editing a beat rebuilds the prompt", "coat pocket" in _after, _after[:300])
    check("and the old beat is gone from it",
          "Turn it slowly to show the material" not in _after, _after[:300])

# =========================================================================
print("\n== 12. per-shot-type aesthetics, not one averaged paragraph ==")
# =========================================================================
check("studio knows a set of shot types", len(studio.SHOT_TYPES) >= 5,
      list(studio.SHOT_TYPES))
check("every archetype maps to a real shot type",
      all(a["shot_type"] in studio.SHOT_TYPES for a in social.ARCHETYPES.values()),
      [(k, a["shot_type"]) for k, a in social.ARCHETYPES.items()
       if a["shot_type"] not in studio.SHOT_TYPES])

_r = studio._parse_reading(
    "SHOT: packaging\nLIGHT: soft overcast from the left\n"
    "COLOUR: kraft brown and deep maroon\nSETTING: pale oak table\n"
    "COMPOSITION: overhead flat lay, box half open\nMOOD: unhurried\n"
    "SIGNATURE: tissue always caught mid-fold")
check("a reading is parsed into fields", _r["shot"] == "packaging", _r)
check("and turned back into a shootable sentence",
      "mid-fold" in studio._reading_prose(_r), studio._reading_prose(_r))
check("a label answer still resolves to a shot id",
      studio._parse_reading("SHOT: Packaging and unboxing")["shot"] == "packaging")
check("an unknown shot degrades instead of vanishing",
      studio._parse_reading("SHOT: banana")["shot"] in studio.SHOT_TYPES)

_brief = studio.build_brief(
    {"name": "Marusche", "look": "luxe", "aesthetic": "Signature: low warm light.",
     "aesthetic_shots": {"packaging": "kraft brown, box half open, tissue mid-fold"}},
    {"name": "Women Wallet", "category": "accessories"}, {})
_p_pack = studio.image_prompt(_brief, studio.guidance_for("new", "carousel", "", "luxe",
                                                          shot_type="packaging"))
_p_use = studio.image_prompt(_brief, studio.guidance_for("new", "carousel", "", "luxe",
                                                         shot_type="in_use"))
check("a packaging beat is shot against the seller's OWN packaging reference",
      "tissue mid-fold" in _p_pack, _p_pack[:300])
check("a shot type they never uploaded still gets sensible direction",
      "Worn or carried by a person" in _p_use, _p_use[:300])
check("two shot types produce genuinely different prompts", _p_pack != _p_use)

# =========================================================================
print("\n== 13. platform exports map correctly ==")
# =========================================================================
from backend.core import mapper  # noqa: E402

_shop = pd.DataFrame([
    {"Name": "#1001", "Created at": "2026-09-01", "Billing Name": "Asha Rao",
     "Email": "a@x.com", "Lineitem name": "Silk Saree", "Lineitem quantity": 2,
     "Lineitem price": 2500, "Total": 5000}] * 6)
_m = mapper.suggest_mapping(_shop)
check("a Shopify export is recognised by name",
      _m.get("_preset") == "shopify", _m.get("_preset"))
check("order_id is the order number, NOT the customer's name",
      _m.get("order_id") == "Name", _m.get("order_id"))
check("the customer's name lands in customer_name",
      _m.get("customer_name") == "Billing Name", _m.get("customer_name"))
_tx, _ = mapper.build_transactions(_shop, _m)
check("a per-unit price is multiplied up to the line total",
      _tx["amount"].sum() == 2500 * 2 * 6, _tx["amount"].sum())

_messy = pd.DataFrame([
    {"Order Date": "2026-09-01", "Invoice No": "INV-1", "Customer Name": "Asha",
     "Item Name": "Saree", "Product Category": "Clothing", "Qty": 1,
     "Total Amount (INR)": 2500}] * 6)
_m2 = mapper.suggest_mapping(_messy)
check("a hand-made Indian sheet is still scored, not forced into a preset",
      not _m2.get("_preset"), _m2.get("_preset"))
check("and it still maps every column correctly",
      (_m2["date"], _m2["order_id"], _m2["customer_name"], _m2["amount"]) ==
      ("Order Date", "Invoice No", "Customer Name", "Total Amount (INR)"), _m2)
_tx2, _ = mapper.build_transactions(_messy, _m2)
check("its revenue is NOT multiplied (already a line total)",
      _tx2["amount"].sum() == 2500 * 6, _tx2["amount"].sum())

# =========================================================================
print("\n== 14. frontend: story bar, prompt block, thin-data blur ==")
# =========================================================================
_js2 = pathlib.Path("Smart CafeX/smart.js").read_text(encoding="utf-8")
_css2 = pathlib.Path("Smart CafeX/smart.css").read_text(encoding="utf-8")
_store = pathlib.Path("Smart CafeX/storefront/store.js").read_text(encoding="utf-8")

check("the editor shows where the post sits in the week", "sm-story" in _js2)
check("it names the archetype", "archetype_label" in _js2)
check("it says what the post earns", "post.earns" in _js2)
check("the reel editor offers the paste-ready prompt", "sm-prompt" in _js2)
check("with a copy button", "smCopyPrompt" in _js2)
check("and a fallback when the clipboard is blocked",
      "Ctrl+C" in _js2 and "getSelection" in _js2)
check("thin data renders a blurred preview", "function thinData" in _js2)
check("Sales Analytics uses it", "your revenue trend, weekday pattern" in _js2)
check("Sub-Category Analysis uses it", "drive your revenue" in _js2)
check("the blur is real CSS blur", "filter: blur(" in _css2)
check("the placeholder carries NO numbers a seller could misread",
      "thin-count" in _css2 and "orders needed for" in _js2)

check("the storefront cancel dialog uses the real scrim class",
      'class="modal-s" id="cxScrim"' in _store)
check("and no longer appends an unstyled div to the body",
      'className = "modal-back"' not in _store)
check("it closes through the shared layer helper",
      "closeLayer()" in _store.split("function askCancel")[1][:1400])


# =========================================================================
print("\n== 15. a reel can be finished: upload the clip, then schedule it ==")
# =========================================================================
# A reel slot could be planned, scripted and handed a paste-ready prompt for a
# video AI -- and then there was nowhere to put the resulting video. The one
# format that out-reaches everything below 50K followers was the one format
# that could never actually be completed.
_ve = f"vid{int(time.time() * 1000)}@t.co"
_vtok = c.post("/api/register", json={"email": _ve, "password": "Test12345!"}).json()["token"]
_VH = {"Authorization": "Bearer " + _vtok, "X-Session-Id": "vid"}
c.post("/api/products/item", json={"name": "Women Wallet", "category": "Accessories",
                                   "price": 2499, "stock": 5}, headers=_VH)
c.post("/api/social/settings", json={"patch": {"category": "clothing",
                                               "cadence": "standard"}}, headers=_VH)
c.post("/api/social/week", json={"weeks": 1}, headers=_VH)
_vps = social.week(_ve)
_reel = next((p for p in _vps if p["format"] == "reel"), None)
_img = next((p for p in _vps if p["format"] != "reel"), None)

check("every planned post has a slot for a clip from the start",
      all("video_url" in p for p in _vps))
check("a reel with no clip is not ready to go out",
      _reel is not None and social.post_ready(_reel) is False)
check("nor is an image post with no picture",
      _img is not None and social.post_ready(_img) is False)

_fake = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 2048
_up = c.post("/api/site/image", headers=_VH,
             files={"files": ("clip.mp4", io.BytesIO(_fake), "video/mp4")})
check("a video uploads through the durable media store", _up.status_code == 200, _up.text[:160])
check("and is stored as a video, not mistaken for a still",
      _up.json().get("kind") == "video", _up.json())
_url = _up.json().get("url")

_at = c.post("/api/social/attach-video", headers=_VH,
             json={"post_id": _reel["id"], "url": _url})
check("the clip attaches to the post", _at.status_code == 200, _at.text[:200])
_after = social.get_post(_ve, _reel["id"])
check("the post now carries the clip", bool(_after["video_url"]))
check("and is ready to schedule", social.post_ready(_after))
check("attaching a clip leaves the caption alone",
      _after["caption"]["hook"] == _reel["caption"]["hook"])
check("and leaves the shot list alone", bool(_after.get("script")))

_sc = c.post("/api/social/state", headers=_VH,
             json={"post_id": _reel["id"], "state": "scheduled"})
check("a reel with a clip schedules cleanly",
      _sc.status_code == 200 and _sc.json().get("state") == "scheduled", _sc.text[:160])

c.post("/api/social/attach-video", headers=_VH, json={"post_id": _reel["id"], "url": ""})
_gone = social.get_post(_ve, _reel["id"])
check("sending an empty url removes the clip", _gone["video_url"] == "")
check("removing it does NOT delete the post or its caption",
      _gone["caption"]["hook"] == _reel["caption"]["hook"])
check("and does not silently unschedule it", _gone["state"] == "scheduled")

check("an unknown post id 404s rather than failing silently",
      c.post("/api/social/attach-video", headers=_VH,
             json={"post_id": "nope", "url": _url}).status_code == 404)

# The video slot must actually be reachable in the editor.
_js3 = pathlib.Path("Smart CafeX/smart.js").read_text(encoding="utf-8")
_css3 = pathlib.Path("Smart CafeX/smart.css").read_text(encoding="utf-8")
check("the editor renders a clip slot", "sm-vid-slot" in _js3)
check("a reel shows it up front", "No clip uploaded yet" in _js3)
check("an image post keeps it as a folded-away option",
      "Post a video instead of the picture" in _js3 and "sm-vid-opt" in _css3)
check("the file picker only offers real video types",
      'accept="video/mp4,video/webm,video/quicktime"' in _js3)
check("oversized clips are caught before the upload starts",
      "48 * 1024 * 1024" in _js3)
check("uploading shows the working indicator", "Uploading your clip" in _js3)
check("the post is told which clip is its own after upload",
      "/api/social/attach-video" in _js3)
check("a post missing its media says so instead of failing on the day",
      "sm-needs" in _js3 and "ready to schedule" in _js3)
check("but it is a warning, never a block — Approve stays enabled",
      "needsMedia ?" in _js3 and 'id="smApprove"' in _js3)
check("the calendar marks which posts already have a clip",
      "cal-has-vid" in _js3 and ".cal-has-vid" in _css3)


# =========================================================================
print("\n== 16. the aesthetic reading is deep enough to be worth having ==")
# =========================================================================
# The reading a seller was shown described any brand and generated none:
# "soft diffused light, muted palette, shallow depth of field, calm mood".
# Three causes: a one-sentence-per-field prompt, a 400-token ceiling, and a
# 90-130 word merge that also leaked its own instruction into the answer.
from backend.core import aiprovider  # noqa: E402

_sys = studio.AESTHETIC_SYSTEM
for _f in ("LIGHT", "PALETTE", "SURFACE", "PROPS", "COMPOSITION", "LENS",
           "GRADE", "MOOD", "SIGNATURE", "REPEATABLE"):
    check(f"the reading asks for {_f}", f"{_f}:" in _sys)
check("each field has a word floor, so 'soft natural light' is not an answer",
      _sys.count("+ words") >= 8, _sys.count("+ words"))
check("it demands numbers, which cannot be vague",
      all(w in _sys for w in ("hex", "f-stop", "focal length", "clock")))
check("it bans the marketing words that made the old output generic",
      all(w in _sys for w in ("stunning", "elevated", "timeless", "premium")))

_src = __import__("inspect").getsource(studio.read_aesthetic)
check("the 400-token ceiling that truncated every reading is gone",
      "max_tokens=400" not in _src, _src[_src.find("max_tokens"):][:60])
check("readings now get real room", "max_tokens=2000" in _src)
check("the merge asks for a photography bible, not a paragraph",
      "650-900 words" in _src and "RULES —" in _src)
check("and explicitly tells the model not to restate the instructions",
      "Do not restate these" in _src)

_rich = """SHOT: packaging
LIGHT: Soft overcast window light from camera-left at roughly 10 o'clock, about
one metre from the subject, near 5600K.
PALETTE: Kraft brown (#A9835C) over about 45% of frame against off-white tissue
(#F2EDE4), one deep maroon accent (#5C1F28).
SURFACE: Pale oak table, open grain, lightly waxed.
PROPS: Scissors and twine out of focus upper-right.
COMPOSITION: Square crop, overhead at 90 degrees, box left of centre.
LENS: Roughly 50mm equivalent, shallow at about f/2.8.
GRADE: Gentle contrast, blacks lifted, warm highlight cast.
MOOD: Unhurried and ceremonial.
SIGNATURE: The tissue is always caught mid-fold, never flat.
REPEATABLE: Shoot overhead on pale oak, key from camera-left, open the box to
exactly half."""
_r = studio._parse_reading(_rich)
check("every field survives parsing",
      all(_r.get(k) for k in studio.READING_FIELDS),
      [k for k in studio.READING_FIELDS if not _r.get(k)])
check("a wrapped line is kept, not truncated at the first newline",
      "one metre from the subject" in _r["light"], _r["light"])
check("hex values survive", "#A9835C" in _r["palette"])
check("an f-stop survives", "f/2.8" in _r["lens"])
check("the reading is substantial, not a caption",
      len(studio._reading_prose(_r)) > 600, len(studio._reading_prose(_r)))
check("labels are kept so a long prompt cannot skim past them",
      "LIGHT:" in studio._reading_prose(_r) and "GRADE:" in studio._reading_prose(_r))

# =========================================================================
print("\n== 17. better free models for vision and for drawing ==")
# =========================================================================
check("vision has its own preference order, not the text chain's",
      hasattr(aiprovider, "VISION_PREFERENCE"))
# This asserted "huggingface" while HF credits lasted. They ran out, and
# Gemini reads pictures better anyway, so Gemini leads again. The rest stay in
# the chain as fallbacks rather than being removed.
check("Gemini is asked first to read pictures",
      aiprovider.VISION_PREFERENCE[0] == "gemini", aiprovider.VISION_PREFERENCE)
check("and the rest remain as fallbacks",
      set(aiprovider.VISION_PREFERENCE) >= {"groq", "cloudflare", "openai"},
      aiprovider.VISION_PREFERENCE)
check("Groq vision is wired now that it has a usable model",
      "groq" in aiprovider.VISION_MODELS)
check("and not with the dead llama-vision id older guides still show",
      "llama-3.2" not in aiprovider.VISION_MODELS["groq"],
      aiprovider.VISION_MODELS["groq"])
check("Hugging Face is available as a provider",
      any(p.name == "huggingface" for p in aiprovider.PROVIDERS))
_hf = next(p for p in aiprovider.PROVIDERS if p.name == "huggingface")
check("but is labelled honestly as credit-metered, not free",
      _hf.free is False and "credit" in _hf.note, (_hf.free, _hf.note))
check("its vision model is a real VLM, not a one-line captioner",
      "VL" in aiprovider.VISION_MODELS["huggingface"],
      aiprovider.VISION_MODELS["huggingface"])
check("every vision model is overridable by env, so a dead id is a config fix",
      all(f"{n.upper()}_VISION_MODEL" in __import__("inspect").getsource(aiprovider)
          for n in ("cf", "gemini", "groq", "hf")))

check("private work keeps its own safety ordering",
      "if sensitivity == \"private\":" in
      __import__("inspect").getsource(aiprovider._vision_order))

check("Gemini image generation is wired", hasattr(aiprovider, "gemini_image"))
_gen = __import__("inspect").getsource(studio.generate_image)
check("the engine is validated before anything is spent",
      "image_engine(engine, for_reshoot=bool(reference))" in _gen)
check("SD-1.5 img2img is kept away from re-shoots — it redraws the product",
      "redraw the product" in __import__("inspect").getsource(studio))
check("a failure names the engine instead of quietly trying another vendor",
      "it is a substitution" in _gen)
check("no image path can raise into the request",
      all("except Exception" in __import__("inspect").getsource(f)
          for f in (aiprovider.gemini_image, aiprovider.hf_image, aiprovider.hf_video)))


# =========================================================================
print("\n== 18. Approve means approve AND make it ready ==")
# =========================================================================
_ae = f"appr{int(time.time() * 1000)}@t.co"
_atok = c.post("/api/register", json={"email": _ae, "password": "Test12345!"}).json()["token"]
_AH = {"Authorization": "Bearer " + _atok, "X-Session-Id": "appr"}
c.post("/api/products/item", json={"name": "Women Wallet", "category": "Accessories",
                                   "price": 2499, "stock": 5}, headers=_AH)
c.post("/api/social/settings", json={"patch": {"category": "clothing",
                                               "cadence": "standard"}}, headers=_AH)
c.post("/api/social/week", json={"weeks": 1}, headers=_AH)
_aps = social.week(_ae)
_aimg = next((p for p in _aps if p["format"] != "reel"), None)
_areel = next((p for p in _aps if p["format"] == "reel"), None)

_r = c.post("/api/social/approve-ready", headers=_AH, json={"post_id": _aimg["id"]})
check("approving an image post succeeds", _r.status_code == 200, _r.text[:200])
_d = _r.json()
check("it is scheduled", _d["post"]["state"] == "scheduled", _d["post"]["state"])
check("a failed generation does NOT lose the seller's decision",
      _d["post"]["state"] == "scheduled" and bool(_d["media_error"]),
      _d["media_error"][:80])
check("and the reason is reported so the panel can say what is left",
      "image engine" in _d["media_error"].lower(), _d["media_error"][:90])

_r2 = c.post("/api/social/approve-ready", headers=_AH, json={"post_id": _areel["id"]})
_d2 = _r2.json()
check("approving a reel succeeds", _r2.status_code == 200, _r2.text[:200])
check("it is scheduled too", _d2["post"]["state"] == "scheduled")
check("a reel is recognised as a reel", _d2["is_reel"] is True)
check("no picture is drawn for it — there is no photograph that IS a video",
      _d2.get("image") is None)
check("it hands back the shot list instead",
      bool((_d2.get("script") or {}).get("beats")), _d2.get("script"))
check("and the paste-ready video prompt",
      bool((_d2.get("script") or {}).get("ai_prompt")))
check("a reel with no clip is still reported as not ready",
      _d2["ready"] is False)
check("approving an unknown post 404s",
      c.post("/api/social/approve-ready", headers=_AH,
             json={"post_id": "nope"}).status_code == 404)

# =========================================================================
print("\n== 19. Hugging Face still carries video, and is honest about cost ==")
# =========================================================================
# History: this section once asserted Hugging Face was first for everything.
# The seller's HF credits ran out, so ChatGPT is now the image default and
# Gemini reads the pictures (section 20/21). HF keeps video -- it is the only
# connected engine that makes one -- and it is still offered as an image
# choice for anyone who has credits. These checks were rewritten, not deleted,
# because the HF paths are still live code.
check("HF is still an offered vision engine, just no longer first",
      "huggingface" in aiprovider.VISION_PREFERENCE, aiprovider.VISION_PREFERENCE)
check("with a real VLM, not a captioner",
      "VL" in aiprovider.VISION_MODELS["huggingface"],
      aiprovider.VISION_MODELS["huggingface"])
check("HF can draw", hasattr(aiprovider, "hf_image"))
check("HF can make video", hasattr(aiprovider, "hf_video"))
check("a re-shoot uses an EDIT model that conditions on the source photo",
      "Edit" in aiprovider.HF_EDIT_MODEL, aiprovider.HF_EDIT_MODEL)
check("and text-to-image uses a cheaper plain model",
      aiprovider.HF_IMAGE_MODEL != aiprovider.HF_EDIT_MODEL)
check("video is image-to-video, so the product stays the seller's",
      "I2V" in aiprovider.HF_VIDEO_MODEL, aiprovider.HF_VIDEO_MODEL)
check("every HF model id is env-overridable",
      all(k in __import__("inspect").getsource(aiprovider)
          for k in ("HF_IMAGE_MODEL", "HF_EDIT_MODEL", "HF_VIDEO_MODEL",
                    "HF_VISION_MODEL")))

_reg = {e["id"]: e for e in studio.IMAGE_ENGINES}
check("HF remains selectable for images", "huggingface" in _reg)
check("and its price is stated plainly, because it is not free",
      "$" in _reg["huggingface"]["cost"], _reg["huggingface"]["cost"])
check("ChatGPT is the one marked default in the registry",
      studio.IMAGE_ENGINES[0]["id"] == "openai", studio.IMAGE_ENGINES[0]["id"])

_gsrc = __import__("inspect").getsource(studio.generate_image)
check("a re-shoot on HF uses the edit model, not the invent model",
      "reference" in _gsrc.split('== "huggingface"')[1][:220],
      "guard missing")

_v = studio.video_engine()
check("video engine reports not-ready without a token", _v["ready"] is False)
check("and says you can still upload your own", "upload your own" in _v["note"])
_vsrc = __import__("inspect").getsource(studio.video_engine)
check("the cost is stated up front, not discovered from a bill",
      "$0.20" in _vsrc and "PRO covers about ten" in _vsrc)
check("and the fidelity limit is stated honestly",
      "drift" in _vsrc)
_gvsrc = __import__("inspect").getsource(studio.generate_video)
check("video is generated FROM the seller's own photo, never invented",
      "_reference_shot" in _gvsrc)
check("and refuses clearly when there is no photo to work from",
      "has none yet" in _gvsrc)

_js4 = pathlib.Path("Smart CafeX/smart.js").read_text(encoding="utf-8")
check("the panel routes post approvals through the new flow",
      'id.startsWith("post_") && decision === "approve"' in _js4)
check("a reel gets its prompt handed over on approval",
      "function openReelPrompt" in _js4)
check("with a copy button", "rpCopy" in _js4)
check("and a route into the editor to upload the clip", "rpOpen" in _js4)
check("the editor offers to generate a clip", "smVidGen" in _js4)
check("but confirms the price BEFORE spending anything",
      "/api/studio/video-engine" in _js4 and "confirm(" in
      _js4.split('vidGen.onclick')[1][:600])
check("and warns that generated clips drift",
      "then detail can drift" in _js4)


# =========================================================================
print("\n== 20. the seller picks which AI draws, per generation ==")
# =========================================================================
import importlib as _il  # noqa: E402

for _k in list(os.environ):
    if any(_x in _k for _x in ("OPENAI", "GEMINI", "GROQ", "CF_", "HF_")):
        os.environ.pop(_k, None)
_il.reload(aiprovider); _il.reload(studio)
check("with nothing connected, no engine is offered",
      studio.image_engines() == [], studio.image_engines())
check("and the default reports itself as unavailable rather than guessing",
      studio.image_engine()["engine"] == "")

os.environ["OPENAI_API_KEY"] = "x"
os.environ["GEMINI_API_KEY"] = "y"
os.environ["CF_ACCOUNT_ID"] = "a"; os.environ["CF_API_TOKEN"] = "b"
os.environ["HF_API_TOKEN"] = "hf"
_il.reload(aiprovider); _il.reload(studio)

_all = [e["id"] for e in studio.image_engines()]
check("every connected engine is offered", set(_all) ==
      {"openai", "gemini", "cloudflare", "huggingface"}, _all)
check("ChatGPT is the default now that the HF credits are gone",
      studio.image_engine()["engine"] == "openai", studio.image_engine()["engine"])
check("Gemini is back as a first-class option", "gemini" in _all)

_rs = [e["id"] for e in studio.image_engines(for_reshoot=True)]
check("Cloudflare is NOT offered for a re-shoot — it would redraw the product",
      "cloudflare" not in _rs, _rs)
check("but it IS offered for inventing a picture", "cloudflare" in _all)

check("picking an engine by name honours it",
      studio.image_engine("gemini")["engine"] == "gemini")
check("every offered engine carries a price the UI can show",
      all(e.get("cost") and e.get("note") for e in studio.image_engines()))

try:
    studio.image_engine("cloudflare", for_reshoot=True)
    check("asking Cloudflare for a re-shoot is refused", False, "no error raised")
except ValueError as _e:
    check("asking Cloudflare for a re-shoot is refused with a reason",
          "redraw the product" in str(_e), str(_e)[:90])
try:
    studio.image_engine("nonsense")
    check("an unconnected engine is refused", False, "no error raised")
except ValueError as _e:
    check("an unconnected engine is refused, never silently swapped",
          "not connected" in str(_e), str(_e)[:90])

_gsrc2 = __import__("inspect").getsource(studio.generate_image)
check("generation dispatches to ONE engine, with no silent vendor swap",
      "it is a substitution" in _gsrc2)
check("and names the engine that failed",
      "eng['label']" in _gsrc2 or 'eng["label"]' in _gsrc2)

check("video engines are listed the same way",
      [e["id"] for e in studio.video_engines()] == ["huggingface"],
      studio.video_engines())
check("video stays on Hugging Face, as asked",
      studio.video_engine()["engine"] == "huggingface")

# =========================================================================
print("\n== 21. Gemini reads the brand aesthetic, and writes an essay ==")
# =========================================================================
check("Gemini is asked first to READ pictures",
      aiprovider.VISION_PREFERENCE[0] == "gemini", aiprovider.VISION_PREFERENCE)
check("and the reason is recorded — reading and drawing are different jobs",
      "not the same judgement as which" in
      __import__("inspect").getsource(aiprovider).split("VISION_PREFERENCE")[0][-900:])

_asrc = __import__("inspect").getsource(studio.read_aesthetic)
check("the brand aesthetic is written as an ESSAY, not a checklist",
      "ESSAY" in _asrc and "Never a bullet" in _asrc)
check("with real paragraphs under each heading",
      "60-110 words of real sentences" in _asrc)
check("that explain WHY, not just what",
      "explain WHY the choice reads" in _asrc)
check("and it is long enough to be worth reading",
      "650-900 words" in _asrc)
check("with the token room to actually get there",
      "max_tokens=3000" in _asrc)

_jsE = pathlib.Path("Smart CafeX/smart.js").read_text(encoding="utf-8")
check("the editor offers the engine picker", "smEngine" in _jsE)
check("loaded from the server, so it only lists connected engines",
      "/api/studio/image-engines" in _jsE)
check("re-shoot and invent load their own valid sets",
      "loadEngines(true)" in _jsE and "loadEngines(false)" in _jsE)
check("the chosen engine is sent with the request",
      'engine: ($("smEngine") || {}).value' in _jsE)
check("each engine's price is shown before it is used",
      "smEngineNote" in _jsE and "e.cost" in _jsE)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)

