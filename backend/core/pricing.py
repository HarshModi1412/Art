"""
Pricing catalog — single source of truth for the One Tap Manager offer.

THREE TIERS, flat monthly, priced in the buyer's currency
---------------------------------------------------------
       Free trial  7 days      every Pro Max feature, no card. When it ends
                               nothing stays free: the app locks until a plan
                               is bought. Data is kept, never deleted.
       Pro         ₹700  $10     everything except AI image and video generation
       Pro Max     ₹1,299 $12.99 everything in Pro, plus AI product photos and clips

   The US is the primary market (September 2026), so USD is the default and
   INR is for buyers in India. The two prices are set separately, not converted:
   see currency.py for why nothing here ever runs an exchange rate. Which
   currency a buyer sees is decided in region.py.

   Internal ids: "free" (the trial, and an expired trial), "pro", "promax".
   "pro" used to be the id of the old ₹999 "Max" tier, and stored rows with it
   now read as the new Pro. "max" and "chain" alias forward to Pro Max.

   The trial start date is written at signup (billing.start_trial). An account
   made before this pricing existed has no date, so its 7 days start the first
   time the app checks it, not retroactively.

CREDIT PACKS
------------
Kept for accounts billed in rupees, as a top-up for the monthly credit meter
(credits.py). They have no dollar price yet, so a USD account is not offered
them.

Everything a seller has already paid for stays theirs — downgrading or a
lapsed trial never deletes data, it only stops new actions.

LAUNCH MODE
-----------
LAUNCH_MODE=true still turns every gate off (every account behaves as Pro Max,
no trial clock). It now defaults to OFF, because the offer is "7-day trial,
then paid". Set it to true on a deployment only for a demo or a free period.
"""
import os

# ---------------------------------------------------------------------------
# tiers
# ---------------------------------------------------------------------------
TRIAL_DAYS = 7
PLAN_ORDER = ["free", "pro", "promax"]
PAID_PLANS = ("pro", "promax")

PLANS: dict[str, dict] = {
    "free": {
        "id": "free",
        "name": "Free trial",
        "price_inr": 0,
        "price_usd": 0,
        "period": f"{TRIAL_DAYS} days",
        "trial_days": TRIAL_DAYS,
        "tagline": f"Every Pro Max feature for {TRIAL_DAYS} days. No card needed.",
        "limits": {
            "ai_per_day": 0,             # 0 = unlimited, the trial is Pro Max
            "products": 0,
            "outlets": 0,
            "site_badge": False,
            "custom_domain": True,
        },
        "includes": [
            f"Everything in Pro Max for {TRIAL_DAYS} days",
            "AI product photos and clips included in the trial",
            "No card needed to start",
            "After the trial, pick Pro or Pro Max to keep going. Your data is kept.",
        ],
    },
    "pro": {
        "id": "pro",
        "name": "Pro",
        "price_inr": 700,
        "price_usd": 10.00,
        "period": "month",
        "tagline": "Runs the whole shop. Everything except AI image generation.",
        "limits": {
            "ai_per_day": 0,             # 0 = unlimited
            "products": 0,
            "outlets": 0,
            "site_badge": False,
            "custom_domain": True,
        },
        "includes": [
            "Sales analytics, category and sub-category trends",
            "Customer groups and the at-risk customer list",
            "Win-back campaigns, messages and Excel included",
            "Stock, reorder levels, suppliers and PDF purchase orders",
            "Instagram week planner, captions and scheduling",
            "Review, complaint and positioning reports",
            "Your own selling website and custom domain",
            "Unlimited AI writing, analyst and chatbot",
        ],
    },
    "promax": {
        "id": "promax",
        "name": "Pro Max",
        "price_inr": 1299,
        "price_usd": 12.99,
        "period": "month",
        "tagline": "Everything in Pro, plus AI product photos and clips.",
        "limits": {
            "ai_per_day": 0,
            "products": 0,
            "outlets": 0,
            "site_badge": False,
            "custom_domain": True,
        },
        "includes": [
            "Everything in Pro",
            "AI product photos made from your own product photo",
            "AI pictures for every planned Instagram post",
            "Short AI product clips",
        ],
    },
}

# Legacy plan names that stored rows may still carry. "semipro" was the retired
# ₹499 tier. "max" and "chain" were the old top tier, which included image
# generation, so they alias to Pro Max rather than down to Pro.
PLAN_ALIASES = {
    "chain": "promax", "chain_monthly": "promax", "max": "promax",
    "pro_max": "promax", "pro-max": "promax", "promax_monthly": "promax",
    "pro_monthly": "pro", "paid": "pro",
    "semipro": "free", "semi_pro": "free", "semipro_monthly": "free",
}

# ---------------------------------------------------------------------------
# feature gating
# ---------------------------------------------------------------------------
# feature -> the lowest plan that may use it. Nothing is on "free": the Free
# tier is the trial, and a live trial is treated as Pro Max (billing.py).
FEATURE_MIN_PLAN: dict[str, str] = {
    "analytics": "pro",
    "subcategory": "pro",
    "rfm_list": "pro",
    "winback_list": "pro",
    "mapping": "pro",
    "upload": "pro",
    "storefront": "pro",
    "orders": "pro",
    "products": "pro",
    "content": "pro",
    "winback_campaign": "pro",
    "ai_use": "pro",
    "complaints": "pro",
    "positioning": "pro",
    "digest": "pro",
    "supply": "pro",
    "purchase_orders": "pro",
    "position_strategy": "pro",
    "custom_domain": "pro",

    # AI image and video generation is the one thing Pro Max adds.
    "image_generation": "promax",
    "video_generation": "promax",
}

# Never gated, on any plan: nothing, since the trial ended the free tier. Kept
# as a name because billing.can_use_free still reads it.
FREE_FOREVER = [f for f, p in FEATURE_MIN_PLAN.items() if p == "free"]

# Gated features a credit can buy outright. Every feature now comes with a
# paid plan, so no feature is sold by the credit any more; the packs only top
# up the credit meter in credits.py.
CREDIT_COST: dict[str, int] = {}

# ---------------------------------------------------------------------------
# usage-based packs (no monthly commitment)
# ---------------------------------------------------------------------------
CREDIT_PACKS: dict[str, dict] = {
    "credits_100": {
        "id": "credits_100", "name": "100 credits", "price_inr": 299, "credits": 100,
        "description": "About 10 win-back campaigns, or 6 positioning reports, or 100 AI runs.",
    },
    "credits_300": {
        "id": "credits_300", "name": "300 credits", "price_inr": 749, "credits": 300,
        "description": "Same credits, 17% cheaper each. Still never expires.",
        "best_value": True,
    },
    "credits_1000": {
        "id": "credits_1000", "name": "1000 credits", "price_inr": 1999, "credits": 1000,
        "description": "For a busy season. Works out cheaper than Pro if you use it in bursts.",
    },
}


def launch_mode() -> bool:
    """Nothing gated while true. Off by default; set LAUNCH_MODE=true to open
    everything up for a demo or a free period."""
    return os.environ.get("LAUNCH_MODE", "false").strip().lower() in ("true", "1", "yes", "on")


def price(plan_or_pack: dict, ccy: str) -> float:
    """The price of a plan or pack in the buyer's currency. USD or INR only;
    anything else is billed in USD, the primary market's currency."""
    if str(ccy).upper() == "INR":
        return plan_or_pack.get("price_inr") or 0
    return plan_or_pack.get("price_usd") or 0


def price_label(plan_or_pack: dict, ccy: str) -> str:
    """'$12.99', '$10', '₹1,299'. Whole dollars drop the cents."""
    from backend.core import currency
    amount = price(plan_or_pack, ccy)
    code = "INR" if str(ccy).upper() == "INR" else "USD"
    decimals = 0 if float(amount).is_integer() else 2
    return currency.fmt(amount, code, decimals=decimals)


def normalize_plan(plan: str | None) -> str:
    p = (plan or "free").strip().lower()
    p = PLAN_ALIASES.get(p, p)
    return p if p in PLANS else "free"


def get_plan(plan_id: str) -> dict:
    return PLANS[normalize_plan(plan_id)]


def plan_rank(plan_id: str) -> int:
    return PLAN_ORDER.index(normalize_plan(plan_id))


def plan_allows(plan_id: str, feature: str) -> bool:
    """Does this subscription tier include this feature outright?"""
    if launch_mode():
        return True
    need = FEATURE_MIN_PLAN.get(feature)
    if need is None:
        return True
    return plan_rank(plan_id) >= PLAN_ORDER.index(need)


def credits_for(feature: str) -> int:
    """Credits this feature costs a usage-plan seller. 0 = not buyable."""
    return CREDIT_COST.get(feature, 0)


def limit(plan_id: str, key: str):
    """A plan limit. 0 means unlimited for numeric limits."""
    return get_plan(plan_id)["limits"].get(key)


def ai_quota(plan_id: str) -> int:
    """Free AI uses per feature per day. 0 = unlimited."""
    if launch_mode():
        return 0
    return int(get_plan(plan_id)["limits"].get("ai_per_day") or 0)


def within_limit(plan_id: str, key: str, count: int) -> bool:
    cap = limit(plan_id, key)
    if launch_mode() or not cap:
        return True
    return int(count) < int(cap)


def upgrade_target(feature: str) -> dict | None:
    """The cheapest plan that unlocks `feature` — what the paywall should offer."""
    need = FEATURE_MIN_PLAN.get(feature)
    return PLANS.get(need) if need else None


# ---------------------------------------------------------------------------
# what /api/pricing hands the frontend
# ---------------------------------------------------------------------------
# Named so the pricing page can put the honest comparison on screen: these are
# the app categories a seller on Shopify pays for separately.
REPLACES = [
    {"category": "Analytics & LTV", "typical_inr": 1600},
    {"category": "Inventory & reorder", "typical_inr": 2500},
    {"category": "Win-back / retention email", "typical_inr": 1500},
    {"category": "Reviews & reputation", "typical_inr": 1200},
    {"category": "Order management", "typical_inr": 800},
]


def stack_comparison() -> dict:
    """The rupee comparison with the Shopify app stack. Rupees only: the US
    app prices have not been checked at source, so no dollar version is shown."""
    total = sum(r["typical_inr"] for r in REPLACES)
    ours = PLANS["pro"]["price_inr"]
    return {
        "rows": REPLACES,
        "typical_total_inr": total,
        "ours_inr": ours,
        "saving_inr": total - ours,
        "note": "Typical monthly cost of separate Shopify apps in each category, "
                "before any percentage-of-sales charges.",
    }


def chatgpt_plan_line() -> dict | None:
    """The "Use your ChatGPT plan" line for the plan cards, or None.

    OpenAI's guidelines for Sign in with ChatGPT require a partner app's pricing
    to show which of its plans support ChatGPT plan usage, with a "Learn more"
    link to OpenAI's help centre. Every plan here supports it, for AI writing.
    It is only shown once the server can actually offer it, so nobody is sold a
    feature that is still waiting for OpenAI's approval."""
    try:
        from backend.core import chatgpt_auth
        if not chatgpt_auth.plan_usage_offered():
            return None
        return {"text": "Use your ChatGPT plan for AI writing (ChatGPT Plus or Pro)",
                "learn_more": chatgpt_auth.HELP_URL}
    except Exception:  # noqa: BLE001
        return None


def _priced(p: dict, ccy: str) -> dict:
    return {**p, "price": price(p, ccy), "price_label": price_label(p, ccy)}


def packs_for(ccy: str) -> list[dict]:
    """Credit packs on sale in this currency. Rupees only for now."""
    if str(ccy).upper() != "INR":
        return []
    return [_priced(c, "INR") for c in CREDIT_PACKS.values()]


def public_catalog(ccy: str = "USD") -> dict:
    ccy = "INR" if str(ccy).upper() == "INR" else "USD"
    packs = packs_for(ccy)
    chatgpt = chatgpt_plan_line()
    return {
        "launch_mode": launch_mode(),
        "model": "trial_then_subscription",
        "currency": ccy,
        "symbol": "₹" if ccy == "INR" else "$",
        "trial_days": TRIAL_DAYS,
        "plans": [{**_priced(PLANS[p], ccy), "chatgpt_plan": chatgpt} for p in PLAN_ORDER],
        "credit_packs": packs,
        "credit_cost": CREDIT_COST,
        "stack": stack_comparison() if ccy == "INR" else None,
        # kept so older frontend code that reads `products` keeps working
        "products": [
            {"id": p["id"], "name": p["name"], "price_inr": p["price_inr"],
             "price_usd": p["price_usd"], "price": price(p, ccy),
             "price_label": price_label(p, ccy),
             "kind": "subscription", "description": p["tagline"]}
            for p in (PLANS["pro"], PLANS["promax"])
        ] + [
            {"id": c["id"], "name": c["name"], "price_inr": c["price_inr"],
             "price": c["price"], "price_label": c["price_label"],
             "kind": "one_time", "credits": c["credits"], "description": c["description"]}
            for c in packs
        ],
    }


def get_product(product_id: str) -> dict | None:
    """Anything buyable: a paid plan or a credit pack. The trial is not."""
    if product_id in CREDIT_PACKS:
        return {**CREDIT_PACKS[product_id], "price_usd": None, "kind": "one_time"}
    pid = normalize_plan(product_id)
    if (product_id in PLANS or product_id in PLAN_ALIASES) and pid in PAID_PLANS:
        p = PLANS[pid]
        return {"id": p["id"], "name": p["name"], "price_inr": p["price_inr"],
                "price_usd": p["price_usd"], "credits": 0, "kind": "subscription",
                "description": p["tagline"]}
    return None
