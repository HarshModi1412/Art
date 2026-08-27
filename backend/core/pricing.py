"""
Pricing catalog — single source of truth for the GTM offer structure.

LAUNCH MODE
-----------
While LAUNCH_MODE is on (default), EVERYTHING is free — no paywall fires
anywhere, and the UI labels paid items "Free during launch". When you're
ready to start charging (target: ~30-50 active cafes or 6-8 weeks in),
set the environment variable LAUNCH_MODE=false and redeploy. No code
changes needed.

OFFER STRUCTURE (from the GTM strategy)
---------------------------------------
Free forever  : basic analytics, category insights, RFM segmentation,
                win-back LIST (who's at risk), 5 AI uses per day/feature.
Pay-per-action: win-back campaign (messages + Excel)   ₹199 / campaign
                market position & reputation report     ₹349 / report
                AI top-up (10 extra uses, shared pool)  ₹99
Subscription  : Chain plan (2+ outlets only)            ₹999 / month
                -> unlimited AI + all reports included.
"""
import os


def launch_mode() -> bool:
    """Everything free while true. Flip with env var LAUNCH_MODE=false."""
    return os.environ.get("LAUNCH_MODE", "true").strip().lower() not in ("false", "0", "no")


# product_id -> definition. `credits` = how many uses one purchase grants.
CATALOG: dict[str, dict] = {
    "winback_campaign": {
        "name": "Win-Back Campaign",
        "price_inr": 199,
        "credits": 1,
        "kind": "one_time",
        "description": "One full campaign round: personalized messages + coupon codes "
                       "for every at-risk customer, ready to send on WhatsApp, with Excel export.",
    },
    "positioning_report": {
        "name": "Market Position & Reputation Report",
        "price_inr": 349,
        "credits": 1,
        "kind": "one_time",
        "description": "How customers see you vs. benchmark cafés across 13 themes, "
                       "straight from Google-review language. Includes your differentiators and gaps.",
    },
    "ai_topup": {
        "name": "AI Top-Up (10 uses)",
        "price_inr": 99,
        "credits": 10,
        "kind": "one_time",
        "description": "10 extra AI Analyst runs or Chatbot messages, shared pool, "
                       "used automatically after your free daily quota.",
    },
    "complaints_report": {
        "name": "Complaint Trends Report",
        "price_inr": 249,
        "credits": 1,
        "kind": "one_time",
        "description": "Upload your reviews and get a fix-first action plan, complaint trends "
                       "over time, and a severity quadrant showing what to fix before it costs you customers.",
    },
    "chain_monthly": {
        "name": "Chain Plan",
        "price_inr": 999,
        "credits": 0,
        "kind": "subscription",
        "description": "For 2+ outlets: unlimited AI, all campaigns and reports included, "
                       "across every location. Billed monthly.",
    },
}

# Features that are always free, launch mode or not — never gate these.
FREE_FOREVER = ["analytics", "subcategory", "rfm_list", "winback_list", "mapping", "upload"]


def get_product(product_id: str) -> dict | None:
    return CATALOG.get(product_id)


def public_catalog() -> dict:
    """What /api/pricing returns for the frontend."""
    return {
        "launch_mode": launch_mode(),
        "free_daily_ai_uses": 5,
        "products": [
            {"id": pid, **{k: v for k, v in p.items()}}
            for pid, p in CATALOG.items()
        ],
    }
