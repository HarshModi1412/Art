"""Instagram performance data: what it reads, and every way it is allowed to fail.

THE THING THIS FEATURE IS REALLY ABOUT
--------------------------------------
Every Meta app gets Standard Access automatically, with no App Review and no
Business Verification. Standard Access lets an app request any permission,
`instagram_business_manage_insights` included, but ONLY from people who hold a
role on that app: an admin, a developer, or a tester.

So insights work in full for the operator's own account and for design partners
who accept a tester invite, and not at all for a seller who simply signed up.
For that, the app needs Advanced Access, which means Business Verification and
App Review of that permission.

That means the refusal is not an edge case. For most accounts, for most of this
app's life, the refusal IS the feature, and it has to read like a sentence a
seller can act on rather than like something broken. Most of this file is about
the refusals for that reason.

The other half is arithmetic that must not lie:
  * A post inside Instagram's own 48 hour reporting delay is held back, never
    reported as a zero. A seller who believes a good post failed stops making
    that kind of post.
  * A ranking needs enough posts behind it. Six in a bucket, two buckets to
    compare. Below that the screen says so instead of ranking noise.
  * Buckets are compared by AVERAGE, not total. A total rewards whichever
    choice the planner already makes most often, so it would confirm the plan
    whatever the posts actually did.

Run: python3 scripts/test_ig_insights.py
"""
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("LAUNCH_MODE", "true")

from backend.core import iginsights, instagram, social  # noqa: E402

PASS = FAIL = 0


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        print(f"  ✗ {label}  <-- {extra}")


# ---------------------------------------------------------------------------
# A stand-in for Instagram, so the tests exercise the real code paths without a
# real token. Each case is a response Meta genuinely returns.
# ---------------------------------------------------------------------------
class FakeResponse:
    def __init__(self, payload, status=200, text=""):
        self._payload = payload
        self.status_code = status
        self.text = text or str(payload)

    def json(self):
        if self._payload is _UNPARSEABLE:
            raise ValueError("not json")
        return self._payload


_UNPARSEABLE = object()


class FakeGraph:
    """Answers the two shapes of call this module makes: a node read and an
    /insights read. Records what was asked, so the tests can check that a
    removed metric is never requested."""

    def __init__(self):
        self.asked = []
        self.account = {"username": "kaya.leather", "followers_count": 840,
                        "media_count": 37}
        self.account_insights = {"data": [
            {"name": "views", "total_value": {"value": 12400}},
            {"name": "reach", "total_value": {"value": 5100}},
            {"name": "accounts_engaged", "total_value": {"value": 430}},
            {"name": "total_interactions", "total_value": {"value": 690}},
            {"name": "profile_links_taps", "total_value": {"value": 58}},
        ]}
        self.follows = {"data": [{"name": "follows_and_unfollows",
                                  "total_value": {"breakdowns": [{"results": [
                                      {"dimension_values": ["FOLLOWER"], "value": 61},
                                      {"dimension_values": ["NON_FOLLOWER"], "value": 9},
                                  ]}]}}]}
        self.media = {}          # media_id -> (node dict, insights dict)
        self.fail_with = None    # (payload, status) forced on every call
        self.fail_insights_with = None   # only on /insights calls

    def __call__(self, url, params=None, timeout=None):
        path = url.split("graph.instagram.com/", 1)[-1]
        self.asked.append((path, dict(params or {})))
        if self.fail_with:
            return FakeResponse(self.fail_with[0], self.fail_with[1])
        if path.endswith("/insights"):
            if self.fail_insights_with:
                return FakeResponse(self.fail_insights_with[0], self.fail_insights_with[1])
            node = path.split("/")[0]
            if node == "17841400000000000":
                if params.get("metric") == iginsights.FOLLOWS_METRIC:
                    return FakeResponse(self.follows)
                return FakeResponse(self.account_insights)
            entry = self.media.get(node)
            return FakeResponse(entry[1] if entry else {"data": []})
        if path == "17841400000000000":
            return FakeResponse(self.account)
        entry = self.media.get(path)
        return FakeResponse(entry[0] if entry else {})


def install(fake):
    iginsights.requests.get = fake          # the module calls requests.get
    iginsights.clear_cache()


def fake_creds(token="tok", ig_id="17841400000000000"):
    def _get(email):
        return {"access_token": token, "ig_user_id": ig_id} if token else {}
    instagram.get_credentials = _get


_REAL_GET = iginsights.requests.get
_REAL_CREDS = instagram.get_credentials

EMAIL = f"ig-{uuid.uuid4().hex[:8]}@test.co"

# =========================================================================
print("\n== the account's own numbers, when Instagram answers ==")
# =========================================================================
g = FakeGraph()
install(g)
fake_creds()

r = iginsights.account_insights(EMAIL, days=28)
check("it reads", r["ok"] is True, r.get("refused"))
check("and nothing was refused", r["refused"] is None)
check("the account is named", r["username"] == "kaya.leather")
check("with its follower count", r["followers"] == 840)
check("times seen comes through", r["metrics"]["views"] == 12400)
check("people reached too", r["metrics"]["reach"] == 5100)
check("people who did something", r["metrics"]["accounts_engaged"] == 430)
check("taps on the link, which is the one that becomes a sale",
      r["metrics"]["profile_links_taps"] == 58)
check("followers gained is unpicked from its breakdown",
      r["metrics"]["followers_gained"] == 61)
check("and followers lost", r["metrics"]["followers_lost"] == 9)
check("the 48 hour reporting delay is declared, not hidden",
      r["settle_hours"] == 48)

_metrics_asked = [p.get("metric", "") for _, p in g.asked if "metric" in p]
check("`impressions` is never asked for, since Meta removed it in April 2025 "
      "and asking fails the whole request",
      not any("impressions" in m for m in _metrics_asked), _metrics_asked)
check("the metrics asked for are the five a seller can act on, not everything "
      "Meta offers", len(iginsights.ACCOUNT_METRICS) == 5)

# =========================================================================
print("\n== the two shapes Instagram returns the same number in ==")
# =========================================================================
check("a total_value metric is read",
      iginsights._flatten({"total_value": {"value": 7}}) == 7)
check("a time_series metric is summed across its days",
      iginsights._flatten({"values": [{"value": 3}, {"value": 4}]}) == 7)
check("and a metric with nothing in it stays None rather than becoming zero, "
      "because an empty dataset is not a measurement of nought",
      iginsights._flatten({"values": []}) is None)
check("a malformed entry does not raise", iginsights._flatten({}) is None)

# =========================================================================
print("\n== caching, because the rate limit is real and the data is not ==")
# =========================================================================
before = len(g.asked)
again = iginsights.account_insights(EMAIL, days=28)
check("a second read inside the hour asks Instagram nothing",
      len(g.asked) == before)
check("and is marked as cached, so the screen can say so",
      again.get("cached") is True)
check("the figures are the same ones", again["metrics"]["views"] == 12400)
check("the window is an hour, because the data underneath only moves every 48",
      iginsights.CACHE_SECONDS == 3600)
iginsights.clear_cache(EMAIL)
iginsights.account_insights(EMAIL, days=28)
check("clearing the cache does go back to Instagram", len(g.asked) > before)

# =========================================================================
print("\n== the refusal that is the normal state of this feature ==")
# =========================================================================
# An app with Standard Access can only read insights for accounts that hold a
# role on it. For everyone else Meta answers like this.
g = FakeGraph()
g.fail_insights_with = ({"error": {
    "message": "(#10) Application does not have permission for this action",
    "type": "OAuthException", "code": 10}}, 403)
install(g)
r = iginsights.account_insights(EMAIL, days=28)
check("the account is still identified, so we know the connection is fine",
      r["username"] == "kaya.leather")
check("but the numbers are refused", r["ok"] is False)
check("named as a tester-list problem rather than 'unknown'",
      r["refused"]["reason"] == iginsights.Refused.NOT_A_TESTER,
      r["refused"])
msg = r["refused"]["message"]
check("the seller is told it is a Meta rule, not a fault", "Meta rule" in msg)
check("and told what would fix it", "tester" in msg.lower())
check("and told that posting still works, so they do not stop using the app",
      "Posting is unaffected" in msg)
check("Meta's own developer-facing wording is kept but not shown as the message",
      "#10" in r["refused"]["detail"] and "#10" not in msg)

# =========================================================================
print("\n== every other way Instagram says no ==")
# =========================================================================
cases = [
    ({"error": {"message": "Error validating access token: Session has expired",
                "code": 190}}, 400, iginsights.Refused.TOKEN_EXPIRED,
     ["Reconnect", "reconnect"]),
    ({"error": {"message": "(#4) Application request limit reached", "code": 4}},
     429, iginsights.Refused.RATE_LIMITED, ["slow down"]),
    ({"error": {"message": "(#32) Page request limit reached", "code": 32}},
     429, iginsights.Refused.RATE_LIMITED, ["slow down"]),
    ({"error": {"message": "Something unusual happened", "code": 1}},
     500, iginsights.Refused.UNKNOWN, ["Nothing is wrong with your account"]),
]
for payload, status, want, phrases in cases:
    g2 = FakeGraph()
    g2.fail_with = (payload, status)
    install(g2)
    rr = iginsights.account_insights(EMAIL, days=28)
    got = rr["refused"]["reason"]
    check(f"{payload['error']['message'][:38]!r} is understood as {want}",
          got == want, got)
    check("   and explained in words a seller can act on",
          any(p in rr["refused"]["message"] for p in phrases),
          rr["refused"]["message"][:80])

g3 = FakeGraph()
install(g3)
instagram.get_credentials = lambda e: {}
r = iginsights.account_insights(EMAIL)
check("a disconnected account is its own reason, not a permission error",
      r["refused"]["reason"] == iginsights.Refused.NOT_CONNECTED)
check("and says what to do about it", "Connect" in r["refused"]["message"])
fake_creds()

# A network failure is not Instagram refusing. The distinction matters because
# one of them means "try again" and the other means "you cannot have this".
class Boom:
    def __call__(self, *a, **k):
        import requests as _rq
        raise _rq.RequestException("connection reset")


iginsights.requests.get = Boom()
iginsights.clear_cache()
r = iginsights.account_insights(EMAIL)
check("a network failure is told apart from a refusal",
      r["refused"]["reason"] == iginsights.Refused.UNREACHABLE)
check("and says the numbers are not lost",
      "not lost" in r["refused"]["message"])

g4 = FakeGraph()
# Meta answers with an empty dataset, not with zeros, when it has nothing to
# report. Both calls have to be empty for this to be the "nothing yet" case:
# if follows came back with numbers there IS something to show, and saying
# "nothing to measure" then would be its own small lie.
g4.account_insights = {"data": []}
g4.follows = {"data": []}
install(g4)
r = iginsights.account_insights(EMAIL, days=7)
check("an empty dataset is reported as nothing to measure, NOT as zero views",
      r["refused"]["reason"] == iginsights.Refused.TOO_SMALL and not r["ok"])
check("and says so in as many words", "not a zero" in r["refused"]["message"])

# =========================================================================
print("\n== per-post numbers ==")
# =========================================================================
g = FakeGraph()
g.media = {
    "m_reel": ({"media_type": "VIDEO", "media_product_type": "REELS",
                "timestamp": "2026-08-01T10:00:00+0000",
                "permalink": "https://instagram.com/p/reel"},
               {"data": [{"name": "views", "values": [{"value": 3000}]},
                         {"name": "reach", "values": [{"value": 2400}]},
                         {"name": "likes", "values": [{"value": 180}]},
                         {"name": "saved", "values": [{"value": 41}]},
                         {"name": "shares", "values": [{"value": 12}]}]}),
    "m_photo": ({"media_type": "IMAGE", "media_product_type": "FEED",
                 "timestamp": "2026-08-02T10:00:00+0000",
                 "permalink": "https://instagram.com/p/photo"},
                {"data": [{"name": "views", "values": [{"value": 900}]},
                          {"name": "reach", "values": [{"value": 700}]},
                          {"name": "likes", "values": [{"value": 55}]}]}),
}
install(g)
r = iginsights.media_insights(EMAIL, ["m_reel", "m_photo"])
check("both posts come back", len(r["posts"]) == 2, r.get("refused"))
check("with their real numbers", r["posts"]["m_reel"]["views"] == 3000)
check("their type", r["posts"]["m_reel"]["kind"] == "REELS")
check("and a link to the real post",
      r["posts"]["m_photo"]["permalink"].endswith("/photo"))
check("an old post is not marked as still settling",
      r["posts"]["m_reel"]["settling"] is False)

import datetime as _dt  # noqa: E402
fresh = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(hours=3)
         ).strftime("%Y-%m-%dT%H:%M:%S+0000")
g.media["m_new"] = ({"media_type": "IMAGE", "media_product_type": "FEED",
                     "timestamp": fresh, "permalink": "x"},
                    {"data": [{"name": "views", "values": [{"value": 4}]}]})
iginsights.clear_cache()
r = iginsights.media_insights(EMAIL, ["m_new"])
check("a post from this morning is flagged as still settling, because "
      "Instagram takes up to two days and 4 views would read as a failure",
      r["posts"]["m_new"]["settling"] is True)

iginsights.clear_cache()
check("asking about nothing asks Instagram nothing",
      iginsights.media_insights(EMAIL, [])["posts"] == {})

g5 = FakeGraph()
g5.fail_with = ({"error": {"message": "(#10) Application does not have permission",
                           "code": 10}}, 403)
install(g5)
r = iginsights.media_insights(EMAIL, ["a", "b", "c"])
check("one refusal stops the loop instead of spending quota proving it twice",
      len([1 for path, _ in g5.asked]) <= 2, len(g5.asked))
check("and the reason travels with it",
      r["refused"]["reason"] == iginsights.Refused.NOT_A_TESTER)
check("with no posts invented in the meantime", r["posts"] == {})

# =========================================================================
print("\n== joining the numbers back to the choices that produced them ==")
# =========================================================================
# This is the part that makes the feature worth having: not "here are your
# numbers" but "the kind of post you keep skipping is the one that works".
rows = []
for i in range(7):
    rows.append({"pillar": "detail", "pillar_name": "Product in detail",
                 "format": "carousel", "product_id": "p1",
                 "product_name": "Card holder", "score": 1000 + i})
for i in range(7):
    rows.append({"pillar": "founder", "pillar_name": "Behind the scenes",
                 "format": "reel", "product_id": "p2",
                 "product_name": "Belt", "score": 200 + i})

groups = social._group(rows, "pillar", "pillar_name")
check("buckets come back biggest first", groups[0]["key"] == "detail")
check("scored by AVERAGE, not total, so the choice the planner already makes "
      "most often cannot win by volume alone",
      groups[0]["average"] == 1003, groups[0])
check("each bucket says whether it has enough behind it",
      groups[0]["enough"] is True and groups[0]["posts"] == 7)

v = social._verdicts(rows)
check("a real difference produces a sentence", len(v) >= 1, v)
sentence = v[0]["sentence"]
check("which names the winner", "Product in detail" in sentence)
check("and the loser, so the seller knows what to stop doing",
      "Behind the scenes" in sentence)
check("and quantifies it in views, not in a percentage nobody pictures",
      "views each" in sentence)
check("and the sample size travels with it", v[0]["sample"] == 14)

thin = rows[:2] + rows[7:9]
check("four posts produce no verdict at all, because a seller would "
      "rearrange their week around it", social._verdicts(thin) == [])
check("and the bar is stated rather than buried",
      social.MIN_FOR_A_VERDICT == 6 and social.MIN_BUCKETS == 2)

close = ([{"pillar": "a", "pillar_name": "A", "format": "reel", "product_id": "x",
           "product_name": "X", "score": 100} for _ in range(7)]
         + [{"pillar": "b", "pillar_name": "B", "format": "carousel",
             "product_id": "y", "product_name": "Y", "score": 90} for _ in range(7)])
check("a 10% difference is not called a finding, because it is not one",
      not any(x["about"] == "kind of post" for x in social._verdicts(close)))

check("the headline number falls back down the chain rather than calling a "
      "missing metric zero",
      social._headline({"reach": 12}) == 12 and social._headline({}) == 0)
check("and prefers views, the one metric every media type still reports",
      social._headline({"views": 5, "reach": 99}) == 5)

# =========================================================================
print("\n== the whole thing, through the API ==")
# =========================================================================
from fastapi.testclient import TestClient  # noqa: E402
from backend.main import app  # noqa: E402

c = TestClient(app)
T = uuid.uuid4().hex[:8]
EM = f"perf-{T}@test.co"
tok = c.post("/api/register", json={"email": EM, "password": "pw123456"}).json()["token"]
H = {"Authorization": "Bearer " + tok, "X-Session-Id": "pf" + T}

instagram.get_credentials = _REAL_CREDS
r = c.get("/api/social/performance", headers=H)
check("the endpoint answers for an account with no Instagram", r.status_code == 200)
j = r.json()
check("a refusal arrives as a 200 with a reason, not as an error status, "
      "because for most accounts the refusal IS the answer",
      j["refused"]["reason"] == iginsights.Refused.NOT_CONNECTED)
check("and the screen is told why it is empty separately from what the "
      "numbers say", j["readiness"]["connected"] is False
      and j["readiness"]["published"] == 0)
check("the bar for a verdict is sent to the client, so the message can name it",
      j["readiness"]["needed"] == social.MIN_FOR_A_VERDICT)

# Now with a connected account and real published posts.
c.post("/api/products/item", headers=H, json={
    "name": "Kaya Card Holder", "category": "Wallets", "price": 1499, "stock": 9})
c.post("/api/social/week", headers=H, json={})
posts = c.get("/api/social", headers=H).json().get("week") or []
check("there is a planned week to work with", len(posts) >= 1, len(posts))

# Mark a few published with media ids, as the publisher does.
made = []
for i, p in enumerate(posts[:4]):
    social.record_publish(EM, p["id"], {"ok": True, "media_id": f"mm{i}",
                                        "permalink": f"https://instagram.com/p/mm{i}"})
    made.append(f"mm{i}")
check("posts with a media id are the ones we can ask about",
      len(social.published_with_ids(EM)) == len(made))

g6 = FakeGraph()
for i, mid in enumerate(made):
    g6.media[mid] = ({"media_type": "IMAGE", "media_product_type": "FEED",
                      "timestamp": "2026-08-01T10:00:00+0000",
                      "permalink": f"https://instagram.com/p/{mid}"},
                     {"data": [{"name": "views", "values": [{"value": 500 + i * 100}]},
                               {"name": "reach", "values": [{"value": 400}]}]})
install(g6)
fake_creds()
out = social.performance(EM, days=28)
check("the numbers arrive joined to the posts", out["measured"] == len(made),
      out["measured"])
check("best first", out["posts"][0]["score"] >= out["posts"][-1]["score"])
check("each row carries the choice the planner made, which is the whole point",
      "pillar" in out["posts"][0] and "format" in out["posts"][0])
check("and a link to the real post on Instagram",
      out["posts"][0]["permalink"].startswith("https://instagram.com/"))
check("the account's own numbers come along", out["account"]["ok"] is True)
check("four posts is not enough for a verdict, and it does not pretend",
      out["verdicts"] == [])
check("but the tables are still shown, so the seller sees the shape",
      len(out["by_pillar"]) >= 1)

# =========================================================================
print("\n== when there is no verdict, say what is actually missing ==")
# =========================================================================
# THE BUG THIS CAUGHT: the screen told a seller looking at sixteen counted
# posts "too early, it takes about 6 of a kind". Both halves were true and
# together they read as a contradiction, because the seller counts posts and
# the rule counts posts OF A KIND. Sixteen split four, four and eight is one
# kind with enough behind it and nothing to compare it against.
def _row(pillar, label, score):
    return {"pillar": pillar, "pillar_name": label, "format": "reel",
            "product_id": "x", "product_name": "X", "score": score}


w = social._why_no_verdict([])
check("nothing counted says so", w["state"] == "nothing")

w = social._why_no_verdict([_row("a", "New arrival", 10)] * 3)
check("with one thin kind, it names that kind", "New arrival" in w["sentence"])
check("and how many more of it are needed", "3 more" in w["sentence"], w["sentence"])

w = social._why_no_verdict([_row("a", "New arrival", 10)] * 8
                           + [_row("b", "Product in detail", 5)] * 4)
check("with one kind ready and one short, it says which is ready",
      "New arrival posts (8) are enough to judge" in w["sentence"], w["sentence"])
check("names the one that is closest to joining it",
      "Product in detail is next closest at 4" in w["sentence"])
check("and says exactly how many more of THOSE, which is the actionable bit",
      "2 more of those" in w["sentence"])
check("and never says the bare count of all posts back at them, which is what "
      "made the old message read as a contradiction",
      "16 posts" not in w["sentence"])

w = social._why_no_verdict([_row("a", "New arrival", 100)] * 7
                           + [_row("b", "Product in detail", 95)] * 7)
check("when both are ready but close, it says the difference is not worth "
      "acting on rather than inventing a winner", w["state"] == "close")
check("and says it plainly", "not worth acting on" in w["sentence"])

# And it must travel to the client, or the screen cannot say any of it.
g7 = FakeGraph()
install(g7)
fake_creds()
out = social.performance(EM, days=28)
check("the reason reaches the client with the rest",
      isinstance(out.get("why_not_yet"), dict) and out["why_not_yet"].get("sentence"))

iginsights.requests.get = _REAL_GET
instagram.get_credentials = _REAL_CREDS
iginsights.clear_cache()

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
