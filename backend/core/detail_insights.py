"""
Category drill-down insights — the consultant's way.

The old drill-down always said the same four bland things (share %, month-over-
month %, best weekday, top product). A consultant doesn't read every number
aloud; they compute many possible observations, throw away the ones that don't
apply or don't matter for THIS category, and lead with the two or three that
would actually change what the owner does on Monday.

So this module works in three passes:

  1. DRAFT   — build a library of candidate insights, each a small function
               that inspects the category's numbers and returns a finding
               (text + prescriptive action + a raw importance score) or None.
  2. FILTER  — drop every candidate that returned None (not applicable, or
               below a materiality threshold — a 2% wobble is not a finding).
  3. RANK    — score the survivors on business impact and surface the top few,
               so the owner sees the sharpest points first, not a wall.

Each insight is emitted as {type, text, action, highlight, score} which the
existing i18n.render() passes straight through (it only translates when a
`key` is present; free-text insights render as-is).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _fmt_inr(v: float) -> str:
    return f"₹{v:,.0f}"


def _pct(v: float) -> str:
    return f"{v:.0f}%" if abs(v) >= 10 else f"{v:.1f}%"


def build_detail_insights(scoped: pd.DataFrame, all_txns: pd.DataFrame,
                          value: str, field: str) -> list[dict]:
    """Draft every candidate, keep the applicable ones, return ranked."""
    ctx = _context(scoped, all_txns, value, field)
    drafts = [fn(ctx) for fn in _CANDIDATES]
    found = [d for d in drafts if d]
    # highest business priority first; ties broken by effect size
    found.sort(key=lambda d: (-d["score"], -d.get("_mag", 0)))
    # de-duplicate by angle so we don't show two concentration insights, etc.
    seen, ranked = set(), []
    for d in found:
        angle = d.get("_angle", d["text"][:20])
        if angle in seen:
            continue
        seen.add(angle)
        ranked.append({k: v for k, v in d.items() if not k.startswith("_")})

    # Never leave the drill-down blank: if nothing cleared the materiality bar,
    # give the owner the plain lay-of-the-land (share + best seller) so the page
    # still says something useful rather than looking broken.
    if not ranked:
        ranked.append(_baseline_share(ctx))
        bp = _baseline_top_product(ctx)
        if bp:
            ranked.append(bp)
    return ranked[:6]


def _baseline_share(c) -> dict:
    return {
        "type": "neutral", "highlight": _pct(c["share"]),
        "text": (f"{c['value']} is {_pct(c['share'])} of your revenue "
                 f"({_fmt_inr(c['rev'])}) across {c['orders']} orders — steady, no red flags this period."),
        "action": (f"Nothing urgent here. Keep an eye on {c['value']} next month; if its share moves either way, "
                   f"that's when to act."),
    }


def _baseline_top_product(c) -> dict | None:
    p = c["prod"]
    if p is None or len(p) < 1 or p.sum() <= 0:
        return None
    return {
        "type": "neutral", "highlight": str(p.index[0]),
        "text": f"'{p.index[0]}' leads {c['value']} at {_fmt_inr(p.iloc[0])} in sales.",
        "action": f"Protect your bestseller: keep '{p.index[0]}' consistent and in stock, it's carrying this category.",
    }


def _context(scoped: pd.DataFrame, all_txns: pd.DataFrame, value: str, field: str) -> dict:
    """Everything the candidate insights might need, computed once."""
    total_rev = float(all_txns["amount"].sum())
    rev = float(scoped["amount"].sum())
    share = (rev / total_rev * 100) if total_rev else 0.0

    has_orders = "order_id" in scoped.columns
    orders = int(scoped["order_id"].nunique()) if has_orders else len(scoped)
    all_orders = int(all_txns["order_id"].nunique()) if "order_id" in all_txns.columns else len(all_txns)
    aov = rev / orders if orders else 0.0
    all_rev = total_rev
    all_aov = all_rev / all_orders if all_orders else 0.0

    scoped = scoped.copy()
    scoped["month"] = scoped["date"].dt.to_period("M")
    monthly = scoped.groupby("month")["amount"].sum()

    # category-vs-overall monthly growth (is this category out/under-performing the shop?)
    allm = all_txns.copy()
    allm["month"] = allm["date"].dt.to_period("M")
    all_monthly = allm.groupby("month")["amount"].sum()

    prod = None
    if "product" in scoped.columns and scoped["product"].nunique() >= 1:
        prod = scoped.groupby("product")["amount"].sum().sort_values(ascending=False)

    weekday = scoped.groupby(scoped["date"].dt.day_name())["amount"].sum()

    # customer concentration within this category
    cust = None
    if "customer_id" in scoped.columns and scoped["customer_id"].notna().any():
        cust = scoped.groupby("customer_id")["amount"].sum().sort_values(ascending=False)

    span_days = (scoped["date"].max() - scoped["date"].min()).days + 1

    # average revenue per line-item, category vs shop (fair like-for-like)
    qty_col = "quantity" if "quantity" in scoped.columns and scoped["quantity"].notna().any() else None
    cat_items = float(scoped[qty_col].sum()) if qty_col else float(len(scoped))
    all_items = float(all_txns[qty_col].sum()) if qty_col and qty_col in all_txns else float(len(all_txns))
    per_item = rev / cat_items if cat_items else 0.0
    all_per_item = all_rev / all_items if all_items else 0.0

    return dict(value=value, field=field, rev=rev, share=share, orders=orders,
                aov=aov, all_aov=all_aov, monthly=monthly, all_monthly=all_monthly,
                prod=prod, weekday=weekday, cust=cust, span_days=span_days,
                total_rev=total_rev, per_item=per_item, all_per_item=all_per_item)


# ---------------------------------------------------------------------------
# CANDIDATE INSIGHTS — each returns a dict or None. Score = business priority
# (0-100). _mag is effect size for tie-breaks; _angle groups similar findings.
# ---------------------------------------------------------------------------

def _c_revenue_concentration(c) -> dict | None:
    """Is the whole shop leaning on this one category? (revenue risk)"""
    if c["share"] < 35 or c["total_rev"] <= 0:
        return None
    return {
        "type": "warning", "highlight": _pct(c["share"]), "_angle": "concentration",
        "score": 92, "_mag": c["share"],
        "text": f"{c['value']} is {_pct(c['share'])} of your entire revenue — a heavy dependence on one category.",
        "action": (f"Protect it and diversify: never let {c['value']} stock out or drop in quality, and "
                   f"build up your #2 category so one bad month here doesn't sink the shop."),
    }


def _c_small_but_present(c) -> dict | None:
    """Tiny share — candidate to cut or grow deliberately."""
    if c["share"] >= 6 or c["rev"] <= 0:
        return None
    return {
        "type": "neutral", "highlight": _pct(c["share"]), "_angle": "concentration",
        "score": 60, "_mag": 6 - c["share"],
        "text": f"{c['value']} brings in only {_pct(c['share'])} of revenue — it's a minor line right now.",
        "action": (f"Decide deliberately: either promote {c['value']} for a month to see if demand is there, "
                   f"or free up the menu space and prep time for something that sells."),
    }


def _c_momentum_vs_shop(c) -> dict | None:
    """Category growth compared to the whole shop — the consultant's key lens."""
    m = c["monthly"]
    am = c["all_monthly"]
    if len(m) < 3 or len(am) < 3:
        return None
    # recent 2 months vs prior 2, for this category and for the shop
    def growth(series):
        s = series.sort_index()
        recent = s.iloc[-2:].mean()
        prior = s.iloc[-4:-2].mean() if len(s) >= 4 else s.iloc[:-2].mean()
        return (recent - prior) / prior * 100 if prior else 0.0
    cat_g = growth(m)
    shop_g = growth(am)
    diff = cat_g - shop_g
    if abs(diff) < 12:  # moving with the shop — not a story
        return None
    if diff < 0:
        return {
            "type": "warning", "highlight": _pct(cat_g), "_angle": "momentum",
            "score": 88, "_mag": abs(diff),
            "text": (f"{c['value']} is lagging the rest of your shop — it moved {_pct(cat_g)} recently while "
                     f"the whole business moved {_pct(shop_g)}."),
            "action": (f"Something specific is dragging {c['value']} down. Check the top items in it for a price "
                       f"hike, a recipe change, or a supplier swap in the last 6-8 weeks, and fix that first."),
        }
    return {
        "type": "positive", "highlight": _pct(cat_g), "_angle": "momentum",
        "score": 84, "_mag": abs(diff),
        "text": (f"{c['value']} is outgrowing the rest of your shop — up {_pct(cat_g)} recently vs "
                 f"{_pct(shop_g)} overall."),
        "action": (f"Lean into it while it's hot: give {c['value']} prime menu placement and train staff to "
                   f"suggest it. Winning categories deserve more visibility, not equal billing."),
    }


def _c_trend_direction(c) -> dict | None:
    """Sustained direction over the available months (fallback when momentum-vs-shop doesn't fire)."""
    m = c["monthly"].sort_index()
    if len(m) < 3:
        return None
    x = np.arange(len(m))
    slope = np.polyfit(x, m.values, 1)[0]
    avg = m.mean()
    if avg <= 0:
        return None
    slope_pct = slope / avg * 100  # % of average per month
    if abs(slope_pct) < 8:
        return None
    if slope_pct < 0:
        return {
            "type": "warning", "highlight": _pct(abs(slope_pct)) + "/mo", "_angle": "trend",
            "score": 72, "_mag": abs(slope_pct),
            "text": f"{c['value']} has been sliding — losing about {_pct(abs(slope_pct))} of its average each month.",
            "action": (f"Don't wait for it to bottom out. Run one focused promotion on {c['value']} this month "
                       f"and watch whether it's a demand problem or an execution problem."),
        }
    return {
        "type": "positive", "highlight": _pct(slope_pct) + "/mo", "_angle": "trend",
        "score": 66, "_mag": slope_pct,
        "text": f"{c['value']} is climbing steadily — gaining roughly {_pct(slope_pct)} of its average each month.",
        "action": f"Keep the momentum: make sure {c['value']} never runs short during peak hours.",
    }


def _c_product_concentration(c) -> dict | None:
    """Within the category, is one item carrying everything? (fragility)"""
    p = c["prod"]
    if p is None or len(p) < 3 or p.sum() <= 0:
        return None
    top_share = p.iloc[0] / p.sum() * 100
    if top_share < 55:
        return None
    return {
        "type": "warning", "highlight": _pct(top_share), "_angle": "product-mix",
        "score": 80, "_mag": top_share,
        "text": (f"Inside {c['value']}, '{p.index[0]}' alone is {_pct(top_share)} of the category — "
                 f"the rest barely sell."),
        "action": (f"That's fragile: if '{p.index[0]}' dips, the whole category dips. Push your #2 and #3 "
                   f"items in {c['value']} with a combo or a staff recommendation to spread the risk."),
    }


def _c_dead_weight(c) -> dict | None:
    """Items in the category that basically don't sell — menu clutter."""
    p = c["prod"]
    if p is None or len(p) < 4 or p.sum() <= 0:
        return None
    tail = p[p / p.sum() < 0.03]  # each under 3% of the category
    if len(tail) < 2:
        return None
    return {
        "type": "neutral", "highlight": f"{len(tail)} items", "_angle": "product-mix",
        "score": 58, "_mag": len(tail),
        "text": (f"{len(tail)} items in {c['value']} each make up under 3% of the category — they add menu "
                 f"clutter and prep complexity without pulling weight."),
        "action": (f"Review these {len(tail)} for the chop. A tighter menu in {c['value']} means faster "
                   f"service, less waste, and fresher stock on the items that do sell."),
    }


def _c_aov_gap(c) -> dict | None:
    """Does this category's line-item value run high/low vs other categories?
    Compares like with like — average revenue per ITEM in this category vs the
    shop-wide average per item — so a single-item category isn't unfairly
    flagged for being smaller than a whole multi-item bill."""
    per_item = c.get("per_item")
    all_per_item = c.get("all_per_item")
    if not per_item or not all_per_item or c["orders"] < 15:
        return None
    diff = (per_item - all_per_item) / all_per_item * 100
    if abs(diff) < 30:  # needs a real gap to be worth a card
        return None
    if diff > 0:
        return {
            "type": "positive", "highlight": _fmt_inr(per_item), "_angle": "basket",
            "score": 68, "_mag": abs(diff),
            "text": (f"{c['value']} items sell at {_pct(diff)} above your average item price "
                     f"({_fmt_inr(per_item)} vs {_fmt_inr(all_per_item)} shop-wide) — it's a premium category."),
            "action": (f"Premium items reward visibility: put {c['value']}'s best sellers where eyes land first "
                       f"and have staff lead with them to lift the average check."),
        }
    return {
        "type": "neutral", "highlight": _fmt_inr(per_item), "_angle": "basket",
        "score": 52, "_mag": abs(diff),
        "text": (f"{c['value']} items sell cheap — {_pct(abs(diff))} below your average item price "
                 f"({_fmt_inr(per_item)} vs {_fmt_inr(all_per_item)} shop-wide)."),
        "action": (f"Low ticket isn't bad if volume is high, but bundle {c['value']} with a higher-margin "
                   f"add-on so each order carries more."),
    }


def _c_weekday_skew(c) -> dict | None:
    """Is the category lopsided toward certain days? (staffing/prep signal)"""
    w = c["weekday"].dropna()
    if len(w) < 5 or w.sum() <= 0:
        return None
    peak_share = w.max() / w.sum() * 100
    even_share = 100 / len(w)
    if peak_share < even_share * 1.8:  # not lopsided enough to matter
        return None
    return {
        "type": "neutral", "highlight": str(w.idxmax()), "_angle": "timing",
        "score": 50, "_mag": peak_share,
        "text": f"{c['value']} is concentrated on {w.idxmax()}s — {_pct(peak_share)} of its sales land that day.",
        "action": (f"Prep and roster for it: make sure {w.idxmax()} has the stock and hands for {c['value']}, "
                   f"and consider a slow-day offer to smooth out the rest of the week."),
    }


def _c_customer_concentration(c) -> dict | None:
    """Is a small set of customers the whole category? (loyalty vs risk)"""
    cust = c["cust"]
    if cust is None or len(cust) < 8 or cust.sum() <= 0:
        return None
    top10 = cust.head(max(1, len(cust) // 10)).sum() / cust.sum() * 100
    if top10 < 40:
        return None
    return {
        "type": "warning", "highlight": _pct(top10), "_angle": "customers",
        "score": 76, "_mag": top10,
        "text": (f"Your top 10% of customers drive {_pct(top10)} of {c['value']} — it leans on a loyal few."),
        "action": (f"That loyalty is an asset and a risk. Get these regulars onto a simple loyalty or WhatsApp "
                   f"list so a few of them drifting away doesn't quietly gut {c['value']}."),
    }


_CANDIDATES = [
    _c_revenue_concentration,
    _c_small_but_present,
    _c_momentum_vs_shop,
    _c_trend_direction,
    _c_product_concentration,
    _c_dead_weight,
    _c_aov_gap,
    _c_weekday_skew,
    _c_customer_concentration,
]
