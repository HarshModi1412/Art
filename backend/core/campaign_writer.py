"""
The words of a Marketing Campaign.

WHAT WAS WRONG
--------------
The old win-back bank (templates.py) was written for a café: "we've been
keeping a seat warm", "the {item} machine keeps asking where you went". Put a
clothing shop's product into that and a customer read

    "Simran A., the Chikankari Kurta, White machine keeps asking where you went."

Two faults in one line: copy for the wrong kind of shop, and the product's
VARIANT (", White", ", 6 ml") pasted into the middle of a sentence. Round one
fixed both, but sent every customer the SAME message, and a customer who sees
their friend's identical "personal" note stops believing either was personal.

HOW IT WORKS NOW
----------------
No AI per campaign, and no two neighbours with the same words. There are ten
hand-written VOICES for each kind of campaign (win back / festival). A voice
is not a template string but five parts:

    open     greeting, with the customer's first name
    bought   a line about what they actually bought most        (if known)
    pick     a suggestion from the shop's own association rules (if any)
    offer    the discount, their personal code and the last date
    close    sign-off, before the link

so a customer with no known product or no honest suggestion still gets a
complete message, never a sentence with a hole in it. Voices are dealt
round-robin in an order shuffled per campaign, so the ten are spread evenly and
two customers next to each other in the list never get the same one.

{pick} comes from analytics.association_rules (Apriori, ranked by lift) via
analytics.recommend_for: the item people who bought what this customer bought
also buy, that this customer has not bought yet. The wording around it is
deliberately neutral ("you might also like") because a fallback pick is a best
seller, not a rule, and the message must stay true either way.
"""
from __future__ import annotations

import random
import re


PLACEHOLDERS = ("{name}", "{product}", "{pick}", "{offer}", "{code}", "{expiry}", "{link}",
                "{brand}", "{occasion}", "{orders}", "{chatlink}")
MAX_MESSAGE = 1000

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


# --------------------------------------------------------------------- voices
# Fifty, in the founder's own voice: backend/core/founder_voices.py.
from backend.core.founder_voices import (  # noqa: E402
    CHAT_LINK, CTA_CHAT, CTA_CHAT_NONE, CTA_SITE, CTA_SITE_NONE, VOICES)

LABELS = {
    "winback": "Win back quiet customers",
    "festival": "Festival offer",
    "second_order": "Second-order nudge",
    "cross_sell": "Goes well with what you bought",
    "restock": "Time to restock",
    "vip": "VIP early access",
    "thank_you": "Thank you + review request",
}

def deal(campaign_id: str, n: int, reason: str = "winback") -> list[int]:
    """Which voice each of n customers gets: every voice used before any
    repeats, in an order shuffled per campaign, so the spread is even and two
    customers next to each other never share one."""
    k = len(VOICES.get(reason) or VOICES["winback"])
    order = list(range(k))
    random.Random(str(campaign_id)).shuffle(order)
    return [order[i % k] for i in range(n)]


# ----------------------------------------------------------------------- fill
def fill(template: str, values: dict) -> str:
    out = template or ""
    for k in PLACEHOLDERS:
        out = out.replace(k, str(values.get(k.strip("{}")) or ""))
    return out


def _sentence(note: str) -> str:
    note = note.strip()
    if not note:
        return ""
    note = note[0].upper() + note[1:]
    return note if note[-1] in ".!?" else note + "."


def signature(ctx: dict) -> tuple[str, str]:
    """(header line, sign-off) for the founder's note. With no founder name
    yet, it is still signed by a person: the founder of the shop."""
    founder = (ctx.get("founder") or "").strip()
    brand = ctx.get("brand") or "our shop"
    if founder:
        return f"_A personal note from {founder}, founder of {brand}_", f"{founder}, {brand}"
    return f"_A personal note from the founder of {brand}_", f"Founder, {brand}"


def message_for(row: dict, ctx: dict) -> dict:
    """One customer's WhatsApp/email text and email subject.

    Uses the customer's own edited message when the seller wrote one
    (`message_override`), otherwise their voice, built only from what is true
    about this customer: what they bought, how often, and a suggestion whose
    wording says where it came from (people who bought the same thing, or
    the shop's most-bought piece)."""
    reason = ctx.get("reason") or "winback"
    voices = VOICES.get(reason) or VOICES["winback"]
    vi = int(row.get("voice") or 0)
    v = voices[vi % len(voices)]
    product = row.get("product_display") or ""
    pick = row.get("pick_display") or ""
    kind = row.get("pick_kind") or ("pair" if reason == "cross_sell" else "best")
    pick_from = row.get("pick_from") or product
    if pick and pick in (product, pick_from):
        pick = ""
    if kind == "pair" and not pick_from:
        pick = ""                     # "people who bought the  also bought" is not a sentence
    orders = int(row.get("frequency") or 0)
    no_offer = (ctx.get("offer") or {}).get("kind") == "none"
    code = row.get("code") or ""
    link = ctx.get("link") or ""
    chatlink = ""
    if link and code:
        sep = "&" if "?" in link else "?"
        # A no-discount campaign's code only tracks: it rides as ref= so the
        # shop applies it quietly instead of announcing "your code".
        link = f"{link}{sep}{'ref' if no_offer else 'code'}={code}"
        if ctx.get("campaign_id"):
            link += f"&c={ctx['campaign_id']}"
    elif not link and code and ctx.get("chat_prefix"):
        # No website: the code is used by replying on WhatsApp, and this
        # tracked link (counted as the click) opens a chat with the shop.
        chatlink = f"{ctx['chat_prefix']}{code}"
    values = {"name": first_name(row.get("customer_name")) or "there",
              "product": product, "pick": pick, "offer": ctx.get("offer_label") or "",
              "code": code, "expiry": ctx.get("expiry_label") or "",
              "link": link, "brand": ctx.get("brand") or "us",
              "occasion": ctx.get("occasion") or "the festival",
              "orders": str(orders), "chatlink": chatlink}

    if (row.get("message_override") or "").strip():
        text = fill(row["message_override"].strip(), values)
        if chatlink and chatlink not in text:
            text = f"{text}\n\n{fill(CHAT_LINK, values)}"
    else:
        header, signoff = signature(ctx)
        first = [fill(v["open"], values)]
        if product:
            # Their product is the most personal detail, so it always stays;
            # for a regular, how often they ordered is added (or, when the
            # loyal line names the product itself, used instead).
            loyal = v.get("loyal") if orders >= 3 else ""
            if loyal and "{product}" in loyal:
                first.append(fill(loyal, values))
            else:
                if v.get("bought"):
                    first.append(fill(v["bought"], values))
                if loyal:
                    first.append(fill(loyal, values))
        if pick:
            line = v.get("pair") if kind == "pair" else v.get("best")
            if line:
                first.append(fill(line, {**values, "product": pick_from}))
        parts = [header, " ".join(p for p in first if p.strip()),
                 fill(v["none"] if no_offer else v["offer"], values)]
        note = _sentence(ctx.get("note") or "")
        if note:
            parts.append(note)
        if link:
            parts.append(fill((CTA_SITE_NONE if no_offer else CTA_SITE)[vi % 3], values))
        else:
            cta = (CTA_CHAT_NONE if (no_offer or not code) else CTA_CHAT)[vi % 3]
            parts.append(fill(cta, values) + (f"\n{fill(CHAT_LINK, values)}" if chatlink else ""))
        parts.append(f"{fill(v['close'], values)}\n{signoff}")
        text = "\n\n".join(p for p in parts if p.strip())
    if link and link not in text:
        text = f"{text}\n\n{link}"
    subj_values = dict(values)
    if subj_values["name"] == "there":
        subj_values["name"] = "Hi"
    subj = v["subject"]
    if no_offer and "{offer}" in subj:
        subj = "A note from me, {name}"
    if not product and "{product}" in subj:
        subj = "A personal note for you, {name}"
    subject = fill(subj, subj_values)
    return {"message": text.strip()[:MAX_MESSAGE], "email_subject": subject[:120],
            "shop_link": link or chatlink}


def valid_override(text: str, code: str, no_offer: bool = False) -> str:
    """The reason a seller's edit of one customer's message cannot be used,
    or "" when it can. The code is the one thing it must keep: without it the
    customer has an offer they cannot redeem."""
    t = (text or "").strip()
    if not t:
        return "The message is empty."
    if len(t) > MAX_MESSAGE:
        return f"Keep it under {MAX_MESSAGE} characters."
    if no_offer:
        return ""          # nothing to redeem: the tracking rides on {link}
    if code and code not in t and "{code}" not in t:
        return f"Keep the customer's code ({code}) in the message, or they cannot use the offer."
    return ""
