"""
Pricing catalog — single source of truth for the One Tap Manager offer.

TWO WAYS TO PAY, offered side by side
-------------------------------------
1. SUBSCRIPTION — three tiers, flat monthly, per outlet:

       Free      ₹0      the numbers, forever
       Semi Pro  ₹499    the actions: campaigns, reports, digest, your own domain-less site without our badge
       Pro       ₹999    the operations: supply, purchase orders, unlimited AI, custom domain, multi-outlet

2. USAGE — no monthly commitment. Buy a pack of credits, spend them on the
   heavy actions only, and they never expire. Deliberately NOT a percentage of
   sales and NOT priced per order: sellers already pay that tax to their app
   stack, and it is the thing they complain about loudest.

Everything a seller has already paid for stays theirs — downgrading never
deletes data, it only stops new gated actions.

LAUNCH MODE
-----------
While LAUNCH_MODE is on (default) NOTHING is gated: every account behaves as
Pro and the UI labels paid rows "Free during launch". The permanent free tier
below is already written down, so flipping LAUNCH_MODE=false later is a
non-event rather than a surprise bill — a seller on Free keeps everything
marked free_forever.
"""
import os

# ---------------------------------------------------------------------------
# tiers
# ---------------------------------------------------------------------------
PLAN_ORDER = ["free", "semipro", "pro"]

PLANS: dict[str, dict] = {
    "free": {
        "id": "free",
        "name": "Free",
        "price_inr": 0,
        "period": "forever",
        "tagline": "Every number about your business, permanently free.",
        "limits": {
            "ai_per_day": 5,
            "products": 25,
            "outlets": 1,
            "site_badge": True,          # storefront carries a small One Tap Manager line
            "custom_domain": False,
        },
        "includes": [
            "Sales analytics, category and sub-category trends",
            "RFM segments and the at-risk customer list",
            "Your own selling website + orders (with our badge in the footer)",
            "Product catalogue up to 25 products",
            "5 AI Analyst or Chatbot uses a day",
        ],
    },
    "semipro": {
        "id": "semipro",
        "name": "Semi Pro",
        "price_inr": 499,
        "period": "month",
        "tagline": "The actions, not just the numbers.",
        "limits": {
            "ai_per_day": 50,
            "products": 250,
            "outlets": 1,
            "site_badge": False,
            "custom_domain": False,
        },
        "includes": [
            "Everything in Free",
            "Win-back campaigns — unlimited, messages and Excel included",
            "Complaint analysis and the fix-first plan",
            "Market position and reputation reports",
            "The daily digest by email (and WhatsApp when you connect it)",
            "Catalogue up to 250 products · badge removed from your site",
            "50 AI uses a day",
        ],
    },
    "pro": {
        "id": "pro",
        "name": "Pro",
        "price_inr": 999,
        "period": "month",
        "tagline": "Runs the shop, not just the reporting.",
        "limits": {
            "ai_per_day": 0,             # 0 = unlimited
            "products": 0,
            "outlets": 0,
            "site_badge": False,
            "custom_domain": True,
        },
        "includes": [
            "Everything in Semi Pro",
            "Supply Management — reorder points, EOQ, safety stock, waste log",
            "PDF purchase orders sent to your suppliers",
            "Position Strategy checklists",
            "Unlimited AI, unlimited products, unlimited outlets",
            "Your own custom domain",
        ],
    },
}

# Legacy plan names that existing rows in user.csv may still carry.
PLAN_ALIASES = {"chain": "pro", "pro_monthly": "pro", "chain_monthly": "pro", "paid": "pro"}

# ---------------------------------------------------------------------------
# feature gating
# ---------------------------------------------------------------------------
# feature -> the lowest plan that may use it.
FEATURE_MIN_PLAN: dict[str, str] = {
    "analytics": "free",
    "subcategory": "free",
    "rfm_list": "free",
    "winback_list": "free",
    "mapping": "free",
    "upload": "free",
    "storefront": "free",
    "orders": "free",
    "products": "free",
    "content": "free",

    "winback_campaign": "semipro",
    # the free tier gets 5 AI runs a day; more of them is a paid thing, but a
    # credit buys one outright so a burst of work never needs a subscription
    "ai_use": "semipro",
    "complaints": "semipro",
    "positioning": "semipro",
    "digest": "semipro",

    "supply": "pro",
    "purchase_orders": "pro",
    "position_strategy": "pro",
    "custom_domain": "pro",
}

# Never gate these, on any plan, in any mode.
FREE_FOREVER = [f for f, p in FEATURE_MIN_PLAN.items() if p == "free"]

# Gated features a credit can buy outright, for sellers on the usage plan.
# feature -> credits it costs.
CREDIT_COST: dict[str, int] = {
    "winback_campaign": 10,
    "positioning": 15,
    "complaints": 12,
    "ai_use": 1,
    "purchase_orders": 5,
}

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
    """Nothing gated while true. Flip with env var LAUNCH_MODE=false."""
    return os.environ.get("LAUNCH_MODE", "true").strip().lower() not in ("false", "0", "no")


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
    total = sum(r["typical_inr"] for r in REPLACES)
    return {
        "rows": REPLACES,
        "typical_total_inr": total,
        "ours_inr": PLANS["pro"]["price_inr"],
        "saving_inr": total - PLANS["pro"]["price_inr"],
        "note": "Typical monthly cost of separate Shopify apps in each category, "
                "before any percentage-of-sales charges.",
    }


def public_catalog() -> dict:
    return {
        "launch_mode": launch_mode(),
        "model": "both",
        "plans": [PLANS[p] for p in PLAN_ORDER],
        "credit_packs": list(CREDIT_PACKS.values()),
        "credit_cost": CREDIT_COST,
        "free_daily_ai_uses": PLANS["free"]["limits"]["ai_per_day"],
        "stack": stack_comparison(),
        # kept so older frontend code that reads `products` keeps working
        "products": [
            {"id": p["id"], "name": p["name"], "price_inr": p["price_inr"],
             "kind": "subscription", "description": p["tagline"]}
            for p in (PLANS["semipro"], PLANS["pro"])
        ] + [
            {"id": c["id"], "name": c["name"], "price_inr": c["price_inr"],
             "kind": "one_time", "credits": c["credits"], "description": c["description"]}
            for c in CREDIT_PACKS.values()
        ],
    }


def get_product(product_id: str) -> dict | None:
    """Anything buyable: a plan or a credit pack."""
    if product_id in CREDIT_PACKS:
        return {**CREDIT_PACKS[product_id], "kind": "one_time"}
    pid = normalize_plan(product_id)
    if product_id in PLANS or product_id in PLAN_ALIASES:
        p = PLANS[pid]
        return {"id": p["id"], "name": p["name"], "price_inr": p["price_inr"],
                "credits": 0, "kind": "subscription", "description": p["tagline"]}
    return None
