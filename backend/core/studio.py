"""
Product Studio — the seller's own material, turned into Instagram posts.

THE PROBLEM IT SOLVES
---------------------
The Content Creator generates a post from a topic and a product *type*. That
produces something generic: a stock-looking picture of "a perfume", not of
*their* perfume. A seller can spot it instantly, and so can their followers.

Studio starts from what the seller actually has — their real photographs, their
real clips, the words they use about the product — plus a brand profile they fill
in once. Every post is generated against that, so the output looks like it came
from their shelf and sounds like them.

WHAT IT HOLDS

* **A brand profile**, once per account: what the brand stands for, who buys it,
  the look (four or five words), the palette, the voice, what to never say. This
  is the thing that keeps twenty generated posts feeling like one brand.
* **Per-product material**: photos, clips, the story behind the piece, materials,
  what makes it different, who it is for, and the occasions it suits. All of it
  optional, all of it makes the output better — and the app says which missing
  piece would help most rather than leaving empty boxes unexplained.

HOW A POST GETS MADE
--------------------
`build_brief()` turns brand + product into one prompt-shaped brief. Two ways to
use it:

* **Use my own photo** — the seller's real photograph with generated copy. Always
  available, costs nothing, and is what most sellers should use most of the time.
* **Generate an image** — an AI photograph built from the brief, so the styling,
  palette and mood follow the brand rather than a generic template.

Generated images are marked as generated in the returned payload. A seller
should always know which of their pictures is a photograph of a real object and
which is not.
"""
from __future__ import annotations

import logging
import os
import uuid

from backend.core import media, products, user_store

log = logging.getLogger("studio")

BRAND_KEY = "studio_brand"
PRODUCT_KEY = "studio_products"     # product_id -> material

# Deliberately short. A long form gets abandoned, and these five are the ones
# that actually change what comes out.
LOOKS = [
    {"id": "clean",     "label": "Clean & minimal",
     "prompt": "clean minimal product photography, soft even lighting, uncluttered neutral backdrop, generous negative space"},
    {"id": "warm",      "label": "Warm & handmade",
     "prompt": "warm natural light, linen and wood textures, gently imperfect handmade feel, soft shadows"},
    {"id": "luxe",      "label": "Dark & luxurious",
     "prompt": "moody low-key product photography, deep shadows, soft rim light, stone or velvet surface, restrained and expensive"},
    {"id": "bright",    "label": "Bright & playful",
     "prompt": "bright high-key photography, bold saturated colour blocking, crisp shadows, energetic and fun"},
    {"id": "editorial", "label": "Editorial",
     "prompt": "fashion editorial photography, styled set, directional light, magazine composition"},
]
LOOK_PROMPT = {l["id"]: l["prompt"] for l in LOOKS}

VOICES = [
    {"id": "warm",     "label": "Warm and personal",   "prompt": "warm, personal, first-person, like a maker talking to a friend"},
    {"id": "minimal",  "label": "Short and confident", "prompt": "short declarative sentences, confident, no filler, no exclamation marks"},
    {"id": "playful",  "label": "Playful",             "prompt": "playful and light, a little wit, never try-hard"},
    {"id": "luxury",   "label": "Quiet luxury",        "prompt": "understated, restrained, lets the craft speak, never shouty"},
    {"id": "helpful",  "label": "Helpful and plain",   "prompt": "plain helpful language, practical detail first"},
]
VOICE_PROMPT = {v["id"]: v["prompt"] for v in VOICES}


# ---------------------------------------------------------------------------
# brand profile
# ---------------------------------------------------------------------------
def blank_brand(email: str = "") -> dict:
    return {
        "name": "", "tagline": "",
        "about": "",                 # what you make and why
        "audience": "",              # who buys it
        "look": "clean",
        "voice": "warm",
        "palette": "",               # free text — "warm sand, black, brass"
        "avoid": "",                 # words or looks to stay away from
        "hashtags": "",              # the ones they always use
        "city": "",
        # --- design language ------------------------------------------------
        # Reference images that define the brand's AESTHETIC rather than its
        # products: shots the seller admires, their packaging, their shop, a
        # mood board. A seller can rarely write "warm sand, brass, low-key
        # light" but can always point at five pictures and say "like this".
        "refs": [],                  # urls of uploaded reference images
        "aesthetic": "",             # what the AI read from those images
        "aesthetic_from": 0,         # how many refs produced it
    }


def get_brand(email: str) -> dict:
    saved = user_store.get_key(email, BRAND_KEY, {}) or {}
    return {**blank_brand(email), **(saved if isinstance(saved, dict) else {})}


def add_ref(email: str, url: str) -> dict:
    """Add one design-language reference image."""
    b = get_brand(email)
    refs = [r for r in (b.get("refs") or []) if r][:23]
    if url and url not in refs:
        refs.append(url)
    b["refs"] = refs
    user_store.set_key(email, BRAND_KEY, b)
    return b


def remove_ref(email: str, url: str) -> dict:
    b = get_brand(email)
    b["refs"] = [r for r in (b.get("refs") or []) if r != url]
    # The reading was derived from the old set, so it no longer describes what
    # is there. Better to blank it and let them re-read than to keep a
    # description of pictures that have been removed.
    if b.get("aesthetic_from", 0) != len(b["refs"]):
        b["aesthetic"] = ""
        b["aesthetic_from"] = 0
    user_store.set_key(email, BRAND_KEY, b)
    return b


AESTHETIC_SYSTEM = (
    "You are an art director writing a brief for a photographer. You are shown "
    "reference images that a brand has chosen to represent its taste. Describe "
    "the VISUAL LANGUAGE they share, not the objects in them.\n\n"
    "Cover, concretely: lighting (hard or soft, direction, warmth); colour "
    "palette in plain colour words; surfaces and materials; composition and "
    "negative space; depth of field; mood; and any styling habits such as props, "
    "hands, fabric folds, shadows.\n\n"
    "Write 90-140 words of plain prose a photographer could shoot from. No "
    "bullet points, no headings, no praise, no marketing adjectives like "
    "'stunning' or 'elevated'. If the references disagree with each other, say "
    "so plainly and describe the dominant one."
)

PRODUCT_SYSTEM = (
    "You are cataloguing a product from its photograph for a seller's own "
    "records. Describe ONLY what you can actually see.\n\n"
    "Cover: what the item is; its colour or colours; the material and weave or "
    "finish; the construction, cut or setting; any pattern, embroidery, stones "
    "or hardware and where they sit; and the visible condition and scale.\n\n"
    "Write 60-110 words of plain prose. Be specific about detail — 'gold-tone "
    "filigree jhumka with three rows of white pearl drops' beats 'elegant "
    "earrings'. Never invent a material, a measurement, a price or a brand you "
    "cannot see. If something is unclear in the photograph, say it is unclear "
    "rather than guessing."
)


def read_aesthetic(email: str) -> dict:
    """Turn the reference images into a written aesthetic.

    Reads up to four references. More than that costs tokens without sharpening
    the answer, and a brand whose taste needs more than four pictures to
    describe does not have a consistent one yet."""
    from backend.core import aiprovider, media
    b = get_brand(email)
    refs = [r for r in (b.get("refs") or []) if r][:4]
    if not refs:
        return {"ok": False, "reason": "No reference images uploaded yet."}
    if not aiprovider.vision_ready():
        return {"ok": False, "reason": "No vision-capable AI is connected. Add a "
                                       "Cloudflare, Gemini or OpenAI key and try again."}

    readings, failed = [], 0
    for url in refs:
        got = media.read(url.rsplit("/", 1)[-1])
        if not got:
            failed += 1
            continue
        data, ctype = got
        r = aiprovider.describe_image(
            data, ctype, system=AESTHETIC_SYSTEM,
            user="Describe the visual language of this reference image.",
            sensitivity="public", max_tokens=320)
        if r["text"]:
            readings.append(r["text"])
        else:
            failed += 1

    if not readings:
        return {"ok": False, "reason": "Could not read any of the reference images."}

    if len(readings) == 1:
        summary = readings[0]
    else:
        merged = aiprovider.generate(
            "You are an art director. You are given several separate readings of "
            "reference images from one brand. Write ONE brief describing the "
            "visual language they share. Lead with what is common to all of them. "
            "Name any real disagreement in a final sentence rather than averaging "
            "it away. 100-150 words, plain prose, no headings.",
            "\n\n---\n\n".join(readings),
            sensitivity="public", max_tokens=400, fallback=readings[0])
        summary = merged["text"] or readings[0]

    b["aesthetic"] = summary.strip()[:2000]
    b["aesthetic_from"] = len(readings)
    user_store.set_key(email, BRAND_KEY, b)
    return {"ok": True, "aesthetic": b["aesthetic"], "read": len(readings),
            "failed": failed, "brand": b}


def read_product_shots(email: str, product_id: str, limit: int = 3) -> dict:
    """Turn a product's own photographs into a written description.

    This is what makes generated imagery look like the seller's ACTUAL product
    rather than a stock idea of it. The description goes into the prompt as
    text, so the model is told what the thing looks like instead of inventing
    one."""
    from backend.core import aiprovider, media
    mat = get_material(email, product_id)
    shots = [s for s in (mat.get("shots") or []) if s][:limit]
    if not shots:
        return {"ok": False, "reason": "No product photos uploaded yet."}
    if not aiprovider.vision_ready():
        return {"ok": False, "reason": "No vision-capable AI is connected."}

    seen = []
    for url in shots:
        got = media.read(url.rsplit("/", 1)[-1])
        if not got:
            continue
        data, ctype = got
        r = aiprovider.describe_image(
            data, ctype, system=PRODUCT_SYSTEM,
            user="Describe this product exactly as photographed.",
            sensitivity="public", max_tokens=260)
        if r["text"]:
            seen.append(r["text"])

    if not seen:
        return {"ok": False, "reason": "Could not read any of the product photos."}

    if len(seen) == 1:
        desc = seen[0]
    else:
        merged = aiprovider.generate(
            "Several photographs of the SAME product were described separately. "
            "Merge them into one description of that single item. Keep every "
            "concrete detail. Drop anything the readings contradict each other "
            "on rather than picking a side. 80-130 words, plain prose.",
            "\n\n---\n\n".join(seen),
            sensitivity="public", max_tokens=340, fallback=seen[0])
        desc = merged["text"] or seen[0]

    save_material(email, product_id, {"seen": desc.strip()[:1500]})
    return {"ok": True, "seen": desc.strip()[:1500], "read": len(seen)}


def save_brand(email: str, patch: dict) -> dict:
    cur = get_brand(email)
    for k in blank_brand():
        if k in (patch or {}):
            cur[k] = str(patch[k] or "").strip()[:400]
    if cur["look"] not in LOOK_PROMPT:
        cur["look"] = "clean"
    if cur["voice"] not in VOICE_PROMPT:
        cur["voice"] = "warm"
    user_store.set_key(email, BRAND_KEY, cur)
    return cur


def brand_ready(brand: dict) -> bool:
    """Enough to generate something that looks like a brand rather than nothing."""
    return bool((brand.get("about") or "").strip() and (brand.get("name") or "").strip())


# ---------------------------------------------------------------------------
# per-product material
# ---------------------------------------------------------------------------
def blank_material() -> dict:
    return {"story": "", "materials": "", "different": "", "for_who": "",
            "occasions": "", "shots": [], "clips": [],
            # what the AI actually saw in the product photographs — the bridge
            # between "a photo exists" and "the generator knows what it looks like"
            "seen": ""}


def _all_material(email: str) -> dict:
    rows = user_store.get_key(email, PRODUCT_KEY, {}) or {}
    return rows if isinstance(rows, dict) else {}


def get_material(email: str, product_id: str) -> dict:
    return {**blank_material(), **(_all_material(email).get(product_id) or {})}


def save_material(email: str, product_id: str, patch: dict) -> dict:
    rows = _all_material(email)
    cur = {**blank_material(), **(rows.get(product_id) or {})}
    for k in ("story", "materials", "different", "for_who", "occasions", "seen"):
        if k in (patch or {}):
            cur[k] = str(patch[k] or "").strip()[:1500]
    for k in ("shots", "clips"):
        if k in (patch or {}):
            vals = patch[k] if isinstance(patch[k], list) else []
            cur[k] = [str(v).strip()[:500] for v in vals if str(v or "").strip()][:24]
    rows[product_id] = cur
    user_store.set_key(email, PRODUCT_KEY, rows)
    return cur


def completeness(product: dict, material: dict) -> dict:
    """What is missing, and which gap is worth closing first. A checklist of
    empty boxes tells a seller nothing; naming the one that matters does."""
    shots = len(material.get("shots") or []) + (1 if product.get("image_url") else 0)
    checks = [
        {"key": "photos", "ok": shots >= 3, "label": f"{shots} photo{'s' if shots != 1 else ''}",
         "want": "Three or more, from different angles",
         "why": "One photo makes one post. Three makes a week of them."},
        {"key": "story", "ok": bool((material.get("story") or "").strip()),
         "label": "The story behind it", "want": "A few lines",
         "why": "This is what captions are actually made of — without it they read like a catalogue."},
        {"key": "different", "ok": bool((material.get("different") or "").strip()),
         "label": "What makes it different", "want": "One or two lines",
         "why": "The line that makes someone stop scrolling."},
        {"key": "materials", "ok": bool((material.get("materials") or "").strip()),
         "label": "Materials and make", "want": "What it's made of",
         "why": "Concrete detail is what makes a caption believable."},
        {"key": "for_who", "ok": bool((material.get("for_who") or "").strip()),
         "label": "Who it's for", "want": "The person you picture buying it",
         "why": "Lets the caption speak to someone instead of everyone."},
        {"key": "clips", "ok": bool(material.get("clips")),
         "label": "A short clip", "want": "Even five seconds",
         "why": "Reels reach people your photos won't."},
    ]
    done = sum(1 for c in checks if c["ok"])
    nxt = next((c for c in checks if not c["ok"]), None)
    return {
        "score": round(done / len(checks) * 100),
        "done": done, "total": len(checks), "checks": checks,
        "next": nxt,
        "ready": done >= 3,
    }


# ---------------------------------------------------------------------------
# the brief
# ---------------------------------------------------------------------------
def build_brief(brand: dict, product: dict, material: dict, angle: str = "") -> dict:
    """Everything a generator needs, assembled once so the caption and the
    image are made against the same instructions."""
    look = LOOK_PROMPT.get(brand.get("look"), LOOK_PROMPT["clean"])
    voice = VOICE_PROMPT.get(brand.get("voice"), VOICE_PROMPT["warm"])
    facts = [f for f in [
        f"Product: {product.get('name')}",
        f"Category: {product.get('category')}" if product.get("category") else "",
        f"Price: ₹{product.get('price'):,.0f}" if product.get("price") else "",
        f"Made of: {material.get('materials')}" if material.get("materials") else "",
        f"What makes it different: {material.get('different')}" if material.get("different") else "",
        f"The story: {material.get('story')}" if material.get("story") else "",
        f"Who it's for: {material.get('for_who')}" if material.get("for_who") else "",
        f"Occasions: {material.get('occasions')}" if material.get("occasions") else "",
    ] if f]
    return {
        "brand_name": brand.get("name") or "",
        # The written reading of the brand's reference images. Where it exists
        # it outranks the preset look, because a seller's own five pictures
        # describe their taste far better than one of five dropdown options.
        "aesthetic": brand.get("aesthetic") or "",
        # What the AI actually saw in this product's photographs.
        "seen": material.get("seen") or "",
        "about": brand.get("about") or "",
        "audience": brand.get("audience") or "",
        "palette": brand.get("palette") or "",
        "avoid": brand.get("avoid") or "",
        "hashtags": brand.get("hashtags") or "",
        "city": brand.get("city") or "",
        "look_prompt": look,
        "voice_prompt": voice,
        "angle": angle or "",
        "facts": facts,
        "product_name": product.get("name") or "",
    }


def image_prompt(brief: dict, guidance: dict | None = None) -> str:
    """The instruction the image model gets.

    Three sources stack, in decreasing authority:

      1. **What the product actually looks like** (`seen`) — read from the
         seller's own photographs. Without this the model invents a plausible
         kurta, and a plausible kurta is not the one that ships.
      2. **The brand's aesthetic** (`aesthetic`) — read from their reference
         images. This is what makes two sellers with the same product get
         different pictures, which is the entire point of Studio.
      3. **The social guidance** (`guidance`) — which pillar and format this
         image is for. A "product in detail" carousel slide and a "behind the
         scenes" reel cover are not the same photograph.

    The preset `look` is the FALLBACK, used only when no references have been
    read. It is a reasonable default, not the goal."""
    g = guidance or {}
    bits = [f"Instagram-ready photograph for a product: {brief['product_name']}."]

    if brief.get("seen"):
        bits.append(f"The product looks like this: {brief['seen']}")
    else:
        detail = [f for f in brief["facts"] if f.startswith(("Made of", "What makes"))]
        if detail:
            bits.append(" ".join(detail) + ".")

    if brief.get("aesthetic"):
        bits.append(f"Shoot it in this visual language: {brief['aesthetic']}")
    else:
        bits.append(f"Style: {brief['look_prompt']}.")
        if brief.get("palette"):
            bits.append(f"Colour palette: {brief['palette']}.")

    if g.get("shot"):
        bits.append(f"This particular shot: {g['shot']}")
    elif brief.get("angle"):
        bits.append(f"This shot should show: {brief['angle']}.")

    if g.get("aspect"):
        bits.append(f"Composition: {g['aspect']}.")
    else:
        bits.append("Square composition.")

    if brief.get("avoid"):
        bits.append(f"Avoid: {brief['avoid']}.")

    bits.append("Photorealistic, sharp, well-composed. No text, no logo, no "
                "watermark, no hands unless they look natural.")
    return " ".join(bits)


# What each social pillar and format wants out of a picture. The Social Media
# Manager decides WHY a post exists; this translates that into what the camera
# should be doing.
SHOT_FOR_PILLAR = {
    "detail":  "a close, even, well-lit shot that makes the material, weave and "
               "construction readable — this image has to answer 'what is it made of'",
    "new":     "a clean hero shot with space around the product, the kind that "
               "reads as an arrival rather than a restock",
    "proof":   "the product in real use or worn, in an ordinary setting rather "
               "than a studio, so it reads as someone's photo and not a catalogue",
    "founder": "the making or packing of it — hands, workbench, materials, "
               "process; the product need not be the subject",
    "offer":   "a simple, uncluttered shot with clear space where a price or "
               "offer could sit later",
}
ASPECT_FOR_FORMAT = {
    "reel": "vertical 9:16, subject centred with headroom for text at top and bottom",
    "carousel": "square 1:1, subject centred",
    "story": "vertical 9:16, subject in the middle third away from the UI edges",
    "image": "square 1:1, subject centred",
}


def guidance_for(pillar: str = "", fmt: str = "") -> dict:
    """Translate a Social Media Manager slot into camera direction."""
    return {"shot": SHOT_FOR_PILLAR.get(pillar or "", ""),
            "aspect": ASPECT_FOR_FORMAT.get(fmt or "", ""),
            "pillar": pillar or "", "format": fmt or ""}


def caption_prompt(brief: dict) -> str:
    return (
        f"Write an Instagram caption for this product.\n\n"
        f"Brand: {brief['brand_name']}. {brief['about']}\n"
        f"Who buys it: {brief['audience'] or 'not specified'}\n"
        f"Voice: {brief['voice_prompt']}\n"
        + ("\n".join(brief["facts"]) + "\n")
        + (f"Angle for this post: {brief['angle']}\n" if brief.get("angle") else "")
        + (f"Never say: {brief['avoid']}\n" if brief.get("avoid") else "")
        + (f"Always include these hashtags: {brief['hashtags']}\n" if brief.get("hashtags") else "")
        + "\nReturn JSON only: {\"caption\": \"...\", \"hashtags\": [\"...\"], "
          "\"first_comment\": \"...\"}. The caption opens with a line worth "
          "stopping for, is under 60 words, uses no emoji unless the voice calls "
          "for it, and ends with one clear thing to do. 8-12 hashtags, a mix of "
          "broad and specific, no banned or spammy tags."
    )


# ---------------------------------------------------------------------------
# generation
# ---------------------------------------------------------------------------
def openai_ready() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


def generate_caption(brief: dict) -> dict:
    """Copy for one post. Falls back to a written-by-hand template when there is
    no API key, so Studio is never a dead screen."""
    if not openai_ready():
        return _fallback_caption(brief)
    try:
        import json as _json
        from openai import OpenAI
        client = OpenAI()
        r = client.chat.completions.create(
            model=os.environ.get("OPENAI_TEXT_MODEL", "gpt-4.1-mini"),
            messages=[{"role": "user", "content": caption_prompt(brief)}],
            response_format={"type": "json_object"},
            temperature=0.8,
        )
        data = _json.loads(r.choices[0].message.content or "{}")
        return {
            "caption": str(data.get("caption") or "").strip(),
            "hashtags": [str(h).lstrip("#") for h in (data.get("hashtags") or [])][:15],
            "first_comment": str(data.get("first_comment") or "").strip(),
            "generated": True,
        }
    except Exception as e:  # noqa: BLE001
        log.warning("caption generation failed: %s", e)
        return _fallback_caption(brief)


def _fallback_caption(brief: dict) -> dict:
    name = brief["product_name"] or "this one"
    diff = next((f.split(": ", 1)[1] for f in brief["facts"]
                 if f.startswith("What makes it different")), "")
    made = next((f.split(": ", 1)[1] for f in brief["facts"] if f.startswith("Made of")), "")
    lines = [f"{name}." ]
    if diff:
        lines.append(diff.rstrip("."))
    if made:
        lines.append(f"Made of {made.rstrip('.').lower()}.")
    lines.append("Tap the link in bio to order.")
    tags = [t.strip().lstrip("#") for t in (brief.get("hashtags") or "").split() if t.strip()]
    return {"caption": " ".join(lines), "hashtags": tags[:12] or ["handmade", "smallbusiness"],
            "first_comment": "", "generated": False,
            "note": "Written from a template — add an OpenAI key for AI copy."}


def image_engine() -> dict:
    """Which engine will draw, and what it costs.

    Cloudflare Flux Schnell first, and not narrowly: at roughly 19 neurons per
    1024x1024 image it sits inside the free 10,000/day — about 500 images a
    day at no cost — and after that costs around Rs 0.04 against gpt-image-1's
    Rs 3.70. On an unlimited Pro plan that difference is the whole margin: a
    seller generating 200 images a month costs Rs 740 of a Rs 999 subscription
    on OpenAI, and Rs 8 on Flux."""
    from backend.core import aiprovider
    if aiprovider.image_ready():
        return {"engine": "cloudflare", "model": aiprovider.CF_IMAGE_MODEL,
                "free": True,
                "note": "Flux Schnell on Cloudflare — about 500 images a day free."}
    if openai_ready():
        return {"engine": "openai",
                "model": os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1"),
                "free": False,
                "note": "OpenAI. Around Rs 3.70 per image — roughly 90x the "
                        "Cloudflare cost. Add CF_ACCOUNT_ID and CF_API_TOKEN "
                        "to switch."}
    return {"engine": "", "model": "", "free": False,
            "note": "No image engine connected. Your own photos still work."}


def generate_image(email: str, brief: dict, guidance: dict | None = None) -> dict:
    """One AI photograph, stored durably like any other upload."""
    from backend.core import aiprovider
    prompt = image_prompt(brief, guidance)
    eng = image_engine()

    if eng["engine"] == "cloudflare":
        content = aiprovider.generate_image(prompt)
        if not content:
            raise RuntimeError("Cloudflare did not return an image. This is "
                               "usually the daily free allowance being spent.")
    elif eng["engine"] == "openai":
        import base64
        from openai import OpenAI
        client = OpenAI()
        r = client.images.generate(
            model=eng["model"], prompt=prompt, size="1024x1024", n=1)
        item = r.data[0]
        if getattr(item, "b64_json", None):
            content = base64.b64decode(item.b64_json)
        elif getattr(item, "url", None):
            import requests
            content = requests.get(item.url, timeout=45).content
        else:
            raise RuntimeError("The image service returned nothing usable.")
    else:
        raise RuntimeError("No image engine is connected on this server, so "
                           "images cannot be generated. Your own photos still work.")

    saved = media.save(f"{uuid.uuid4().hex}.png", content, email)
    return {"url": saved["url"], "durable": saved["durable"], "generated": True,
            "prompt": prompt, "engine": eng["engine"], "free": eng["free"]}


def generate_image_only(email: str, product_id: str, pillar: str = "",
                        fmt: str = "", angle: str = "") -> dict:
    """Make a picture and nothing else.

    Separate from make_post because the two are wanted at different moments:
    a seller planning a week wants images for slots that already have captions,
    and writing a second caption over the first one would be actively
    unhelpful."""
    brand = get_brand(email)
    product = next((p for p in products.get_products(email) if p["id"] == product_id), None)
    if not product:
        raise ValueError("That product no longer exists.")
    material = get_material(email, product_id)
    brief = build_brief(brand, product, material, angle)
    img = generate_image(email, brief, guidance_for(pillar, fmt))
    return {**img, "product_id": product_id,
            "product_name": product.get("name"),
            "pillar": pillar, "format": fmt,
            "used_aesthetic": bool(brief.get("aesthetic")),
            "used_seen": bool(brief.get("seen"))}


def make_post(email: str, product_id: str, angle: str = "",
              want_image: bool = False, pillar: str = "", fmt: str = "") -> dict:
    """One ready-to-post draft for one product."""
    brand = get_brand(email)
    product = next((p for p in products.get_products(email) if p["id"] == product_id), None)
    if not product:
        raise ValueError("That product no longer exists.")
    material = get_material(email, product_id)
    brief = build_brief(brand, product, material, angle)

    copy = generate_caption(brief)
    own = [s for s in (material.get("shots") or []) if s] or \
          [s for s in [product.get("image_url")] + list(product.get("images") or []) if s]

    out = {
        "product_id": product_id,
        "product_name": product.get("name"),
        "angle": angle,
        "caption": copy["caption"],
        "hashtags": copy["hashtags"],
        "first_comment": copy.get("first_comment") or "",
        "copy_generated": copy.get("generated", False),
        "note": copy.get("note", ""),
        "own_photos": own,
        "image_url": own[0] if own else "",
        "image_is_generated": False,
    }
    if want_image:
        try:
            img = generate_image(email, brief, guidance_for(pillar, fmt))
            out["image_url"] = img["url"]
            out["image_is_generated"] = True
            out["image_prompt"] = img["prompt"]
        except (RuntimeError, Exception) as e:  # noqa: BLE001
            out["image_error"] = str(e)
    return out


def angles(product: dict, material: dict) -> list[dict]:
    """Post ideas built from what this product actually has. Each one names the
    material it draws on, so a seller can see why it was suggested."""
    out = [
        {"id": "hero", "label": "The product, plainly",
         "why": "Your best photo and a line about what it is."},
    ]
    if material.get("story"):
        out.append({"id": "story", "label": "The story behind it",
                    "why": "Drawn from the story you wrote."})
    if material.get("materials"):
        out.append({"id": "detail", "label": "Close on the material",
                    "why": "Uses what you said it's made of."})
    if material.get("different"):
        out.append({"id": "why", "label": "Why this one and not another",
                    "why": "Built on what makes it different."})
    if material.get("occasions"):
        out.append({"id": "occasion", "label": "Where you'd wear or use it",
                    "why": "From the occasions you listed."})
    if material.get("for_who"):
        out.append({"id": "gift", "label": "As a gift",
                    "why": "Aimed at who you said it's for."})
    return out
