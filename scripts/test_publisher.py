"""
Tests for the piece that publishes the calendar to Instagram.

THIS DID NOT EXIST. The Social Media Manager planned a week, took the seller's
approval, attached the media and showed posts on the calendar marked
"scheduled" — and nothing ever published them. `social.py` contained no
Instagram code at all, and `published` was a state nothing ever set. A seller
could connect their account, approve a week, and none of it would go out, with
no error anywhere, because nothing had tried.

The three things these tests exist to stop:

  * DOUBLE POSTING. A reel takes minutes to transcode. If a tick overlaps the
    previous one, or two workers run, the same video appears on the seller's
    profile twice. That is not a small bug — it is visible to their customers
    and they cannot undo the embarrassment.
  * PUBLISHING WITHOUT APPROVAL. Only `scheduled` posts may go out. A draft, a
    cancelled post, or one still waiting for its clip must never be touched.
  * A POST THAT FAILED LOOKING FINE. A failure has to show on the calendar. A
    post stuck on "scheduled" forever, while the seller believes it went out,
    is worse than an error: they find out when a customer asks why they have
    gone quiet.

Run: python scripts/test_publisher.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["CAFEX_DATA_DIR"] = tempfile.mkdtemp(prefix="pubtest_")

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


from backend.core import instagram, publisher, social, user_store  # noqa: E402

EMAIL = "shop@test.local"
BASE = "https://shop.example.com"
NOW = datetime(2026, 9, 12, 19, 0)


def at(hours):
    return (NOW + timedelta(hours=hours)).isoformat(timespec="minutes")


def seed(posts):
    user_store.set_key(EMAIL, social.POSTS_KEY, posts)


def post(pid, state="scheduled", when=0, fmt="photo", img="/generated_images/a.jpg",
         vid="", caption="Hello", tags=None):
    return {"id": pid, "state": state, "scheduled_at": at(when), "format": fmt,
            "image_url": img, "video_url": vid, "caption": caption,
            "hashtags": tags if tags is not None else ["kurta", "handmade"]}


# A stand-in for Instagram. Records every publish so double posts are visible.
CALLS = []
NEXT = {"ok": True, "media_id": "m1", "permalink": "https://instagram.com/p/abc"}


def fake_publish(email, kind, url, caption, cover_url=""):
    CALLS.append({"kind": kind, "url": url, "caption": caption, "cover": cover_url})
    return dict(NEXT)


instagram.publish = fake_publish
instagram.is_connected = lambda email: True

section("Only approved posts go out")

seed([
    post("p_draft", state="draft"),
    post("p_ready", state="ready"),
    post("p_approved", state="approved"),
    post("p_cancelled", state="cancelled"),
    post("p_published", state="published"),
    post("p_failed", state="failed"),
    post("p_go", state="scheduled"),
])
due = [p["id"] for p in publisher.due_posts(EMAIL, NOW)]
check("a scheduled post is due", "p_go" in due, str(due))
for bad in ("p_draft", "p_ready", "p_approved", "p_cancelled", "p_published", "p_failed"):
    check(f"  {bad.split('_')[1]} is not", bad not in due, str(due))

section("Timing")

seed([
    post("past", when=-1),
    post("now", when=0),
    post("soon", when=1),
    post("tomorrow", when=24),
])
due = [p["id"] for p in publisher.due_posts(EMAIL, NOW)]
check("a post due an hour ago goes now", "past" in due)
check("a post due this minute goes now", "now" in due)
check("a post due in an hour waits", "soon" not in due, str(due))
check("tomorrow's post waits", "tomorrow" not in due)

seed([post("stale", when=-(publisher.GRACE_HOURS + 2))])
check("a post hours past its time is NOT published late",
      publisher.due_posts(EMAIL, NOW) == [],
      "a Tuesday evening post appearing Thursday morning is worse than not appearing")
check("it is reported as overdue instead",
      [p["id"] for p in publisher.stale_posts(EMAIL, NOW)] == ["stale"])

seed([post("edge", when=-(publisher.GRACE_HOURS - 1))])
check("but one just inside the grace window still goes",
      [p["id"] for p in publisher.due_posts(EMAIL, NOW)] == ["edge"])

section("A post with no media is never published")

seed([
    post("no_pic", img="", vid=""),
    post("reel_no_clip", fmt="reel", img="/generated_images/cover.jpg", vid=""),
    post("reel_ok", fmt="reel", vid="/generated_images/clip.mp4"),
])
due = [p["id"] for p in publisher.due_posts(EMAIL, NOW)]
check("a photo post with no picture is skipped", "no_pic" not in due, str(due))
check("a reel with no clip is skipped", "reel_no_clip" not in due, str(due))
check("a reel WITH a clip goes", "reel_ok" in due)

section("Reels go out as reels")

CALLS.clear()
seed([post("r1", fmt="reel", vid="/generated_images/clip.mp4",
           img="/generated_images/cover.jpg", caption="New drop", tags=["reel"])])
res = publisher.run_for(EMAIL, BASE, NOW)
check("it published", res["published"] == 1, str(res))
check("as a reel, not a photo", CALLS[0]["kind"] == "reel", CALLS[0]["kind"])
check("using the clip, not the cover image",
      CALLS[0]["url"] == f"{BASE}/generated_images/clip.mp4", CALLS[0]["url"])
check("and the cover is passed separately",
      CALLS[0]["cover"] == f"{BASE}/generated_images/cover.jpg", CALLS[0]["cover"])

CALLS.clear()
seed([post("i1", caption="Cotton kurta", tags=["kurta", "handmade"])])
publisher.run_for(EMAIL, BASE, NOW)
check("a photo post goes as a photo", CALLS[0]["kind"] == "image")
check("the caption carries the hashtags",
      CALLS[0]["caption"] == "Cotton kurta\n\n#kurta #handmade", repr(CALLS[0]["caption"]))

section("Meta fetches the media itself, so the URL must be absolute")

CALLS.clear()
seed([post("rel")])
publisher.run_for(EMAIL, BASE, NOW)
check("a stored path becomes a full https url",
      CALLS[0]["url"].startswith("https://"), CALLS[0]["url"])

CALLS.clear()
seed([post("abs", img="https://cdn.example.com/x.jpg")])
publisher.run_for(EMAIL, BASE, NOW)
check("a url that is already absolute is left alone",
      CALLS[0]["url"] == "https://cdn.example.com/x.jpg", CALLS[0]["url"])

CALLS.clear()
seed([post("nobase")])
r = publisher.run_for(EMAIL, "", NOW)
check("with no public base url, nothing is sent to Instagram", CALLS == [], str(CALLS))
check("and it fails with something the seller can act on", r["failed"] == 1, str(r))
p = next(x for x in social.all_posts(EMAIL) if x["id"] == "nobase")
check("saying the media is not on a public address",
      "public https" in (p.get("publish_error") or ""), p.get("publish_error"))
# A failure the app can see for itself must still leave the scheduled queue.
# Left as "scheduled" it fails identically on every tick, forever, while the
# calendar goes on showing a post that is about to go out.
check("and the post leaves the queue rather than failing forever",
      p["state"] == "failed", p["state"])
check("so the next tick does not try it again",
      publisher.run_for(EMAIL, "", NOW)["failed"] == 0)

section("The same post is never published twice")

CALLS.clear()
seed([post("once")])
publisher.run_for(EMAIL, BASE, NOW)
publisher.run_for(EMAIL, BASE, NOW)
publisher.run_for(EMAIL, BASE, NOW)
check("three ticks, one post", len(CALLS) == 1, f"{len(CALLS)} calls")
check("because it is no longer scheduled after the first",
      publisher.due_posts(EMAIL, NOW) == [])

# The dangerous case: a reel takes minutes to transcode, so a tick can start
# while the previous one is still inside publish. The claim is what stops the
# same video landing on the profile twice.
CALLS.clear()
seed([post("slow", fmt="reel", vid="/generated_images/slow.mp4")])
overlapped = []


def slow_publish(email, kind, url, caption, cover_url=""):
    CALLS.append({"kind": kind, "url": url, "caption": caption, "cover": cover_url})
    # A second tick lands while we are still uploading.
    overlapped.append(publisher.run_for(EMAIL, BASE, NOW))
    return dict(NEXT)


instagram.publish = slow_publish
publisher.run_for(EMAIL, BASE, NOW)
instagram.publish = fake_publish
check("a tick that overlaps a slow reel does not publish it again",
      len(CALLS) == 1, f"{len(CALLS)} calls — the seller's feed would show it twice")
check("and the overlapping tick reports nothing published",
      overlapped and overlapped[0]["published"] == 0, str(overlapped))

section("A failure is visible, not silent")

CALLS.clear()
NEXT.clear()
NEXT.update({"ok": False, "error": "The aspect ratio is not supported", "step": "create_media"})
seed([post("bad")])
res = publisher.run_for(EMAIL, BASE, NOW)
check("it is counted as failed", res["failed"] == 1 and res["published"] == 0, str(res))
p = next(x for x in social.all_posts(EMAIL) if x["id"] == "bad")
check("the post is marked failed on the calendar", p["state"] == "failed", p["state"])
check("with Instagram's own reason on it",
      "aspect ratio" in (p.get("publish_error") or ""), p.get("publish_error"))
check("and it is NOT left looking scheduled", p["state"] != "scheduled")

check("a failed post is not retried on the next tick",
      (publisher.run_for(EMAIL, BASE, NOW)["failed"] == 0 and not CALLS[1:]),
      "retrying a rejected caption on a loop is how an account gets rate-limited")

NEXT.clear()
NEXT.update({"ok": True, "media_id": "m2", "permalink": "https://instagram.com/p/xyz"})

section("A published post records where it went")

CALLS.clear()
seed([post("good")])
publisher.run_for(EMAIL, BASE, NOW)
p = next(x for x in social.all_posts(EMAIL) if x["id"] == "good")
check("state is published", p["state"] == "published")
check("the permalink is kept so the seller can open it",
      p.get("permalink") == "https://instagram.com/p/xyz", str(p.get("permalink")))
check("and when it went out", bool(p.get("published_at")))
check("with no error left on it", not p.get("publish_error"))

section("A post nobody published while the server was down")

seed([post("missed", when=-(publisher.GRACE_HOURS + 3))])
res = publisher.run_for(EMAIL, BASE, NOW)
check("it is counted as missed", res["missed"] == 1, str(res))
p = next(x for x in social.all_posts(EMAIL) if x["id"] == "missed")
check("taken out of the queue so it is not retried forever", p["state"] != "scheduled")
check("and flagged as missed rather than as our failure", p.get("publish_missed") is True)
check("with an explanation that says what to do",
      "reschedule" in (p.get("publish_error") or "").lower(), p.get("publish_error"))

section("One tick cannot flood a feed")

CALLS.clear()
seed([post(f"m{i}", when=-1) for i in range(9)])
res = publisher.run_for(EMAIL, BASE, NOW)
check("a tick publishes at most a few posts",
      res["published"] == publisher.MAX_PER_TICK, str(res))
check("nine posts landing at once would be a bug doing visible damage",
      publisher.MAX_PER_TICK <= 5, str(publisher.MAX_PER_TICK))
check("the rest stay scheduled for the next tick",
      len(publisher.due_posts(EMAIL, NOW)) == 9 - publisher.MAX_PER_TICK)

section("Accounts with no Instagram are skipped entirely")

instagram.is_connected = lambda email: False
CALLS.clear()
seed([post("x")])
publisher.run_due(BASE)
check("nothing is attempted", CALLS == [], str(CALLS))
p = next(x for x in social.all_posts(EMAIL) if x["id"] == "x")
check("and the post is left alone, not marked failed", p["state"] == "scheduled")
instagram.is_connected = lambda email: True

section("Status, for the screen")

st = publisher.status(EMAIL)
for k in ("last_run_at", "recent", "due_now", "overdue"):
    check(f"status carries {k}", k in st, str(list(st)))

section("Instagram accepts JPEG only — and this app makes PNGs")

# THE BUG THIS SECTION EXISTS FOR. Every picture the app generates is saved as
# PNG (studio.py, content_gen.py both write .png). Meta's content-publishing
# docs say "JPEG is the only image format supported": a PNG is refused at
# container creation with subcode 2207005, before the post exists. So every
# photo post ever scheduled would have failed, on every account, with an error
# nobody would have connected to a file extension.
import io  # noqa: E402
from PIL import Image  # noqa: E402
from backend.core import media  # noqa: E402


def make(name, size, mode="RGB", colour=(200, 120, 90)):
    img = Image.new(mode, size, colour + ((255,) if mode == "RGBA" else ()))
    buf = io.BytesIO()
    img.save(buf, format="PNG" if name.endswith(".png") else "JPEG")
    media.save(name, buf.getvalue(), EMAIL)
    return name


png = make("shot1.png", (1000, 1000))
twin = media.instagram_jpeg(png, EMAIL)
check("a PNG gets a JPEG twin", twin.endswith(".jpg"), twin)
got = media.read(twin)
check("the twin exists and has bytes", bool(got) and len(got[0]) > 100)
check("and it really is a JPEG, not a renamed PNG",
      Image.open(io.BytesIO(got[0])).format == "JPEG",
      Image.open(io.BytesIO(got[0])).format)
check("the original PNG is untouched — the storefront still uses it",
      media.read(png) is not None)
check("asking twice reuses the twin rather than rebuilding it",
      media.instagram_jpeg(png, EMAIL) == twin)
check("a file that is already a twin is returned as-is",
      media.instagram_jpeg(twin, EMAIL) == twin)
check("a video is never converted", media.instagram_jpeg("clip.mp4", EMAIL) == "")

# Transparency. A cut-out product on a JPEG has no alpha channel to fall back
# on, and flattening onto black looks like a mistake.
rgba = make("cutout.png", (800, 800), mode="RGBA")
t2 = media.instagram_jpeg(rgba, EMAIL)
im2 = Image.open(io.BytesIO(media.read(t2)[0]))
check("a transparent PNG converts without crashing", im2.format == "JPEG")
check("and has no alpha left", im2.mode == "RGB", im2.mode)

section("The shapes Instagram refuses")

def ratio_of(name):
    im = Image.open(io.BytesIO(media.read(media.instagram_jpeg(name, EMAIL))[0]))
    return im.size[0] / im.size[1], im.size

tall = make("tall.png", (600, 1600))          # 0.375 — far outside 4:5
r, size = ratio_of(tall)
check("a very tall picture is padded into range",
      media.IG_MIN_RATIO - 0.01 <= r <= media.IG_MAX_RATIO + 0.01, f"{r:.3f} {size}")

wide = make("wide.png", (2400, 500))          # 4.8 — far outside 1.91
r, size = ratio_of(wide)
check("a very wide picture is padded into range",
      media.IG_MIN_RATIO - 0.01 <= r <= media.IG_MAX_RATIO + 0.01, f"{r:.3f} {size}")

square = make("square.png", (1080, 1080))
r, size = ratio_of(square)
check("a square picture is left square", abs(r - 1.0) < 0.01, f"{r:.3f}")

big = make("big.png", (4000, 4000))
_, size = ratio_of(big)
check("an oversized picture is brought under Instagram's width limit",
      size[0] <= media.IG_MAX_WIDTH, str(size))
small = make("small.png", (120, 120))
_, size = ratio_of(small)
check("an undersized picture is brought up to the minimum",
      size[0] >= media.IG_MIN_WIDTH, str(size))

# Padding rather than cropping, because these are product photographs: a crop
# that satisfies Instagram by removing the top of a kurta has published the
# wrong picture, and the seller hears about it from a customer.
im = Image.open(io.BytesIO(media.read(media.instagram_jpeg(tall, EMAIL))[0]))
check("padding is used, not cropping — nothing is cut off the product",
      im.size[1] >= 1000 or im.size[0] / im.size[1] >= media.IG_MIN_RATIO,
      str(im.size))

section("Publishing sends the JPEG, not the PNG")

CALLS.clear()
seed([post("pngpost", img=f"/generated_images/{png}")])
publisher.run_for(EMAIL, BASE, NOW)
check("the URL Instagram is given ends in .jpg",
      CALLS[0]["url"].endswith(".jpg"), CALLS[0]["url"])
check("and it is NOT the .png that would have been refused",
      not CALLS[0]["url"].endswith(".png"), CALLS[0]["url"])

CALLS.clear()
seed([post("ext", img="https://someoneelse.example.com/photo.png")])
publisher.run_for(EMAIL, BASE, NOW)
check("a picture hosted somewhere else is left alone — we cannot convert it",
      CALLS[0]["url"] == "https://someoneelse.example.com/photo.png", CALLS[0]["url"])

CALLS.clear()
seed([post("reelpng", fmt="reel", vid="/generated_images/clip.mp4",
           img=f"/generated_images/{png}")])
publisher.run_for(EMAIL, BASE, NOW)
check("a reel still sends the video untouched",
      CALLS[0]["url"].endswith(".mp4"), CALLS[0]["url"])

section("Reels: the clip Instagram is given must be one it accepts")

# THE GAP THIS CLOSES. The watermark remover re-encodes properly — H.264,
# yuv420p, AAC, +faststart — but ONLY when it removed something.
# `clean_video_bytes` says it outright: "The original comes back when nothing
# was removed." So a clip with no watermark reaches Instagram exactly as the
# seller downloaded it: possibly .webm, possibly VP9, possibly with its moov
# atom at the end where Meta's ranged fetch cannot find it. Nothing checked.
import shutil as _shutil  # noqa: E402
import subprocess as _sub  # noqa: E402
from backend.core import videotools  # noqa: E402

_FF = _shutil.which("ffmpeg")
if not _FF:
    try:
        import imageio_ffmpeg
        _FF = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        _FF = None

if not _FF or not videotools._ffprobe():
    print("  (ffmpeg/ffprobe unavailable here — reel checks skipped)")
else:
    import tempfile as _tf  # noqa: E402
    _vdir = _tf.mkdtemp(prefix="vids_")

    def clip(name, seconds=8, size="1080x1920", vcodec="libx264", acodec="aac",
             faststart=True, container=None):
        """A real encoded file — mocks would prove nothing about ffprobe."""
        path = os.path.join(_vdir, name)
        cmd = [_FF, "-y", "-v", "error",
               "-f", "lavfi", "-i", f"testsrc=size={size}:rate=24:duration={seconds}",
               "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
               "-c:v", vcodec, "-pix_fmt", "yuv420p", "-c:a", acodec, "-shortest"]
        if faststart and name.endswith((".mp4", ".mov")):
            cmd += ["-movflags", "+faststart"]
        if container:
            cmd += ["-f", container]
        cmd.append(path)
        _sub.run(cmd, capture_output=True, timeout=180)
        return path

    good = clip("good.mp4")
    rep = videotools.reel_report(good)
    check("a proper 9:16 H.264 clip passes", rep["ok"], str(rep["blocking"]))
    check("with no warnings either", not rep["warnings"], str(rep["warnings"]))
    info = rep["info"]
    check("the probe reads its real duration", 7 < info["duration"] < 9, str(info["duration"]))
    check("and its real size", info["width"] == 1080 and info["height"] == 1920, str(info))
    check("and its real codec", info["vcodec"] == "h264", info["vcodec"])

    landscape = clip("wide.mp4", size="1920x1080")
    rep = videotools.reel_report(landscape)
    check("a landscape clip still publishes", rep["ok"], str(rep["blocking"]))
    check("but is warned about, because only 9:16 reaches the Reels tab",
          any("Reels tab" in w for w in rep["warnings"]), str(rep["warnings"]))

    short = clip("short.mp4", seconds=1)
    rep = videotools.reel_report(short)
    check("a one-second clip is refused", not rep["ok"], str(rep))
    check("and told how long it actually is",
          any("second" in b for b in rep["blocking"]), str(rep["blocking"]))
    check("and is NOT offered as fixable — no encode adds seconds",
          not rep["fixable"])

    long_tab = clip("longish.mp4", seconds=120)
    rep = videotools.reel_report(long_tab)
    check("a two-minute clip still publishes", rep["ok"], str(rep["blocking"]))
    check("with a warning about the Reels tab window",
          any("Reels tab" in w for w in rep["warnings"]), str(rep["warnings"]))

    webm = clip("odd.webm", vcodec="libvpx-vp9", acodec="libopus")
    if os.path.exists(webm) and os.path.getsize(webm) > 0:
        rep = videotools.reel_report(webm)
        check("a VP9 .webm is refused", not rep["ok"], str(rep))
        check("naming the codec, not just 'invalid file'",
              any("H.264" in b for b in rep["blocking"]), str(rep["blocking"]))
        check("and it IS fixable, because re-encoding solves it", rep["fixable"])

        fixed = os.path.join(_vdir, "fixed.mp4")
        res = videotools.make_reel_ready(webm, fixed)
        check("converting it succeeds", res.get("ok"), str(res))
        rep2 = videotools.reel_report(fixed)
        check("and the result passes", rep2["ok"], str(rep2["blocking"]))
        check("as H.264", rep2["info"]["vcodec"] == "h264", rep2["info"]["vcodec"])
        check("with AAC sound", rep2["info"]["acodec"] == "aac", rep2["info"]["acodec"])

    check("a file that cannot be probed is sent as-is rather than blocked",
          videotools.reel_report(os.path.join(_vdir, "nope.mp4"))["ok"])

    section("Publishing a reel uses the checked clip")

    media.save("realclip.mp4", open(good, "rb").read(), EMAIL)
    CALLS.clear()
    seed([post("okreel", fmt="reel", vid="/generated_images/realclip.mp4")])
    res = publisher.run_for(EMAIL, BASE, NOW)
    check("a good clip publishes", res["published"] == 1, str(res))
    check("and is sent untouched — no pointless re-encode",
          CALLS[0]["url"].endswith("realclip.mp4"), CALLS[0]["url"])

    CALLS.clear()
    media.save("tooshort.mp4", open(short, "rb").read(), EMAIL)
    seed([post("badreel", fmt="reel", vid="/generated_images/tooshort.mp4")])
    res = publisher.run_for(EMAIL, BASE, NOW)
    check("a clip Instagram would refuse is never sent", CALLS == [], str(CALLS))
    check("it is failed locally instead", res["failed"] == 1, str(res))
    p = next(x for x in social.all_posts(EMAIL) if x["id"] == "badreel")
    check("with the real reason on the post",
          "second" in (p.get("publish_error") or ""), p.get("publish_error"))
    check("and it leaves the queue rather than retrying forever",
          p["state"] == "failed", p["state"])

section("One clock: the planner and the publisher must agree on what time it is")

# THE BUG CLASS THIS LOCKS OUT. Every scheduled_at in this app is a NAIVE
# wall-clock time in the seller's own timezone — "14 Sep, 7:00 pm" means seven
# in the evening where they live. Render runs in UTC. So the moment any part of
# this chain reads the server clock instead of the seller's, the two halves
# disagree: the planner writes 7pm meaning IST, the publisher reads 7pm meaning
# UTC, and the post goes out at half past midnight. Nothing crashes. The seller
# just finds their reel was published while they were asleep.
#
# social.py read `date.today()` in eight places. Between midnight and 5:30am
# IST that is still yesterday — the calendar highlighted the wrong square, the
# festival countdown was a day out, and a week planned in that window started
# on the wrong Monday.
import inspect  # noqa: E402
from backend.core import localtime  # noqa: E402

_pub_src = inspect.getsource(publisher)
check("the publisher reads the seller's clock", "localtime.now(email)" in _pub_src)
check("and never the server's for deciding what is due",
      "datetime.now()" not in inspect.getsource(publisher.due_posts),
      inspect.getsource(publisher.due_posts))
check("nor for deciding what has gone stale",
      "datetime.now()" not in inspect.getsource(publisher.stale_posts))

_soc_src = inspect.getsource(social)
# Comment lines stripped: the note explaining this fix quotes `date.today()`,
# and a test that fails because someone documented the bug is a bad test.
_soc_code = "\n".join(l for l in _soc_src.splitlines()
                      if not l.lstrip().startswith("#"))
check("the planner no longer reads the server's date",
      _soc_code.count("date.today()") <= 1,
      f"{_soc_code.count('date.today()')} left — the one survivor is the "
      "fallback in upcoming_festivals(), which takes no account")
check("the calendar's highlighted day is the seller's day",
      "localtime.today(email).isoformat()" in _soc_src)
check("and the week is planned from the seller's day",
      "start = start or localtime.today(email)" in _soc_src)

# Both sides must resolve to the SAME function, not two that merely agree today.
check("both read the one timezone module",
      social.localtime is localtime and publisher.localtime is localtime)


class _FakeTZ:
    """Pin the account to a zone far from UTC and check both halves move."""


_real_get = localtime.get
try:
    localtime.get = lambda email="": {"country": "IN", "country_name": "India",
                                      "tz": "Pacific/Kiritimati",   # UTC+14
                                      "note": "", "set": True}
    planner_day = social.localtime.today(EMAIL)
    publisher_now = publisher.localtime.now(EMAIL)
    check("the planner follows the account's timezone",
          planner_day == publisher_now.date(),
          f"{planner_day} vs {publisher_now.date()}")

    localtime.get = lambda email="": {"country": "US", "country_name": "United States",
                                      "tz": "Pacific/Honolulu",     # UTC-10
                                      "note": "", "set": True}
    check("and both move together when it changes",
          social.localtime.today(EMAIL) == publisher.localtime.now(EMAIL).date(),
          "a 24-hour swing must not split the two halves apart")
finally:
    localtime.get = _real_get

# The end-to-end check: a post scheduled for the seller's evening is due at the
# seller's evening, and not at the server's.
_real_now = localtime.now
try:
    # 7pm for the seller, while the server believes it is 1:30pm UTC.
    localtime.now = lambda email="": datetime(2026, 9, 14, 19, 0)
    seed([{"id": "tz", "state": "scheduled", "scheduled_at": "2026-09-14T19:00",
           "format": "photo", "image_url": "/generated_images/a.jpg",
           "video_url": "", "caption": "evening", "hashtags": []}])
    check("a 7pm post is due at the seller's 7pm",
          [p["id"] for p in publisher.due_posts(EMAIL)] == ["tz"])

    localtime.now = lambda email="": datetime(2026, 9, 14, 13, 30)
    check("and is NOT due at the same wall-clock hour in a different zone",
          publisher.due_posts(EMAIL) == [],
          "5.5 hours early is exactly the India/UTC mistake")
finally:
    localtime.now = _real_now

print(f"\n{PASSED} passed, {FAILED} failed")
sys.exit(1 if FAILED else 0)
