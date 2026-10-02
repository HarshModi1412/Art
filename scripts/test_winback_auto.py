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

section("It runs every second week, not once a tick")

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
check("NOT due the following week: campaigns are fortnightly",
      winback_auto.due(EMAIL, datetime(2026, 9, 21, 10, 5)) is None)
check("due again the week after that",
      winback_auto.due(EMAIL, datetime(2026, 9, 28, 10, 5)) is not None)
nt = winback_auto.next_trigger(datetime(2026, 9, 15, 9, 0), 0, 10, first)
check("and the next run shown to the seller skips the off week",
      nt.date().isoformat() == "2026-09-28", nt.isoformat())
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

section("A run builds a campaign draft, through the campaign engine")

from backend.core import analytics, campaign_engine, smart  # noqa: E402

analytics.at_risk_cached = lambda email, txns, limit=60: []

_drafts = {}
_built = []
_sent = []
_audience = {"n": 8, "unreachable": 0, "fail": ""}
_festival = {"next": None}


def fake_build(email, reason="winback", offer=None, occasion="", note="",
               with_image=True, trigger="manual", limit=150):
    fail = _audience["fail"]
    if fail and (fail != "festival only" or reason == "festival"):
        raise campaign_engine.CampaignError(fail)
    _built.append({"reason": reason, "occasion": occasion, "offer": offer,
                   "trigger": trigger, "limit": limit})
    did = f"d{len(_built)}"
    n = _audience["n"]
    rows = [{**customer(i), "code": f"C{i}-XXXXX", "message": f"hi {i}"} for i in range(1, n + 1)]
    _drafts[did] = {"id": did, "state": "draft", "reason": reason, "occasion": occasion,
                    "rows": rows, "held_back": 2}
    return {**_drafts[did], "counts": {"audience": n, "unreachable": _audience["unreachable"],
                                       "value": 1000.0 * n, "phone": n, "email": n}}


def fake_send(email, draft_id, channels=("whatsapp", "email")):
    _sent.append((draft_id, channels))
    _drafts[draft_id]["state"] = "sent"
    return {"summary": f"{len(_drafts[draft_id]['rows'])} emails sent"}


campaign_engine.build = fake_build
campaign_engine.send = fake_send
campaign_engine.get_draft = lambda email, did: _drafts.get(did)
campaign_engine.discard = lambda email, did: _drafts.pop(did, None)
campaign_engine.upcoming_occasion = lambda email, horizon=21: _festival["next"]
smart.load_sales = lambda email, copy=True: ["one row"]

user_store.set_key(EMAIL, winback_auto.STATE_KEY,
                   {"armed_at": datetime(2026, 9, 1, 9, 0).isoformat(timespec="seconds")})

res = winback_auto.run_if_due(EMAIL, trigger="manual")
check("the run completes", not res.get("skipped"), str(res))
check("it prepared a campaign", res["ok"] and res["n"] == 8, str(res))
check("a win-back one, with no festival coming", _built[-1]["reason"] == "winback", str(_built[-1]))
check("using the seller's saved offer (10% by default)",
      _built[-1]["offer"] == winback_auto.DEFAULT_OFFER, str(_built[-1]["offer"]))
check("marked as automatic", _built[-1]["trigger"] == "auto")
check("and capped to one send's worth", _built[-1]["limit"] == winback_auto.MAX_BATCH)
check("NOTHING was sent", _sent == [], str(_sent))
p = winback_auto.pending(EMAIL)
check("the campaign is waiting", p is not None and len(p["rows"]) == 8)
check("with the exact messages and codes that were prepared",
      all(r.get("message") and r.get("code") for r in p["rows"]),
      "approving must send what the seller was shown, not a fresh scan")
check("and how many were held back by the cooldown", p.get("skipped_cooldown") == 2, str(p))

winback_auto.save_config(EMAIL, {"offer": {"kind": "flat", "value": 200, "min_order": 999}})
check("the offer can be changed", winback_auto.get_config(EMAIL)["offer"]["value"] == 200)
try:
    winback_auto.save_config(EMAIL, {"offer": {"kind": "percent", "value": 95}})
    check("an absurd offer is refused", False, "it was saved")
except ValueError as e:
    check("an absurd offer is refused", "90" in str(e), str(e))

section("A festival takes the slot when one is coming")

_festival["next"] = {"name": "Diwali", "date": "2026-11-08", "days_away": 14}
res = winback_auto.run_if_due(EMAIL, trigger="manual")
check("a festival campaign is built", _built[-1]["reason"] == "festival"
      and _built[-1]["occasion"] == "Diwali", str(_built[-1]))
check("the new run replaces the old card, it does not stack",
      len([d for d in _drafts.values() if d["state"] == "draft"]) == 1, str(list(_drafts)))
check("and the offer it uses is the saved one",
      _built[-1]["offer"]["value"] == 200, str(_built[-1]["offer"]))

_audience["fail"] = "festival only"
res = winback_auto.prepare(EMAIL, "festival", "Diwali")
check("a festival with nobody to reach falls back to win-back, it does not skip the fortnight",
      res["ok"] and _built[-1]["reason"] == "winback", str(res))
campaign_engine.discard(EMAIL, res.get("draft_id"))
_audience["fail"] = ""

section("A run that finds nobody leaves no card")

_festival["next"] = None
_audience.update(n=1)
res = winback_auto.run_if_due(EMAIL, trigger="manual")
check("one lonely customer is not a campaign", not res["ok"], str(res))
check("and it says so rather than showing a card", "not worth" in res["reason"], res["reason"])
check("there is nothing waiting", winback_auto.pending(EMAIL) is None)
check("and the draft it built was thrown away", not [d for d in _drafts.values() if d["state"] == "draft"])

_audience.update(n=8, unreachable=8)
res = winback_auto.run_if_due(EMAIL, trigger="manual")
check("customers with no contact details produce no campaign", not res["ok"])
check("and it says that, not 'nobody is at risk'", "email or phone" in res["reason"], res["reason"])

_audience.update(n=8, unreachable=0, fail="Everyone this campaign would reach was contacted recently")
res = winback_auto.run_if_due(EMAIL, trigger="manual")
check("with everyone cooling down there is no campaign", not res["ok"])
check("and the reason is the engine's", "contacted" in res["reason"], res["reason"])
_audience["fail"] = ""

section("The card in the Approval panel")

winback_auto.run_if_due(EMAIL, trigger="manual")
cards = []
try:
    cards = smart.build_insights(EMAIL) or []
except Exception as e:  # noqa: BLE001
    check("insights build", False, str(e))
ids = [c.get("id") for c in cards]
check("the sending card appears", "winback_auto" in ids, str(ids))
check("and the old card does not, at the same time",
      not ("winback" in ids and "winback_auto" in ids),
      "two win-back cards means the seller decides the same thing twice")
card = next((c for c in cards if c.get("id") == "winback_auto"), {})
check("it says it will send, not download", "send" in (card.get("action_label") or "").lower(),
      card.get("action_label"))
check("it names the number of people", "8" in (card.get("title") or ""), card.get("title"))
check("it explains the messages are already written, with codes",
      "written" in (card.get("detail") or "") and "code" in (card.get("detail") or ""),
      (card.get("detail") or "")[:120])

section("Approving is what sends")

res = winback_auto.approve(EMAIL)
check("the campaign went out", len(_sent) == 1, str(_sent))
check("the draft that was waiting", _drafts[_sent[0][0]]["state"] == "sent")
check("on WhatsApp and email", set(_sent[0][1]) == {"whatsapp", "email"}, str(_sent[0][1]))
check("and the summary comes back", "8 emails" in str(res.get("summary")), str(res))
check("the campaign is cleared so it cannot be sent twice", winback_auto.pending(EMAIL) is None)
check("and the card is gone from the panel",
      "winback_auto" not in [c.get("id") for c in (smart.build_insights(EMAIL) or [])])
try:
    winback_auto.approve(EMAIL)
    check("approving nothing is refused", False, "it went ahead")
except ValueError as e:
    check("approving nothing is refused", "waiting" in str(e), str(e))

_festival["next"] = {"name": "Diwali", "date": "2026-11-08", "days_away": 14}
winback_auto.run_if_due(EMAIL, trigger="manual")
winback_auto.approve(EMAIL)
winback_auto.run_if_due(EMAIL, trigger="manual")
check("once a festival's campaign is sent, the next run is win-back again",
      _built[-1]["reason"] == "winback", str(_built[-1]))
_festival["next"] = None

section("Skipping a fortnight")

winback_auto.run_if_due(EMAIL, trigger="manual")
check("a new campaign is waiting", winback_auto.pending(EMAIL) is not None)
before = len(user_store.get_key(EMAIL, winback_proof.CAMPAIGNS_KEY, []) or [])
did = winback_auto._state(EMAIL)["pending"]["draft_id"]
winback_auto.clear_pending(EMAIL)
check("skipping throws it away", winback_auto.pending(EMAIL) is None)
check("and its draft with it", did not in _drafts)
check("without marking anyone as contacted",
      len(user_store.get_key(EMAIL, winback_proof.CAMPAIGNS_KEY, []) or []) == before,
      "a skipped campaign must leave those customers eligible next time")

section("Status, for the settings screen")

st = winback_auto.status(EMAIL)
for k in ("enabled", "day", "hour", "day_name", "next_run_label", "tz_label", "cooldown_days",
          "every_weeks", "offer"):
    check(f"status carries {k}", k in st, str(list(st)))
check("the next run is in the seller's own timezone, not the server's",
      bool(st["tz_label"]), st["tz_label"])
check("it never leaks the customer rows",
      "rows" not in str(st.get("pending") or {}),
      "the panel needs a count, not everyone's email address")

print(f"\n{PASSED} passed, {FAILED} failed")
sys.exit(1 if FAILED else 0)
