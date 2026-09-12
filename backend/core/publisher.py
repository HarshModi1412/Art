"""
The wire between the calendar and Instagram.

WHY THIS EXISTS
---------------
It did not. That is the whole story, and it is worth writing down plainly.

The Social Media Manager plans a week, writes the captions, picks the times,
takes the seller's approval, attaches the picture or the clip and shows the
post on the calendar marked "scheduled". Then nothing happened. `social.py`
contained no Instagram code at all: `post_image` was called from exactly one
place, the older Content Creator module, and even there it only ran when
someone hit an endpoint by hand. There was no scheduler, no publisher, and
`published` was a state in `social.STATES` that nothing ever set.

So a seller could connect Instagram, approve a week of posts, watch them sit
on the calendar with times against them, and none of them would ever go out —
with no error anywhere, because nothing had tried. "Connected" was true and
meaningless.

HOW IT WORKS NOW
  * Every fifteen minutes (the same ticker as the weekly plan and the weekly
    win-back — one thread, three jobs) this looks for posts whose time has
    come, and publishes them.
  * A reel goes out as a reel and a photo as a photo, through
    `instagram.publish`.
  * The result is written onto the post: `published` with a permalink, or
    `failed` with the reason Instagram gave, in words. A failure is visible on
    the calendar rather than being a post that quietly did not appear.

THE RULES THAT KEEP THIS SAFE
  * ONLY `scheduled` posts. A draft, an approved-but-media-less post, or a
    cancelled one is never touched. The seller's approval is the gate and this
    never reopens it.
  * A post is claimed before it is published. Two workers, or a tick that
    overlaps the previous one, must not publish the same reel twice — and on
    Instagram a double post is not a small bug, it is the seller's feed with
    the same video on it twice.
  * Nothing older than GRACE_HOURS. If the server was down for two days, a
    Tuesday-evening post should not appear on Thursday morning out of context,
    next to a festival that has already passed. It is marked missed, and the
    seller decides.
  * A failure is never retried automatically. Instagram's failures are mostly
    permanent for that post (wrong aspect ratio, a video it cannot transcode,
    a revoked permission), and retrying a caption on a loop is how an account
    gets rate-limited into silence.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta

from backend.core import localtime, social, user_store

log = logging.getLogger("publisher")

STATE_KEY = "publisher_state"

# A post more than this far past its time is not published late.
GRACE_HOURS = 6

# Instagram's own ceiling is 100 API-published posts per account per 24 hours.
# This is far below it on purpose: a planner that suddenly publishes nine posts
# in one tick is a bug, and the damage is done to the seller's feed before
# anyone notices. Anything above this is a signal, not a workload.
MAX_PER_TICK = 3

_claim_lock = threading.Lock()


def _state(email: str) -> dict:
    st = user_store.get_key((email or "").lower(), STATE_KEY, {}) or {}
    return st if isinstance(st, dict) else {}


def _save_state(email: str, st: dict) -> None:
    st["log"] = (st.get("log") or [])[-30:]
    user_store.set_key((email or "").lower(), STATE_KEY, st)


def due_posts(email: str, now: datetime | None = None) -> list[dict]:
    """Scheduled posts whose moment has arrived and has not gone stale.

    `scheduled_at` is naive wall-clock time in the SELLER's timezone — that is
    the frame the whole app writes times in — so it is compared against their
    local now, not the server's. Render runs UTC; comparing against that would
    publish every Indian seller's 7pm post at 12:30am."""
    now = now or localtime.now(email)
    floor = now - timedelta(hours=GRACE_HOURS)
    out = []
    for p in social.all_posts(email):
        if p.get("state") != "scheduled":
            continue
        raw = str(p.get("scheduled_at") or "")
        if not raw:
            continue
        try:
            when = datetime.fromisoformat(raw[:19])
        except ValueError:
            continue
        if when > now:
            continue
        if when < floor:
            continue                     # too late to be in context
        if not social.post_ready(p):
            continue                     # no media — nothing to publish
        out.append(p)
    out.sort(key=lambda p: p.get("scheduled_at") or "")
    return out


def stale_posts(email: str, now: datetime | None = None) -> list[dict]:
    """Scheduled posts whose time passed while nobody was publishing."""
    now = now or localtime.now(email)
    floor = now - timedelta(hours=GRACE_HOURS)
    out = []
    for p in social.all_posts(email):
        if p.get("state") != "scheduled":
            continue
        try:
            when = datetime.fromisoformat(str(p.get("scheduled_at") or "")[:19])
        except ValueError:
            continue
        if when < floor:
            out.append(p)
    return out


def _claim(email: str, post_id: str) -> bool:
    """Mark a post as being published, once. Returns False if someone else got
    there first — which is the only thing standing between a slow reel upload
    and the same video appearing on the seller's profile twice."""
    with _claim_lock:
        st = _state(email)
        claimed = st.get("claimed") or {}
        stamp = claimed.get(post_id)
        if stamp:
            try:
                # A claim older than an hour was left behind by a process that
                # died mid-publish; anything newer is genuinely in flight.
                if datetime.now() - datetime.fromisoformat(stamp) < timedelta(hours=1):
                    return False
            except ValueError:
                pass
        claimed[post_id] = datetime.now().isoformat(timespec="seconds")
        st["claimed"] = claimed
        _save_state(email, st)
        return True


def _release(email: str, post_id: str) -> None:
    with _claim_lock:
        st = _state(email)
        (st.get("claimed") or {}).pop(post_id, None)
        _save_state(email, st)


def _fail_now(email: str, pid: str, reason: str) -> dict:
    social.record_publish(email, pid, {"ok": False, "error": reason})
    return {"ok": False, "post_id": pid, "error": reason}


def _reel_ready(email: str, url: str) -> tuple[str, dict]:
    """Swap a clip for one Instagram accepts, when that is possible."""
    from backend.core import media

    u = str(url or "")
    if "/generated_images/" not in u:
        return u, {}
    name = u.split("/generated_images/")[-1].split("?")[0]
    twin, report = media.instagram_mp4(name, email)
    return (u.replace(name, twin) if twin and twin != name else u), (report or {})


def _instagram_ready(email: str, url: str) -> str:
    """Swap a locally-served picture for a JPEG twin Instagram will accept.

    Only touches media this app serves. A picture the seller pointed at some
    other website is left alone — we cannot convert what we do not host, and
    guessing would turn a working URL into a broken one."""
    from backend.core import media

    u = str(url or "")
    if "/generated_images/" not in u:
        return u
    name = u.split("/generated_images/")[-1].split("?")[0]
    twin = media.instagram_jpeg(name, email)
    return u.replace(name, twin) if twin else u


def _absolute(url: str, base_url: str) -> str:
    """Meta fetches the media itself, so a path is useless to it."""
    u = str(url or "")
    if u.startswith("http://") or u.startswith("https://"):
        return u
    if u.startswith("/") and base_url:
        return base_url.rstrip("/") + u
    return u


def publish_post(email: str, post: dict, base_url: str = "") -> dict:
    """Publish one post and record what happened on it."""
    from backend.core import instagram

    from backend.core import media

    pid = post.get("id") or ""
    is_reel = (post.get("format") or "") == "reel"
    raw = post.get("video_url") if is_reel else (post.get("image_url") or post.get("video_url"))

    # EVERY picture this app generates is a PNG, and Meta accepts JPEG only —
    # so before this line existed, every photo post was refused before it
    # existed, with an error nobody would have traced back to a file extension.
    # A JPEG twin is made once and cached; the original PNG is untouched and
    # still what the storefront and the editor use.
    if not is_reel:
        raw = _instagram_ready(email, raw)
    else:
        # A clip only reaches the watermark remover's clean H.264/AAC/faststart
        # encode if something was actually removed from it — `clean_video_bytes`
        # returns the original untouched otherwise. So a clip with no watermark
        # arrives exactly as the seller downloaded it, and may be VP9, or .webm,
        # or have its metadata at the end of the file where Meta's ranged fetch
        # cannot find it. Checked here, and converted when converting can help.
        raw, vreport = _reel_ready(email, raw)
        blocking = (vreport or {}).get("blocking") or []
        if blocking and not (vreport or {}).get("converted"):
            return _fail_now(email, pid, "This clip cannot go out as a reel. "
                             + " ".join(blocking))
    url = _absolute(raw, base_url)

    def _fail(reason: str) -> dict:
        """Record it, do not just return it.

        THE BUG THIS FIXES: these two checks used to return early without
        touching the post, which left it `scheduled` — so the next tick found
        it due again, failed the same way, and the one after that too, forever,
        while the seller's calendar went on showing a post that was about to go
        out. A failure the app knows about must always land on the post."""
        social.record_publish(email, pid, {"ok": False, "error": reason})
        return {"ok": False, "post_id": pid, "error": reason}

    if not url:
        return _fail("This post has no picture or clip yet.")
    if not url.startswith("https://"):
        # Meta will not fetch over plain http, and the error it returns for
        # that is not one a shop owner could act on.
        return _fail("The media is not on a public https address, so Instagram "
                     "cannot fetch it. Set the app's public URL and try again.")

    caption = _caption(post)
    cover = _absolute(post.get("image_url") or "", base_url) if is_reel else ""
    try:
        res = instagram.publish(email, "reel" if is_reel else "image", url, caption,
                                cover_url=cover if cover != url else "")
    except instagram.InstagramError as e:
        res = {"ok": False, "error": str(e)}
    except Exception as e:  # noqa: BLE001
        res = {"ok": False, "error": str(e)[:200]}

    social.record_publish(email, pid, res)
    return {**res, "post_id": pid}


def _caption(post: dict) -> str:
    cap = str(post.get("caption") or "").strip()
    tags = post.get("hashtags") or []
    if tags:
        cap = (cap + "\n\n" + " ".join("#" + str(t).strip().lstrip("#") for t in tags)).strip()
    return cap


def run_for(email: str, base_url: str = "", now: datetime | None = None) -> dict:
    """Publish everything due for one account."""
    fired, failed = [], []
    for post in due_posts(email, now)[:MAX_PER_TICK]:
        pid = post.get("id") or ""
        if not _claim(email, pid):
            continue
        try:
            res = publish_post(email, post, base_url)
        finally:
            _release(email, pid)
        (fired if res.get("ok") else failed).append(
            {"id": pid, "permalink": res.get("permalink"), "error": res.get("error")})

    missed = 0
    for post in stale_posts(email, now):
        social.record_publish(email, post.get("id") or "", {
            "ok": False, "missed": True,
            "error": (f"This post's time passed more than {GRACE_HOURS} hours ago and it "
                      "was not published, so it was not sent late. Reschedule it if you "
                      "still want it to go out.")})
        missed += 1

    if fired or failed or missed:
        st = _state(email)
        st["last_run_at"] = datetime.now().isoformat(timespec="seconds")
        st["log"] = (st.get("log") or []) + [{
            "at": st["last_run_at"], "published": len(fired),
            "failed": len(failed), "missed": missed}]
        _save_state(email, st)
    return {"published": len(fired), "failed": len(failed), "missed": missed,
            "details": {"published": fired, "failed": failed}}


def run_due(base_url: str = "") -> dict:
    """Every account. Called by the ticker."""
    from backend.core import auth, instagram
    total = {"accounts": 0, "published": 0, "failed": 0, "missed": 0}
    for account in (auth.load_users() or {}):
        try:
            if not instagram.is_connected(account):
                continue                 # nothing to publish to
            res = run_for(account, base_url)
        except Exception as e:  # noqa: BLE001
            log.warning("publishing failed for %s: %s", account, e)
            continue
        total["accounts"] += 1
        for k in ("published", "failed", "missed"):
            total[k] += res[k]
    return total


def status(email: str) -> dict:
    st = _state(email)
    return {"last_run_at": st.get("last_run_at", ""),
            "recent": (st.get("log") or [])[-5:][::-1],
            "due_now": len(due_posts(email)),
            "overdue": len(stale_posts(email))}
