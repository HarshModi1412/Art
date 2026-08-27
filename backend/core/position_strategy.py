"""
Position Strategy — turn the positioning 2x2 into an actionable, LEVELLED move plan
for a small social-media product seller.

positioning.py places a brand on a 2x2 built from its own reviews:

        y+  Product-driven (known for the product itself)
             |
    x-  -----+-----  x+      (x-: value pricing, x+: premium)
             |
        y-  Brand & aesthetic driven

...which yields four positions:

    Premium quality brand   = premium price + product focus   (x+ , y+)
    Everyday value brand     = value price   + product focus   (x- , y+)
    Premium lifestyle brand  = premium price + brand focus     (x+ , y-)
    Affordable trendy brand  = value price   + brand focus     (x- , y-)

This module adds the "so what do I do?" layer:

  1. current position (auto-detected)                         -> pros & cons
  2. every OTHER position, PLUS the current one, as targets   -> pros & cons
       * choosing the SAME position gives a "strengthen where you are" plan
       * choosing a DIFFERENT one gives an A -> B move plan
  3. either way the checklist is split into LEVELS (Level 1 -> 2 -> 3): you
     finish one level before the next unlocks, so the work is paced instead of
     dumped all at once.

Every checklist item has a stable id (current__target__n) so the frontend can
persist which boxes are ticked across logins.
"""
from __future__ import annotations

# ---------------------------------------------------------
# The four positions  (price in {premium,value}, focus in {product,brand})
# ---------------------------------------------------------
POSITIONS: dict[str, dict] = {
    "premium_product": {
        "name": "Premium quality brand",
        "price": "premium", "focus": "product",
        "tagline": "People pay more because the product itself is clearly better.",
        "pros": [
            "Highest margin per order — buyers already accept premium pricing.",
            "Reputation rides on product quality, which you control directly.",
            "Attracts serious buyers who become repeat customers and refer friends.",
            "Easy to justify limited drops and higher-priced signature pieces.",
        ],
        "cons": [
            "Quality has to be flawless every time, or the price feels unfair.",
            "Smaller audience — the price filters out casual browsers.",
            "Vulnerable if a cheaper seller gets 'good enough'.",
            "Higher material and QC cost to hold the standard.",
        ],
    },
    "value_product": {
        "name": "Everyday value brand",
        "price": "value", "focus": "product",
        "tagline": "Genuinely good products at a fair price — the reliable go-to.",
        "pros": [
            "Broadest audience — the price welcomes almost everyone.",
            "High repeat rate; becomes a habit, not a one-off splurge.",
            "Word of mouth compounds fast when value is obvious.",
            "Resilient — 'affordable treat' spending holds up in a downturn.",
        ],
        "cons": [
            "Thin margins — profit depends on volume and tight sourcing.",
            "Hard to raise prices later without upsetting regulars.",
            "Easy to copy; little that's defensible beyond consistency.",
            "Busy-but-broke risk if fulfilment isn't efficient.",
        ],
    },
    "premium_brand": {
        "name": "Premium lifestyle brand",
        "price": "premium", "focus": "brand",
        "tagline": "People pay for the brand, the aesthetic and how it makes them feel.",
        "pros": [
            "Highest perceived value — story and aesthetic justify the price.",
            "Strong on Instagram — the brand markets itself for free.",
            "Great for collabs, drops, and aspirational content.",
            "The brand world is hard for a bare-product seller to copy.",
        ],
        "cons": [
            "Heavy upfront work — photography, packaging, consistent identity.",
            "The product still has to be at least good, or the brand rings hollow.",
            "Trends move; an aesthetic dates and needs refreshing.",
            "Slower to build trust than a straightforward value pitch.",
        ],
    },
    "value_brand": {
        "name": "Affordable trendy brand",
        "price": "value", "focus": "brand",
        "tagline": "On-trend looks at a price young buyers can say yes to.",
        "pros": [
            "Magnet for trend-driven, social-first buyers — high shareability.",
            "Low price + strong aesthetic is a very viral combination.",
            "Fast to ride trends and test new drops cheaply.",
            "Community and identity build loyalty price alone can't.",
        ],
        "cons": [
            "Lowest margin — you live and die by volume and virality.",
            "Trend risk — today's hot look is next month's dead stock.",
            "Crowded space; lots of lookalike sellers competing on price.",
            "Hard to trade up either the price or the product later.",
        ],
    },
}

ORDER = ["premium_product", "value_product", "premium_brand", "value_brand"]

# map the positioning quadrant label -> position id (kept in lock-step with
# positioning.QUADRANTS)
QUADRANT_TO_ID = {
    "Premium quality brand": "premium_product",
    "Everyday value brand": "value_product",
    "Premium lifestyle brand": "premium_brand",
    "Affordable trendy brand": "value_brand",
}

# Foundations that matter in EVERY position.
UNIVERSAL_KEEP = [
    "Reply to every review and DM quickly — responsiveness is free trust.",
    "Consistent core quality — your bestsellers are the same every order.",
    "Honest photos and descriptions so what arrives matches what was promised.",
    "Reliable dispatch and clear tracking on every order.",
]


# ---------------------------------------------------------
# Move-plan building blocks (per axis change)
# ---------------------------------------------------------
_PRICE_UP = {  # value -> premium
    "label": "Move from value pricing to premium pricing",
    "keep_note": "You're keeping what you're known for — you're changing what you charge and how premium it feels.",
    "steps": [
        ("Cost your 5 bestsellers precisely (materials + making + overhead + shipping per unit).",
         "You can't price up safely until you know your true unit cost and current margin."),
        ("Upgrade the visible quality cues of those 5: better finish, better packaging, better photos.",
         "A premium price needs a premium cue the buyer can see and photograph."),
        ("Introduce 2–3 higher-priced signature pieces ABOVE your current range.",
         "This lifts the price ceiling gently instead of raising everything at once."),
        ("Raise prices on the upgraded pieces by 10–15%, holding one or two 'anchor' favourites steady.",
         "A kept anchor stops regulars feeling the whole shop got expensive."),
        ("Write a one-line quality/sourcing story for each piece ('hand-finished', 'small-batch').",
         "Story justifies price; silence makes it feel like a hike."),
        ("Refresh your feed and product pages to look considered and premium, not busy.",
         "Your grid is the price tag buyers stare at longest."),
        ("Watch repeat rate and average order value for 4 weeks; tune the two weakest pieces.",
         "Repositioning is a dial, not a switch — adjust with real data."),
    ],
}
_PRICE_DOWN = {  # premium -> value
    "label": "Move from premium pricing to value pricing",
    "keep_note": "You're keeping what you're known for — you're making it more affordable and higher-volume.",
    "steps": [
        ("Find your highest-margin pieces and build bundles/sets around them.",
         "Value positioning wins on bundles, not across-the-board price cuts."),
        ("Trim the catalogue — drop slow, costly pieces so fulfilment gets faster and cheaper.",
         "Value economics only work when operations are lean."),
        ("Introduce one clear 'everyday' price point that undercuts the premium options.",
         "Give buyers one obvious reason you're the smart daily choice."),
        ("Renegotiate your top 3 supplier costs or switch to bulk on your highest-volume inputs.",
         "Protected margin is what makes low prices survivable."),
        ("Message value loudly — bundle offers, first-order discount, loyalty perks.",
         "Value has to be advertised; premium sells on restraint, value sells on shouting it."),
        ("Speed up fulfilment: pre-pack bestsellers, streamline dispatch, offer quick shipping.",
         "More orders per week is how volume pricing makes money."),
        ("Track weekly orders and margin for 4 weeks; drop any bundle below target margin.",
         "Keep only the value plays that actually pay."),
    ],
}
_FOCUS_TO_PRODUCT = {  # brand -> product
    "label": "Shift what you're known for from the brand to the product",
    "keep_note": "You're keeping your price positioning — you're changing what buyers come for.",
    "steps": [
        ("Pick 2–3 pieces to become your signature and perfect them until they're undeniable.",
         "A product reputation is built on a few things done exceptionally, not a huge catalogue."),
        ("Invest in the craft: better materials, tighter QC, real improvements buyers can feel.",
         "Product-led positioning lives or dies on what actually arrives."),
        ("Put the product front and centre — close-up shots, detail videos, how it's made.",
         "Buyers switch to coming-for-the-product only when the product is the story."),
        ("Run a small drop of your signature pieces and collect honest buyer feedback.",
         "Direct feedback tells you which piece deserves the spotlight."),
        ("Shift your content from lifestyle/aesthetic to product detail and quality proof.",
         "Your feed teaches buyers what to come for."),
        ("Set a consistency standard (QC checklist, spec cards) so quality never wobbles.",
         "A product rep is fragile — one bad order undoes ten good ones."),
    ],
}
_FOCUS_TO_BRAND = {  # product -> brand
    "label": "Shift what you're known for from the product to the brand & aesthetic",
    "keep_note": "You're keeping your price positioning — you're changing what buyers come for.",
    "steps": [
        ("Define your brand feeling in one line (minimal / bold / vintage / playful) and design to it.",
         "A brand needs one clear identity, not a bit of everything."),
        ("Upgrade photography, packaging and your grid so everything looks like one world.",
         "Aesthetic consistency is what turns a shop into a brand."),
        ("Create one genuinely shareable signature detail (packaging, a motif, an unboxing moment).",
         "The brand spreads only if there's something worth posting."),
        ("Build a content rhythm — a recognisable style of reels/posts people start to expect.",
         "Brand positioning is about presence, not just products."),
        ("Tell your founder/brand story across bio, highlights and captions.",
         "People buy a small brand partly for who's behind it."),
        ("Reshare customer photos and build a hashtag so buyers market the brand for you.",
         "User content is the cheapest, most credible brand marketing."),
    ],
}


def _axis_plan(cur: dict, tgt: dict) -> list[dict]:
    blocks = []
    if cur["price"] != tgt["price"]:
        blocks.append(_PRICE_UP if tgt["price"] == "premium" else _PRICE_DOWN)
    if cur["focus"] != tgt["focus"]:
        blocks.append(_FOCUS_TO_PRODUCT if tgt["focus"] == "product" else _FOCUS_TO_BRAND)
    return blocks


def _improve_blocks(pid: str) -> list[dict]:
    """Same-position plan: strengthen where you already are, in three levels."""
    p = POSITIONS[pid]
    focus_word = "product quality" if p["focus"] == "product" else "brand & aesthetic"
    price_word = "premium" if p["price"] == "premium" else "value"
    return [
        {"label": "Level 1 · Make it undeniable",
         "keep_note": f"You're staying a “{p['name']}” — Level 1 hardens the foundations so nobody has a reason to doubt you.",
         "steps": [
            (f"List your top 5 pieces and make each one's {focus_word} visibly excellent — fix the weakest first.",
             "You strengthen a position by removing its single biggest reason-to-doubt."),
            ("Rewrite your bio and pinned posts so your one-line positioning is instantly clear.",
             "If a new visitor can't tell what you stand for in 3 seconds, the position isn't working yet."),
            ("Reply to every recent review/DM and fix any repeated complaint this week.",
             "Trust is the base layer of every position; unanswered gripes leak it away."),
         ]},
        {"label": "Level 2 · Get more people to see it",
         "keep_note": "Level 2 turns a solid position into reach — more of the right people discovering you.",
         "steps": [
            (f"Post 3x/week of content that proves your {focus_word}, not just shows product.",
             "Proof content converts strangers; pretty-but-empty content doesn't."),
            (f"Lean into your {price_word} angle in every caption and offer so the message is consistent.",
             "A position compounds only when every touchpoint repeats it."),
            ("Collaborate with 2–3 micro-creators whose audience matches your buyer.",
             "Borrowed audiences are the fastest honest way to grow a small brand."),
            ("Turn your happiest buyers into content — reshare their photos, ask for reviews.",
             "Social proof at scale is what makes a position believable."),
         ]},
        {"label": "Level 3 · Defend & compound",
         "keep_note": "Level 3 locks in the lead so the position keeps paying off.",
         "steps": [
            ("Launch a signature drop or limited edition that only your brand could do.",
             "A signature nobody can copy is what makes a position defensible."),
            ("Start a simple loyalty or repeat-buyer perk to raise lifetime value.",
             "Keeping a buyer is cheaper than winning a new one — that's where margin compounds."),
            ("Re-upload reviews monthly and watch your positioning score hold or climb.",
             "What you measure monthly is what you keep improving."),
         ]},
    ]


def _shared(cur: dict, tgt: dict) -> list[str]:
    keep = list(UNIVERSAL_KEEP)
    if cur["price"] == tgt["price"]:
        if cur["price"] == "premium":
            keep.append("Your premium price positioning stays — protect the quality cues that justify it.")
        else:
            keep.append("Your value/affordable positioning stays — keep prices honest and visible.")
    if cur["focus"] == tgt["focus"]:
        if cur["focus"] == "product":
            keep.append("Your product reputation stays — never let signature quality slip while you change the rest.")
        else:
            keep.append("Your brand & aesthetic stays — keep the identity your followers already recognise.")
    return keep


def position_card(pid: str) -> dict:
    p = POSITIONS[pid]
    return {"id": pid, "name": p["name"], "tagline": p["tagline"],
            "price": p["price"], "focus": p["focus"],
            "pros": p["pros"], "cons": p["cons"]}


def target_options(current_id: str) -> list[dict]:
    """All four positions as targets — the current one first ('stay &
    strengthen'), then the other three annotated with move difficulty."""
    out = []
    cur = POSITIONS[current_id]
    # current position, offered as "strengthen where you are"
    out.append({**position_card(current_id), "difficulty": "Stay & strengthen",
                "axes_changing": 0, "is_current": True})
    for pid in ORDER:
        if pid == current_id:
            continue
        tgt = POSITIONS[pid]
        changes = (cur["price"] != tgt["price"]) + (cur["focus"] != tgt["focus"])
        difficulty = {1: "Adjacent move", 2: "Big repositioning"}[changes]
        out.append({**position_card(pid), "difficulty": difficulty,
                    "axes_changing": changes, "is_current": False})
    return out


def _assign_levels(checklist: list[dict], blocks: list[dict]) -> None:
    """Give each item a `level` (1..N). If the blocks already carry explicit
    'Level …' labels (the improvement plan), map each block to its own level.
    Otherwise split a move plan's items into 3 contiguous levels."""
    labels = [b["label"] for b in blocks]
    if all(l.lower().startswith("level") for l in labels):
        level_of = {b["label"]: i + 1 for i, b in enumerate(blocks)}
        for it in checklist:
            it["level"] = level_of.get(it["phase"], 1)
        return
    n = len(checklist)
    if n == 0:
        return
    # 3 roughly-equal contiguous buckets
    size = max(1, (n + 2) // 3)
    for i, it in enumerate(checklist):
        it["level"] = min(3, i // size + 1)


def build_plan(current_id: str, target_id: str) -> dict:
    """Full plan. current==target -> strengthen plan; else A->B move plan.
    Either way the checklist is levelled (item['level'] = 1..N)."""
    if current_id not in POSITIONS or target_id not in POSITIONS:
        raise ValueError("Pick a current and a target position.")
    cur, tgt = POSITIONS[current_id], POSITIONS[target_id]

    same = current_id == target_id
    blocks = _improve_blocks(current_id) if same else _axis_plan(cur, tgt)
    if not blocks:  # safety: identical axes but different id shouldn't happen
        blocks = _improve_blocks(current_id)

    checklist = []
    n = 0
    for block in blocks:
        phase = block["label"]
        for (text, why) in block["steps"]:
            n += 1
            checklist.append({
                "id": f"{current_id}__{target_id}__{n}",
                "phase": phase, "text": text, "why": why,
            })
    _assign_levels(checklist, blocks)

    if same:
        gap = "You're staying put and getting stronger — no repositioning, just compounding what already works."
    else:
        gap_bits = []
        if cur["price"] != tgt["price"]:
            gap_bits.append(f"price ({cur['price']} → {tgt['price']})")
        if cur["focus"] != tgt["focus"]:
            gap_bits.append(f"what you're known for ({cur['focus']} → {tgt['focus']})")
        gap = "You're changing " + " and ".join(gap_bits) + "." if gap_bits else ""

    levels = sorted({it["level"] for it in checklist})
    return {
        "current": position_card(current_id),
        "target": position_card(target_id),
        "same_position": same,
        "keep_same": _shared(cur, tgt),
        "keep_note": blocks[0]["keep_note"] if len(blocks) == 1 or same else
                     "This is a big move on both axes — change one axis at a time, and keep the foundations below rock-solid throughout.",
        "gap": gap,
        "axes_changing": 0 if same else len(_axis_plan(cur, tgt)),
        "levels": levels,
        "checklist": checklist,
    }
