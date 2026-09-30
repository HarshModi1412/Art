"""The September 2026 pricing: a 7-day Pro Max trial saved at signup, then Pro
($10 / ₹700) or Pro Max ($12.99 / ₹1,299), priced by region.

Run from the repo root:  python scripts/test_pricing_trial.py
"""
import os, sys
os.environ["AUTOPLAN_SCHEDULER"] = "off"
os.environ.pop("LAUNCH_MODE", None)
for k in ("SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
    os.environ.pop(k, None)
sys.path.insert(0, os.getcwd())
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from backend import main
from backend.core import billing, pricing, user_store

c = TestClient(main.app)
ok = bad = 0
def check(name, cond, extra=""):
    global ok, bad
    if cond: ok += 1
    else:
        bad += 1; print("FAIL", name, extra)

email = f"trial{os.getpid()}@example.com"
r = c.post("/api/register", json={"email": email, "password": "secret123"},
           headers={"CF-IPCountry": "US"})
check("register", r.status_code == 200, r.text[:200])
tok = r.json()["token"]
H = {"Authorization": "Bearer " + tok}
rec = user_store.get_key(email, billing.BILLING_KEY, {})
check("trial date saved", bool(rec.get("trial_started_at")), rec)
check("usd currency", rec.get("currency") == "USD", rec)
check("trial is promax", billing.effective_plan(email) == "promax")

# pricing by region
p_us = c.get("/api/pricing", headers={"CF-IPCountry": "US"}).json()
p_in = c.get("/api/pricing", headers={"CF-IPCountry": "IN"}).json()
p_lang = c.get("/api/pricing", headers={"Accept-Language": "en-IN,en;q=0.9"}).json()
check("us currency", p_us["currency"] == "USD", p_us["currency"])
check("in currency", p_in["currency"] == "INR", p_in["currency"])
check("lang in", p_lang["currency"] == "INR")
labels = {p["id"]: p["price_label"] for p in p_us["plans"]}
check("usd labels", labels == {"free": "$0", "pro": "$10", "promax": "$12.99"}, labels)
labels_in = {p["id"]: p["price_label"] for p in p_in["plans"]}
check("inr labels", labels_in == {"free": "₹0", "pro": "₹700", "promax": "₹1,299"}, labels_in)
check("no packs in usd", p_us["credit_packs"] == [])

# during trial: app works
r = c.get("/api/today", headers=H)
check("trial app open", r.status_code != 402, r.status_code)

# expire the trial
rec["trial_started_at"] = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
user_store.set_key(email, billing.BILLING_KEY, rec)
billing._lock_cache.clear()
check("locked", billing.is_locked(email))
r = c.get("/api/today", headers=H)
check("locked 402", r.status_code == 402 and r.json()["code"] == "trial_ended", r.text[:200])
check("paywall usd", "$10" in r.json()["detail"]["message"], r.json()["detail"]["message"])
r = c.get("/api/account", headers=H)
check("account open", r.status_code == 200, r.status_code)
pl = r.json().get("plan", {})
check("offers usd", [o["price_label"] for o in pl.get("offers", [])] == ["$10", "$12.99"], pl.get("offers"))
check("pricing open", c.get("/api/pricing", headers=H).status_code == 200)

# pay for Pro: unlocked, but no image generation
billing.set_plan(email, "pro")
billing._extend_paid(email, "pro", 10.0, "USD", "o1", "p1")
check("pro active", billing.effective_plan(email) == "pro")
check("unlocked", c.get("/api/today", headers=H).status_code != 402)
from backend.core import aicaps
try:
    aicaps.check_image_month(email); check("pro no images", False)
except aicaps.PlanRequired as e:
    check("pro no images", True)
    check("pro msg", "Pro Max" in str(e), str(e))
try:
    aicaps.check(email, "video"); check("pro no video", False)
except aicaps.PlanRequired:
    check("pro no video", True)
aicaps.check(email, "text")  # text still fine
billing.set_plan(email, "promax")
aicaps.check_image_month(email)
check("promax images ok", True)

# legacy paid row with no paid_until gets a month
e2 = f"legacy{os.getpid()}@example.com"
c.post("/api/register", json={"email": e2, "password": "secret123"})
billing.set_plan(e2, "max")
check("max alias -> promax", billing.get_plan(e2) == "promax")

# India signup
e3 = f"india{os.getpid()}@example.com"
c.post("/api/register", json={"email": e3, "password": "secret123"}, headers={"CF-IPCountry": "IN"})
check("inr account", billing.billing_currency(e3) == "INR")
check("trial not restartable", billing.start_trial(e3)["trial_started_at"] == user_store.get_key(e3, billing.BILLING_KEY)["trial_started_at"])

# launch mode opens everything
os.environ["LAUNCH_MODE"] = "true"
check("launch unlocks", billing.effective_plan(email) == "promax")
os.environ.pop("LAUNCH_MODE")

for e in (email, e2, e3):
    try:
        from backend.core import auth
        auth.delete_account(e)
    except Exception as ex:
        print("cleanup", e, ex)
print(f"{ok} passed, {bad} failed")
