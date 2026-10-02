"""
Guard for the 2 October 2026 outage: Render OOM-killed the 512MB instance in
the middle of a sales upload's "Confirm & save", and the seller saw "The server
did not answer, it may be starting up."

Two things were stacking up:
  1. Browser sessions were never dropped. Each holds its own copy of the sales
     table, and the browser mints a new session id on every logout, so dead
     sessions alone pushed the idle server toward the limit.
  2. /api/smart/map held the raw upload, the mapped frame, a re-downloaded
     copy of what it had just saved and a full insights pass all at once.

This checks the behaviour that fixed it, and that the seller-visible result of
Confirm & save did not change.

Run: python3 scripts/test_upload_memory.py
"""
import io
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend import main  # noqa: E402
from backend.core import smart, user_store  # noqa: E402

PASS = FAIL = 0


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}{(' (' + str(extra) + ')') if extra else ''}")
    else:
        FAIL += 1
        print(f"  ✗ {label}  <-- {extra}")


def sales_csv(n=400):
    df = pd.DataFrame({
        "ORDER_ID": [f"O{i // 2}" for i in range(n)],
        "CUSTOMER_ID": [f"C{i % 37}" for i in range(n)],
        "PRODUCT_NAME": [f"Item {i % 11}" for i in range(n)],
        "ORDER_DATE": pd.date_range("2026-01-01", periods=n, freq="6h").strftime("%Y-%m-%d"),
        "QUANTITY": [1 + i % 3 for i in range(n)],
        "REVENUE": [round(10 + (i % 50) * 3.5, 2) for i in range(n)],
    })
    return df.to_csv(index=False).encode()


c = TestClient(main.app)
email = f"mem{int(time.time() * 1000)}@t.co"
tok = c.post("/api/register", json={"email": email, "password": "Test12345!"}).json()["token"]
SID = f"mem-sess-{time.time_ns()}"
H = {"Authorization": "Bearer " + tok, "X-Session-Id": SID}

print("\n== 1. Confirm & save still saves, and answers the same way ==")
up = c.post("/api/smart/upload?kind=sales", headers=H,
            files={"files": ("sales.csv", io.BytesIO(sales_csv()), "text/csv")})
check("upload is staged", up.status_code == 200, up.status_code)
mapping = up.json().get("suggested_mapping") or {}
check("date and amount are recognised", mapping.get("date") and mapping.get("amount"), mapping)
r = c.post("/api/smart/map", headers=H, json={"kind": "sales", "mapping": mapping, "mode": "replace"})
body = r.json()
check("Confirm & save returns 200", r.status_code == 200, r.status_code)
check("it reports the rows it saved", body.get("rows") == 400 and body.get("added") == 400, body)
check("and the mode the seller picked", body.get("mode") == "replace")
check("data status still says sales are ready", (body.get("data") or {}).get("sales", {}).get("ready"))
check("insights are no longer built inside the save (nobody read them)", "insights" not in body)

sess = main._data_sessions.get(SID)
check("the raw upload is gone from the session once saved",
      sess is not None and "smart_pending_sales" not in sess.raw_dfs)
check("the session can still run the analytics endpoints",
      sess is not None and sess.txns_df is not None and len(sess.txns_df) == 400)
saved = smart.load_sales(email)
check("the saved dataset loads back", saved is not None and len(saved) == 400)

print("\n== 2. the just-saved table is served from memory, not re-downloaded ==")
hit = user_store._DF_CACHE.get((email, smart.SALES_KEY))
check("save seeded the dataset cache", hit is not None)
a, b = smart.load_sales(email), smart.load_sales(email)
a["amount"] = 0
check("each caller gets its own copy, so one cannot corrupt another", float(b["amount"].sum()) > 0)

print("\n== 3. append still adds on top ==")
up = c.post("/api/smart/upload?kind=sales", headers=H,
            files={"files": ("more.csv", io.BytesIO(sales_csv(100)), "text/csv")})
r = c.post("/api/smart/map", headers=H, json={"kind": "sales", "mapping": mapping, "mode": "append"})
check("append totals old + new", r.json().get("rows") == 500 and r.json().get("added") == 100, r.json())
check("and the session sees the combined table", len(main._data_sessions[SID].txns_df) == 500)

print("\n== 4. a bad mapping keeps the upload so the seller can fix it ==")
c.post("/api/smart/upload?kind=sales", headers=H,
       files={"files": ("sales.csv", io.BytesIO(sales_csv(50)), "text/csv")})
bad = dict(mapping, amount="PRODUCT_NAME")   # text, so no row has an amount
r = c.post("/api/smart/map", headers=H, json={"kind": "sales", "mapping": bad, "mode": "replace"})
check("refused with a reason", r.status_code == 400, r.status_code)
check("the staged upload is still there to re-map",
      "smart_pending_sales" in main._data_sessions[SID].raw_dfs)
check("and the saved data was not touched", len(smart.load_sales(email)) == 500)

print("\n== 5. dead sessions are let go ==")
r = c.post("/api/logout", headers=H)
check("logout succeeds", r.status_code == 200)
check("logging out drops that browser session's data", SID not in main._data_sessions)

old = f"idle-{time.time_ns()}"
main.get_session(old)
main._data_sessions[old].last_used = time.time() - main._SESSION_IDLE_SECONDS - 5
main._last_session_sweep = 0.0
live = f"live-{time.time_ns()}"
main.get_session(live)
check("a session idle past the window is swept", old not in main._data_sessions)
check("an active one is kept", live in main._data_sessions)

tok2 = c.post("/api/login", json={"email": email, "password": "Test12345!"}).json().get("token")
H2 = {"Authorization": "Bearer " + str(tok2), "X-Session-Id": f"back-{time.time_ns()}"}
r = c.get("/api/smart/state", headers=H2)
check("signing back in gets the saved data back, nothing was lost",
      r.status_code == 200 and r.json().get("data", {}).get("sales", {}).get("rows") == 500,
      r.status_code)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
