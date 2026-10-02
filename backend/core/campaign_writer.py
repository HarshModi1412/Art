"""
The words of a Marketing Campaign.

WHAT WAS WRONG
--------------
The old win-back bank (templates.py) was written for a café: "we've been
keeping a seat warm", "the {item} machine keeps asking where you went". Put a
clothing shop's product into that and a customer read

    "Simran A., the Chikankari Kurta, White machine keeps asking where you went."

Two faults in one line: copy for the wrong kind of shop, and the product's
VARIANT (", White", ", 6 ml") pasted into the middle of a sentence. A message
that reads like a mail-merge accident is worse than no message, because it is
the customer's first contact from the shop in months.

HOW IT WORKS NOW
----------------
One AI call per CAMPAIGN, not per customer. The AI is told what the shop sells,
why this campaign is going out (win back quiet customers / a festival), what
the offer is, and is asked for a short WhatsApp message and an email subject
with placeholders:

    {name} {product} {offer} {code} {expiry} {link} {brand} {occasion}

Every customer's message is then the template filled in locally. That keeps it
to one call (cheap, fast, inside free tiers), and it means no customer's name,
spend or contact details are ever sent to an AI provider — only the brief.

The AI goes through aiprovider.generate with the seller's email, so it is
written on the seller's own ChatGPT plan when they connected one, then
OpenAI / Cloudflare / the rest of the chain. If every provider is down, or the
answer does not carry the placeholders a campaign cannot work without ({code}
and {offer}), the hand-written retail templates below are used. They are
written to be good on their own, not a placeholder for the AI.
"""
from __future__ import annotations

import json
import logging
import random
import re

log = logging.getLogger("campaign_writer")

REASONS = {
    "winback": "Win back customers who have gone quiet",
    "festival": "Festival offer for your best customers",
}

PLACEHOLDERS = ("{name}", "{product}", "{offer}", "{code}", "{expiry}", "{link}",
                "{brand}", "{occasion}")
REQUIRED = ("{code}", "{offer}")
MAX_WHATSAPP = 700

# --------------------------------------------------------------- product names
_SKUISH = re.compile(r"^[A-Za-z0-9_./#-]{3,24}$")


def _norm(v) -> str:
    return re.sub(r"[^a-z0-9]", "", str(v or "").lower())


def catalogue_names(email: str) -> dict:
    """{normalised name, alias or SKU -> the product's proper name}."""
    try:
        from backend.core import products
        m = dict(products.alias_map(email) or {})
        for p in products.get_products(email) or []:
            if p.get("sku") and p.get("name"):
                m[_norm(p["sku"])] = p["name"]
            for v in p.get("variants") or []:
                if v.get("sku") and p.get("name"):
                    m[_norm(v["sku"])] = p["name"]
        return {_norm(k): v for k, v in m.items() if k and v}
    except Exception:  # noqa: BLE001 — a missing catalogue only means no lookup
        return {}


def clean_product_name(name, names: dict | None = None) -> str:
    """The product as a person would say it in a sentence.

      "Chikankari Kurta, White"   -> "Chikankari Kurta"
      "Mogra Attar, 6 ml"         -> "Mogra Attar"
      "Linen Shirt - Blue / XL"   -> "Linen Shirt"
      "SKU-10023" (in catalogue)  -> the catalogue's name for it
      "SKU-10023" (unknown)       -> ""   (better to say nothing than a code)
    """
    s = str(name or "").strip()
    if not s or s.lower() in ("-", "—", "nan", "none", "null"):
        return ""
    if names:
        hit = names.get(_norm(s))
        if hit:
            s = str(hit).strip()
    if " " not in s and _SKUISH.match(s) and re.search(r"\d", s):
        return ""
    for sep in (" | ", " – ", " — ", " - ", ", ", " / ", " ("):
        if sep in s:
            head = s.split(sep)[0].strip()
            if len(head) >= 3:
                s = head
                break
    return s[:60].strip()


def first_name(full) -> str:
    s = str(full or "").strip()
    if not s or re.match(r"^(cust|customer|c)?[\s#_-]*\d+$", s, re.I):
        return ""
    first = s.split()[0].strip(",.")
    # "Sana D." -> "Sana"; a bare initial is not a name
    return first if len(first) >= 2 else ""


# ------------------------------------------------------------------- fallback
_WA_WINBACK = [
    ("Hi {name}, it's {brand}. It's been a while, and we wanted to say we've missed you.\n\n"
     "Since you liked the {product}, we've put aside {offer} for your next order. "
     "Your code is *{code}*, valid till {expiry}.\n\n{link}"),
    ("Hi {name}! {brand} here. We noticed it's been some time since your last order, "
     "so here's a small thank-you for shopping with us before: {offer}.\n\n"
     "Use code *{code}* by {expiry}. Fancy another {product}? This is a good week for it.\n\n{link}"),
    ("Hello {name}, hope you're well! It's {brand}. We'd love to see you back, "
     "so this one's just for you: {offer} with code *{code}* (till {expiry}).\n\n"
     "Thank you for choosing the {product} last time, we'd love to help you find your next favourite.\n\n{link}"),
]
_WA_WINBACK_GENERIC = [
    ("Hi {name}, it's {brand}. It's been a while, and we wanted to say we've missed you.\n\n"
     "Here's {offer} on your next order. Your code is *{code}*, valid till {expiry}.\n\n{link}"),
    ("Hello {name}! {brand} here. As a thank-you for shopping with us before, "
     "here's {offer} on whatever you pick next. Code *{code}*, till {expiry}.\n\n{link}"),
]
_WA_FESTIVAL = [
    ("Hi {name}, {occasion} is almost here! From all of us at {brand}, here's "
     "{offer} to make it special.\n\nYour code: *{code}* (valid till {expiry}). "
     "You loved the {product}, so this felt like the perfect time to say thank you.\n\n{link}"),
    ("Happy {occasion} in advance, {name}! As one of our favourite customers, "
     "you get {offer} at {brand}. Use code *{code}* by {expiry}.\n\n"
     "Pair it with the {product} you liked.\n\n{link}"),
]
_WA_FESTIVAL_GENERIC = [
    ("Hi {name}, {occasion} is almost here! From all of us at {brand}, here's "
     "{offer} to make it special.\n\nYour code: *{code}* (valid till {expiry}).\n\n{link}"),
    ("Happy {occasion} in advance, {name}! As one of our favourite customers, "
     "you get {offer} at {brand}. Use code *{code}* by {expiry}.\n\n{link}"),
]
_SUBJECTS = {
    "winback": ["{name}, we've missed you: {offer} inside", "A little something from {brand}"],
    "festival": ["{occasion} at {brand}: {offer} for you", "{name}, your {occasion} offer is here"],
}


def fallback_copy(reason: str) -> dict:
    if reason == "festival":
        return {"whatsapp": random.choice(_WA_FESTIVAL),
                "whatsapp_generic": random.choice(_WA_FESTIVAL_GENERIC),
                "email_subject": random.choice(_SUBJECTS["festival"]),
                "source": "template"}
    return {"whatsapp": random.choice(_WA_WINBACK),
            "whatsapp_generic": random.choice(_WA_WINBACK_GENERIC),
            "email_subject": random.choice(_SUBJECTS["winback"]),
            "source": "template"}


# ---------------------------------------------------------------------- AI
_SYSTEM = """You write marketing messages for a small independent online shop.
They are sent on WhatsApp (and the same text by email) to the shop's own past
customers. Sound like the shop owner: warm, specific, short, never pushy, never
salesy jargon. Plain English. At most one emoji per message, or none.

Use these placeholders EXACTLY as written, they are filled in per customer:
{name} customer's first name, {brand} the shop name, {product} the product this
customer bought most, {offer} the discount (e.g. "Rs 200 off"), {code} their
personal code, {expiry} the last date it works, {link} the shop link,
{occasion} the festival name (festival campaigns only).

Rules:
- "whatsapp": 3 to 5 short sentences, under 450 characters. MUST contain {code},
  {offer} and {expiry}. Put {link} alone on the last line. Bold the code as *{code}*.
- "whatsapp_generic": the same message for a customer whose product we do not
  know: identical rules, but it must NOT contain {product}.
- "email_subject": under 60 characters, may use {name}, {offer}, {brand}, {occasion}.
- Never invent facts: no "new collection", "limited stock", prices or delivery
  promises unless the brief says so.

Reply with ONLY a JSON object with keys whatsapp, whatsapp_generic, email_subject."""


def _brief(ctx: dict) -> str:
    lines = [f"Shop name: {ctx.get('brand') or 'the shop'}",
             f"What the shop sells: {ctx.get('sells') or 'retail products'}",
             f"Campaign: {REASONS.get(ctx.get('reason'), ctx.get('reason'))}",
             f"Offer: {ctx.get('offer_label')}"]
    if ctx.get("reason") == "festival":
        lines.append(f"Festival: {ctx.get('occasion') or 'the festival'}")
    else:
        lines.append("Audience: customers who used to buy and have not ordered for a while.")
    if ctx.get("note"):
        lines.append(f"The owner wants to mention: {str(ctx['note'])[:300]}")
    return "\n".join(lines)


def _parse(text: str) -> dict | None:
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except (TypeError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def valid_template(t: str, allow_product: bool = True) -> bool:
    if not isinstance(t, str) or not t.strip() or len(t) > MAX_WHATSAPP:
        return False
    if any(p not in t for p in REQUIRED):
        return False
    if not allow_product and "{product}" in t:
        return False
    # anything in braces that is not one of ours would reach a customer as-is
    stray = [x for x in re.findall(r"\{[^{}]*\}", t) if x not in PLACEHOLDERS]
    return not stray


def write(email: str, ctx: dict) -> dict:
    """The campaign's message templates. Never raises; falls back to the
    hand-written copy when the AI is unavailable or its answer is unusable."""
    base = fallback_copy(ctx.get("reason") or "winback")
    try:
        from backend.core import aiprovider
        res = aiprovider.generate(_SYSTEM, _brief(ctx), sensitivity="public",
                                  max_tokens=500, temperature=0.8,
                                  role="writer", email=email, fallback="")
    except Exception as e:  # noqa: BLE001 — incl. a spent ChatGPT plan
        log.info("campaign copy fell back to templates: %s", e)
        return base
    d = _parse(res.get("text") or "")
    if not d:
        return base
    wa, gen, subj = d.get("whatsapp"), d.get("whatsapp_generic"), d.get("email_subject")
    out = dict(base)
    if valid_template(wa):
        out["whatsapp"] = wa.strip()
        out["source"] = res.get("provider") or "ai"
    if valid_template(gen, allow_product=False):
        out["whatsapp_generic"] = gen.strip()
    if isinstance(subj, str) and subj.strip() and len(subj) <= 90 and \
            not [x for x in re.findall(r"\{[^{}]*\}", subj) if x not in PLACEHOLDERS]:
        out["email_subject"] = subj.strip()
    return out


# ----------------------------------------------------------------------- fill
def fill(template: str, values: dict) -> str:
    out = template or ""
    for k in PLACEHOLDERS:
        out = out.replace(k, str(values.get(k.strip("{}")) or ""))
    # a message with no link leaves an empty last line; tidy the whitespace
    out = re.sub(r"[ \t]+\n", "\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    return out


def message_for(copy: dict, row: dict, ctx: dict) -> dict:
    """One customer's WhatsApp text and email subject."""
    product = row.get("product_display") or ""
    tpl = copy["whatsapp"] if product else copy["whatsapp_generic"]
    link = ctx.get("link") or ""
    if link and row.get("code"):
        link = f"{link}{'&' if '?' in link else '?'}code={row['code']}"
    values = {"name": first_name(row.get("customer_name")) or "there",
              "product": product, "offer": ctx.get("offer_label") or "",
              "code": row.get("code") or "", "expiry": ctx.get("expiry_label") or "",
              "link": link, "brand": ctx.get("brand") or "us",
              "occasion": ctx.get("occasion") or "the festival"}
    text = fill(tpl, values)
    # The AI works the seller's note into its own sentences; the hand-written
    # copy cannot, so the note goes in as its own line rather than being
    # silently dropped.
    note = (ctx.get("note") or "").strip()
    if note and copy.get("source") == "template" and note not in text:
        note = note[0].upper() + note[1:]
        note = note if note[-1] in ".!?" else note + "."
        if link and link in text:
            text = text.replace(link, f"{note}\n\n{link}", 1)
        else:
            text = f"{text}\n\n{note}"
    if link and link not in text:
        text = f"{text}\n\n{link}"
    subj_values = dict(values)
    if subj_values["name"] == "there":
        subj_values["name"] = "Hi"
    subject = fill(copy.get("email_subject") or "", subj_values)
    return {"message": text, "email_subject": subject[:120], "shop_link": link}
