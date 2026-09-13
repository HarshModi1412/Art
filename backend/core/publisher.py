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
import os
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

# ---------------------------------------------------------------------------
# Where this app lives, as the public internet sees it
# ---------------------------------------------------------------------------
# THE BUG THIS FIXES, and it is the reason posts were not going out at all.
# Meta fetches the picture and the clip from us, so it needs an absolute
# https:// address — a stored path like /generated_images/x.jpg means nothing
# to it. Inside a web request that address is obvious (it is on the request).
# The background ticker has no request, so it read PUBLIC_BASE_URL from the
# environment — a variable that was documented nowhere, set nowhere, and
# present in no deployment. Every background publish therefore failed with
# "the media is not on a public https address", which reads like a
# configuration mistake by the seller and was in fact ours.
#
# So the app now LEARNS its own address from the first real request that
# arrives and remembers it on disk, which means it is correct with nothing to
# configure. The env var still wins when it is set, for a deployment behind a
# proxy that rewrites Host.
_BASE_FILE = "public_base_url.txt"
_base_cache = ""


def _base_path() -> str:
    from backend.core import auth
    return os.path.join(auth.BASE_DIR, _BASE_FILE)


def remember_base_url(url: str) -> None:
    """Called on real requests. Cheap, and idempotent once it settles."""
    global _base_cache
    url = str(url or "").strip().rstrip("/")
    if not url.startswith("http") or url == _base_cache:
        return
    # localhost is useless to Meta and must never overwrite a real address.
    if "127.0.0.1" in url or "localhost" in url:
        if _base_cache:
            return
    _base_cache = url
    try:
        os.makedirs(os.path.dirname(_base_path()), exist_ok=True)
        with open(_base_path(), "w", encoding="utf-8") as fh:
            fh.write(url)
    except Exception:  # noqa: BLE001 — the in-memory copy still works
        pass


def base_url() -> str:
    """The address to hand Meta. Env wins, then what we learned, then disk."""
    global _base_cache
    env = (os.environ.get("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if env:
        return env
    if _base_cache:
        return _base_cache
    try:
        with open(_base_path(), encoding="utf-8") as fh:
            _base_cache = fh.read().strip().rstrip("/")
    except Exception:  # noqa: BLE001
        _base_cache = ""
    return _base_cache


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


def publish_post(email: str, post: dict, base: str = "") -> dict:
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
    url = _absolute(raw, base or base_url())

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
    cover = _absolute(post.get("image_url") or "", base or base_url()) if is_reel else ""
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


def run_for(email: str, base: str = "", now: datetime | None = None) -> dict:
    """Publish everything due for one account. `base` defaults to the address
    the app learned about itself, so a caller with no request still works."""
    base = base or base_url()
    fired, failed = [], []
    for post in due_posts(email, now)[:MAX_PER_TICK]:
        pid = post.get("id") or ""
        if not _claim(email, pid):
            continue
        try:
            res = publish_post(email, post, base)
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


def run_due(base: str = "") -> dict:
    """Every account. Called by the ticker."""
    from backend.core import auth, instagram
    base = base or base_url()
    total = {"accounts": 0, "published": 0, "failed": 0, "missed": 0}
    for account in (auth.load_users() or {}):
        try:
            if not instagram.is_connected(account):
                continue                 # nothing to publish to
            res = run_for(account, base)
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


# ---------------------------------------------------------------------------
# "Why is this post not going out?"
# ---------------------------------------------------------------------------
# WHY THIS EXISTS. A scheduled post that does not appear gives you nothing to
# work with. The post looks fine on the calendar, Instagram is connected, and
# the only way to find out which of eight conditions failed was to read the
# publisher's source. That turned every "it is not posting" into a day of
# guessing — for the seller, and for whoever they ask.
#
# So the publisher can now explain itself: for every post that has not finished,
# the one sentence that says where it stands and what would move it.
def queue_report(email: str, now: datetime | None = None) -> dict:
    """Every unfinished post, with the reason it is or is not going out."""
    from backend.core import instagram

    now = now or localtime.now(email)
    floor = now - timedelta(hours=GRACE_HOURS)
    connected = False
    try:
        connected = instagram.is_connected(email)
    except Exception:  # noqa: BLE001
        connected = False

    rows, due_n = [], 0
    for p in social.all_posts(email):
        state = p.get("state") or ""
        if state in ("cancelled",):
            continue
        raw = str(p.get("scheduled_at") or "")
        when = None
        if raw:
            try:
                when = datetime.fromisoformat(raw[:19])
            except ValueError:
                when = None

        ready = social.post_ready(p)
        verdict, will_post = "", False

        if state == "published":
            verdict = "Published." + (f" {p.get('permalink')}" if p.get("permalink") else "")
        elif state == "failed":
            verdict = "Failed: " + (p.get("publish_error") or "no reason recorded")
        elif state in ("draft", "ready"):
            verdict = "Not approved yet — it is waiting for you in the Approval panel."
        elif state == "approved" and not ready:
            verdict = ("Approved, but it has no "
                       + ("clip" if p.get("format") == "reel" else "picture")
                       + " yet. It goes out once the media is on it.")
        elif state == "approved":
            # The trap: media arrived but nothing moved it on. Worth saying,
            # because the calendar shows a time and the post never goes.
            verdict = ("Approved and has its media, but was never scheduled. "
                       "Open it and press Save & schedule.")
        elif state != "scheduled":
            verdict = f"In state '{state}', which the publisher does not send."
        elif not raw or when is None:
            verdict = "Scheduled, but its date and time could not be read."
        elif not ready:
            verdict = ("Scheduled, but it has no "
                       + ("clip" if p.get("format") == "reel" else "picture") + " yet.")
        elif when > now:
            mins = int((when - now).total_seconds() // 60)
            verdict = (f"Goes out {raw[:16].replace('T', ' at ')} — "
                       + (f"in {mins} minutes." if mins < 120
                          else f"in about {mins // 60} hours."))
        elif when < floor:
            verdict = (f"Its time ({raw[:16].replace('T', ' at ')}) passed more than "
                       f"{GRACE_HOURS} hours ago, so it will not be sent late. "
                       "Reschedule it to send it.")
        elif not connected:
            verdict = "Due now, but Instagram is not connected."
        else:
            verdict = "Due now — it goes out at the next check."
            will_post = True
            due_n += 1

        rows.append({"id": p.get("id"), "state": state, "format": p.get("format") or "photo",
                     "scheduled_at": raw, "has_media": ready,
                     "verdict": verdict, "will_post": will_post})

    rows.sort(key=lambda r: r["scheduled_at"] or "")
    return {
        "instagram_connected": connected,
        "now": now.isoformat(timespec="minutes"),
        "tz": localtime.label(email),
        "public_base_url": base_url(),
        "due_now": due_n,
        "posts": rows[-40:],
    }


def kick(email: str) -> bool:
    """Publish anything due for this seller, in the background, right now.

    THE GAP THIS CLOSES. The weekly plan and the weekly win-back both catch up
    the moment a seller opens the app. Publishing did not — it waited for the
    fifteen-minute ticker, and that ticker dies with the process. So a seller
    sitting in front of the app, watching a post's time come and go, saw
    nothing happen, and the app had given them no reason to think opening it
    would help. It does now."""
    try:
        if not due_posts(email):
            return False
        from backend.core import instagram
        if not instagram.is_connected(email):
            return False
    except Exception:  # noqa: BLE001
        return False
    threading.Thread(target=_safe_run, args=(email,), daemon=True,
                     name=f"publish-{email[:12]}").start()
    return True


def _safe_run(email: str) -> None:
    try:
        run_for(email)
    except Exception as e:  # noqa: BLE001
        log.warning("publish kick failed for %s: %s", email, e)
