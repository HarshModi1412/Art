"""
The approval panel, staffed.

WHY
---
A seller reading "Reorder 4 items below reorder point" has to work out who
would normally have told them that, whether it is urgent, and what happens if
they ignore it. Every card costs them that thinking, and the panel becomes a
list of chores rather than a team.

Attributing each card to a named manager does three things a bare list cannot:

  * it says which part of the business the card is about before the seller
    reads a word of it;
  * it sets the register. A manager makes a RECOMMENDATION and then explains
    it. A dashboard states a fact and leaves the seller to infer the action;
  * it makes the product's real claim legible — that a seller running alone
    is getting the functions a bigger company would hire for.

WHY THE COPY IS WRITTEN, NOT GENERATED
--------------------------------------
It would be easy to send each card through an LLM and ask for "a marketing
manager's voice". That would be slower, non-deterministic, cost money on every
panel render, and produce worse copy than writing it once by hand. The
templates below interpolate the seller's real numbers into sentences a
competent manager would actually say.

THE VOICE
---------
Recommendation first, reasoning second, and never hedged into uselessness. A
good manager says "reorder these four, you have eleven days of cover and your
supplier takes fourteen" — not "inventory levels may warrant attention."
No exclamation marks, no "Great news!", no pretending a small number is a
crisis. Where the data is thin, the manager says so rather than bluffing.

TWO LENGTHS
-----------
The approval panel is a narrow column beside the workspace. A five-line
paragraph there is a wall of text that gets skipped, which defeats the whole
exercise. So every card carries:

  * `body` — one sentence, under about 140 characters. The recommendation and
    the single number that justifies it. This is what the panel shows.
  * `why`  — the full reasoning. Lives behind Details, for the seller who wants
    to know before they press the button.

Cutting the panel text is not dumbing it down; it is putting the argument where
someone has room to read it.
"""
from __future__ import annotations

MANAGERS = {
    "social": {
        "id": "social", "name": "Social Media Manager", "short": "Social",
        "icon": "spark", "colour": "#7b5ea7",
        "remit": "What goes out on Instagram, and when.",
    },
    "operations": {
        "id": "operations", "name": "Operations Manager", "short": "Ops",
        "icon": "package", "colour": "#4d6d9e",
        "remit": "Stock levels, order quantities, and what is about to run out "
                 "or is sitting too long.",
    },
    "supply": {
        "id": "supply", "name": "Supply Chain Manager", "short": "Supply",
        "icon": "truck", "colour": "#3f7d63",
        "remit": "Who you buy from, what it costs, and where you are exposed.",
    },
    "marketing": {
        "id": "marketing", "name": "Marketing Manager", "short": "Marketing",
        "icon": "trend", "colour": "#96702f",
        "remit": "Getting customers back, and getting ahead of the calendar.",
    },
    "brand": {
        "id": "brand", "name": "Brand Manager", "short": "Brand",
        "icon": "star", "colour": "#a85450",
        "remit": "What people say about you, and what to fix because of it.",
    },
}

ORDER = ["operations", "marketing", "supply", "brand", "social"]

# Which manager owns which card. Matched on the insight id first, then the
# module, so a new card gets a sensible desk even before anyone writes copy
# for it.
BY_ID = {
    "winback": "marketing",
    "festival": "marketing",
    "reorder": "operations",
    "overstock": "operations",
    "supplier_risk": "supply",
    "reputation": "brand",
    "complaints": "brand",
}
BY_MODULE = {
    "sales": "marketing", "review": "brand", "supply": "operations",
    "content": "social", "social": "social", "site": "operations",
}


def assign(card: dict) -> str:
    cid = str(card.get("id") or "")
    if cid in BY_ID:
        return BY_ID[cid]
    for prefix, who in (("content_", "social"), ("post_", "social"), ("autoplan_", "social"),
                        ("po_", "supply"),
                        ("supplier_", "supply"), ("stock_", "operations")):
        if cid.startswith(prefix):
            return who
    return BY_MODULE.get(str(card.get("module") or ""), "operations")


def _n(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _rupees(v) -> str:
    try:
        n = float(v)
    except (TypeError, ValueError):
        return ""
    if n >= 100000:
        return f"Rs {n / 100000:.1f}L"
    if n >= 1000:
        return f"Rs {n / 1000:.0f}k"
    return f"Rs {n:.0f}"


# ---------------------------------------------------------------------------
# The copy. One function per card type: takes the raw card, returns what the
# manager says. Keeping these as functions rather than format strings lets a
# card change its whole argument when the numbers change — which is what a
# real manager does, and what a template cannot.
# ---------------------------------------------------------------------------

def _winback(card: dict) -> dict:
    n = _n(card.get("count"))
    value = card.get("value")
    worth = f" worth {_rupees(value)}" if value else ""
    return {
        "headline": f"Win back {n} quiet customers",
        "body": f"{n} regulars{worth} have stopped coming. List and messages ready.",
        "why": (f"{n} people who used to buy regularly have not been back in a "
                f"while.{' They are worth ' + _rupees(value) + ' of past business.' if value else ''} "
                f"I have the list and a message written for each one. This is "
                f"cheaper than discounting everybody, and I will tell you in 30 "
                f"days how much actually came back."),
        "cta": "Send the win-back",
    }


def _festival(card: dict) -> dict:
    fest = card.get("festival") or "the next festival"
    days = _n(card.get("days_away"))
    start = card.get("start_on") or ""
    late = bool(card.get("act_now"))
    return {
        "headline": f"Start the {fest} campaign",
        "body": (f"{fest} is {days} days out — "
                 + ("we are already late." if late else f"posting starts {start}.")),
        "why": (f"{fest} is {days} days away. "
                + ("We are already inside the window, so this should have started."
                   if late else f"Posting should start on {start}.")
                + f" I have built a plan around your festival stock and the "
                  f"customers most likely to buy it. Worth knowing: ad costs "
                  f"climb hard from mid-September as everyone piles in, so the "
                  f"cheap audience-building happens now, not in the last week."),
        "cta": "Build the campaign",
    }


def _reorder(card: dict) -> dict:
    n = _n(card.get("count"))
    names = card.get("names") or ""
    cover = card.get("min_cover")
    return {
        "headline": f"Order {n} item{'s' if n != 1 else ''} before we run out",
        "body": (f"{_n(cover)} days of cover left on the tightest. Quantities worked out."
                 if cover else f"{names[:60]} at or below reorder point."),
        "why": (f"{names} {'are' if n != 1 else 'is'} down to fewer days of supply "
                f"than 1.2 × the supplier's lead time, and no order is on its way."
                + (f" The tightest is down to {_n(cover)} days of cover." if cover else "")
                + f" Each quantity is the default order quantity — the supplier's "
                  f"minimum, or the economic order quantity once your ordering and "
                  f"holding costs are in. Approve and I will draft one purchase "
                  f"order per supplier for you to check and send."),
        "cta": "Draft the purchase orders",
    }


def _overstock(card: dict) -> dict:
    n = _n(card.get("count"))
    names = card.get("names") or ""
    cash = card.get("tied_up")
    return {
        "headline": f"Too much stock on {n} item{'s' if n != 1 else ''}",
        "body": (f"About {_rupees(cash)} sitting still. Stop reordering, or push them."
                 if cash else f"{names[:60]} — far more cover than sales justify."),
        "why": (f"{names} {'have' if n != 1 else 'has'} far more cover than the "
                f"sales rate justifies."
                + (f" That is roughly {_rupees(cash)} sitting still." if cash else "")
                + " Nothing is going wrong, but that is working capital doing "
                  "nothing and stock that ages. Either stop reordering these for "
                  "now, or push them — a bundle or a feature slot moves them "
                  "faster than a discount does."),
        "cta": "Review what we are holding",
    }


def _supplier_risk(card: dict) -> dict:
    n = _n(card.get("count"))
    names = card.get("names") or ""
    return {
        "headline": f"Find a second supplier for {n} item{'s' if n != 1 else ''}",
        "body": "One supplier, no backup and no price benchmark.",
        "why": (f"{names} {'come' if n != 1 else 'comes'} from a single supplier "
                f"with nothing behind {'them' if n != 1 else 'it'}. If they raise "
                f"prices, miss a delivery or simply stop answering, we have no "
                f"second option and no benchmark to tell whether the price is "
                f"fair. I would get quotes from two alternatives before the next "
                f"reorder rather than during a stockout."),
        "cta": "Start sourcing alternatives",
    }


def _reputation(card: dict) -> dict:
    n = _n(card.get("count"))
    return {
        "headline": "Sharpen how we are positioned",
        "body": f"{n} move{'s' if n != 1 else ''} from what your reviews already say.",
        "why": (f"Your reviews say something fairly specific about what people "
                f"come to you for. I have {n} move{'s' if n != 1 else ''} that "
                f"would make that clearer — on the website, in the listings and "
                f"in what we lead with. This is the difference between being "
                f"chosen for a reason and being chosen on price."),
        "cta": "See the positioning plan",
    }


def _complaints(card: dict) -> dict:
    n = _n(card.get("count"))
    return {
        "headline": f"Fix the {n} complaint{'s' if n != 1 else ''} costing us most",
        "body": "Ranked by how often and how badly. Mostly fixable this week.",
        "why": (f"These are the themes doing real damage right now, ranked by how "
                f"often they come up against how badly they land. Most of them are "
                f"operational rather than about the product, which means they are "
                f"fixable this week. I would rather we fix the top {n} properly "
                f"than acknowledge twelve."),
        "cta": "See the fix-first plan",
    }


def _social(card: dict) -> dict:
    product = card.get("product_name") or card.get("title") or "a product"
    occ = card.get("occasion")
    return {
        "headline": (f"{occ} post ready to check" if occ else "A post is ready to check"),
        "body": f"Drafted around {product}. Caption, question and hashtags done.",
        "why": (f"I have drafted this around {product} — caption, question and "
                f"hashtags"
                + (f", tied to {occ}." if occ else ".")
                + " Worth remembering that the posts which sell are the boring "
                  "informational ones about fabric, sizing and care, not the "
                  "pretty ones. Check it reads like you, then it goes out."),
        "cta": "Review the post",
    }


def _social_post(card: dict) -> dict:
    """A real, already-written scheduled post waiting on a decision -- not
    the one-off 'here's an idea' card _social() writes. This is what fills
    the Approval panel for the Social Media Manager's calendar now that
    decisions live there instead of in a second panel on the page itself."""
    product = card.get("product_name") or "a product"
    occ = card.get("occasion")
    when = card.get("when_label") or ""
    hook = (card.get("hook") or "").strip()
    overdue = bool(card.get("overdue"))
    headline = (f"Overdue: {occ} post for {product}" if overdue and occ
                else f"Overdue post for {product}" if overdue
                else f"{occ} post — {when}" if occ and when
                else f"Post ready — {when}" if when
                else "A post is ready to check")
    body = hook if hook else f"Drafted around {product}. Caption, question and hashtags done."
    if len(body) > 140:
        body = body[:137] + "…"
    why = (f"Scheduled for {when or 'this week'}, built around {product}"
           + (f" for {occ}" if occ else "") + "."
           + (f' The hook: "{hook}"' if hook else "")
           + (" This one is already overdue — it stayed a draft past its own"
              " posting time." if overdue else "")
           # Auto-planned posts say why THIS product this week — the sales
           # signal or the festival that put it on the calendar.
           + (f" Why this one: {card['plan_reason']}" if card.get("plan_reason") else ""))
    # A reel and a photo post are two different asks, and the button has to say
    # which. "Approve → schedule" was the same word for both, so a seller who
    # tapped it expecting a picture got a shot list to go and film, and a seller
    # who wanted a shot list got a picture. social.py has already worked out
    # which this is and what we can actually deliver; use its words.
    return {"headline": headline, "body": body, "why": why,
            "cta": card.get("cta") or "Approve → schedule",
            "kind": card.get("kind") or "",
            "kind_label": card.get("kind_label") or "",
            "needs_from_you": card.get("needs_from_you") or ""}


def _autoplan_week(card: dict) -> dict:
    """The header card over one auto-planned week: what the planner found,
    in the Social Media Manager's voice, before the seller looks at posts."""
    n = _n(card.get("waiting"))
    added, existing, target = _n(card.get("added")), _n(card.get("existing")), _n(card.get("target"))
    occ = card.get("occasion") or ""
    wins = [w for w in (card.get("winners") or []) if w]
    slow = [x for x in (card.get("strugglers") or []) if x]
    body = (f"{card.get('week_label') or 'Next week'}: {n} post{'' if n == 1 else 's'} "
            f"to approve" + (f", built around {occ}" if occ else "") + ".")
    why = (f"I planned {card.get('week_label') or 'next week'}. "
           + (f"{existing} post{'' if existing == 1 else 's'} were already on the "
              f"calendar, so I added {added} to reach your {target}. " if existing
              else f"I added {added} — your week is {target}. ")
           + (f"{occ} is live, so the week builds towards it. " if occ else "")
           + (f"Selling well: {', '.join(wins)} — those get the proof posts. " if wins else "")
           + (f"Struggling: {', '.join(slow)} — those get the detail posts, which "
              f"are the ones that actually sell. " if slow else "")
           + "Approve makes each picture and schedules it; reels go on your task "
             "list with the prompt ready for Google Flow.")
    return {"headline": f"Next week is planned — {n} post{'' if n == 1 else 's'} waiting",
            "body": body, "why": why, "cta": f"Approve all {n}"}


def _purchase_order(card: dict) -> dict:
    """A purchase order the replenishment check drafted after an order."""
    sup = card.get("supplier_name") or "the supplier"
    n = _n(card.get("n_items"))
    dos = card.get("tightest_dos")
    amt = _rupees(card.get("total_amount")) if card.get("total_amount") else ""
    body = (f"{card.get('detail') or ''}"[:120]
            + (f" · {amt}" if amt else ""))
    why = (f"{card.get('reason') or ''} "
           f"Days of supply fell below 1.2 × the lead time, so I drafted this order to {sup} "
           f"at each item's default order quantity."
           + (f" The tightest item has {dos:g} days left." if isinstance(dos, (int, float)) else "")
           + (" Approve and I will write the email, attach the PO as a PDF and send it to "
              f"{card.get('supplier_email')}." if card.get("has_email") else
              " There is no email on file for this supplier, so Approve gives you the PDF "
              "and a ready email to send yourself — add their email in Suppliers for next time."))
    return {"headline": f"Send {sup} an order for {n} item{'s' if n != 1 else ''}",
            "body": body, "why": why.strip(),
            "cta": card.get("cta") or "Approve & send"}


WRITERS = {
    "winback": _winback, "festival": _festival, "reorder": _reorder,
    "overstock": _overstock, "supplier_risk": _supplier_risk,
    "reputation": _reputation, "complaints": _complaints,
}
# Dynamic ids (one per social post, e.g. "post_a1b2c3") can't live in WRITERS
# by exact match, so they're matched by prefix instead, checked in dress().
PREFIX_WRITERS = [("post_", _social_post), ("content_", _social),
                  ("autoplan_", _autoplan_week), ("po_", _purchase_order)]


def dress(card: dict) -> dict:
    """Attach a manager and their words to one insight card.

    The original `title` and `detail` are kept untouched. History, the email
    digest and the Today strip already render them, and silently changing what
    those show would be a bigger blast radius than this feature deserves."""
    who = assign(card)
    mgr = MANAGERS[who]
    cid = str(card.get("id") or "")

    writer = WRITERS.get(cid)
    if writer is None:
        for prefix, w in PREFIX_WRITERS:
            if cid.startswith(prefix):
                writer = w
                break
    if writer is None and who == "social":
        writer = _social

    if writer:
        said = writer(card)
    else:
        # An unknown card still gets a desk and a sane presentation rather than
        # falling out of the redesign looking like a bug.
        said = {"headline": card.get("title") or "Something needs a decision",
                "body": (card.get("detail") or "")[:140],
                "why": card.get("detail") or "",
                "cta": card.get("action_label") or "Approve"}

    return {**card,
            "manager": mgr["id"], "manager_name": mgr["name"],
            "manager_short": mgr["short"], "manager_icon": mgr["icon"],
            "manager_colour": mgr["colour"], "manager_remit": mgr["remit"],
            "headline": said["headline"], "body": said["body"],
            "why": said.get("why") or said["body"], "cta": said["cta"]}


def dress_all(cards: list[dict]) -> list[dict]:
    """Dress every card and order them by desk, so the panel reads as a team
    reporting in rather than a shuffled queue."""
    dressed = [dress(c) for c in (cards or [])]
    rank = {m: i for i, m in enumerate(ORDER)}
    return sorted(dressed, key=lambda c: (rank.get(c["manager"], 99),
                                          -_n(c.get("count"))))


def desks(cards: list[dict]) -> list[dict]:
    """A summary line per manager — how many cards each has waiting."""
    counts: dict[str, int] = {}
    for c in cards or []:
        counts[c.get("manager") or assign(c)] = counts.get(
            c.get("manager") or assign(c), 0) + 1
    return [{**MANAGERS[m], "pending": counts.get(m, 0)}
            for m in ORDER if counts.get(m)]
