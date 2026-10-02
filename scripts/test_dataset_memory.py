"""
Guard for the second OOM on 2 October 2026: a seller opened Sales Analytics
right after a deploy and the 512MB instance was killed.

The home screen's first requests all worked on the whole sales table at once
on a cold process, each with its own copies: the session reload on every home
load, a full-frame copy inside RFM, the supply demand pass four times per page.
This checks the behaviour that fixed it and that the numbers did not change.

Run: python3 scripts/test_dataset_memory.py
"""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend import main  # noqa: E402
from backend.core import analytics, cache, memory, smart, supply, user_store  # noqa: E402

PASS = FAIL = 0


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}{(' (' + str(extra) + ')') if extra else ''}")
    else:
        FAIL += 1
        print(f"  ✗ {label}  <-- {extra}")


def sales(n, seed=1, products=40):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "order_id": [f"O{i // 2}" for i in range(n)],
        "customer_id": [f"C{x}" for x in rng.integers(0, max(2, n // 6), n)],
        "product": rng.choice([f"Item {i}" for i in range(products)], n),
        "date": pd.Timestamp("2026-01-01") + pd.to_timedelta(rng.integers(0, 200, n), unit="D"),
        "quantity": rng.integers(1, 4, n).astype(float),
        "amount": rng.uniform(5, 500, n).round(2),
    })


print("\n== 1. RFM gives exactly the old numbers ==")


def old_rfm(txns):
    """The implementation before this change, kept here as the reference."""
    df = txns.copy()
    snapshot = df["date"].max() + pd.Timedelta(days=1)
    order_col = "order_id" if "order_id" in df.columns else "date"
    rfm = df.groupby("customer_id").agg(
        recency=("date", lambda x: (snapshot - x.max()).days),
        frequency=(order_col, "nunique"), monetary=("amount", "sum")).reset_index()
    rfm["R"] = analytics._quintile(rfm["recency"], invert=True)
    rfm["F"] = analytics._quintile(rfm["frequency"])
    rfm["M"] = analytics._quintile(rfm["monetary"])
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
    return rfm.sort_values("monetary", ascending=False).head(500).values.tolist()


for n, seed in ((3, 1), (40, 2), (2000, 3), (9000, 4)):
    t = sales(n, seed)
    before = t.copy()
    new = analytics.calculate_rfm(t)
    check(f"{n} rows: same rows, scores and segments", new["rows"] == old_rfm(t))
    check(f"{n} rows: the input frame is untouched", t.equals(before))
t = sales(500, 9).drop(columns=["order_id"])
check("no order_id column: still counts by date", analytics.calculate_rfm(t)["rows"] == old_rfm(t))

print("\n== 2. one cold load per dataset, however many ask at once ==")
email = f"dm{int(time.time() * 1000)}@t.co"
smart.save_sales(email, sales(3000), {"files": "x"})
user_store._DF_CACHE.clear()
calls = {"n": 0}
real = user_store._load_df_uncached


def slow(email_, key, copy):
    calls["n"] += 1
    time.sleep(0.3)
    return real(email_, key, copy)


user_store._load_df_uncached = slow
got = []
ts = [threading.Thread(target=lambda: got.append(smart.load_sales(email))) for _ in range(4)]
[t.start() for t in ts]
[t.join() for t in ts]
user_store._load_df_uncached = real
check("four callers, one download", calls["n"] == 1, calls["n"])
check("every caller got the data", len(got) == 4 and all(len(g) == 3000 for g in got))
got[0]["amount"] = 0
check("each got its own copy (one cannot corrupt another)", float(got[1]["amount"].sum()) > 0)
shared = smart.load_sales(email, copy=False)
check("copy=False hands out the cached frame itself",
      shared is user_store._DF_CACHE[(email, smart.SALES_KEY)][1])

print("\n== 3. heavy work runs one at a time ==")
inside, peak = {"n": 0}, {"n": 0}
lock = threading.Lock()


def work():
    with memory.heavy():
        with lock:
            inside["n"] += 1
            peak["n"] = max(peak["n"], inside["n"])
        time.sleep(0.1)
        with lock:
            inside["n"] -= 1


ts = [threading.Thread(target=work) for _ in range(4)]
[t.start() for t in ts]
[t.join() for t in ts]
check("never two at once", peak["n"] == 1, peak["n"])


def nested():
    with memory.heavy():
        with memory.heavy():
            return "ok"


r = []
t = threading.Thread(target=lambda: r.append(nested()))
t.start()
t.join(5)
check("a gated call inside a gated call does not wait on itself", r == ["ok"])

print("\n== 4. the session's copy: loaded on use, reloaded when the data changes ==")
c = TestClient(main.app)
email2 = f"dm{int(time.time() * 1000) + 3}@t.co"
tok = c.post("/api/register", json={"email": email2, "password": "Test12345!"}).json()["token"]
SID = f"dm-{time.time_ns()}"
H = {"Authorization": "Bearer " + tok, "X-Session-Id": SID}
smart.save_sales(email2, sales(800, 5), {"files": "a"})
c.get("/api/smart/state", headers=H)
sess = main._data_sessions[SID]
check("the home screen no longer copies the table into the session", sess.txns_df is None)
r = c.get("/api/analytics?lang=en", headers=H)
check("Sales Analytics loads it when asked", r.status_code == 200 and sess.txns_df is not None
      and len(sess.txns_df) == 800, r.status_code)
smart.save_sales(email2, sales(1200, 6), {"files": "b"})     # e.g. another device
time.sleep(1.1)                                              # updated_at is to the second
smart.save_sales(email2, sales(1200, 6), {"files": "b"})
c.get("/api/smart/state", headers=H)
check("a new upload makes the home screen drop the stale copy", sess.txns_df is None)
r = c.get("/api/analytics?lang=en", headers=H)
check("and the next analytics request sees the new data", len(sess.txns_df) == 1200,
      None if sess.txns_df is None else len(sess.txns_df))

print("\n== 5. supply demand stats: computed once per data version ==")
email3 = f"dm{int(time.time() * 1000) + 5}@t.co"
smart.save_sales(email3, sales(1500, 7), {"files": "x"})
cache.clear(email3)
runs = {"n": 0}
real_ds = supply._demand_stats_uncached


def counting(e):
    runs["n"] += 1
    return real_ds(e)


supply._demand_stats_uncached = counting
for _ in range(4):
    supply.compute_inventory(email3)
check("four inventory checks, one pass over the sales", runs["n"] == 1, runs["n"])
time.sleep(1.1)
smart.save_sales(email3, sales(1600, 8), {"files": "y"})
supply.compute_inventory(email3)
check("new sales data recomputes it", runs["n"] == 2, runs["n"])
supply._demand_stats_uncached = real_ds
daily, piv, meta = supply._demand_stats(email3)
t = sales(1600, 8)
want = t.groupby(t["product"].str.lower())["quantity"].sum()
check("the numbers still come from every row", piv is not None and
      abs(float(piv.sum().sum()) - float(want.sum())) < 1e-6)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
