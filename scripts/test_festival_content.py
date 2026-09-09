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
print("\n== 2. _stamp_brand(): deterministic brand visibility ==")
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

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
