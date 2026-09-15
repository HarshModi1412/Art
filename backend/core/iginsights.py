"""What the seller's Instagram account and posts actually did.

WHAT THIS CAN AND CANNOT SEE, WHICH IS THE WHOLE POINT
------------------------------------------------------
Every Meta app is granted **Standard Access** automatically. No App Review, no
Business Verification, nothing to apply for. Standard Access lets an app request
any permission, `instagram_business_manage_insights` included, but only from
people who hold a ROLE on that app: an admin, a developer or a tester.

So this module works, in full, today, for:

  * the operator's own Instagram account, and
  * any design partner who has accepted an Instagram Tester invite on the Meta
    app (up to 50 of them on an app not linked to a verified business).

And it returns nothing at all, by Meta's design, for a seller who simply signed
up and connected. For them the app needs **Advanced Access**, which means
Business Verification (so, a registered company) plus App Review of that one
permission.

That distinction is not an edge case to be handled quietly. It is the normal
state of this feature for most of this app's life, so the refusal it produces is
a first-class result with its own plain-English explanation, not an error string
from Meta leaking onto a seller's screen. `_explain()` is where that translation
lives and it is the most important function in this file.

The permission is already in `instagram.OAUTH_SCOPES`, so every seller who has
ever connected has already granted it. Nothing was reading the numbers.

OTHER THINGS METE'S DOCS SAY THAT THIS CODE HAS TO RESPECT
---------------------------------------------------------
  * **Data is delayed up to 48 hours.** A post published this morning has no
    numbers this afternoon, and that is not a bug. Anything that looks like a
    zero within that window is reported as "too early to tell" instead.
  * **`impressions` was removed on 21 April 2025.** Asking for it now fails the
    whole request, so it is not asked for. `views` replaced it.
  * **Accounts under 100 followers get no `follower_count` and no
    demographics.** A seller starting out is exactly who this app is for, so
    that is expected rather than exceptional: the metrics that do work are
    still shown, and the ones that do not say why.
  * **Empty datasets come back instead of zeros** when Instagram has nothing,
    which is a different thing from a real zero and is kept different here.
  * **Rate limits are real.** Insights are cached, and the cache is deliberately
    generous (one hour) because the underlying data only moves every 48 hours.
    Refreshing faster would spend the seller's quota to re-read the same figures.

Nothing in here raises for an API problem. A seller looking at a performance
screen that says "Instagram would not give us your numbers, here is why" is in a
better position than one looking at a stack trace or, worse, at a confident zero.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import requests

log = logging.getLogger(__name__)

GRAPH = "https://graph.instagram.com"

# The account-level metrics this app asks for, and why each one is here.
#
# Deliberately NOT the full list Meta offers. Every extra metric is another way
# for the whole request to fail, and a seller who is shown twenty numbers reads
# none of them. These six answer the only questions a small seller actually has:
# did people see it, did it reach past my own followers, did anyone do anything,
# did I gain followers, did anyone go to my link.
ACCOUNT_METRICS = [
    "views",              # replaced impressions, which Meta removed in April 2025
    "reach",              # how many separate people, not how many times
    "accounts_engaged",   # people who did something, not the count of somethings
    "total_interactions",
    "profile_links_taps",
]
# Asked for separately because it is the one that needs a breakdown parameter,
# and a metric that needs different arguments does not belong in the same call.
FOLLOWS_METRIC = "follows_and_unfollows"

# Per-post metrics. Meta returns different sets for a reel and a feed post, and
# asking for one the media type does not support fails the request for that post
# rather than returning what it can. So each media type gets its own list.
MEDIA_METRICS = {
    "REELS": ["views", "reach", "likes", "comments", "saved", "shares"],
    "VIDEO": ["views", "reach", "likes", "comments", "saved", "shares"],
    "IMAGE": ["views", "reach", "likes", "comments", "saved", "shares"],
    "CAROUSEL_ALBUM": ["views", "reach", "likes", "comments", "saved", "shares"],
}
DEFAULT_MEDIA_METRICS = ["views", "reach", "likes", "comments", "saved", "shares"]

# Instagram's own figure, not ours: numbers can lag reality by up to two days.
SETTLE_HOURS = 48

# One hour. The data underneath moves every 48 hours, so anything faster spends
# the seller's rate limit to fetch figures that cannot have changed.
CACHE_SECONDS = 3600

_CACHE: dict[str, tuple[float, dict]] = {}


class Refused:
    """Named reasons Instagram can decline, so callers switch on a value rather
    than on the text of a message that Meta is free to reword tomorrow."""
    NOT_CONNECTED = "not_connected"
    NO_PERMISSION = "no_permission"
    NOT_A_TESTER = "not_a_tester"
    TOKEN_EXPIRED = "token_expired"
    RATE_LIMITED = "rate_limited"
    TOO_SMALL = "too_small"
    UNREACHABLE = "unreachable"
    UNKNOWN = "unknown"


def _explain(err: dict, http_status: int = 0) -> dict:
    """Turn a Graph API error into something a seller can act on.

    This is the function that decides whether this feature feels finished or
    broken, because for most accounts, most of the time, THIS is the feature.
    Meta's own messages are written for developers ("Application does not have
    permission for this action"), and a seller reading that concludes the app is
    broken rather than that they are not on the tester list.
    """
    msg = str((err or {}).get("message") or "")
    low = msg.lower()
    code = (err or {}).get("code")
    sub = (err or {}).get("error_subcode")

    # Code 4 and 17 are throttling; 32 is the page-level rate limit.
    if code in (4, 17, 32, 613) or "rate limit" in low or "too many calls" in low:
        return {"reason": Refused.RATE_LIMITED,
                "message": "Instagram is asking us to slow down. The numbers you "
                           "can see are the last ones we fetched; try again in "
                           "an hour.",
                "detail": msg}

    # 190 is the expired/invalid token family.
    if code == 190 or "expired" in low or "session has been invalidated" in low:
        return {"reason": Refused.TOKEN_EXPIRED,
                "message": "Your Instagram connection has expired. Reconnect the "
                           "account and the numbers come back.",
                "detail": msg}

    # 10 and the 200s are the permission family. The distinction between "this
    # app has not been approved for that permission" and "you did not grant it"
    # is invisible in the error, so the explanation covers both and puts the
    # likely one first.
    if code in (10, 200, 803) or http_status == 403 or "permission" in low \
            or "not authorized" in low or "does not have" in low:
        return {"reason": Refused.NOT_A_TESTER,
                "message": (
                    "Instagram will not share this account's numbers with us yet. "
                    "This is a Meta rule, not a fault: an app can only read "
                    "insights for accounts that are on its tester list until the "
                    "app itself has been through Meta's review. Ask the operator "
                    "to add you as an Instagram tester, or wait for the review to "
                    "finish. Posting is unaffected."),
                "detail": msg}

    if "100 followers" in low or "not available" in low and "follower" in low:
        return {"reason": Refused.TOO_SMALL,
                "message": "Instagram does not report follower numbers for "
                           "accounts under 100 followers yet. Everything else "
                           "below is real.",
                "detail": msg}

    return {"reason": Refused.UNKNOWN,
            "message": "Instagram did not return the numbers this time. Nothing "
                       "is wrong with your account or your posts; try again "
                       "later.",
            "detail": msg or f"HTTP {http_status}"}


def _get(path: str, params: dict, timeout: int = 20) -> dict:
    """One GET, with every failure turned into a refusal rather than an exception."""
    try:
        r = requests.get(f"{GRAPH}/{path}", params=params, timeout=timeout)
    except requests.RequestException as e:
        return {"_refused": {"reason": Refused.UNREACHABLE,
                             "message": "Could not reach Instagram just now. "
                                        "This is usually a passing network "
                                        "problem; the numbers are not lost.",
                             "detail": str(e)}}
    try:
        data = r.json()
    except ValueError:
        return {"_refused": {"reason": Refused.UNKNOWN,
                             "message": "Instagram sent back something we could "
                                        "not read.",
                             "detail": r.text[:200]}}
    if r.status_code != 200 or data.get("error"):
        return {"_refused": _explain(data.get("error") or {}, r.status_code)}
    return data


# ---------------------------------------------------------------- account
def _flatten(entry: dict) -> Any:
    """One metric out of Instagram's two different shapes for the same thing.

    `total_value` metrics arrive as {"total_value": {"value": 12}} and
    `time_series` ones as {"values": [{"value": 12, "end_time": ...}]}. Callers
    should not have to care which kind a metric happens to be this year.
    """
    tv = entry.get("total_value")
    if isinstance(tv, dict) and "value" in tv:
        return tv.get("value")
    values = entry.get("values") or []
    if values:
        total = 0
        seen = False
        for v in values:
            if isinstance(v.get("value"), (int, float)):
                total += v["value"]
                seen = True
        if seen:
            return total
    return None


def account_insights(email: str, days: int = 28) -> dict:
    """The account's own numbers over the last `days` days.

    Returns {"ok": bool, "metrics": {...}, "refused": {...}|None, ...}. Never
    raises: a refusal is a result, because for most accounts a refusal IS the
    result and the screen has to say something useful either way.
    """
    from backend.core import instagram

    days = max(1, min(int(days or 28), 90))
    out = {"ok": False, "days": days, "metrics": {}, "refused": None,
           "username": "", "followers": None, "settle_hours": SETTLE_HOURS,
           "fetched_at": None}

    creds = instagram.get_credentials(email)
    token, ig_id = creds.get("access_token"), creds.get("ig_user_id")
    if not (token and ig_id):
        out["refused"] = {"reason": Refused.NOT_CONNECTED,
                          "message": "Instagram is not connected yet. Connect the "
                                     "account and its numbers appear here.",
                          "detail": ""}
        return out

    key = f"acct:{email}:{days}"
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return {**hit[1], "cached": True}

    # Who the account is, and how big. Asked for first and separately because it
    # works on every account, so a failure here means the connection itself is
    # the problem rather than the insights permission.
    who = _get(ig_id, {"fields": "username,followers_count,media_count",
                       "access_token": token})
    if "_refused" in who:
        out["refused"] = who["_refused"]
        return out
    out["username"] = who.get("username") or ""
    out["followers"] = who.get("followers_count")
    out["posts_total"] = who.get("media_count")

    since, until = _window(days)
    got = _get(f"{ig_id}/insights", {
        "metric": ",".join(ACCOUNT_METRICS),
        "period": "day",
        "metric_type": "total_value",
        "since": since, "until": until,
        "access_token": token,
    })
    if "_refused" in got:
        # The identity call worked and this one did not, which almost always
        # means the insights permission specifically. Keep what we learned.
        out["refused"] = got["_refused"]
        _CACHE[key] = (time.time(), out)
        return out

    for entry in got.get("data") or []:
        name = entry.get("name")
        if not name:
            continue
        val = _flatten(entry)
        if val is not None:
            out["metrics"][name] = val

    # Follows and unfollows, separately: it needs its own breakdown and it is
    # the metric most likely to be unavailable on a small account, so it must
    # not be able to take the other five down with it.
    follows = _get(f"{ig_id}/insights", {
        "metric": FOLLOWS_METRIC, "period": "day", "metric_type": "total_value",
        "breakdown": "follow_type", "since": since, "until": until,
        "access_token": token,
    })
    if "_refused" not in follows:
        for entry in follows.get("data") or []:
            results = ((entry.get("total_value") or {}).get("breakdowns") or [{}])
            for br in results:
                for row in br.get("results") or []:
                    dim = (row.get("dimension_values") or [""])[0]
                    if dim == "FOLLOWER":
                        out["metrics"]["followers_gained"] = row.get("value")
                    elif dim == "NON_FOLLOWER":
                        out["metrics"]["followers_lost"] = row.get("value")

    out["ok"] = bool(out["metrics"])
    if not out["ok"] and not out["refused"]:
        # Instagram answers with an empty dataset rather than zeros when it has
        # nothing to report. That is "no activity yet", not "zero views", and
        # saying zero would be a claim we cannot support.
        out["refused"] = {
            "reason": Refused.TOO_SMALL,
            "message": ("Instagram has no activity to report for this account in "
                        f"the last {days} days. That is not a zero, it is "
                        "nothing to measure yet. Post a few times and come back."),
            "detail": "empty dataset"}
    out["fetched_at"] = _iso_now()
    _CACHE[key] = (time.time(), out)
    return out


def _window(days: int) -> tuple[int, int]:
    """Unix seconds for the period, ending now."""
    now = int(time.time())
    return now - days * 86400, now


def _iso_now() -> str:
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


# ---------------------------------------------------------------- per post
def media_insights(email: str, media_ids: list[str]) -> dict:
    """Numbers for specific posts, keyed by media id.

    Returns {"posts": {media_id: {...}}, "refused": {...}|None}. A post that
    Instagram will not talk about is simply absent from the map rather than
    present with zeros, because a zero here would be read as "nobody saw it".
    """
    from backend.core import instagram

    out = {"posts": {}, "refused": None, "asked": len(media_ids or [])}
    ids = [str(m).strip() for m in (media_ids or []) if str(m).strip()]
    if not ids:
        return out

    creds = instagram.get_credentials(email)
    token = creds.get("access_token")
    if not token:
        out["refused"] = {"reason": Refused.NOT_CONNECTED,
                          "message": "Instagram is not connected.", "detail": ""}
        return out

    # Newest first, and capped. A seller with four hundred published posts does
    # not need four hundred round trips to answer "how is this week going", and
    # the rate limit would not allow it anyway.
    ids = ids[:60]
    key = f"media:{email}:{','.join(sorted(ids))}"
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return {**hit[1], "cached": True}

    for mid in ids:
        meta = _get(mid, {"fields": "media_type,media_product_type,timestamp,permalink",
                          "access_token": token})
        if "_refused" in meta:
            # The first refusal is the answer for all of them: they all use one
            # token against one account, so the second call would fail the same
            # way and only spend quota proving it.
            out["refused"] = meta["_refused"]
            break

        kind = (meta.get("media_product_type") or meta.get("media_type") or "").upper()
        metrics = MEDIA_METRICS.get(kind, DEFAULT_MEDIA_METRICS)
        got = _get(f"{mid}/insights",
                   {"metric": ",".join(metrics), "access_token": token})
        if "_refused" in got:
            out["refused"] = out["refused"] or got["_refused"]
            continue

        row = {"media_id": mid, "kind": kind,
               "posted_at": meta.get("timestamp") or "",
               "permalink": meta.get("permalink") or "",
               "settling": _is_settling(meta.get("timestamp"))}
        for entry in got.get("data") or []:
            val = _flatten(entry)
            if val is not None:
                row[entry.get("name")] = val
        out["posts"][mid] = row

    _CACHE[key] = (time.time(), out)
    return out


def _is_settling(timestamp: str | None) -> bool:
    """True while a post is inside Instagram's own 48 hour reporting delay.

    Worth its own flag: the difference between "nobody saw this" and "Instagram
    has not counted it yet" is the difference between a seller changing what
    they post and a seller panicking for no reason.
    """
    if not timestamp:
        return False
    try:
        import datetime as _dt
        t = _dt.datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        age = (_dt.datetime.now(_dt.timezone.utc) - t).total_seconds() / 3600.0
        return age < SETTLE_HOURS
    except Exception:  # noqa: BLE001
        return False


def clear_cache(email: str = "") -> None:
    """Forget what we fetched. Used by the Refresh button and by the tests."""
    if not email:
        _CACHE.clear()
        return
    for k in [k for k in _CACHE if f":{email}:" in k]:
        _CACHE.pop(k, None)
