"""Brand Management: a seller's brand as a system, not a logo.

Design: docs/designs/brand-management-module.md

The seller picks what they sell, who buys it (an age bracket) and one of a
curated set of directions. Each direction is a complete identity system: how the
name is typeset, the type that sits under it, five colours with fixed roles, a
voice, photography rules, and lines of copy written in that voice. The composer
fills the copy with the seller's own name; the seller can change anything; Apply
copies the result into the Website Builder and Product Studio.

Three rules shape everything here.

1. The wordmark is the NAME SET IN TYPE, in code. H&M, Zara and Gucci are
   wordmarks. Image models misspell text, and a misspelt AI logo is exactly the
   home-grown look this module exists to remove. AI images are only ever asked
   for things with no text in them (see scripts/gen_brand_prompts.py).

2. Generated copy never states a product fact. Not the material, not the
   process ("handmade"), not where it was made, not what is in it, not a return
   or delivery promise. The seller knows those facts; we do not, and a template
   that guesses publishes a false claim under the seller's name. The library
   test scans every line for those words.

3. Copy is written in words spelled the same in US and UK English. The one
   word that differs by market (jewellery / jewelry) is a slot.

Library ids (directions, palettes, categories, ages) are stable forever: saved
kits refer to them. Change the words freely; never rename an id.
"""
from __future__ import annotations

import copy
import datetime as _dt
import hashlib
import os
import re

from backend.core import user_store

KIT_KEY = "brand_kit"
LIBRARY_VERSION = 1

NAME_MAX = 40          # a wordmark longer than this stops reading as a mark
TEXT_CAPS = {"tagline": 90, "statement": 400, "promise": 120, "bio": 150,
             "about": 700, "caption": 220}

# ---------------------------------------------------------------------------
# what they sell, and who buys it
# ---------------------------------------------------------------------------
CATEGORIES = [
    {"id": "jewellery", "label": "Jewellery", "label_us": "Jewelry",
     "thing": "jewellery", "thing_us": "jewelry", "noun": "piece", "nouns": "pieces", "wear": "wear"},
    {"id": "clothing", "label": "Clothing", "label_us": "Clothing",
     "thing": "clothing", "thing_us": "clothing", "noun": "piece", "nouns": "pieces", "wear": "wear"},
    {"id": "fragrance", "label": "Fragrance", "label_us": "Fragrance",
     "thing": "fragrance", "thing_us": "fragrance", "noun": "scent", "nouns": "scents", "wear": "wear"},
    {"id": "home_decor", "label": "Home decor", "label_us": "Home decor",
     "thing": "objects for the home", "thing_us": "objects for the home",
     "noun": "piece", "nouns": "pieces", "wear": "live with"},
]
CATEGORY_IDS = [c["id"] for c in CATEGORIES]
_CAT = {c["id"]: c for c in CATEGORIES}

# What the rest of the app calls the seller's product type -> our category.
# "generic" maps to nothing on purpose: a candle maker and a pickle maker are
# both "generic", and guessing home decor for the second would be wrong.
FROM_PRODUCT_TYPE = {"jewellery": "jewellery", "clothes": "clothing", "perfumes": "fragrance"}

AGES = [
    {"id": "18-24", "label": "18–24", "name": "Gen Z",
     "note": "Your buyers are 18 to 24: keep lines short, speak like them, and show the {noun} before the story."},
    {"id": "25-34", "label": "25–34", "name": "Young professionals",
     "note": "Your buyers are 25 to 34: confident, clear and quick to the point. They compare before they buy."},
    {"id": "35-49", "label": "35–49", "name": "Established",
     "note": "Your buyers are 35 to 49: they value clarity and reassurance. Say what it is and why it is worth it."},
    {"id": "50+", "label": "50+", "name": "Mature buyers",
     "note": "Your buyers are 50 and up: be courteous and complete, and leave out slang and abbreviations."},
    {"id": "all", "label": "Not sure", "name": "All ages", "note": ""},
]
AGE_IDS = [a["id"] for a in AGES]
_AGE = {a["id"]: a for a in AGES}

# Faces a wordmark can be set in. A subset of the Website Builder's catalogue,
# so whatever the seller picks here, the site can show.
WORDMARK_FONTS = ["tenorsans", "marcellus", "bodoni", "italiana", "cormorant", "prata",
                  "librecaslon", "playfair", "gloock", "dmserif", "fraunces", "instrserif",
                  "jost", "intertight", "bricolage", "syne", "anton", "archivo",
                  "spacemono"]

FRAMES = ["none", "circle", "square", "circle-solid", "square-solid"]
COLOUR_ROLES = ["ground", "surface", "ink", "accent", "support"]
TEXT_FIELDS = ["tagline", "statement", "promise", "bio", "about"]
CAPTION_COUNT = 4


def _p(pid, name, ground, surface, ink, accent, support):
    return {"id": pid, "name": name,
            "colours": {"ground": ground, "surface": surface, "ink": ink,
                        "accent": accent, "support": support}}


# ---------------------------------------------------------------------------
# the directions
# ---------------------------------------------------------------------------
# Slots in copy: {name} {thing} {Thing} {noun} {nouns} {wear}. Nothing else.
# "spirit" is shown to the seller as a pointer and NEVER enters copy or prompts.
DIRECTIONS: list[dict] = [
    {
        "id": "quiet_luxury", "name": "Quiet Luxury", "ready": True,
        "essence": "Restraint as the luxury. Few words, exact details, nothing loud.",
        "spirit": ["The Row", "Celine", "Mejuri"],
        "mood": ["Restrained", "Exact", "Calm"],
        "ages": {"18-24": 1, "25-34": 2, "35-49": 3, "50+": 2},
        "why": "Buyers past their trend-chasing years read restraint as confidence; younger buyers read it as something to grow into.",
        "categories": ["jewellery", "clothing", "fragrance", "home_decor"],
        "wordmark": {"font": "tenorsans", "case": "upper", "track": 0.30, "weight": 400},
        "frame": "none",
        "fonts": {"heading": "cormorant", "body": "inter", "accent": "jost"},
        "site": {"heading_weight": 400, "heading_track": 2,
                 "themes": {"jewellery": "jewellery", "*": "luxury"}, "fits": ["luxury", "jewellery", "basic"]},
        "studio": {"look": "clean", "voice": "luxury"},
        "palettes": [
            _p("stone", "Stone", "#F3F0EA", "#E7E2D9", "#1F1D1A", "#6E6253", "#A89D8E"),
            _p("noir", "Noir", "#121212", "#1C1B1A", "#ECE8E1", "#B9A889", "#6F675C"),
            _p("sage", "Sage", "#EEF0EA", "#E0E4DA", "#1E231E", "#56614F", "#A3AC98"),
        ],
        "voice": {
            "traits": ["Calm", "Exact", "Unhurried"],
            "say": ["Short, declarative sentences.", "One idea per line.",
                    "Describe what it is, never how amazing it is."],
            "never": ["Exclamation marks.", "Words like stunning or must-have.",
                      "Discount language in the first line."],
            "use": ["considered", "kept", "quiet", "exact", "everyday"],
            "avoid": ["amazing", "obsessed", "must-have", "trendy", "hurry"],
        },
        "exclaim": 0,
        "imagery": ["Soft daylight from one side, long gentle shadows.",
                    "Plain stone or plaster backgrounds in the ground tone.",
                    "One {noun} per frame, with generous empty space.",
                    "No busy props, no filters."],
        "prompt_style": "minimal still life, soft directional daylight, plaster and pale stone surfaces, muted warm neutral tones, generous negative space, calm and restrained mood",
        "copy": {
            "tagline": ["Quietly, always.", "{Thing}, without the noise.", "Made to be kept.", "Say less. Mean it."],
            "statement": [
                "{name} makes {thing} for people who would rather be noticed slowly. Each {noun} is chosen to outlast the season it arrived in. Nothing extra, nothing loud.",
                "At {name}, restraint is the point. We keep the line small and the details exact, so what you {wear} can speak for itself.",
                "{name} is for the ones who notice what others miss. Few {nouns}, considered closely, meant to stay with you for a long time.",
            ],
            "promise": ["Nothing we would not {wear} ourselves.", "Fewer {nouns}, each one considered."],
            "bio": ["Few {nouns}, considered closely. Made to be kept.", "{name}. Quietly, always."],
            "about": [
                "{name} began with a simple belief: the things you keep longest are rarely the loudest. We make a small line of {thing} and give each {noun} the attention a larger line never could. No trends to chase, no noise to cut through. Just {nouns} you will reach for again and again.",
                "We started {name} to make less, and make it matter. Every {noun} in the line has to earn its place. If something does not feel right, it does not reach you.",
            ],
            "caption": ["New in. Quiet enough for every day.", "The {noun} you reach for without thinking.",
                        "Less, chosen well.", "Back, for those who asked."],
        },
    },
    {
        "id": "heritage_maison", "name": "Heritage Maison", "ready": True,
        "essence": "Grand, assured and ceremonial. Deep tones, a serif with presence.",
        "spirit": ["Gucci", "Tiffany & Co.", "Sabyasachi"],
        "mood": ["Assured", "Rich", "Ceremonial"],
        "ages": {"18-24": 1, "25-34": 2, "35-49": 3, "50+": 3},
        "why": "Established buyers and gift-givers trust rich, classic codes; they read as worthy of an occasion.",
        "categories": ["jewellery", "clothing", "fragrance", "home_decor"],
        "wordmark": {"font": "marcellus", "case": "upper", "track": 0.18, "weight": 400},
        "frame": "square",
        "fonts": {"heading": "playfair", "body": "lora", "accent": "jost"},
        "site": {"heading_weight": 500, "heading_track": 1,
                 "themes": {"jewellery": "jewellery", "*": "luxury"}, "fits": ["luxury", "jewellery"]},
        "studio": {"look": "luxe", "voice": "luxury"},
        "palettes": [
            _p("emerald", "Emerald", "#F6F1E7", "#ECE3D1", "#14261E", "#1F4D3A", "#9C7A45"),
            _p("oxblood", "Oxblood", "#F7F2EC", "#EDE2D6", "#2A1215", "#6B1F2A", "#9C7A45"),
            _p("night", "Night and gilt", "#0F0E0C", "#1A1815", "#EFE6D2", "#C2A25E", "#7A6A48"),
        ],
        "voice": {
            "traits": ["Assured", "Warm", "Ceremonial"],
            "say": ["Speak of moments and occasions.", "Use rich, specific words.",
                    "Write in full, graceful sentences."],
            "never": ["Slang or abbreviations.", "Discount-first headlines.", "Exclamation marks."],
            "use": ["occasion", "ceremony", "gift", "presence", "detail"],
            "avoid": ["cheap", "deal", "hack", "basic", "cute"],
        },
        "exclaim": 0,
        "imagery": ["Warm, low light with soft highlights.",
                    "Deep velvet, dark wood or marble surfaces.",
                    "Symmetrical, centred compositions with a sense of ceremony.",
                    "Rich tones from the palette, never washed out."],
        "prompt_style": "rich still life, warm low-key light with soft golden highlights, deep velvet and dark marble surfaces, emerald and oxblood tones, symmetrical composition, opulent and assured mood",
        "copy": {
            "tagline": ["Made for the moments you keep.", "For occasions, and everything after.",
                        "Presence, in every detail.", "A {noun} worth giving."],
            "statement": [
                "{name} makes {thing} for the moments that become memories. Deep in tone, generous in detail, and made to be noticed for all the right reasons.",
                "At {name}, every {noun} is designed with ceremony in mind. Deep tones, careful symmetry and a sense of occasion you can feel the moment it arrives.",
                "{name} is {thing} with presence. For celebrations, for gifts, and for the days you simply want to feel like an occasion.",
            ],
            "promise": ["Every {noun} feels like an occasion.", "Designed to be given, and to be kept."],
            "bio": ["{name}. For the moments you keep.", "Presence, in every detail. For occasions, and everything after."],
            "about": [
                "{name} was started for the moments people remember: the wedding, the promotion, the gift that says more than words. We design {thing} with deep tones and generous detail, so each {noun} feels like an occasion from the moment it is unwrapped.",
                "At {name}, we believe some things should feel grand. Our {nouns} borrow from the codes of classic houses: rich tones, careful symmetry and a sense of ceremony. They are made to be given, and made to be kept.",
            ],
            "caption": ["Made for the moment. Kept for long after.", "Gift it, or keep it. We will not tell.",
                        "Deep tones for the season ahead.", "Every detail, considered for the occasion."],
        },
    },
    {
        "id": "modern_minimal", "name": "Modern Minimal", "ready": True,
        "essence": "Sharp, current and clean. Black, white and one confident line of type.",
        "spirit": ["Zara", "COS", "Arket"],
        "mood": ["Sharp", "Current", "Clean"],
        "ages": {"18-24": 2, "25-34": 3, "35-49": 3, "50+": 1},
        "why": "City buyers in their twenties and thirties read clean monochrome as current and sure of itself.",
        "categories": ["jewellery", "clothing", "fragrance", "home_decor"],
        "wordmark": {"font": "bodoni", "case": "upper", "track": 0.06, "weight": 500},
        "frame": "none",
        "fonts": {"heading": "bodoni", "body": "inter", "accent": "intertight"},
        "site": {"heading_weight": 500, "heading_track": -1,
                 "themes": {"*": "basic"}, "fits": ["basic", "fashion", "tech"]},
        "studio": {"look": "clean", "voice": "minimal"},
        "palettes": [
            _p("mono", "Mono", "#FFFFFF", "#F2F2F2", "#111111", "#111111", "#8A8A8A"),
            _p("greige", "Greige", "#F4F2EF", "#E8E5E0", "#1A1A1A", "#3F3B36", "#9A948B"),
            _p("ink", "Ink blue", "#F7F7F5", "#ECECE8", "#101418", "#1C2B4A", "#8C96A8"),
        ],
        "voice": {
            "traits": ["Direct", "Precise", "Confident"],
            "say": ["Short headlines, often two or three words.", "Facts over adjectives.",
                    "Full stops for rhythm."],
            "never": ["Exclamation marks.", "Long paragraphs.", "Cute wordplay."],
            "use": ["edit", "sharp", "clean", "now", "essential"],
            "avoid": ["cute", "gorgeous", "bestie", "vibes", "literally"],
        },
        "exclaim": 0,
        "imagery": ["Even studio light, crisp shadows.",
                    "Seamless white or stone backdrop.",
                    "Architectural framing; the {noun} placed with intent.",
                    "Monochrome styling, one accent at most."],
        "prompt_style": "minimal studio still life, crisp even light, seamless white and pale stone backdrop, monochrome palette, sharp architectural shadows, precise composition",
        "copy": {
            "tagline": ["Now, in its simplest form.", "Clean lines. Clear choices.", "{Thing}, edited.",
                        "Everything you need. Nothing you do not."],
            "statement": [
                "{name} edits {thing} down to what matters. Clean lines, sharp proportions, nothing added for the sake of it.",
                "At {name}, every {noun} has to earn its place. The result is a short, sharp line that works with everything.",
                "{name} is {thing} for people who decide quickly and choose well. Current, precise and easy to {wear}.",
            ],
            "promise": ["Only what earns its place.", "Simple to choose. Easy to {wear}."],
            "bio": ["{Thing}, edited. Clean lines, clear choices.", "{name}. Now, in its simplest form."],
            "about": [
                "{name} is built on one rule: if it does not need to be there, it goes. We keep the line short and the shapes sharp, so every {noun} works on its own and with everything else you own.",
                "We started {name} to make choosing simple. A tight edit of {thing}: clear in shape, clean in finish, designed for the way you actually live.",
            ],
            "caption": ["New. Sharp. Ready.", "One {noun}. Endless ways to {wear} it.",
                        "The edit, this week.", "Clean lines for a busy week."],
        },
    },
    {
        "id": "everyday_bright", "name": "Everyday Bright", "ready": True,
        "essence": "Friendly, bright and easy. Bold tones, clear type, a brand for every day.",
        "spirit": ["H&M", "Uniqlo", "Gap"],
        "mood": ["Friendly", "Bright", "Easy"],
        "ages": {"18-24": 3, "25-34": 3, "35-49": 2, "50+": 1},
        "why": "Buyers who shop often respond to clear, cheerful brands that feel easy to choose from.",
        "categories": ["jewellery", "clothing", "fragrance", "home_decor"],
        "wordmark": {"font": "jost", "case": "none", "track": -0.01, "weight": 600},
        "frame": "square-solid",
        "fonts": {"heading": "jost", "body": "figtree", "accent": "figtree"},
        "site": {"heading_weight": 600, "heading_track": -1,
                 "themes": {"fragrance": "beauty", "*": "basic"}, "fits": ["basic", "beauty"]},
        "studio": {"look": "bright", "voice": "warm"},
        "palettes": [
            _p("signal", "Signal red", "#FFFFFF", "#F5F3F0", "#161616", "#C8102E", "#E0A82E"),
            _p("cobalt", "Cobalt", "#FFFFFF", "#F1F4F9", "#121826", "#1F4FD8", "#E8846B"),
            _p("fresh", "Fresh green", "#FBFBF8", "#EFF2EA", "#152018", "#1C6E45", "#D9A82B"),
        ],
        "voice": {
            "traits": ["Friendly", "Upbeat", "Clear"],
            "say": ["Talk like a friend who knows what works.", "Ask simple questions.",
                    "Keep it light and clear."],
            "never": ["Jargon.", "Long, formal sentences.", "Making anyone feel left out."],
            "use": ["easy", "fresh", "every day", "bright", "yours"],
            "avoid": ["exclusive", "elite", "bespoke", "opulent", "rarefied"],
        },
        "exclaim": 1,
        "imagery": ["Clean, bright daylight.",
                    "White backdrops with blocks of bold tone.",
                    "Real, easy styling; the {noun} in use.",
                    "Crisp shadows and cheerful energy."],
        "prompt_style": "bright cheerful still life, clean daylight, saturated primary colour blocks against white, crisp shadows, energetic and friendly mood",
        "copy": {
            "tagline": ["Made for every day.", "Easy to love. Easy to {wear}.", "Your everyday, brighter.",
                        "Good things, every day."],
            "statement": [
                "{name} makes {thing} that fits your real life. Bright, easy and ready for whatever the day brings.",
                "At {name}, we think good {thing} should be easy to find and easy to love. Fresh {nouns}, every season, for every day.",
                "{name} is your everyday {thing} brand. Simple to choose, fun to {wear}, and always in step with the season.",
            ],
            "promise": ["Easy to choose, easy to love.", "Something new, every season."],
            "bio": ["{name}. Bright, easy, yours.", "{name}. Easy to love. Easy to {wear}."],
            "about": [
                "{name} started with a simple idea: everyday {thing} should feel good. We keep things bright, easy and honest, with fresh {nouns} every season and nothing complicated in between.",
                "We are {name}. We make {thing} for real days: the commute, the weekend, the dinner you almost skipped. Bright, easy, and always ready to go.",
            ],
            "caption": ["New this week. Which one is yours?", "Bright days start here.",
                        "Easy pick for the weekend.", "Mix it, match it, make it yours."],
        },
    },
    {
        "id": "playful_pop", "name": "Playful Pop", "ready": True,
        "essence": "Loud, funny and unmistakable. Chunky type, candy tones, a wink in every line.",
        "spirit": ["Glossier", "Lazy Oaf", "Bonkers Corner"],
        "mood": ["Playful", "Bold", "Cheeky"],
        "ages": {"18-24": 3, "25-34": 2, "35-49": 1, "50+": 0},
        "why": "Gen Z buyers reward self-expression and wit; this direction is built to be shared.",
        "categories": ["jewellery", "clothing", "fragrance", "home_decor"],
        "wordmark": {"font": "bricolage", "case": "lower", "track": -0.03, "weight": 800},
        "frame": "circle-solid",
        "fonts": {"heading": "bricolage", "body": "dmsans", "accent": "spacegro"},
        "site": {"heading_weight": 800, "heading_track": -2,
                 "themes": {"fragrance": "beauty", "jewellery": "beauty", "*": "basic"}, "fits": ["beauty", "basic"]},
        "studio": {"look": "bright", "voice": "playful"},
        "palettes": [
            _p("bubblegum", "Bubblegum", "#FFF4F8", "#FFE4EE", "#2B0F2E", "#C2185B", "#F2B705"),
            _p("acid", "Acid", "#121512", "#1D211C", "#F2FBE6", "#C6F432", "#FF7AB6"),
            _p("cobaltpop", "Cobalt pop", "#F3F5FF", "#E2E7FF", "#0F1433", "#3438C8", "#E8762E"),
        ],
        "voice": {
            "traits": ["Cheeky", "Bold", "Warm"],
            "say": ["Write like you text your closest friend.", "Short, punchy lines with a twist.",
                    "One exclamation mark is fine. Two is too many."],
            "never": ["Corporate phrasing.", "Mean jokes.", "Long explanations."],
            "use": ["obsessed", "main character", "bold", "fun", "yours"],
            "avoid": ["timeless", "elegant", "refined", "classic", "understated"],
        },
        "exclaim": 1,
        "imagery": ["Hard, bright flash light.",
                    "Candy-toned backdrops and glossy surfaces.",
                    "Chunky shapes, playful angles, the {noun} front and centre.",
                    "Bold blocks of tone from the palette."],
        "prompt_style": "playful pop still life, hard flash light, glossy candy-toned surfaces, chunky geometric shapes, bold colour blocking, joyful and cheeky mood",
        "copy": {
            "tagline": ["Main character energy.", "Made to be seen.", "Not for the quiet ones.",
                        "More fun, on purpose."],
            "statement": [
                "{name} makes {thing} for people who refuse to blend in. Big shapes, bold tones and zero apologies.",
                "At {name}, boring is the only thing we do not make. Every {noun} is designed to start a conversation.",
                "{name} is {thing} with a wink. Loud when you want it, louder when you need it.",
            ],
            "promise": ["Never boring. That is the deal.", "Made to be noticed, every time."],
            "bio": ["{name}. For people who refuse to blend in.", "{name}. Main character energy, daily."],
            "about": [
                "{name} started because everything looked the same. So we made {thing} that does not. Big shapes, bold tones and a little mischief in every {noun}. If it does not make you smile, it does not make the cut.",
                "We are {name}, and we take fun seriously. Our {nouns} are made for the group chat, the first date and the Tuesday that needed something. Loud, bright and entirely yours.",
            ],
            "caption": ["Okay but this one though.", "Tag the friend who needs this.",
                        "Not subtle. Not sorry.", "Your feed called. It wants this one!"],
        },
    },
    {
        "id": "street_edge", "name": "Street Edge", "ready": True,
        "essence": "Raw, loud and sure of itself. Condensed caps, black and one acid accent.",
        "spirit": ["Supreme", "Off-White", "Bonkers Corner"],
        "mood": ["Raw", "Urban", "Defiant"],
        "ages": {"18-24": 3, "25-34": 2, "35-49": 1, "50+": 0},
        "why": "Younger city buyers read condensed caps and hard contrast as street credibility.",
        "categories": ["jewellery", "clothing"],
        "wordmark": {"font": "anton", "case": "upper", "track": 0.02, "weight": 400},
        "frame": "square-solid",
        "fonts": {"heading": "anton", "body": "intertight", "accent": "archivo"},
        "site": {"heading_weight": 400, "heading_track": 0,
                 "themes": {"*": "fashion"}, "fits": ["fashion", "fitness"]},
        "studio": {"look": "editorial", "voice": "minimal"},
        "palettes": [
            _p("blackout", "Blackout", "#0E0E0E", "#1A1A1A", "#F2F2F2", "#D7FF3A", "#FF5A4F"),
            _p("concrete", "Concrete", "#E9E9E6", "#DCDCD8", "#111111", "#C21A12", "#4A4A4A"),
            _p("hazard", "Hazard", "#111111", "#1E1E1E", "#F5F5F0", "#FF6A13", "#8C8C8C"),
        ],
        "voice": {
            "traits": ["Direct", "Confident", "Raw"],
            "say": ["Short lines. Capitals for impact, sparingly.", "Speak like the culture, not about it.",
                    "Let the {noun} be the hero."],
            "never": ["Soft or polite filler.", "Corporate words like solutions or offerings.",
                      "Explaining the joke."],
            "use": ["drop", "out now", "raw", "loud", "move"],
            "avoid": ["elegant", "delicate", "timeless", "gentle", "sweet"],
        },
        "exclaim": 0,
        "imagery": ["Hard flash, deep shadows.",
                    "Concrete, steel and asphalt textures.",
                    "Black with a single acid accent from the palette.",
                    "Low angles and tight crops."],
        "prompt_style": "gritty urban still life, hard flash, concrete and brushed steel surfaces, near-black tones with a single acid accent, high contrast, raw and defiant mood",
        "copy": {
            "tagline": ["Built for the street.", "No rules. Just this.", "Stay loud.", "Drop. {Wear}. Repeat."],
            "statement": [
                "{name} is {thing} for the street, the late nights and everything in between. No rules, no apologies, no second takes.",
                "At {name}, we make {nouns} with attitude. Hard lines, loud tones and nothing that asks for permission.",
                "{name} is raw, direct {thing} for people who set the pace instead of following it.",
            ],
            "promise": ["No filler. Ever.", "Made for people who set the pace."],
            "bio": ["{Thing} with attitude. No rules, no apologies.", "{name}. Stay loud."],
            "about": [
                "{name} is for people who would rather lead than follow. We make {thing} with hard lines and loud tones, in drops that do not wait around.",
                "No backstory, no sales pitch. {name} makes {nouns} that speak first. If you know, you know.",
            ],
            "caption": ["Out now. Move fast.", "This drop does not wait.", "Built for the street.",
                        "If you know, you know."],
        },
    },
    {
        "id": "soft_romantic", "name": "Soft Romantic", "ready": True,
        "essence": "Soft, graceful and personal. Blush tones, fine serifs, a gentle voice.",
        "spirit": ["Chloé", "Mejuri", "Palmonas"],
        "mood": ["Soft", "Graceful", "Tender"],
        "ages": {"18-24": 2, "25-34": 3, "35-49": 2, "50+": 1},
        "why": "Gift buyers and buyers in their twenties and thirties respond to soft, personal warmth.",
        "categories": ["jewellery", "clothing", "fragrance", "home_decor"],
        "wordmark": {"font": "italiana", "case": "upper", "track": 0.16, "weight": 400},
        "frame": "circle",
        "fonts": {"heading": "cormorant", "body": "dmsans", "accent": "jost"},
        "site": {"heading_weight": 500, "heading_track": 1,
                 "themes": {"jewellery": "jewellery", "*": "beauty"}, "fits": ["beauty", "jewellery"]},
        "studio": {"look": "warm", "voice": "warm"},
        "palettes": [
            _p("blush", "Blush", "#FBF3F0", "#F3E3DD", "#3A2328", "#9A4A5B", "#D2B2A2"),
            _p("pearl", "Pearl", "#F8F6F2", "#EEE9E1", "#2F2A33", "#7E6281", "#CFC2D6"),
            _p("rosewood", "Rosewood", "#F6EEEA", "#EBDCD5", "#3B1F22", "#8E3B46", "#C9A27E"),
        ],
        "voice": {
            "traits": ["Gentle", "Warm", "Personal"],
            "say": ["Speak to one person, warmly.", "Use soft, sensory words.",
                    "Keep sentences light and flowing."],
            "never": ["Harsh or shouty words.", "All capitals.", "Pressure to buy."],
            "use": ["soft", "gentle", "yours", "moment", "close"],
            "avoid": ["savage", "beast", "hustle", "insane", "crazy"],
        },
        "exclaim": 0,
        "imagery": ["Diffused window light, no hard shadows.",
                    "Blush and ivory fabrics, soft folds.",
                    "Close, intimate framing of the {noun}.",
                    "A dreamy, tender mood."],
        "prompt_style": "soft romantic still life, diffused window light, blush and ivory draped fabric, petals and pearl tones, delicate shadows, dreamy and tender mood",
        "copy": {
            "tagline": ["For the soft moments.", "Gentle, and entirely you.", "Made to feel like you.",
                        "A little tenderness, every day."],
            "statement": [
                "{name} makes {thing} for the softer side of you. Delicate shapes, warm tones and the kind of detail you notice up close.",
                "At {name}, every {noun} is meant to feel personal. Gentle, graceful and made for the moments you hold onto.",
                "{name} is {thing} with a tender touch. Soft enough for every day, special enough to remember.",
            ],
            "promise": ["Every {noun} feels personal.", "Soft enough for every day."],
            "bio": ["{name}. For the soft moments. Gentle, graceful, yours.", "{name}. Made to feel like you."],
            "about": [
                "{name} began with a feeling more than a plan: that the things we love most are the ones that feel personal. Our {nouns} are soft in shape and warm in tone, made for the quiet, happy moments that make up a life.",
                "We are {name}. We design {thing} the way you would write a note to someone you love: gently, carefully, and with a little more feeling than necessary.",
            ],
            "caption": ["For the soft days.", "A little something, just for you.",
                        "Made for the moments you keep close.", "Gentle tones for the week ahead."],
        },
    },
    {
        "id": "artisan_earth", "name": "Artisan Earth", "ready": True,
        "essence": "Warm, grounded and tactile. Earth tones, a characterful serif, a slower pace.",
        "spirit": ["Anthropologie", "Jaypore", "Toast"],
        "mood": ["Warm", "Grounded", "Tactile"],
        "ages": {"18-24": 1, "25-34": 2, "35-49": 3, "50+": 2},
        "why": "Buyers who prefer slower, considered shopping respond to warm, earthy codes.",
        "categories": ["jewellery", "clothing", "fragrance", "home_decor"],
        "wordmark": {"font": "fraunces", "case": "none", "track": -0.01, "weight": 600},
        "frame": "circle",
        "fonts": {"heading": "fraunces", "body": "worksans", "accent": "jost"},
        "site": {"heading_weight": 600, "heading_track": -1,
                 "themes": {"*": "luxury"}, "fits": ["luxury", "basic"]},
        "studio": {"look": "warm", "voice": "warm"},
        "palettes": [
            _p("olive", "Olive and clay", "#F2EEE4", "#E6DFD0", "#2A2620", "#5E5D33", "#B5653F"),
            _p("indigo", "Indigo earth", "#F1EFEA", "#E3DFD6", "#1D2230", "#2F4A7A", "#B07A3E"),
            _p("walnut", "Walnut", "#EFE9E0", "#E2D8C9", "#2B2119", "#6E4527", "#A9A27A"),
        ],
        "voice": {
            "traits": ["Warm", "Grounded", "Honest"],
            "say": ["Describe texture, tone and feeling.", "Write like a letter, not an ad.",
                    "Keep a calm, unhurried pace."],
            "never": ["Claims about how it is made unless they are true for you.", "Hype or urgency.",
                      "Trend words."],
            "use": ["warm", "texture", "grounded", "character", "time"],
            "avoid": ["trendy", "hype", "viral", "flash sale", "cheap"],
        },
        "exclaim": 0,
        "imagery": ["Low, golden afternoon light.",
                    "Raw fabric, clay and wood surfaces.",
                    "Tactile close-ups that invite touch.",
                    "Olive, ochre and earth tones."],
        "prompt_style": "warm earthy still life, low golden afternoon light, raw linen, unglazed clay and wood surfaces, olive and ochre tones, tactile textures, calm and grounded mood",
        "copy": {
            "tagline": ["Warmth you can feel.", "Grounded, like you.", "For a slower kind of life.",
                        "Texture, warmth, time."],
            "statement": [
                "{name} makes {thing} with warmth you can feel. Earthy tones, honest shapes and textures that invite a second look.",
                "At {name}, we care about the slow things: texture, tone and the quiet pleasure of a {noun} that feels like yours from the first day.",
                "{name} is {thing} for a slower kind of life. Grounded, tactile and full of small details worth noticing.",
            ],
            "promise": ["Warmth in every detail.", "Small details, worth noticing."],
            "bio": ["{name}. Warmth you can feel. Earthy, grounded, yours.", "{name}. For a slower kind of life."],
            "about": [
                "{name} grew from a love of things with character. We work in earthy tones and honest shapes, and we take our time over the details, because a {noun} that feels right is worth the wait.",
                "We are {name}. We make {thing} for lives that move a little slower. Warm, tactile and full of small details that reward a second look.",
            ],
            "caption": ["Warm tones for cooler days.", "Texture you can almost feel through the screen.",
                        "The slow pleasure of a good {noun}.", "Small details, worth a second look."],
        },
    },
    {
        "id": "modern_heritage", "name": "Modern Heritage", "ready": True,
        "essence": "Tradition, made contemporary. Vivid celebration tones in a clean, modern frame.",
        "spirit": ["Good Earth", "Nicobar", "Raw Mango"],
        "mood": ["Rooted", "Contemporary", "Vivid"],
        "ages": {"18-24": 1, "25-34": 2, "35-49": 3, "50+": 3},
        "why": "Buyers who value culture and occasion respond to traditional tones set in a modern frame.",
        "categories": ["jewellery", "clothing", "fragrance", "home_decor"],
        "wordmark": {"font": "prata", "case": "upper", "track": 0.12, "weight": 400},
        "frame": "square",
        "fonts": {"heading": "prata", "body": "newsreader", "accent": "jost"},
        "site": {"heading_weight": 400, "heading_track": 1,
                 "themes": {"jewellery": "jewellery", "*": "luxury"}, "fits": ["luxury", "jewellery"]},
        "studio": {"look": "editorial", "voice": "warm"},
        "palettes": [
            _p("indigo_marigold", "Indigo and marigold", "#F6F1E6", "#EEE4D0", "#1B1F3B", "#2D3A8C", "#D99A14"),
            _p("madder", "Madder", "#F8F0E8", "#EFE0D2", "#2E1410", "#A2322A", "#C99532"),
            _p("peacock", "Peacock", "#F3F1EA", "#E4E3D6", "#102A2B", "#0F5C5E", "#C8963E"),
        ],
        "voice": {
            "traits": ["Proud", "Warm", "Contemporary"],
            "say": ["Speak of celebration and occasion.", "Name tones and patterns precisely.",
                    "Mix warmth with a modern, clean rhythm."],
            "never": ["Claims about origin or craft unless they are true for you.",
                      "Phrases like timeless traditions of the past.", "Overloaded, flowery sentences."],
            "use": ["celebration", "rooted", "rich", "festive", "new"],
            "avoid": ["exotic", "oriental", "ethnic", "primitive", "tribal"],
        },
        "exclaim": 0,
        "imagery": ["Warm directional light.",
                    "Printed textiles and brass in clean, modern compositions.",
                    "Indigo, marigold and madder tones from the palette.",
                    "Festive, but never cluttered."],
        "prompt_style": "contemporary festive still life, warm directional light, block printed textile and brass surfaces, indigo marigold and madder red tones, clean modern composition, vivid and rooted mood",
        "copy": {
            "tagline": ["Tradition, in a new rhythm.", "Rooted, and right now.",
                        "Where old patterns meet new days.", "Made for celebrations, and after."],
            "statement": [
                "{name} brings the richness of tradition into the present. Deep indigo, warm marigold and clean modern shapes, made for the way you live now.",
                "At {name}, we love the patterns and tones that have always meant celebration, and we give them a contemporary rhythm. Every {noun} feels rooted and new at once.",
                "{name} is {thing} for people who carry tradition lightly. Vivid, modern and made for every celebration in between.",
            ],
            "promise": ["Rooted, and made for now.", "Every {noun} carries a little celebration."],
            "bio": ["{name}. Where tradition meets today.", "{name}. Rooted, and right now."],
            "about": [
                "{name} is inspired by the tones and patterns of celebration: indigo, marigold, madder red. We set them in clean, modern forms so each {noun} feels at home at a festival and on an ordinary Tuesday.",
                "We are {name}. We believe tradition is something to live with, not something to keep behind glass. Our {nouns} take the richness of the past and give it room to breathe.",
            ],
            "caption": ["For the festive season, and the days after it.", "Tradition, in a new rhythm.",
                        "Rich tones for the celebrations ahead.", "Rooted, and right now."],
        },
    },
    {
        "id": "apothecary", "name": "Apothecary", "ready": True,
        "essence": "Precise, sensory and calm. Plain labels, amber glass, measured words.",
        "spirit": ["Le Labo", "Aesop", "Byredo"],
        "mood": ["Precise", "Sensory", "Calm"],
        "ages": {"18-24": 1, "25-34": 3, "35-49": 3, "50+": 1},
        "why": "Buyers in their late twenties and thirties respond to the calm precision of the lab look.",
        "categories": ["fragrance", "home_decor"],
        "wordmark": {"font": "spacemono", "case": "upper", "track": 0.14, "weight": 400},
        "frame": "square",
        "fonts": {"heading": "newsreader", "body": "inter", "accent": "spacemono"},
        "site": {"heading_weight": 400, "heading_track": 0,
                 "themes": {"*": "basic"}, "fits": ["basic", "beauty"]},
        "studio": {"look": "clean", "voice": "minimal"},
        "palettes": [
            _p("kraft", "Kraft", "#EFE8DC", "#E2D7C4", "#1E1B17", "#5C4A32", "#9C8463"),
            _p("amber", "Amber glass", "#F4EFE6", "#E9E0D0", "#22180F", "#7E5119", "#3E5A48"),
            _p("clinic", "Clinic", "#F6F6F4", "#E9EAE6", "#141414", "#2F3A33", "#A8ADA4"),
        ],
        "voice": {
            "traits": ["Precise", "Calm", "Curious"],
            "say": ["Use measured, exact language.", "Describe notes, moods and rituals.",
                    "Plain labels, no decoration."],
            "never": ["Claims about what is inside unless they are true for you.", "Hype words.", "Emoji."],
            "use": ["notes", "balance", "ritual", "composed", "study"],
            "avoid": ["sexy", "irresistible", "magic", "miracle", "viral"],
        },
        "exclaim": 0,
        "imagery": ["Soft, overcast light.",
                    "Amber glass, kraft paper, matte stone and steel.",
                    "Orderly, precise arrangements.",
                    "Muted earth tones from the palette."],
        "prompt_style": "apothecary still life, soft overcast light, amber glass and kraft paper, matte stone and steel surfaces, muted earth tones, orderly precise composition, calm and studied mood",
        "copy": {
            "tagline": ["Composed with intent.", "Notes for daily life.", "Precise, by design.",
                        "Considered, down to the detail."],
            "statement": [
                "{name} approaches {thing} with a calm, precise hand. Every {noun} is considered down to the last detail, then left to speak quietly.",
                "At {name}, we treat each {noun} like a small study: measured, balanced and made for daily ritual.",
                "{name} is {thing} for people who like to know why. Plain labels, careful balance and nothing added for show.",
            ],
            "promise": ["Measured, balanced, considered.", "Every {noun} has a reason to exist."],
            "bio": ["{name}. Composed with intent. Notes for daily life.", "{name}. Considered, down to the detail."],
            "about": [
                "{name} began as a study in balance. We approach {thing} the way a good lab approaches a question: carefully, patiently, with notes kept at every step. What reaches you is calm, precise and made for daily ritual.",
                "We are {name}. We believe the most rewarding {nouns} reveal themselves slowly. Our labels are plain, our approach is patient, and our aim is simple: something you will want to come back to every day.",
            ],
            "caption": ["Composed for the morning ritual.", "Notes for daily life.",
                        "Field notes: calm, warm, clear.", "A study in balance."],
        },
    },
    {
        "id": "calm_airy", "name": "Calm & Airy", "ready": True,
        "essence": "Quiet, airy and balanced. Pale tones, light type, room to breathe.",
        "spirit": ["Muji", "Kinfolk", "Ferm Living"],
        "mood": ["Airy", "Balanced", "Serene"],
        "ages": {"18-24": 1, "25-34": 3, "35-49": 3, "50+": 2},
        "why": "Buyers setting up their own homes and routines respond to calm, uncluttered restraint.",
        "categories": ["jewellery", "clothing", "fragrance", "home_decor"],
        "wordmark": {"font": "jost", "case": "lower", "track": 0.18, "weight": 400},
        "frame": "none",
        "fonts": {"heading": "newsreader", "body": "worksans", "accent": "jost"},
        "site": {"heading_weight": 400, "heading_track": 0,
                 "themes": {"*": "basic"}, "fits": ["basic"]},
        "studio": {"look": "clean", "voice": "minimal"},
        "palettes": [
            _p("linen", "Linen", "#F4F1EC", "#E9E4DC", "#2B2926", "#686055", "#A9A08F"),
            _p("ash", "Ash", "#EFEFEC", "#E2E2DE", "#22231F", "#52554C", "#B9B4A8"),
            _p("charcoal", "Charcoal", "#1C1C1A", "#262624", "#EAE6DE", "#B8AD99", "#6E6A61"),
        ],
        "voice": {
            "traits": ["Calm", "Clear", "Gentle"],
            "say": ["Use few words and lots of space.", "Describe light, space and feeling.",
                    "Keep the rhythm slow."],
            "never": ["Urgency or countdowns.", "Crowded, busy sentences.", "Exclamation marks."],
            "use": ["calm", "space", "light", "quiet", "balance"],
            "avoid": ["hurry", "last chance", "crazy", "insane", "hype"],
        },
        "exclaim": 0,
        "imagery": ["Soft, diffused daylight.",
                    "Pale oak, paper and stoneware surfaces.",
                    "Lots of empty space around the {noun}.",
                    "Warm ivory and ash tones."],
        "prompt_style": "serene japandi still life, soft diffused daylight, pale oak, rice paper and stoneware surfaces, warm ivory and ash tones, lots of empty space, airy and balanced mood",
        "copy": {
            "tagline": ["Room to breathe.", "Calm, every day.", "Less clutter, more quiet.",
                        "Balance, in every {noun}."],
            "statement": [
                "{name} makes {thing} that leaves room to breathe. Pale tones, simple forms and a sense of calm you can feel.",
                "At {name}, we believe the right {noun} makes a day feel lighter. Balanced, quiet and easy to live with.",
                "{name} is {thing} for calm, uncluttered days. Simple, light and made to sit quietly in your life.",
            ],
            "promise": ["Calm, in every detail.", "Simple forms, quiet days."],
            "bio": ["{name}. Room to breathe. Simple forms, quiet days.", "{name}. Calm, every day."],
            "about": [
                "{name} started with a wish for quieter days. We design {thing} in pale, balanced tones and simple forms, so every {noun} brings a little calm with it.",
                "We are {name}. We believe in less clutter and more space: to think, to rest, to notice. Our {nouns} are made to fit into that space quietly.",
            ],
            "caption": ["Room to breathe.", "A quiet start to the week.", "Simple forms, soft light.",
                        "Less, and calmer for it."],
        },
    },
    {
        "id": "bold_maximal", "name": "Bold Maximal", "ready": True,
        "essence": "More is more. Jewel tones, pattern, drama and a serif with swagger.",
        "spirit": ["Gucci (2015 to 2022)", "Dolce & Gabbana", "Anthropologie"],
        "mood": ["Dramatic", "Rich", "Exuberant"],
        "ages": {"18-24": 2, "25-34": 3, "35-49": 2, "50+": 1},
        "why": "Confident buyers who dress or decorate to be remembered respond to drama and pattern.",
        "categories": ["jewellery", "clothing", "fragrance", "home_decor"],
        "wordmark": {"font": "gloock", "case": "upper", "track": 0.04, "weight": 400},
        "frame": "circle-solid",
        "fonts": {"heading": "dmserif", "body": "figtree", "accent": "syne"},
        "site": {"heading_weight": 400, "heading_track": -1,
                 "themes": {"fragrance": "beauty", "clothing": "fashion", "*": "luxury"},
                 "fits": ["luxury", "beauty", "fashion"]},
        "studio": {"look": "luxe", "voice": "playful"},
        "palettes": [
            _p("jewel", "Jewel box", "#FBF6EE", "#F1E6D6", "#1C1023", "#0F6B4F", "#B8185A"),
            _p("saffron", "Saffron", "#FFF7E8", "#FCE7BF", "#2A1608", "#A8320E", "#2D5BA8"),
            _p("midnight", "Midnight", "#120E1F", "#1D1730", "#F5EEDC", "#E8B931", "#E0628C"),
        ],
        "voice": {
            "traits": ["Bold", "Witty", "Lavish"],
            "say": ["Use vivid, sensory words.", "Play with rhythm and repetition.",
                    "One exclamation mark is allowed when it earns it."],
            "never": ["Apologising for being too much.", "Plain, flat descriptions.", "Corporate language."],
            "use": ["jewel", "drama", "rich", "entrance", "layered"],
            "avoid": ["minimal", "simple", "basic", "subtle", "understated"],
        },
        "exclaim": 1,
        "imagery": ["Dramatic, warm spotlight.",
                    "Velvet, brocade and gilded surfaces.",
                    "Layered pattern around the {noun}.",
                    "Emerald, fuchsia and saffron jewel tones."],
        "prompt_style": "maximalist still life, dramatic warm spotlight, velvet, brocade and gilded surfaces, emerald fuchsia and saffron jewel tones, layered pattern, opulent and theatrical mood",
        "copy": {
            "tagline": ["More is more.", "Made for a grand entrance.", "Never too much.", "Drama, daily."],
            "statement": [
                "{name} makes {thing} for people who never ask if it is too much. Jewel tones, bold pattern and drama in every detail.",
                "At {name}, we believe more is more. Every {noun} is designed to make an entrance and leave an impression.",
                "{name} is {thing} with swagger. Rich, layered and unapologetically bold.",
            ],
            "promise": ["Never too much.", "Every {noun} makes an entrance."],
            "bio": ["{name}. Made for a grand entrance. More is more.", "{name}. Drama, daily."],
            "about": [
                "{name} was made for people who love a little too much: tone, pattern and shine, all at once. We design {thing} in jewel tones and bold layers, so every {noun} feels like the start of a story.",
                "We are {name}. Minimal was never our style. Our {nouns} are rich, layered and joyful, made for people who would rather be remembered than overlooked.",
            ],
            "caption": ["Too much? Never heard of it.", "Jewel tones, all season.", "Make the entrance!",
                        "More is more, again."],
        },
    },
    {
        "id": "classic_timeless", "name": "Classic Timeless", "ready": True,
        "essence": "Polished, trusted and enduring. Navy, cream, a classic serif and good manners.",
        "spirit": ["Ralph Lauren", "Brooks Brothers", "Tanishq"],
        "mood": ["Polished", "Trusted", "Composed"],
        "ages": {"18-24": 0, "25-34": 1, "35-49": 3, "50+": 3},
        "why": "Buyers 40 and up trust polished, familiar codes and value reassurance over novelty.",
        "categories": ["jewellery", "clothing", "fragrance", "home_decor"],
        "wordmark": {"font": "librecaslon", "case": "upper", "track": 0.10, "weight": 400},
        "frame": "circle",
        "fonts": {"heading": "librecaslon", "body": "lora", "accent": "instrsans"},
        "site": {"heading_weight": 400, "heading_track": 0,
                 "themes": {"jewellery": "jewellery", "*": "luxury"}, "fits": ["luxury", "jewellery", "basic"]},
        "studio": {"look": "editorial", "voice": "luxury"},
        "palettes": [
            _p("navy", "Navy", "#F7F5F0", "#ECE8DF", "#141C2E", "#1F2F55", "#9E2B33"),
            _p("burgundy", "Burgundy", "#F6F2EC", "#EBE3D8", "#2A1418", "#6E1E2B", "#9C8457"),
            _p("forest", "Forest", "#F4F3EE", "#E6E5DC", "#15221B", "#2C4A3A", "#9C7E4A"),
        ],
        "voice": {
            "traits": ["Polished", "Reassuring", "Courteous"],
            "say": ["Write complete, well-mannered sentences.", "Reassure with clarity.",
                    "Choose familiar, trusted words."],
            "never": ["Slang.", "Trend words.", "Pushy sales language."],
            "use": ["classic", "polished", "trusted", "occasion", "enduring"],
            "avoid": ["viral", "drip", "slay", "obsessed", "hype"],
        },
        "exclaim": 0,
        "imagery": ["Soft, warm studio light.",
                    "Navy wool, cream paper and dark polished wood.",
                    "Balanced, traditional compositions.",
                    "Navy, cream and burgundy tones."],
        "prompt_style": "classic polished still life, soft warm studio light, navy wool, cream paper and dark polished wood surfaces, navy cream and burgundy tones, balanced traditional composition, refined and composed mood",
        "copy": {
            "tagline": ["Classic, for good reason.", "Polished, every day.", "Good taste never rushes.",
                        "Always in style."],
            "statement": [
                "{name} makes {thing} with polish and good manners. Classic shapes, rich tones and details that never go out of style.",
                "At {name}, we believe the classics are classic for a reason. Every {noun} is designed to look right today and in ten years.",
                "{name} is {thing} you can trust to look right. Polished, composed and always appropriate.",
            ],
            "promise": ["Always in style.", "Polished, for every occasion."],
            "bio": ["{name}. Classic, for good reason. Polished every day.", "{name}. Always in style."],
            "about": [
                "{name} stands for the quiet confidence of a classic. We design {thing} in rich, familiar tones and lasting shapes, so every {noun} feels right for the office, the dinner and the occasion in between.",
                "We are {name}. We are not interested in what is new this week. We are interested in what will still look right years from now, and we design every {noun} with that in mind.",
            ],
            "caption": ["Classic, for good reason.", "Polished for the week ahead.",
                        "A {noun} for every occasion.", "Good taste, quietly."],
        },
    },
]
_DIR = {d["id"]: d for d in DIRECTIONS}

# The order a direction is offered in, per category, before buyer age is taken
# into account. Also the whole ranking when the seller is "not sure".
CATEGORY_ORDER = {
    "jewellery": ["quiet_luxury", "soft_romantic", "modern_minimal", "heritage_maison", "modern_heritage",
                  "classic_timeless", "playful_pop", "everyday_bright", "street_edge", "artisan_earth",
                  "bold_maximal", "calm_airy"],
    "clothing": ["modern_minimal", "everyday_bright", "street_edge", "quiet_luxury", "playful_pop",
                 "soft_romantic", "artisan_earth", "modern_heritage", "classic_timeless", "bold_maximal",
                 "calm_airy", "heritage_maison"],
    "fragrance": ["quiet_luxury", "apothecary", "heritage_maison", "soft_romantic", "bold_maximal",
                  "modern_minimal", "playful_pop", "calm_airy", "artisan_earth", "modern_heritage",
                  "classic_timeless", "everyday_bright"],
    "home_decor": ["calm_airy", "artisan_earth", "quiet_luxury", "bold_maximal", "modern_heritage",
                   "apothecary", "modern_minimal", "playful_pop", "heritage_maison", "classic_timeless",
                   "everyday_bright", "soft_romantic"],
}


# ---------------------------------------------------------------------------
# colour maths (WCAG 2)
# ---------------------------------------------------------------------------
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def clean_hex(v) -> str:
    s = str(v or "").strip()
    if re.fullmatch(r"#?[0-9A-Fa-f]{3}", s):
        s = s.lstrip("#")
        s = "#" + "".join(ch * 2 for ch in s)
    if not s.startswith("#"):
        s = "#" + s
    return s.upper() if _HEX.match(s) else ""


def _lum(hex_: str) -> float:
    h = hex_.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def contrast(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return round((hi + 0.05) / (lo + 0.05), 2)


def on_accent(colours: dict) -> str:
    """The colour type sits in when it is set on the accent: ground or ink,
    whichever reads better."""
    a = colours["accent"]
    return colours["ground"] if contrast(colours["ground"], a) >= contrast(colours["ink"], a) else colours["ink"]


# The pairs every mockup actually draws, with the ratio each must reach.
CONTRAST_RULES = [
    ("ink", "ground", 4.5, "Text on the background"),
    ("ink", "surface", 4.5, "Text on panels"),
    ("accent", "ground", 3.0, "Accent on the background"),
    ("on_accent", "accent", 4.5, "Text on the accent"),
]


def contrast_report(colours: dict) -> list[dict]:
    c = dict(colours)
    c["on_accent"] = on_accent(colours)
    out = []
    for fg, bg, need, label in CONTRAST_RULES:
        r = contrast(c[fg], c[bg])
        out.append({"pair": f"{fg}/{bg}", "label": label, "ratio": r, "need": need, "ok": r >= need})
    return out


# ---------------------------------------------------------------------------
# library lookups
# ---------------------------------------------------------------------------
def direction(did: str) -> dict | None:
    return _DIR.get(did)


def palette(d: dict, pid: str) -> dict:
    return next((p for p in d["palettes"] if p["id"] == pid), d["palettes"][0])


def category_for_product_type(product_type: str) -> str:
    return FROM_PRODUCT_TYPE.get(str(product_type or ""), "")


def ranked(category: str, age: str) -> list[dict]:
    """Directions for this category, best suggestion first.

    A judgement, not a measurement: the scores are the author's reading of the
    research, and the UI labels the top ones "Suggested", never "best"."""
    order = CATEGORY_ORDER.get(category) or [d["id"] for d in DIRECTIONS]
    rows = []
    for pos, did in enumerate(order):
        d = _DIR[did]
        if not d.get("ready", True) or category not in d["categories"]:
            continue
        fit = d["ages"].get(age, 0) if age in d["ages"] else None
        rows.append((-(fit if fit is not None else 0), pos, d, fit))
    rows.sort(key=lambda r: (r[0], r[1]))
    return [{"id": d["id"], "fit": fit, "suggested": fit == 3} for _, _, d, fit in rows]


def public_library(spelling: str = "intl") -> dict:
    """Everything the module's screens need, minus the raw copy templates
    (those stay on the server; the composer is the only writer)."""
    us = spelling == "us"
    dirs = []
    for d in DIRECTIONS:
        if not d.get("ready", True):
            continue
        dirs.append({
            "id": d["id"], "name": d["name"], "essence": d["essence"], "spirit": d["spirit"],
            "mood": d["mood"], "ages": d["ages"], "why": d["why"], "categories": d["categories"],
            "wordmark": d["wordmark"], "frame": d["frame"], "fonts": d["fonts"],
            "palettes": d["palettes"], "voice": d["voice"],
            "imagery": d["imagery"], "site": {"heading_weight": d["site"]["heading_weight"],
                                              "heading_track": d["site"]["heading_track"]},
        })
    return {
        "version": LIBRARY_VERSION,
        "categories": [{"id": c["id"], "label": c["label_us"] if us else c["label"]} for c in CATEGORIES],
        "ages": [{"id": a["id"], "label": a["label"], "name": a["name"]} for a in AGES],
        "directions": dirs,
        "order": CATEGORY_ORDER,
        "wordmark_fonts": WORDMARK_FONTS,
        "frames": FRAMES,
        "contrast_rules": [{"pair": f"{f}/{b}", "need": n, "label": l} for f, b, n, l in CONTRAST_RULES],
        "name_max": NAME_MAX,
    }


# ---------------------------------------------------------------------------
# the composer
# ---------------------------------------------------------------------------
def _slots(name: str, category: str, spelling: str) -> dict:
    c = _CAT.get(category) or _CAT["jewellery"]
    thing = c["thing_us"] if spelling == "us" else c["thing"]
    return {"name": name or "Your brand", "thing": thing, "Thing": thing[:1].upper() + thing[1:],
            "noun": c["noun"], "nouns": c["nouns"], "wear": c["wear"],
            "Wear": c["wear"][:1].upper() + c["wear"][1:]}


def fill(template: str, slots: dict) -> str:
    return template.format(**slots)


def _seed(email: str, field: str, n: int) -> int:
    if n <= 1:
        return 0
    h = hashlib.sha1(f"{(email or '').lower()}|{field}".encode()).hexdigest()
    return int(h[:8], 16) % n


def variant_counts(did: str) -> dict:
    d = _DIR.get(did)
    if not d:
        return {}
    out = {f: len(d["copy"][f]) for f in TEXT_FIELDS}
    out["captions"] = len(d["copy"]["caption"])
    return out


def generated_text(email: str, did: str, category: str, name: str, spelling: str,
                   variants: dict | None = None) -> dict:
    """Every copy field for this direction, filled. `variants` holds the
    seller's chosen variant per field; a missing one falls back to a stable
    per-seller default so two sellers in one direction start differently."""
    d = _DIR[did]
    slots = _slots(name, category, spelling)
    variants = variants or {}
    out = {}
    for f in TEXT_FIELDS:
        pool = d["copy"][f]
        i = variants.get(f)
        i = i if isinstance(i, int) and 0 <= i < len(pool) else _seed(email, f, len(pool))
        out[f] = fill(pool[i], slots)
    caps = d["copy"]["caption"]
    start = variants.get("captions")
    start = start if isinstance(start, int) and 0 <= start < len(caps) else _seed(email, "captions", len(caps))
    out["captions"] = [fill(caps[(start + k) % len(caps)], slots) for k in range(len(caps))]
    return out


def monogram(name: str) -> str:
    """First letters of the first two significant words; one letter for a
    one-word name. Skips words that are never part of a monogram."""
    skip = {"the", "and", "&", "of", "a", "an", "by", "co", "co.", "studio"}
    words = [w for w in re.split(r"[\s\-_/]+", (name or "").strip()) if w]
    sig = [w for w in words if w.lower() not in skip] or words
    letters = [w[0] for w in sig if w and w[0].isalnum()][:2]
    return "".join(letters).upper() or "•"


def _is_latin(s: str) -> bool:
    return all(ord(ch) < 0x0250 or not ch.isalpha() for ch in s or "")


def _replace_name(text: str, old: str, new: str) -> tuple[str, bool]:
    """Whole-word, case-insensitive. Returns (text, still_contains_old)."""
    if not old or not text or old.lower() == (new or "").lower():
        return text, False
    pat = re.compile(r"(?<![\w])" + re.escape(old) + r"(?![\w])", re.I)
    out = pat.sub(new, text)
    return out, old.lower() in out.lower()


def blank_kit() -> dict:
    return {
        "v": LIBRARY_VERSION, "name": "", "name_source": "", "keep_case": False,
        "category": "", "age": "", "direction": "", "palette": "",
        "colours": {}, "fonts": {}, "wordmark": {}, "frame": "",
        "text": {f: "" for f in TEXT_FIELDS} | {"captions": []},
        "variants": {}, "edited": {}, "stale": [], "spelling": "intl",
        "applied_at": "", "last_apply": None, "updated_at": "",
    }


def get_kit(email: str) -> dict:
    saved = user_store.get_key(email, KIT_KEY, None) or {}
    kit = blank_kit()
    for k, v in saved.items():
        if k in kit:
            kit[k] = v
    return kit


def _clean_text(v, cap: int) -> str:
    s = re.sub(r"[ \t]+", " ", str(v or "").replace("\r", "")).strip()
    return s[:cap]


class BrandError(ValueError):
    pass


def compose(email: str, draft: dict, spelling: str = "intl") -> dict:
    """The kit as it should be after this draft, NOT saved.

    The draft is what the screen holds: the seller's choices, any fields they
    typed into (flagged in draft.edited), and their variant picks. Everything
    not edited is regenerated from the library, so a new name, category or
    direction flows into every line the seller has not made their own."""
    prev = get_kit(email)
    d_in = draft or {}
    kit = copy.deepcopy(prev)
    kit["spelling"] = "us" if spelling == "us" else "intl"

    # ---- choices ----
    name = " ".join(str(d_in.get("name", prev["name"]) or "").split())
    if len(name) > NAME_MAX:
        raise BrandError(f"Keep the brand name to {NAME_MAX} characters or fewer. Shorten it here; "
                         "your shop and site keep the full name until you apply.")
    old_name = prev["name"]
    kit["name"] = name
    if "name_source" in d_in:
        kit["name_source"] = str(d_in.get("name_source") or "")[:20]
    kit["keep_case"] = bool(d_in.get("keep_case", prev["keep_case"]))
    cat = str(d_in.get("category", prev["category"]) or "")
    kit["category"] = cat if cat in CATEGORY_IDS else ""
    age = str(d_in.get("age", prev["age"]) or "")
    kit["age"] = age if age in AGE_IDS else ""
    did = str(d_in.get("direction", prev["direction"]) or "")
    d = _DIR.get(did)
    if d and kit["category"] and kit["category"] not in d["categories"]:
        d = None
    kit["direction"] = d["id"] if d else ""
    edited = dict(prev.get("edited") or {})
    edited.update({k: bool(v) for k, v in (d_in.get("edited") or {}).items()
                   if k in TEXT_FIELDS + ["captions", "colours", "fonts", "wordmark"]})
    variants = dict(prev.get("variants") or {})
    for k, v in (d_in.get("variants") or {}).items():
        if k in TEXT_FIELDS + ["captions"] and isinstance(v, int):
            variants[k] = v
    direction_changed = kit["direction"] != prev["direction"]
    reset_visuals = bool(d_in.get("reset_visuals")) or direction_changed and not (
        edited.get("colours") or edited.get("fonts") or edited.get("wordmark"))

    if not d:
        kit["edited"], kit["variants"] = edited, variants
        kit["stale"] = []
        return kit

    # ---- colours ----
    pid = str(d_in.get("palette", prev["palette"]) or "")
    colours_in = d_in.get("colours")
    if reset_visuals:
        edited.pop("colours", None)
    if colours_in and edited.get("colours") and not reset_visuals:
        cols = {r: clean_hex(colours_in.get(r)) or (kit["colours"] or {}).get(r) or "" for r in COLOUR_ROLES}
        if all(cols.values()):
            kit["colours"], kit["palette"] = cols, "custom"
    else:
        pal = palette(d, pid if pid != "custom" else "")
        if direction_changed and pid not in [p["id"] for p in d["palettes"]]:
            pal = d["palettes"][0]
        kit["colours"], kit["palette"] = dict(pal["colours"]), pal["id"]
        edited.pop("colours", None)

    # ---- type ----
    from backend.core import sitebuilder
    if reset_visuals:
        edited.pop("fonts", None)
        edited.pop("wordmark", None)
    fonts_in = d_in.get("fonts") or {}
    if edited.get("fonts") and fonts_in:
        f = {r: (fonts_in.get(r) if fonts_in.get(r) in sitebuilder.FONT_IDS else d["fonts"][r])
             for r in ("heading", "body", "accent")}
        kit["fonts"] = f
    else:
        kit["fonts"] = dict(d["fonts"])
    wm_in = d_in.get("wordmark") or {}
    if edited.get("wordmark") and wm_in:
        font = wm_in.get("font") if wm_in.get("font") in WORDMARK_FONTS else d["wordmark"]["font"]
        case = wm_in.get("case") if wm_in.get("case") in ("upper", "lower", "none") else d["wordmark"]["case"]
        try:
            track = max(-0.05, min(0.4, float(wm_in.get("track"))))
        except (TypeError, ValueError):
            track = d["wordmark"]["track"]
        try:
            weight = int(wm_in.get("weight"))
            weight = weight if weight in (300, 400, 500, 600, 700, 800) else d["wordmark"]["weight"]
        except (TypeError, ValueError):
            weight = d["wordmark"]["weight"]
        kit["wordmark"] = {"font": font, "case": case, "track": round(track, 3), "weight": weight}
    else:
        kit["wordmark"] = dict(d["wordmark"])
    frame = str(d_in.get("frame") or "")
    kit["frame"] = frame if (frame in FRAMES and not reset_visuals and not direction_changed) else d["frame"]

    # ---- copy ----
    gen = generated_text(email, d["id"], kit["category"] or d["categories"][0], name,
                         kit["spelling"], variants)
    text_in = d_in.get("text") or {}
    text = {}
    stale = []
    for f in TEXT_FIELDS:
        if edited.get(f):
            cap = TEXT_CAPS[f]
            v = _clean_text(text_in.get(f, (prev["text"] or {}).get(f, "")), cap)
            v, still = _replace_name(v, old_name, name)
            if still:
                stale.append(f)
            text[f] = v
        else:
            text[f] = gen[f]
    if edited.get("captions"):
        caps_in = text_in.get("captions", (prev["text"] or {}).get("captions") or [])
        caps = []
        for i, c in enumerate(list(caps_in)[:CAPTION_COUNT]):
            v = _clean_text(c, TEXT_CAPS["caption"])
            v, still = _replace_name(v, old_name, name)
            if still and "captions" not in stale:
                stale.append("captions")
            caps.append(v)
        text["captions"] = caps
    else:
        text["captions"] = gen["captions"]
    kit["text"] = text
    kit["stale"] = stale
    kit["edited"] = {k: True for k, v in edited.items() if v}
    kit["variants"] = variants
    kit["v"] = LIBRARY_VERSION
    return kit


def describe(kit: dict) -> dict:
    """The derived things a screen shows next to a kit: monogram, contrast,
    whether the name is Latin, the website theme Apply would use."""
    cols = kit.get("colours") or {}
    rep = contrast_report(cols) if len(cols) == 5 else []
    d = _DIR.get(kit.get("direction") or "")
    slots = _slots(kit.get("name"), kit.get("category") or "jewellery", kit.get("spelling") or "intl")
    age_note = (_AGE.get(kit.get("age") or "") or {}).get("note", "")
    return {
        # Photo rules and voice lines with the seller's category filled in.
        "imagery": [fill(s, slots) for s in d["imagery"]] if d else [],
        "voice": ({**d["voice"], "say": [fill(s, slots) for s in d["voice"]["say"]]} if d else {}),
        "age_note": fill(age_note, slots) if age_note else "",
        "thing": slots["thing"], "noun": slots["noun"], "nouns": slots["nouns"],
        "monogram": monogram(kit.get("name") or ""),
        "latin": _is_latin(kit.get("name") or ""),
        "contrast": rep,
        "contrast_ok": all(r["ok"] for r in rep) if rep else False,
        "blocking": [r for r in rep if r["pair"] == "ink/ground" and not r["ok"]],
        "on_accent": on_accent(cols) if len(cols) == 5 else "",
        "variant_counts": variant_counts(kit.get("direction") or ""),
    }


def save(email: str, draft: dict, spelling: str = "intl") -> dict:
    kit = compose(email, draft, spelling)
    prev = get_kit(email)
    kit["applied_at"] = prev.get("applied_at") or ""
    kit["last_apply"] = prev.get("last_apply")
    kit["updated_at"] = _now()
    user_store.set_key(email, KIT_KEY, kit)
    return kit


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Apply: copy the kit into the Website Builder and Product Studio
# ---------------------------------------------------------------------------
def theme_for(kit: dict, current_theme: str = "") -> str:
    """The website theme this direction maps to. Keeps the seller's current
    theme when it already suits the direction."""
    d = _DIR.get(kit.get("direction") or "")
    if not d:
        return current_theme or "basic"
    if current_theme and current_theme in d["site"].get("fits", []):
        return current_theme
    themes = d["site"]["themes"]
    return themes.get(kit.get("category") or "", themes["*"])


def site_accents(colours: dict, theme_id: str) -> dict:
    """The site's accent for light and dark mode.

    The theme keeps its own background, text and button-text colours; only the
    accent is ours. So the accent has to read against THAT theme: button text
    (accent_ink) at 4.5:1 and the page background at 3:1. The first of the
    kit's accent, support, ink and ground that passes wins; if none does, that
    mode keeps the theme's own accent (empty string)."""
    from backend.core import sitebuilder
    th = next((t for t in sitebuilder.THEMES if t["id"] == theme_id), sitebuilder.THEMES[0])
    out = {}
    for mode in ("light", "dark"):
        pal = th[mode]
        pick = ""
        for role in ("accent", "support", "ink", "ground"):
            c = colours.get(role)
            if c and contrast(c, pal["accent_ink"]) >= 4.5 and contrast(c, pal["bg"]) >= 3.0:
                pick = c
                break
        out[mode] = pick
    return out


def voice_rules(kit: dict) -> str:
    """One compact paragraph for the caption writer. Studio caps fields at 400
    characters, so this is built to fit."""
    d = _DIR.get(kit.get("direction") or "")
    if not d:
        return ""
    v = d["voice"]
    slots = _slots(kit.get("name"), kit.get("category") or "jewellery", kit.get("spelling") or "intl")
    age_note = (_AGE.get(kit.get("age") or "") or {}).get("note", "")
    parts = [f"{d['name']} voice: {', '.join(v['traits']).lower()}.",
             "Do: " + " ".join(fill(s, slots) for s in v["say"]),
             "Never: " + " ".join(v["never"]),
             (fill(age_note, slots) if age_note else "")]
    out = " ".join(p for p in parts if p)
    return out[:400]


def _studio_patch(kit: dict) -> dict:
    d = _DIR[kit["direction"]]
    c = kit["colours"]
    pal_name = palette(d, kit["palette"])["name"] if kit["palette"] != "custom" else "Custom"
    age = _AGE.get(kit.get("age") or "") or {}
    cat = _CAT.get(kit.get("category") or "") or {}
    thing = (cat.get("thing_us") if kit.get("spelling") == "us" else cat.get("thing")) or ""
    audience = (f"Buyers aged {age['label']} ({age['name'].lower()}) shopping for {thing}"
                if age and age.get("id") != "all" else f"People shopping for {thing}")
    return {
        "name": kit["name"],
        "tagline": kit["text"]["tagline"],
        "about": kit["text"]["statement"],
        "audience": audience,
        "look": d["studio"]["look"],
        "voice": d["studio"]["voice"],
        "palette": (f"{d['name']} / {pal_name}: background {c['ground']}, text {c['ink']}, "
                    f"accent {c['accent']}, support {c['support']}"),
        "avoid": ", ".join(d["voice"]["avoid"]),
        "voice_rules": voice_rules(kit),
    }


def has_site(email: str) -> bool:
    from backend.core import sitebuilder
    raw = user_store.get_key(email, sitebuilder.SITE_KEY, None)
    if raw:
        return True
    try:
        return bool((sitebuilder.get_site(email) or {}).get("seeded"))
    except Exception:  # noqa: BLE001
        return False


def _get(obj: dict, path: str):
    for k in path.split("."):
        obj = (obj or {}).get(k) if isinstance(obj, dict) else None
    return obj


FIELD_LABELS = {
    "site.brand": "Shop name", "site.tagline": "Tagline", "site.story.body": "Story (About us)",
    "site.brief": "Site brief (what the site writer works from)",
    "site.style.heading_font": "Heading font", "site.style.body_font": "Body font",
    "site.style.accent_font": "Small caps font", "site.style.accent": "Accent colour (light mode)",
    "site.style.accent_dark": "Accent colour (dark mode)", "site.style.heading_weight": "Heading weight",
    "site.style.heading_track": "Heading letter spacing", "site.theme": "Website layout (theme)",
    "site.logo_url": "Uploaded logo image",
    "studio.name": "Brand name", "studio.tagline": "Tagline", "studio.about": "About (what you make and why)",
    "studio.audience": "Who buys it", "studio.look": "Photo look", "studio.voice": "Writing voice",
    "studio.palette": "Brand colours", "studio.avoid": "Words to avoid",
    "studio.voice_rules": "Voice rules for captions",
}
# Seller-written fields that carry facts about their products. Replaced only
# when the seller ticks them (or they are empty / still what we last wrote).
_PROTECTED = {"site.story.body", "site.brief", "studio.about"}


def plan_apply(email: str, kit: dict, opts: dict | None = None) -> dict:
    """What Apply would change, field by field, without changing anything."""
    from backend.core import sitebuilder, studio
    opts = opts or {}
    if not kit.get("direction") or not kit.get("name"):
        raise BrandError("Pick a name and a direction first.")
    d = _DIR[kit["direction"]]
    last = (kit.get("last_apply") or {}).get("written") or {}
    rows = []
    site_ok = has_site(email)
    site = sitebuilder.get_site(email) if site_ok else {}
    switch = bool(opts.get("switch_theme", not site.get("published"))) if site_ok else False
    post_theme = ""
    if site_ok:
        # Switch on: the direction's theme, unless the current one already
        # suits it. Switch off: the current theme. The accent is checked
        # against whichever this is, in both modes.
        post_theme = theme_for(kit, site.get("theme", "")) if switch else (site.get("theme") or "basic")

    def add(dest_path: str, before, after, protected=False):
        if before == after:
            return
        drift = dest_path in last and before != last[dest_path]
        default = not drift
        if protected and str(before or "").strip() and before != last.get(dest_path):
            default = False
        rows.append({"path": dest_path, "label": FIELD_LABELS.get(dest_path, dest_path),
                     "before": before, "after": after, "drift": drift, "default": default})

    if site_ok:
        acc = site_accents(kit["colours"], post_theme)
        sp = {
            "site.brand": kit["name"], "site.tagline": kit["text"]["tagline"],
            "site.story.body": kit["text"]["about"], "site.brief": kit["text"]["statement"],
            "site.style.heading_font": kit["fonts"]["heading"], "site.style.body_font": kit["fonts"]["body"],
            "site.style.accent_font": kit["fonts"]["accent"],
            "site.style.accent": acc["light"], "site.style.accent_dark": acc["dark"],
            "site.style.heading_weight": d["site"]["heading_weight"],
            "site.style.heading_track": max(-8, min(30, int(d["site"]["heading_track"]))),
        }
        if switch:
            sp["site.theme"] = post_theme
        if opts.get("clear_logo"):
            sp["site.logo_url"] = ""
        for path, after in sp.items():
            add(path, _get({"site": site}, path), after, path in _PROTECTED)
    stu = studio.get_brand(email)
    for k, after in _studio_patch(kit).items():
        add(f"studio.{k}", stu.get(k, ""), after, f"studio.{k}" in _PROTECTED)

    theme_case = ""
    if site_ok:
        th = next((t for t in sitebuilder.THEMES if t["id"] == post_theme), sitebuilder.THEMES[0])
        theme_case = th["layout"].get("case", "none")
    return {
        "rows": rows, "has_site": site_ok,
        # What the site preview draws: the accent the site will carry after
        # Apply (or already carries), whether or not that row still differs.
        "preview": {"accent": (site_accents(kit["colours"], post_theme)["light"]
                               if site_ok else "")},
        "published": bool(site.get("published")) if site_ok else False,
        "theme": {"current": site.get("theme", "") if site_ok else "", "after": post_theme,
                  "switch": switch, "case": theme_case,
                  "label": next((t["label"] for t in sitebuilder.THEMES if t["id"] == post_theme), "")},
        "has_logo": bool(site.get("logo_url")) if site_ok else False,
        "aesthetic_kept": bool((stu.get("aesthetic") or "").strip()),
        "blocked": _blocked(kit),
    }


def _blocked(kit: dict) -> list[str]:
    out = []
    if kit.get("stale"):
        out.append("Some edited lines still use your old shop name. Update them, then apply.")
    rep = contrast_report(kit["colours"]) if len(kit.get("colours") or {}) == 5 else []
    if any(r["pair"] == "ink/ground" and not r["ok"] for r in rep):
        out.append("Your text colour is too faint on your background. Pick darker text or a lighter background.")
    return out


def _write(email: str, rows: list[dict], restore: bool = False) -> None:
    from backend.core import sitebuilder, studio
    site_patch: dict = {}
    studio_patch: dict = {}
    key = "before" if restore else "after"
    for r in rows:
        dest, _, rest = r["path"].partition(".")
        if dest == "site":
            parts = rest.split(".")
            o = site_patch
            for p in parts[:-1]:
                o = o.setdefault(p, {})
            o[parts[-1]] = r[key]
        elif dest == "studio":
            studio_patch[rest] = r[key] if r[key] is not None else ""
    if site_patch:
        cur = sitebuilder.get_site(email)
        for k, v in list(site_patch.items()):
            if isinstance(v, dict) and isinstance(cur.get(k), dict):
                site_patch[k] = {**cur[k], **v}
        sitebuilder.save_site(email, site_patch)
    if studio_patch:
        studio.save_brand(email, studio_patch)


def apply(email: str, draft: dict, opts: dict | None = None, spelling: str = "intl") -> dict:
    """Save the posted kit, then copy the ticked fields into the website and
    Product Studio. Keeps what it replaced so Undo can put it back."""
    opts = opts or {}
    kit = save(email, draft, spelling)
    plan = plan_apply(email, kit, opts)
    if plan["blocked"]:
        raise BrandError(" ".join(plan["blocked"]))
    ticks = opts.get("fields") or {}
    sections = opts.get("sections") or {"site": True, "studio": True}
    chosen = [r for r in plan["rows"]
              if sections.get(r["path"].split(".")[0], True) and ticks.get(r["path"], r["default"])]
    if any(r["path"].startswith("site.") for r in chosen) and plan["published"] and not opts.get("confirm_live"):
        raise BrandError("CONFIRM_LIVE: This updates your live shop now. Confirm to continue.")
    _write(email, chosen)
    kit["applied_at"] = _now()
    if not chosen:
        # Nothing changed. Keep the previous snapshot, or this "apply" would
        # silently take away the seller's way back from the last real one.
        user_store.set_key(email, KIT_KEY, kit)
        return {"kit": kit, "applied": [], "plan": plan}
    kit["last_apply"] = {"at": kit["applied_at"],
                         "rows": [{"path": r["path"], "before": r["before"], "after": r["after"]} for r in chosen],
                         "written": {r["path"]: r["after"] for r in chosen}}
    user_store.set_key(email, KIT_KEY, kit)
    return {"kit": kit, "applied": [r["path"] for r in chosen], "plan": plan}


def plan_undo(email: str) -> dict:
    """What Undo would put back. A field changed since Apply is listed as drift
    and left alone unless the seller ticks it."""
    from backend.core import sitebuilder, studio
    kit = get_kit(email)
    la = kit.get("last_apply") or {}
    if not la.get("rows"):
        return {"rows": [], "at": "", "published": False}
    site = sitebuilder.get_site(email) if has_site(email) else {}
    stu = studio.get_brand(email)
    rows = []
    for r in la["rows"]:
        dest = {"site": site, "studio": stu}[r["path"].split(".")[0]]
        now = _get({r["path"].split(".")[0]: dest}, r["path"])
        drift = now != r["after"]
        rows.append({"path": r["path"], "label": FIELD_LABELS.get(r["path"], r["path"]),
                     "before": r["before"], "after": r["after"], "now": now,
                     "drift": drift, "default": not drift})
    return {"rows": rows, "at": la.get("at", ""), "published": bool(site.get("published"))}


def undo(email: str, opts: dict | None = None) -> dict:
    opts = opts or {}
    plan = plan_undo(email)
    if not plan["rows"]:
        raise BrandError("There is nothing to undo.")
    ticks = opts.get("fields") or {}
    chosen = [r for r in plan["rows"] if ticks.get(r["path"], r["default"])]
    if any(r["path"].startswith("site.") for r in chosen) and plan["published"] and not opts.get("confirm_live"):
        raise BrandError("CONFIRM_LIVE: This updates your live shop now. Confirm to continue.")
    _write(email, chosen, restore=True)
    kit = get_kit(email)
    kit["last_apply"] = None
    kit["applied_at"] = ""
    user_store.set_key(email, KIT_KEY, kit)
    return {"kit": kit, "restored": [r["path"] for r in chosen]}


# ---------------------------------------------------------------------------
# images the founder generated from BRAND_IMAGE_PROMPTS.md
# ---------------------------------------------------------------------------
ASSET_KEYS = ["post-bg", "story-bg", "hero", "texture", "pattern", "packaging", "motif"] + \
             [f"mood-{c}" for c in CATEGORY_IDS]
ASSET_EXT = (".webp", ".jpg", ".jpeg", ".png")
# Greyscale assets: tinted in CSS so they follow any palette.
TINTED = {"texture", "pattern"}


def assets_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(os.path.dirname(here)), "Smart CafeX", "brand-assets")


def list_assets() -> dict:
    """{direction: {asset_key: url}} for files that exist on disk."""
    root = assets_dir()
    out: dict = {}
    if not os.path.isdir(root):
        return out
    for did in _DIR:
        folder = os.path.join(root, did)
        if not os.path.isdir(folder):
            continue
        found = {}
        for fn in sorted(os.listdir(folder)):
            stem, ext = os.path.splitext(fn)
            if ext.lower() in ASSET_EXT and stem in ASSET_KEYS and stem not in found:
                found[stem] = f"/smart-static/brand-assets/{did}/{fn}"
        if found:
            out[did] = found
    return out


# ---------------------------------------------------------------------------
# library scans (used by the tests and by scripts/gen_brand_prompts.py)
# ---------------------------------------------------------------------------
# Product facts a template must never assert. The seller knows these; we do not.
CLAIM_WORDS = [
    r"hand[\s-]?made", r"hand[\s-]?crafted", r"hand[\s-]?finished", r"hand[\s-]?woven", r"hand[\s-]?sewn",
    r"natural", r"organic", r"sustainab\w*", r"eco\b", r"eco-friendly", r"ethical\w*", r"recycled",
    r"upcycled", r"vegan", r"cruelty", r"non-toxic", r"toxin\w*", r"chemical\w*", r"\bpure\b", r"purest",
    r"certified", r"certificat\w*", r"hallmark\w*", r"guarantee\w*", r"warranty", r"lifetime",
    r"refund\w*", r"\breturns?\b", r"free shipping", r"delivery", r"dispatch\w*", r"small[\s-]batch\w*",
    r"\bbatch(es)?\b", r"ingredient\w*", r"artisan(s|al)?\b", r"heritage", r"since \d", r"generations",
    r"family[\s-]run", r"ancestral", r"authentic", r"genuine", r"\bbest\b", r"finest", r"(?<![0-9A-Fa-f])#1(?![0-9A-Fa-f])",
    r"number one", r"world'?s", r"locally", r"made in",
]
# Materials: fine in photo directions (props), never in seller copy.
MATERIAL_WORDS = [r"\bgold\b", r"silver", r"sterling", r"platinum", r"diamond\w*", r"gem\w*", r"leather",
                  r"cotton", r"\blinen\b", r"\bsilk\b", r"\bwool\b", r"cashmere", r"\bbrass\b", r"copper",
                  r"\bwood\w*", r"\bclay\b", r"ceramic\w*", r"\boud\b", r"sandalwood", r"\bpearls?\b",
                  r"velvet"]
# Words spelled differently in US and UK English. Copy uses neither spelling.
SPELLING_VARIANTS = [r"colou?r\w*", r"favou?rit\w*", r"\bgr[ae]y\b", r"cent(er|re)\w*", r"personali[sz]\w*",
                     r"jewel(le)?ry", r"\bcos[yz]\w*", r"travel+ing", r"organi[sz]\w*", r"reali[sz]\w*",
                     r"honou?r\w*", r"flavou?r\w*", r"glamou?r\w*", r"humou?r\w*", r"neighbou?r\w*",
                     r"behaviou?r\w*", r"\bmo(u)?ld\w*", r"catalog(ue)?\b", r"theat(er|re)\w*",
                     r"apologi[sz]\w*", r"\bfavou?r\b"]


def _matches(patterns: list[str], text: str) -> list[str]:
    return [p for p in patterns if re.search(p, text, re.I)]


def seller_copy_lines(d: dict) -> list[str]:
    """Every line from this direction that can reach a shopper or a caption
    prompt as-is: the copy templates, plus the voice 'say' and 'use' lists."""
    lines = []
    for f in TEXT_FIELDS + ["caption"]:
        lines += d["copy"][f]
    lines += d["voice"]["say"] + d["voice"]["use"]
    return lines


def scan_direction(d: dict) -> list[str]:
    problems = []
    spirit = [s.split(" (")[0] for s in d["spirit"]]
    copy_lines = []
    for f in TEXT_FIELDS + ["caption"]:
        copy_lines += d["copy"][f]
    for line in seller_copy_lines(d):
        stripped = re.sub(r"\{[A-Za-z]+\}", "", line)
        for w in _matches(CLAIM_WORDS, stripped):
            problems.append(f"{d['id']}: claim word /{w}/ in: {line}")
        for w in _matches(SPELLING_VARIANTS, stripped):
            problems.append(f"{d['id']}: US/UK spelling /{w}/ in: {line}")
        if "—" in line or "–" in line:
            problems.append(f"{d['id']}: dash in: {line}")
        for s in spirit:
            if s.lower() in line.lower():
                problems.append(f"{d['id']}: brand reference {s} in: {line}")
    for line in copy_lines:
        stripped = re.sub(r"\{[A-Za-z]+\}", "", line)
        for w in _matches(MATERIAL_WORDS, stripped):
            problems.append(f"{d['id']}: material word /{w}/ in: {line}")
    for line in d["imagery"] + [d["prompt_style"]]:
        for w in _matches(CLAIM_WORDS, line):
            problems.append(f"{d['id']}: claim word /{w}/ in imagery: {line}")
        for s in spirit:
            if s.lower() in line.lower():
                problems.append(f"{d['id']}: brand reference {s} in imagery: {line}")
    for f in TEXT_FIELDS + ["caption"]:
        for line in d["copy"][f]:
            if line.count("!") > d.get("exclaim", 0):
                problems.append(f"{d['id']}: too many exclamation marks in: {line}")
    return problems
