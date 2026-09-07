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
    }


def get_brand(email: str) -> dict:
    saved = user_store.get_key(email, BRAND_KEY, {}) or {}
    return {**blank_brand(email), **(saved if isinstance(saved, dict) else {})}


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
            "occasions": "", "shots": [], "clips": []}


def _all_material(email: str) -> dict:
    rows = user_store.get_key(email, PRODUCT_KEY, {}) or {}
    return rows if isinstance(rows, dict) else {}


def get_material(email: str, product_id: str) -> dict:
    return {**blank_material(), **(_all_material(email).get(product_id) or {})}


def save_material(email: str, product_id: str, patch: dict) -> dict:
    rows = _all_material(email)
    cur = {**blank_material(), **(rows.get(product_id) or {})}
    for k in ("story", "materials", "different", "for_who", "occasions"):
        if k in (patch or {}):
            cur[k] = str(patch[k] or "").strip()[:1200]
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


def image_prompt(brief: dict) -> str:
    """The instruction the image model gets. Brand-led, not template-led — the
    whole reason Studio exists is that generic prompts produce generic pictures."""
    bits = [
        f"Instagram-ready product photograph of: {brief['product_name']}.",
        f"Style: {brief['look_prompt']}.",
    ]
    if brief.get("palette"):
        bits.append(f"Colour palette: {brief['palette']}.")
    detail = [f for f in brief["facts"] if f.startswith(("Made of", "What makes"))]
    if detail:
        bits.append(" ".join(detail) + ".")
    if brief.get("about"):
        bits.append(f"The brand: {brief['about'][:200]}.")
    if brief.get("angle"):
        bits.append(f"This shot should show: {brief['angle']}.")
    if brief.get("avoid"):
        bits.append(f"Avoid: {brief['avoid']}.")
    bits.append("Photorealistic, sharp, well-composed. No text, no logo, no watermark, "
                "no hands unless they look natural. Square composition.")
    return " ".join(bits)


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


def generate_image(email: str, brief: dict) -> dict:
    """One AI photograph, stored durably like any other upload."""
    if not openai_ready():
        raise RuntimeError("No OpenAI key is set on the server, so images cannot "
                           "be generated. Your own photos still work.")
    import base64
    from openai import OpenAI
    client = OpenAI()
    r = client.images.generate(
        model=os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1"),
        prompt=image_prompt(brief), size="1024x1024", n=1,
    )
    item = r.data[0]
    if getattr(item, "b64_json", None):
        content = base64.b64decode(item.b64_json)
    elif getattr(item, "url", None):
        import requests
        content = requests.get(item.url, timeout=45).content
    else:
        raise RuntimeError("The image service returned nothing usable.")
    saved = media.save(f"{uuid.uuid4().hex}.png", content, email)
    return {"url": saved["url"], "durable": saved["durable"],
            "generated": True, "prompt": image_prompt(brief)}


def make_post(email: str, product_id: str, angle: str = "",
              want_image: bool = False) -> dict:
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
            img = generate_image(email, brief)
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
