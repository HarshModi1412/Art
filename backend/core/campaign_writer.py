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

REASONS = {
    "winback": "Win back customers who have gone quiet",
    "festival": "Festival offer for your best customers",
}

PLACEHOLDERS = ("{name}", "{product}", "{pick}", "{offer}", "{code}", "{expiry}", "{link}",
                "{brand}", "{occasion}")
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
# Ten per kind. Each part must read on its own: `bought` and `pick` are left
# out when unknown, so `open` must never lean on them.
WINBACK = [
    {"open": "Hi {name}, it's {brand}. It has been a little while, and we wanted to say we've missed you.",
     "bought": "We still remember the {product} you picked.",
     "pick": "If you're looking for something new, we think you'd love the {pick}.",
     "offer": "Here's {offer} on your next order, just for you. Your code is *{code}*, valid till {expiry}.",
     "close": "Hope to see you soon!",
     "subject": "{name}, we've missed you: {offer} inside"},
    {"open": "Hello {name}! {brand} here.",
     "bought": "Thank you for choosing the {product} with us before, it meant a lot to a small shop like ours.",
     "pick": "Customers with your taste have been loving the {pick} lately.",
     "offer": "As a thank-you, take {offer} with your personal code *{code}*. It's yours till {expiry}.",
     "close": "Warmly, the {brand} team",
     "subject": "A thank-you from {brand}"},
    {"open": "Hi {name}, a quick note from {brand}.",
     "bought": "Your {product} order is one of our favourite memories of this year.",
     "pick": "The {pick} might be the perfect next pick for you.",
     "offer": "We've saved {offer} for you: use *{code}* at checkout before {expiry}.",
     "close": "No pressure at all, we just wanted you to have it.",
     "subject": "Saved for you, {name}: {offer}"},
    {"open": "Dear {name}, greetings from {brand}.",
     "bought": "We hope the {product} is still a favourite.",
     "pick": "When you're ready for something new, have a look at the {pick}.",
     "offer": "Your next order comes with {offer}. Code: *{code}*, valid till {expiry}.",
     "close": "With love, {brand}",
     "subject": "{name}, something special from {brand}"},
    {"open": "Hey {name}! It's {brand}, and it's been too long.",
     "bought": "Fancy another {product}?",
     "pick": "Or try the {pick}, it's been a hit with people who shop like you.",
     "offer": "Either way, {offer} is waiting for you with code *{code}* (till {expiry}).",
     "close": "See you soon!",
     "subject": "It's been too long, {name}"},
    {"open": "Hi {name}, this is {brand}.",
     "bought": "We loved packing your {product} for you, and we'd love to do it again.",
     "pick": "Our pick for you this time: the {pick}.",
     "offer": "Here's {offer} to make it easy. Your code *{code}* works till {expiry}.",
     "close": "Thank you for being part of our story.",
     "subject": "We'd love to pack your next order, {name}"},
    {"open": "Hello {name}, it's {brand}.",
     "bought": "You have great taste: the {product} is one of our most loved pieces.",
     "pick": "We think the {pick} would suit you just as well.",
     "offer": "Treat yourself with {offer}, using code *{code}* before {expiry}.",
     "close": "Always happy to help if you have questions.",
     "subject": "{offer} for you, {name}"},
    {"open": "Hi {name}! A little hello from {brand}.",
     "bought": "Since you liked the {product}, we kept you in mind.",
     "pick": "The {pick} is one we think you'll enjoy next.",
     "offer": "Your exclusive code *{code}* gives you {offer}, valid till {expiry}.",
     "close": "Just reply here if you'd like any help choosing.",
     "subject": "Your exclusive code from {brand}"},
    {"open": "Dear {name}, we've been thinking of our favourite customers at {brand}, and you're one of them.",
     "bought": "Thank you again for the {product} order.",
     "pick": "You might also like the {pick}.",
     "offer": "To welcome you back: {offer} with code *{code}*, till {expiry}.",
     "close": "Hope you're doing well!",
     "subject": "One of our favourite customers: {name}"},
    {"open": "Hi {name}, {brand} here with something just for you.",
     "bought": "Remember the {product}? We'd love to help you find your next favourite.",
     "pick": "The {pick} is a lovely place to start.",
     "offer": "Use *{code}* for {offer}. It's personal to you and works till {expiry}.",
     "close": "Thank you for shopping small with us.",
     "subject": "Something just for you, {name}"},
]

FESTIVAL = [
    {"open": "Hi {name}, {occasion} is almost here, and everyone at {brand} wishes you a beautiful one.",
     "bought": "Since you loved the {product}, we wanted you to hear from us first.",
     "pick": "For {occasion}, we think the {pick} would be perfect for you.",
     "offer": "Celebrate with {offer}: your code is *{code}*, valid till {expiry}.",
     "close": "Happy {occasion}!",
     "subject": "Happy {occasion}, {name}: {offer} for you"},
    {"open": "Happy {occasion} in advance, {name}! It's {brand}.",
     "bought": "Thank you for bringing home the {product} with us.",
     "pick": "This {occasion}, the {pick} could be a lovely addition.",
     "offer": "As one of our favourite customers, you get {offer} with code *{code}* till {expiry}.",
     "close": "Wishing you and your family a wonderful {occasion}.",
     "subject": "Your {occasion} gift from {brand}"},
    {"open": "Hello {name}! {occasion} is around the corner.",
     "bought": "We hope the {product} is ready for the celebrations.",
     "pick": "If you're planning something new, have a look at the {pick}.",
     "offer": "{brand} has saved {offer} for you: use *{code}* before {expiry}.",
     "close": "With warm {occasion} wishes, {brand}",
     "subject": "{occasion} is almost here, {name}"},
    {"open": "Dear {name}, warm {occasion} wishes from all of us at {brand}.",
     "bought": "Customers like you, who chose the {product}, make this season special for us.",
     "pick": "We think you'd love the {pick} this {occasion}.",
     "offer": "Here's {offer} for your {occasion} shopping. Code: *{code}*, till {expiry}.",
     "close": "Have a joyful {occasion}!",
     "subject": "Warm {occasion} wishes from {brand}"},
    {"open": "Hi {name}! Getting ready for {occasion}?",
     "bought": "The {product} you chose last time was one of our favourites too.",
     "pick": "For the festive look, the {pick} is our pick for you.",
     "offer": "{brand} is giving you {offer} with your own code *{code}* (valid till {expiry}).",
     "close": "Happy celebrating!",
     "subject": "Getting ready for {occasion}, {name}?"},
    {"open": "Hello {name}, this is {brand}, wishing you a very happy {occasion}.",
     "bought": "Thank you for your {product} order, it's customers like you who keep us going.",
     "pick": "You might also like the {pick} for the festivities.",
     "offer": "Our {occasion} thank-you: {offer} with code *{code}* until {expiry}.",
     "close": "Warmly, {brand}",
     "subject": "Our {occasion} thank-you to you, {name}"},
    {"open": "Hi {name}, {occasion} is the perfect time to treat yourself.",
     "bought": "You've got great taste: the {product} proves it.",
     "pick": "The {pick} might be just the thing this {occasion}.",
     "offer": "Here's {offer} from {brand}. Your code *{code}* works till {expiry}.",
     "close": "Happy {occasion}!",
     "subject": "Treat yourself this {occasion}, {name}"},
    {"open": "Dear {name}, as {occasion} comes closer, we're thinking of the people who made our year at {brand}.",
     "bought": "Your {product} order was one of them.",
     "pick": "We think the {pick} would make a lovely {occasion} pick.",
     "offer": "Please enjoy {offer} with code *{code}*, valid till {expiry}.",
     "close": "Wishing you light and joy.",
     "subject": "{name}, you made our year"},
    {"open": "Hey {name}! {brand} here with an early {occasion} surprise.",
     "bought": "Loved the {product}? There's more where that came from.",
     "pick": "Our suggestion for you: the {pick}.",
     "offer": "Your surprise is {offer}, with code *{code}* until {expiry}.",
     "close": "Happy {occasion} in advance!",
     "subject": "An early {occasion} surprise"},
    {"open": "Hi {name}, wishing you a happy {occasion} from {brand}.",
     "bought": "Thank you for choosing the {product} with us.",
     "pick": "This season, the {pick} is one we think you'll love.",
     "offer": "Celebrate with {offer}: your personal code *{code}* works till {expiry}.",
     "close": "Just reply here if you'd like help picking something.",
     "subject": "{offer} this {occasion}, {name}"},
]

VOICES = {"winback": WINBACK, "festival": FESTIVAL}
assert all(len(v) == 10 for v in VOICES.values())


def deal(campaign_id: str, n: int, reason: str = "winback") -> list[int]:
    """Which voice each of n customers gets: every voice used before any
    repeats, in an order shuffled per campaign, so the spread is even and two
    customers next to each other never share one."""
    k = len(VOICES.get(reason) or WINBACK)
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


def message_for(row: dict, ctx: dict) -> dict:
    """One customer's WhatsApp/email text and email subject.

    Uses the customer's own edited message when the seller wrote one
    (`message_override`), otherwise their voice."""
    reason = ctx.get("reason") or "winback"
    voices = VOICES.get(reason) or WINBACK
    v = voices[int(row.get("voice") or 0) % len(voices)]
    product = row.get("product_display") or ""
    pick = row.get("pick_display") or ""
    if pick and pick == product:
        pick = ""
    link = ctx.get("link") or ""
    if link and row.get("code"):
        sep = "&" if "?" in link else "?"
        link = f"{link}{sep}code={row['code']}"
        if ctx.get("campaign_id"):
            link += f"&c={ctx['campaign_id']}"
    values = {"name": first_name(row.get("customer_name")) or "there",
              "product": product, "pick": pick, "offer": ctx.get("offer_label") or "",
              "code": row.get("code") or "", "expiry": ctx.get("expiry_label") or "",
              "link": link, "brand": ctx.get("brand") or "us",
              "occasion": ctx.get("occasion") or "the festival"}

    if (row.get("message_override") or "").strip():
        text = fill(row["message_override"].strip(), values)
    else:
        first = [fill(v["open"], values)]
        if product:
            first.append(fill(v["bought"], values))
        if pick:
            first.append(fill(v["pick"], values))
        parts = [" ".join(first), fill(v["offer"], values)]
        note = _sentence(ctx.get("note") or "")
        if note:
            parts.append(note)
        parts.append(fill(v["close"], values))
        if link:
            parts.append(link)
        text = "\n\n".join(p for p in parts if p.strip())
    if link and link not in text:
        text = f"{text}\n\n{link}"
    subj_values = dict(values)
    if subj_values["name"] == "there":
        subj_values["name"] = "Hi"
    subject = fill(v["subject"], subj_values)
    return {"message": text.strip()[:MAX_MESSAGE], "email_subject": subject[:120],
            "shop_link": link}


def valid_override(text: str, code: str) -> str:
    """The reason a seller's edit of one customer's message cannot be used,
    or "" when it can. The code is the one thing it must keep: without it the
    customer has an offer they cannot redeem."""
    t = (text or "").strip()
    if not t:
        return "The message is empty."
    if len(t) > MAX_MESSAGE:
        return f"Keep it under {MAX_MESSAGE} characters."
    if code and code not in t and "{code}" not in t:
        return f"Keep the customer's code ({code}) in the message, or they cannot use the offer."
    return ""
