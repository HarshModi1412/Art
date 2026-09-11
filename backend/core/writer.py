"""
The content writer — every "✨ Write with AI" in the app goes through here.

WHY ONE MODULE
--------------
A seller types in a dozen places: the website's headline and story, product
descriptions, key points, their brand profile, captions, a win-back message,
a note on a purchase order, the email that goes to a supplier. If each of
those wrote its own prompt, each would sound like a different person and each
would make its own mistakes (inventing a discount, a material, a delivery
promise). So there is one writer, with one set of rules, briefed with the
brand's own voice from Product Studio, and each place only says WHAT it needs.

WHO WRITES
----------
`aiprovider.generate(..., role="writer")`, which tries Puter first when
PUTER_AUTH_TOKEN is set (github.com/heyputer/puter — its gateway reaches
Claude, GPT and Gemini with one token, and the writer role asks for the
stronger copy model), then the rest of the chain. With no provider reachable
every function returns a usable hand-written template and says so, and the
browser can fall back to puter.js on the seller's own Puter account.

THE RULES (the part that makes it a writer rather than a text generator)
------------------------------------------------------------------------
Specific beats evocative. Short sentences. The seller's facts only — never a
price, discount, material, certification or delivery time that was not given.
Indian English, ₹, no Americanisms like "zip code". No stock phrases: the list
in BANNED is what makes AI copy recognisable at a glance.
"""
from __future__ import annotations

import json
import re

from backend.core import aiprovider

BANNED = ["elevate", "unleash", "curated", "timeless elegance", "look no further",
          "in today's fast-paced world", "game-changer", "must-have", "indulge",
          "exquisite", "embark", "journey", "delve", "unlock", "seamless",
          "whether you're", "perfect blend", "treat yourself", "second to none",
          "top-notch", "world-class", "revolutionary", "best-in-class"]

WRITER_SYSTEM = """You are a senior copywriter for small Indian D2C brands — clothing, jewellery, perfume, handmade goods. You write the words that go on a seller's own website, product pages, social posts and business emails.

How you write:
- Specific beats evocative. "Hand-block printed in Sanganer, 100% cotton, 2.5 m" beats "beautifully crafted".
- Short sentences. Plain words. Confident, warm, never shouty. No exclamation marks unless the brand voice asks for them.
- Indian English and ₹. Say "PIN code", not "zip code".
- Write in the brand's voice when one is given, and for the buyer described.
- Use ONLY the facts you are given. Never invent a price, a discount, a material, a certification, a statistic, a review, an award or a delivery time. If a fact is missing, write around it — do not fill it in.
- Never use these phrases: {banned}.
- No emoji unless asked. No hashtags unless asked. No quotation marks around the whole answer.
- Return only the text asked for — no preamble, no "Here is", no explanation.""".format(
    banned=", ".join(BANNED))


# --------------------------------------------------------------- context
def brand_context(email: str) -> str:
    """What the writer knows about this seller, from Product Studio and the site."""
    lines = []
    try:
        from backend.core import studio
        b = studio.get_brand(email) or {}
        voice = studio.VOICE_PROMPT.get(b.get("voice") or "", "")
        if b.get("name"):
            lines.append(f"Brand: {b['name']}")
        if b.get("about"):
            lines.append(f"What they make and why: {b['about']}")
        if b.get("audience"):
            lines.append(f"Who buys it: {b['audience']}")
        if voice:
            lines.append(f"Brand voice: {voice}")
        if b.get("avoid"):
            lines.append(f"Never say: {b['avoid']}")
        if b.get("city"):
            lines.append(f"Based in: {b['city']}")
    except Exception:  # noqa: BLE001
        pass
    try:
        from backend.core import sitebuilder
        site = sitebuilder.get_site(email) or {}
        brand = site.get("brand")
        if brand and not any(l.startswith("Brand:") for l in lines) and not site.get("brand_placeholder"):
            lines.append(f"Brand: {brand}")
        if site.get("brief"):
            lines.append(f"In the seller's own words: {site['brief']}")
        if site.get("tagline"):
            lines.append(f"Tagline: {site['tagline']}")
    except Exception:  # noqa: BLE001
        pass
    return "\n".join(lines)


def catalogue_context(email: str, limit: int = 12) -> str:
    try:
        from backend.core import products
        items = [p for p in products.get_products(email) if p.get("status") != "archived"][:limit]
    except Exception:  # noqa: BLE001
        return ""
    if not items:
        return ""
    rows = []
    for p in items:
        bits = [p.get("name") or ""]
        if p.get("category"):
            bits.append(p["category"])
        if p.get("price") is not None:
            bits.append(f"₹{float(p['price']):,.0f}")
        rows.append(" · ".join(b for b in bits if b))
    return "Products they sell:\n" + "\n".join(f"- {r}" for r in rows)


def _clean(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", t).strip()
    t = re.sub(r"^(here(?: is|'s)[^:\n]*:\s*)", "", t, flags=re.I).strip()
    if len(t) > 1 and t[0] == t[-1] and t[0] in "\"'“”":
        t = t[1:-1].strip()
    return t


def _json(text: str) -> dict:
    t = _clean(text)
    m = re.search(r"\{.*\}", t, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except ValueError:
        return {}


def _call(user: str, *, max_tokens: int = 500, sensitivity: str = "public",
          temperature: float = 0.7) -> dict:
    return aiprovider.generate(WRITER_SYSTEM, user, sensitivity=sensitivity,
                               max_tokens=max_tokens, temperature=temperature,
                               fallback="", role="writer")


def _result(text: str, res: dict, prompt_user: str, template: bool = False) -> dict:
    return {"text": text, "provider": "template" if template else res.get("provider", ""),
            "ai": not template, "error": res.get("error", "") if template else "",
            # the exact brief, so the browser can hand it to puter.js when the
            # server has no AI of its own
            "prompt": {"system": WRITER_SYSTEM, "user": prompt_user}}


# --------------------------------------------------------------- any field
FIELD_KINDS = {
    "product_description": "a product description for the product page: 2 short paragraphs, what it is, what it is made of, how it feels or fits, who it is for. 60-110 words.",
    "product_highlights": "3 to 5 key points for the product page, one per line, each under 8 words, no bullets or dashes.",
    "hero_heading": "a website hero headline, 3-7 words, no full stop unless it is a statement.",
    "hero_sub": "one sentence under the hero headline, under 18 words.",
    "tagline": "a one-line brand tagline, under 10 words.",
    "story": "the 'Our story' section of the website: 60-110 words, first person plural, what they make, why, how, and one concrete detail.",
    "manifesto": "a short brand statement that is revealed word by word on the site: 15-30 words, one or two sentences.",
    "announcement": "an announcement bar line, under 12 words.",
    "newsletter": "a newsletter sign-up line, under 14 words, and what they will get.",
    "policy": "a clear, fair store policy paragraph in plain English, 50-120 words. Use only terms the seller gave; where a number is missing leave a bracketed placeholder like [7] days.",
    "seo_description": "a search/meta description, 140-160 characters, with the product category words in it.",
    "brand_about": "what the brand makes and why, 2-3 sentences, first person plural.",
    "brand_audience": "who buys from this brand, one or two sentences, concrete.",
    "product_story": "the story behind this product, 2-4 sentences.",
    "product_different": "what makes this product different, one or two sentences.",
    "caption": "an Instagram caption: a hook line under 125 characters, then 2-3 short lines, then one question.",
    "caption_hook": "an Instagram hook line under 125 characters that carries the product and a reason to care.",
    "message": "a short WhatsApp message from the seller to a customer, warm, under 60 words.",
    "po_note": "a short, polite note to a supplier to go on a purchase order, under 40 words.",
    "label": "a short website section label or heading, 1-5 words.",
    "site_brief": "a 2-3 sentence description of the shop in the seller's own voice — what they sell, who makes it, who buys it, what makes it theirs. It will be used to write their whole website, so stick to facts given here.",
    "product_materials": "what the product is made of, as a short comma-separated list under 12 words. Only materials stated in the facts or the current text; if none are given, return a fill-in line like '[main material], [finish or trim]'.",
    "product_for": "who this product is for, one line under 14 words, a person not a demographic.",
    "product_occasions": "where or when it is worn or used, a comma-separated list of 3-5 occasions, under 10 words.",
    "hashtags": "8 to 15 Instagram hashtags, space-separated, each starting with #, a mix of broad and niche, relevant to Indian shoppers, no spaces inside a tag, nothing else.",
    "brand_palette": "the brand's colours in words, 3-5 colour names separated by commas, matching the look and products.",
    "brand_avoid": "words and looks this brand should never use, 4-8 items separated by commas.",
    "voiceover": "a voiceover for a short reel, spoken, under 30 words, following the shots given.",
    "general": "the text for this field.",
}


def write_field(email: str, kind: str, label: str = "", current: str = "",
                context: dict | None = None, instruction: str = "") -> dict:
    """Write, or rewrite, the text for one field."""
    kind = kind if kind in FIELD_KINDS else "general"
    ctx = context or {}
    facts = "\n".join(f"- {k}: {v}" for k, v in ctx.items()
                      if v not in (None, "", [], {}) and not str(k).startswith("_"))
    extra = ""
    if kind == "site_brief":
        try:
            extra = catalogue_context(email) + "\n"
        except Exception:  # noqa: BLE001
            extra = ""
    user = (f"{brand_context(email)}\n\n{extra}"
            + (f"About this item:\n{facts}\n\n" if facts else "")
            + (f"The field is: {label}\n" if label else "")
            + f"Write {FIELD_KINDS[kind]}\n"
            + (f"\nWhat is there now (improve it, keep every fact):\n{current}\n" if current.strip() else "")
            + (f"\nAlso: {instruction}\n" if instruction else ""))
    res = _call(user, max_tokens=450 if kind not in ("story", "policy", "product_description") else 700)
    text = _clean(res.get("text", ""))
    if text:
        return _result(text, res, user)
    return _result(_template_field(kind, label, current, ctx, email), res, user, template=True)


def _template_field(kind: str, label: str, current: str, ctx: dict, email: str) -> str:
    """No AI reachable. Still something the seller can edit, built only from
    what they told us — where a fact is missing it is left as a [bracketed]
    gap to fill in, never guessed."""
    name = ctx.get("name") or ctx.get("product") or "This piece"
    cat = (ctx.get("category") or "").lower()
    mat = ctx.get("materials") or ctx.get("fabric") or ""
    if current.strip():
        return current.strip()
    if kind == "product_description":
        s = f"{name}" + (f" — {cat}" if cat else "") + "."
        s += f" Made of {mat}." if mat else " Made of [what it is made of]."
        if ctx.get("key_points"):
            s += " " + " ".join(str(x).rstrip(".") + "." for x in ctx["key_points"][:3])
        else:
            s += " [How it feels or fits, and who it is for.]"
        return s + " Message us for sizes, colours and delivery to your PIN code."
    if kind == "product_highlights":
        pts = [f"Made of {mat}" if mat else "[What it is made of]",
               "[How it fits or feels]", "[Care or delivery detail]"]
        return "\n".join(pts)
    if kind == "hero_heading":
        return ctx.get("brand") or name if (ctx.get("brand") or ctx.get("name")) else "Everything we make, in one place"
    if kind == "hero_sub":
        return (ctx.get("tagline") or "Browse the full range and order in a few taps.")
    if kind == "story":
        return ((ctx.get("brief") or "").strip()
                or "[Who you are, what you make and why — one concrete detail a customer would remember.]")
    if kind == "site_brief":
        return "[What you sell]. [Who makes it, and where]. [Who buys it, and why they choose you]."
    if kind == "product_materials":
        return mat or "[main material], [finish or trim]"
    if kind == "hashtags":
        words = [w for w in re.split(r"[^a-z0-9]+", f"{name} {cat}".lower()) if len(w) > 2][:5]
        return " ".join(f"#{w}" for w in words) or "#[yourbrand] #[category]"
    return label or ""


# --------------------------------------------------------------- product copy
def product_copy(email: str, product: dict, notes: str = "") -> dict:
    """Description + key points for one product, from what the seller gave."""
    facts = {k: product.get(k) for k in ("name", "category", "price", "mrp", "unit_label")
             if product.get(k) not in (None, "")}
    try:
        from backend.core import studio
        if product.get("id"):
            mat = studio.get_material(email, product["id"])
            for k, lbl in (("materials", "materials"), ("story", "story"),
                           ("different", "what makes it different"),
                           ("for_who", "who it is for"), ("occasions", "occasions"),
                           ("seen", "what the photos show")):
                if mat.get(k):
                    facts[lbl] = mat[k]
    except Exception:  # noqa: BLE001
        pass
    if product.get("highlights"):
        facts["key points given"] = "; ".join(product["highlights"])
    if product.get("description"):
        facts["current description"] = product["description"]
    if notes:
        facts["the seller's notes"] = notes
    user = (f"{brand_context(email)}\n\nProduct facts:\n"
            + "\n".join(f"- {k}: {v}" for k, v in facts.items())
            + "\n\nWrite the product page copy. Return JSON only: "
              '{"description": "2 short paragraphs, 60-110 words", '
              '"highlights": ["3-5 key points, each under 8 words"], '
              '"seo": "a 140-160 character meta description"}')
    res = _call(user, max_tokens=700)
    data = _json(res.get("text", ""))
    if data.get("description"):
        hl = data.get("highlights") or []
        if isinstance(hl, str):
            hl = [x.strip("-• ").strip() for x in hl.splitlines() if x.strip()]
        return {"description": _clean(str(data["description"])),
                "highlights": [str(x).strip("-• ").strip() for x in hl if str(x).strip()][:6],
                "seo": _clean(str(data.get("seo") or ""))[:170],
                "provider": res.get("provider"), "ai": True, "error": "",
                "prompt": {"system": WRITER_SYSTEM, "user": user}}
    ctx = {"name": product.get("name"), "category": product.get("category"),
           "materials": facts.get("materials", ""),
           "key_points": product.get("highlights") or []}
    return {"description": _template_field("product_description", "", "", ctx, email),
            "highlights": _template_field("product_highlights", "", "", ctx, email).split("\n"),
            "seo": "", "provider": "template", "ai": False, "error": res.get("error", ""),
            "prompt": {"system": WRITER_SYSTEM, "user": user}}


# --------------------------------------------------------------- the whole site
SITE_FIELDS = {
    "tagline": "one-line tagline under 10 words",
    "hero_heading": "hero headline, 3-7 words",
    "hero_sub": "one sentence under the headline, under 18 words",
    "hero_cta": "button text, 1-3 words",
    "announcement": "announcement bar, under 12 words — only facts given (e.g. shipping terms)",
    "story_title": "title for the story section, 2-4 words",
    "story_body": "the story section, 60-110 words",
    "manifesto": "a brand statement, 15-30 words",
    "highlights": "exactly 3 promises, each {\"title\": 2-3 words, \"text\": under 10 words} — only promises the facts support",
    "news_title": "newsletter heading, 2-5 words",
    "news_sub": "newsletter line, under 14 words",
    "shop_title": "heading over all products, 2-5 words",
    "feat_title": "heading over featured products, 1-4 words",
    "seo_title": "page title for search, under 60 characters",
    "seo_description": "meta description, 140-160 characters",
    "seo_keywords": "6-10 comma-separated search keywords",
}


def site_copy(email: str, brief: str) -> dict:
    """Everything written on the storefront, from a line or two about the shop."""
    try:
        from backend.core import sitebuilder
        site = sitebuilder.get_site(email) or {}
        c = site.get("commerce") or {}
        terms = []
        if c.get("free_shipping_above"):
            terms.append(f"free shipping over ₹{float(c['free_shipping_above']):,.0f}")
        if c.get("cod_enabled"):
            terms.append("cash on delivery available")
        t = site.get("trust") or {}
        if t.get("returns_days"):
            terms.append(f"{t['returns_days']}-day returns")
        if t.get("dispatch_days"):
            terms.append(f"dispatch within {t['dispatch_days']} days")
    except Exception:  # noqa: BLE001
        terms = []
    spec = ",\n".join(f'  "{k}": {v}' for k, v in SITE_FIELDS.items())
    user = (f"The seller describes their shop:\n\"{brief.strip()}\"\n\n"
            f"{brand_context(email)}\n{catalogue_context(email)}\n"
            + (f"Store terms (the only promises you may make): {', '.join(terms)}\n" if terms else
               "No store terms were given — do not promise shipping, returns or timings.\n")
            + "\nWrite all the words on their website. Return JSON only, with these keys:\n{\n"
            + spec + "\n}")
    res = _call(user, max_tokens=1400, temperature=0.75)
    data = _json(res.get("text", ""))
    if data.get("hero_heading"):
        out = {k: (_clean(str(v)) if not isinstance(v, list) else v)
               for k, v in data.items() if k in SITE_FIELDS}
        hl = out.get("highlights") or []
        out["highlights"] = [{"title": _clean(str(h.get("title", ""))),
                              "text": _clean(str(h.get("text", "")))}
                             for h in hl if isinstance(h, dict)][:3]
        return {"copy": out, "provider": res.get("provider"), "ai": True, "error": "",
                "prompt": {"system": WRITER_SYSTEM, "user": user}}
    first = (brief or "").strip().split(".")[0][:90]
    return {"copy": {
        "tagline": first or "Browse the range and order in a few taps",
        "hero_heading": "Made to be kept",
        "hero_sub": (first + ".") if first else "Browse the full range and order in a few taps.",
        "hero_cta": "Shop now",
        "story_title": "Our story",
        "story_body": (brief or "").strip()[:600],
        "news_title": "Stay in the loop",
        "news_sub": "New pieces first. No spam, ever.",
        "shop_title": "Everything we make",
        "feat_title": "Featured",
        "seo_description": (brief or "").strip()[:158],
    }, "provider": "template", "ai": False, "error": res.get("error", ""),
        "prompt": {"system": WRITER_SYSTEM, "user": user}}


# --------------------------------------------------------------- supplier email
def po_email(email: str, po: dict) -> dict:
    """The email that carries a purchase order to the supplier.

    Marked private: it names what the seller buys, from whom and how much —
    business information, so it only goes to providers that do not train on
    what they are sent."""
    from backend.core import brandname
    brand = brandname.display(email)
    sup = po.get("supplier") or {}
    lines = po.get("lines") or []
    lead = max((float(ln.get("lead_time_days") or 0) for ln in lines), default=0)
    items = "\n".join(
        f"- {ln.get('name')}: {ln.get('order_qty')} {ln.get('unit_label') or 'units'}"
        + (f" at ₹{float(ln['unit_cost']):,.2f}" if ln.get("unit_cost") is not None else "")
        for ln in lines)
    user = (f"Write the email that sends a purchase order to a supplier.\n"
            f"From: {brand} (buyer), reply-to {email}\n"
            f"To: {sup.get('name') or 'the supplier'}\n"
            f"PO number: {po.get('po_number')} (PDF attached)\n"
            f"Items:\n{items}\n"
            + (f"We usually get delivery in about {int(lead)} days.\n" if lead else "")
            + "Ask them to confirm availability, price and the dispatch date by reply, "
              "and to quote the PO number on the invoice. Polite, brief, businesslike, "
              "Indian business English. Sign off as the team at the buyer's brand.\n"
              'Return JSON only: {"subject": "...", "body": "..."}')
    res = aiprovider.generate(WRITER_SYSTEM, user, sensitivity="private",
                              max_tokens=600, temperature=0.4, fallback="", role="writer")
    data = _json(res.get("text", ""))
    if data.get("subject") and data.get("body"):
        return {"subject": _clean(str(data["subject"]))[:200],
                "body": str(data["body"]).strip(), "provider": res.get("provider"), "ai": True}
    greet = f"Dear {sup.get('name')}," if sup.get("name") else "Hello,"
    body = (f"{greet}\n\nPlease find attached our purchase order {po.get('po_number')} for:\n\n"
            f"{items}\n\n"
            "Kindly confirm availability, price and the dispatch date by reply, and quote "
            "the PO number on your invoice and delivery challan.\n\n"
            f"Thank you,\nTeam {brand}\n{email}")
    return {"subject": f"Purchase order {po.get('po_number')} from {brand}",
            "body": body, "provider": "template", "ai": False}
