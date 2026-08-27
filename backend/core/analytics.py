"""
Analytics engine — web port of modules/sales_analytics.py and modules/rfm.py.

Instead of rendering Streamlit widgets, every function returns plain dict/list
structures that the frontend turns into Plotly charts and tables.
"""
import numpy as np
import pandas as pd


# =========================================================
# SALES ANALYTICS  (port of render_sales_analytics)
# =========================================================
def sales_analytics(txns: pd.DataFrame) -> dict:
    df = txns.copy()
    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()

    kpis = {
        "revenue": float(df["amount"].sum()),
        "orders": int(df["order_id"].nunique()) if "order_id" in df else int(len(df)),
        "customers": int(df["customer_id"].nunique()) if "customer_id" in df else None,
        "avg_order_value": None,
        "date_from": df["date"].min().strftime("%d %b %Y"),
        "date_to": df["date"].max().strftime("%d %b %Y"),
    }
    if kpis["orders"]:
        kpis["avg_order_value"] = kpis["revenue"] / kpis["orders"]

    monthly = df.groupby("month")["amount"].sum().reset_index()
    monthly_trend = {
        "x": monthly["month"].dt.strftime("%Y-%m").tolist(),
        "y": monthly["amount"].round(2).tolist(),
    }

    by_category = None
    if "category" in df.columns:
        cat = df.groupby("category")["amount"].sum().sort_values(ascending=False).head(12)
        by_category = {"x": cat.index.astype(str).tolist(), "y": cat.round(2).tolist()}

    top_products = None
    if "product" in df.columns:
        prod = df.groupby("product")["amount"].sum().sort_values(ascending=False).head(10)
        top_products = {"x": prod.round(2).tolist()[::-1], "y": prod.index.astype(str).tolist()[::-1]}

    weekday = df.groupby(df["date"].dt.day_name())["amount"].sum()
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday = weekday.reindex([d for d in order if d in weekday.index])
    weekday_pattern = {"x": weekday.index.tolist(), "y": weekday.round(2).tolist()}

    forecast = sales_forecast(df)
    return {
        "kpis": kpis,
        "monthly_trend": monthly_trend,
        "by_category": by_category,
        "top_products": top_products,
        "weekday_pattern": weekday_pattern,
        "forecast": forecast,
        "insights": _prioritize_insights(generate_sales_insights(df, forecast=forecast), df),
    }


# Priority weight per insight — higher = more decision-driving. Anything the
# owner can literally do tomorrow (bundle these two items, run a Monday offer)
# beats "remember what went well in August". The strip keeps only the top few.
_INSIGHT_PRIORITY = {
    "menu_bundle": 100,      # sell THIS slow item with THAT drink — most actionable
    "forecast_down": 95, "forecast_up": 70,
    "weekday_pattern": 85,   # run a Monday offer / staff up Friday
    "revenue_down": 90, "worst_month": 40, "best_month": 25,
    "aov": 80,               # upsell line — concrete script for staff
    "menu_star": 55, "menu_puzzle": 45,
    "top_category": 50,
}
_DEFAULT_PRIORITY = 30


def _prioritize_insights(insights: list[dict], df: pd.DataFrame, keep: int = 5) -> list[dict]:
    """Keep only the most actionable insights. We drop low-signal ones (e.g. a
    'slowest item' built on a 1-unit fluke), score the rest by how much they
    drive a decision, and return the top `keep` — fewer, sharper cards beat a
    wall of text an owner won't read."""
    scored = []
    for ins in insights:
        key = ins.get("key", "")
        # map raw keys to priority buckets
        if key.startswith("menu_bundle") or (ins.get("type") == "warning" and "sold the least" in ins.get("text", "")):
            bucket = "menu_bundle"
        elif "Star" in ins.get("text", "") and ins.get("type") == "positive":
            bucket = "menu_star"
        elif "Puzzle" in ins.get("text", ""):
            bucket = "menu_puzzle"
        elif key in _INSIGHT_PRIORITY:
            bucket = key
        elif "busiest day" in ins.get("text", ""):
            bucket = "weekday_pattern"
        elif "each customer spends" in ins.get("text", ""):
            bucket = "aov"
        elif "most money" in ins.get("text", ""):
            bucket = "top_category"
        else:
            bucket = key

        # drop low-signal menu insights built on tiny volumes (1-2 unit "slowest item")
        import re as _re
        m = _re.search(r"only (\d+) units", ins.get("text", ""))
        if m and int(m.group(1)) < 5:
            continue

        prio = _INSIGHT_PRIORITY.get(bucket, _DEFAULT_PRIORITY)
        # a real revenue drop always matters; a tiny month-to-month wobble doesn't
        if bucket in ("revenue_down", "worst_month", "best_month"):
            mm = _re.search(r"([\d.]+)%", ins.get("text", ""))
            if mm and float(mm.group(1)) < 10:
                continue
        scored.append((prio, ins))

    scored.sort(key=lambda t: -t[0])
    # keep only those with a concrete action, then top-N
    actionable = [ins for _, ins in scored if ins.get("action")]
    passive = [ins for _, ins in scored if not ins.get("action")]
    return (actionable + passive)[:keep]


# =========================================================


def _weekday_factors(series: pd.Series) -> dict:
    overall = max(series.mean(), 1e-9)
    return (series.groupby(series.index.dayofweek).mean() / overall).clip(lower=0.2).to_dict()


def _m_naive_weekday(train: pd.Series, future_idx) -> "np.ndarray":
    """Model A — seasonal naive: average of the same weekday over the last 4 weeks."""
    tail = train.tail(28)
    wk = tail.groupby(tail.index.dayofweek).mean()
    fallback = train.tail(14).mean()
    return np.array([max(wk.get(d.dayofweek, fallback), 0.0) for d in future_idx])


def _m_linear_weekday(train: pd.Series, future_idx) -> "np.ndarray":
    """Model B — linear trend on seasonally-adjusted revenue, re-seasonalized."""
    factors = _weekday_factors(train)
    adj = train / train.index.dayofweek.map(lambda d: factors.get(d, 1.0))
    t = np.arange(len(adj), dtype=float)
    b, a = np.polyfit(t, adj.values, 1)
    ft = np.arange(len(adj), len(adj) + len(future_idx), dtype=float)
    return np.maximum((a + b * ft) * np.array([factors.get(d.dayofweek, 1.0) for d in future_idx]), 0.0)


def _m_ses_weekday(train: pd.Series, future_idx, alpha: float = 0.3) -> "np.ndarray":
    """Model C — exponential smoothing of the level, re-seasonalized by weekday."""
    factors = _weekday_factors(train)
    adj = (train / train.index.dayofweek.map(lambda d: factors.get(d, 1.0))).values
    level = adj[0]
    for v in adj[1:]:
        level = alpha * v + (1 - alpha) * level
    return np.maximum(level * np.array([factors.get(d.dayofweek, 1.0) for d in future_idx]), 0.0)


def _m_drift_weekday(train: pd.Series, future_idx) -> "np.ndarray":
    """Model D — drift: recent 14-day level + average daily drift, re-seasonalized."""
    factors = _weekday_factors(train)
    adj = train / train.index.dayofweek.map(lambda d: factors.get(d, 1.0))
    level = adj.tail(14).mean()
    drift = (adj.tail(14).mean() - adj.head(14).mean()) / max(len(adj) - 14, 1)
    steps = np.arange(1, len(future_idx) + 1)
    return np.maximum((level + drift * steps) * np.array([factors.get(d.dayofweek, 1.0) for d in future_idx]), 0.0)


_FORECAST_MODELS = {
    "Seasonal naive (4-week weekday avg)": _m_naive_weekday,
    "Linear trend + weekday seasonality": _m_linear_weekday,
    "Exponential smoothing + weekday seasonality": _m_ses_weekday,
    "Drift + weekday seasonality": _m_drift_weekday,
}


def sales_forecast(df: pd.DataFrame, horizon_days: int = 30) -> dict | None:
    """Model competition with an honest train/test split:
    hold out the last 14 days, train every candidate on the rest, score each
    on the holdout (MAE, with MAPE reported), refit the winner on ALL data,
    then forecast the next `horizon_days`. The winning model and its backtest
    error are returned so the UI can show them."""
    daily = df.groupby(df["date"].dt.normalize())["amount"].sum()
    if len(daily) < 21:  # need >= 1 week of test on top of a sane train window
        return None
    idx = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    daily = daily.reindex(idx, fill_value=0.0)

    test_days = 14 if len(daily) >= 42 else 7
    train, test = daily.iloc[:-test_days], daily.iloc[-test_days:]

    scores = {}
    for name, fn in _FORECAST_MODELS.items():
        try:
            pred = fn(train, test.index)
            mae = float(np.mean(np.abs(pred - test.values)))
            denom = np.where(test.values > 0, test.values, np.nan)
            mape = float(np.nanmean(np.abs(pred - test.values) / denom) * 100)
            scores[name] = {"mae": round(mae, 2), "mape": round(mape, 1)}
        except Exception:
            continue
    if not scores:
        return None
    best = min(scores, key=lambda n: scores[n]["mae"])

    # refit the winner on the FULL history and forecast forward
    future_idx = pd.date_range(idx[-1] + pd.Timedelta(days=1), periods=horizon_days, freq="D")
    fcst = _FORECAST_MODELS[best](daily, future_idx)

    hist_tail = daily.tail(60)
    last_30 = float(daily.tail(min(30, len(daily))).sum())
    next_30 = float(fcst[:30].sum()) if horizon_days >= 30 else float(fcst.sum())
    pct = (next_30 - last_30) / max(last_30, 1e-9) * 100
    return {
        "hist_x": [d.strftime("%Y-%m-%d") for d in hist_tail.index],
        "hist_y": [round(v, 2) for v in hist_tail.values],
        "fcst_x": [d.strftime("%Y-%m-%d") for d in future_idx],
        "fcst_y": [round(v, 2) for v in fcst],
        "next_30_total": round(next_30, 0),
        "vs_last_30_pct": round(pct, 1),
        "model": best,
        "backtest_mape_pct": scores[best]["mape"],
        "backtest_mae": scores[best]["mae"],
        "models_tried": scores,
    }


def _menu_insights_safe(df, me=None):
    try:
        from backend.core.menu_engineering import menu_insights
        return menu_insights(df, me=me)
    except Exception:
        return []


def _menu_engineering_safe(df):
    try:
        from backend.core.menu_engineering import menu_engineering
        return menu_engineering(df)
    except Exception:
        return None


# RULE-BASED INSIGHTS  (port of generate_sales_insights)
# =========================================================
def generate_sales_insights(df: pd.DataFrame, forecast: dict | None = None) -> list[dict]:
    """
    Emits KEY + PARAMS, not sentences — i18n.render() turns these into
    plain-language text + action in the reader's language (see i18n.py).
    `highlight` names the figure the UI should colour and bold.

    `forecast` lets a caller that already ran sales_forecast() (e.g.
    sales_analytics()) pass the result in instead of paying for the
    4-model backtest a second time. Falls back to computing it here so
    this function still works standalone.
    """
    insights = []
    monthly = df.groupby(df["date"].dt.to_period("M"))["amount"].sum()
    if len(monthly) >= 2:
        change = (monthly.iloc[-1] - monthly.iloc[-2]) / max(monthly.iloc[-2], 1e-9) * 100
        pct_text = f"{abs(change):.1f}%"
        insights.append({
            "type": "positive" if change >= 0 else "negative",
            "key": "revenue_up" if change >= 0 else "revenue_down",
            "params": {"pct": pct_text},
            "highlight": pct_text,
        })
        best = monthly.idxmax()
        best_val = f"{monthly.max():,.0f}"
        insights.append({
            "type": "positive", "key": "best_month",
            "params": {"month": best.strftime("%b %Y"), "value": best_val},
            "highlight": best_val,
        })
        worst = monthly.idxmin()
        worst_val = f"{monthly.min():,.0f}"
        if worst != best:
            insights.append({
                "type": "warning", "key": "worst_month",
                "params": {"month": worst.strftime("%b %Y"), "value": worst_val},
                "highlight": worst_val,
            })
    if "category" in df.columns:
        cat = df.groupby("category")["amount"].sum().sort_values(ascending=False)
        if len(cat) >= 1:
            share = cat.iloc[0] / cat.sum() * 100
            share_text = f"{share:.0f}%"
            high = share >= 50
            insights.append({
                "type": "warning" if high else "neutral",
                "key": "category_concentration_high" if high else "category_concentration_ok",
                "params": {"pct": share_text, "name": str(cat.index[0])},
                "highlight": share_text,
            })
    weekday = df.groupby(df["date"].dt.day_name())["amount"].sum()
    if len(weekday) >= 2:
        gap_pct = (weekday.max() - weekday.min()) / max(weekday.max(), 1e-9) * 100
        gap_text = f"{gap_pct:.0f}%"
        insights.append({
            "type": "warning" if gap_pct >= 40 else "neutral",
            "key": "weekday_gap",
            "params": {"best": str(weekday.idxmax()), "worst": str(weekday.idxmin()), "pct": gap_text},
            "highlight": gap_text,
        })
    fc = forecast if forecast is not None else sales_forecast(df)
    if fc and abs(fc["vs_last_30_pct"]) >= 5:  # a ±1-2% forecast is flat — not worth a card
        val = f"{fc['next_30_total']:,.0f}"
        pct = f"{abs(fc['vs_last_30_pct']):.1f}%"
        up = fc["vs_last_30_pct"] >= 0
        top_product = "your top seller"
        if "product" in df.columns and df["product"].notna().any():
            top_product = str(df.groupby("product")["amount"].sum().idxmax())
        wk = df.groupby(df["date"].dt.day_name())["amount"].sum()
        peak_day, slow_day = (str(wk.idxmax()), str(wk.idxmin())) if len(wk) else ("weekend", "weekday")
        insights.append({
            "type": "positive" if up else "warning",
            "key": "forecast_up" if up else "forecast_down",
            "params": {"value": val, "pct": pct, "top_product": top_product,
                       "peak_day": peak_day, "slow_day": slow_day},
            "highlight": val,
        })
    if "order_id" in df.columns:
        aov = df.groupby("order_id")["amount"].sum()
        if len(aov) >= 5:
            aov_text = f"{aov.mean():,.0f}"
            uplift = f"{aov.mean() * 0.10 * len(aov):,.0f}"
            insights.append({
                "type": "neutral", "key": "aov",
                "params": {"value": aov_text, "uplift": uplift},
                "highlight": aov_text,
            })
    return insights


# =========================================================
# SUBCATEGORY TRENDS  (port of render_subcategory_trends)
# =========================================================
def _dimension_col(df: pd.DataFrame) -> str | None:
    """Pick the drill-down dimension. Prefer sub-category ONLY when it's
    actually populated — a mapped-but-mostly-empty column (e.g. PetPooja's
    'Variation', filled on <1% of rows) must fall back to category, or the
    whole drill-down silently breaks."""
    for col in ("subcategory", "category"):
        if col in df.columns and df[col].notna().mean() >= 0.3:
            return col
    # last resort: category even if sparse, else nothing
    return "category" if "category" in df.columns else None


def subcategory_trends(txns: pd.DataFrame) -> dict:
    df = txns.copy()
    col = _dimension_col(df)
    if col is None:
        return {"available": False, "reason": "No category or sub-category column was mapped."}

    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()
    totals_all = df.groupby(col)["amount"].sum().sort_values(ascending=False)
    top = totals_all.head(8).index

    series = []
    for name in top:
        sub = df[df[col] == name].groupby("month")["amount"].sum().reset_index()
        series.append({
            "name": str(name),
            "x": sub["month"].dt.strftime("%Y-%m").tolist(),
            "y": sub["amount"].round(2).tolist(),
        })

    # structured insights (key+params -> i18n renders plain language)
    insights = []
    if len(totals_all) >= 1:
        leader_share = totals_all.iloc[0] / totals_all.sum() * 100
        leader_text = f"{leader_share:.0f}%"
        high = leader_share >= 40
        insights.append({
            "type": "warning" if high else "positive",
            "key": "subcat_leader_high" if high else "subcat_leader_ok",
            "params": {"name": str(totals_all.index[0]), "pct": leader_text},
            "highlight": leader_text,
        })
    if len(totals_all) >= 2:
        laggard = str(totals_all.idxmin())
        laggard_val = f"{totals_all.min():,.0f}"
        insights.append({
            "type": "neutral", "key": "subcat_laggard",
            "params": {"name": laggard, "value": laggard_val},
            "highlight": laggard_val,
        })
    if len(totals_all) >= 3:
        top3_share = totals_all.head(3).sum() / totals_all.sum() * 100
        top3_text = f"{top3_share:.0f}%"
        high3 = top3_share >= 70
        insights.append({
            "type": "warning" if high3 else "neutral",
            "key": "subcat_top3_high" if high3 else "subcat_top3_ok",
            "params": {"pct": top3_text},
            "highlight": top3_text,
        })

    return {
        "available": True,
        "field": col,
        "series": series,
        "totals": {"x": totals_all.head(12).index.astype(str).tolist(), "y": totals_all.head(12).round(2).tolist()},
        "all_values": totals_all.index.astype(str).tolist(),
        "insights": insights,
    }


def subcategory_detail(txns: pd.DataFrame, value: str) -> dict:
    """
    Drill-down view for one specific category/sub-category — the "mini main
    page" a business owner would want when they pick one item from the filter:
    its own KPIs, its own trend, its own top products, its own insights.
    """
    df = txns.copy()
    # find the column that actually contains the clicked value — the overview
    # and the detail must agree on which dimension we're drilling into
    col = None
    for candidate in ("subcategory", "category"):
        if candidate in df.columns and value in df[candidate].astype(str).unique():
            col = candidate
            break
    if col is None:
        return {"available": False, "reason": "That category wasn't found in the current data."}

    scoped = df[df[col].astype(str) == value].copy()
    total_revenue = df["amount"].sum()
    scoped_revenue = scoped["amount"].sum()
    share_pct = (scoped_revenue / total_revenue * 100) if total_revenue else 0

    kpis = {
        "revenue": float(scoped_revenue),
        "orders": int(scoped["order_id"].nunique()) if "order_id" in scoped.columns else int(len(scoped)),
        "share_of_total_pct": round(float(share_pct), 1),
        "avg_order_value": None,
    }
    if kpis["orders"]:
        kpis["avg_order_value"] = kpis["revenue"] / kpis["orders"]

    scoped["month"] = scoped["date"].dt.to_period("M").dt.to_timestamp()
    monthly = scoped.groupby("month")["amount"].sum().reset_index()
    monthly_trend = {"x": monthly["month"].dt.strftime("%Y-%m").tolist(), "y": monthly["amount"].round(2).tolist()}

    top_products = None
    if "product" in scoped.columns and scoped["product"].nunique() > 1:
        prod = scoped.groupby("product")["amount"].sum().sort_values(ascending=False).head(8)
        top_products = {"x": prod.round(2).tolist()[::-1], "y": prod.index.astype(str).tolist()[::-1]}

    weekday = scoped.groupby(scoped["date"].dt.day_name())["amount"].sum()
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday = weekday.reindex([d for d in order if d in weekday.index])
    weekday_pattern = {"x": weekday.index.tolist(), "y": weekday.round(2).tolist()}

    # Consultant-style insights: draft many candidates, keep the ones that
    # actually apply to THIS category, and rank by business priority. See
    # detail_insights.py for the candidate library.
    from backend.core.detail_insights import build_detail_insights
    insights = build_detail_insights(scoped, df, value, col)

    return {
        "available": True,
        "field": col,
        "value": value,
        "kpis": kpis,
        "monthly_trend": monthly_trend,
        "top_products": top_products,
        "weekday_pattern": weekday_pattern,
        "insights": insights,
    }


# =========================================================
# RFM  (port of modules/rfm.calculate_rfm)
# =========================================================
def calculate_rfm(txns: pd.DataFrame) -> dict:
    df = txns.copy()
    if "customer_id" not in df.columns:
        return {"available": False, "reason": "No customer ID column was mapped — RFM needs one."}

    snapshot = df["date"].max() + pd.Timedelta(days=1)
    order_col = "order_id" if "order_id" in df.columns else "date"

    rfm = df.groupby("customer_id").agg(
        recency=("date", lambda x: (snapshot - x.max()).days),
        frequency=(order_col, "nunique"),
        monetary=("amount", "sum"),
    ).reset_index()

    # quintile scores (5 = best). Recency inverted: fewer days = higher score.
    rfm["R"] = pd.qcut(rfm["recency"].rank(method="first"), 5, labels=[5, 4, 3, 2, 1]).astype(int)
    rfm["F"] = pd.qcut(rfm["frequency"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
    rfm["M"] = pd.qcut(rfm["monetary"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
    rfm["RFM_score"] = rfm["R"].astype(str) + rfm["F"].astype(str) + rfm["M"].astype(str)

    def segment(row):
        if row.R >= 4 and row.F >= 4:
            return "Champions"
        if row.R >= 4 and row.F >= 2:
            return "Loyal / Potential"
        if row.R >= 3 and row.F <= 2:
            return "New Customers"
        if row.R == 2:
            return "At Risk"
        return "Hibernating"

    rfm["segment"] = rfm.apply(segment, axis=1)
    rfm["monetary"] = rfm["monetary"].round(2)

    seg_counts = rfm["segment"].value_counts()
    return {
        "available": True,
        "columns": ["customer_id", "recency", "frequency", "monetary", "R", "F", "M", "RFM_score", "segment"],
        "rows": rfm.sort_values("monetary", ascending=False).head(500).values.tolist(),
        "segments": {"labels": seg_counts.index.tolist(), "values": seg_counts.tolist()},
        "customer_count": int(len(rfm)),
    }


# =========================================================
# =========================================================
# MARKET BASKET ANALYSIS  (feeds cross-sell suggestions into win-back messages)
# =========================================================
def market_basket_pairs(txns: pd.DataFrame, item_field: str, min_pair_count: int = 3) -> dict[str, str]:
    """
    Simple, fast co-occurrence analysis: for every item, find the item most
    frequently bought in the same order ("customers who bought X also bought Y").
    Not a full Apriori implementation — a direct pairwise count is plenty for
    a shop-sized product catalog and stays instant even on thousands of orders.
    Returns {item: best_paired_item} for pairs seen together at least
    `min_pair_count` times, so rare coincidental pairings don't get suggested.
    """
    if "order_id" not in txns.columns or item_field not in txns.columns:
        return {}

    from collections import Counter, defaultdict

    order_baskets = txns.groupby("order_id")[item_field].apply(lambda s: list(set(s.dropna().astype(str))))
    pair_counts: dict[str, Counter] = defaultdict(Counter)
    for basket in order_baskets:
        if len(basket) < 2:
            continue
        for i, item_a in enumerate(basket):
            for item_b in basket:
                if item_a != item_b:
                    pair_counts[item_a][item_b] += 1

    best_pairs = {}
    for item, counter in pair_counts.items():
        if counter:
            top_item, count = counter.most_common(1)[0]
            if count >= min_pair_count:
                best_pairs[item] = top_item
    return best_pairs


# =========================================================
# AT-RISK CUSTOMER PROFILES  (feeds the AI win-back message generator)
# =========================================================
def at_risk_customers(txns: pd.DataFrame, limit: int = 60) -> list[dict]:
    """
    Re-run RFM, take the 'At Risk' segment, and build a marketing-analytics
    profile for each customer — not just their top product, but the signals a
    marketer would actually use to personalize outreach:

      - favorite_item / favorite_category : biggest revenue driver, by name
      - category_affinity                 : do they stick to one category or browse widely
      - price_tier                        : premium / mid / value spender vs the customer base
      - preferred_day                     : which weekday they usually show up
      - trend                             : were they buying more or less before they went quiet
      - cross_sell_item                   : from market basket analysis — what's commonly bought
                                             alongside their favorite item, a natural upsell hook
      - signal_strength                   : "strong" / "weak" — tells the AI whether it has enough
                                             real data to personalize, or should write something
                                             warm and generic instead of guessing

    Capped at `limit` customers (highest spend first) to keep AI calls fast and cheap.
    """
    rfm_result = calculate_rfm(txns)
    if not rfm_result.get("available"):
        return []

    cols = rfm_result["columns"]
    rows = rfm_result["rows"]
    idx = {c: i for i, c in enumerate(cols)}
    at_risk_ids = [r[idx["customer_id"]] for r in rows if r[idx["segment"]] == "At Risk"]
    if not at_risk_ids:
        return []

    df = txns.copy()
    overall_avg_amount = df.groupby("order_id")["amount"].sum().mean() if "order_id" in df.columns else df["amount"].mean()

    # item_field and market-basket pairs are dataset-wide — compute once, not per customer
    item_field = next((f for f in ("product", "subcategory", "category") if f in df.columns), None)
    basket_pairs = market_basket_pairs(df, item_field) if item_field else {}

    profiles = []
    for cid in at_risk_ids:
        cust_txns = df[df["customer_id"] == cid].sort_values("date")
        if cust_txns.empty:
            continue
        row = next(r for r in rows if r[idx["customer_id"]] == cid)
        frequency = int(row[idx["frequency"]])

        # --- favorite item / category by revenue ---
        favorite_item, favorite_category, category_affinity = None, None, None
        if item_field:
            counts = cust_txns.groupby(item_field)["amount"].sum().sort_values(ascending=False)
            if len(counts):
                favorite_item = str(counts.index[0])
                # affinity: how dominant is the #1 item vs everything else they buy
                category_affinity = round(float(counts.iloc[0] / counts.sum()) * 100, 0)
        if "category" in cust_txns.columns:
            cat_counts = cust_txns.groupby("category")["amount"].sum().sort_values(ascending=False)
            if len(cat_counts):
                favorite_category = str(cat_counts.index[0])

        # --- market basket cross-sell: what pairs well with their favorite item ---
        cross_sell_item = basket_pairs.get(favorite_item) if favorite_item else None

        # --- price tier vs the rest of the customer base ---
        cust_avg = cust_txns["amount"].mean()
        if overall_avg_amount > 0:
            ratio = cust_avg / overall_avg_amount
            price_tier = "premium" if ratio >= 1.25 else ("value" if ratio <= 0.75 else "mid-range")
        else:
            price_tier = "mid-range"

        # --- preferred day of week ---
        preferred_day = None
        if len(cust_txns) >= 3:
            day_counts = cust_txns["date"].dt.day_name().value_counts()
            if len(day_counts):
                preferred_day = str(day_counts.index[0])

        # --- trend: first half of their history vs second half (before they went quiet) ---
        trend = "steady"
        if frequency >= 4:
            mid = len(cust_txns) // 2
            first_half_avg = cust_txns.iloc[:mid]["amount"].mean()
            second_half_avg = cust_txns.iloc[mid:]["amount"].mean()
            if second_half_avg > first_half_avg * 1.15:
                trend = "was increasing spend before going quiet"
            elif second_half_avg < first_half_avg * 0.85:
                trend = "was already slowing down before going quiet"

        # --- signal strength: do we actually have enough to personalize, or should the AI improvise? ---
        signal_strength = "strong" if (frequency >= 2 and favorite_item) else "weak"

        display_name = None
        if "customer_name" in cust_txns.columns:
            names = cust_txns["customer_name"].dropna()
            if len(names):
                display_name = str(names.iloc[0]).strip() or None

        profiles.append({
            "customer_id": str(cid),
            "customer_name": display_name,
            "recency_days": int(row[idx["recency"]]),
            "frequency": frequency,
            "monetary": float(row[idx["monetary"]]),
            "last_purchase_date": cust_txns["date"].max().strftime("%d %b %Y"),
            "favorite_item": favorite_item or "—",
            "favorite_category": favorite_category or "—",
            "cross_sell_item": cross_sell_item,
            "category_affinity_pct": category_affinity,
            "price_tier": price_tier,
            "preferred_day": preferred_day,
            "trend": trend,
            "signal_strength": signal_strength,
        })

    profiles.sort(key=lambda p: p["monetary"], reverse=True)
    return profiles[:limit]
