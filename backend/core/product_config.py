"""
Product-type configuration — the single source of truth for the pivot from a
café-analytics tool to a small-scale social-media seller's command centre.

A seller picks WHAT they sell (jewellery / clothes / perfumes, or a generic
default) when they upload reviews or connect a source. That choice drives:

  * positioning themes + the keyword lexicon used to tag review text
    (replaces the old café benchmark's Keyword_Diagnostics.csv), and
  * complaint themes + keywords + severity + fix-first playbook
    (replaces complaints.py's café-specific THEME_KEYWORDS).

There is deliberately ONE shared theme set across product types — a review
that praises "quality" or "packaging" means the same thing whether it's a
ring or a kurta. What changes per type is the KEYWORDS that map onto each
theme (a perfume's "longevity" vs a dress's "fit"), so the same engine reads
each catalogue in its own language.

No café benchmark, no peer comparison — positioning here is about the
seller's OWN customers, not how they stack up against other shops.
"""
from __future__ import annotations

# ---------------------------------------------------------
# Product types
# ---------------------------------------------------------
PRODUCT_TYPES = [
    {"id": "jewellery", "label": "Jewellery", "icon": "💍",
     "noun": "piece", "nouns": "pieces"},
    {"id": "clothes", "label": "Clothes", "icon": "👗",
     "noun": "item", "nouns": "items"},
    {"id": "perfumes", "label": "Perfumes", "icon": "🧴",
     "noun": "fragrance", "nouns": "fragrances"},
    {"id": "generic", "label": "Other products", "icon": "🛍️",
     "noun": "product", "nouns": "products"},
]
_BY_ID = {p["id"]: p for p in PRODUCT_TYPES}
DEFAULT_TYPE = "generic"


def normalize(product_type: str | None) -> str:
    return product_type if product_type in _BY_ID else DEFAULT_TYPE


def meta(product_type: str | None) -> dict:
    return _BY_ID[normalize(product_type)]


def public_types() -> list[dict]:
    """What the frontend shows in the product-type picker."""
    return [{"id": p["id"], "label": p["label"], "icon": p["icon"]} for p in PRODUCT_TYPES]


# ---------------------------------------------------------
# Positioning themes (shared) + the two axes they map onto
# ---------------------------------------------------------
# The 2x2 positioning map keeps the two axes a small brand actually thinks in:
#   x:  value  <-->  premium          (what you charge / how premium it feels)
#   y:  brand & aesthetic  <-->  product      (what customers come to you FOR)
# Themes are grouped onto those axes below.
POSITIONING_THEMES = [
    "Quality", "Design & Style", "Value for Money", "Premium & Luxury",
    "Authenticity", "Packaging & Unboxing", "Delivery & Shipping",
    "Customer Service", "Aesthetic & Trendy", "Fit & Feel",
]

# axis groupings (theme -> weight); "product" = known for the product itself,
# "brand" = known for the brand / aesthetic / experience.
PREMIUM_THEME_W = {"Premium & Luxury": 1.0, "Authenticity": 0.5}
VALUE_THEME_W   = {"Value for Money": 1.0}
PRODUCT_THEME_W = {"Quality": 1.0, "Design & Style": 0.7, "Fit & Feel": 0.7}
BRAND_THEME_W   = {"Aesthetic & Trendy": 1.0, "Packaging & Unboxing": 0.8,
                   "Customer Service": 0.5}

# Keywords shared by every product type, then per-type enrichment. Each entry
# is a plain lowercase substring; matching is substring-in-review-text.
_SHARED_KEYWORDS: dict[str, list[str]] = {
    "Quality": ["quality", "well made", "well-made", "durable", "sturdy", "long lasting",
                "long-lasting", "premium quality", "good quality", "top notch", "finish",
                "finishing", "craftsmanship", "build quality"],
    "Design & Style": ["design", "designs", "stylish", "style", "beautiful", "gorgeous",
                       "elegant", "pretty", "look", "looks", "classy", "unique design",
                       "colour", "color", "pattern"],
    "Value for Money": ["value for money", "worth the price", "worth it", "affordable",
                        "reasonable", "budget", "cheap", "good price", "great deal",
                        "value", "pocket friendly", "pocket-friendly", "worth every"],
    "Premium & Luxury": ["premium", "luxury", "luxurious", "high end", "high-end",
                         "expensive but", "rich look", "royal", "exclusive", "classy"],
    "Authenticity": ["authentic", "genuine", "original", "real", "as described",
                     "as shown", "as pictured", "legit", "not fake", "true to"],
    "Packaging & Unboxing": ["packaging", "packed", "package", "unboxing", "box",
                             "gift wrap", "wrapping", "beautifully packed", "nicely packed",
                             "presentation"],
    "Delivery & Shipping": ["delivery", "delivered", "shipping", "shipped", "arrived",
                            "fast delivery", "quick delivery", "on time", "courier",
                            "dispatch", "tracking"],
    "Customer Service": ["customer service", "support", "responsive", "helpful", "seller",
                         "replied", "response", "resolved", "communication", "polite",
                         "query", "queries"],
    "Aesthetic & Trendy": ["aesthetic", "trendy", "trending", "instagram", "insta",
                           "reel", "viral", "on trend", "fashionable", "vibe",
                           "photogenic", "picture perfect"],
    "Fit & Feel": ["comfortable", "comfort", "feel", "feels", "light weight",
                   "lightweight", "smooth"],
}

_TYPE_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "jewellery": {
        "Quality": ["polish", "plating", "does not tarnish", "doesn't tarnish", "no tarnish",
                    "hallmark", "bis", "solid", "clasp"],
        "Design & Style": ["sparkle", "shine", "shiny", "bling", "stone", "stones",
                           "kundan", "meenakari", "oxidised", "oxidized", "statement piece"],
        "Premium & Luxury": ["gold", "diamond", "solitaire", "22k", "18k", "karat",
                             "carat", "sterling", "sterling silver", "925"],
        "Authenticity": ["real gold", "real silver", "certified", "hallmarked",
                         "genuine stone", "not artificial"],
        "Fit & Feel": ["adjustable", "not heavy", "comfortable to wear", "skin friendly",
                       "no allergy", "did not turn skin", "didn't turn skin"],
    },
    "clothes": {
        "Quality": ["fabric", "material", "stitching", "cloth", "cotton", "linen",
                    "thread", "seams", "does not shrink", "colour did not fade",
                    "color did not fade", "no fade"],
        "Design & Style": ["print", "prints", "embroidery", "pattern", "cut", "drape",
                           "silhouette", "neckline"],
        "Fit & Feel": ["fit", "fitting", "fits", "true to size", "size", "sizing",
                       "comfortable", "breathable", "soft", "stretchable", "loose",
                       "tight", "length"],
        "Premium & Luxury": ["premium fabric", "pure cotton", "handloom", "silk",
                            "designer", "boutique"],
    },
    "perfumes": {
        "Quality": ["longevity", "lasts", "long lasting", "stays", "sillage", "projection",
                    "does not fade", "lasted all day", "long lasting smell"],
        "Design & Style": ["bottle", "fragrance", "scent", "smell", "aroma", "notes",
                           "fresh", "musky", "floral", "woody", "sweet smell"],
        "Premium & Luxury": ["premium fragrance", "luxury scent", "eau de parfum",
                            "edp", "long lasting perfume", "designer dupe", "niche"],
        "Authenticity": ["original fragrance", "not a knockoff", "smells like the original",
                         "authentic scent"],
        "Fit & Feel": ["not overpowering", "subtle", "pleasant", "skin friendly"],
    },
}


def positioning_lexicon(product_type: str | None) -> dict[str, list[str]]:
    """theme -> [keywords], shared set enriched with the product type's own."""
    pt = normalize(product_type)
    out: dict[str, list[str]] = {t: list(_SHARED_KEYWORDS.get(t, [])) for t in POSITIONING_THEMES}
    for theme, extra in _TYPE_KEYWORDS.get(pt, {}).items():
        out.setdefault(theme, [])
        # dedupe while preserving order
        seen = set(out[theme])
        for k in extra:
            if k not in seen:
                out[theme].append(k); seen.add(k)
    return out


# ---------------------------------------------------------
# Complaint themes: keywords + severity + fix-first playbook
# ---------------------------------------------------------
# Shared across product types; a few keywords are enriched per type below.
COMPLAINT_KEYWORDS: dict[str, list[str]] = {
    "Product Quality":  ["poor quality", "bad quality", "cheap quality", "low quality",
                         "flimsy", "broke", "broken", "defective", "faulty", "damaged product",
                         "not durable", "fell apart", "stopped working", "quality is bad",
                         "worst quality", "material is bad", "cheap material"],
    "Not As Described": ["not as described", "not as shown", "different from picture",
                         "different from image", "looks different", "not what i ordered",
                         "misleading", "false", "photo is different", "colour different",
                         "color different", "not same as", "totally different"],
    "Fake / Not Genuine": ["fake", "duplicate", "not original", "not genuine", "counterfeit",
                           "first copy", "replica", "knockoff", "not authentic", "cheap copy"],
    "Damaged in Transit": ["damaged", "broken in transit", "arrived broken", "arrived damaged",
                           "crushed", "dented", "torn", "leaked", "leaking", "shattered",
                           "packaging was damaged", "box was crushed"],
    "Late / No Delivery": ["late delivery", "delayed", "never delivered", "not delivered",
                           "still waiting", "took forever", "took too long", "no tracking",
                           "delivery was late", "very late", "not received", "lost package",
                           "where is my order"],
    "Wrong Item":       ["wrong item", "wrong product", "wrong size", "wrong colour",
                         "wrong color", "sent wrong", "received wrong", "different item",
                         "incorrect item", "mixed up my order"],
    "Poor Packaging":   ["poor packaging", "bad packaging", "no packaging", "cheap packaging",
                         "loosely packed", "not packed well", "no bubble wrap", "flimsy box"],
    "Overpriced":       ["overpriced", "too expensive", "not worth the price", "too costly",
                         "not worth the money", "waste of money", "pricey", "expensive for what"],
    "Return / Refund Issue": ["refund", "return", "no refund", "refund not", "exchange",
                              "return policy", "did not refund", "money not returned",
                              "no return", "refused refund", "still waiting for refund"],
    "Poor Customer Service": ["rude", "no response", "did not respond", "no reply", "ignored",
                              "unresponsive", "worst service", "poor service", "no support",
                              "never replied", "bad service", "customer care"],
    "Sizing Issue":     ["too small", "too big", "size issue", "not true to size", "size chart",
                         "runs small", "runs large", "did not fit", "didn't fit", "loose",
                         "tight", "size was wrong"],
}

COMPLAINT_SEVERITY: dict[str, tuple[str, int]] = {
    "Fake / Not Genuine":      ("Critical", 4),
    "Return / Refund Issue":   ("Critical", 4),
    "Product Quality":         ("High Priority", 3),
    "Not As Described":        ("High Priority", 3),
    "Damaged in Transit":      ("High Priority", 3),
    "Wrong Item":              ("High Priority", 3),
    "Late / No Delivery":      ("Medium Priority", 2),
    "Poor Customer Service":   ("Medium Priority", 2),
    "Sizing Issue":            ("Medium Priority", 2),
    "Overpriced":              ("Medium Priority", 2),
    "Poor Packaging":          ("Low Priority", 1),
    "Other":                   ("Medium Priority", 2),
}

COMPLAINT_PLAYBOOK: dict[str, str] = {
    "Product Quality": "Pull the affected batch and inspect it yourself before shipping any more. Add a quick quality-check photo step before dispatch, and reply to each reviewer with a replacement offer.",
    "Not As Described": "Reshoot your product photos in natural light against a plain background and add real close-ups + measurements. Most 'not as described' complaints are a photo problem, not a product problem.",
    "Fake / Not Genuine": "Post proof of authenticity (invoices, hallmark/certificate, sourcing) in your highlights and product pages today. Nothing kills a small brand faster than a 'fake' accusation left unanswered.",
    "Damaged in Transit": "Upgrade packaging now: bubble wrap + a rigid box for fragile pieces. Add a 'damaged on arrival? send a photo, we replace free' line to every order note.",
    "Late / No Delivery": "Set honest delivery timelines on your page and share tracking automatically. Message anyone waiting proactively — a heads-up before they complain saves the review.",
    "Wrong Item": "Add a scan/double-check step against the order before you seal the parcel. Fix wrong-item orders same day with a free correct shipment.",
    "Poor Packaging": "Invest in branded, protective packaging — for a social brand the unboxing IS the marketing. Even a printed thank-you card lifts repeat orders.",
    "Overpriced": "Don't just cut prices — show the value: material, making, and care in your captions, and offer a first-order or bundle deal instead of a blanket discount.",
    "Return / Refund Issue": "Write a clear, fair return policy and honour refunds fast — a quick refund is far cheaper than a 1-star review that scares off ten buyers.",
    "Poor Customer Service": "Set a reply-within-a-day rule for DMs and comments. Pin an FAQ story so common questions answer themselves and you look responsive.",
    "Sizing Issue": "Publish a real size chart with actual garment measurements and add fit notes ('runs small, size up'). Offer easy size exchanges to stop returns turning into bad reviews.",
    "Other": "Read your 5 most recent negative reviews with fresh eyes and pick one concrete fix to ship this week.",
}

# per-type keyword enrichment for complaints
_TYPE_COMPLAINT_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "jewellery": {
        "Product Quality": ["tarnished", "turned black", "colour came off", "color came off",
                            "plating came off", "stone fell", "stone missing", "chain broke",
                            "clasp broke", "skin turned green", "rusted"],
        "Fake / Not Genuine": ["not real gold", "not real silver", "fake stone", "no hallmark"],
    },
    "clothes": {
        "Product Quality": ["colour bleed", "color bleed", "shrunk", "shrank", "fabric tore",
                            "stitching came off", "thread coming out", "faded after wash",
                            "poor stitching", "cheap fabric"],
        "Sizing Issue": ["size too small", "size too big", "not my size", "wrong size sent"],
    },
    "perfumes": {
        "Product Quality": ["no smell", "faded quickly", "does not last", "doesn't last",
                            "smell gone", "weak fragrance", "cheap smell", "spoilt", "expired"],
        "Fake / Not Genuine": ["fake perfume", "not original scent", "smells cheap", "diluted"],
    },
}


def complaint_lexicon(product_type: str | None) -> dict[str, list[str]]:
    pt = normalize(product_type)
    out: dict[str, list[str]] = {t: list(v) for t, v in COMPLAINT_KEYWORDS.items()}
    for theme, extra in _TYPE_COMPLAINT_KEYWORDS.get(pt, {}).items():
        out.setdefault(theme, [])
        seen = set(out[theme])
        for k in extra:
            if k not in seen:
                out[theme].append(k); seen.add(k)
    return out
