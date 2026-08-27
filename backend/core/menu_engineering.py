"""
Menu engineering — the classic hospitality framework (Kasavana & Smith).

Every menu item is scored on two axes and dropped into one of four quadrants:

                     high popularity        low popularity
   high profit   ->  STAR                   PUZZLE
   low  profit   ->  PLOWHORSE              DOG

  - Star      : popular AND profitable        -> feature it, protect it
  - Plowhorse : popular but low margin         -> nudge margin up gently
  - Puzzle    : profitable but nobody buys it  -> promote / reposition
  - Dog       : unpopular AND low margin       -> bundle, rework, or cut

Since transaction exports rarely carry item COST, we can't compute true food-cost
margin. We use REVENUE PER ITEM as the profit proxy (higher-priced items are
treated as higher-margin) and UNITS SOLD as popularity — both directly available.
This is stated in the output so nobody mistakes it for a true cost-margin study.

The headline output is the SLOW MOVERS list (Dogs + Puzzles: the bottom sellers)
each paired with the beverage most likely to move it — a concrete bundle the
owner can put on the board tomorrow. Pairing uses real market-basket
co-occurrence when available (what actually gets bought together), and falls
back to the best-selling beverage when an item has no strong basket partner.
"""
import pandas as pd

from backend.core.analytics import market_basket_pairs

_BEVERAGE_HINTS = ("beverage", "drink", "coffee", "tea", "juice", "shake", "smoothie",
                   "soda", "latte", "cappuccino", "americano", "espresso", "mocha",
                   "frappe", "cooler", "lemonade", "cola", "beer", "wine", "cocktail")


def _is_beverage_row(product: str, category: str) -> bool:
    blob = f"{product} {category}".lower()
    return any(h in blob for h in _BEVERAGE_HINTS)


def _beverage_product_set(df: pd.DataFrame) -> set:
    """Which distinct products classify as a beverage. Classification only
    depends on (product, category), so we check each UNIQUE pair once —
    not once per transaction row, which used to make this O(rows) with a
    23-substring scan on every single row (very slow on large sales files)."""
    if "category" in df.columns:
        pairs = df[["product", "category"]].astype(str).drop_duplicates()
        return {p for p, c in zip(pairs["product"], pairs["category"]) if _is_beverage_row(p, c)}
    products = df["product"].astype(str).unique()
    return {p for p in products if _is_beverage_row(p, "")}


def _beverage_items(df: pd.DataFrame) -> pd.Series:
    """Revenue per beverage product, best-seller first."""
    bev_products = _beverage_product_set(df)
    if not bev_products:
        return pd.Series(dtype=float)
    bev = df[df["product"].astype(str).isin(bev_products)]
    if bev.empty:
        return pd.Series(dtype=float)
    return bev.groupby("product")["amount"].sum().sort_values(ascending=False)


def _best_beverage_partner(df: pd.DataFrame, beverage_set: set) -> dict[str, tuple[str, int]]:
    """For every item, the BEVERAGE most often bought in the same order, with
    the co-occurrence count. Unlike market_basket_pairs (which returns only the
    single top partner of any kind), this restricts partners to beverages — so
    a slow food item gets its real best-matching drink, not just any pairing.

    Built with vectorized pandas ops (dedup + a self-merge on order_id) instead
    of a per-order Python groupby().apply(lambda) — the old version ran a
    Python-level set()/list() conversion once per order, which took ~20s on a
    ~100k-order file. This is a couple of seconds even at that scale."""
    if "order_id" not in df.columns or not beverage_set:
        return {}
    items = df[["order_id", "product"]].dropna()
    items = items.assign(product=items["product"].astype(str)).drop_duplicates()
    if items.empty:
        return {}
    bev_items = items[items["product"].isin(beverage_set)].rename(columns={"product": "beverage"})
    food_items = items[~items["product"].isin(beverage_set)]
    if bev_items.empty or food_items.empty:
        return {}
    pairs = food_items.merge(bev_items, on="order_id", how="inner")
    if pairs.empty:
        return {}
    counts = pairs.groupby(["product", "beverage"]).size()
    best = counts.groupby(level=0).idxmax()
    return {item: (pair[1], int(counts[pair])) for item, pair in best.items()}


def menu_engineering(txns: pd.DataFrame) -> dict | None:
    """Classify items and build slow-item + beverage bundle recommendations."""
    df = txns.copy()
    if "product" not in df.columns or df["product"].isna().all():
        return None

    qty_col = "quantity" if "quantity" in df.columns and df["quantity"].notna().any() else None
    grp = df.groupby("product").agg(
        revenue=("amount", "sum"),
        units=("quantity", "sum") if qty_col else ("amount", "size"),
        orders=("order_id", "nunique") if "order_id" in df.columns else ("amount", "size"),
    )
    grp = grp[grp["revenue"] > 0]
    if len(grp) < 4:
        return None

    # popularity = units sold; profit proxy = revenue per unit (avg price)
    grp["avg_price"] = grp["revenue"] / grp["units"].clip(lower=1)
    pop_median = grp["units"].median()
    price_median = grp["avg_price"].median()

    def classify(r):
        hi_pop, hi_profit = r["units"] >= pop_median, r["avg_price"] >= price_median
        if hi_pop and hi_profit:
            return "Star"
        if hi_pop and not hi_profit:
            return "Plowhorse"
        if not hi_pop and hi_profit:
            return "Puzzle"
        return "Dog"

    grp["quadrant"] = grp.apply(classify, axis=1)

    # category lookup (for tagging + avoiding beverage-on-beverage bundles)
    cat_of = {}
    if "category" in df.columns:
        cat_of = df.groupby("product")["category"].agg(
            lambda s: s.dropna().astype(str).mode().iloc[0] if s.dropna().size else "").to_dict()

    # market-basket pairs (real "bought together") + best beverages as fallback
    bevs = _beverage_items(df)
    top_bev = bevs.index[0] if len(bevs) else None
    beverage_set = set(bevs.index)

    def is_bev(prod):
        return _is_beverage_row(str(prod), str(cat_of.get(prod, ""))) or prod in beverage_set

    bev_partner = _best_beverage_partner(df, beverage_set)

    # slow movers = Dogs first, then Puzzles; the items that need a push.
    # Ignore near-zero sellers (< 5 units): a 1-unit item is a data fluke or a
    # discontinued dish, not a slow-mover worth a combo. We want items that
    # sell steadily-but-weakly, where a bundle can actually lift volume.
    slow_all = grp[grp["quadrant"].isin(["Dog", "Puzzle"])]
    slow = slow_all[slow_all["units"] >= 5].sort_values("units")
    if slow.empty:  # tiny catalog / low volume — fall back so we still say something
        slow = slow_all.sort_values("units")
    bundles = []
    for prod, r in slow.iterrows():
        if is_bev(prod):
            continue  # don't recommend pairing a drink with a drink
        partner, reason = None, ""
        # 1) the beverage this item is ACTUALLY bought with most (real signal)
        bp = bev_partner.get(prod)
        if bp and bp[1] >= 3:
            partner = bp[0]
            reason = f"already bought together in {bp[1]} orders — a pairing your customers picked themselves"
        # 2) else the best-selling beverage overall (guaranteed footfall)
        elif top_bev:
            partner, reason = top_bev, "your best-selling drink — the most likely to carry a slow item"
        if not partner:
            continue
        bundles.append({
            "item": str(prod), "quadrant": r["quadrant"],
            "units": int(r["units"]), "revenue": round(float(r["revenue"]), 0),
            "pair_with": str(partner), "reason": reason,
            "category": str(cat_of.get(prod, "")),
        })

    quadrant_counts = grp["quadrant"].value_counts().to_dict()
    quadrant_points = [{
        "product": str(p), "units": int(r["units"]), "avg_price": round(float(r["avg_price"]), 1),
        "revenue": round(float(r["revenue"]), 0), "quadrant": r["quadrant"],
    } for p, r in grp.iterrows()]

    return {
        "method_note": ("Popularity = units sold; profitability is proxied by average price "
                        "(true food-cost margin isn't in POS exports). Big gaps are real; treat "
                        "borderline items as 'watch', not gospel."),
        "medians": {"units": round(float(pop_median), 1), "avg_price": round(float(price_median), 1)},
        "counts": quadrant_counts,
        "points": quadrant_points,
        "bundles": bundles[:8],
        "top_beverage": str(top_bev) if top_bev else None,
    }


def menu_insights(txns: pd.DataFrame, me: dict | None = None) -> list[dict]:
    """Prescriptive, specific insights for the analytics strip — action first.

    Pass a `me` already computed by menu_engineering() to skip recomputing it
    (menu_engineering does the expensive basket/beverage-pairing work)."""
    if me is None:
        me = menu_engineering(txns)
    if not me:
        return []
    out = []

    # headline: the slowest item, named, with its beverage bundle
    if me["bundles"]:
        b = me["bundles"][0]
        combo = f"{b['item']} + {b['pair_with']}"
        out.append({
            "type": "warning",
            "text": f"{b['item']} sold the least — only {b['units']} units. It's a {b['quadrant']} "
                    f"on your menu (few buyers, thin pull).",
            "action": f"Bundle it: put a '{combo}' combo on the board at a small saving vs buying "
                      f"separately ({b['reason']}). Slow food moves fastest when it rides on a drink "
                      f"people already want.",
            "highlight": b["item"],
        })

    # the puzzles: profitable items that sell steadily-but-weakly (food only).
    # Require >= 5 units so a 1-unit fluke or discontinued dish never shows,
    # and surface the one leaving the most money on the table (highest revenue).
    puzzles = [p for p in me["points"] if p["quadrant"] == "Puzzle"
               and not _is_beverage_row(p["product"], "") and p["units"] >= 5]
    if puzzles:
        puzzles.sort(key=lambda x: -x["revenue"])
        p = puzzles[0]
        out.append({
            "type": "neutral",
            "text": f"{p['product']} earns good margin (₹{p['avg_price']:.0f} avg) but barely sells "
                    f"({p['units']} units) — a hidden Puzzle.",
            "action": f"Move {p['product']} to the top of the menu and have staff suggest it at the "
                      f"counter for one week. Profitable items only need visibility, not discounts.",
            "highlight": p["product"],
        })

    # stars: protect them
    stars = [p for p in me["points"] if p["quadrant"] == "Star"]
    if stars:
        stars.sort(key=lambda x: -x["revenue"])
        s = stars[0]
        out.append({
            "type": "positive",
            "text": f"{s['product']} is your Star — high sales and healthy price. It carries the menu.",
            "action": f"Never discount {s['product']} or move it off the menu. Feature it, keep quality "
                      f"dead consistent, and pair slow items with it to pull them along.",
            "highlight": s["product"],
        })

    return out
