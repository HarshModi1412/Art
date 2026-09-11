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
import re
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


# The kinds of photograph a seller's reference set actually contains.
#
# WHY THIS EXISTS: read_aesthetic used to collapse every reference into ONE
# 100-150 word paragraph describing "what is common to all of them". A seller
# who uploads a packshot, a wearing-it-on-the-street shot, a flat lay and a
# hands-holding-it shot has told you FOUR different things, and averaging them
# produces a description so general it fits any brand — which is why generated
# images came back looking nothing like the references. The differences ARE
# the brand. So each reference is now classified and described in its own
# right, and the generator picks the reading that matches the shot it is
# being asked for.
SHOT_TYPES = {
    "product_only": {
        "label": "Product on its own",
        "hint": "packshot, hero, still life — the product is the whole subject, no person",
    },
    "in_use": {
        "label": "Worn or carried by a person",
        "hint": "someone actually wearing, carrying or using it, in a real setting",
    },
    "held": {
        "label": "Held in hands",
        "hint": "hands presenting or holding the product, face usually out of frame",
    },
    "lifestyle": {
        "label": "Lying in a scene",
        "hint": "placed on a surface among props — table, bed, chair — nobody in frame",
    },
    "packaging": {
        "label": "Packaging and unboxing",
        "hint": "box, pouch, tissue, tags; often half-open mid-reveal",
    },
    "detail": {
        "label": "Close detail",
        "hint": "macro crop on stitching, clasp, weave, hardware, stone or texture",
    },
}
SHOT_TYPE_IDS = list(SHOT_TYPES)

# WHY THIS PROMPT IS SO DEMANDING: the first version asked for one sentence
# per field and got exactly that — a reading so thin it described any brand and
# generated none. The output a seller saw ("soft diffused light, muted palette,
# shallow depth of field, calm mood") is true of roughly every product
# photograph ever taken, so it steered the image model nowhere.
#
# Three changes fix it, and all three are needed:
#   * more FIELDS, so the model has to look at things it was skipping — lens,
#     grade, props, the actual arrangement;
#   * a WORD FLOOR per field, because a model asked for "a sentence" writes the
#     shortest true sentence available, and the shortest true sentence about
#     lighting is "soft natural light";
#   * a demand for VALUES not adjectives — approximate hex, an f-stop guess, a
#     focal length, a clock direction for the key light. A number cannot be
#     vague, so asking for numbers is the cheapest way to force real looking.
AESTHETIC_SYSTEM = (
    "You are a photographer's art director. You are shown ONE reference image a "
    "brand chose to represent its taste. Reverse-engineer HOW IT WAS SHOT, in "
    "enough detail that another photographer could reproduce the look with a "
    "different product and it would still belong in the same feed.\n\n"
    "Return exactly these labelled lines, in this order, nothing before or "
    "after:\n"
    "SHOT: <one of: " + ", ".join(SHOT_TYPE_IDS) + ">\n"
    "LIGHT: <40+ words. Key light: hard or soft, its direction as a clock "
    "position and rough height, apparent size and distance. Colour temperature. "
    "Fill and how much. Where the shadows fall, how sharp their edges are, how "
    "deep they go. Any rim, kicker or bounce. Named if you can see it — window "
    "light, overcast, softbox, bare sun, ring light, practical lamp.>\n"
    "PALETTE: <40+ words. The dominant colours with approximate hex values, the "
    "background colour, the accents, and roughly what share of frame each takes. "
    "Say whether it is saturated or desaturated and by how much.>\n"
    "SURFACE: <25+ words. What the product rests on or against, its material and "
    "texture, and how that surface reads — polished, raw, woven, worn.>\n"
    "PROPS: <25+ words. Every object in frame besides the product, and how they "
    "are arranged relative to it. Say 'nothing else in frame' if that is true.>\n"
    "COMPOSITION: <35+ words. Crop and aspect, camera height and angle relative "
    "to the product, where the subject sits in the frame, how much negative "
    "space and where, symmetry or deliberate imbalance, leading lines.>\n"
    "LENS: <25+ words. Apparent focal length, how compressed or wide the "
    "perspective looks, subject distance, depth of field with an f-stop guess, "
    "and what falls out of focus.>\n"
    "GRADE: <25+ words. Contrast, whether blacks are lifted or crushed, "
    "highlight rolloff, any colour cast in shadows or highlights, grain or "
    "cleanliness, and how processed it looks.>\n"
    "MOOD: <25+ words. What the picture feels like AND the specific choices "
    "creating that feeling.>\n"
    "SIGNATURE: <25+ words. The one habit that would let a stranger recognise "
    "another photograph by this brand.>\n"
    "REPEATABLE: <35+ words. A direct instruction another photographer could "
    "follow to shoot a DIFFERENT product in this exact style.>\n\n"
    "Rules. Be specific to THIS picture: 'low winter sun from camera-left at "
    "about 20 degrees, throwing a hard shadow twice the length of the product "
    "across raw grey concrete' is the standard; 'nice natural light' is a "
    "failure. Give numbers wherever you can — hex, f-stop, focal length, clock "
    "position, percentages of frame — and mark them as estimates. Never use "
    "praise or marketing adjectives such as stunning, elevated, timeless, "
    "premium or aesthetic. If something is genuinely not visible, say so "
    "plainly instead of inventing it. No bullets, no headings, no preamble."
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


def _parse_reading(text: str) -> dict:
    """One reference image's reading, as fields rather than a paragraph."""
    out = {}
    cur = None
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^\s*(SHOT|LIGHT|COLOUR|COLOR|PALETTE|SETTING|SURFACE|"
                     r"PROPS|COMPOSITION|LENS|GRADE|MOOD|SIGNATURE|REPEATABLE)"
                     r"\s*:\s*(.*)$", line, re.I)
        if m:
            key = m.group(1).lower()
            key = {"color": "palette", "colour": "palette",
                   "setting": "surface"}.get(key, key)
            out[key] = m.group(2).strip()[:1200]
            cur = key
        elif cur and cur != "shot":
            # A model writing 40 words will wrap. Keeping the continuation is
            # the difference between a full reading and its first line.
            out[cur] = f"{out[cur]} {line}".strip()[:1200]
    shot = (out.get("shot") or "").lower().strip()
    # Models like to answer with the label rather than the id; accept both, and
    # fall back to the safest bucket rather than dropping the reading.
    if shot not in SHOT_TYPES:
        shot = next((k for k in SHOT_TYPES
                     if k in shot or SHOT_TYPES[k]["label"].lower() in shot),
                    "product_only")
    out["shot"] = shot
    return out


# The order a photographer would want to read them in, and the order they are
# handed to the image model.
READING_FIELDS = ("light", "palette", "surface", "props", "composition",
                  "lens", "grade", "mood", "signature", "repeatable")


def _reading_prose(r: dict) -> str:
    """One reading as a shootable brief, labels kept.

    The labels stay in deliberately. This string is pasted into the image
    prompt, and "LIGHT: ... PALETTE: ..." survives being embedded in a longer
    instruction far better than a run-on paragraph, which models skim."""
    return "\n".join(f"{k.upper()}: {r[k]}" for k in READING_FIELDS
                     if r.get(k)).strip()


def read_aesthetic(email: str) -> dict:
    """Turn the reference images into a written aesthetic — by SHOT TYPE.

    WHAT CHANGED AND WHY: this used to read at most four references and merge
    them into one paragraph of "what they have in common". That was the wrong
    shape twice over. It threw away most of what a seller uploaded, and the
    merge step actively deleted the differences: a brand that shoots crisp
    packshots AND grainy street photographs came back as "clean, natural
    light", which describes neither and generates neither. Sellers noticed —
    the generated image looked nothing like the pictures they had given it.

    Now every reference is read on its own and filed under the kind of
    photograph it is. The brand keeps a SIGNATURE (what genuinely holds across
    all of them, which is what makes a feed look like one brand) and a
    per-shot-type reading (what makes an unboxing shot different from a
    packshot, which is what makes each post look different from the last).
    image_prompt then asks for the slice it needs."""
    from backend.core import aicaps
    aicaps.check(email, "vision")
    from backend.core import aiprovider, media
    b = get_brand(email)
    refs = [r for r in (b.get("refs") or []) if r][:12]
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
            user="Read this reference image and return the labelled lines.",
            # 400 was the ceiling that made every reading two lines long. Ten
            # fields with a 25-40 word floor each needs room to land; the free
            # tiers all allow it, and Cloudflare in particular defaults to a
            # very low cap unless it is told otherwise.
            sensitivity="public", max_tokens=2000)
        if r["text"]:
            parsed = _parse_reading(r["text"])
            if _reading_prose(parsed):
                readings.append(parsed)
            else:
                # Unparseable but non-empty — keep the prose rather than lose
                # a picture the seller paid attention to.
                readings.append({"shot": "product_only",
                                 "signature": r["text"].strip()[:1200]})
        else:
            failed += 1

    if not readings:
        return {"ok": False, "reason": "Could not read any of the reference images."}

    # One reading per shot type, so a brand that uploaded five packshots does
    # not get five near-identical paragraphs stored.
    by_shot: dict[str, list[str]] = {}
    for r in readings:
        by_shot.setdefault(r["shot"], []).append(_reading_prose(r))
    shots = {k: max(v, key=len)[:2500] for k, v in by_shot.items() if any(v)}

    signature = ""
    sig_lines = [r.get("signature", "") for r in readings if r.get("signature")]
    if len(readings) == 1:
        signature = _reading_prose(readings[0])
    else:
        # The old version of this asked for "90-130 words, plain prose" and got
        # exactly that: one short paragraph that fit any brand. It also leaked
        # its own instruction into the output ("If the references genuinely
        # disagree on look, it's in..."), which is what a model does when the
        # instruction is easier to restate than to follow. This asks for a
        # working document instead, with named sections and rules a
        # photographer could actually shoot from.
        merged = aiprovider.generate(
            "You are an art director writing an ESSAY about a brand's "
            "photography, built from separate readings of their own reference "
            "images. Not a summary and not a checklist — a piece of writing a "
            "photographer could read once and then shoot from, and a piece the "
            "brand's owner would recognise as a description of their own "
            "taste.\n\n"
            "Write it as flowing prose in short paragraphs under these "
            "headings. Under each heading write 60-110 words of real sentences "
            "— explain WHY the choice reads the way it does, not just what it "
            "is. 'The key sits low and to the left, which is why every shadow "
            "runs long across the frame and the whole set feels like late "
            "afternoon rather than a studio' is the register. Never a bullet "
            "list.\n\n"
            "Use exactly these headings, each on its own line:\n"
            "LIGHT — the lighting setup this brand repeats. Direction, quality, "
            "colour temperature, shadow behaviour. Give the setup, not an "
            "adjective.\n"
            "PALETTE — the actual colours, with approximate hex. Say which "
            "dominate, which are accents, and what the background usually is.\n"
            "SURFACES AND PROPS — what they shoot on and what they put in "
            "frame, and equally what never appears.\n"
            "FRAMING — crop, camera height and angle, where the subject sits, "
            "how much negative space and where.\n"
            "LENS AND DEPTH — focal length and depth of field they favour, and "
            "what they let fall out of focus.\n"
            "GRADE — contrast, black level, highlight rolloff, colour cast, how "
            "processed the files look.\n"
            "RULES — five to eight numbered, specific, checkable instructions. "
            "Each must be something a photographer could obey or break, e.g. "
            "'key light always from camera-left, never frontal' or 'the product "
            "never touches the frame edge'.\n"
            "WHERE THEY VARY — the genuine differences between their images. "
            "Name them; do not average them away.\n\n"
            "Be concrete and quantitative wherever the readings support it — "
            "name the hex, the f-stop, the direction — but carry those inside "
            "sentences rather than listing them. Never use praise or marketing "
            "words such as stunning, elevated, timeless, premium, curated or "
            "aesthetic. Do not restate these instructions in your answer — "
            "follow them. Aim for 650-900 words in total: this is the document "
            "the whole feature rests on, and a thin one is worth nothing.",
            "\n\n=== NEXT REFERENCE ===\n\n".join(
                f"[{SHOT_TYPES.get(r['shot'], {}).get('label', r['shot'])}]\n"
                + _reading_prose(r) for r in readings),
            sensitivity="public", max_tokens=3000, fallback="")
        signature = (merged["text"] or " ".join(sig_lines) or
                     _reading_prose(readings[0]))

    # Three layers, deliberately kept apart rather than flattened into one
    # paragraph — each answers a different question, and merging them is what
    # made generated pictures look like nobody's brand in particular:
    #   aesthetic        the THEME. What holds across everything they shoot.
    #   aesthetic_shots  the TYPES. How an unboxing differs from a packshot.
    #   aesthetic_reads  every INDIVIDUAL picture, kept so the seller can see
    #                    what was read out of each one and nothing is silently
    #                    averaged away.
    b["aesthetic"] = signature.strip()[:9000]
    # And the version the image model can actually use. See distil_aesthetic().
    b["aesthetic_directive"] = ""
    b["directive_from"] = ""
    b["aesthetic_shots"] = shots
    b["aesthetic_reads"] = [{"shot": r["shot"], "shot_label":
                             SHOT_TYPES.get(r["shot"], {}).get("label", r["shot"]),
                             "reading": _reading_prose(r)[:2500]}
                            for r in readings][:12]
    b["aesthetic_from"] = len(readings)
    user_store.set_key(email, BRAND_KEY, b)
    # One read is one charge against the vision budget however many references it
    # looked at — the seller asked for one thing.
    aicaps.consume(email, "vision")
    return {"ok": True, "aesthetic": b["aesthetic"], "shots": shots,
            "reads": b["aesthetic_reads"],
            "shot_labels": {k: SHOT_TYPES[k]["label"] for k in shots
                            if k in SHOT_TYPES},
            "read": len(readings), "failed": failed, "brand": b}


# ---------------------------------------------------------------------------
# From the essay to the camera
# ---------------------------------------------------------------------------
# THE BUG THIS FIXES, and it is the reason generated pictures barely looked like
# the seller's brand even after the aesthetic reading got long and good:
#
# image_prompt() pasted the WHOLE essay in, verbatim. The essay is 650-900 words
# by design — that is what makes it worth reading, and the seller asked for it.
# But an image model does not read 900 words. gpt-image-1's edit call truncates a
# long prompt; anything built on CLIP text encoding (Flux, SD) hard-stops at 77
# TOKENS, which is about fifty words. So the model saw the LIGHT paragraph and a
# sentence of PALETTE, and everything after it — surfaces, framing, lens, grade,
# and the numbered RULES, which are the most shootable part of the whole document
# — was silently discarded. The essay was not being ignored because it was bad.
# It was being cut off because it was long.
#
# Two audiences need two artefacts, so there are two:
#   `aesthetic`           the essay. For the seller to read and correct.
#   `aesthetic_directive` 70-110 words of camera instructions, front-loaded with
#                         the things that survive truncation. For the model.
#
# It is derived once per essay and cached against a fingerprint of that essay, so
# it costs one extra call per re-read of the references, not one per image.
DIRECTIVE_WORDS = (70, 110)


def _fingerprint(text: str) -> str:
    import hashlib
    return hashlib.sha1((text or "").encode("utf-8", "ignore")).hexdigest()[:16]


def distil_aesthetic(email: str, brand: dict | None = None) -> str:
    """The essay, compressed into instructions a camera could follow.

    Ordering inside the result is deliberate: light, then palette with hex, then
    surface and background, then framing and lens, then grade, then the two or
    three hardest rules. If a model truncates, it truncates the least important
    end.
    """
    from backend.core import aiprovider

    b = brand if brand is not None else get_brand(email)
    essay = (b.get("aesthetic") or "").strip()
    if not essay:
        return ""
    fp = _fingerprint(essay)
    if b.get("aesthetic_directive") and b.get("directive_from") == fp:
        return b["aesthetic_directive"]

    lo, hi = DIRECTIVE_WORDS
    out = aiprovider.generate(
        "You are turning an art director's essay about a brand's photography "
        "into the instruction line a photographer is handed on set. "
        f"Write {lo}-{hi} words, one paragraph, no headings, no bullet points, "
        "no preamble.\n\n"
        "Include, in this order, only what the essay actually supports:\n"
        "1. the lighting setup — direction, quality, colour temperature;\n"
        "2. the palette, with hex values, saying which dominates and what the "
        "background is;\n"
        "3. what the product sits on or against;\n"
        "4. framing and camera height, and the lens or depth of field;\n"
        "5. the grade — contrast, black level, any colour cast;\n"
        "6. end with the two or three strictest rules as short clauses, e.g. "
        "'key from camera-left, never frontal; product never touches the frame "
        "edge'.\n\n"
        "Write it as instructions to a camera, not description of a mood. Every "
        "clause must be something a photographer either did or did not do. Never "
        "use praise or marketing words. Do not mention the essay, the brand's "
        "name, or these instructions.",
        essay[:7000], sensitivity="public", max_tokens=400, fallback="")

    directive = (out.get("text") or "").strip()
    if not directive:
        # No AI available. Take the RULES section and the first sentence of each
        # other section — worse than the model's version, far better than the
        # first fifty words of the essay, which is what happened before.
        directive = _directive_fallback(essay)
    directive = " ".join(directive.split())[:1400]

    b["aesthetic_directive"] = directive
    b["directive_from"] = fp
    user_store.set_key(email, BRAND_KEY, b)
    return directive


_DIRECTIVE_ORDER = ("LIGHT", "PALETTE", "SURFACES AND PROPS", "FRAMING",
                    "LENS AND DEPTH", "GRADE", "RULES")


def _directive_fallback(essay: str) -> str:
    """Deterministic compression: first sentence per section, plus the rules.

    Used when no text model is reachable. Keeps the same priority order as the
    prompt above so the head of the string is still the useful part.
    """
    sections: dict[str, str] = {}
    current = ""
    # Longest heading first, so "LENS AND DEPTH" is not swallowed by a prefix
    # match. The heading and its prose share a line, separated by an em dash,
    # a hyphen or a colon depending on what the model felt like.
    heads = sorted(_DIRECTIVE_ORDER, key=len, reverse=True)
    for line in (essay or "").splitlines():
        raw = line.strip()
        head = raw.upper()
        hit = next((h for h in heads
                    if head.startswith(h)
                    and (len(head) == len(h) or head[len(h)] in " \u2014-:\u2013")), None)
        if hit:
            current = hit
            sections[current] = raw[len(hit):].lstrip(" \u2014\u2013-:")
            continue
        if current:
            sections[current] = (sections.get(current, "") + " " + raw).strip()

    parts = []
    for h in _DIRECTIVE_ORDER:
        body = " ".join((sections.get(h) or "").split())
        if not body:
            continue
        if h == "RULES":
            # The rules are the shootable part — keep up to three whole ones.
            rules = re.split(r"(?:^|\s)\d+[.)]\s*", body)
            keep = [r.strip(" .;") for r in rules if len(r.strip()) > 12][:3]
            if keep:
                parts.append("; ".join(keep) + ".")
        else:
            first = re.split(r"(?<=[.!?])\s+", body)[0]
            if first:
                parts.append(first if first.endswith((".", "!", "?")) else first + ".")
    return " ".join(parts)


def shootable_shot_types(email: str) -> list[str]:
    """Which kinds of photograph this seller has actually shown they shoot.

    The Social Media Manager plans a week of posts, and some archetypes only
    work if the seller can produce that kind of picture: an unboxing beat is
    useless to someone who has never photographed their packaging. Their own
    reference set is the honest answer to what they can produce, so the
    planner favours archetypes backed by a real reference and treats the rest
    as a stretch rather than a default.

    Empty means "we do not know yet" — NOT "they can shoot nothing" — and the
    planner falls back to the full range rather than refusing to plan."""
    try:
        shots = (get_brand(email) or {}).get("aesthetic_shots") or {}
        return [k for k in shots if k in SHOT_TYPES and shots[k]]
    except Exception:  # noqa: BLE001 — never let this stop a week being planned
        return []


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
        # The camera-ready compression of that essay. This is what the image
        # model is given; the essay is what the seller reads. See
        # distil_aesthetic() for why they cannot be the same string.
        "aesthetic_directive": brand.get("aesthetic_directive") or "",
        # And the per-shot-type readings, so a post asking for an unboxing
        # shot is shot like their unboxing references rather than like the
        # average of everything they uploaded.
        "aesthetic_shots": brand.get("aesthetic_shots") or {},
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


def image_prompt(brief: dict, guidance: dict | None = None,
                 has_reference: bool = False) -> str:
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
    read. It is a reasonable default, not the goal.

    `has_reference` says whether the seller's own photograph is the starting
    point. It changes exactly one thing, and it matters: a blanket "no text, no
    logo" told the model to WIPE the brand name that is embossed, printed or
    stitched onto the product itself. A wallet whose reference photo carries
    the maker's name came back blank, which reads as a counterfeit of the
    seller's own product. Re-shooting keeps whatever is physically on the item
    exactly as it is; only ADDED text and watermarks are refused."""
    g = guidance or {}
    bits = [f"Instagram-ready photograph for a product: {brief['product_name']}."]

    if brief.get("seen"):
        bits.append(f"The product looks like this: {brief['seen']}")
    else:
        detail = [f for f in brief["facts"] if f.startswith(("Made of", "What makes"))]
        if detail:
            bits.append(" ".join(detail) + ".")

    # ORDER MATTERS HERE. Everything below this line may be cut off by the
    # model's prompt limit, so the brand's own look goes near the top rather
    # than after the festival notes and the aspect ratio.
    if brief.get("aesthetic_directive"):
        bits.append(f"Shoot it exactly like this: {brief['aesthetic_directive']}")
    elif brief.get("aesthetic"):
        # No directive yet (references read before this existed). Take the head
        # of the essay rather than all 900 words — the tail was being silently
        # discarded anyway, and a shorter honest prompt beats a truncated one.
        bits.append("Shoot it in this visual language: "
                    + " ".join(brief["aesthetic"].split())[:900])
    else:
        bits.append(f"Style: {brief['look_prompt']}.")
        if brief.get("palette"):
            bits.append(f"Colour palette: {brief['palette']}.")

    # The seller's own reference for THIS kind of photograph, when they have
    # one. This is what stops every post in a week looking like the same
    # picture: an unboxing beat is shot like their unboxing references, a
    # worn-in-the-street beat like their street references.
    shot_type = g.get("shot_type") or ""
    ref_shots = brief.get("aesthetic_shots") or {}
    if shot_type and ref_shots.get(shot_type):
        spec = SHOT_TYPES.get(shot_type, {})
        # Trimmed for the same reason as the essay: a full per-shot reading can
        # run several hundred words and push the rest of the prompt off the end.
        own = " ".join(str(ref_shots[shot_type]).split())[:700]
        bits.append(f"This is a {spec.get('label', shot_type)} shot "
                    f"({spec.get('hint', '')}). Their own reference for this kind "
                    f"of photograph reads: {own}")
    elif shot_type and shot_type in SHOT_TYPES:
        spec = SHOT_TYPES[shot_type]
        bits.append(f"This is a {spec['label']} shot: {spec['hint']}.")

    if g.get("shot"):
        bits.append(f"This particular shot: {g['shot']}")
    elif brief.get("angle"):
        bits.append(f"This shot should show: {brief['angle']}.")

    if g.get("festival"):
        colours = ", ".join(g.get("festival_colours") or [])
        motifs = ", ".join(g.get("festival_motifs") or [])
        bits.append(f"This is for {g['festival']}: {g.get('festive_intensity', '')}."
                    + (f" Work in these colours where they fit naturally: {colours}."
                       if colours else "")
                    + (f" A motif from this festival may appear, if it fits without "
                       f"crowding the product: {motifs}." if motifs else ""))

    if g.get("aspect"):
        bits.append(f"Composition: {g['aspect']}.")
    else:
        bits.append("Square composition.")

    if brief.get("avoid"):
        bits.append(f"Avoid: {brief['avoid']}.")

    if has_reference:
        # The product's OWN branding is part of the product. Erasing it was the
        # bug; the model is told to reproduce it rather than to invent one.
        bits.append("Keep the product itself exactly as it is in the reference, "
                    "including any brand name, logo, monogram, stitching or "
                    "lettering on it — reproduce those markings exactly where "
                    "and as they appear, same spelling, same placement. Do not "
                    "add any new text, logo or watermark of your own.")
        bits.append("Photorealistic, sharp, well-composed. No hands unless they "
                    "look natural.")
    else:
        bits.append("Photorealistic, sharp, well-composed. No text, no logo, no "
                    "watermark, no hands unless they look natural.")
    return " ".join(bits)


# How hard a generated photo should lean into a festival, by brand LOOK.
#
# The bug this exists to fix: image_prompt() had no idea a post was for
# Ganesh Chaturthi at all -- guidance_for() only ever carried pillar and
# format, never the occasion, so every "festive" post got exactly the same
# picture a plain product post would have. Threading the festival through is
# only half the fix, though -- a "Dark & luxurious" wallet brand and a
# "Bright & playful" jewellery brand should not get the same DOSE of diyas
# and marigold for the same festival. This is the dial: a subtler brand gets
# one tasteful detail, a bolder one gets the full colour-and-motif treatment.
FESTIVE_INTENSITY = {
    "clean":     "one small, tasteful festive detail near the product -- not a themed backdrop",
    "warm":      "a few natural festive touches in frame -- warm light, a motif placed casually, nothing staged",
    "luxe":      "restrained festive luxury -- gold light and a single motif, never busy or bright",
    "bright":    "the product fully styled into the festival's colours and motifs",
    "editorial": "a styled festival set, shot like a magazine feature rather than a greeting card",
}


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


def guidance_for(pillar: str = "", fmt: str = "", occasion_key: str = "",
                 brand_look: str = "", shot_type: str = "") -> dict:
    """Translate a Social Media Manager slot into camera direction.

    occasion_key is the festival's slug in playbook.FESTIVALS (e.g.
    "ganesh_chaturthi"), the same table Social already writes captions from --
    so a post's photo and its caption agree on which festival's colours and
    motifs they mean, instead of the caption knowing and the photo not.

    shot_type is the archetype this beat of the week is (see SHOT_TYPES) --
    an unboxing, a worn-in-use shot, a macro detail. It is what stops seven
    posts in a week from being seven versions of the same photograph."""
    g = {"shot": SHOT_FOR_PILLAR.get(pillar or "", ""),
         "aspect": ASPECT_FOR_FORMAT.get(fmt or "", ""),
         "shot_type": shot_type or "",
         "pillar": pillar or "", "format": fmt or ""}
    if occasion_key:
        from backend.core import playbook
        fest = playbook.FESTIVALS.get(occasion_key)
        if fest:
            g["festival"] = fest["name"]
            g["festival_colours"] = fest.get("colours", [])[:4]
            g["festival_motifs"] = fest.get("motifs", [])[:4]
            g["festive_intensity"] = FESTIVE_INTENSITY.get(
                brand_look or "clean", FESTIVE_INTENSITY["clean"])
    return g


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
    """Copy for one post, through the content writer's provider chain (Puter
    first when configured, then the free tiers, then OpenAI). Falls back to a
    written-by-hand template when nothing is reachable, so Studio is never a
    dead screen."""
    from backend.core import aiprovider, writer
    res = aiprovider.generate(writer.WRITER_SYSTEM, caption_prompt(brief),
                              sensitivity="public", max_tokens=600, temperature=0.8,
                              fallback="", role="writer")
    data = writer._json(res.get("text", "")) if res.get("text") else {}
    if data.get("caption"):
        return {
            "caption": str(data.get("caption") or "").strip(),
            "hashtags": [str(h).lstrip("#") for h in (data.get("hashtags") or [])][:15],
            "first_comment": str(data.get("first_comment") or "").strip(),
            "generated": True, "provider": res.get("provider"),
        }
    if res.get("error"):
        log.warning("caption generation failed: %s", res.get("error"))
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
            "note": "Written from a template — connect an AI provider (Puter, or any "
                    "in the chain) for AI copy."}


# Every engine that can draw, in default preference order.
#
# WHY A REGISTRY AND NOT AN IF-CHAIN: the seller wants to pick the engine per
# generation, not inherit whatever the server happened to prefer. An if-chain
# can only answer "which one now"; a list can also answer "what are my
# options, what does each cost, and which handle a re-shoot properly" — which
# is what a picker needs.
#
# `reshoot` is the field that matters most. It says whether the engine can
# take the seller's own photograph as input and keep the product intact.
# Engines without it can still draw a picture, but asking one for a "re-shoot"
# would quietly hand back a different wallet, so the caller must not offer it
# for that job.
IMAGE_ENGINES = [
    {"id": "openai", "label": "ChatGPT (OpenAI)",
     "model_env": "OPENAI_IMAGE_MODEL", "model_default": "gpt-image-1",
     "free": False, "reshoot": True, "cost": "about Rs 3.70 an image",
     "note": "The default. Best all-round quality, and its edit call holds on "
             "to your product's real details. Paid per image."},
    {"id": "gemini", "label": "Google Gemini",
     "model_env": "GEMINI_IMAGE_MODEL", "model_default": "gemini-2.5-flash-image",
     "free": True, "reshoot": True, "cost": "free tier, then paid",
     "note": "Very good at keeping a real product — including any lettering on "
             "it — when re-shooting. Free tier available."},
    {"id": "cloudflare", "label": "Cloudflare (Flux)",
     "model_env": "CF_IMAGE_MODEL",
     "model_default": "@cf/black-forest-labs/flux-1-schnell",
     "free": True, "reshoot": False, "cost": "about 500 images a day free",
     "note": "Cheapest by far, and fine for an invented backdrop. Its only "
             "image-to-image model redraws the product, so it is not offered "
             "for re-shoots."},
    {"id": "huggingface", "label": "Hugging Face",
     "model_env": "HF_EDIT_MODEL", "model_default": "Qwen/Qwen-Image-Edit-2511",
     "free": False, "reshoot": True, "cost": "about $0.03 an edit",
     "note": "Credit-metered. A free account's monthly allowance covers about "
             "four edits, so this needs PRO or pay-as-you-go."},
]


def _engine_ready(eid: str) -> bool:
    from backend.core import aiprovider
    return {
        "openai": openai_ready,
        "gemini": aiprovider.gemini_image_ready,
        "cloudflare": aiprovider.image_ready,
        "huggingface": aiprovider.hf_ready,
    }.get(eid, lambda: False)()


def _engine_row(spec: dict) -> dict:
    return {"engine": spec["id"], "id": spec["id"], "label": spec["label"],
            "model": os.environ.get(spec["model_env"]) or spec["model_default"],
            "free": spec["free"], "reshoot": spec["reshoot"],
            "cost": spec["cost"], "note": spec["note"],
            "ready": _engine_ready(spec["id"])}


def image_engines(for_reshoot: bool = False) -> list[dict]:
    """Every drawing engine this server can offer, so the seller can choose.

    Only CONFIGURED engines are returned — offering a choice that then fails
    for want of a key is worse than not offering it. When `for_reshoot` is set,
    engines that cannot preserve a source photograph are dropped rather than
    silently substituting an invented product."""
    rows = [_engine_row(s) for s in IMAGE_ENGINES if _engine_ready(s["id"])]
    return [r for r in rows if r["reshoot"]] if for_reshoot else rows


def image_engine(preferred: str = "", for_reshoot: bool = False) -> dict:
    """The engine that will draw, honouring the seller's choice when they made
    one and it is actually usable.

    ChatGPT is the default. It was Hugging Face until the credits ran out, and
    before that Cloudflare — the ordering is a running answer to "what is both
    good and available", not a permanent judgement."""
    options = image_engines(for_reshoot)
    if preferred:
        pick = next((r for r in options if r["id"] == preferred), None)
        if pick:
            return pick
        # A named engine that is not usable is worth saying out loud rather
        # than silently drawing on a different one — the seller chose for a
        # reason, and the picture would come back looking wrong to them.
        spec = next((s for s in IMAGE_ENGINES if s["id"] == preferred), None)
        if spec and for_reshoot and not spec["reshoot"]:
            raise ValueError(
                f"{spec['label']} cannot re-shoot from your own photograph — it "
                f"would redraw the product. Use 'Invent a picture' with it, or "
                f"pick another engine for a re-shoot.")
        raise ValueError(
            f"{(spec or {}).get('label', preferred)} is not connected on this "
            f"server. Pick another engine, or add its key.")
    if options:
        return options[0]
    return {"engine": "", "id": "", "label": "", "model": "", "free": False,
            "reshoot": False, "ready": False, "cost": "",
            "note": "No image engine connected. Your own photos still work."}


def _reference_shot(email: str, product: dict, material: dict) -> tuple[bytes, str] | None:
    """The seller's own photograph of this product, if there is one."""
    from backend.core import media
    urls = [u for u in (material.get("shots") or []) if u]
    urls += [u for u in [product.get("image_url")] + list(product.get("images") or []) if u]
    for u in urls:
        got = media.read(u.rsplit("/", 1)[-1])
        if got:
            return got
    return None


def _openai_image(prompt: str, reference: tuple[bytes, str] | None) -> tuple[bytes, bool]:
    """The OpenAI/ChatGPT image call. Returns (bytes, from_reference).

    Two different endpoints, and the difference matters more than anything
    else here: images.edit() is the actual image-to-image call — it takes
    the source image (no mask needed for a full re-render, a mask is only
    for inpainting one region) and re-renders it against the prompt.
    input_fidelity="high" asks the model to hold onto the source's actual
    features rather than loosely reinterpreting them, which is the entire
    point of a re-shoot: the item in the photo has to be the item that ships.
    images.generate() is plain text-to-image and has no argument for a
    source image at all — calling it for a re-shoot would silently throw
    the seller's own photo away, which is the bug this split exists to
    prevent."""
    import base64
    from openai import OpenAI
    client = OpenAI()
    model = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1")
    if reference:
        ref_bytes, ref_mime = reference
        ext = "png" if "png" in (ref_mime or "") else "jpg"
        r = client.images.edit(
            model=model, image=(f"reference.{ext}", ref_bytes, ref_mime or "image/jpeg"),
            prompt=prompt, size="1024x1024", input_fidelity="high", n=1)
        from_ref = True
    else:
        r = client.images.generate(model=model, prompt=prompt, size="1024x1024", n=1)
        from_ref = False
    item = r.data[0]
    if getattr(item, "b64_json", None):
        content = base64.b64decode(item.b64_json)
    elif getattr(item, "url", None):
        import requests
        content = requests.get(item.url, timeout=45).content
    else:
        raise RuntimeError("The image service returned nothing usable.")
    return content, from_ref


def generate_image(email: str, brief: dict, guidance: dict | None = None,
                   reference: tuple[bytes, str] | None = None,
                   strength: float | None = None, engine: str = "") -> dict:
    """One photograph, stored durably like any other upload.

    Two paths, and the difference matters more than anything else in Studio:

      * **With a reference** — the seller's own photo is re-shot. Same garment,
        same stones, same colour; new light and setting. The thing in the
        picture is the thing that ships.
      * **Without one** — the model invents a product from the description.
        Fine for a backdrop or a mood piece; NOT fine as "here is my kurta",
        because it is not their kurta.

    The result says which path ran, so the UI can tell the seller plainly.

    Which AI draws is the SELLER's choice, passed in as `engine` and validated
    against the registry by image_engine(). An empty `engine` means "use the
    default", which is ChatGPT. There is no cross-vendor fallback: see the
    comment on the dispatch below for why.
    """
    from backend.core import aiprovider, aicaps
    # A ceiling on our own spend, checked before anything is called and counted
    # only after it succeeds. See backend/core/aicaps.py — this sits underneath
    # billing and applies on every plan, including in launch mode, because the
    # cost here is real money per call rather than a feature flag.
    aicaps.check(email, "image")
    # Make sure the brand's essay has been compressed for the camera before we
    # build the prompt. Cached against the essay, so this is one call the first
    # time after a re-read and free afterwards.
    if brief.get("aesthetic") and not brief.get("aesthetic_directive"):
        try:
            brief = {**brief, "aesthetic_directive": distil_aesthetic(email)}
        except Exception as e:  # noqa: BLE001 — never block a generation on this
            log.warning("could not distil the aesthetic: %s", e)
    prompt = image_prompt(brief, guidance, has_reference=bool(reference))
    eng = image_engine(engine, for_reshoot=bool(reference))   # raises if unusable
    if not eng["engine"]:
        raise RuntimeError("No image engine is connected on this server, so "
                           "images cannot be generated. Your own photos still work.")

    # ONE dispatch, one engine. This used to be a chain that quietly tried a
    # different vendor when the first failed — which was fine while the server
    # chose, and wrong the moment the SELLER chooses: silently drawing on an
    # engine they did not pick, at a price they did not agree to, is not a
    # fallback, it is a substitution. A failure now says which engine failed
    # and leaves the choice with them.
    content, from_ref = None, False
    eid = eng["engine"]
    try:
        if eid == "openai":
            content, from_ref = _openai_image(prompt, reference)
        elif eid == "gemini":
            content = aiprovider.gemini_image(
                prompt, reference[0] if reference else None,
                (reference[1] if reference else "") or "image/jpeg")
            from_ref = bool(reference and content)
        elif eid == "huggingface":
            content = aiprovider.hf_image(prompt, reference[0] if reference else None)
            from_ref = bool(reference and content)
        elif eid == "cloudflare":
            # image_engine() already refused Cloudflare for a re-shoot, so this
            # is always the text-to-image path.
            content = aiprovider.generate_image(prompt)
            from_ref = False
    except Exception as e:  # noqa: BLE001 — turned into a message the seller can act on
        log.warning("%s image path raised: %s", eid, e)
        content = None

    if not content:
        raise RuntimeError(
            f"{eng['label']} could not {'re-shoot your photo' if reference else 'draw the picture'} "
            f"just now. This is usually that account's allowance being spent — "
            f"try another engine from the list, or again later.")

    # The corner tag is for INVENTED pictures only. A re-shoot starts from the
    # seller's own photograph, so the product already carries its real brand
    # marking and the prompt above now preserves it — stamping a second name
    # into the corner would show the brand twice, once real and once pasted on.
    aicaps.consume(email, "image")

    # Every generated picture goes through the watermark remover BEFORE the
    # brand tag is added — the other order would have the remover looking at
    # the seller's own corner plate. Engines known to return unmarked pictures
    # are checked with stricter limits (see backend/core/watermark.py), so a
    # white stitch near the corner of a re-shoot is never rubbed out.
    from backend.core import watermark
    content, wm_report = watermark.clean_image(content, source=eid)

    if not from_ref:
        content = _stamp_brand(content, brief.get("brand_name") or "")
    saved = media.save(f"{uuid.uuid4().hex}.png", content, email)
    return {"url": saved["url"], "durable": saved["durable"], "generated": True,
            "watermark": wm_report,
            "prompt": prompt, "engine": eng["engine"],
            "engine_label": eng["label"], "model": eng["model"],
            "free": eng["free"],
            "from_reference": from_ref,
            "strength": (aiprovider.STRENGTH_DEFAULT if strength is None else strength)
                        if from_ref else None}


def _stamp_brand(image_bytes: bytes, brand_name: str) -> bytes:
    """A small, legible brand tag in the corner of a generated photo.

    BUG THIS FIXES: image_prompt() tells the model "no text, no logo, no
    watermark" -- deliberately, because asking a diffusion or even GPT-image
    model to render a specific brand's logo is unreliable; it garbles small
    text often enough that banning it was the safer call. The side effect was
    that every AI-generated photo came back completely brandless, which a
    seller notices immediately: their generated posts don't look like their
    feed. This composites the brand's name as a small, tasteful plate
    instead -- legible on every engine, every time, since it never touches
    the model at all.

    Uses matplotlib's bundled DejaVu Sans Bold (matplotlib is already a hard
    dependency for the PDF report) so no extra font asset has to ship; falls
    back to Pillow's built-in font if that path is ever missing. Never lets a
    cosmetic failure break image generation -- worst case, the photo comes
    back unstamped."""
    if not brand_name.strip():
        return image_bytes
    try:
        import io
        from PIL import Image, ImageDraw, ImageFont

        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        w, h = img.size
        size = max(16, min(34, w // 22))

        font = None
        try:
            import matplotlib
            font_path = os.path.join(os.path.dirname(matplotlib.__file__),
                                     "mpl-data", "fonts", "ttf", "DejaVuSans-Bold.ttf")
            if os.path.exists(font_path):
                font = ImageFont.truetype(font_path, size)
        except Exception:  # noqa: BLE001
            font = None
        if font is None:
            font = ImageFont.load_default(size=size)

        text = brand_name.strip().upper()[:40]
        draw = ImageDraw.Draw(img)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        pad_x, pad_y = size * 0.7, size * 0.45
        margin = max(14, w // 40)
        plate_w, plate_h = tw + pad_x * 2, th + pad_y * 2
        x0, y0 = w - margin - plate_w, h - margin - plate_h

        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        odraw.rounded_rectangle([x0, y0, x0 + plate_w, y0 + plate_h],
                                radius=plate_h * 0.22, fill=(15, 15, 15, 150))
        odraw.text((x0 + pad_x - bbox[0], y0 + pad_y - bbox[1]), text,
                   font=font, fill=(255, 255, 255, 235))

        out = Image.alpha_composite(img, overlay).convert("RGB")
        buf = io.BytesIO()
        out.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:  # noqa: BLE001 -- a cosmetic stamp must never break generation
        log.warning("brand stamp failed, returning unstamped image: %s", e)
        return image_bytes


# Engines that can turn a still into a short clip. Only Hugging Face for now,
# by the seller's choice — but the list exists so the picker has the same shape
# as the image one and a second engine is a data change, not a rewrite.
# Both are image-to-video: the clip is animated FROM the seller's own product
# photograph, never invented from text. Order is the default order, and the
# seller can pick either per clip.
VIDEO_ENGINES = [
    {"id": "gemini", "label": "Google Veo (Gemini)",
     "model_env": "GEMINI_VIDEO_MODEL", "model_default": "veo-3.0-fast-generate-preview",
     "free": False, "reshoot": True, "cost_usd": 1.20,
     "cost": "roughly $1.20 for an 8-second clip",
     "note": "The better-looking of the two by a wide margin, and it holds the "
             "product's shape for the whole clip rather than the first two "
             "seconds. Takes one to three minutes. Needs a PAID Gemini key with "
             "Veo access — a free key will be refused, and we will tell you so "
             "plainly rather than charging you to find out."},
    {"id": "huggingface", "label": "Hugging Face (Wan I2V)",
     "model_env": "HF_VIDEO_MODEL", "model_default": "Wan-AI/Wan2.2-I2V-A14B",
     "free": False, "reshoot": True, "cost_usd": 0.20,
     "cost": "about $0.20 for 5 seconds",
     "note": "Six times cheaper, and it shows: identity holds for the first "
             "couple of seconds and then detail drifts, so keep it to a slow "
             "push-in. About a minute per clip."},
]


def video_engines() -> list[dict]:
    """Every clip engine this server can offer. Configured ones only."""
    return [{**_engine_row(s), "cost_usd": s.get("cost_usd")}
            for s in VIDEO_ENGINES if _engine_ready(s["id"])]


def video_engine(preferred: str = "") -> dict:
    """The clip engine that will run, honouring the seller's pick.

    Same contract as image_engine(): a named engine that is not usable is an
    error, never a quiet substitution with a different vendor at a different
    price — a clip costs real money and a $1.20 charge nobody asked for is worse
    than a refusal that explains itself.
    """
    rows = video_engines()
    if preferred:
        hit = next((r for r in rows if r["id"] == preferred), None)
        if not hit:
            known = {e["id"]: e["label"] for e in VIDEO_ENGINES}
            label = known.get(preferred, preferred)
            raise ValueError(
                f"{label} is not connected on this server, so it cannot make a "
                f"clip. Pick another, or add its key."
                if preferred in known else
                f"{preferred} is not a clip engine we know about.")
        return {"engine": hit["id"], "model": hit["model"], "free": False,
                "ready": True, "label": hit["label"],
                "cost_usd": hit.get("cost_usd"), "note": hit["note"]}
    if not rows:
        return {"engine": "", "model": "", "free": False, "ready": False,
                "label": "", "note":
                    "No clip engine is connected on this server, so a video "
                    "cannot be generated here. You can still film one on your "
                    "phone and upload it — which usually looks better anyway."}
    first = rows[0]
    return {"engine": first["id"], "model": first["model"], "free": False,
            "ready": True, "label": first["label"],
            "cost_usd": first.get("cost_usd"), "note": first["note"]}


def generate_video(email: str, product_id: str, prompt: str = "",
                   engine: str = "") -> dict:
    """A short clip made FROM the seller's own product photograph.

    Image-to-video on purpose. Text-to-video would invent a product, and a
    video of a wallet the seller does not sell is worse than no video — the
    same rule that separates Re-shoot from Invent for stills.

    Takes about a minute, so callers keep it off the request path."""
    from backend.core import aiprovider, media, aicaps
    # Clips are 30x the price of an image, so they get their own much tighter
    # ceiling — and the message when it is reached points at Google Flow, which
    # is free, rather than at an upgrade page.
    aicaps.check(email, "video")
    eng = video_engine(engine)          # raises on an unusable named pick
    if not eng["ready"]:
        raise RuntimeError(eng["note"])
    product = next((p for p in products.get_products(email)
                    if p["id"] == product_id), None)
    if not product:
        raise ValueError("That product no longer exists.")
    material = get_material(email, product_id)
    ref = _reference_shot(email, product, material)
    if not ref:
        raise RuntimeError(
            "A clip is made FROM one of your own photographs, and this product "
            "has none yet. Add a photo in Product Studio first.")
    brand = get_brand(email)
    # The brand's look reaches the clip the same way it reaches a still: through
    # the short camera directive, not the 900-word essay. A video model has an
    # even tighter prompt budget than an image one.
    look = (brand.get("aesthetic_directive") or "").strip()
    if not look and brand.get("aesthetic"):
        try:
            look = distil_aesthetic(email, brand)
        except Exception:  # noqa: BLE001
            look = " ".join((brand.get("aesthetic") or "").split())[:300]
    motion = (prompt or "").strip() or (
        "Slow gentle push-in on the product, steady shot, no cuts. " + look[:600]).strip()

    if eng["engine"] == "gemini":
        data = aiprovider.gemini_video(ref[0], motion, ref[1] or "image/jpeg")
        fail = ("Veo would not make that clip. Almost always this is the Gemini "
                "key not having Veo access — it needs a paid key, and free keys "
                "are refused. Hugging Face is cheaper and works on any token.")
    else:
        data = aiprovider.hf_video(ref[0], motion)
        fail = ("Could not generate the clip. This is usually the Hugging Face "
                "credit allowance being spent — check your usage there, or try "
                "Google Veo instead.")
    if not data:
        raise RuntimeError(fail)
    aicaps.consume(email, "video")
    # Same rule as stills: a generated clip is cleaned of any visible corner
    # mark before it is stored against the seller's post.
    from backend.core import watermark
    data, wm_report = watermark.clean_video_bytes(data, "clip.mp4", source=eng["engine"])
    saved = media.save(f"{uuid.uuid4().hex}.mp4", data, email)
    return {"url": saved["url"], "durable": saved["durable"], "generated": True,
            "watermark": wm_report,
            "product_id": product_id, "prompt": motion,
            "engine": eng["engine"], "engine_label": eng.get("label", ""),
            "model": eng["model"],
            "cost_usd": eng.get("cost_usd"), "free": False}


def preview_prompt(email: str, product_id: str, pillar: str = "", fmt: str = "",
                   angle: str = "", use_reference: bool = True,
                   occasion_key: str = "", shot_type: str = "") -> dict:
    """The exact instruction the image model will be sent, without sending it.

    Worth having for its own sake: it is the only way for a seller to find out
    WHY a picture came back wrong. "It ignored my brand" and "it was never told
    about my brand" look identical from the outside, and until this existed the
    seller could only guess which one had happened.

    It also reports where each part came from, so an empty aesthetic reads as
    "you have not uploaded reference images yet" rather than as a mystery.
    """
    brand = get_brand(email)
    product = next((p for p in products.get_products(email) if p["id"] == product_id), None)
    if not product:
        raise ValueError("That product no longer exists.")
    material = get_material(email, product_id)
    brief = build_brief(brand, product, material, angle)
    if brief.get("aesthetic") and not brief.get("aesthetic_directive"):
        try:
            brief = {**brief, "aesthetic_directive": distil_aesthetic(email, brand)}
        except Exception:  # noqa: BLE001
            pass
    ref = _reference_shot(email, product, material) if use_reference else None
    guidance = guidance_for(pillar, fmt, occasion_key, brand.get("look"), shot_type)
    prompt = image_prompt(brief, guidance, has_reference=bool(ref))
    return {
        "prompt": prompt,
        "words": len(prompt.split()),
        "from_reference": bool(ref),
        "sources": [
            {"part": "Your brand's look",
             "have": bool(brief.get("aesthetic_directive") or brief.get("aesthetic")),
             "note": ("Read from the reference images you uploaded to Product Studio."
                      if brief.get("aesthetic") else
                      "Not set yet — upload a few reference images in Product Studio "
                      "and every picture starts looking like your brand.")},
            {"part": "What this product looks like",
             "have": bool(brief.get("seen")),
             "note": ("Read from this product's own photographs."
                      if brief.get("seen") else
                      "Not read yet — add a photo of this product.")},
            {"part": "Your photo as the starting point",
             "have": bool(ref),
             "note": ("The picture is a re-shoot of your own photograph, so it is "
                      "your actual product." if ref else
                      "No usable photo for this product, so the picture will be "
                      "invented rather than re-shot.")},
            {"part": "This kind of shot",
             "have": bool(shot_type and (brief.get("aesthetic_shots") or {}).get(shot_type)),
             "note": (f"Shot like your own {SHOT_TYPES.get(shot_type, {}).get('label', shot_type)} references."
                      if shot_type and (brief.get("aesthetic_shots") or {}).get(shot_type)
                      else "No reference of this particular kind — using a general rule.")},
            {"part": "Festival",
             "have": bool(guidance.get("festival")),
             "note": (f"Styled for {guidance['festival']}." if guidance.get("festival")
                      else "Not a festival post.")},
        ],
    }


def generate_image_only(email: str, product_id: str, pillar: str = "",
                        fmt: str = "", angle: str = "",
                        use_reference: bool = True,
                        strength: float | None = None,
                        occasion_key: str = "", shot_type: str = "",
                        engine: str = "") -> dict:
    """Make a picture and nothing else.

    Separate from make_post because the two are wanted at different moments: a
    seller planning a week wants images for slots that already have captions,
    and writing a second caption over the first one would be actively
    unhelpful.

    `use_reference` defaults to True — the seller's own photo is the starting
    point unless they deliberately ask for an invented image. That default is
    the difference between a catalogue and a fiction.

    `occasion_key` is the festival slug (e.g. "ganesh_chaturthi") from the
    calling post, when there is one — this is what makes a festival post's
    photo actually look like the festival, instead of an ordinary product
    shot with a festival name in the caption next to it."""
    brand = get_brand(email)
    product = next((p for p in products.get_products(email) if p["id"] == product_id), None)
    if not product:
        raise ValueError("That product no longer exists.")
    material = get_material(email, product_id)
    brief = build_brief(brand, product, material, angle)
    ref = _reference_shot(email, product, material) if use_reference else None
    guidance = guidance_for(pillar, fmt, occasion_key, brand.get("look"), shot_type)
    img = generate_image(email, brief, guidance, ref, strength, engine)
    return {**img, "product_id": product_id,
            "product_name": product.get("name"),
            "pillar": pillar, "format": fmt,
            "had_reference": bool(ref),
            "used_aesthetic": bool(brief.get("aesthetic")),
            "used_seen": bool(brief.get("seen")),
            "shot_type": shot_type or "",
            # True when the picture was shot against the seller's OWN reference
            # for this kind of photograph, rather than the brand average.
            "used_shot_reference": bool(shot_type and
                                        (brief.get("aesthetic_shots") or {}).get(shot_type)),
            "festival": guidance.get("festival", "")}


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
            img = generate_image(email, brief, guidance_for(pillar, fmt),
                                 _reference_shot(email, product, material))
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
