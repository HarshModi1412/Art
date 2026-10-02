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


# Campaign types beyond win-back and festival. Same five parts, plus
# `offer_none`: the line used when the campaign carries no discount.
SECOND_ORDER = [
    {"open": "Hi {name}, it's {brand}. Thank you again for your first order with us!",
     "bought": "We hope you're enjoying the {product}.",
     "pick": "A lot of our customers pick the {pick} next, we think you'd like it.",
     "offer": "For your second order, here's {offer}: use *{code}* by {expiry}.",
     "offer_none": "Whenever you're ready for the next one, we're right here.",
     "close": "Thank you for giving a small shop a try.",
     "subject": "Thank you for your first order, {name}"},
    {"open": "Hello {name}! {brand} here.",
     "bought": "It's been a few weeks since your {product} arrived, and we hope it's a favourite.",
     "pick": "If you're looking for something to go with it, the {pick} is a lovely choice.",
     "offer": "Your second order comes with {offer}. Code: *{code}*, valid till {expiry}.",
     "offer_none": "We'd love to help you find your next piece.",
     "close": "Warmly, the {brand} team",
     "subject": "{name}, a little something for your next order"},
    {"open": "Hi {name}, a quick hello from {brand}.",
     "bought": "We loved packing your first order, the {product}.",
     "pick": "Our pick for your next one: the {pick}.",
     "offer": "To make the next one easier: {offer} with *{code}* (till {expiry}).",
     "offer_none": "Have a look around whenever you like.",
     "close": "Just reply here if you need anything.",
     "subject": "We loved packing your first order"},
    {"open": "Dear {name}, welcome to the {brand} family.",
     "bought": "We hope the {product} was everything you hoped for.",
     "pick": "You might also love the {pick}.",
     "offer": "Here's {offer} on your next order with code *{code}*, till {expiry}.",
     "offer_none": "We'd be happy to see you again soon.",
     "close": "With love, {brand}",
     "subject": "Welcome to the {brand} family"},
    {"open": "Hey {name}! It's {brand}.",
     "bought": "How are you finding the {product}?",
     "pick": "People who loved it often come back for the {pick}.",
     "offer": "If you fancy a second order, {offer} is yours with *{code}* until {expiry}.",
     "offer_none": "We'd love to hear what you think, just reply here.",
     "close": "See you soon!",
     "subject": "How did we do, {name}?"},
    {"open": "Hi {name}, thank you for choosing {brand} for the first time.",
     "bought": "The {product} is one of our customers' favourites, great choice.",
     "pick": "Next, we think the {pick} would suit you.",
     "offer": "As a thank-you for coming back: {offer}, code *{code}*, valid till {expiry}.",
     "offer_none": "Whenever you're ready, we'd love to help you pick the next one.",
     "close": "Thank you for supporting a small business.",
     "subject": "A thank-you from {brand}"},
    {"open": "Hello {name}, it's {brand} checking in.",
     "bought": "We hope your {product} has been treating you well.",
     "pick": "If you're in the mood for something new, try the {pick}.",
     "offer": "We've saved {offer} for your second order. Use *{code}* before {expiry}.",
     "offer_none": "We're here whenever you'd like something new.",
     "close": "Have a lovely week!",
     "subject": "Checking in, {name}"},
    {"open": "Hi {name}! {brand} here, still smiling about your first order.",
     "bought": "Thank you for trusting us with the {product}.",
     "pick": "The {pick} might be the perfect next pick.",
     "offer": "Your next order gets {offer} with code *{code}* (till {expiry}).",
     "offer_none": "We'd love to see you again.",
     "close": "Warm wishes, {brand}",
     "subject": "Still smiling about your first order"},
    {"open": "Dear {name}, a short note from {brand}.",
     "bought": "We hope the {product} made you happy.",
     "pick": "Many people who buy it go on to love the {pick}.",
     "offer": "To welcome you back: {offer}. Your code *{code}* works till {expiry}.",
     "offer_none": "We'd be glad to have you back whenever you like.",
     "close": "Thank you for being here.",
     "subject": "A short note from {brand}"},
    {"open": "Hi {name}, it's {brand}. You're officially one of us now!",
     "bought": "Thanks again for the {product}.",
     "pick": "Here's one we think you'll love next: the {pick}.",
     "offer": "Enjoy {offer} on your second order with *{code}*, valid till {expiry}.",
     "offer_none": "Come and say hello again soon.",
     "close": "Big thanks from all of us.",
     "subject": "You're one of us now, {name}"},
]

CROSS_SELL = [
    {"open": "Hi {name}, it's {brand}.",
     "bought": "Since you have the {product},",
     "pick": "we think you'd love the {pick}: our customers often pair the two.",
     "offer": "Try it with {offer}, code *{code}*, valid till {expiry}.",
     "offer_none": "Have a look whenever you like.",
     "close": "Happy shopping!",
     "subject": "{name}, we found the perfect match"},
    {"open": "Hello {name}! A little idea from {brand}.",
     "bought": "Your {product}",
     "pick": "goes beautifully with the {pick}, a favourite combination with our customers.",
     "offer": "Here's {offer} if you'd like to complete the set. Use *{code}* by {expiry}.",
     "offer_none": "Thought you'd like to know.",
     "close": "Warmly, the {brand} team",
     "subject": "An idea for you from {brand}"},
    {"open": "Hi {name}, quick tip from {brand}.",
     "bought": "Customers who bought the {product}",
     "pick": "very often come back for the {pick}.",
     "offer": "If you'd like to try it, {offer} is yours with *{code}* (till {expiry}).",
     "offer_none": "Just in case you were looking for something to go with it.",
     "close": "Reply here if you have any questions.",
     "subject": "Customers like you also loved this"},
    {"open": "Dear {name}, we've been thinking about your last order at {brand}.",
     "bought": "The {product}",
     "pick": "would look lovely with the {pick}.",
     "offer": "To make it easy: {offer}, code *{code}*, until {expiry}.",
     "offer_none": "Have a look and see what you think.",
     "close": "With love, {brand}",
     "subject": "{name}, this would go lovely with yours"},
    {"open": "Hey {name}! {brand} here.",
     "bought": "Loving your {product}?",
     "pick": "Then you'll probably love the {pick} too, it's the most common pairing in our shop.",
     "offer": "Grab it with {offer}: *{code}*, valid till {expiry}.",
     "offer_none": "Worth a look!",
     "close": "See you soon!",
     "subject": "The most loved pairing in our shop"},
    {"open": "Hi {name}, this is {brand}.",
     "bought": "We noticed you have the {product}.",
     "pick": "The {pick} is what many of our customers choose to go with it.",
     "offer": "Here's {offer} to try it, with your code *{code}* until {expiry}.",
     "offer_none": "We think it's worth a look.",
     "close": "Thank you for shopping with us.",
     "subject": "A match for your {brand} favourite"},
    {"open": "Hello {name}, a styling note from {brand}.",
     "bought": "Pair your {product}",
     "pick": "with the {pick} for a look our customers love.",
     "offer": "Complete it with {offer}. Code *{code}*, till {expiry}.",
     "offer_none": "Have fun trying it out.",
     "close": "Warm wishes, {brand}",
     "subject": "A styling note for you, {name}"},
    {"open": "Hi {name}! {brand} with a suggestion just for you.",
     "bought": "Because you bought the {product},",
     "pick": "we picked the {pick} for you.",
     "offer": "Enjoy {offer} on it with *{code}* (valid till {expiry}).",
     "offer_none": "Let us know what you think.",
     "close": "Happy browsing!",
     "subject": "Picked for you, {name}"},
    {"open": "Dear {name}, greetings from {brand}.",
     "bought": "Owners of the {product}",
     "pick": "tell us the {pick} is the perfect companion.",
     "offer": "Here's {offer} to try it, code *{code}*, until {expiry}.",
     "offer_none": "We think you'll agree.",
     "close": "Thank you for being a customer.",
     "subject": "The perfect companion"},
    {"open": "Hi {name}, it's {brand}.",
     "bought": "You've got the {product},",
     "pick": "and the {pick} is the one our customers most often add next.",
     "offer": "Add it with {offer}: *{code}*, valid till {expiry}.",
     "offer_none": "Whenever you're ready, it's waiting.",
     "close": "Thank you!",
     "subject": "{name}, the one people add next"},
]

RESTOCK = [
    {"open": "Hi {name}, it's {brand}.",
     "bought": "It's been about the usual time since your last {product}, so it might be running low.",
     "pick": "",
     "offer": "Restock with {offer}: use *{code}* by {expiry}.",
     "offer_none": "Restock whenever you're ready, it's in stock.",
     "close": "Thank you for coming back to us.",
     "subject": "Running low, {name}?"},
    {"open": "Hello {name}! A friendly reminder from {brand}.",
     "bought": "Your {product} might be close to finishing.",
     "pick": "",
     "offer": "Here's {offer} on your restock with code *{code}*, till {expiry}.",
     "offer_none": "We have it ready whenever you need it.",
     "close": "Warmly, the {brand} team",
     "subject": "A friendly reminder from {brand}"},
    {"open": "Hi {name}, {brand} here.",
     "bought": "Customers usually come back for the {product} around now.",
     "pick": "",
     "offer": "Stock up with {offer}. Your code *{code}* works till {expiry}.",
     "offer_none": "Tap below to get it again in a minute.",
     "close": "Just reply if you'd like any help.",
     "subject": "Time for your {brand} restock?"},
    {"open": "Dear {name}, hope you're well. It's {brand}.",
     "bought": "We thought you might be needing a fresh {product} soon.",
     "pick": "",
     "offer": "Here's {offer} to make it easy: *{code}*, valid till {expiry}.",
     "offer_none": "Order whenever suits you.",
     "close": "With love, {brand}",
     "subject": "{name}, need a fresh one?"},
    {"open": "Hey {name}! {brand} here.",
     "bought": "Is your {product} running out?",
     "pick": "",
     "offer": "Top up with {offer} using *{code}* (till {expiry}).",
     "offer_none": "It's one tap away.",
     "close": "See you soon!",
     "subject": "Running out, {name}?"},
    {"open": "Hi {name}, it's {brand} with a quick reminder.",
     "bought": "Based on your last order, you might be due for more {product}.",
     "pick": "",
     "offer": "Restock with {offer}, code *{code}*, until {expiry}.",
     "offer_none": "We're ready when you are.",
     "close": "Thank you!",
     "subject": "A quick reminder from {brand}"},
    {"open": "Hello {name}, from all of us at {brand}.",
     "bought": "Don't run out of your {product}!",
     "pick": "",
     "offer": "Here's {offer} for your next one. Code *{code}*, valid till {expiry}.",
     "offer_none": "It's in stock and ready to go.",
     "close": "Warm wishes, {brand}",
     "subject": "Don't run out, {name}"},
    {"open": "Hi {name}! {brand} here.",
     "bought": "Time flies: it's about time for a new {product}.",
     "pick": "",
     "offer": "Treat yourself with {offer}: *{code}* works till {expiry}.",
     "offer_none": "Order it again in a few taps.",
     "close": "Thank you for being a regular.",
     "subject": "Time flies, {name}"},
    {"open": "Dear {name}, a short note from {brand}.",
     "bought": "Your {product} may be running low by now.",
     "pick": "",
     "offer": "Restock with {offer} using *{code}* before {expiry}.",
     "offer_none": "We'd be happy to send you another.",
     "close": "Thank you for shopping with us.",
     "subject": "A short note from {brand}"},
    {"open": "Hi {name}, it's {brand}.",
     "bought": "Ready for another {product}?",
     "pick": "",
     "offer": "Here's {offer} with *{code}* (valid till {expiry}).",
     "offer_none": "It's waiting for you.",
     "close": "See you soon!",
     "subject": "Ready for another, {name}?"},
]

VIP = [
    {"open": "Hi {name}, it's {brand}. You're one of our very best customers, so you hear first.",
     "bought": "Thank you for every order, including the {product}.",
     "pick": "We think you'll love the {pick} too.",
     "offer": "As a thank-you: {offer} with your code *{code}*, till {expiry}.",
     "offer_none": "Have a look before anyone else does.",
     "close": "Thank you for being with us.",
     "subject": "{name}, you hear it first"},
    {"open": "Hello {name}! A private note from {brand} to our favourite customers.",
     "bought": "You've been with us since the {product}, and we're grateful.",
     "pick": "One we'd love you to see: the {pick}.",
     "offer": "Here's {offer}, just for you: *{code}*, valid till {expiry}.",
     "offer_none": "You get first look, before we tell anyone else.",
     "close": "Warmly, the {brand} team",
     "subject": "A private note for you, {name}"},
    {"open": "Hi {name}, {brand} here with early access for you.",
     "bought": "Customers who loved the {product} get to see this first.",
     "pick": "You might especially like the {pick}.",
     "offer": "Your VIP code *{code}* gives you {offer} till {expiry}.",
     "offer_none": "Take a look before it opens to everyone.",
     "close": "Enjoy!",
     "subject": "Early access for you, {name}"},
    {"open": "Dear {name}, you're on our VIP list at {brand}.",
     "bought": "Thank you for choosing us again and again, from the {product} on.",
     "pick": "Here's one we picked for you: the {pick}.",
     "offer": "Enjoy {offer} with code *{code}*, until {expiry}.",
     "offer_none": "As a VIP, you're the first to know.",
     "close": "With love, {brand}",
     "subject": "You're on our VIP list"},
    {"open": "Hey {name}! Before anyone else hears about it, we wanted to tell you.",
     "bought": "You've got great taste: the {product} proved it.",
     "pick": "So we think you'll love the {pick}.",
     "offer": "VIP perk: {offer} with *{code}* (till {expiry}).",
     "offer_none": "Have a look, you're first in line.",
     "close": "See you soon! Love, {brand}",
     "subject": "Before anyone else, {name}"},
    {"open": "Hi {name}, it's {brand}. Our best customers always get the first look.",
     "bought": "That includes you, thanks to orders like your {product}.",
     "pick": "One to look out for: the {pick}.",
     "offer": "Here's {offer} too, code *{code}*, valid till {expiry}.",
     "offer_none": "This is your first look.",
     "close": "Thank you for everything.",
     "subject": "Your first look, from {brand}"},
    {"open": "Hello {name}, thank you for being one of {brand}'s most loyal customers.",
     "bought": "From the {product} to every order since, it means a lot.",
     "pick": "We set aside a moment to show you the {pick}.",
     "offer": "Please enjoy {offer} with *{code}* until {expiry}.",
     "offer_none": "You're seeing this before anyone else.",
     "close": "Gratefully, {brand}",
     "subject": "Thank you for being loyal, {name}"},
    {"open": "Hi {name}! You're invited: early access at {brand}.",
     "bought": "Because you loved the {product},",
     "pick": "we think the {pick} will be right up your street.",
     "offer": "Your invite comes with {offer}: *{code}*, till {expiry}.",
     "offer_none": "Your invite is below.",
     "close": "Enjoy the first look!",
     "subject": "You're invited, {name}"},
    {"open": "Dear {name}, a first look for a favourite customer, from {brand}.",
     "bought": "Thank you for the {product} and every order since.",
     "pick": "We'd love to know what you think of the {pick}.",
     "offer": "Here's {offer} with code *{code}*, valid till {expiry}.",
     "offer_none": "Have a look and tell us what you think.",
     "close": "With love, {brand}",
     "subject": "A first look, just for you"},
    {"open": "Hi {name}, it's {brand}. VIPs first, always.",
     "bought": "You've been part of our story since the {product}.",
     "pick": "Here's one we're excited for you to see: the {pick}.",
     "offer": "VIP code *{code}*: {offer}, till {expiry}.",
     "offer_none": "You're getting this before everyone else.",
     "close": "Thank you for being here.",
     "subject": "VIPs first, {name}"},
]

THANK_YOU = [
    {"open": "Hi {name}, it's {brand}. Thank you so much for your order!",
     "bought": "We hope the {product} arrived safely and you love it.",
     "pick": "",
     "offer": "Here's {offer} on your next order as a thank-you: *{code}*, till {expiry}.",
     "offer_none": "If you have a moment, reply with a line about how you like it, or a photo. It helps other customers more than anything.",
     "close": "Thank you for supporting a small business.",
     "subject": "Thank you for your order, {name}"},
    {"open": "Hello {name}! A big thank-you from everyone at {brand}.",
     "bought": "How are you finding the {product}?",
     "pick": "",
     "offer": "As a thank-you, take {offer} next time with *{code}* (till {expiry}).",
     "offer_none": "We'd love a quick review: just reply here with what you think.",
     "close": "Warmly, the {brand} team",
     "subject": "How did we do, {name}?"},
    {"open": "Hi {name}, {brand} here.",
     "bought": "Your {product} should be with you by now.",
     "pick": "",
     "offer": "Here's {offer} for next time: code *{code}*, valid till {expiry}.",
     "offer_none": "If anything isn't perfect, reply here and we'll fix it. And if you love it, we'd be grateful for a review.",
     "close": "Thank you!",
     "subject": "Did your order arrive safely?"},
    {"open": "Dear {name}, thank you for choosing {brand}.",
     "bought": "We packed your {product} with care, and we hope it shows.",
     "pick": "",
     "offer": "A small thank-you: {offer} with *{code}* until {expiry}.",
     "offer_none": "Would you share a photo or a few words about it? Just reply here.",
     "close": "With love, {brand}",
     "subject": "Thank you for choosing {brand}"},
    {"open": "Hey {name}! It's {brand}.",
     "bought": "Hope you're loving the {product}!",
     "pick": "",
     "offer": "Next time, {offer} is yours with *{code}* (till {expiry}).",
     "offer_none": "Tell us what you think, a one-line reply helps us a lot.",
     "close": "Thanks again!",
     "subject": "Loving it, {name}?"},
    {"open": "Hi {name}, thank you for your recent order with {brand}.",
     "bought": "We'd love to hear how the {product} is working out.",
     "pick": "",
     "offer": "Here's {offer} for your next order: *{code}*, valid till {expiry}.",
     "offer_none": "Your feedback, good or bad, helps us get better. Just reply here.",
     "close": "Thank you for shopping small.",
     "subject": "We'd love your feedback, {name}"},
    {"open": "Hello {name}, from all of us at {brand}: thank you!",
     "bought": "Orders like your {product} keep our small shop going.",
     "pick": "",
     "offer": "As thanks, here's {offer} with *{code}* until {expiry}.",
     "offer_none": "If you're happy with it, a quick review would mean the world to us.",
     "close": "Warm wishes, {brand}",
     "subject": "From all of us: thank you"},
    {"open": "Hi {name}! Just checking in from {brand}.",
     "bought": "Is the {product} everything you hoped for?",
     "pick": "",
     "offer": "Here's {offer} on your next one: code *{code}*, till {expiry}.",
     "offer_none": "Reply with a photo of it in use, we'd love to see it.",
     "close": "Thank you!",
     "subject": "Just checking in, {name}"},
    {"open": "Dear {name}, a quick thank-you note from {brand}.",
     "bought": "We hope the {product} is already a favourite.",
     "pick": "",
     "offer": "Please enjoy {offer} next time, with *{code}* until {expiry}.",
     "offer_none": "If you have a minute, we'd be grateful for a short review.",
     "close": "With gratitude, {brand}",
     "subject": "A thank-you note from {brand}"},
    {"open": "Hi {name}, it's {brand}. Thank you for shopping with us!",
     "bought": "Enjoy your {product}.",
     "pick": "",
     "offer": "Here's {offer} for your next order: *{code}*, valid till {expiry}.",
     "offer_none": "If you love it, tell us (and others) with a quick review. Just reply here.",
     "close": "See you again soon!",
     "subject": "Thank you for shopping with us, {name}"},
]

# Win-back and festival had no no-discount line; one per voice, by index.
_OFFER_NONE = {
    "winback": ["We'd love to see you again.", "Have a look whenever you're ready.",
                "Whenever you're ready, we're right here.", "We'd be happy to help you find something new.",
                "Come and say hello again soon."],
    "festival": ["Have a look at what we have for {occasion}.", "Celebrate with something special from us.",
                 "We'd love to be part of your {occasion}.", "Have a look whenever you're ready.",
                 "Wishing you the very best this season."],
}
_SUBJECT_NONE = {
    "winback": "{name}, we've missed you", "festival": "Happy {occasion}, {name}",
}

LABELS = {
    "winback": "Win back quiet customers",
    "festival": "Festival offer",
    "second_order": "Second-order nudge",
    "cross_sell": "Goes well with what you bought",
    "restock": "Time to restock",
    "vip": "VIP early access",
    "thank_you": "Thank you + review request",
}

VOICES = {"winback": WINBACK, "festival": FESTIVAL, "second_order": SECOND_ORDER,
          "cross_sell": CROSS_SELL, "restock": RESTOCK, "vip": VIP, "thank_you": THANK_YOU}
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
    no_offer = (ctx.get("offer") or {}).get("kind") == "none"
    link = ctx.get("link") or ""
    if link and row.get("code"):
        sep = "&" if "?" in link else "?"
        # A no-discount campaign's code only tracks: it rides as ref= so the
        # shop applies it quietly instead of announcing "your code".
        link = f"{link}{sep}{'ref' if no_offer else 'code'}={row['code']}"
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
        if pick and v.get("pick"):
            first.append(fill(v["pick"], values))
        if no_offer:
            line = v.get("offer_none") or _OFFER_NONE.get(reason, _OFFER_NONE["winback"])[
                int(row.get("voice") or 0) % 5]
        else:
            line = v["offer"]
        parts = [" ".join(p for p in first if p.strip()), fill(line, values)]
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
    subj = v["subject"]
    if no_offer and "{offer}" in subj:
        subj = _SUBJECT_NONE.get(reason, "A note from {brand}")
    subject = fill(subj, subj_values)
    return {"message": text.strip()[:MAX_MESSAGE], "email_subject": subject[:120],
            "shop_link": link}


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
