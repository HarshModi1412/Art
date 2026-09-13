"""
Social Media Manager — planning, writing and scheduling, for a seller with
twenty minutes a week and no marketing training.

THE FINDING THAT SHAPES EVERYTHING HERE
---------------------------------------
Liadeli, Sotgiu & Verlegh (Journal of Marketing, 2023) pooled 1,641 elasticities
from 86 studies and 95 million observations. The result that matters:

    content type          -> engagement      -> SALES
    emotional / hedonic       +0.266             -0.073
    informational              +0.018            +0.580
    deals / promotional          --              negative

**The content mix that maximises likes is close to the inverse of the mix that
maximises revenue.** A module that optimises for engagement actively misleads a
seller who is trying to make money.

Two consequences run through this file:

  * The default pillar mix is weighted to INFORMATIONAL product content, and
    offers are capped at 5% with the cap explained rather than silently applied.
    Sellers will want to post discounts constantly. The honest thing is to make
    that friction-ful.
  * "What's working" reports reach rate, saves, sends and DMs. Follower count
    and likes are shown small and labelled as not being sales signals — because
    only 21% of sub-10K accounts grew at all last year, and a seller measuring
    themselves on followers will conclude they are failing while selling fine.

OTHER EVIDENCE ENCODED HERE
---------------------------
  * Instagram capped hashtags at 5 (January 2026). Anything that generates 30
    is broken tooling. Keywords in the caption now do what hashtags used to.
  * Captions under 30 words engage best (Socialinsider, 9.1M posts). The first
    125 characters are all that show before "... more".
  * A comment-focused CTA is worth +202% comments and a question +36%
    (Metricool, 24.3M posts) — the single highest-leverage caption element
    measured anywhere.
  * Reels out-reach everything, but only below ~50K followers — which is
    exactly this app's users. Carousels win on saves, 9x over single images.
  * Posting more does NOT cannibalise reach per post; it rises with frequency.
    The binding constraint is the seller's production capacity, which is why
    the Shoot List and atomisation matter more than the scheduler.
  * Indian D2C converts in DMs and on WhatsApp, not at a link-in-bio checkout
    (Meta/YouGov: 66% more likely to buy from a business offering instant
    messaging; 76% prefer local-language advertising). Every CTA ends in a
    conversation.
"""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import date, datetime, timedelta, timezone

from backend.core import aiprovider, localtime, user_store

PLAN_KEY = "social_plan"
POSTS_KEY = "social_posts"
SETTINGS_KEY = "social_settings"


# --------------------------------------------------------------- vocabulary

PILLARS = [
    {"id": "detail", "name": "Product in detail", "type": "informational", "share": 40,
     "why": "Fabric, weight, karat, sizing, notes, care. Dull to write, and the "
            "single strongest driver of sales in the research (+0.580).",
     "prompts": ["What is it made of?", "How does it fit?", "How do you care for it?"]},
    {"id": "new", "name": "New arrival", "type": "informational", "share": 20,
     "why": "New products show a larger effect than existing ones, so a drop "
            "cadence is doing real work, not filling space.",
     "prompts": ["What just landed?", "How many pieces?", "When does it ship?"]},
    {"id": "proof", "name": "Proof", "type": "social", "share": 20,
     "why": "Customer photos, reviews, unboxings, 'we shipped 50 today'. Builds "
            "trust and cannot be copied by a competitor.",
     "prompts": ["Who wore it?", "What did they say?", "How many went out?"]},
    {"id": "founder", "name": "Behind the scenes", "type": "emotional", "share": 15,
     "why": "The studio, the karigar, the packing table. Drives the reach that "
            "carries your product posts — but on its own it does not sell.",
     "prompts": ["Who made it?", "What went wrong today?", "Where do you source?"]},
    {"id": "offer", "name": "Offer", "type": "deals", "share": 5,
     "why": "Capped deliberately. Deals content is NEGATIVELY associated with "
            "sales in the research. Posting discounts feels productive and is "
            "the most common way small sellers train their audience to wait.",
     "prompts": ["What is the offer?", "When does it end?"]},
]
PILLAR_BY_ID = {p["id"]: p for p in PILLARS}
OFFER_CAP_PERCENT = 5

CADENCE = {
    "survival": {"label": "Survival", "posts": 2, "stories": 2,
                 "hours": "under 1 hour a week",
                 "why": "Below this an account shrinks — dormant accounts lose "
                        "0.08% of followers a week."},
    "standard": {"label": "Standard", "posts": 4, "stories": 4,
                 "hours": "about 2 hours a week",
                 "why": "3-5 posts a week roughly doubles growth versus 1-2, and "
                        "reach per post goes UP, not down."},
    "growth":   {"label": "Growth", "posts": 6, "stories": 5,
                 "hours": "about 4 hours a week",
                 "why": "6-9 a week is where growth compounds. Only take this on "
                        "if you can actually shoot enough."},
}

FORMATS = {
    "reel": {"label": "Reel", "why": "Highest reach rate below 50K followers "
                                     "(9.8% at 1-5K). 30-60 seconds is the sweet spot.",
             "target_seconds": 45},
    "carousel": {"label": "Carousel", "why": "9x the saves of a single image. A save "
                                             "on a Rs 4,000 lehenga is purchase intent.",
                 "slides": 5},
    "story": {"label": "Story", "why": "Retention, not reach. Story replies are up "
                                       "88% year on year and a reply is a sales lead."},
    "image": {"label": "Single image", "why": "Reach down 22% and engagement down 46% "
                                              "year on year. Use sparingly.",
              "deprecated": True},
}

LANGUAGES = {
    "hinglish": "Hinglish written in Roman script",
    "english": "English",
    "hindi": "Hindi in Devanagari script",
}

# Verified against panchang-based sources rather than marketing blogs, which
# routinely get these wrong by a week. Lunisolar dates shift every year, so this
# table is DATED and must be refreshed — never extrapolate it forward.
FESTIVALS_2026 = [
    {"key": "ganesh_chaturthi", "date": "2026-09-14", "name": "Ganesh Chaturthi",
     "lead": 10, "span": 10, "categories": ["clothing"],
     "note": "Regionally concentrated — Maharashtra, Goa, Karnataka."},
    {"key": "navratri", "date": "2026-10-11", "name": "Navratri", "lead": 21,
     "span": 9, "categories": ["clothing", "jewellery"],
     "note": "Peak clothing window. Chaniya choli, lehenga, oxidised jewellery."},
    {"key": "dussehra", "date": "2026-10-20", "name": "Dussehra", "lead": 3,
     "span": 0, "categories": ["clothing", "jewellery"]},
    {"key": "karva_chauth", "date": "2026-10-29", "name": "Karva Chauth",
     "lead": 10, "span": 0, "categories": ["clothing", "jewellery", "perfume"],
     "note": "A hard stop — intent dies at moonrise, with no tail at all."},
    {"key": "dhanteras", "date": "2026-11-06", "name": "Dhanteras", "lead": 7,
     "span": 0, "categories": ["jewellery"],
     "note": "The highest-conversion jewellery day of the Indian year."},
    {"key": "diwali", "date": "2026-11-08", "name": "Diwali", "lead": 17,
     "span": 3, "categories": ["clothing", "jewellery", "perfume"],
     "note": "Start pre-campaign around 22 Oct. Ad costs climb from mid-September, "
             "so build the audience in August, not November."},
    {"key": "bhai_dooj", "date": "2026-11-11", "name": "Bhai Dooj", "lead": 5,
     "span": 0, "categories": ["jewellery", "perfume", "clothing"]},
    {"key": "christmas_ny", "date": "2026-12-25", "name": "Christmas", "lead": 14,
     "span": 7, "categories": ["clothing", "perfume"]},
    {"key": "christmas_ny", "date": "2026-12-31", "name": "New Year's Eve",
     "lead": 7, "span": 0, "categories": ["clothing", "perfume"],
     "note": "The one night of the year when Western eveningwear outsells ethnic."},
    {"key": "valentines", "date": "2027-02-14", "name": "Valentine's Day",
     "lead": 14, "span": 0, "categories": ["jewellery", "perfume", "clothing"]},
]

# Festivals in the library that have NO date here are not broken — they are
# lunisolar and their next occurrence falls outside the dates verified for this
# table. The app says so plainly rather than guessing: a festival campaign
# planned against a wrong date is worse than no campaign, because the seller
# only finds out when the day passes.
UNDATED_NOTE = ("This festival's date moves with the lunar calendar and is not "
                "in this year's verified table yet. Its content library is ready "
                "— add the date and the campaign builds itself.")

# Wedding demand runs on a different rhythm from festivals: Chaturmas means no
# auspicious dates Aug-Oct, and January has none either. Together the two
# calendars cover most of the year, leaving January as the only genuinely slack
# month — which is when the module should push evergreen catalogue work.
WEDDING_MONTHS = {2: "high", 3: "high", 4: "medium", 5: "medium", 6: "medium",
                  7: "low", 8: "none", 9: "none", 10: "none",
                  11: "high", 12: "high", 1: "none"}


# --------------------------------------------------------------- settings

def blank_settings() -> dict:
    # Category starts EMPTY, not "clothing". A hardcoded default is a guess
    # about the seller's whole business, and it was wrong for everyone who does
    # not sell clothes — their captions opened by calling their candles an
    # item of clothing. get_settings() fills it from what they told us they
    # sell; if they have told us nothing, it stays empty and the copy simply
    # does not claim a category.
    return {"category": "", "language": "hinglish", "cadence": "standard",
            "pillars": [p["id"] for p in PILLARS], "whatsapp": "",
            "brand_hashtag": "", "handle": "", "city": "",
            "order_cta": "DM us to order",
            # Automatic weekly planning (backend/core/autoplan.py): on by
            # default, every Saturday at 9am India time, planning the week
            # that starts the following Monday. Monday = 0 ... Sunday = 6.
            "auto_plan": True, "auto_plan_day": 5, "auto_plan_hour": 9}


def get_settings(email: str) -> dict:
    s = blank_settings()
    s.update(user_store.get_key((email or "").lower(), SETTINGS_KEY, {}) or {})
    # What the seller said they sell, in their own words, is the best answer to
    # "what category is this shop" — better than a preset and far better than a
    # default. Only used when they have not set a category here explicitly.
    if not str(s.get("category") or "").strip():
        s["category"] = product_label(email)
    return s


def product_label(email: str) -> str:
    """The seller's own words for what they sell, or the preset's label.

    Read straight from the store rather than through smart.py, which imports
    this module — going the other way would be a cycle."""
    from backend.core import product_config
    key = (email or "").lower()
    try:
        label = user_store.get_key(key, "product_type_label", "")
        ptype = user_store.get_key(key, "product_type", None)
    except Exception:  # noqa: BLE001
        return ""
    meta = product_config.meta(ptype, label)
    # "Other products" is the generic preset's label and says nothing useful in
    # a caption, so it is treated as "they have not told us".
    return "" if meta["id"] == "generic" and not meta.get("custom") else meta["label"]


def save_settings(email: str, patch: dict) -> dict:
    s = get_settings(email)
    for k, v in (patch or {}).items():
        if k in s:
            s[k] = v
    if s["cadence"] not in CADENCE:
        s["cadence"] = "standard"
    if s["language"] not in LANGUAGES:
        s["language"] = "hinglish"
    s["auto_plan"] = bool(s.get("auto_plan", True))
    try:
        s["auto_plan_day"] = int(s.get("auto_plan_day", 5)) % 7
    except (TypeError, ValueError):
        s["auto_plan_day"] = 5
    try:
        s["auto_plan_hour"] = max(0, min(23, int(s.get("auto_plan_hour", 9))))
    except (TypeError, ValueError):
        s["auto_plan_hour"] = 9
    user_store.set_key((email or "").lower(), SETTINGS_KEY, s)
    return s


# --------------------------------------------------------------- planning

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------- archetypes
#
# THE PROBLEM THIS FIXES: a planned week used to be N independent slots. Each
# one picked a pillar, wrote a caption and stopped. Nothing connected Monday to
# Thursday, so a seller opened their week and saw the same product photographed
# the same way four times with four interchangeable captions. It read as a
# template, because it was one.
#
# Brands whose feeds look designed rather than accumulated do something else:
# they run ONE theme per week and rotate deliberately different KINDS of
# photograph through it, each doing a different job. Comet (Indian D2C
# sneakers, ~215K followers, built with no celebrity spend) runs a named drop
# per month and moves tease -> half-open packaging -> the one detail you can
# only see up close -> worn on a real person -> sold out. Subko runs named
# recurring buckets and caps itself at three posts a week. The common
# machinery is: a named theme, a fixed arc, and no two adjacent posts of the
# same archetype.
#
# `earns` is what the archetype is FOR. Instagram's own ranking signals for
# reels are watch time, likes per reach and SENDS per reach -- and sends are
# what carries a post to people who do not follow you yet. So "what would make
# someone send this to a friend" is a design input here, not an afterthought.
ARCHETYPES = {
    "tease": {
        "label": "Tease",
        "shot_type": "detail",
        "job": "Withhold the product. Show one cropped, shadowed or partial detail "
               "and ask what it is.",
        "earns": "comments and DMs — this is the post that opens the week",
    },
    "hero": {
        "label": "Cinematic hero",
        "shot_type": "product_only",
        "job": "The product alone, lit and composed properly. No person, no clutter.",
        "earns": "the brand's look — this is the post someone screenshots",
    },
    "unbox": {
        "label": "Half-open packaging",
        "shot_type": "packaging",
        "job": "The box or pouch caught mid-open — tissue, tags, the reveal frozen "
               "halfway.",
        "earns": "saves and sends; the strongest anticipation trigger there is",
    },
    "detail": {
        "label": "The one detail",
        "shot_type": "detail",
        "job": "Macro on the thing that only reads from four inches away — the "
               "stitch, the clasp, the weave, the setting.",
        "earns": "saves, and it is what justifies the price",
    },
    "in_use": {
        "label": "A real person using it",
        "shot_type": "in_use",
        "job": "Worn, carried or used by an actual person in an ordinary place. "
               "Not a model card.",
        "earns": "trust and DMs — the post that converts",
    },
    "process": {
        "label": "Made by hand",
        "shot_type": "held",
        "job": "The making of it — hands, workbench, tools, materials mid-work.",
        "earns": "watch time, the best of any archetype, and trust",
    },
    "styling": {
        "label": "One piece, three ways",
        "shot_type": "lifestyle",
        "job": "The same item styled or used several ways, as a carousel the "
               "viewer can flick through.",
        "earns": "saves — the highest save rate of any archetype",
    },
    "proof": {
        "label": "Someone else already bought it",
        "shot_type": "in_use",
        "job": "A customer's own photo, a review, or a real 'we shipped these "
               "today' moment.",
        "earns": "conversion; it does the convincing you cannot do about yourself",
    },
    "answer": {
        "label": "The question they actually have",
        "shot_type": "detail",
        "job": "Kill one real objection — sizing, care, does it tarnish, is the "
               "leather real.",
        "earns": "saves, and it removes the reason people hesitate",
    },
    "festival": {
        "label": "Festival or occasion",
        "shot_type": "lifestyle",
        "job": "Tie the piece to the occasion people are actually shopping for.",
        "earns": "reach and revenue — but it degrades fast if overused",
    },
}

# The arc. A week is an episode, not a bag of posts: withhold, reveal, prove,
# then place it in someone's life. Each beat references the one before it, so
# the captions read as a sequence rather than a set.
WEEK_ARC = [
    {"beat": "tease",  "archetypes": ["tease"],                       "pillar": "new"},
    {"beat": "reveal", "archetypes": ["hero", "unbox"],               "pillar": "new"},
    {"beat": "prove",  "archetypes": ["detail", "answer", "process"], "pillar": "detail"},
    {"beat": "place",  "archetypes": ["in_use", "styling", "proof"],  "pillar": "proof"},
    {"beat": "close",  "archetypes": ["festival", "proof", "styling"], "pillar": "founder"},
]

# What each beat is trying to do, said to the caption writer in plain words so
# the copy carries the arc too and not just the pictures.
BEAT_JOB = {
    "tease":  "Open the week. Do not name the product outright — make them ask.",
    "reveal": "Show it properly for the first time. This is the announcement.",
    "prove":  "Earn the price. Show the detail or answer the doubt.",
    "place":  "Put it in a real life so they can picture owning it.",
    "close":  "Close the loop the week opened, and give a reason to act now.",
}

# Carousels get roughly nine times the saves of a single image, and reels
# out-reach everything below ~50K followers -- so the format follows the JOB of
# the beat rather than rotating blindly.
FORMAT_FOR_ARCHETYPE = {
    "tease": "reel", "hero": "carousel", "unbox": "reel", "detail": "carousel",
    "in_use": "reel", "process": "reel", "styling": "carousel",
    "proof": "carousel", "answer": "carousel", "festival": "reel",
}


def slate_shape(cadence: str, occasion: dict | None = None,
                rotation: int = 0, shootable: list[str] | None = None) -> list[dict]:
    """Which beat, archetype, pillar and format each slot in the week gets.

    The week is built as an ARC, not a rotation. Slot 1 teases, the middle
    slots reveal and prove, the last places the product in a real life. Within
    a beat the archetype is varied so two weeks in a row do not produce the
    same photographs, and no two adjacent slots ever share an archetype --
    consecutive near-identical posts are the single fastest way to make a
    planned feed look automated.

    `occasion` steers the closing beat onto the festival when one is live,
    which is how the week connects to what people are actually shopping for."""
    n = CADENCE.get(cadence, CADENCE["standard"])["posts"]
    # Which arc beats this cadence can afford. Two posts a week still get a
    # beginning and an end; six get the full arc with the middle expanded.
    if n <= 2:
        plan = ["reveal", "place"]
    elif n == 3:
        plan = ["tease", "reveal", "place"]
    elif n == 4:
        plan = ["tease", "reveal", "prove", "place"]
    else:
        plan = ["tease", "reveal", "prove", "place", "close"]
        while len(plan) < n:                      # expand the middle, never the ends
            plan.insert(3, "prove" if len(plan) % 2 else "place")
    plan = plan[:n]

    by_beat = {b["beat"]: b for b in WEEK_ARC}
    slots, used, seen_counts = [], None, {}
    # Reels carry reach and carousels carry saves, so a week wants both. Left
    # to a blind rotation the arc produced four reels to two carousels, and a
    # lopsided week makes a balanced per-product mix impossible downstream —
    # somebody always ends up reels-only. Counting as we go keeps the week
    # near even, which is also just the better content mix.
    fmt_count = {"reel": 0, "image": 0}

    def bucket(a):
        return "reel" if FORMAT_FOR_ARCHETYPE.get(a) == "reel" else "image"

    for i, beat in enumerate(plan):
        spec = by_beat[beat]
        options = list(spec["archetypes"])
        if occasion and beat == "close" and "festival" in options:
            arch = "festival"                     # a live festival owns the close
        else:
            # Never repeat the previous slot's archetype -- two identical-looking
            # posts back to back is exactly the "everything looks the same"
            # complaint. Among what is left, prefer the format the week is short
            # of, then rotate so repeated beats do not all pick the same thing.
            options = [a for a in options if a != used] or options
            k = seen_counts.get(beat, 0) + rotation
            # Prefer a beat the seller has actually shown they can shoot. Their
            # Product Studio references say which kinds of photograph they
            # produce; asking for an unboxing beat from someone who has never
            # photographed their packaging is a post that will not get made.
            # A stretch is still allowed — it just goes last, and only when
            # nothing they already shoot fits this beat.
            arch = min(options, key=lambda a, k=k: (
                0 if (not shootable or ARCHETYPES[a]["shot_type"] in shootable) else 1,
                (options.index(a) - k) % len(options),
                fmt_count[bucket(a)]))
            seen_counts[beat] = seen_counts.get(beat, 0) + 1
        used = arch
        fmt_count[bucket(arch)] += 1
        a = ARCHETYPES[arch]
        pillar = spec["pillar"]
        # The offer cap survives the rewrite: deals content is negatively
        # associated with sales, so it stays capped by slot count.
        if pillar == "offer" and (i + 1) / n * 100 > OFFER_CAP_PERCENT and n < 20:
            pillar = "detail"
        slots.append({
            "slot": i + 1, "beat": beat, "archetype": arch,
            "archetype_label": a["label"], "job": a["job"], "earns": a["earns"],
            "beat_job": BEAT_JOB.get(beat, ""),
            "shot_type": a["shot_type"], "pillar": pillar,
            "format": FORMAT_FOR_ARCHETYPE.get(arch, "carousel"),
        })
    return slots


def upcoming_festivals(today: date | None = None, category: str = "",
                       horizon_days: int = 90) -> list[dict]:
    today = today or date.today()
    out = []
    for f in FESTIVALS_2026:
        d = date.fromisoformat(f["date"])
        days = (d - today).days
        if not (0 <= days <= horizon_days):
            continue
        if category and f.get("categories") and category not in f["categories"]:
            continue
        start = d - timedelta(days=f.get("lead", 7))
        out.append({**f, "days_away": days, "start_on": start.isoformat(),
                    "start_in_days": (start - today).days,
                    "act_now": (start - today).days <= 0})
    return sorted(out, key=lambda x: x["days_away"])


def radar(email: str, today: date | None = None) -> dict:
    s = get_settings(email)
    # THE SELLER'S DATE, NOT THE SERVER'S. Every scheduled_at in this app is a
    # naive wall-clock time in the seller's own timezone, and Render runs in
    # UTC. `date.today()` here meant that between midnight and 5:30am IST the
    # app believed it was still yesterday: the calendar highlighted the wrong
    # day, festival countdowns were a day out, and a week planned in that
    # window started on the wrong Monday. The publisher reads
    # `localtime.now(email)`, so leaving these on the server clock would also
    # have meant the planner and the publisher disagreeing about what day it is.
    today = today or localtime.today(email)
    fest = upcoming_festivals(today, s.get("category") or "")
    wed = WEDDING_MONTHS.get(today.month, "low")
    lines = []
    for f in fest[:3]:
        if f["act_now"]:
            lines.append(f"{f['name']} is {f['days_away']} days away. "
                         f"You should already be posting for it.")
        else:
            lines.append(f"{f['name']} is {f['days_away']} days away. "
                         f"Start posting on {f['start_on']}.")
    if wed in ("high", "medium") and (s.get("category") in ("clothing", "jewellery")):
        lines.append(f"Wedding demand is {wed} this month — a second, independent "
                     f"driver from the festival calendar.")
    if today.month == 1:
        lines.append("January is the one genuinely slack month: no festivals, no "
                     "wedding dates. Good time to build catalogue and collect reviews.")
    return {"festivals": fest, "wedding_density": wed, "headline": lines,
            "dates_note": "Festival dates are lunisolar and shift every year. "
                          "This table is for 2026 and must be refreshed, not "
                          "extrapolated."}


# --------------------------------------------------------------- writing

def _caption_system(settings: dict) -> str:
    lang = LANGUAGES.get(settings.get("language") or "hinglish")
    return f"""You write Instagram captions for a small Indian D2C seller.

Write in {lang}.

Structure, in this exact order:
1. A hook line of at most 125 characters. Instagram truncates there, so this line
   must carry the product and a reason to care. No greeting, no throat-clearing.
2. Two or three lines of SPECIFIC, factual detail — fabric, weight, karat, notes,
   sizing, care, how many pieces exist. Concrete beats evocative.
3. One question that invites a COMMENT, not a like.
4. One line telling them how to order.

Hard rules:
- The body after the hook must be under 30 words. Short captions engage best.
- Exactly 5 hashtags, no more. Instagram capped them at 5 in January 2026.
- Include the product category as plain words in the hook, because Instagram now
  ranks on caption keywords rather than hashtags.
- No emoji spam. At most two, and only if they aid scanning.
- Never invent a discount, a price, a delivery time or a material that you were
  not given.

Return exactly this, nothing else:
HOOK: <one line>
BODY: <two or three short lines>
QUESTION: <one question>
CTA: <one line>
TAGS: <5 hashtags separated by spaces>"""


def _tags_from(text: str) -> list[str]:
    """Hashtags out of a line a model wrote, however it chose to write them.

    THE BUG THIS FIXES: this used to be `re.findall(r"#[\w]+")`, which only
    matched tags that already had a #. Smaller models — Cloudflare's, the one
    that had actually been writing these captions — routinely answer
    `TAGS: kurta handmade ganeshchaturthi` with no hashes at all, so every
    caption it wrote went out with NO hashtags and nobody noticed, because an
    empty list is not an error.

    So: take the hashed ones when they are there, and otherwise treat the line
    as plain words. `#` is added on the way out either way."""
    line = str(text or "").strip()
    if not line:
        return []
    hashed = re.findall(r"#([\w]+)", line)
    if hashed:
        return hashed
    # No hashes: split on commas and spaces, drop anything that is obviously a
    # sentence rather than a tag.
    words = [w.strip(" .,;:#\"'") for w in re.split(r"[,\s]+", line)]
    return [w for w in words if w and len(w) > 2 and not w.endswith(".")][:8]


def clean_tags(raw: list, limit: int = 5) -> list[str]:
    """Five usable hashtags: no #, no spaces, no duplicates, nothing empty.

    Five because Instagram capped them there in January 2026 — more are
    ignored, and a wall of them reads as spam to a human either way."""
    out, seen = [], set()
    for t in raw or []:
        tag = re.sub(r"[^0-9A-Za-z_]", "", str(t or "").strip().lstrip("#"))
        if not tag or len(tag) < 3:
            continue
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(tag)
        if len(out) >= limit:
            break
    return out


def _parse_caption(text: str) -> dict:
    out = {"hook": "", "body": "", "question": "", "cta": "", "tags": []}
    cur = None
    for raw in (text or "").splitlines():
        line = raw.strip()
        # HASHTAGS: is what half the models write when asked for TAGS.
        m = re.match(r"^(HOOK|BODY|QUESTION|CTA|TAGS|HASHTAGS)\s*:\s*(.*)$", line, re.I)
        if m:
            cur = m.group(1).lower()
            if cur == "hashtags":
                cur = "tags"
            val = m.group(2).strip()
            if cur == "tags":
                out["tags"] = _tags_from(val)
            else:
                out[cur] = val
        elif cur == "body" and line:
            out["body"] = f"{out['body']}\n{line}".strip()
        elif cur == "tags" and line:
            out["tags"] += _tags_from(line)
    # A model that ignored the format entirely may still have scattered
    # hashtags through its answer. Better than nothing.
    if not out["tags"]:
        out["tags"] = re.findall(r"#([\w]+)", text or "")
    out["tags"] = clean_tags(out["tags"])
    return out


HOOK_BY_ARCHETYPE = {
    "tease":    "Something new lands this week.",
    "hero":     "New in: {name}",
    "unbox":    "This is how {name} arrives.",
    "detail":   "Look closer at {name}",
    "in_use":   "{name}, out in the real world",
    "process":  "How {name} gets made",
    "styling":  "{name}, three ways",
    "proof":    "Another {name} went out today",
    "answer":   "The thing everyone asks about {name}",
    "festival": "{name} — ready for the season",
}
BODY_BY_ARCHETYPE = {
    "tease":    "Not showing the whole thing yet. Guess what it is.",
    "hero":     "Handpicked {cat}. Limited pieces.",
    "unbox":    "Wrapped by hand, packed the same day.",
    "detail":   "The part you only notice when you are holding it.",
    "in_use":   "Worn in, carried around, still holding up.",
    "process":  "Made in small batches, by hand, here.",
    "styling":  "One piece, three ways to wear it.",
    "proof":    "Packed and shipped this morning.",
    "answer":   "The honest answer, before you ask.",
    "festival": "Ready in time, if you order this week.",
}
QUESTION_BY_ARCHETYPE = {
    "tease":    "Any guesses?",
    "hero":     "Which colour should we restock first?",
    "unbox":    "Should we keep this packaging?",
    "detail":   "Would you have spotted this?",
    "in_use":   "Where would you carry this?",
    "process":  "Want to see the rest of the process?",
    "styling":  "Which of the three is yours?",
    "proof":    "Tag someone who needs one.",
    "answer":   "What else do you want to know?",
    "festival": "Who are you shopping for?",
}


def _fallback_caption(product: dict, pillar: dict, settings: dict,
                      playbook: dict | None = None,
                      beat: dict | None = None,
                      slot: dict | None = None) -> dict:
    """No AI configured, or every provider down. Still produces something a
    seller can post — a duller caption beats an error message.

    When a festival playbook is in hand the fallback uses it, so a Diwali post
    is recognisably a Diwali post even with no model in the loop: the real
    tagline, the real hashtags, and the right grammar for who is buying.

    BUG THIS FIXES: outside a festival this had exactly TWO possible hooks —
    one for the `new` pillar and one for literally everything else — and the
    body, question and tags never varied at all. A seller with one product
    pressing "Plan my week" with no AI reachable (no key, a rate limit, an
    outage) got four posts of which three were identical. The campaign path
    already rotated its lines by beat; the weekly path never got the same
    treatment. Now the ARCHETYPE picks the line, so each beat of the week
    reads differently even with no model in the loop."""
    # "piece" is jewellery language. For a candle maker it is simply wrong, and
    # this is the path that runs when there is no AI at all — the one a free
    # account sees most.
    cat = settings.get("category") or "product"
    name = product.get("name") or f"this {cat}"
    price = product.get("price")
    cta = settings.get("order_cta") or "DM us to order"

    if playbook:
        fest = playbook["festival"]
        gifting = playbook.get("buys_for") == "gift"
        # Rotate the tagline by beat, so two posts in the same campaign do not
        # open with the identical line. Repeating the hook is the fastest way to
        # make a planned campaign look automated.
        lines = playbook.get("taglines") or [f"{fest} is close."]
        idx = 0
        if beat:
            order = [b["key"] for b in __import__("backend.core.playbook",
                                                  fromlist=["BEATS"]).BEATS]
            idx = order.index(beat["key"]) if beat.get("key") in order else 0
        hook = lines[idx % len(lines)]
        if beat and beat.get("key") == "deadline":
            hook = f"Last day to order and still have it for {fest}."
            body = "Message us today and we will confirm the delivery date " \
                   "before you pay."
        elif beat and beat.get("key") == "day":
            hook = f"{fest} from our workshop."
            body = "Thank you to everyone who ordered. Photos of your pieces " \
                   "arriving have made our week."
            # This beat's whole job is to be present WITHOUT selling. Leaving a
            # sales question and an order CTA on it would defeat the one thing
            # it is for.
            return {"hook": hook[:125], "body": body, "question": "", "cta": "",
                    "tags": playbook.get("hashtags", [])[:5],
                    "generated_by": "template"}
        else:
            body = (f"{name} — ready for {fest}."
                    + (f" Rs {int(float(price))}." if price else ""))
            if playbook.get("buys"):
                body += f" Also in: {', '.join(playbook['buys'][:2])}."
        question = (f"Who are you shopping for this {fest}?" if gifting
                    else f"Which one are you wearing for {fest}?")
        return {"hook": hook[:125], "body": body[:200], "question": question,
                "cta": cta, "tags": playbook.get("hashtags", [])[:5],
                "generated_by": "template"}

    arch = (slot or {}).get("archetype") or ""
    if arch in HOOK_BY_ARCHETYPE:
        hook = HOOK_BY_ARCHETYPE[arch].format(name=name)
        body = BODY_BY_ARCHETYPE[arch].format(name=name, cat=cat)
        question = QUESTION_BY_ARCHETYPE[arch]
        # A tease that names its own price has stopped teasing.
        if price and arch not in ("tease", "process", "proof"):
            hook = f"{hook} · Rs {int(float(price))}"
    else:
        hook = f"New in: {name}" if pillar["id"] == "new" else f"{name} — the details"
        if price:
            hook = f"{hook} · Rs {int(float(price))}"
        body = product.get("description") or f"Handpicked {cat}. Limited pieces."
        question = "Which colour should we restock first?"
    return {"hook": hook[:125], "body": body[:160],
            "question": question,
            "cta": "" if arch == "tease" else cta,
            "tags": [f"#{re.sub(r'[^a-z]', '', cat.lower())}", "#indianfashion",
                     "#smallbusinessindia", "#handmade", "#shoplocal"][:5],
            "generated_by": "template"}


def week_theme(product: dict, occasion: dict | None = None) -> dict:
    """The one thing this week is about.

    Brands whose grids look designed run a NAMED unit -- a drop, a series, a
    chapter -- and every post that week belongs to it. A small seller rarely
    has a launch to hang a week on, so one is manufactured from what they do
    have: the piece the week is built around, and the occasion if one is live.
    The name is repeated in every caption, which is most of what makes seven
    posts read as one story."""
    name = (product.get("name") or "this piece").strip()
    if occasion:
        return {"name": f"{name} for {occasion['name']}",
                "product": name, "occasion": occasion.get("name", ""),
                "note": f"Every post this week is about {name}, building towards "
                        f"{occasion['name']}."}
    return {"name": name, "product": name, "occasion": "",
            "note": f"Every post this week is about {name}, from first look to "
                    f"someone actually using it."}


def _story_context(theme: dict, slot: dict, prev: dict | None = None) -> str:
    """What the writer needs to make this post part of a week, not a one-off.

    Three things do the work: the week's theme (so the same noun recurs), this
    beat's job (so the post has a reason to exist that the others do not), and
    what the PREVIOUS post did (so the opening line can pick the thread up
    instead of starting cold). The third is the one that actually makes a feed
    feel sequenced, and it is the one nothing in this module used to carry."""
    if not theme or not slot:
        return ""
    out = (f"THIS WEEK'S STORY: {theme['note']}\n"
           f"THIS POST'S PLACE IN IT: {slot.get('beat_job', '')} "
           f"Its job is: {slot.get('job', '')}\n"
           f"THE PICTURE: {slot.get('archetype_label', '')} — {slot.get('job', '')}\n")
    if prev:
        out += (f"THE PREVIOUS POST: was the {prev.get('archetype_label', '')} "
                f"({prev.get('job', '')}). Open by picking that thread up in a "
                f"few words — a reader who saw it should feel continued, and a "
                f"reader who did not should still follow.\n")
    else:
        out += ("This is the FIRST post of the week. Do not refer to an earlier "
                "one.\n")
    out += ("Do not restate the theme mechanically in every post; carry it in the "
            "product name and the through-line.\n")
    return out


def _occasion_context(occasion: dict | None = None, playbook: dict | None = None,
                      beat: dict | None = None) -> str:
    """The festival facts, handed to the model as FACTS rather than left for it
    to invent. Shared by captions, reel scripts and (via studio.guidance_for)
    photos, so a post's picture, caption and script all agree on which
    festival they mean and say it the same way -- rather than, say, a caption
    that knows it's for Ganesh Chaturthi and a photo that has no idea."""
    occ = ""
    if playbook:
        # A model asked to "write a Diwali post" produces a diya and the words
        # "festival of lights"; a model told what people actually buy, who
        # they are buying for, and what not to say produces something a
        # seller can post.
        occ += (f"FESTIVAL: {playbook['festival']}. {playbook['core']}\n"
                f"WHO IS BUYING: {playbook['grammar']}\n"
                f"WHAT PEOPLE BUY: {', '.join(playbook['buys'][:6])}\n"
                f"COLOURS AND MOTIFS: {', '.join(playbook['colours'][:5])}; "
                f"{', '.join(playbook['motifs'][:5])}\n"
                f"NEVER: {' '.join(playbook['caution'])}\n")
        if playbook.get("taglines"):
            occ += (f"Lines in this register work well (do not copy them "
                    f"verbatim): {' / '.join(playbook['taglines'][:3])}\n")
    if beat:
        occ += (f"THIS POST'S ONE JOB: {beat['job']} "
                f"It is {beat['days_before']} days before the festival.\n")
    if occasion and not playbook:
        occ = (f"Occasion: {occasion['name']}, {occasion['days_away']} days away. "
               f"Write it as a {occasion['name']} post — mention the occasion "
               f"naturally, and give a reason to buy NOW rather than later. "
               f"Do not invent a discount.\n")
    return occ


# --------------------------------------------------------------- hashtags
#
# WHY HASHTAGS GET THEIR OWN CALL. Asking one small model for a hook, a body, a
# question, a CTA and five hashtags in one strictly-formatted answer is asking
# it to get five things right at once, and the hashtags are the field it drops
# — which is exactly what happened: captions went out with none at all. Asking
# the same model ONE question it can answer in a line is a different task, and
# small free models are good at it.
#
# Five, because Instagram capped them at five in January 2026. They are worth
# roughly +2% reach now — real but small, which is why this never blocks a post
# and never costs a second round trip when the caption already produced them.
HASHTAG_SYSTEM = """You pick Instagram hashtags for a small Indian D2C seller.

Return EXACTLY 5 hashtags on one line, separated by spaces, and nothing else.

Rules:
- Mix them: one or two broad (the category), two mid-size (the style, the
  occasion, the material), one narrow or local (the city, the craft, the niche).
  Five broad tags compete with millions of posts and reach nobody.
- Real tags people search, not invented phrases. No #viral, #trending,
  #followforfollow, #explorepage — those reach bots, not buyers.
- No spaces inside a tag. No punctuation. No emoji.
- Indian and local tags in Roman script.

Answer with the five hashtags only."""


def _derived_tags(product: dict, settings: dict, occasion: dict | None = None) -> list[str]:
    """Hashtags from what we already know, for when the AI gives us nothing.

    Not clever, but never empty and never wrong: these come from the seller's
    own category, city and product, so the worst case is a tag that is merely
    unambitious."""
    # ORDER IS THE WHOLE DESIGN HERE, because only the first five survive.
    # The mix that actually reaches buyers is one broad, one narrow, one
    # timely, one local, one material — not five broad ones competing with a
    # million posts. So: category, product, occasion, city, fabric. A
    # "#clothinglover" filler used to sit second and push the city out of the
    # list entirely, which threw away the only tag with local intent behind it.
    bits = []
    cat = str((settings or {}).get("category") or "").strip()
    if cat:
        bits.append(cat.replace(" ", ""))                      # broad
    name = str((product or {}).get("name") or "").strip()
    if name:
        bits.append(re.sub(r"[^0-9A-Za-z]", "", name)[:24])    # narrow
    if occasion and occasion.get("name"):
        bits.append(re.sub(r"[^0-9A-Za-z]", "", str(occasion["name"]))[:24])   # timely
    city = str((settings or {}).get("city") or "").strip()
    if city:
        bits.append(re.sub(r"[^0-9A-Za-z]", "", city))         # local
    if (product or {}).get("fabric"):
        bits.append(re.sub(r"[^0-9A-Za-z]", "", str(product["fabric"]))[:20])  # material
    # Evergreen, and honest for this market — only reached when the above is thin.
    bits += ["handmade", "shopsmall", "madeinindia", "smallbusiness"]
    return clean_tags(bits)


def write_hashtags(email: str, product: dict, caption: dict | None = None,
                   occasion: dict | None = None) -> list[str]:
    """Five hashtags for this post. Never returns fewer than it can."""
    s = get_settings(email)
    facts = []
    if (product or {}).get("name"):
        facts.append(f"Product: {product['name']}")
    for k in ("category", "fabric", "description"):
        v = (product or {}).get(k)
        if v:
            facts.append(f"{k.title()}: {str(v)[:120]}")
    if s.get("category"):
        facts.append(f"Shop sells: {s['category']}")
    if s.get("city"):
        facts.append(f"City: {s['city']}")
    if occasion and occasion.get("name"):
        facts.append(f"Occasion: {occasion['name']}")
    if caption and caption.get("hook"):
        facts.append(f"The caption's hook: {caption['hook']}")

    tags = []
    try:
        res = aiprovider.generate(HASHTAG_SYSTEM, "\n".join(facts) or "An Indian D2C product.",
                                  sensitivity="public", max_tokens=80, temperature=0.7,
                                  fallback="")
        tags = clean_tags(_tags_from(res.get("text") or ""))
    except Exception:  # noqa: BLE001 — hashtags are never worth failing a post for
        tags = []

    if len(tags) < 5:
        # Top up rather than replace: three good AI tags plus two derived ones
        # beats five derived ones.
        tags = clean_tags(tags + _derived_tags(product, s, occasion))
    return tags


def write_caption(email: str, product: dict, pillar_id: str,
                  angle: str = "", occasion: dict | None = None,
                  playbook: dict | None = None, beat: dict | None = None,
                  story: str = "", slot: dict | None = None) -> dict:
    s = get_settings(email)
    pillar = PILLAR_BY_ID.get(pillar_id) or PILLARS[0]
    facts = {k: product.get(k) for k in
             ("name", "price", "description", "fabric", "sizes", "care", "stock", "category")
             if product.get(k)}
    occ = _occasion_context(occasion, playbook, beat)
    sells = product_label(email) or s.get("category") or ""
    user = (f"Pillar: {pillar['name']} ({pillar['type']}).\n"
            f"{story}"
            f"{occ}"
            f"Angle: {angle or pillar['prompts'][0]}\n"
            # In the seller's own words. Without this the model is told only a
            # product name and invents a category — which is how a candle maker
            # got a caption about an outfit.
            + (f"This shop sells: {sells}. Write as a {sells} seller would.\n" if sells else "")
            + f"Seller city: {s.get('city') or 'India'}\n"
            f"How to order: {s.get('order_cta')}\n"
            f"Product facts (use only these):\n"
            + "\n".join(f"- {k}: {v}" for k, v in facts.items()))

    fb = _fallback_caption(product, pillar, s, playbook, beat, slot)
    res = aiprovider.generate(_caption_system(s), user, sensitivity="public",
                              max_tokens=400, temperature=0.8,
                              fallback="")
    if not res["text"]:
        return {**fb, "provider": "template", "free": True, "error": res.get("error", "")}
    parsed = _parse_caption(res["text"])
    if not parsed["hook"]:
        return {**fb, "provider": "template", "free": True,
                "error": "model did not return the expected shape"}
    # The hashtags are the field models drop. If they did, ask for just those —
    # one short question a small model can answer — rather than shipping a post
    # with none.
    if len(parsed.get("tags") or []) < 5:
        try:
            parsed["tags"] = write_hashtags(email, product, parsed, occasion)
        except Exception:  # noqa: BLE001
            parsed["tags"] = _derived_tags(product, s, occasion)
    return {**parsed, "provider": res["provider"], "free": res["free"], "error": ""}


# --------------------------------------------------------------- reel scripts
#
# A reel is the one format Studio cannot generate an image for -- there is no
# single photograph that IS a 30-second video. Offering "Invent a picture" on
# a reel slot used to hand the seller a still image with nowhere to go. What
# a seller filming on their own phone actually needs instead is a short shot
# list: what to film, in what order, with what text on screen -- something
# they can act on directly with no crew and no edit rig.

# Not every reel is a slow cinematic product film. A week of those looks like
# one long advert, and the sellers who grow post in several registers: a hand
# demo, a making-of, an order being packed, a question answered to camera. The
# style is chosen per post (see _reel_style) so a week has variety by default,
# and it changes the beats AND the pacing of the prompt handed to the video AI.
REEL_STYLES = {
    "hand_demo": {
        "label": "hands-on demo",
        "brief": "One continuous hand demo. Hands do everything — pick it up, open it, turn it, "
                 "put it down. No people's faces, no location change. Calm and plain.",
        "pace": "one take, no cuts, natural hand speed",
    },
    "quick_cuts": {
        "label": "quick cuts",
        "brief": "Six to eight very short shots, each one a different angle or detail, cut fast on "
                 "the beat. Energy comes from the cutting, not from camera moves.",
        "pace": "fast cuts, roughly one second a shot, hard cuts only",
    },
    "making": {
        "label": "how it is made",
        "brief": "The work behind it: hands cutting, stitching, printing, polishing, finishing. "
                 "The product appears finished only in the last shot.",
        "pace": "unhurried, medium and close shots, real working sounds",
    },
    "packing": {
        "label": "packing an order",
        "brief": "An order being packed for a real customer: item folded, wrapped, note added, "
                 "box or pouch closed, label on. Ends with it ready to go.",
        "pace": "steady, top-down and over-the-shoulder shots",
    },
    "styling": {
        "label": "styled two ways",
        "brief": "The same product presented two different ways — two settings, two pairings, two "
                 "occasions — with a clear switch in the middle.",
        "pace": "two halves with one clean transition",
    },
    "before_after": {
        "label": "before and after",
        "brief": "Start with the plain or empty version, end with it in use and looking its best. "
                 "The change is the whole point.",
        "pace": "slow build, hold on the final state",
    },
    "story": {
        "label": "a quiet film",
        "brief": "A short, cinematic piece: light, texture, one slow move, the product at rest. "
                 "Mood over information.",
        "pace": "slow, one or two long takes, shallow depth of field",
    },
    "to_camera": {
        "label": "talking to camera",
        "brief": "The seller answers one real question a customer asks, holding the product. "
                 "Voiceover carries it; the shots just show what is being talked about.",
        "pace": "medium shots, cut only when the point changes",
    },
}
REEL_STYLE_IDS = list(REEL_STYLES)
# What a video AI can actually make in one go today, and what the reel task
# tells the seller to export from Google Flow.
AI_CLIP_SECONDS = 8


def _reel_style(product_name: str = "", pillar: str = "", when: str = "") -> str:
    """Pick a style. Deterministic on the slot, so re-planning the same week
    gives the same answer, and spread so a week is not eight of one kind."""
    key = f"{product_name}|{pillar}|{when}"
    return REEL_STYLE_IDS[int(hashlib.md5(key.encode()).hexdigest(), 16) % len(REEL_STYLE_IDS)]


def _script_system(settings: dict, style: str = "") -> str:
    lang = LANGUAGES.get(settings.get("language") or "hinglish")
    st = REEL_STYLES.get(style) or {}
    style_line = (f"\nTHIS ONE IS: {st['label']}. {st['brief']}\n" if st else "")
    return f"""You write short vertical video scripts for a small Indian D2C seller who films on their own phone -- no crew, no studio lights, no editor.
{style_line}

Write on-screen text and voiceover in {lang}.

A script is 4 to 6 beats. Each beat is ONE camera instruction a seller can actually do alone -- pick the product up, turn it, hold it next to something, walk somewhere. Never call for a second person, a tripod rig, or a shot that needs more than a phone in one hand.

Hard rules:
- Every beat names the ACTION, not the mood: "Turn the wallet over to show the stitching" beats "show the craftsmanship".
- On-screen text is short -- 3 to 6 words a beat, not a caption pasted onto the screen. It is a NOTE FOR THE SELLER to add in the app afterwards, never something burnt into the footage.
- Match the style above. A hand demo is not a mood film; a making-of is not quick cuts. Two reels in a week should not read the same.
- Voiceover is optional. Leave it blank if text-and-music carries the reel better -- most reels under 5K followers do.
- Never invent a discount, a price, a delivery time or a material you were not given.
- The last beat is always the one clear thing to do (DM, link, visit).

Return exactly this, nothing else, one beat per line:
BEAT: <seconds e.g. 0-3> | <camera instruction> | <on-screen text>
BEAT: <seconds> | <camera instruction> | <on-screen text>
VOICEOVER: <optional narration, or leave blank>
CAPTION HINT: <one line the caption for this reel should mention>"""


def _parse_script(text: str) -> dict:
    beats, voiceover, hint = [], "", ""
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^BEAT\s*:\s*(.*)$", line, re.I)
        if m:
            parts = [p.strip() for p in m.group(1).split("|")]
            if len(parts) >= 2:
                beats.append({"sec": parts[0] if len(parts) > 0 else "",
                              "shot": parts[1] if len(parts) > 1 else "",
                              "on_screen_text": parts[2] if len(parts) > 2 else ""})
            continue
        m = re.match(r"^VOICEOVER\s*:\s*(.*)$", line, re.I)
        if m:
            voiceover = m.group(1).strip()
            continue
        m = re.match(r"^CAPTION\s*HINT\s*:\s*(.*)$", line, re.I)
        if m:
            hint = m.group(1).strip()
    return {"beats": beats[:6], "voiceover": voiceover, "caption_hint": hint}


def _fallback_script(product: dict, occasion: dict | None = None) -> dict:
    """No AI configured, or every provider down -- still a filmable script,
    not an error message. Festival-aware when there's an occasion in hand, the
    same way _fallback_caption is."""
    name = product.get("name") or "this piece"
    fest = (occasion or {}).get("name")
    beats = [
        {"sec": "0-2", "shot": f"Hold {name} up straight to camera, good light",
         "on_screen_text": f"{name}" + (f" for {fest}" if fest else "")},
        {"sec": "2-5", "shot": "Turn it slowly to show the material and finish",
         "on_screen_text": "Look closer"},
        {"sec": "5-8", "shot": "Show it in use / worn / carried, an ordinary setting",
         "on_screen_text": f"Ready for {fest}" if fest else "Everyday, made well"},
        {"sec": "8-10", "shot": "Hold it back up to camera to close", "on_screen_text": "DM to order"},
    ]
    return {"beats": beats, "voiceover": "", "caption_hint": "", "generated_by": "template"}


def build_video_prompt(script: dict, product: dict, settings: dict,
                       occasion: dict | None = None, shot_type: str = "",
                       aesthetic: str = "", theme: str = "", style: str = "") -> str:
    """The reel script as ONE block a seller can paste straight into a video AI.

    WHY THIS SHAPE: the shot list is what you use if you are filming it
    yourself, and it stays. But most sellers asking for a reel now hand it to
    Gemini/Veo, Sora or Kling, and those want a single self-contained
    paragraph-and-spec prompt, not a table of beats. Pasting our old output
    produced a confused clip, so the seller concluded the feature was broken.
    This composes the prompt deterministically from the beats we already have,
    which means it also works when no model is reachable.

    The field order follows what video models actually condition on: subject,
    action, camera, lighting and style, then the hard specs (duration, aspect,
    audio, on-screen text) last."""
    name = product.get("name") or "the product"
    cat = product.get("category") or settings.get("category") or "product"
    # The shot list is a 45-second reel the seller films. THIS prompt goes to a
    # video AI, and those make one short clip — Flow/Veo cap out around 8
    # seconds, which is also what the task tells the seller to export. Asking
    # for 45 got a clip that either raced through the shots or ignored most.
    seconds = AI_CLIP_SECONDS
    beats = script.get("beats") or []

    look = aesthetic.strip() or ("clean, natural daylight, uncluttered "
                                 "background, shallow depth of field")
    subject = f"{name} ({cat})"
    if product.get("fabric"):
        subject += f" in {product['fabric']}"
    if product.get("description"):
        subject += f". {str(product['description'])[:180]}"

    st = REEL_STYLES.get(style) or {}
    lines = [
        # No platform named on purpose. Saying "Instagram Reel" to a video model
        # is what produced clips with a phone frame, an app interface and a
        # caption bar drawn into the footage — the seller wanted a video, and
        # got a picture of a post.
        "Create a vertical 9:16 video. Real footage only: no app interface, no "
        "phone frame, no social media layout, no borders, no split screen.",
        "",
        f"SUBJECT: {subject}",
    ]
    if st:
        lines.append(f"STYLE: {st['label']} — {st['brief']}")
    if theme:
        lines.append(f"STORY: {theme}")
    if occasion and occasion.get("name"):
        lines.append(f"OCCASION: {occasion['name']} — the styling and colours "
                     f"should read as {occasion['name']} without any text saying so.")
    if shot_type:
        lines.append(f"TREATMENT: {shot_type.replace('_', ' ')}")

    # Three shots is what fits in eight seconds. The rest stay in the shot list
    # for the seller filming it themselves.
    lines += ["", f"SHOT SEQUENCE (fit all of it into {seconds} seconds):"]
    for i, b in enumerate(beats[:3], 1):
        sec = (b.get("sec") or "").strip()
        shot = (b.get("shot") or "").strip()
        ost = (b.get("on_screen_text") or "").strip()
        seg = f"{i}. " + (f"({sec}) " if sec else "") + shot
        lines.append(seg)          # the on-screen line is the seller's, added later

    vo = (script.get("voiceover") or "").strip()
    pace = st.get("pace") or ("handheld phone, eye level, slow deliberate moves; "
                              "one clean cut between shots")
    lines += [
        "",
        f"CAMERA AND PACE: {pace}. Handheld phone, eye level. No whip pans, no zoom effects.",
        f"LIGHTING AND STYLE: {look}",
        f"DURATION: about {seconds} seconds total.",
        "FRAMING: 9:16 vertical, filling the whole frame edge to edge. The "
        "product stays fully in frame and in focus.",
        f"AUDIO: {'voiceover — ' + vo if vo else 'no voiceover; ambient sound only'}.",
        # The on-screen lines stay in the shot list for the seller to add in the
        # app, where they can move and style them. Asking the model for them got
        # centred white lettering burnt into the picture, which cannot be undone.
        "TEXT: none. No captions, titles, subtitles, watermarks, logos, stickers "
        "or lettering of any kind anywhere in the frame.",
        "",
        "DO NOT: change the product's shape, colour, material or any brand name, "
        "logo or lettering on it; add a person's face unless the shots ask for "
        "one; invent a price, a discount or a delivery promise.",
    ]
    return "\n".join(lines).strip()


def write_reel_script(email: str, product: dict, pillar_id: str,
                      angle: str = "", occasion: dict | None = None,
                      playbook: dict | None = None, beat: dict | None = None,
                      story: str = "", shot_type: str = "",
                      theme: str = "") -> dict:
    """The one thing a seller presses for a reel slot instead of an image
    button. Uses the same festival facts as write_caption (_occasion_context)
    so the reel and its caption are never telling two different stories.

    Returns BOTH the shot list (to film yourself) and `ai_prompt` — a single
    paste-ready block for Gemini/Veo, Sora or Kling. The prompt is composed
    from the beats rather than asked for separately, so the two can never
    describe different videos."""
    s = get_settings(email)
    pillar = PILLAR_BY_ID.get(pillar_id) or PILLARS[0]
    seconds = FORMATS["reel"]["target_seconds"]
    occ = _occasion_context(occasion, playbook, beat)
    facts = {k: product.get(k) for k in
             ("name", "price", "description", "fabric", "sizes", "care", "stock", "category")
             if product.get(k)}
    user = (f"Pillar: {pillar['name']} ({pillar['type']}).\n"
            f"{story}"
            f"{occ}"
            f"Angle: {angle or pillar['prompts'][0]}\n"
            f"Target length: about {seconds} seconds.\n"
            f"Product facts (use only these):\n"
            + "\n".join(f"- {k}: {v}" for k, v in facts.items()))

    # The seller's own visual language, so the pasted prompt produces something
    # in their look rather than generic stock-video gloss.
    aesthetic = ""
    try:
        from backend.core import studio
        brand = studio.get_brand(email)
        shots = brand.get("aesthetic_shots") or {}
        aesthetic = (shots.get(shot_type) or brand.get("aesthetic") or "")[:600]
    except Exception:  # noqa: BLE001 — the prompt is still useful without it
        aesthetic = ""

    # Which register this one is in — a hand demo, a making-of, a quiet film.
    style = _reel_style(product.get("name") or "", pillar_id, angle or shot_type)
    fb = _fallback_script(product, occasion)
    res = aiprovider.generate(_script_system(s, style), user, sensitivity="public",
                              max_tokens=500, temperature=0.8, fallback="")
    parsed = _parse_script(res["text"]) if res["text"] else {}
    if not res["text"] or not parsed.get("beats"):
        out = {**fb, "provider": "template", "free": True,
               "error": res.get("error", "") if not res["text"]
                        else "model did not return the expected shape"}
    else:
        out = {**parsed, "provider": res["provider"], "free": res["free"], "error": ""}
    out["style"] = style
    out["style_label"] = REEL_STYLES[style]["label"]
    out["ai_prompt"] = build_video_prompt(out, product, s, occasion, shot_type,
                                          aesthetic, theme, style)
    return out


def assemble(caption: dict) -> str:
    """The caption as it will actually be posted.

    The # is added HERE, not stored. Tags reach this app from four places — the
    caption model, the dedicated hashtag call, the playbook, and the seller
    typing them — and each has its own idea about whether a tag carries a #.
    Normalising at the one point where they become text is the only way that
    does not eventually publish `#kurta ##silk handmade`."""
    parts = [caption.get("hook", "")]
    if caption.get("body"):
        parts += ["", caption["body"]]
    if caption.get("question"):
        parts += ["", caption["question"]]
    if caption.get("cta"):
        parts += ["", caption["cta"]]
    tags = clean_tags(caption.get("tags") or [])
    if tags:
        parts += ["", " ".join("#" + t for t in tags)]
    return "\n".join(parts).strip()


def caption_check(caption: dict, settings: dict) -> list[dict]:
    """Warnings, not blocks. The seller can post anyway — this just tells them
    what the evidence says they are giving up."""
    out = []
    hook = caption.get("hook") or ""
    if len(hook) > 125:
        out.append({"level": "warn", "text":
                    f"The hook is {len(hook)} characters. Instagram cuts at 125, "
                    f"so the rest is hidden behind '... more'."})
    words = len((caption.get("body") or "").split())
    if words > 30:
        out.append({"level": "info", "text":
                    f"The body is {words} words. Captions under 30 words engage "
                    f"best across 9 million posts studied."})
    if not (caption.get("question") or "").strip():
        out.append({"level": "warn", "text":
                    "No question. A comment-focused prompt is worth about 200% "
                    "more comments — the biggest single lever in a caption."})
    n = len(caption.get("tags") or [])
    if n > 5:
        out.append({"level": "error", "text":
                    f"{n} hashtags. Instagram capped them at 5 in January 2026."})
    elif n == 0:
        out.append({"level": "info", "text":
                    "No hashtags. They are only worth about +2% reach now, so this "
                    "is fine — but make sure your category words are in the hook, "
                    "because that is what search ranks on."})
    return out


# --------------------------------------------------------------- posts

# "approved" — the seller said yes, but the post is still waiting on its media
#   (a reel waiting for its clip, or a photo post whose picture could not be
#   made). It sits on the task list at the top of Home until it has one, and
#   only then becomes "scheduled".
# "cancelled" — turned down from the Approval panel. Not counted towards the
#   week's total, and hidden from the calendar.
STATES = ["draft", "ready", "approved", "scheduled", "published", "failed", "cancelled"]


def _posts(email: str) -> list[dict]:
    rows = user_store.get_key((email or "").lower(), POSTS_KEY, []) or []
    return rows if isinstance(rows, list) else []


def _save_posts(email: str, rows: list[dict]) -> None:
    user_store.set_key((email or "").lower(), POSTS_KEY, rows[-400:])


def occasion_for(day: date, category: str = "") -> dict | None:
    """Is this day inside a festival's run-up?

    Windows overlap — on 25 October a clothing seller is four days from Karva
    Chauth and fourteen from Diwali, and both run-ups are live. The NEAREST
    festival wins, because that is the one the customer is thinking about and
    the one where a late post is wasted.

    Without this rule the answer depended on the order of the table, which made
    a real behaviour depend on an editing accident."""
    best, best_gap = None, 10 ** 6
    for f in FESTIVALS_2026:
        d = date.fromisoformat(f["date"])
        lead = f.get("lead", 7)
        span = f.get("span", 0)
        if category and f.get("categories") and category not in f["categories"]:
            continue
        # The window runs from the campaign start through the festival AND its
        # span. Navratri is nine nights; a post on the fourth of them is still
        # a Navratri post, and that is when people are actually buying.
        if not (d - timedelta(days=lead) <= day <= d + timedelta(days=span)):
            continue
        gap = abs((d - day).days)
        if gap < best_gap:
            best, best_gap = f, gap
    if not best:
        return None
    d = date.fromisoformat(best["date"])
    return {"name": best["name"], "date": best["date"], "key": best.get("key", ""),
            "days_away": (d - day).days, "note": best.get("note", "")}


def assign_products(shape: list[dict], pool: list[dict], hero: dict,
                    occasion: dict | None = None,
                    already: list[dict] | None = None) -> list[dict]:
    """Which product each slot in the week is about.

    BUG THIS FIXES: the arc's opening beats were pinned to the hero and every
    remaining beat fell through to a rotation — and because the format follows
    the archetype, the leftover beats happened to be the reel ones. A seller
    with three products got four well-mixed posts about the first and a single
    reel each for the other two, with no carousel between them. The catalogue
    looked like one product plus two afterthoughts.

    Two things have to hold at once, so both are balanced explicitly rather
    than left to fall out of the ordering:

      * the hero opens the week (tease, reveal) — that is what makes the week
        a story about something rather than a rotation;
      * after that, every slot goes to whichever product is furthest behind,
        preferring one that does not yet have THIS slot's format. So no piece
        ends up reels-only, and no piece ends up carousels-only.

    A single-product catalogue is not a special case to apologise for: the
    hero carries all of it, which is correct, because there is nothing else
    to show.

    `already` is the plan that exists on the calendar. Balancing only within
    one week is not enough: planning four weeks in a row, each starting from
    zero, still let a piece collect four carousels and no reel across the
    month. Counting what is already scheduled makes the balance hold over the
    whole plan, not just each week in isolation."""
    names = [p.get("name") or f"item{i}" for i, p in enumerate(pool)]
    counts = {n: {"total": 0, "reel": 0, "image": 0} for n in names}
    hero_name = hero.get("name") or names[0]

    def bucket(fmt):
        return "reel" if fmt == "reel" else "image"

    for p in (already or []):
        n = p.get("product_name") or ""
        if n in counts:
            counts[n]["total"] += 1
            counts[n][bucket(p.get("format"))] += 1

    # Inside a festival window a product actually tagged for it should be
    # preferred where the balance is otherwise equal — the same rule
    # _pick_product applies, kept rather than dropped.
    tag = (occasion or {}).get("name", "").split()[0].lower() if occasion else ""

    def tagged(p):
        if not tag:
            return False
        hay = " ".join(str(x).lower() for x in (p.get("festival_tags") or []))
        return (tag in hay or tag in str(p.get("category") or "").lower()
                or tag in str(p.get("name") or "").lower())

    out = []
    for slot in shape:
        if len(pool) == 1 or slot["beat"] in ("tease", "reveal"):
            chosen = hero
        else:
            b = bucket(slot["format"])
            chosen = min(
                pool,
                key=lambda p, b=b: (
                    counts[p.get("name") or ""]["total"],      # furthest behind first
                    counts[p.get("name") or ""][b],            # then missing this format
                    0 if tagged(p) else 1,                     # then festival-relevant
                    names.index(p.get("name") or ""),          # then stable order
                ))
        n = chosen.get("name") or hero_name
        counts.setdefault(n, {"total": 0, "reel": 0, "image": 0})
        counts[n]["total"] += 1
        counts[n][bucket(slot["format"])] += 1
        out.append(chosen)
    return out


def _pick_product(pool: list[dict], i: int, occasion: dict | None,
                  slots: int = 4) -> dict:
    """Which product this slot is about.

    Inside a festival window, prefer products actually tagged for it — but
    never let the occasion take over the whole week. A seller with one lehenga
    tagged for Navratri would otherwise get four consecutive posts about that
    one lehenga, which reads as a broken feed rather than a campaign.

    The rule: tagged products get at most half the slots unless there are
    enough of them to fill the week without repeating."""
    if occasion:
        tag = occasion["name"].split()[0].lower()
        tagged = [p for p in pool
                  if tag in " ".join(str(t).lower() for t in (p.get("festival_tags") or []))
                  or tag in str(p.get("category") or "").lower()
                  or tag in str(p.get("name") or "").lower()]
        if tagged:
            if len(tagged) >= slots:
                return tagged[i % len(tagged)]
            # Not enough tagged products to carry the week — alternate, so the
            # occasion is present without becoming the only thing on the feed.
            if i % 2 == 0:
                return tagged[(i // 2) % len(tagged)]
            others = [p for p in pool if p not in tagged] or tagged
            return others[(i // 2) % len(others)]
    return pool[i % len(pool)]


def build_week(email: str, catalogue: list[dict], start: date | None = None,
               replace: bool = True) -> list[dict]:
    """Generate the coming week's slate.

    `replace` clears any post in the same window that the seller has NOT yet
    acted on. Without it, pressing "Plan my week" twice produced two posts at
    the same day and time — the first press's drafts were never cleared, so the
    week doubled every time somebody pressed the button again. Published posts
    and anything already scheduled by hand are left alone, because those are
    decisions the seller made and re-planning is not permission to undo them."""
    s = get_settings(email)
    start = start or localtime.today(email)
    shape = slate_shape(s.get("cadence") or "standard")
    pool = [p for p in catalogue if p.get("name")] or [{"name": "your product"}]
    rows = _posts(email)

    # Best slots from 9.6M posts: Wed and Thu strongest, evenings 6-11pm,
    # Fri/Sat weakest. Local time — no India-specific adjustment needed.
    #
    # Which WEEKDAY each slot wants, strongest first (Python's weekday(): Monday
    # is 0), so: Wed, Thu, Mon, Fri, Tue, Sat.
    #
    # BUG THIS FIXES: these used to be fixed day-offsets from the planning date
    # — [2, 3, 0, 4, 1, 5] — which produced the intended pattern ONLY if the
    # seller happened to press "Plan my week" on a Monday. Plan on a Wednesday
    # and offset 2 put the strongest slot on Friday, one of the two weakest days
    # of the week; the whole table silently rotated by however far the planning
    # day was from Monday. The reach data is about weekdays, so the weekday is
    # what this anchors to now: each slot claims the next occurrence of its
    # weekday on or after the planning date. That is always 0-6 days out, so
    # every post still lands inside the week being planned.
    best_weekdays = [2, 3, 0, 4, 1, 5]
    best_hours = [18, 12, 19, 9, 20, 18]
    window_end = start + timedelta(days=6)

    if replace:
        keep = []
        for p in rows:
            if p.get("state") not in ("draft", "ready"):
                keep.append(p)                       # published, scheduled, skipped
                continue
            when = (p.get("scheduled_at") or "")[:10]
            try:
                on = date.fromisoformat(when) if when else None
            except ValueError:
                on = None
            if on and start <= on <= window_end:
                continue                             # superseded by this replan
            keep.append(p)
        rows = keep

    # The week runs on ONE theme, not N unrelated posts. The theme is the
    # product the arc is about, and every beat refers back to it -- that single
    # repeated noun is most of what makes a feed read as planned rather than
    # accumulated.
    lead_occasion = occasion_for(start + timedelta(days=3), s.get("category") or "")
    # Rotate the archetype choice week to week, so consecutive weeks are not the
    # same six posts with new words. It is derived from the date rather than
    # stored, so re-planning the SAME week is stable while the NEXT week moves
    # on -- and over a month every archetype gets its turn.
    week_no = start.isocalendar()[1]
    # What Product Studio learned from this seller's own reference images: the
    # kinds of photograph they demonstrably shoot. The planner leans on it so a
    # week asks for pictures they can actually produce.
    try:
        from backend.core import studio
        shootable = studio.shootable_shot_types(email)
    except Exception:  # noqa: BLE001 — planning must never depend on Studio
        shootable = []
    shape = slate_shape(s.get("cadence") or "standard", lead_occasion,
                        rotation=week_no, shootable=shootable)
    # A DIFFERENT piece leads each week. The hero owns the opening beats, so
    # pinning it to the same product meant that product collected every tease
    # and every reveal for the whole month while the rest of the catalogue got
    # the leftovers. Rotating it also gives the seller what a drop calendar
    # gives a real brand: this week is about this piece, next week another.
    # Inside a festival window a product actually tagged for it still leads,
    # because that is the one people are shopping for.
    hero = _pick_product(pool, week_no, lead_occasion, len(shape))
    theme = week_theme(hero, lead_occasion)
    # Worked out for the whole week up front, because balancing the product mix
    # and the format mix needs to see every slot at once — decided slot by slot
    # it degenerates into one product taking all the carousels.
    slot_products = assign_products(shape, pool, hero, lead_occasion, already=rows)

    # The slate is an ARC, so it has to run in calendar order: the tease must
    # go out before the reveal, and the reveal before the proof. The weekday
    # table is ranked by REACH, not by date — slot 0 wants Wednesday and slot 2
    # wants Monday — so assigning beats to it directly scattered the story
    # (a week planned on a Monday published its tease two days after its
    # reveal). Take the best N weekdays, then sort them into date order and
    # hand them to the beats in sequence: the same strong slots, in a sequence
    # that reads.
    n_slots = len(shape)
    times = []
    now = localtime.now(email)          # the seller's wall clock, not the server's
    for i in range(n_slots):
        offset = (best_weekdays[i % len(best_weekdays)] - start.weekday()) % 7
        when = datetime.combine(start + timedelta(days=offset),
                                datetime.min.time()).replace(
            hour=best_hours[i % len(best_hours)])
        # Planning at 9pm on a Wednesday should not hand the seller a post that
        # was already due at 6pm. Only the slot whose weekday IS the planning
        # day can fall in the past (every other offset is at least a full day
        # out), so nudging that one to tomorrow keeps it inside the planned week
        # rather than being born overdue.
        if when < now:
            when += timedelta(days=1)
        times.append(when)
    times.sort()

    made = []
    prev = None                      # the beat before this one, for the callback
    for i, slot in enumerate(shape):
        when = times[i]
        when_day = when.date()
        occasion = occasion_for(when_day, s.get("category") or "")
        product = slot_products[i]
        story = _story_context(theme, slot, prev)
        cap = write_caption(email, product, slot["pillar"],
                            angle=slot["job"], occasion=occasion, story=story,
                            slot=slot)
        # A reel gets a shot list instead of an image button -- there's no
        # single photograph that IS the video, so generating one at plan time
        # (like the caption) is what a seller filming later actually needs.
        script = (write_reel_script(email, product, slot["pillar"],
                                    angle=slot["job"], occasion=occasion,
                                    story=story, shot_type=slot["shot_type"],
                                    theme=theme["note"])
                 if slot["format"] == "reel" else None)
        post = {
            "id": secrets.token_hex(6),
            "created_at": _now(),
            "product_id": product.get("id") or "",
            "product_name": product.get("name") or "",
            "pillar": slot["pillar"],
            "pillar_name": PILLAR_BY_ID[slot["pillar"]]["name"],
            "format": slot["format"],
            # Where this post sits in the week's story, and what kind of
            # photograph it is. The editor shows both, and /api/studio/image
            # uses shot_type to shoot it like the seller's own reference for
            # that kind of picture rather than like their brand average.
            "beat": slot["beat"],
            "beat_job": slot["beat_job"],
            "archetype": slot["archetype"],
            "archetype_label": slot["archetype_label"],
            "shot_type": slot["shot_type"],
            "earns": slot["earns"],
            "theme": theme["name"],
            "theme_note": theme["note"],
            "occasion": (occasion or {}).get("name", ""),
            "occasion_days": (occasion or {}).get("days_away"),
            # The festival's slug in playbook.FESTIVALS, e.g. "ganesh_chaturthi"
            # -- lets a generated image pull the same festival's colours and
            # motifs the caption already uses (see studio.guidance_for).
            "occasion_key": (occasion or {}).get("key", ""),
            "caption": cap,
            "text": assemble(cap),
            "checks": caption_check(cap, s),
            "script": script,
            "scheduled_at": when.isoformat(timespec="minutes"),
            "state": "draft",
            "provider": cap.get("provider", "template"),
            # The picture is planned, not made. Generating four images every
            # time a seller presses "Plan my week" would burn the free daily
            # allowance on posts they may skip, so the slot is created empty
            # and filled on demand.
            "image_url": "", "image_generated": False, "image_prompt": "",
            # A reel is filmed or generated elsewhere and uploaded here. The
            # field exists from the moment the slot does, so the editor always
            # has somewhere to put the clip.
            "video_url": "",
            "metrics": {},
        }
        made.append(post)
        rows.append(post)
        prev = slot

    _save_posts(email, rows)
    return made


def plan_ahead(email: str, catalogue: list[dict], weeks: int = 4,
               start: date | None = None) -> list[dict]:
    """Plan several weeks out, so a festival that is a month away already has
    posts on the calendar when the seller flips forward to look."""
    start = start or localtime.today(email)
    made = []
    for w in range(max(1, min(8, weeks))):
        made += build_week(email, catalogue, start + timedelta(days=7 * w),
                           replace=(w == 0))
    return made


def week(email: str) -> list[dict]:
    live = [p for p in _posts(email)
            if p.get("state") in ("draft", "ready", "approved", "scheduled")]
    return sorted(live, key=lambda p: p.get("scheduled_at") or "")


def all_posts(email: str) -> list[dict]:
    """Every post on the account, any week, any state.

    The calendar only ever loads one month, which is right for a calendar and
    wrong for the publisher — a post scheduled for the 1st is due while the
    seller is still looking at the previous month."""
    return list(_posts(email))


def record_publish(email: str, post_id: str, result: dict) -> dict:
    """What Instagram did with this post, written onto the post itself.

    A post that failed must LOOK failed on the calendar. The alternative — the
    one this replaces — is a post that stays "scheduled" forever while the
    seller believes it went out, which is worse than an error because they only
    find out when a customer asks why they have gone quiet."""
    rows = _posts(email)
    for p in rows:
        if p.get("id") != post_id:
            continue
        if result.get("ok"):
            p["state"] = "published"
            p["published_at"] = _now()
            p["permalink"] = result.get("permalink") or ""
            p["media_id"] = result.get("media_id") or ""
            p["publish_error"] = ""
        else:
            # "missed" is not a failure of ours — the time simply passed — but
            # it has to leave the scheduled queue or it is retried forever.
            p["state"] = "failed"
            p["failed_at"] = _now()
            p["publish_error"] = str(result.get("error") or "")[:400]
            p["publish_missed"] = bool(result.get("missed"))
        _save_posts(email, rows)
        _sync_tasks(email, p)
        return p
    return {"error": "not found"}


def set_state(email: str, post_id: str, state: str) -> dict:
    if state not in STATES:
        return {"error": "bad state"}
    rows = _posts(email)
    for p in rows:
        if p.get("id") == post_id:
            p["state"] = state
            p["state_at"] = _now()
            _save_posts(email, rows)
            _sync_tasks(email, p)
            return p
    return {"error": "not found"}


def _sync_tasks(email: str, post: dict) -> None:
    """Keep the task list honest about this post.

    A reel that was approved gets a "make the clip" task at the top of Home.
    The moment the post is scheduled with its media, or cancelled, that task
    has nothing left to ask for — so it is closed here, at the one place every
    state change passes through, rather than trusting each caller to remember."""
    try:
        from backend.core import smart
        st = post.get("state")
        if st == "scheduled" and post_ready(post):
            smart.close_post_tasks(email, post["id"])
        elif st in ("cancelled", "failed"):
            smart.close_post_tasks(email, post["id"], remove=True)
    except Exception:  # noqa: BLE001 — a task list hiccup must never block a post
        pass


def approve_all(email: str) -> dict:
    """The one tap that matters. Everything in draft becomes scheduled."""
    rows = _posts(email)
    n = 0
    for p in rows:
        if p.get("state") == "draft":
            p["state"] = "scheduled"
            p["state_at"] = _now()
            n += 1
    _save_posts(email, rows)
    return {"scheduled": n}


def get_post(email: str, post_id: str) -> dict | None:
    """One post by id, regardless of which week it falls in -- the calendar
    only ever has the current month loaded, so this is what lets the
    Approval panel (or anything else) open a specific post's editor without
    first fetching the whole plan."""
    for p in _posts(email):
        if p.get("id") == post_id:
            return p
    return None


PENDING_WINDOW_DAYS = 7


def pending_insight_cards(email: str) -> list[dict]:
    """Drafts due soon, shaped as Approval-panel cards.

    Window, not the whole plan: "Plan 4 weeks" can leave ~28 drafts sitting,
    and dumping all of them into the panel alongside win-back/reorder/etc.
    would drown everything else out. Same 7-day horizon the Home page teaser
    already uses (/api/social/upcoming), so a seller sees one consistent
    "what's coming up" window everywhere, not two different ones.

    Overdue drafts (scheduled_at already in the past) are included too --
    those are MORE urgent than a fresh one, not less; they just never got a
    decision. Posts further out than the window are not orphaned: they're
    still fully approvable by opening them from the calendar, which is what
    "explain me complete logic" below documents."""
    from datetime import datetime, timedelta
    _now = localtime.now(email)
    horizon = _now + timedelta(days=PENDING_WINDOW_DAYS)
    cards = []
    # Asked once for the whole list rather than per card: it is a server
    # capability, not a per-post one.
    try:
        from backend.core import studio
        can_draw = bool(studio.image_engines())
    except Exception:  # noqa: BLE001
        can_draw = False
    for p in _posts(email):
        if p.get("state") != "draft":
            continue
        when_raw = p.get("scheduled_at") or ""
        try:
            when = datetime.fromisoformat(when_raw)
        except ValueError:
            continue
        # The weekly auto-plan runs on Saturday for the week after, so its
        # Sunday post is eight days out — past the usual window. Everything it
        # planned is shown, because the seller was promised one list to approve.
        if when > horizon and p.get("source") != "autoplan":
            continue
        cap = p.get("caption") or {}
        cards.append({
            "id": f"post_{p['id']}",
            "module": "social",
            "title": p.get("product_name") or "A post is ready",
            "detail": cap.get("hook") or "",
            "product_name": p.get("product_name") or "",
            "occasion": p.get("occasion") or "",
            "scheduled_at": when_raw,
            "hook": cap.get("hook") or "",
            "when_label": when.strftime("%a %d %b, %I:%M %p").replace(" 0", " "),
            "overdue": when < _now,
            # WHAT KIND OF POST THIS IS, said plainly on the card.
            #
            # A photo post and a reel need completely different things from the
            # seller — one we can draw for them, the other they have to film —
            # and the panel showed neither, so both cards said "Approve" and did
            # two different things. A seller who taps Approve expecting a picture
            # and gets a shot list has been surprised by their own tool.
            "format": p.get("format") or "",
            # Auto-planned posts carry why this product, this week — the panel
            # shows it, and they get Approve / Details / Cancel.
            "autoplan": p.get("source") == "autoplan",
            "autoplan_week": p.get("autoplan_week") or "",
            "plan_reason": p.get("plan_reason") or "",
            "signal": p.get("signal") or "",
            "signal_label": p.get("signal_label") or "",
            "reference_photo": p.get("reference_photo") or "",
            **_card_kind(p, can_draw),
        })
    cards.sort(key=lambda c: c["scheduled_at"])
    return _autoplan_summary_cards(email, cards) + cards


def _autoplan_summary_cards(email: str, cards: list[dict]) -> list[dict]:
    """One header card per auto-planned week that still has posts waiting:
    what the planner found, and one tap to approve or cancel the lot."""
    weeks: dict[str, list[dict]] = {}
    for c in cards:
        if c.get("autoplan") and c.get("autoplan_week"):
            weeks.setdefault(c["autoplan_week"], []).append(c)
    if not weeks:
        return []
    try:
        from backend.core import autoplan
    except Exception:  # noqa: BLE001
        return []
    out = []
    for wk, members in sorted(weeks.items()):
        brief = autoplan.latest_brief(email, wk) or {}
        occ = next((o for o in (brief.get("opportunities") or [])
                    if o.get("kind") == "festival"), None)
        out.append({
            "id": f"autoplan_{wk}", "module": "social",
            "title": f"Next week's posts: {len(members)} waiting",
            "detail": brief.get("note") or "",
            "week": wk, "week_label": brief.get("week_label") or wk,
            "post_ids": [m["id"][len("post_"):] for m in members],
            "waiting": len(members),
            "added": brief.get("added", len(members)),
            "existing": brief.get("existing", 0),
            "target": brief.get("target", 0),
            "occasion": (occ or {}).get("name", ""),
            "winners": [w.get("name") for w in (brief.get("winners") or [])][:3],
            "strugglers": [x.get("name") for x in (brief.get("strugglers") or [])][:3],
            "summary": True, "autoplan": True,
            # dress_all() orders a desk's cards by count, largest first, so
            # the week's header leads its own posts.
            "count": 1000 + len(members),
        })
    return out


def _card_kind(post: dict, can_draw: bool) -> dict:
    """What kind of post this is, and — crucially — what we can actually deliver.

    Two separate mistakes this fixes.

    The first: the panel used one button, "Approve → schedule", for both a photo
    post and a reel. Tapping it did two completely different things. A seller
    expecting a picture got a shot list to go and film; a seller who wanted the
    shot list got a picture. Both were surprised by their own tool.

    The second is worse, and only shows up on a deployment with no image AI
    connected: the card promised "we draw it" and then could not. Promising
    something the server cannot do is the exact failure that ends a trial — it is
    not a missing feature, it is a lie the product told. So the promise is
    conditional on the capability, and when there is no engine the card says what
    the seller can do instead, which is upload their own photo. That still gets
    the post out.
    """
    is_reel = (post.get("format") or "") == "reel"
    if is_reel:
        return {"kind": "reel",
                "kind_label": "REEL · you make the clip",
                "cta": "Approve & add the video task",
                "needs_from_you": "Approving puts a task at the top of Home: copy the "
                                  "prompt, make the clip in Google Flow, upload it here, "
                                  "then schedule."}
    if can_draw:
        return {"kind": "photo",
                "kind_label": "PHOTO POST · we draw it",
                "cta": "Approve & make the picture",
                "needs_from_you": "Nothing — the picture is made, cleaned of any "
                                  "watermark and scheduled for you."}
    if post.get("image_url"):
        return {"kind": "photo",
                "kind_label": "PHOTO POST · picture ready",
                "cta": "Approve & schedule",
                "needs_from_you": "Nothing — this one already has its picture."}
    return {"kind": "photo",
            "kind_label": "PHOTO POST · add a photo",
            "cta": "Approve & schedule",
            "needs_from_you": "Add one of your own photos to this post before it goes out. "
                              "No image AI is connected on this server, so we will not "
                              "pretend we can draw one."}


def clear_plan(email: str) -> int:
    """Wipe every planned post and every tracked campaign for this account --
    the full reset button. Returns how many posts were removed.

    Deliberately total: a partial clear ("just the drafts") leaves scheduled
    posts from a plan the seller is trying to walk away from, which is a
    worse outcome than losing a scheduled post that genuinely should have
    gone out -- they can always re-plan the week in one tap."""
    n = len(_posts(email))
    _save_posts(email, [])
    user_store.set_key((email or "").lower(), CAMPAIGN_KEY, [])
    # The open "make the reel" / "add a picture" tasks belonged to those posts.
    try:
        from backend.core import smart
        keep = [t for t in smart.get_tasks(email) if not t.get("post_id") or t.get("done")]
        user_store.set_key((email or "").lower(), "smart_tasks", keep)
    except Exception:  # noqa: BLE001
        pass
    return n


def update_post(email: str, post_id: str, patch: dict) -> dict:
    rows = _posts(email)
    s = get_settings(email)
    for p in rows:
        if p.get("id") == post_id:
            cap = dict(p.get("caption") or {})
            for k in ("hook", "body", "question", "cta"):
                if k in (patch or {}):
                    cap[k] = str(patch[k])[:600]
            if "tags" in (patch or {}):
                cap["tags"] = [t if t.startswith("#") else f"#{t}"
                               for t in (patch["tags"] or [])][:5]
            p["caption"] = cap
            p["text"] = assemble(cap)
            p["checks"] = caption_check(cap, s)
            if "scheduled_at" in (patch or {}):
                p["scheduled_at"] = str(patch["scheduled_at"])[:20]
            if "format" in (patch or {}) and patch["format"] in FORMATS:
                p["format"] = patch["format"]
            if "script" in (patch or {}):
                sc = patch["script"] or {}
                beats = [{"sec": str(b.get("sec", ""))[:20],
                          "shot": str(b.get("shot", ""))[:200],
                          "on_screen_text": str(b.get("on_screen_text", ""))[:120]}
                         for b in (sc.get("beats") or [])
                         if b.get("shot") or b.get("on_screen_text")][:8]
                script = {"beats": beats,
                          "voiceover": str(sc.get("voiceover", ""))[:600],
                          "caption_hint": str(sc.get("caption_hint", ""))[:200]}
                # The paste-into-Gemini block is REBUILT from the edited beats
                # rather than taken from the client. A seller who rewrites a
                # shot and then copies a prompt still describing the old one
                # would rightly call that broken.
                script["ai_prompt"] = build_video_prompt(
                    script,
                    {"name": p.get("product_name") or "",
                     "category": s.get("category") or ""},
                    s,
                    ({"name": p["occasion"], "days_away": p.get("occasion_days") or 0}
                     if p.get("occasion") else None),
                    p.get("shot_type") or "",
                    "", p.get("theme_note") or "",
                    (p.get("script") or {}).get("style") or "")
                script["style"] = (p.get("script") or {}).get("style") or ""
                script["style_label"] = REEL_STYLES.get(script["style"], {}).get("label", "")
                p["script"] = script
            _save_posts(email, rows)
            return p
    return {"error": "not found"}


def attach_image(email: str, post_id: str, url: str, generated: bool = False,
                 prompt: str = "") -> dict:
    """Put a picture on a planned post.

    Used both by Studio generation and by a seller uploading their own shot or
    a clip they made in Flow — the post does not care where the file came
    from, only that it has one."""
    rows = _posts(email)
    for p in rows:
        if p.get("id") == post_id:
            p["image_url"] = str(url or "")
            p["image_generated"] = bool(generated)
            p["image_prompt"] = str(prompt or "")[:2000]
            _save_posts(email, rows)
            return p
    return {"error": "not found"}


def attach_video(email: str, post_id: str, url: str, original_url: str | None = None,
                 watermark: dict | None = None) -> dict:
    """Put the finished clip on a planned post.

    WHY THIS EXISTS: a reel slot could be planned, scripted and given a
    paste-ready prompt for a video AI — and then there was nowhere to put the
    video. The seller filmed it (or generated it), and the post still showed an
    empty picture frame, so the one format the research says out-reaches
    everything below 50K followers was the one format that could never actually
    be finished and scheduled.

    Deliberately a SEPARATE field from image_url rather than reusing it. A reel
    wants a clip; a carousel wants stills; a few posts sensibly carry both (a
    cover frame and the video). Overloading one field would have made "does
    this post have what it needs" unanswerable.

    Passing an empty url removes the clip, which is how a seller undoes a
    wrong upload without deleting the post they have already written."""
    rows = _posts(email)
    for p in rows:
        if p.get("id") == post_id:
            p["video_url"] = str(url or "")
            # The upload as it came in, so "still see a watermark?" re-cleans
            # the original rather than an already re-encoded copy — and the
            # result of the last pass, so the editor can say what happened.
            if not url:
                p.pop("video_original_url", None)
                p.pop("video_watermark", None)
            else:
                if original_url is not None:
                    p["video_original_url"] = str(original_url or "")
                if watermark is not None:
                    p["video_watermark"] = {k: watermark.get(k) for k in
                                            ("checked", "removed", "reason", "regions", "corner")
                                            if k in watermark}
            _save_posts(email, rows)
            return p
    return {"error": "not found"}


def post_ready(post: dict) -> bool:
    """Does this post have the media it needs to actually go out?

    A reel needs a clip. Everything else needs a picture. This is what the
    editor uses to tell a seller why a post is not schedulable yet, instead of
    letting them approve an empty frame and find out on the day."""
    if (post or {}).get("format") == "reel":
        return bool(post.get("video_url"))
    return bool(post.get("image_url") or post.get("video_url"))


def post_guidance(email: str, post_id: str) -> dict:
    """What Studio needs to draw for this slot: which product, which pillar,
    which format."""
    p = next((x for x in _posts(email) if x.get("id") == post_id), None)
    if not p:
        return {"error": "not found"}
    return {"post_id": p["id"], "product_id": p.get("product_id") or "",
            "product_name": p.get("product_name") or "",
            "pillar": p.get("pillar") or "", "format": p.get("format") or "",
            "has_image": bool(p.get("image_url"))}


# --------------------------------------------------------------- campaigns

CAMPAIGN_KEY = "social_campaigns"


def _campaigns(email: str) -> list[dict]:
    rows = user_store.get_key((email or "").lower(), CAMPAIGN_KEY, []) or []
    return rows if isinstance(rows, list) else []


def _save_campaigns(email: str, rows: list[dict]) -> None:
    user_store.set_key((email or "").lower(), CAMPAIGN_KEY, rows[-60:])


def campaign_preview(email: str, festival_key: str,
                     today: date | None = None) -> dict:
    """What the campaign WOULD be, without creating anything.

    Shown before the seller commits, because a campaign is a promise about the
    next three weeks of their time and they should see the shape before
    agreeing to it."""
    from backend.core import playbook
    s = get_settings(email)
    today = today or localtime.today(email)
    # Matched on key, not on name — name matching broke the moment two entries
    # shared a library key (Christmas and New Year's Eve both map to one).
    dated = [x for x in FESTIVALS_2026 if x.get("key") == festival_key
             and date.fromisoformat(x["date"]) >= today]
    f = dated[0] if dated else None
    pb = playbook.brief(festival_key, s.get("category") or "clothing")
    if not pb:
        return {"error": "unknown festival"}
    if not f:
        return {"error": f"{pb['festival']}: {UNDATED_NOTE}",
                "festival": pb["festival"], "undated": True,
                "angles": pb["angles"], "taglines": pb["taglines"],
                "caution": pb["caution"]}

    day = date.fromisoformat(f["date"])
    lead = f.get("lead", 7)
    days_out = (day - today).days
    runway = max(lead, 7)

    beats = []
    for b in playbook.BEATS:
        on = day - timedelta(days=round(runway * b["offset_frac"]))
        beats.append({**b, "date": on.isoformat(),
                      "days_before": (day - on).days,
                      "past": on < today})
    return {
        "festival": pb["festival"], "key": festival_key,
        "date": f["date"], "days_out": days_out,
        "weight": pb["weight"], "core": pb["core"],
        "grammar": pb["grammar"], "buys_for": pb["buys_for"],
        "caution": pb["caution"], "note": pb["note"],
        "angles": pb["angles"], "taglines": pb["taglines"],
        "hashtags": pb["hashtags"], "colours": pb["colours"],
        "beats": beats,
        "objective": (f"Get DMs about {pb['festival']} stock before "
                      f"{day.strftime('%d %b')}."),
        "late": days_out < runway * 0.5,
        "runway": runway,
    }


def start_campaign(email: str, festival_key: str, catalogue: list[dict],
                   today: date | None = None) -> dict:
    """Turn a festival into a sequenced set of posts.

    The properties that make this a campaign rather than a queue, all enforced
    here rather than left to the writer:

      * every beat has ONE job, and no job repeats;
      * the beats are positioned relative to the festival date, not to today;
      * the occasion, the grammar (gifting vs self-purchase) and the cautions
        are carried into every caption in the set;
      * it has a stated objective it can be judged against afterwards.
    """
    from backend.core import playbook
    prev = campaign_preview(email, festival_key, today)
    if prev.get("error"):
        return prev
    today = today or localtime.today(email)
    s = get_settings(email)
    pb = playbook.brief(festival_key, s.get("category") or "clothing", get_settings(email))

    pool = [p for p in catalogue if p.get("name")] or [{"name": "your product"}]
    rows = _posts(email)
    made = []

    # Drop any earlier undecided posts for this same festival, so pressing the
    # button twice re-plans rather than doubling — the same rule as the week.
    rows = [p for p in rows
            if not (p.get("campaign") == festival_key and p.get("state") in ("draft", "ready"))]

    for i, beat in enumerate(prev["beats"]):
        if beat["past"]:
            continue                       # do not schedule a post into the past
        product = pool[i % len(pool)]
        angle = pb["angles"][i % len(pb["angles"])]
        occ = {"name": pb["festival"], "days_away": beat["days_before"]}
        cap = write_caption(email, product, _beat_pillar(beat["key"]),
                            angle=angle, occasion=occ, playbook=pb, beat=beat)
        script = (write_reel_script(email, product, _beat_pillar(beat["key"]),
                                    angle=angle, occasion=occ, playbook=pb, beat=beat,
                                    shot_type=_BEAT_SHOT.get(beat["key"], ""),
                                    theme=f"{pb['festival']} campaign — this post's "
                                          f"job is: {beat['job']}")
                 if beat["format"] == "reel" else None)
        when = datetime.combine(date.fromisoformat(beat["date"]),
                                datetime.min.time()).replace(hour=18)
        post = {
            "id": secrets.token_hex(6), "created_at": _now(),
            "product_id": product.get("id") or "",
            "product_name": product.get("name") or "",
            "pillar": _beat_pillar(beat["key"]),
            "pillar_name": PILLAR_BY_ID[_beat_pillar(beat["key"])]["name"],
            "format": beat["format"],
            "occasion": pb["festival"],
            "occasion_key": festival_key,
            "campaign": festival_key,
            "beat": beat["key"], "beat_label": beat["label"],
            "job": beat["job"], "beat_why": beat["why"],
            # Same shot-type threading as the weekly plan, so a campaign's
            # photos vary too and /api/studio/image can shoot each beat
            # against the seller's own reference for that kind of picture.
            "shot_type": _BEAT_SHOT.get(beat["key"], ""),
            "theme_note": f"{pb['festival']} campaign — {beat['job']}",
            "caption": cap, "text": assemble(cap),
            "checks": caption_check(cap, s),
            "script": script,
            "scheduled_at": when.isoformat(timespec="minutes"),
            "state": "draft", "provider": cap.get("provider", "template"),
            "image_url": "", "image_generated": False, "image_prompt": "",
            # A reel is filmed or generated elsewhere and uploaded here. The
            # field exists from the moment the slot does, so the editor always
            # has somewhere to put the clip.
            "video_url": "",
            "metrics": {},
        }
        made.append(post)
        rows.append(post)

    _save_posts(email, rows)

    camps = [c for c in _campaigns(email) if c.get("key") != festival_key]
    camps.append({
        "key": festival_key, "festival": pb["festival"], "date": prev["date"],
        "started_at": _now(), "objective": prev["objective"],
        "posts": [p["id"] for p in made], "beats": len(made),
        "caution": pb["caution"],
    })
    _save_campaigns(email, camps)
    return {**prev, "posts": made, "created": len(made)}


# Which kind of photograph each campaign beat wants, so a festival campaign
# varies its shots the same way a planned week now does.
_BEAT_SHOT = {"tease": "detail", "reveal": "product_only", "useful": "detail",
              "proof": "in_use", "deadline": "packaging", "day": "held"}

_BEAT_PILLAR = {"tease": "new", "reveal": "new", "useful": "detail",
                "proof": "proof", "deadline": "detail", "day": "founder"}


def _beat_pillar(beat_key: str) -> str:
    return _BEAT_PILLAR.get(beat_key, "detail")


def campaigns(email: str) -> list[dict]:
    """Running campaigns, with how far through each one is."""
    rows = _posts(email)
    out = []
    for c in _campaigns(email):
        mine = [p for p in rows if p.get("campaign") == c.get("key")]
        done = [p for p in mine if p.get("state") == "published"]
        out.append({**c, "total": len(mine), "published": len(done),
                    "waiting": len([p for p in mine if p.get("state") == "draft"])})
    return sorted(out, key=lambda c: c.get("date") or "")


def month(email: str, year: int, mon: int) -> dict:
    """One month, laid out as a calendar.

    Festivals are included whether or not anything is planned for them, because
    the empty ones are the point: a seller flipping to October should SEE that
    Navratri and Diwali are there and that nothing is planned yet."""
    import calendar as _cal
    s = get_settings(email)
    first = date(year, mon, 1)
    last = date(year, mon, _cal.monthrange(year, mon)[1])

    posts = [p for p in _posts(email)
             if p.get("scheduled_at") and p.get("state") != "cancelled"]
    by_day: dict[str, list] = {}
    for p in posts:
        d = (p.get("scheduled_at") or "")[:10]
        if d[:7] == f"{year:04d}-{mon:02d}":
            by_day.setdefault(d, []).append(p)
    for v in by_day.values():
        v.sort(key=lambda p: p.get("scheduled_at") or "")

    fests = []
    for f in FESTIVALS_2026:
        d = date.fromisoformat(f["date"])
        lead = f.get("lead", 7)
        start = d - timedelta(days=lead)
        # Show a festival whose day OR whose run-up touches this month, so the
        # seller sees "start posting on the 22nd" while looking at October.
        end = d + timedelta(days=f.get("span", 0))
        if (first <= d <= last) or (start <= last and end >= first):
            fests.append({**f, "start_on": start.isoformat(),
                          "planned": len([p for p in posts
                                          if p.get("occasion") == f["name"]]),
                          "relevant": (not f.get("categories")
                                       or (s.get("category") or "") in f["categories"])})

    # Which weekday the month starts on, so the grid can be padded. Monday = 0.
    return {
        "year": year, "month": mon,
        "label": first.strftime("%B %Y"),
        "days_in_month": last.day,
        "starts_on": first.weekday(),
        # The highlighted cell. On the server clock this was the wrong square
        # for the first five and a half hours of every Indian seller's day.
        "today": localtime.today(email).isoformat(),
        "days": [{"date": f"{year:04d}-{mon:02d}-{d:02d}",
                  "posts": by_day.get(f"{year:04d}-{mon:02d}-{d:02d}", [])}
                 for d in range(1, last.day + 1)],
        "festivals": fests,
        "counts": {"planned": sum(len(v) for v in by_day.values()),
                   "needs_decision": sum(1 for v in by_day.values()
                                         for p in v if p.get("state") == "draft")},
    }


def upcoming(email: str, days: int = 5) -> list[dict]:
    """The next few days, for the home screen. Undecided posts first, because
    those are the ones that need the seller rather than just informing them."""
    today = localtime.today(email)
    horizon = today + timedelta(days=max(1, days))
    out = []
    for p in _posts(email):
        d = (p.get("scheduled_at") or "")[:10]
        if not d:
            continue
        try:
            on = date.fromisoformat(d)
        except ValueError:
            continue
        if today <= on <= horizon and p.get("state") in ("draft", "ready", "approved", "scheduled"):
            out.append(p)
    out.sort(key=lambda p: (p.get("state") != "draft", p.get("scheduled_at") or ""))
    return out


# --------------------------------------------------------------- shoot list

def shoot_list(email: str, catalogue: list[dict], n: int = 3) -> dict:
    """The highest-value screen in the module.

    Reach per post rises with frequency and does not cannibalise, so the only
    thing limiting a seller is how much material they have. One 20-minute shoot
    of three products atomises into roughly nine assets, which is two to three
    weeks of the recommended cadence."""
    picks = [p for p in catalogue if p.get("name")][:n]
    return {
        "products": [{"id": p.get("id"), "name": p.get("name")} for p in picks],
        "minutes": 20,
        "per_product": ["6-10 stills on a plain backdrop, front / detail / worn",
                        "60 seconds of video, slow pan then a wear test",
                        "One 10-second clip of it being packed"],
        "yields": [
            {"asset": "Reel 1", "from": "video", "angle": "product detail, 30-60s"},
            {"asset": "Reel 2", "from": "same video", "angle": "styling or wear test"},
            {"asset": "Carousel A", "from": "5 stills", "angle": "fabric, sizing, care"},
            {"asset": "Carousel B", "from": "same stills", "angle": "3 ways to style"},
            {"asset": "Story set 1", "from": "behind the scenes", "angle": "colour poll"},
            {"asset": "Story set 2", "from": "packing clip", "angle": "drop countdown"},
            {"asset": "Highlight", "from": "best frames", "angle": "catalogue"},
            {"asset": "Reel 3 (later)", "from": "customer photos", "angle": "proof"},
            {"asset": "Carousel C (later)", "from": "reviews", "angle": "proof"},
        ],
        "note": "Nine assets from one session covers two to three weeks. Batching "
                "is the only way the arithmetic works at this cadence.",
    }


# --------------------------------------------------------------- metrics

def whats_working(email: str) -> dict:
    """Four numbers, and an honest label on the two everyone else features."""
    rows = [p for p in _posts(email) if p.get("state") == "published"]
    agg = {"reach": 0, "saves": 0, "sends": 0, "dms": 0, "likes": 0, "posts": len(rows)}
    for p in rows:
        m = p.get("metrics") or {}
        for k in ("reach", "saves", "sends", "dms", "likes"):
            agg[k] += int(m.get(k) or 0)

    best = None
    if rows:
        best = max(rows, key=lambda p: int((p.get("metrics") or {}).get("saves") or 0))

    return {
        "headline": [
            {"key": "reach_rate", "label": "Reach rate", "value": None,
             "benchmark": "9.8% is typical for Reels on a 1-5K account",
             "matters": True},
            {"key": "saves", "label": "Saves", "value": agg["saves"], "matters": True,
             "why": "A save on a considered purchase is deferred buying intent."},
            {"key": "sends", "label": "Sends", "value": agg["sends"], "matters": True,
             "why": "The heaviest-weighted signal in Instagram's ranking, and "
                    "usually a purchase conversation starting."},
            {"key": "dms", "label": "DMs started", "value": agg["dms"], "matters": True,
             "why": "In India this is where the sale actually happens."},
        ],
        "muted": [
            {"key": "likes", "label": "Likes", "value": agg["likes"],
             "note": "Not a sales signal. Likes correlate with engagement and "
                     "mildly NEGATIVELY with sales."},
            {"key": "followers", "label": "Followers", "value": None,
             "note": "Not a sales signal. Only 21% of accounts under 10,000 "
                     "followers grew at all last year — measuring yourself on "
                     "this will tell you you are failing while you are selling fine."},
        ],
        "best_post": ({"id": best["id"], "product": best.get("product_name"),
                       "pillar": best.get("pillar_name"), "format": best.get("format")}
                      if best else None),
        "posts": agg["posts"],
        "enough_data": agg["posts"] >= 8,
    }


def clone_winner(email: str, post_id: str, catalogue: list[dict]) -> dict:
    """'Make more like this' — reuse the winning pillar and format on the next
    product, rather than asking the seller to work out why it worked."""
    src = next((p for p in _posts(email) if p.get("id") == post_id), None)
    if not src:
        return {"error": "not found"}
    pool = [p for p in catalogue if p.get("id") != src.get("product_id")] or catalogue
    if not pool:
        return {"error": "no products"}
    product = pool[0]
    cap = write_caption(email, product, src.get("pillar") or "detail")
    s = get_settings(email)
    post = {"id": secrets.token_hex(6), "created_at": _now(),
            "product_id": product.get("id") or "", "product_name": product.get("name") or "",
            "pillar": src.get("pillar"), "pillar_name": src.get("pillar_name"),
            "format": src.get("format"), "caption": cap, "text": assemble(cap),
            "checks": caption_check(cap, s),
            "scheduled_at": "", "state": "draft", "cloned_from": post_id,
            "provider": cap.get("provider", "template"), "metrics": {}}
    rows = _posts(email)
    rows.append(post)
    _save_posts(email, rows)
    return post
