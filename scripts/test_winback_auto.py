"""
Tests for the weekly win-back run.

THE ONE THAT MATTERS MOST is the cooldown. An at-risk customer stays at-risk,
so a weekly job with no memory mails the same person every Monday forever.
That is not a campaign, it is how a small shop's domain ends up in a spam
folder permanently — and it would look like it was working right up until it
had destroyed the seller's deliverability.

Also covered: nothing is ever sent without a person pressing approve; a run
that finds nobody produces no card rather than a "0 customers" card that trains
the seller to ignore the panel; and enabling the feature does not immediately
fire a trigger that has already passed today.

Run: python scripts/test_winback_auto.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["CAFEX_DATA_DIR"] = tempfile.mkdtemp(prefix="wbauto_")

PASSED = 0
FAILED = 0


def check(label, cond, extra=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
    else:
        FAILED += 1
        print(f"  FAIL: {label}" + (f"  [{extra}]" if extra else ""))


def section(t):
    print(f"\n{t}")


from backend.core import user_store, winback_auto, winback_proof  # noqa: E402

EMAIL = "shop@test.local"


def customer(i, value=1000):
    return {"customer_id": f"C{i}", "customer_name": f"Customer {i}",
            "email": f"c{i}@buyer.test", "phone": f"9198765432{i:02d}",
            "monetary": value, "frequency": 4, "recency_days": 90,
            "favorite_item": "Cotton Kurta", "price_tier": "mid",
            "last_purchase_date": "2026-06-01"}


section("When it runs")

cfg = winback_auto.get_config(EMAIL)
check("on by default", cfg["enabled"])
check("Monday by default", cfg["day"] == 0 and cfg["day_name"] == "Monday", str(cfg))
check("mid-morning by default", cfg["hour"] == 10, str(cfg["hour"]))
check("which is a different day from the Saturday social plan",
      winback_auto.DEFAULT_DAY != 5,
      "two decisions landing together means one gets rubber-stamped")

winback_auto.save_config(EMAIL, {"day": 2, "hour": 15})
cfg = winback_auto.get_config(EMAIL)
check("the day can be changed", cfg["day"] == 2 and cfg["day_name"] == "Wednesday")
check("and the hour", cfg["hour"] == 15)
winback_auto.save_config(EMAIL, {"enabled": False})
check("and it can be switched off", not winback_auto.get_config(EMAIL)["enabled"])
check("switched off, nothing is ever due", winback_auto.due(EMAIL) is None)
winback_auto.save_config(EMAIL, {"enabled": True, "day": 0, "hour": 10})

section("Turning it on does not fire a trigger that has already passed")

user_store.set_key(EMAIL, winback_auto.STATE_KEY, {})
# Arm at Monday 11am — an hour AFTER this week's 10am trigger.
armed = datetime(2026, 9, 14, 11, 0)          # a Monday
user_store.set_key(EMAIL, winback_auto.STATE_KEY,
                   {"armed_at": armed.isoformat(timespec="seconds")})
check("the trigger from an hour ago does not fire",
      winback_auto.due(EMAIL, datetime(2026, 9, 14, 11, 5)) is None)
check("nor later that same day",
      winback_auto.due(EMAIL, datetime(2026, 9, 14, 23, 0)) is None)
nxt = winback_auto.due(EMAIL, datetime(2026, 9, 21, 10, 1))   # the next Monday
check("but the next week's does", nxt is not None, str(nxt))

section("It runs once a week, not once a tick")

user_store.set_key(EMAIL, winback_auto.STATE_KEY,
                   {"armed_at": datetime(2026, 9, 1, 9, 0).isoformat(timespec="seconds")})
first = winback_auto.due(EMAIL, datetime(2026, 9, 14, 10, 30))
check("due at the trigger", first is not None)
st = winback_auto._state(EMAIL)
st["last_trigger"] = first
winback_auto._save_state(EMAIL, st)
check("not due again fifteen minutes later",
      winback_auto.due(EMAIL, datetime(2026, 9, 14, 10, 45)) is None)
check("not due again that evening",
      winback_auto.due(EMAIL, datetime(2026, 9, 14, 21, 0)) is None)
check("due again the following week",
      winback_auto.due(EMAIL, datetime(2026, 9, 21, 10, 5)) is not None)
# A server that slept through three Mondays must wake up and run ONCE, against
# today's data — not three times, and not against a customer list from three
# weeks ago, half of whom may have bought since.
late = winback_auto.due(EMAIL, datetime(2026, 10, 5, 12, 0))
check("after a long outage it is due", late is not None)
check("and only for the most recent Monday, not every missed one",
      late.startswith("2026-10-05"), str(late))
st = winback_auto._state(EMAIL)
st["last_trigger"] = late
winback_auto._save_state(EMAIL, st)
check("and once that is done it is not due again",
      winback_auto.due(EMAIL, datetime(2026, 10, 5, 13, 0)) is None)

section("The cooldown — the one that stops us becoming a spammer")

user_store.set_key(EMAIL, winback_proof.CAMPAIGNS_KEY, [])
check("nobody is cooling down to begin with", winback_auto.recently_contacted(EMAIL) == set())

winback_proof.mark_sent(EMAIL, [customer(1), customer(2)], channel="email", state="sent")
cooling = winback_auto.recently_contacted(EMAIL)
check("someone just contacted is cooling down", "C1" in cooling and "C2" in cooling, str(cooling))
check("someone who was not, is not", "C3" not in cooling)

# A campaign the seller was handed tap-to-send links for. We do not know if
# they tapped them, and mailing again on the assumption they did not is the
# wrong way to be wrong.
winback_proof.mark_sent(EMAIL, [customer(3)], channel="whatsapp", state="pending")
check("a PENDING campaign also counts as contacted",
      "C3" in winback_auto.recently_contacted(EMAIL))

rows = user_store.get_key(EMAIL, winback_proof.CAMPAIGNS_KEY, [])
rows[0]["sent_at"] = (datetime.now() - timedelta(days=winback_auto.COOLDOWN_DAYS + 5)).isoformat()
user_store.set_key(EMAIL, winback_proof.CAMPAIGNS_KEY, rows)
cooling = winback_auto.recently_contacted(EMAIL)
check("an old campaign stops counting", "C1" not in cooling and "C2" not in cooling, str(cooling))
check("a recent one still does", "C3" in cooling)
check("the cooldown is long enough to matter", winback_auto.COOLDOWN_DAYS >= 30,
      f"{winback_auto.COOLDOWN_DAYS} days")

section("Building the batch")

from backend.core import analytics, smart  # noqa: E402

_pool = []
analytics.at_risk_cached = lambda email, txns: list(_pool)
smart.load_sales = lambda email: ["one row"]        # just needs to be non-empty

user_store.set_key(EMAIL, winback_proof.CAMPAIGNS_KEY, [])
_pool = []
b = winback_auto.build_batch(EMAIL)
check("nobody at risk means no batch", not b["ok"])
check("and it says why", "quiet" in b["reason"], b["reason"])

_pool = [customer(1)]
b = winback_auto.build_batch(EMAIL)
check("one lonely customer is not a campaign", not b["ok"], b["reason"])
check("and it says so rather than showing a card", "not worth" in b["reason"], b["reason"])

_pool = [customer(i) for i in range(1, 9)]
b = winback_auto.build_batch(EMAIL)
check("eight is a campaign", b["ok"])
check("everyone is in it", len(b["rows"]) == 8, str(len(b["rows"])))
check("each message is written", all(r.get("message") for r in b["rows"]))
check("each carries a coupon", all(r.get("coupon_code") for r in b["rows"]))
check("and the value at stake is totalled", b["value"] > 0, str(b["value"]))

winback_proof.mark_sent(EMAIL, [customer(1), customer(2), customer(3)],
                        channel="email", state="sent")
b = winback_auto.build_batch(EMAIL)
ids = {r["customer_id"] for r in b["rows"]}
check("the three just contacted are left out", not ({"C1", "C2", "C3"} & ids), str(ids))
check("the other five are in", len(b["rows"]) == 5, str(len(b["rows"])))
check("and the seller is told how many were held back", b["skipped"] == 3, str(b["skipped"]))

winback_proof.mark_sent(EMAIL, [customer(i) for i in range(4, 9)],
                        channel="email", state="sent")
b = winback_auto.build_batch(EMAIL)
check("with everyone cooling down there is no batch at all", not b["ok"])
check("and the reason names the cooldown", "contacted" in b["reason"], b["reason"])

user_store.set_key(EMAIL, winback_proof.CAMPAIGNS_KEY, [])
_pool = [customer(i, value=i * 100) for i in range(1, 90)]
b = winback_auto.build_batch(EMAIL)
check("a huge list is capped", len(b["rows"]) == winback_auto.MAX_BATCH, str(len(b["rows"])))
check("and the cap keeps the most valuable customers, not the first ones",
      min(float(r["monetary"]) for r in b["rows"]) > 100,
      "a capped batch that drops the big spenders is worse than no cap")

_pool = [{**customer(i), "email": "", "phone": ""} for i in range(1, 9)]
b = winback_auto.build_batch(EMAIL)
check("customers with no contact details produce no campaign", not b["ok"])
check("and it says that, not 'nobody is at risk'", "email or phone" in b["reason"], b["reason"])

section("A run prepares, it never sends")

user_store.set_key(EMAIL, winback_proof.CAMPAIGNS_KEY, [])
user_store.set_key(EMAIL, winback_auto.STATE_KEY,
                   {"armed_at": datetime(2026, 9, 1, 9, 0).isoformat(timespec="seconds")})
_pool = [customer(i) for i in range(1, 9)]

sent_calls = []
from backend.core import campaigns  # noqa: E402
campaigns.send = lambda *a, **k: (sent_calls.append((a, k)) or
                                  {"summary": "8 emails sent", "recipients": 8})

res = winback_auto.run_if_due(EMAIL, trigger="manual")
check("the run completes", not res.get("skipped"), str(res))
check("it prepared a batch", res["ok"] and res["n"] == 8, str(res))
check("NOTHING was sent", sent_calls == [], str(sent_calls))

p = winback_auto.pending(EMAIL)
check("the batch is waiting", p is not None and len(p["rows"]) == 8)
check("with the exact messages that were prepared",
      all(r.get("message") for r in p["rows"]),
      "approving must send what the seller was shown, not a fresh scan")

section("The card in the Approval panel")

cards = []
try:
    cards = smart.build_insights(EMAIL) or []
except Exception as e:  # noqa: BLE001
    check("insights build", False, str(e))
ids = [c.get("id") for c in cards]
check("the sending card appears", "winback_auto" in ids, str(ids))
check("and the old download card does not, at the same time",
      not ("winback" in ids and "winback_auto" in ids),
      "two win-back cards means the seller decides the same thing twice")
card = next((c for c in cards if c.get("id") == "winback_auto"), {})
check("it says it will send, not download", "send" in (card.get("action_label") or "").lower(),
      card.get("action_label"))
check("it names the number of people", "8" in (card.get("title") or ""), card.get("title"))
check("it explains the messages are already written",
      "written" in (card.get("detail") or ""), (card.get("detail") or "")[:80])

section("Approving is what sends")

res = winback_auto.approve(EMAIL)
check("the campaign went out", len(sent_calls) == 1, str(len(sent_calls)))
check("with the batch that was waiting", len(sent_calls[0][0][1]) == 8)
check("and the summary comes back", "8 emails" in str(res.get("summary")), str(res))
check("the batch is cleared so it cannot be sent twice",
      winback_auto.pending(EMAIL) is None)
check("and the card is gone from the panel",
      "winback_auto" not in [c.get("id") for c in (smart.build_insights(EMAIL) or [])])

try:
    winback_auto.approve(EMAIL)
    check("approving nothing is refused", False, "it went ahead")
except ValueError as e:
    check("approving nothing is refused", "waiting" in str(e), str(e))

section("Skipping a week")

winback_auto.run_if_due(EMAIL, trigger="manual")
check("a new batch is waiting", winback_auto.pending(EMAIL) is not None)
before = len(user_store.get_key(EMAIL, winback_proof.CAMPAIGNS_KEY, []) or [])
winback_auto.clear_pending(EMAIL)
check("skipping throws it away", winback_auto.pending(EMAIL) is None)
check("without marking anyone as contacted",
      len(user_store.get_key(EMAIL, winback_proof.CAMPAIGNS_KEY, []) or []) == before,
      "a skipped batch must leave those customers eligible next week")

section("Status, for the settings screen")

st = winback_auto.status(EMAIL)
for k in ("enabled", "day", "hour", "day_name", "next_run_label", "tz_label", "cooldown_days"):
    check(f"status carries {k}", k in st, str(list(st)))
check("the next run is in the seller's own timezone, not the server's",
      bool(st["tz_label"]), st["tz_label"])
check("it never leaks the customer rows",
      "rows" not in str(st.get("pending") or {}),
      "the panel needs a count, not everyone's email address")

print(f"\n{PASSED} passed, {FAILED} failed")
sys.exit(1 if FAILED else 0)
