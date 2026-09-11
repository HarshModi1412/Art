"""
Website Builder — each seller gets exactly one storefront.

A site is a small JSON document owned by the seller's account:

    handle      the public address, /s/<handle>
    theme       one of THEMES below — layout + motion + type + colour, not a skin
    style       the seller's overrides (fonts, accent, radius, motion strength)
    hero/story  the editable content blocks
    commerce    shipping fee, free-shipping threshold, GST %, COD

Storage mirrors the rest of the backend: the `sites` table when Supabase is
configured, otherwise the per-account JSON state. The handle -> email index is
the one genuinely global piece — a handle has to be unique across all sellers —
so it lives in the `sites` table, or in data/site_index.json locally.

Products come from Product Management (products.storefront_payload); this module
never keeps its own catalogue.
"""
from __future__ import annotations

import json
import os
import re
import threading

import pandas as pd

from backend.core import auth, db, products, user_store

SITE_KEY = "site_config"
T_SITE = "sites"

_INDEX_PATH = os.path.join(auth.BASE_DIR, "site_index.json")
_lock = threading.Lock()

RESERVED_HANDLES = {
    "app", "smart", "api", "static", "admin", "store", "s", "site", "sites",
    "login", "signup", "privacy", "help", "support", "about", "contact",
    "checkout", "cart", "orders", "account", "generated_images", "smart-static",
    "www", "mail", "blog", "shop", "new", "assets", "public", "health",
}


# =========================================================================
# Fonts offered in the customiser (Google Fonts, loaded on demand)
#
# Curated rather than exhaustive: these are the faces that actually carry the
# look each genre is going for. `kind` groups them in the picker.
# =========================================================================
FONTS = [
    # --- grotesk / neutral UI ---
    {"id": "inter",       "label": "Inter",              "stack": "'Inter', system-ui, sans-serif",              "g": "Inter:wght@300;400;500;600;700;800",             "kind": "grotesk"},
    {"id": "intertight",  "label": "Inter Tight",        "stack": "'Inter Tight', system-ui, sans-serif",        "g": "Inter+Tight:wght@300;400;500;600;700;800",        "kind": "grotesk"},
    {"id": "schibsted",   "label": "Schibsted Grotesk",  "stack": "'Schibsted Grotesk', system-ui, sans-serif",  "g": "Schibsted+Grotesk:wght@400;500;600;700;800",      "kind": "grotesk"},
    {"id": "hostgrotesk", "label": "Host Grotesk",       "stack": "'Host Grotesk', system-ui, sans-serif",       "g": "Host+Grotesk:wght@300;400;500;600;700",           "kind": "grotesk"},
    {"id": "geist",       "label": "Geist",              "stack": "'Geist', system-ui, sans-serif",              "g": "Geist:wght@300;400;500;600;700;800",              "kind": "grotesk"},
    {"id": "manrope",     "label": "Manrope",            "stack": "'Manrope', system-ui, sans-serif",            "g": "Manrope:wght@300;400;500;600;700;800",            "kind": "grotesk"},
    {"id": "dmsans",      "label": "DM Sans",            "stack": "'DM Sans', system-ui, sans-serif",            "g": "DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,700", "kind": "grotesk"},
    {"id": "figtree",     "label": "Figtree",            "stack": "'Figtree', system-ui, sans-serif",            "g": "Figtree:wght@300;400;500;600;700;800",            "kind": "grotesk"},
    {"id": "onest",       "label": "Onest",              "stack": "'Onest', system-ui, sans-serif",              "g": "Onest:wght@300;400;500;600;700;800",              "kind": "grotesk"},
    {"id": "jost",        "label": "Jost",               "stack": "'Jost', system-ui, sans-serif",               "g": "Jost:wght@300;400;500;600;700",                   "kind": "grotesk"},
    {"id": "worksans",    "label": "Work Sans",          "stack": "'Work Sans', system-ui, sans-serif",          "g": "Work+Sans:wght@300;400;500;600;700",              "kind": "grotesk"},
    {"id": "tenorsans",   "label": "Tenor Sans",         "stack": "'Tenor Sans', system-ui, sans-serif",         "g": "Tenor+Sans",                                      "kind": "grotesk"},
    {"id": "instrsans",   "label": "Instrument Sans",    "stack": "'Instrument Sans', system-ui, sans-serif",    "g": "Instrument+Sans:wght@400;500;600;700",            "kind": "grotesk"},

    # --- display / statement ---
    {"id": "archivo",     "label": "Archivo Expanded",   "stack": "'Archivo', system-ui, sans-serif",            "g": "Archivo:wdth,wght@112,600;112,700;125,800;125,900", "kind": "display"},
    {"id": "anton",       "label": "Anton",              "stack": "'Anton', system-ui, sans-serif",              "g": "Anton",                                           "kind": "display"},
    {"id": "bebas",       "label": "Bebas Neue",         "stack": "'Bebas Neue', system-ui, sans-serif",         "g": "Bebas+Neue",                                      "kind": "display"},
    {"id": "syne",        "label": "Syne",               "stack": "'Syne', system-ui, sans-serif",               "g": "Syne:wght@400;600;700;800",                       "kind": "display"},
    {"id": "spacegro",    "label": "Space Grotesk",      "stack": "'Space Grotesk', system-ui, sans-serif",      "g": "Space+Grotesk:wght@400;500;600;700",              "kind": "display"},
    {"id": "bricolage",   "label": "Bricolage Grotesque","stack": "'Bricolage Grotesque', system-ui, sans-serif","g": "Bricolage+Grotesque:opsz,wght@12..96,400;12..96,600;12..96,800", "kind": "display"},
    {"id": "oswald",      "label": "Oswald",             "stack": "'Oswald', system-ui, sans-serif",             "g": "Oswald:wght@400;500;600;700",                     "kind": "display"},
    {"id": "italiana",    "label": "Italiana",           "stack": "'Italiana', Georgia, serif",                  "g": "Italiana",                                        "kind": "display"},

    # --- serif / editorial ---
    {"id": "bodoni",      "label": "Bodoni Moda",        "stack": "'Bodoni Moda', Georgia, serif",               "g": "Bodoni+Moda:opsz,wght@6..96,400;6..96,500;6..96,700", "kind": "serif"},
    {"id": "gloock",      "label": "Gloock",             "stack": "'Gloock', Georgia, serif",                    "g": "Gloock",                                          "kind": "serif"},
    {"id": "instrserif",  "label": "Instrument Serif",   "stack": "'Instrument Serif', Georgia, serif",          "g": "Instrument+Serif:ital@0;1",                       "kind": "serif"},
    {"id": "cormorant",   "label": "Cormorant Garamond", "stack": "'Cormorant Garamond', Georgia, serif",        "g": "Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;1,300;1,400", "kind": "serif"},
    {"id": "prata",       "label": "Prata",              "stack": "'Prata', Georgia, serif",                     "g": "Prata",                                           "kind": "serif"},
    {"id": "playfair",    "label": "Playfair Display",   "stack": "'Playfair Display', Georgia, serif",          "g": "Playfair+Display:ital,wght@0,400;0,500;0,600;0,700;1,400", "kind": "serif"},
    {"id": "fraunces",    "label": "Fraunces",           "stack": "'Fraunces', Georgia, serif",                  "g": "Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700", "kind": "serif"},
    {"id": "youngserif",  "label": "Young Serif",        "stack": "'Young Serif', Georgia, serif",               "g": "Young+Serif",                                     "kind": "serif"},
    {"id": "newsreader",  "label": "Newsreader",         "stack": "'Newsreader', Georgia, serif",                "g": "Newsreader:ital,opsz,wght@0,6..72,300;0,6..72,400;0,6..72,500;1,6..72,300", "kind": "serif"},
    {"id": "librecaslon", "label": "Libre Caslon Display","stack": "'Libre Caslon Display', Georgia, serif",     "g": "Libre+Caslon+Display",                            "kind": "serif"},
    {"id": "marcellus",   "label": "Marcellus",          "stack": "'Marcellus', Georgia, serif",                 "g": "Marcellus",                                       "kind": "serif"},
    {"id": "dmserif",     "label": "DM Serif Display",   "stack": "'DM Serif Display', Georgia, serif",          "g": "DM+Serif+Display",                                "kind": "serif"},
    {"id": "lora",        "label": "Lora",               "stack": "'Lora', Georgia, serif",                      "g": "Lora:ital,wght@0,400;0,500;0,600;1,400",           "kind": "serif"},

    # --- mono ---
    {"id": "jetbrains",   "label": "JetBrains Mono",     "stack": "'JetBrains Mono', ui-monospace, monospace",   "g": "JetBrains+Mono:wght@400;500;700",                 "kind": "mono"},
    {"id": "spacemono",   "label": "Space Mono",         "stack": "'Space Mono', ui-monospace, monospace",       "g": "Space+Mono:wght@400;700",                         "kind": "mono"},
]
FONT_IDS = {f["id"] for f in FONTS}


# ---------------------------------------------------------------------------
# Curated pairings
# ---------------------------------------------------------------------------
# Three free-choice dropdowns across thirty-five families is forty-two thousand
# combinations, most of them bad, offered to someone who did not ask to become
# a typographer. These are the pairings worth having: a display face, the body
# face that sits under it, and the small uppercase face for eyebrows, buttons
# and prices. "Choose your own" stays available behind a link — this is the
# default, not a cage.
PAIRINGS = [
    {"id": "editorial", "name": "Editorial",
     "note": "High-contrast serif over a quiet grotesk. Reads expensive without shouting.",
     "heading": "bodoni", "body": "inter", "accent": "instrsans",
     "suits": ["luxury", "jewellery", "beauty"]},
    {"id": "quiet", "name": "Quiet Modern",
     "note": "One family doing all three jobs at different weights. Never wrong.",
     "heading": "intertight", "body": "inter", "accent": "inter",
     "suits": ["basic", "tech", "fitness"]},
    {"id": "gallery", "name": "Gallery",
     "note": "Wide airy caps over a warm serif. For pieces that photograph well.",
     "heading": "italiana", "body": "newsreader", "accent": "jost",
     "suits": ["jewellery", "luxury", "beauty"]},
    {"id": "counter", "name": "Counter",
     "note": "Friendly geometric with a soft serif body. Approachable, not cute.",
     "heading": "fraunces", "body": "dmsans", "accent": "dmsans",
     "suits": ["cafe", "beauty", "basic"]},
    {"id": "impact", "name": "Impact",
     "note": "Condensed display at full volume over a plain workhorse.",
     "heading": "anton", "body": "worksans", "accent": "archivo",
     "suits": ["fitness", "tech", "fashion"]},
    {"id": "atelier", "name": "Atelier",
     "note": "Old-world serif headings, modern body. The catalogue look.",
     "heading": "playfair", "body": "figtree", "accent": "jost",
     "suits": ["fashion", "luxury", "cafe"]},
    {"id": "studio", "name": "Studio",
     "note": "Sculpted grotesk display with a neutral body. Quietly contemporary.",
     "heading": "bricolage", "body": "schibsted", "accent": "spacegro",
     "suits": ["tech", "basic", "fashion"]},
    {"id": "press", "name": "Press",
     "note": "Newsprint serif with a technical accent face. Good with lots of copy.",
     "heading": "instrserif", "body": "lora", "accent": "spacemono",
     "suits": ["cafe", "basic", "beauty"]},
]


def pairing(pairing_id: str) -> dict | None:
    return next((p for p in PAIRINGS if p["id"] == pairing_id), None)


def pairings_for(theme_id: str = "") -> list[dict]:
    """Every pairing, the ones that suit this theme first — so the recommended
    three sit at the top without hiding the rest."""
    tid = (theme_id or "").strip().lower()
    ranked = sorted(PAIRINGS, key=lambda p: (0 if tid in p.get("suits", []) else 1))
    out = []
    for p in ranked:
        out.append({**p,
                    "recommended": tid in p.get("suits", []),
                    "heading_stack": font(p["heading"])["stack"],
                    "body_stack": font(p["body"])["stack"],
                    "accent_stack": font(p["accent"])["stack"],
                    "google": sorted({font(p["heading"])["g"], font(p["body"])["g"],
                                      font(p["accent"])["g"]})})
    return out


def apply_pairing(site: dict, pairing_id: str) -> dict:
    """Write a pairing into a site's style. Returns the patched style dict."""
    pr = pairing(pairing_id)
    if not pr:
        return site.get("style") or {}
    style = dict(site.get("style") or {})
    style["heading_font"] = pr["heading"]
    style["body_font"] = pr["body"]
    style["accent_font"] = pr["accent"]
    style["pairing"] = pr["id"]
    return style


def font(font_id: str) -> dict:
    return next((f for f in FONTS if f["id"] == font_id), FONTS[0])


# =========================================================================
# Icon set — one source of truth, shipped to both the storefront and the
# builder so a seller picks an icon by name and gets the same drawing in the
# editor as their shoppers get on the site. Paths are drawn on a 24x24 grid
# with a 1.6 stroke and no fill; the renderer supplies the <svg> wrapper.
# =========================================================================
ICONS = {
    # ---- app modules -------------------------------------------------------
    # Drawn on the same 24x24 grid and the same 1.6 stroke as everything below,
    # because the seller app and the storefronts it publishes should not look
    # like two different products.
    "chart": '<path d="M4 20V4"/><path d="M4 20h16"/><path d="M8 16v-5"/>'
             '<path d="M13 16V8"/><path d="M18 16v-3"/>',
    "layers": '<path d="m12 3 8 4.5-8 4.5-8-4.5L12 3Z"/><path d="m4 12.5 8 4.5 8-4.5"/>'
              '<path d="m4 16.5 8 4.5 8-4.5"/>',
    "tag": '<path d="M4 11V4h7l9 9-7 7-9-9Z"/><circle cx="8" cy="8" r="1.4"/>',
    "compass": '<circle cx="12" cy="12" r="8.5"/><path d="m15 9-2 5-4 1 2-5 4-1Z"/>',
    "trend": '<path d="m4 16 5-5 3.5 3.5L20 7"/><path d="M15 7h5v5"/>',
    "receipt": '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Z"/><path d="M9 8h6"/><path d="M9 12h6"/>',
    "edit": '<path d="M4 20h4l10-10-4-4L4 16v4Z"/><path d="m14 6 4 4"/>',
    "bell": '<path d="M6 9a6 6 0 0 1 12 0c0 4 1.5 5.5 1.5 5.5h-15S6 13 6 9Z"/>'
            '<path d="M10 18a2 2 0 0 0 4 0"/>',
    "undo": '<path d="M4 10h9a5 5 0 0 1 0 10h-4"/><path d="m4 10 4-4M4 10l4 4"/>',
    "grid": '<rect x="4" y="4" width="7" height="7" rx="1.2"/>'
            '<rect x="13" y="4" width="7" height="7" rx="1.2"/>'
            '<rect x="4" y="13" width="7" height="7" rx="1.2"/>'
            '<rect x="13" y="13" width="7" height="7" rx="1.2"/>',
    # chrome
    "bag": '<path d="M6 7h12l1 13H5L6 7Z"/><path d="M9 10V6a3 3 0 0 1 6 0v4"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.6-3.6"/>',
    "user": '<circle cx="12" cy="8" r="3.6"/><path d="M5 20c0-3.6 3.1-5.6 7-5.6s7 2 7 5.6"/>',
    "close": '<path d="M6 6 18 18M18 6 6 18"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "minus": '<path d="M5 12h14"/>',
    "check": '<path d="m4.5 12.5 5 5 10-11"/>',
    "arrow-right": '<path d="M4 12h16"/><path d="m14 6 6 6-6 6"/>',
    "arrow-left": '<path d="M20 12H4"/><path d="m10 6-6 6 6 6"/>',
    "arrow-up-right": '<path d="M7 17 17 7"/><path d="M8 7h9v9"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
    # promise strip / product
    "truck": '<path d="M2 7h11v10H2z"/><path d="M13 10h4.5l3.5 3.5V17H13z"/><circle cx="6.5" cy="18.5" r="1.8"/><circle cx="17" cy="18.5" r="1.8"/>',
    "shield": '<path d="M12 3.5 5 6v6c0 4 3 7.2 7 8.5 4-1.3 7-4.5 7-8.5V6l-7-2.5Z"/>',
    "refresh": '<path d="M20 12a8 8 0 1 1-2.6-5.9"/><path d="M20 4v4.5h-4.5"/>',
    "star": '<path d="m12 3.8 2.5 5.3 5.6.8-4 4.1 1 5.8-5.1-2.8-5.1 2.8 1-5.8-4-4.1 5.6-.8L12 3.8Z"/>',
    "leaf": '<path d="M5 19c0-8 5-13 14-13 0 9-5 14-14 13Z"/><path d="M9 15c2-3 4.5-5 8-6.5"/>',
    "spark": '<path d="M12 3v5M12 16v5M3 12h5M16 12h5M6.3 6.3l3.2 3.2M14.5 14.5l3.2 3.2M17.7 6.3l-3.2 3.2M9.5 14.5l-3.2 3.2"/>',
    "lock": '<rect x="5" y="10.5" width="14" height="9.5" rx="2"/><path d="M8.5 10.5V7.8a3.5 3.5 0 0 1 7 0v2.7"/>',
    "gift": '<rect x="3.5" y="9" width="17" height="11" rx="1.5"/><path d="M3.5 13.5h17M12 9v11"/><path d="M12 9C9 9 7.5 8 7.5 6.5S9.5 4.5 12 9Zm0 0c3 0 4.5-1 4.5-2.5S14.5 4.5 12 9Z"/>',
    "clock": '<circle cx="12" cy="12" r="8"/><path d="M12 7.5V12l3 2"/>',
    "credit-card": '<rect x="3" y="6" width="18" height="12" rx="2"/><path d="M3 10.5h18"/>',
    "package": '<path d="m12 3 8 4.2v9.6L12 21l-8-4.2V7.2L12 3Z"/><path d="M4 7.2 12 11.5l8-4.3M12 11.5V21"/>',
    "heart": '<path d="M12 20s-7-4.4-7-9.3A3.8 3.8 0 0 1 12 8a3.8 3.8 0 0 1 7 2.7C19 15.6 12 20 12 20Z"/>',
    "image": '<rect x="3.5" y="5" width="17" height="14" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="m4.5 17 4.6-4.4L13 16l2.8-2.5 3.7 3.4"/>',
    # A reel slot needs a clip, so the empty state needs something that reads
    # as video rather than as another still.
    "play": '<circle cx="12" cy="12" r="8.5"/><path d="M10.2 8.6 16 12l-5.8 3.4V8.6Z"/>',
    "camera": '<path d="M3.5 8.5h3l1.5-2h8l1.5 2h3v10h-17v-10Z"/><circle cx="12" cy="13" r="3.4"/>',
    "map-pin": '<path d="M12 21c4-4.4 6-7.6 6-10a6 6 0 1 0-12 0c0 2.4 2 5.6 6 10Z"/><circle cx="12" cy="11" r="2.2"/>',
    "mail": '<rect x="3" y="5.5" width="18" height="13" rx="2"/><path d="m3.6 7 8.4 6 8.4-6"/>',
    "phone": '<path d="M6 3.8h3.2l1.6 4-2 1.4a11.6 11.6 0 0 0 5 5l1.4-2 4 1.6V17c0 1.7-1.4 3.1-3.1 2.9C9.6 19.2 4.8 14.4 3.9 6.9 3.7 5.2 4.3 3.8 6 3.8Z"/>',
    "instagram": '<rect x="4" y="4" width="16" height="16" rx="4.6"/><circle cx="12" cy="12" r="3.6"/><circle cx="16.8" cy="7.2" r="1"/>',
    "whatsapp": '<path d="M4 20l1.3-4A8 8 0 1 1 8 18.7L4 20Z"/><path d="M9 9.4c.4 2.4 2.2 4.2 4.6 4.6l1-1.3 1.8.8v1.2c0 .6-.5 1.1-1.1 1a7.6 7.6 0 0 1-6.9-6.9c-.1-.6.4-1.1 1-1.1h1.2l.8 1.8-1.4 1"/>',
    "scissors": '<circle cx="6.5" cy="7" r="2.2"/><circle cx="6.5" cy="17" r="2.2"/><path d="M8.4 8.4 19 17M19 7 8.4 15.6"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6 7 7M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4"/>',
    "droplet": '<path d="M12 3.5c3.4 4 5.5 6.7 5.5 9.3a5.5 5.5 0 1 1-11 0c0-2.6 2.1-5.3 5.5-9.3Z"/>',
    "flame": '<path d="M12 21a5.5 5.5 0 0 0 5.5-5.5c0-4-3.5-5.5-3-9.5-2.5 1-4 3.5-4 5.5-1 0-2-1-2-2.5-1.3 1.4-2 3.4-2 6.5A5.5 5.5 0 0 0 12 21Z"/>',
    "globe": '<circle cx="12" cy="12" r="8"/><path d="M4 12h16"/><path d="M12 4c2.2 2.2 3.3 5 3.3 8s-1.1 5.8-3.3 8c-2.2-2.2-3.3-5-3.3-8s1.1-5.8 3.3-8Z"/>',
}
PROMISE_ICONS = ["truck", "shield", "refresh", "leaf", "spark", "lock", "gift",
                 "clock", "credit-card", "package", "heart", "star", "scissors",
                 "sun", "droplet", "flame", "globe", "map-pin", "check"]

# Sites built before the icon set existed stored emoji here. Map the ones we
# shipped onto real icons so an old site heals the moment it is read, and fall
# back to a tick for anything we don't recognise.
_ICON_ALIASES = {
    "🚚": "truck", "🔒": "shield", "↩️": "refresh", "↩": "refresh", "✅": "check",
    "🌿": "leaf", "✨": "spark", "🎁": "gift", "⏱": "clock", "⏰": "clock",
    "💳": "credit-card", "📦": "package", "❤️": "heart", "⭐": "star",
    "🔐": "lock", "🌍": "globe", "📍": "map-pin", "💧": "droplet", "🔥": "flame",
    "☀️": "sun", "✂️": "scissors",
}


def icon_name(raw) -> str:
    """Whatever is stored -> a name the icon set actually draws."""
    v = str(raw or "").strip()
    if v in ICONS:
        return v
    return _ICON_ALIASES.get(v, "check")




# =========================================================================
# Themes.
#
# Each theme is a different storefront, not a recoloured one. Three dials do
# most of that work, in this order of impact:
#
#   layout.radius   0px reads couture, 999px reads friendly
#   feel.dur/ease   slow expo curves read luxury, fast quart curves read sport
#   layout.track    +0.16em on an eyebrow reads couture, +0.06em reads sportswear
#
# Colour and typeface come after those. Palettes below use near-black rather
# than #000 and warm off-white rather than #fff, which is most of the
# difference between "designed" and "default".
#
# motion values the storefront runtime understands:
#   reveal    line-mask rise as a section enters
#   parallax  media moves against the scroll
#   hscroll   horizontal collection rails
#   pin       a section holds while its content advances
#   marquee   continuous ticker band
#   zoom      counter-scaled image inside a clip-path reveal
#   blur      soft blur-in for headings (beauty / jewellery register)
#   magnetic  buttons lean toward the pointer
# =========================================================================
THEMES = [
    {
        "id": "basic", "label": "Studio", "icon": "◻", "genre": "Universal",
        "blurb": "A quiet, confident grid. Generous white space, one strong typeface, nothing competing with the product photograph.",
        "fonts": {"heading": "inter", "body": "inter"},
        "light": {"bg": "#fbfbfa", "surface": "#f2f2f0", "ink": "#111112", "muted": "#6e6e73",
                  "border": "#e4e4e1", "accent": "#1b1b1f", "accent_ink": "#ffffff"},
        "dark":  {"bg": "#0c0c0d", "surface": "#141416", "ink": "#ececed", "muted": "#8b8b90",
                  "border": "#232326", "accent": "#ededef", "accent_ink": "#101012"},
        "layout": {"hero": "split", "grid": "cards", "cta": "solid", "radius": 10,
                   "case": "none", "track": -1, "density": "normal", "grain": 0},
        "motion": ["reveal"],
    },
    {
        "id": "luxury", "label": "Maison", "icon": "◈", "genre": "Luxury / heritage",
        "blurb": "Espresso and champagne, wide margins, a serif that takes its time. Collections move sideways; the hero drifts behind the type.",
        "fonts": {"heading": "cormorant", "body": "worksans"},
        "light": {"bg": "#f7f4ee", "surface": "#efe9de", "ink": "#1a1713", "muted": "#7b7266",
                  "border": "#e2d9ca", "accent": "#8c6f45", "accent_ink": "#ffffff"},
        "dark":  {"bg": "#0b0a09", "surface": "#131110", "ink": "#ede7dc", "muted": "#948b7e",
                  "border": "#241f1a", "accent": "#c9a86b", "accent_ink": "#100e0b"},
        "layout": {"hero": "full", "grid": "editorial", "cta": "outline", "radius": 0,
                   "case": "upper", "track": 12, "density": "airy", "grain": 0.05},
        "motion": ["reveal", "parallax", "hscroll", "zoom", "split"],
    },
    {
        "id": "fitness", "label": "Charge", "icon": "◤", "genre": "Sport / supplements",
        "blurb": "Carbon black and a green that shouts. Headlines set solid, a claims band that never stops moving, sections that lock as you scroll.",
        "fonts": {"heading": "bebas", "body": "manrope"},
        "light": {"bg": "#f4f4f5", "surface": "#ffffff", "ink": "#0d0e11", "muted": "#62656e",
                  "border": "#e3e4e8", "accent": "#12704a", "accent_ink": "#ffffff"},
        "dark":  {"bg": "#08090b", "surface": "#101216", "ink": "#f0f2f5", "muted": "#8a8f99",
                  "border": "#1e2127", "accent": "#46e08a", "accent_ink": "#06110a"},
        "layout": {"hero": "full", "grid": "cards", "cta": "solid", "radius": 4,
                   "case": "upper", "track": 2, "density": "tight", "grain": 0},
        "motion": ["reveal", "parallax", "marquee", "pin", "split"],
    },
    {
        "id": "fashion", "label": "Atelier", "icon": "▤", "genre": "Apparel / lookbook",
        "blurb": "Bone and ink. Full-bleed photography, a lookbook that scrolls sideways, images that uncover themselves as they arrive.",
        "fonts": {"heading": "syne", "body": "dmsans"},
        "light": {"bg": "#f8f7f5", "surface": "#ffffff", "ink": "#101012", "muted": "#6d6d72",
                  "border": "#e8e6e2", "accent": "#101012", "accent_ink": "#ffffff"},
        "dark":  {"bg": "#0b0b0c", "surface": "#131314", "ink": "#f0efed", "muted": "#8c8c92",
                  "border": "#232325", "accent": "#f0efed", "accent_ink": "#0f0f10"},
        "layout": {"hero": "full", "grid": "editorial", "cta": "outline", "radius": 0,
                   "case": "upper", "track": 6, "density": "airy", "grain": 0.04},
        "motion": ["reveal", "hscroll", "zoom", "split", "mask"],
    },
    {
        "id": "jewellery", "label": "Lustre", "icon": "◇", "genre": "Fine jewellery",
        "blurb": "Pearl grounds and antique gold. Small things photographed enormous, a slow carousel, and a shine that crosses each piece as you pass it.",
        "fonts": {"heading": "marcellus", "body": "worksans"},
        "light": {"bg": "#fbf9f5", "surface": "#ffffff", "ink": "#191713", "muted": "#7d746a",
                  "border": "#ece4d7", "accent": "#9a7b45", "accent_ink": "#ffffff"},
        "dark":  {"bg": "#0d0c0a", "surface": "#16140f", "ink": "#f0eae0", "muted": "#9b9286",
                  "border": "#262119", "accent": "#d9bb7c", "accent_ink": "#14110c"},
        "layout": {"hero": "split", "grid": "editorial", "cta": "outline", "radius": 2,
                   "case": "upper", "track": 14, "density": "airy", "grain": 0.03},
        "motion": ["reveal", "hscroll", "zoom", "parallax", "shine", "split"],
    },
    {
        "id": "cafe", "label": "Counter", "icon": "◐", "genre": "Food & drink",
        "blurb": "Cream paper and burnt orange. Prices set like a board behind the counter, categories on rails, warmth over polish.",
        "fonts": {"heading": "fraunces", "body": "worksans"},
        "light": {"bg": "#fcf8f1", "surface": "#ffffff", "ink": "#1e1810", "muted": "#7b7164",
                  "border": "#eee3d1", "accent": "#a9541f", "accent_ink": "#ffffff"},
        "dark":  {"bg": "#100e0b", "surface": "#1a1712", "ink": "#f2ebe0", "muted": "#9c9287",
                  "border": "#2a241c", "accent": "#e8874a", "accent_ink": "#150d07"},
        "layout": {"hero": "split", "grid": "list", "cta": "solid", "radius": 16,
                   "case": "none", "track": -1, "density": "normal", "grain": 0.04},
        "motion": ["reveal", "hscroll"],
    },
    {
        "id": "beauty", "label": "Bloom", "icon": "○", "genre": "Beauty / skincare",
        "blurb": "Blush grounds with plum accents and soft gradients that drift behind the hero. Ingredients called out under every product.",
        "fonts": {"heading": "playfair", "body": "manrope"},
        "light": {"bg": "#fcf7f6", "surface": "#ffffff", "ink": "#1c1719", "muted": "#7c7173",
                  "border": "#f2e5e3", "accent": "#9d5f74", "accent_ink": "#ffffff"},
        "dark":  {"bg": "#100d0f", "surface": "#191517", "ink": "#f2eaec", "muted": "#9a8f92",
                  "border": "#2a2226", "accent": "#e3a5b7", "accent_ink": "#171013"},
        "layout": {"hero": "split", "grid": "cards", "cta": "solid", "radius": 22,
                   "case": "none", "track": -1, "density": "airy", "grain": 0},
        "motion": ["reveal", "parallax", "zoom", "drift"],
    },
    {
        "id": "tech", "label": "Obsidian", "icon": "◼", "genre": "Electronics",
        "blurb": "A spec sheet with taste. Ice blue on near-black, feature sections that pin while their detail scrolls, hard numbers under every product.",
        "fonts": {"heading": "spacegro", "body": "inter"},
        "light": {"bg": "#f4f5f7", "surface": "#ffffff", "ink": "#0e1015", "muted": "#626775",
                  "border": "#e4e6ec", "accent": "#2b5fa8", "accent_ink": "#ffffff"},
        "dark":  {"bg": "#07080b", "surface": "#0f1116", "ink": "#e9ebf0", "muted": "#868c99",
                  "border": "#1c1f26", "accent": "#6ea8f5", "accent_ink": "#060a12"},
        "layout": {"hero": "full", "grid": "cards", "cta": "solid", "radius": 8,
                   "case": "none", "track": -2, "density": "tight", "grain": 0},
        "motion": ["reveal", "pin", "parallax", "marquee"],
    },
]
THEME_IDS = {t["id"] for t in THEMES}

# How a theme *moves*. Each theme may override any of these; the resolver falls
# back here so adding a theme never means remembering every knob.
DEFAULT_FEEL = {"grain": 0.0, "dur": 1.0, "ease": "expo"}

# easing curves the storefront can be handed
EASES = {
    "expo":  "cubic-bezier(0.16, 1, 0.30, 1)",
    "quart": "cubic-bezier(0.25, 1, 0.50, 1)",
    "back":  "cubic-bezier(0.34, 1.56, 0.64, 1)",
}


def theme(theme_id: str) -> dict:
    return next((t for t in THEMES if t["id"] == theme_id), THEMES[0])


def theme_catalog() -> list[dict]:
    """What the theme picker shows."""
    return [{
        "id": t["id"], "label": t["label"], "icon": t["icon"], "genre": t["genre"],
        "blurb": t["blurb"], "motion": t["motion"],
        "feel": {**DEFAULT_FEEL, **(t.get("feel") or {})},
        "fonts": t["fonts"], "light": t["light"], "dark": t["dark"], "layout": t["layout"],
        "prefers_dark": bool(t.get("prefers_dark")),
    } for t in THEMES]


# =========================================================================
# handle index (global — a handle must be unique across all sellers)
# =========================================================================
def _read_index() -> dict:
    try:
        with open(_INDEX_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_index(idx: dict) -> None:
    try:
        os.makedirs(os.path.dirname(_INDEX_PATH), exist_ok=True)
        tmp = _INDEX_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(idx, f, indent=2)
        os.replace(tmp, _INDEX_PATH)
    except OSError:
        pass


def normalise_handle(raw: str) -> str:
    h = re.sub(r"[^a-z0-9-]", "-", (raw or "").strip().lower())
    h = re.sub(r"-{2,}", "-", h).strip("-")
    return h[:40]


def handle_available(handle: str, for_email: str = "") -> bool:
    h = normalise_handle(handle)
    if not h or h in RESERVED_HANDLES or len(h) < 3:
        return False
    owner = resolve_handle(h)
    return owner is None or owner == (for_email or "").strip().lower()


def resolve_handle(handle: str) -> str | None:
    """Which seller owns this handle, or None."""
    h = normalise_handle(handle)
    if not h:
        return None
    if db.SUPABASE_ENABLED:
        try:
            row = db.fetch_one(T_SITE, {"handle": h})
            if row:
                return (row.get("email") or "").strip().lower() or None
        except Exception:  # noqa: BLE001 - table may not exist yet
            pass
    with _lock:
        return _read_index().get(h)


def _claim_handle(handle: str, email: str, previous: str = "") -> None:
    h, email = normalise_handle(handle), (email or "").strip().lower()
    with _lock:
        idx = _read_index()
        if previous and previous != h and idx.get(previous) == email:
            idx.pop(previous, None)
        idx[h] = email
        _write_index(idx)


def suggest_handle(brand: str, email: str) -> str:
    # NOTE: deliberately no email fallback. The handle is the public web address
    # of the shop (/s/<handle>), so falling back to the email local part put the
    # seller's personal handle on every product URL they ever shared. A generic
    # "my-store" that they rename is embarrassing for a minute; a URL carrying
    # their email handle is permanent once customers have the link.
    base = normalise_handle(brand) or "my-store"
    if len(base) < 3:
        base = f"{base}-store"
    if handle_available(base, email):
        return base
    for n in range(2, 60):
        cand = f"{base}-{n}"
        if handle_available(cand, email):
            return cand
    return f"{base}-{os.urandom(2).hex()}"


# =========================================================================
# site document
# =========================================================================
def _now() -> str:
    return pd.Timestamp.now().isoformat(timespec="seconds")


def _f(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _b(v, default=False) -> bool:
    if v is None or v == "":
        return default
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("1", "true", "yes", "on", "y")


def default_site(email: str) -> dict:
    t = theme("basic")
    return {
        "handle": "",
        "brand": "",
        # A line or two in the seller's own words about the shop — what the
        # content writer builds every other piece of site copy from.
        "brief": "",
        "tagline": "",
        "logo_url": "",
        "published": False,
        "theme": "basic",
        "style": {
            "accent": "", "accent_dark": "",         # blank = use the theme's own
            "mode": "auto",                          # auto | light | dark
            # three type roles: display headings, body copy, and the small
            # uppercase UI text (eyebrows, buttons, prices)
            "heading_font": "", "body_font": "", "accent_font": "",
            "heading_weight": None,                  # 300-900, None = theme default
            "heading_track": None,                   # letter-spacing, hundredths of an em
            "heading_scale": None,                   # 80-140 (% of the theme's display size)
            "body_scale": None,                      # 90-115
            "radius": None,                          # None = theme default
            "motion": "full",                        # full | subtle | none
            "preloader": True,                       # brand curtain on first load
            "card_style": "",                        # blank = theme default
            "cols": None,                            # products per row, None = theme default
            "grain": None,                           # film grain strength, None = theme default
            "width": "wide",                         # wide | compact | full
            "pairing": "",                           # id of a curated font pairing
        },
        "hero": {
            "image_url": "", "video_url": "", "heading": "", "sub": "",
            "cta_text": "Shop now", "overlay": 45, "align": "left",
        },
        # Every fixed label on the page, so nothing on the site is text the
        # seller cannot change.
        "copy": {
            "cat_eyebrow": "Browse",       "cat_title": "Shop by category",
            "feat_eyebrow": "Handpicked",  "feat_title": "Featured",
            "all_eyebrow": "Catalogue",    "all_title": "All products",
            "story_eyebrow": "About us",
            "rev_eyebrow": "Reviews",      "rev_title": "What buyers say",
            "news_title": "Stay in the loop",
            "news_sub": "New drops and offers. No spam, ever.",
            "news_cta": "Join",
            "stats_eyebrow": "By the numbers",
            "drop_eyebrow": "Limited",     "drop_title": "When it's gone, it's gone",
            "gallery_eyebrow": "Lookbook", "gallery_title": "In the wild",
            "shop_title": "Everything we sell",
        },
        # Count-up figures. Blank ones are simply not rendered.
        "stats": [
            {"value": "", "label": ""},
            {"value": "", "label": ""},
            {"value": "", "label": ""},
        ],
        "gallery": [],          # lookbook images / clips
        "manifesto": "",        # the scrubbed, word-by-word statement
        "sections": {
            "featured": True, "categories": True, "story": True,
            "highlights": True, "testimonials": False, "newsletter": False,
            "stats": False, "drop": False, "gallery": False,
            "manifesto": False, "spotlight": True,
        },
        "story": {"title": "Our story", "body": "", "image_url": ""},
        "highlights": [
            {"icon": "truck", "title": "Fast dispatch", "text": "Orders leave within 24 hours."},
            {"icon": "shield", "title": "Secure checkout", "text": "Your details stay with us, never resold."},
            {"icon": "refresh", "title": "Easy returns", "text": "7-day no-questions returns."},
        ],
        "testimonials": [],
        "announcement": "",
        "contact": {"email": email, "phone": "", "whatsapp": "", "address": "", "instagram": ""},
        "commerce": {
            "currency": "INR",
            "shipping_fee": 49.0,
            "free_shipping_above": 999.0,
            "gst_percent": 0.0,
            "gst_inclusive": True,
            "cod_enabled": True,
            "order_note": "We'll call to confirm your order before dispatch.",
            "min_order": 0.0,
            # Online payment, into the seller's OWN Razorpay account.
            "online_enabled": False,
            # A flat advance a cash-on-delivery shopper pays online to confirm.
            # 0 = plain COD. This is the cheapest lever a small Indian seller
            # has against return-to-origin, which runs ~26% on COD.
            "cod_advance": 0.0,
        },
        "policies": {"shipping": "", "returns": "", "privacy": ""},
        # What a pasted link shows in WhatsApp, and what a search engine reads.
        # Blank fields fall back to the brand, tagline and hero image, so a
        # seller never has to fill this in to get a decent card.
        "seo": {"title": "", "description": "", "og_image": "", "keywords": ""},
        # Legal / trust block shown at checkout. Indian shoppers buying from a
        # brand they have never heard of need this more than they would on a
        # marketplace, not less.
        "trust": {
            "business_name": "", "gstin": "", "address": "",
            "support_phone": "", "support_email": email,
            "returns_days": 7, "dispatch_days": 2,
            "show": True,
        },
        "seeded": False,
        "published_at": "",
        "created_at": _now(),
        "updated_at": _now(),
    }


def _merge(base: dict, incoming: dict) -> dict:
    """One level of nested-dict merge — enough for this document shape."""
    out = dict(base)
    for k, v in (incoming or {}).items():
        if k not in base:
            continue
        if isinstance(base[k], dict) and isinstance(v, dict):
            out[k] = {**base[k], **{ik: iv for ik, iv in v.items() if ik in base[k]}}
        else:
            out[k] = v
    return out


def get_site(email: str) -> dict:
    email = (email or "").strip().lower()
    raw = None
    if db.SUPABASE_ENABLED:
        try:
            row = db.fetch_one(T_SITE, {"email": email})
            if row:
                raw = row.get("config")
                if isinstance(raw, str):
                    raw = json.loads(raw)
        except Exception:  # noqa: BLE001
            raw = None
    if raw is None:
        raw = user_store.get_key(email, SITE_KEY, None)
    site = _merge(default_site(email), raw or {})
    if site["theme"] not in THEME_IDS:
        site["theme"] = "basic"
    for h in site.get("highlights") or []:
        if isinstance(h, dict):
            h["icon"] = icon_name(h.get("icon"))
    return site


def save_site(email: str, patch: dict) -> dict:
    email = (email or "").strip().lower()
    current = get_site(email)
    previous_handle = current.get("handle") or ""
    site = _merge(current, patch or {})

    site["brand"] = str(site.get("brand") or "").strip()[:80]
    site["tagline"] = str(site.get("tagline") or "").strip()[:160]
    site["brief"] = str(site.get("brief") or "").strip()[:1200]
    site["announcement"] = str(site.get("announcement") or "").strip()[:200]
    if site["theme"] not in THEME_IDS:
        site["theme"] = "basic"

    # ---- handle ----
    wanted = normalise_handle(site.get("handle") or "")
    if not wanted:
        wanted = suggest_handle(site["brand"] or "my-store", email)
    if wanted != previous_handle and not handle_available(wanted, email):
        raise ValueError(f"The address “{wanted}” is already taken — try another.")
    if wanted in RESERVED_HANDLES or len(wanted) < 3:
        raise ValueError("Pick an address of at least 3 letters that isn't a reserved word.")
    site["handle"] = wanted

    # ---- style ----
    st = site["style"]
    st["mode"] = st.get("mode") if st.get("mode") in ("auto", "light", "dark") else "auto"
    st["motion"] = st.get("motion") if st.get("motion") in ("full", "subtle", "none") else "full"
    # A pairing is a shorthand for the three faces: naming one writes all three,
    # and choosing a face by hand afterwards simply clears the pairing label.
    if st.get("pairing") and pairing(st["pairing"]):
        pr = pairing(st["pairing"])
        if (patch or {}).get("style", {}).get("pairing"):
            st["heading_font"], st["body_font"], st["accent_font"] = \
                pr["heading"], pr["body"], pr["accent"]
    for k in ("heading_font", "body_font", "accent_font"):
        if st.get(k) and st[k] not in FONT_IDS:
            st[k] = ""
    if st.get("pairing") and not pairing(st["pairing"]):
        st["pairing"] = ""
    chosen = (st.get("heading_font"), st.get("body_font"), st.get("accent_font"))
    if st.get("pairing"):
        pr = pairing(st["pairing"])
        if chosen != (pr["heading"], pr["body"], pr["accent"]):
            st["pairing"] = ""      # they have since hand-picked a face
    st["preloader"] = _b(st.get("preloader"), True)
    if st.get("width") not in ("wide", "compact", "full"):
        st["width"] = "wide"
    for k, lo, hi in (("heading_weight", 300, 900), ("heading_track", -8, 30),
                      ("heading_scale", 75, 145), ("body_scale", 88, 118)):
        if st.get(k) in (None, ""):
            st[k] = None
        else:
            try:
                st[k] = max(lo, min(hi, int(float(st[k]))))
            except (TypeError, ValueError):
                st[k] = None
    for k in ("accent", "accent_dark"):
        v = str(st.get(k) or "").strip()
        st[k] = v if re.fullmatch(r"#[0-9a-fA-F]{6}", v) else ""
    if st.get("radius") not in (None, ""):
        try:
            st["radius"] = max(0, min(32, int(float(st["radius"]))))
        except (TypeError, ValueError):
            st["radius"] = None
    if st.get("card_style") not in ("", "cards", "editorial", "list"):
        st["card_style"] = ""
    if st.get("cols") not in (None, ""):
        try:
            st["cols"] = max(2, min(5, int(float(st["cols"]))))
        except (TypeError, ValueError):
            st["cols"] = None
    if st.get("grain") not in (None, ""):
        try:
            st["grain"] = max(0.0, min(0.12, round(float(st["grain"]), 3)))
        except (TypeError, ValueError):
            st["grain"] = None

    # ---- hero ----
    site["hero"]["heading"] = str(site["hero"].get("heading") or "").strip()[:120]
    site["hero"]["sub"] = str(site["hero"].get("sub") or "").strip()[:240]
    site["hero"]["cta_text"] = str(site["hero"].get("cta_text") or "Shop now").strip()[:30] or "Shop now"
    site["hero"]["align"] = site["hero"].get("align") if site["hero"].get("align") in ("left", "center") else "left"
    try:
        site["hero"]["overlay"] = max(0, min(90, int(float(site["hero"].get("overlay", 45)))))
    except (TypeError, ValueError):
        site["hero"]["overlay"] = 45

    # ---- sections / blocks ----
    site["sections"] = {k: _b(v, True) for k, v in site["sections"].items()}
    site["highlights"] = [
        {"icon": icon_name(h.get("icon")),
         "title": str(h.get("title") or "").strip()[:60],
         "text": str(h.get("text") or "").strip()[:160]}
        for h in (site.get("highlights") or [])[:6] if isinstance(h, dict)
    ]
    site["copy"] = {k: str(v or "").strip()[:120] for k, v in (site.get("copy") or {}).items()}
    site["manifesto"] = str(site.get("manifesto") or "").strip()[:400]
    site["stats"] = [
        {"value": str(x.get("value") or "").strip()[:12],
         "label": str(x.get("label") or "").strip()[:40]}
        for x in (site.get("stats") or [])[:4] if isinstance(x, dict)
    ]
    site["gallery"] = [
        {"url": str(x.get("url") or "").strip()[:500],
         "caption": str(x.get("caption") or "").strip()[:80]}
        for x in (site.get("gallery") or [])[:12]
        if isinstance(x, dict) and str(x.get("url") or "").strip()
    ]
    site["hero"]["video_url"] = str(site["hero"].get("video_url") or "").strip()[:500]

    site["testimonials"] = [
        {"name": str(t.get("name") or "").strip()[:60],
         "text": str(t.get("text") or "").strip()[:300],
         "rating": max(1, min(5, int(_f(t.get("rating"), 5))))}
        for t in (site.get("testimonials") or [])[:8] if isinstance(t, dict)
    ]

    # ---- commerce ----
    c = site["commerce"]
    c["shipping_fee"] = max(0.0, round(_f(c.get("shipping_fee"), 0), 2))
    c["free_shipping_above"] = max(0.0, round(_f(c.get("free_shipping_above"), 0), 2))
    c["gst_percent"] = max(0.0, min(28.0, round(_f(c.get("gst_percent"), 0), 2)))
    c["min_order"] = max(0.0, round(_f(c.get("min_order"), 0), 2))
    c["cod_enabled"] = _b(c.get("cod_enabled"), True)
    c["online_enabled"] = _b(c.get("online_enabled"), False)
    c["cod_advance"] = max(0.0, round(_f(c.get("cod_advance"), 0), 2))
    c["gst_inclusive"] = _b(c.get("gst_inclusive"), True)
    c["currency"] = "INR"
    c["order_note"] = str(c.get("order_note") or "").strip()[:200]

    # ---- link previews ----
    seo = site.get("seo") or {}
    site["seo"] = {
        "title": str(seo.get("title") or "").strip()[:120],
        "description": " ".join(str(seo.get("description") or "").split())[:300],
        "og_image": str(seo.get("og_image") or "").strip()[:500],
        "keywords": str(seo.get("keywords") or "").strip()[:300],
    }

    # ---- checkout trust block ----
    tr = site.get("trust") or {}
    site["trust"] = {
        "business_name": str(tr.get("business_name") or "").strip()[:120],
        "gstin": str(tr.get("gstin") or "").strip().upper()[:20],
        "address": str(tr.get("address") or "").strip()[:300],
        "support_phone": re.sub(r"[^0-9+ ]", "", str(tr.get("support_phone") or ""))[:20],
        "support_email": str(tr.get("support_email") or "").strip()[:120],
        "returns_days": max(0, min(90, int(_f(tr.get("returns_days"), 7)))),
        "dispatch_days": max(0, min(30, int(_f(tr.get("dispatch_days"), 2)))),
        "show": _b(tr.get("show"), True),
    }
    site["seeded"] = _b(site.get("seeded"), False)
    site["published_at"] = str(site.get("published_at") or "")[:40]

    site["published"] = _b(site.get("published"), False)
    site["updated_at"] = _now()

    _persist(email, site)
    _claim_handle(site["handle"], email, previous_handle)
    return site


def _persist(email: str, site: dict) -> None:
    user_store.set_key(email, SITE_KEY, site)
    if db.SUPABASE_ENABLED:
        try:
            db.upsert(T_SITE, {
                "email": email, "handle": site["handle"],
                "published": bool(site["published"]),
                "config": site, "updated_at": site["updated_at"],
            }, on_conflict="email")
        except Exception:  # noqa: BLE001 - run supabase/site.sql to enable
            import logging
            logging.getLogger("sitebuilder").warning(
                "site upsert failed — run supabase/site.sql; using JSON state.")


def set_published(email: str, published: bool) -> dict:
    site = get_site(email)
    if published and not site.get("handle"):
        raise ValueError("Give your site an address before publishing it.")
    if published and not site.get("brand"):
        raise ValueError("Give your site a brand name before publishing it.")
    site["published"] = bool(published)
    site["updated_at"] = _now()
    # Stamped so the builder can tell "saved" from "saved AND live" — a saved
    # edit on a published site is not live until Publish is pressed again, and
    # nothing on screen used to say so.
    if published:
        site["published_at"] = site["updated_at"]
    _persist(email, site)
    return site


# =========================================================================
# public payload — what the storefront renders from
# =========================================================================
def resolved_style(site: dict) -> dict:
    """Theme defaults with the seller's overrides applied.

    Everything the storefront needs is final by the time it leaves here — the
    page turns this straight into CSS custom properties and never has to know
    which parts came from the theme and which from the seller.
    """
    t = theme(site.get("theme"))
    st = site.get("style") or {}
    light = dict(t["light"])
    dark = dict(t["dark"])
    if st.get("accent"):
        light["accent"] = st["accent"]
        light["accent_soft"] = _tint(st["accent"], light["bg"], 0.12)
        light["accent_ink"] = _readable_on(st["accent"])
    if st.get("accent_dark"):
        dark["accent"] = st["accent_dark"]
        dark["accent_soft"] = _tint(st["accent_dark"], dark["bg"], 0.16)
        dark["accent_ink"] = _readable_on(st["accent_dark"])
    elif st.get("accent"):
        dark["accent"] = st["accent"]
        dark["accent_soft"] = _tint(st["accent"], dark["bg"], 0.16)
        dark["accent_ink"] = _readable_on(st["accent"])

    layout = dict(t["layout"])
    if st.get("radius") not in (None, ""):
        r = int(st["radius"])
        layout["radius"] = r
        layout["radius_btn"] = r
        layout["radius_badge"] = 999 if r >= 24 else r
    if st.get("card_style"):
        layout["grid"] = st["card_style"]
    if st.get("cols") not in (None, ""):
        layout["cols"] = max(2, min(5, int(st["cols"])))

    heading = font(st.get("heading_font") or t["fonts"]["heading"])
    body = font(st.get("body_font") or t["fonts"]["body"])
    accent_face = font(st.get("accent_font")
                       or (t.get("fonts") or {}).get("accent")
                       or t["fonts"]["body"])
    type_scale = {
        "heading_weight": st.get("heading_weight"),
        "heading_track": st["heading_track"] if st.get("heading_track") not in (None, "") else layout.get("track", 0),
        "heading_scale": st.get("heading_scale") or 100,
        "body_scale": st.get("body_scale") or 100,
    }

    feel = {**DEFAULT_FEEL, **(t.get("feel") or {})}
    # a theme may carry its grain on the layout block instead
    if t.get("layout", {}).get("grain") is not None:
        feel["grain"] = t["layout"]["grain"]
    motion = list(t["motion"])
    if st.get("motion") == "none":
        motion = []
        feel["grain"] = 0.0
    elif st.get("motion") == "subtle":
        motion = [m for m in motion if m in ("reveal", "hscroll", "shine")]
        feel["dur"] = min(feel["dur"], 1.0)
    if st.get("grain") not in (None, ""):
        try:
            feel["grain"] = max(0.0, min(0.12, float(st["grain"])))
        except (TypeError, ValueError):
            pass

    mode = st.get("mode") or "auto"
    return {
        "theme": t["id"],
        "light": light, "dark": dark, "layout": layout,
        "motion": motion, "feel": feel,
        "ease": EASES.get(feel.get("ease", "expo"), EASES["expo"]),
        "mode": mode,
        "prefers_dark": bool(t.get("prefers_dark")) and mode == "auto",
        "width": st.get("width") or "wide",
        "heading_font": heading, "body_font": body, "accent_font": accent_face,
        "type": type_scale,
        "preloader": bool(st.get("preloader", True)),
        "google_fonts": sorted({heading["g"], body["g"], accent_face["g"]}),
    }


def _hex(c: str) -> tuple[int, int, int]:
    c = (c or "#000000").lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    try:
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    except ValueError:
        return 0, 0, 0


def _tint(colour: str, ground: str, amount: float) -> str:
    """Mix `amount` of the accent into the page ground — the soft wash used for
    badges and hover fills. Computed here so a custom accent gets a matching
    soft tint instead of keeping the theme's original one."""
    r1, g1, b1 = _hex(colour)
    r2, g2, b2 = _hex(ground)
    mix = lambda a, b: round(b + (a - b) * amount)  # noqa: E731
    return "#%02x%02x%02x" % (mix(r1, r2), mix(g1, g2), mix(b1, b2))


def _readable_on(colour: str) -> str:
    """Black or white text on a chosen accent, whichever actually reads."""
    r, g, b = _hex(colour)
    lin = lambda v: (v / 255) ** 2.2  # noqa: E731 - close enough for a UI choice
    lum = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
    return "#12100e" if lum > 0.32 else "#ffffff"


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------
# The brand, the products, the photos and the copy already exist in Product
# Management by the time a seller opens the builder. Opening on five steps of
# blank fields therefore asks them to type things the app already knows. This
# fills the document from what is there, once, so step three opens on a
# finished site they edit — the difference between "build me a website" and
# "here is your website".
_SEED_HEROES = {
    "jewellery": ("Made to be kept", "Pieces finished by hand, in small numbers."),
    "clothes":   ("Made to be worn out", "Cut, sewn and checked before it ships."),
    "fashion":   ("Made to be worn out", "Cut, sewn and checked before it ships."),
    "perfumes":  ("Scent that stays with you", "Small batches, rested before bottling."),
    "beauty":    ("Honest formulas", "Short ingredient lists, nothing you cannot pronounce."),
    "cafe":      ("Made this morning", "Small batches, gone by evening."),
    "tech":      ("Built to last a decade", "Repairable, documented, no surprises."),
    "fitness":   ("Show up. Repeat.", "Kit that survives the sessions you plan to do."),
}


def seed_from_catalogue(email: str, force: bool = False) -> dict:
    """Fill an untouched site from the seller's real catalogue.

    Only ever writes into fields the seller has left blank, and only when the
    site has not been seeded before — so re-entering the builder can never
    overwrite something they wrote themselves. Returns the site.
    """
    site = get_site(email)
    if site.get("seeded") and not force:
        return site

    items = products.listed_products(email)
    patch: dict = {}

    brand = (site.get("brand") or "").strip()
    if not brand:
        # GATE 1: this line used to build a brand out of the email local part and
        # SAVE it, which is how "sunshine.creations1214" ended up printed on
        # storefronts and in win-back emails. A neutral placeholder is used
        # instead, and `brand_placeholder` tells the UI to ask for the real one.
        brand = "My store"
        patch["brand"] = brand
        patch["brand_placeholder"] = True
    if not (site.get("handle") or "").strip():
        patch["handle"] = suggest_handle(brand, email)

    ptype = ""
    try:
        from backend.core import smart
        ptype = (smart.get_product_type(email) or "").strip().lower()
    except Exception:  # noqa: BLE001
        ptype = ""
    head, sub = _SEED_HEROES.get(ptype) or _SEED_HEROES.get(site.get("theme") or "") or \
        ("Everything we make, in one place", "Browse the full range and order in a few taps.")

    hero = dict(site.get("hero") or {})
    hero_patch = {}
    if not (hero.get("heading") or "").strip():
        hero_patch["heading"] = head
    if not (hero.get("sub") or "").strip():
        hero_patch["sub"] = sub
    if not (hero.get("image_url") or "").strip():
        # the first listed product photo beats an empty hero every time
        shot = next((p.get("image_url") for p in items if p.get("image_url")), "")
        if shot:
            hero_patch["image_url"] = shot
    if hero_patch:
        patch["hero"] = hero_patch

    story = dict(site.get("story") or {})
    if not (story.get("body") or "").strip():
        n = len(items)
        cats = sorted({(p.get("category") or "").strip() for p in items if p.get("category")})
        made = (", ".join(cats[:3]) + " and more") if len(cats) > 3 else ", ".join(cats)
        patch["story"] = {
            "title": story.get("title") or "Our story",
            "body": (f"We are {brand}. We make {made.lower()} " if made else f"We are {brand}. We make things ") +
                    (f"— {n} of them are listed here right now. " if n else "— the range is growing. ") +
                    "Every order is packed by the same people who made it, and we answer our own phone.",
            "image_url": story.get("image_url") or "",
        }

    if not (site.get("tagline") or "").strip():
        patch["tagline"] = sub

    if not (site.get("announcement") or "").strip():
        c = site.get("commerce") or {}
        above = _f(c.get("free_shipping_above"))
        if above:
            patch["announcement"] = f"Free shipping over ₹{above:,.0f} · Dispatched within 24 hours"

    # a pairing that matches the theme beats three empty font dropdowns
    style = dict(site.get("style") or {})
    if not (style.get("heading_font") or style.get("pairing")):
        best = next((p for p in pairings_for(site.get("theme") or "") if p["recommended"]), None)
        if best:
            patch["style"] = {**apply_pairing(site, best["id"])}

    trust = dict(site.get("trust") or {})
    if not (trust.get("business_name") or "").strip():
        patch["trust"] = {**trust, "business_name": brand,
                          "support_email": trust.get("support_email") or email}

    patch["seeded"] = True
    return save_site(email, patch)


def seo_meta(handle: str, site: dict, product: dict | None = None) -> dict:
    """The tags that decide whether a pasted link becomes a card or grey text.

    Every page falls back to the brand's own words, so a seller who never opens
    the SEO fields still gets a real preview in WhatsApp.
    """
    seo = site.get("seo") or {}
    brand = (site.get("brand") or handle or "Store").strip()
    hero = site.get("hero") or {}
    if product:
        title = f"{product.get('name')} — {brand}"
        desc = (product.get("description") or "").strip() or \
            (f"{product.get('name')} from {brand}." +
             (f" ₹{float(product['price']):,.0f}." if product.get("price") else ""))
        image = product.get("image_url") or seo.get("og_image") or hero.get("image_url") or ""
    else:
        title = (seo.get("title") or "").strip() or \
            (f"{brand} — {site.get('tagline')}" if site.get("tagline") else brand)
        desc = (seo.get("description") or "").strip() or \
            (site.get("tagline") or hero.get("sub") or
             f"Shop {brand}. Ordering takes a few taps.")
        image = seo.get("og_image") or hero.get("image_url") or site.get("logo_url") or ""
    return {
        "title": title[:120],
        "description": " ".join(str(desc).split())[:300],
        "image": image,
        "site_name": brand,
        "keywords": (seo.get("keywords") or "").strip()[:300],
    }


def public_site(handle: str) -> dict | None:
    """Everything the storefront needs for one seller, or None when the handle
    is unknown or the site is not published."""
    owner = resolve_handle(handle)
    if not owner:
        return None
    site = get_site(owner)
    if not site.get("published"):
        return None
    return _payload(owner, site)


def preview_site(email: str) -> dict:
    """Same payload for the owner, published or not — powers the live preview."""
    return _payload(email, get_site(email))


def _payload(email: str, site: dict) -> dict:
    items = products.storefront_payload(email)
    cats: list[dict] = []
    seen: dict[str, dict] = {}
    for p in items:
        c = (p.get("category") or "").strip()
        if not c:
            continue
        if c not in seen:
            seen[c] = {"name": c, "image": p.get("image_url") or "", "count": 0}
            cats.append(seen[c])
        seen[c]["count"] += 1
        if not seen[c]["image"]:
            seen[c]["image"] = p.get("image_url") or ""
    public = {k: v for k, v in site.items() if k not in ("policies",)}
    public["policies"] = site.get("policies") or {}
    # the scarcity block reads the real catalogue: the listed, stock-tracked
    # product with the fewest units left is the one worth counting down.
    scarce = None
    # a sold-out item is not a countdown — only pieces still buyable qualify
    tracked = [p for p in items if p.get("available") not in (None, 0) and p.get("in_stock")]
    if tracked:
        low = min(tracked, key=lambda p: p["available"])
        started = max(low["available"], 1)
        scarce = {
            "name": low["name"], "id": low["id"],
            "left": low["available"],
            "of": max(started, 20 if started < 20 else started),
            "image": low.get("image_url") or "",
        }
    return {
        "site": public,
        "style": resolved_style(site),
        "products": items,
        "categories": cats,
        "scarce": scarce,
        "icons": ICONS,
        "seller": email,
    }
