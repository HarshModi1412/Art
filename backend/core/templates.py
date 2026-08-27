"""
Win-back message templates — no OpenAI, no per-message cost.

Two banks, exactly 50 messages each, built from small pools of openers /
bodies / call-to-actions (5 x 5 x 2 = 50) so every combination reads as a
complete, natural message:

  WINBACK_TEMPLATES  — used when we know the customer's favorite item
                       (name + product + a personalized discount coupon)
  FALLBACK_TEMPLATES — used when there isn't enough purchase history to
                       reference a specific product, but still built to be
                       a strong, warm invitation (name + coupon, no product)

Market basket analysis (see analytics.market_basket_pairs) feeds an optional
one-line cross-sell hint appended to WINBACK messages when a real "bought
together" pairing exists for that customer's favorite item.

Discount size is itself a small piece of marketing logic: premium spenders
get a bigger coupon than value-tier spenders, since retaining a high-value
regular is worth more than the extra discount costs.
"""
import hashlib
import itertools
import random

OPENERS_W = [
    "Hey {name}, it's been {days} days since we last saw you at the counter!",
    "{name}, we've been keeping a seat warm for you these past {days} days.",
    "Miss us, {name}? Because it's officially been {days} days.",
    "{name}, the {item} machine keeps asking where you went.",
    "It's been {days} days, {name} — long enough that we genuinely noticed.",
]
BODIES_W = [
    "Your usual {item} is still our best-seller, and honestly, it's been waiting for you.",
    "We remember you're a {item} person through and through — that title hasn't expired.",
    "Nobody's touched your spot at the {item} counter. We checked. Twice.",
    "Bring back the {item} energy, {name} — the crew's been asking about you.",
    "One {item}, coming right up, the moment you decide to walk back in.",
]
CTAS_W = [
    "Use code {coupon} for {discount}% off your next visit — no strings attached.",
    "Show this message for {discount}% off with code {coupon}. See you soon!",
]
WINBACK_TEMPLATES = [f"{o} {b} {c}" for o, b, c in itertools.product(OPENERS_W, BODIES_W, CTAS_W)]

OPENERS_F = [
    "Hey {name}, it's been a while!",
    "{name}, we haven't seen you in some time — hope all's well!",
    "Long time no see, {name}!",
    "{name}, we've genuinely missed having you around.",
    "It's a little quieter around here without you, {name}.",
]
BODIES_F = [
    "We've refreshed a few things since your last visit, and we think you'd like where we've taken it.",
    "No pressure, no pitch — just an open invitation to come see what's new.",
    "Sometimes the best reason to come back is simply that you were missed — consider this that reason.",
    "We can't promise it'll be exactly like you remember, but we can promise it'll be worth the visit.",
    "A little birdie told us you deserve a treat this week — we happen to agree.",
]
CTAS_F = [
    "Use code {coupon} for {discount}% off — just because.",
    "Here's {discount}% off with code {coupon}, whenever you're ready to swing by.",
]
FALLBACK_TEMPLATES = [f"{o} {b} {c}" for o, b, c in itertools.product(OPENERS_F, BODIES_F, CTAS_F)]

assert len(WINBACK_TEMPLATES) == 50
assert len(FALLBACK_TEMPLATES) == 50

_CROSS_SELL_HINTS = [
    "Psst — {cross_sell} pairs perfectly with it, if you're feeling adventurous.",
    "Bonus tip: a lot of people order {cross_sell} right alongside it these days.",
    "While you're at it, {cross_sell} has been a surprise favorite lately — might be worth a try.",
]

_DISCOUNT_BY_TIER = {"premium": 20, "mid-range": 15, "value": 10}


def generate_coupon(customer_id: str, price_tier: str | None) -> tuple[str, int]:
    """
    Deterministic per-customer coupon code + discount percentage. Same
    customer always gets the same code (useful if messages are regenerated),
    and the discount scales with how valuable the customer is — a small
    piece of real marketing logic, not just a random number.
    """
    discount = _DISCOUNT_BY_TIER.get(price_tier, 15)
    digest = hashlib.md5(customer_id.encode()).hexdigest()
    suffix = digest[:4].upper()
    code = f"BACK{discount}-{suffix}"
    return code, discount


def pick_winback_message(profile: dict) -> str:
    """
    Choose a template bank based on how much real signal we have for this
    customer, fill in their details, and — when market basket analysis found
    a real cross-sell pairing — append a bonus line suggesting it.
    """
    # If no customer name column was mapped, address them as "dear customer"
    # instead of exposing a raw ID like CUST0007 in the message.
    name = (profile.get("customer_name") or "").strip() or "dear customer"
    days = profile.get("recency_days", 0)
    coupon, discount = generate_coupon(profile.get("customer_id", ""), profile.get("price_tier"))

    has_strong_signal = profile.get("signal_strength") == "strong" and profile.get("favorite_item") not in (None, "—")

    if has_strong_signal:
        template = random.choice(WINBACK_TEMPLATES)
        msg = template.format(name=name, item=profile["favorite_item"], days=days, coupon=coupon, discount=discount)
        cross_sell = profile.get("cross_sell_item")
        if cross_sell:
            msg += " " + random.choice(_CROSS_SELL_HINTS).format(cross_sell=cross_sell)
    else:
        template = random.choice(FALLBACK_TEMPLATES)
        msg = template.format(name=name, days=days, coupon=coupon, discount=discount)

    # ensure a clean start when the template begins with the {name} placeholder
    # and the fallback "dear customer" was substituted in
    return msg[0].upper() + msg[1:] if msg else msg


def build_winback_messages(profiles: list[dict]) -> list[dict]:
    """Apply pick_winback_message to every profile, attaching coupon details for the export."""
    results = []
    for p in profiles:
        coupon, discount = generate_coupon(p.get("customer_id", ""), p.get("price_tier"))
        results.append({
            **p,
            "message": pick_winback_message(p),
            "coupon_code": coupon,
            "discount_pct": discount,
        })
    return results
