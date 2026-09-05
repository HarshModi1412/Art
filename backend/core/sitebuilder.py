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
# Fonts offered in the customiser (all Google Fonts, loaded on demand)
# =========================================================================
FONTS = [
    {"id": "inter",      "label": "Inter",              "stack": "'Inter', system-ui, sans-serif",                 "g": "Inter:wght@400;500;600;700;800",           "kind": "sans"},
    {"id": "manrope",    "label": "Manrope",            "stack": "'Manrope', system-ui, sans-serif",               "g": "Manrope:wght@400;500;600;700;800",         "kind": "sans"},
    {"id": "dmsans",     "label": "DM Sans",            "stack": "'DM Sans', system-ui, sans-serif",               "g": "DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,700", "kind": "sans"},
    {"id": "poppins",    "label": "Poppins",            "stack": "'Poppins', system-ui, sans-serif",               "g": "Poppins:wght@300;400;500;600;700",         "kind": "sans"},
    {"id": "montserrat", "label": "Montserrat",         "stack": "'Montserrat', system-ui, sans-serif",            "g": "Montserrat:wght@400;500;600;700;800",      "kind": "sans"},
    {"id": "outfit",     "label": "Outfit",             "stack": "'Outfit', system-ui, sans-serif",                "g": "Outfit:wght@300;400;500;600;700;800",      "kind": "sans"},
    {"id": "spacegro",   "label": "Space Grotesk",      "stack": "'Space Grotesk', system-ui, sans-serif",         "g": "Space+Grotesk:wght@400;500;600;700",       "kind": "sans"},
    {"id": "sora",       "label": "Sora",               "stack": "'Sora', system-ui, sans-serif",                  "g": "Sora:wght@300;400;500;600;700;800",        "kind": "sans"},
    {"id": "worksans",   "label": "Work Sans",          "stack": "'Work Sans', system-ui, sans-serif",             "g": "Work+Sans:wght@400;500;600;700",           "kind": "sans"},
    {"id": "syne",       "label": "Syne",               "stack": "'Syne', system-ui, sans-serif",                  "g": "Syne:wght@400;600;700;800",                "kind": "display"},
    {"id": "oswald",     "label": "Oswald",             "stack": "'Oswald', system-ui, sans-serif",                "g": "Oswald:wght@400;500;600;700",              "kind": "display"},
    {"id": "bebas",      "label": "Bebas Neue",         "stack": "'Bebas Neue', system-ui, sans-serif",            "g": "Bebas+Neue",                               "kind": "display"},
    {"id": "archivo",    "label": "Archivo Black",      "stack": "'Archivo Black', system-ui, sans-serif",         "g": "Archivo+Black",                            "kind": "display"},
    {"id": "playfair",   "label": "Playfair Display",   "stack": "'Playfair Display', Georgia, serif",             "g": "Playfair+Display:wght@400;500;600;700;800","kind": "serif"},
    {"id": "cormorant",  "label": "Cormorant Garamond", "stack": "'Cormorant Garamond', Georgia, serif",           "g": "Cormorant+Garamond:wght@300;400;500;600;700","kind": "serif"},
    {"id": "dmserif",    "label": "DM Serif Display",   "stack": "'DM Serif Display', Georgia, serif",             "g": "DM+Serif+Display",                         "kind": "serif"},
    {"id": "marcellus",  "label": "Marcellus",          "stack": "'Marcellus', Georgia, serif",                    "g": "Marcellus",                                "kind": "serif"},
    {"id": "fraunces",   "label": "Fraunces",           "stack": "'Fraunces', Georgia, serif",                     "g": "Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700", "kind": "serif"},
    {"id": "lora",       "label": "Lora",               "stack": "'Lora', Georgia, serif",                         "g": "Lora:wght@400;500;600;700",                "kind": "serif"},
    {"id": "libre",      "label": "Libre Baskerville",  "stack": "'Libre Baskerville', Georgia, serif",            "g": "Libre+Baskerville:wght@400;700",           "kind": "serif"},
]
FONT_IDS = {f["id"] for f in FONTS}


def font(font_id: str) -> dict:
    return next((f for f in FONTS if f["id"] == font_id), FONTS[0])


# =========================================================================
# Themes — each is a different storefront, not a recoloured one
# =========================================================================
# motion values understood by the storefront runtime:
#   reveal      fade + rise as sections enter the viewport
#   hscroll     horizontal collection rails (drag / wheel / arrows)
#   parallax    background moves slower than content on vertical scroll
#   pin         section sticks while its content advances
#   marquee     continuous horizontal ticker band
#   zoom        slow image scale on enter
THEMES = [
    {
        "id": "basic", "label": "Basic", "icon": "◻️", "genre": "Universal",
        "blurb": "Clean, fast and quiet. Big product grid, no theatrics — the safe default that suits any category.",
        "fonts": {"heading": "inter", "body": "inter"},
        "light": {"bg": "#ffffff", "surface": "#f7f7f8", "ink": "#17181c", "muted": "#6b7078",
                  "border": "#e5e6ea", "accent": "#3f4757", "accent_ink": "#ffffff"},
        "dark":  {"bg": "#101216", "surface": "#181a1f", "ink": "#e8eaee", "muted": "#8d929c",
                  "border": "#282b33", "accent": "#c3cadb", "accent_ink": "#14161a"},
        "layout": {"hero": "split", "grid": "cards", "cta": "solid", "radius": 12,
                   "case": "none", "track": 0, "density": "normal"},
        "motion": ["reveal"],
    },
    {
        "id": "luxury", "label": "Luxury", "icon": "🕯️", "genre": "Premium / heritage",
        "blurb": "Ink-dark, wide margins, serif display type. Slow horizontal collection rails and a parallax hero — built to make one product feel expensive.",
        "fonts": {"heading": "cormorant", "body": "worksans"},
        "light": {"bg": "#f6f3ee", "surface": "#efe9e0", "ink": "#1c1a17", "muted": "#7a736a",
                  "border": "#ddd5c9", "accent": "#8a6f43", "accent_ink": "#ffffff"},
        "dark":  {"bg": "#0e0d0c", "surface": "#161412", "ink": "#ece7de", "muted": "#9a9186",
                  "border": "#2a2622", "accent": "#c8a86a", "accent_ink": "#14120f"},
        "layout": {"hero": "full", "grid": "editorial", "cta": "outline", "radius": 0,
                   "case": "upper", "track": 3, "density": "airy"},
        "motion": ["reveal", "parallax", "hscroll", "zoom"],
    },
    {
        "id": "fitness", "label": "Fitness", "icon": "🏋️", "genre": "Sports / supplements",
        "blurb": "Loud condensed headlines, high-contrast blocks, a scrolling claims band and fast vertical parallax. Made to convert on energy.",
        "fonts": {"heading": "bebas", "body": "manrope"},
        "light": {"bg": "#f4f5f7", "surface": "#ffffff", "ink": "#101317", "muted": "#666d78",
                  "border": "#dfe2e7", "accent": "#1f6f4a", "accent_ink": "#ffffff"},
        "dark":  {"bg": "#0b0d10", "surface": "#14181d", "ink": "#eef1f5", "muted": "#8a929d",
                  "border": "#242a31", "accent": "#4fd18b", "accent_ink": "#08110c"},
        "layout": {"hero": "full", "grid": "cards", "cta": "solid", "radius": 6,
                   "case": "upper", "track": 1, "density": "tight"},
        "motion": ["reveal", "parallax", "marquee", "pin"],
    },
    {
        "id": "fashion", "label": "Fashion & Apparel", "icon": "👗", "genre": "Clothing / lookbook",
        "blurb": "Editorial lookbook. Full-bleed imagery, horizontal collection scroll and mask reveals — the grid gets out of the photo's way.",
        "fonts": {"heading": "syne", "body": "dmsans"},
        "light": {"bg": "#faf9f7", "surface": "#ffffff", "ink": "#15161a", "muted": "#71737b",
                  "border": "#e6e4e0", "accent": "#1b1c20", "accent_ink": "#ffffff"},
        "dark":  {"bg": "#0f0f11", "surface": "#17171a", "ink": "#eeedeb", "muted": "#90919a",
                  "border": "#26262b", "accent": "#e8e6e1", "accent_ink": "#131315"},
        "layout": {"hero": "full", "grid": "editorial", "cta": "outline", "radius": 2,
                   "case": "upper", "track": 2, "density": "airy"},
        "motion": ["reveal", "hscroll", "zoom"],
    },
    {
        "id": "jewellery", "label": "Jewellery", "icon": "💍", "genre": "Fine jewellery",
        "blurb": "Small pieces, huge close-ups. Soft champagne palette, a slow carousel and a gentle shine pass over each card.",
        "fonts": {"heading": "marcellus", "body": "worksans"},
        "light": {"bg": "#fbf8f4", "surface": "#ffffff", "ink": "#1d1a16", "muted": "#7d746a",
                  "border": "#e9e0d4", "accent": "#9c7c46", "accent_ink": "#ffffff"},
        "dark":  {"bg": "#100e0c", "surface": "#191614", "ink": "#efe9e0", "muted": "#9a9086",
                  "border": "#2b2620", "accent": "#d8b877", "accent_ink": "#161310"},
        "layout": {"hero": "split", "grid": "editorial", "cta": "outline", "radius": 3,
                   "case": "upper", "track": 4, "density": "airy"},
        "motion": ["reveal", "hscroll", "zoom", "parallax"],
    },
    {
        "id": "cafe", "label": "Food & Beverage", "icon": "☕", "genre": "Cafe / kitchen",
        "blurb": "A menu, not a catalogue. Warm paper tones, horizontal category rails and prices that read like a board behind the counter.",
        "fonts": {"heading": "fraunces", "body": "worksans"},
        "light": {"bg": "#fbf7f0", "surface": "#ffffff", "ink": "#211a12", "muted": "#7d7266",
                  "border": "#e8ded0", "accent": "#a2542a", "accent_ink": "#ffffff"},
        "dark":  {"bg": "#12100d", "surface": "#1b1814", "ink": "#f0e9df", "muted": "#9c9287",
                  "border": "#2c2721", "accent": "#e08a52", "accent_ink": "#170f09"},
        "layout": {"hero": "split", "grid": "list", "cta": "solid", "radius": 14,
                   "case": "none", "track": 0, "density": "normal"},
        "motion": ["reveal", "hscroll"],
    },
    {
        "id": "beauty", "label": "Beauty & Skincare", "icon": "🧴", "genre": "Skincare / wellness",
        "blurb": "Soft pastel ground, ingredient callouts under every product, gentle drifting gradients. Calm and clinical at once.",
        "fonts": {"heading": "playfair", "body": "manrope"},
        "light": {"bg": "#fbf6f5", "surface": "#ffffff", "ink": "#1e191b", "muted": "#7c7175",
                  "border": "#eddfdd", "accent": "#a8657a", "accent_ink": "#ffffff"},
        "dark":  {"bg": "#120f11", "surface": "#1a1618", "ink": "#f0e8ea", "muted": "#9a8f93",
                  "border": "#2b2427", "accent": "#e0a3b6", "accent_ink": "#181114"},
        "layout": {"hero": "split", "grid": "cards", "cta": "solid", "radius": 20,
                   "case": "none", "track": 0, "density": "airy"},
        "motion": ["reveal", "parallax", "zoom"],
    },
    {
        "id": "tech", "label": "Tech & Gadgets", "icon": "🎧", "genre": "Electronics",
        "blurb": "Dark spec-sheet layout. Feature sections pin while their detail scrolls, and every product carries a hard numbers strip.",
        "fonts": {"heading": "spacegro", "body": "inter"},
        "light": {"bg": "#f5f6f8", "surface": "#ffffff", "ink": "#111318", "muted": "#666c77",
                  "border": "#e1e4e9", "accent": "#2f5d8c", "accent_ink": "#ffffff"},
        "dark":  {"bg": "#0a0c10", "surface": "#12151b", "ink": "#e9ecf1", "muted": "#8a919d",
                  "border": "#20242c", "accent": "#6fa8dc", "accent_ink": "#0a0f14"},
        "layout": {"hero": "full", "grid": "cards", "cta": "solid", "radius": 10,
                   "case": "none", "track": 0, "density": "tight"},
        "motion": ["reveal", "pin", "parallax", "marquee"],
    },
]
THEME_IDS = {t["id"] for t in THEMES}


def theme(theme_id: str) -> dict:
    return next((t for t in THEMES if t["id"] == theme_id), THEMES[0])


def theme_catalog() -> list[dict]:
    """What the theme picker shows — no need to ship the whole palette twice."""
    return [{
        "id": t["id"], "label": t["label"], "icon": t["icon"], "genre": t["genre"],
        "blurb": t["blurb"], "motion": t["motion"],
        "fonts": t["fonts"], "light": t["light"], "dark": t["dark"], "layout": t["layout"],
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
    base = normalise_handle(brand) or normalise_handle((email or "").split("@")[0]) or "my-store"
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
        "tagline": "",
        "logo_url": "",
        "published": False,
        "theme": "basic",
        "style": {
            "accent": "", "accent_dark": "",         # blank = use the theme's own
            "mode": "auto",                          # auto | light | dark
            "heading_font": "", "body_font": "",     # blank = theme default
            "radius": None,                          # None = theme default
            "motion": "full",                        # full | subtle | none
            "card_style": "",                        # blank = theme default
            "width": "wide",                         # wide | compact
        },
        "hero": {
            "image_url": "", "heading": "", "sub": "",
            "cta_text": "Shop now", "overlay": 45, "align": "left",
        },
        "sections": {
            "featured": True, "categories": True, "story": True,
            "highlights": True, "testimonials": False, "newsletter": False,
        },
        "story": {"title": "Our story", "body": "", "image_url": ""},
        "highlights": [
            {"icon": "🚚", "title": "Fast dispatch", "text": "Orders leave within 24 hours."},
            {"icon": "🔒", "title": "Secure checkout", "text": "Your details stay with us, never resold."},
            {"icon": "↩️", "title": "Easy returns", "text": "7-day no-questions returns."},
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
        },
        "policies": {"shipping": "", "returns": "", "privacy": ""},
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
    return site


def save_site(email: str, patch: dict) -> dict:
    email = (email or "").strip().lower()
    current = get_site(email)
    previous_handle = current.get("handle") or ""
    site = _merge(current, patch or {})

    site["brand"] = str(site.get("brand") or "").strip()[:80]
    site["tagline"] = str(site.get("tagline") or "").strip()[:160]
    site["announcement"] = str(site.get("announcement") or "").strip()[:200]
    if site["theme"] not in THEME_IDS:
        site["theme"] = "basic"

    # ---- handle ----
    wanted = normalise_handle(site.get("handle") or "")
    if not wanted:
        wanted = suggest_handle(site["brand"] or email.split("@")[0], email)
    if wanted != previous_handle and not handle_available(wanted, email):
        raise ValueError(f"The address “{wanted}” is already taken — try another.")
    if wanted in RESERVED_HANDLES or len(wanted) < 3:
        raise ValueError("Pick an address of at least 3 letters that isn't a reserved word.")
    site["handle"] = wanted

    # ---- style ----
    st = site["style"]
    st["mode"] = st.get("mode") if st.get("mode") in ("auto", "light", "dark") else "auto"
    st["motion"] = st.get("motion") if st.get("motion") in ("full", "subtle", "none") else "full"
    st["width"] = st.get("width") if st.get("width") in ("wide", "compact") else "wide"
    for k in ("heading_font", "body_font"):
        if st.get(k) and st[k] not in FONT_IDS:
            st[k] = ""
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
        {"icon": str(h.get("icon") or "✅")[:4],
         "title": str(h.get("title") or "").strip()[:60],
         "text": str(h.get("text") or "").strip()[:160]}
        for h in (site.get("highlights") or [])[:6] if isinstance(h, dict)
    ]
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
    c["gst_inclusive"] = _b(c.get("gst_inclusive"), True)
    c["currency"] = "INR"
    c["order_note"] = str(c.get("order_note") or "").strip()[:200]

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
    _persist(email, site)
    return site


# =========================================================================
# public payload — what the storefront renders from
# =========================================================================
def resolved_style(site: dict) -> dict:
    """Theme defaults with the seller's overrides applied. The storefront turns
    this straight into CSS custom properties, so every value is final here."""
    t = theme(site.get("theme"))
    st = site.get("style") or {}
    light = dict(t["light"])
    dark = dict(t["dark"])
    if st.get("accent"):
        light["accent"] = st["accent"]
    if st.get("accent_dark"):
        dark["accent"] = st["accent_dark"]
    elif st.get("accent"):
        dark["accent"] = st["accent"]
    layout = dict(t["layout"])
    if st.get("radius") not in (None, ""):
        layout["radius"] = st["radius"]
    if st.get("card_style"):
        layout["grid"] = st["card_style"]
    heading = font(st.get("heading_font") or t["fonts"]["heading"])
    body = font(st.get("body_font") or t["fonts"]["body"])
    motion = t["motion"]
    if st.get("motion") == "none":
        motion = []
    elif st.get("motion") == "subtle":
        motion = [m for m in motion if m in ("reveal", "hscroll")]
    return {
        "theme": t["id"], "light": light, "dark": dark, "layout": layout,
        "motion": motion, "mode": st.get("mode") or "auto",
        "width": st.get("width") or "wide",
        "heading_font": heading, "body_font": body,
        "google_fonts": sorted({heading["g"], body["g"]}),
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
    cats: list[str] = []
    for p in items:
        c = (p.get("category") or "").strip()
        if c and c not in cats:
            cats.append(c)
    public = {k: v for k, v in site.items() if k not in ("policies",)}
    public["policies"] = site.get("policies") or {}
    return {
        "site": public,
        "style": resolved_style(site),
        "products": items,
        "categories": cats,
        "seller": email,
    }
