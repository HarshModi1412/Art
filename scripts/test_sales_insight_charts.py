"""
Guard for the Sales Analytics insight charts that replaced "Top products".

"Top products" drew SKU codes (3000, 4000...) on a numeric axis as hairlines,
and a ranking of totals said nothing a seller could act on. In its place:
best day to sell, when sales happen, products rising and falling, and new vs
returning customers. This checks their numbers and their edge cases.

Run: python3 scripts/test_sales_insight_charts.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from backend.core import analytics  # noqa: E402

PASS = FAIL = 0


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}{(' (' + str(extra) + ')') if extra else ''}")
    else:
        FAIL += 1
        print(f"  ✗ {label}  <-- {extra}")


def frame(days=365, n=12000, seed=2, hours=False):
    rng = np.random.default_rng(seed)
    d = pd.Timestamp("2025-10-01") + pd.to_timedelta(rng.integers(0, days, n), unit="D")
    if hours:
        d = d + pd.to_timedelta(rng.integers(10, 21, n), unit="h")
    dow = pd.Series(d).dt.dayofweek.values
    return pd.DataFrame({
        "order_id": [f"O{i}" for i in range(n)],
        "customer_id": [f"C{x}" for x in rng.integers(0, 2000, n)],
        "product": rng.choice([3000, 4000, 6500], n),          # numeric SKU names
        "date": d,
        "amount": rng.uniform(100, 500, n) * np.where(dow == 5, 1.5, 1.0),
    })


print("\n== 1. the payload ==")
r = analytics.sales_analytics(frame())
check("Top products is gone", "top_products" not in r)
check("the four insight charts are there",
      all(r.get(k) for k in ("best_days", "heatmap", "product_movers", "new_vs_returning")))

print("\n== 2. best day to sell ==")
bd = r["best_days"]
check("Saturday (+50% in the data) is the best day", bd["best"] == "Saturday", bd["best"])
check("by about the right margin", 25 <= bd["best_lift_pct"] <= 45, bd["best_lift_pct"])
# a typical day counts days with no sales as zero: one big day in a quiet month
t = pd.DataFrame({"order_id": ["a", "b"], "customer_id": ["x", "y"], "product": ["p", "p"],
                  "date": pd.to_datetime(["2026-01-05", "2026-01-31"]), "amount": [700.0, 100.0]})
b2 = analytics._best_days(t)
check("days with no sales count as zero", b2 and abs(b2["typical"] - 800 / 27) < 0.01, b2 and b2["typical"])
check("under two weeks of data: no weekday claim",
      analytics._best_days(t[t["date"] < "2026-01-10"]) is None)

print("\n== 3. when sales happen ==")
check("date-only data: day x month", r["heatmap"]["mode"] == "month")
check("12 months at most, 7 days", len(r["heatmap"]["x"]) <= 12 and len(r["heatmap"]["z"]) == 7)
hm = analytics.sales_analytics(frame(hours=True))["heatmap"]
check("data with times: day x hour", hm["mode"] == "hour" and hm["x"][0] == "10am", hm["x"][:2])
part = frame()
part = pd.concat([part, part.tail(1).assign(date=pd.Timestamp("2026-10-01"))])
check("a month with one day of data is left out",
      "Oct 26" not in analytics._sales_heatmap(part)["x"])

print("\n== 4. products rising and falling ==")
f = frame()
end = f["date"].max()
f.loc[(f["date"] > end - pd.Timedelta(days=30)) & (f["product"] == 4000), "amount"] *= 2
mv = analytics._product_movers(f)
check("the product that doubled leads", mv["top_gainer"] == "4000", mv["top_gainer"])
check("names are strings even when they are numbers", all(isinstance(y, str) for y in mv["y"]))
check("biggest gain first, biggest fall last", mv["x"] == sorted(mv["x"], reverse=True), mv["x"])
check("under 45 days of history: no movers", analytics._product_movers(frame(days=30)) is None)

print("\n== 5. new and returning customers ==")
nr = r["new_vs_returning"]
check("both series per month", len(nr["new"]) == len(nr["returning"]) == len(nr["x"]))
check("the first month is all new customers", nr["returning"][0] == 0)
check("shares are percentages", 0 <= nr["returning_share_pct"] <= 100)
check("no customer column: no chart",
      analytics._new_vs_returning(frame().drop(columns=["customer_id"])) is None)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
