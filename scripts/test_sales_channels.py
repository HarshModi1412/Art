"""
Sales from several places at once: website, Amazon, Shopify, uploaded files.

  1. Each source owns its slice: re-pulling Shopify replaces only Shopify;
     an upload "replace" replaces only uploads; sample data goes when real
     data arrives. (Before: a platform pull replaced EVERYTHING.)
  2. Sales / Sub-Category Analytics: the split by channel, a filter, and no
     split when there is only one channel.

Run: python scripts/test_sales_channels.py
"""
from __future__ import annotations

import os
import secrets
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["CAFEX_DATA_DIR"] = tempfile.mkdtemp(prefix="chan_")
os.environ.setdefault("LAUNCH_MODE", "true")
os.environ["AUTOPLAN_SCHEDULER"] = "off"

import pandas as pd  # noqa: E402

PASSED = FAILED = 0


def check(label, cond, extra=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  ✓ {label}")
    else:
        FAILED += 1
        print(f"  ✗ {label}" + (f"  [{extra}]" if extra else ""))


from backend.core import analytics, smart  # noqa: E402

df = pd.read_csv(os.path.join(os.path.dirname(__file__), "..", "data", "sample_transactions.csv"),
                 parse_dates=["date"])
E = "multi@shop.local"

print("\n== 1. each source owns its slice ==")
smart.save_sales(E, df.iloc[:900], {}, channel="sample")
smart.save_sales(E, df.iloc[:500], {}, channel="upload")
t = smart.load_sales(E)
check("sample data is dropped when real data arrives", set(t["channel"]) == {"upload"}, t["channel"].value_counts().to_dict())
smart.save_sales(E, df.iloc[500:800], {}, channel="shopify")
smart.save_sales(E, df.iloc[800:1000], {}, channel="amazon")
t = smart.load_sales(E)
check("a platform pull ADDS its sales, it does not wipe the rest",
      t["channel"].value_counts().to_dict() == {"upload": 500, "shopify": 300, "amazon": 200},
      t["channel"].value_counts().to_dict())
smart.save_sales(E, df.iloc[500:600], {}, channel="shopify")
t = smart.load_sales(E)
check("re-pulling a platform replaces only that platform",
      t["channel"].value_counts().to_dict() == {"upload": 500, "shopify": 100, "amazon": 200},
      t["channel"].value_counts().to_dict())
smart.save_sales(E, df.iloc[1000:1041], {}, mode="append", channel="upload")
smart.save_sales(E, df.iloc[:50], {}, mode="replace", channel="upload")
t = smart.load_sales(E)
check("an upload 'replace' replaces only uploaded rows",
      t["channel"].value_counts().to_dict() == {"upload": 50, "shopify": 100, "amazon": 200},
      t["channel"].value_counts().to_dict())
old = df.iloc[:40].copy()
smart.save_sales("legacy@shop.local", old, {}, channel=None)
smart.save_sales("legacy@shop.local", df.iloc[40:60], {}, channel="shopify")
t2 = smart.load_sales("legacy@shop.local")
check("rows saved before channels existed count as uploads",
      t2["channel"].value_counts().to_dict() == {"upload": 40, "shopify": 20}, t2["channel"].value_counts().to_dict())

print("\n== 2. split and filter ==")
sp = analytics.channel_split(t)
check("the split names every channel", [c["id"] for c in sp["channels"]] == ["amazon", "shopify", "upload"]
      or {c["id"] for c in sp["channels"]} == {"amazon", "shopify", "upload"}, str(sp["channels"]))
check("with readable names", {c["label"] for c in sp["channels"]} == {"Amazon", "Shopify", "Uploaded files"})
check("shares add up to 100%", abs(sum(c["share"] for c in sp["channels"]) - 100) < 0.5)
check("and a monthly breakdown", sp["monthly"] and len(sp["monthly"]["series"]) == 3)
one = analytics.channel_split(analytics.filter_channel(t, "amazon"))
check("one channel: nothing to split, the screen hides it", not one["multi"])
check("filtering keeps only that channel", len(analytics.filter_channel(t, "amazon")) == 200)
check("'all' or nothing keeps everything", len(analytics.filter_channel(t, "")) == len(t)
      and len(analytics.filter_channel(t, "all")) == len(t))

print("\n== 3. through the API ==")
from fastapi.testclient import TestClient  # noqa: E402
from backend.main import app  # noqa: E402
c = TestClient(app)
em = f"api{secrets.token_hex(3)}@shop.local"
tok = c.post("/api/register", json={"email": em, "password": "pw123456"}).json()["token"]
H = {"Authorization": "Bearer " + tok, "X-Session-Id": "ch-" + secrets.token_hex(3)}
smart.save_sales(em, df.iloc[:700], {}, channel="upload")
r = c.get("/api/analytics", headers=H)
check("Sales Analytics with one channel: no split", r.status_code == 200
      and not r.json()["channel_split"]["multi"], r.text[:200])
smart.save_sales(em, df.iloc[700:1041], {}, channel="amazon")
H["X-Session-Id"] = "ch-" + secrets.token_hex(3)
r = c.get("/api/analytics", headers=H)
d = r.json()
check("with two: the split is there", d["channel_split"]["multi"] and len(d["channel_split"]["channels"]) == 2)
all_rev = d["kpis"]["revenue"]
r = c.get("/api/analytics?channel=amazon", headers=H)
check("filtered to Amazon, revenue is Amazon's", r.status_code == 200
      and abs(r.json()["kpis"]["revenue"] - next(x["revenue"] for x in d["channel_split"]["channels"]
                                                    if x["id"] == "amazon")) < 1, r.text[:200])
check("and the split still describes everything", r.json()["channel_split"]["multi"] and r.json()["channel"] == "amazon")
check("totals still add up", abs(sum(x["revenue"] for x in d["channel_split"]["channels"]) - all_rev) < 1)
r = c.get("/api/subcategory?channel=upload", headers=H)
check("Sub-Category Analytics filters too", r.status_code == 200 and r.json()["channel"] == "upload"
      and r.json()["channel_split"]["multi"], r.text[:200])
r = c.get("/api/analytics?channel=wix", headers=H)
check("a channel with no sales says so", r.status_code == 400 and "No sales" in r.text)

print("\n== 4. product codes become names ==")
from backend.core import mapper, products  # noqa: E402
codes = df.copy()
names = sorted(codes["product"].unique())
code_of = {n: str(5000 + i) for i, n in enumerate(names)}
codes["product"] = codes["product"].map(code_of).astype(int)
check("a Product column of codes is flagged at mapping",
      mapper.suggest_mapping(codes.rename(columns={"product": "Item"}))["_product_codes"] is True)
check("a column of names is not", not mapper.product_is_codes(df, "product"))
mv = analytics.sales_analytics(codes).get("product_movers")
check("the movers chart says it is showing codes", mv and mv["codes"], str(mv)[:120])
P = "codes@shop.local"
first = names[0]
products.upsert_product(P, {"name": first.split(",")[0], "sku": code_of[first], "price": 100})
smart.save_sales(P, codes, {}, channel="upload")
named = smart.session_sales(P)
check("a code that matches a product's SKU shows the product's name",
      first.split(",")[0] in set(named["product"]) and int(code_of[first]) not in set(named["product"]),
      str(sorted(set(map(str, named["product"])))[:5]))
fl = codes.copy()
fl["product"] = fl["product"].astype(float)
smart.save_sales(P, fl, {}, channel="upload")
check("even when the codes were read as decimals (5000.0)",
      first.split(",")[0] in set(smart.session_sales(P)["product"]))

print(f"\n{PASSED} passed, {FAILED} failed")
sys.exit(1 if FAILED else 0)
