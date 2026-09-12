"""Where a seller goes to turn a prompt into a clip, and what it will cost them.

WHY THIS IS A MODULE AND NOT THREE LINKS IN THE HTML
----------------------------------------------------
Two reasons.

The first is honesty. Every fact below — free-tier credit counts, which model
costs what, whether there is a visible watermark, which hours the free tier is
switched off — was checked on 10 September 2026 and every one of them has moved
at least once in the past year. Google retired Whisk, superseded Veo 3 with 3.1
and Gemini Omni, and changed the watermark policy a month before this was
written. Hard-coding a number without a date next to it is how an app ends up
confidently telling a seller something that stopped being true in March. So
CHECKED_ON travels with the numbers, and the UI shows it.

The second is that generating video in-app is the wrong default for this
audience. Our own Veo call costs about ₹105 a clip against the seller's card and
gives them no chance to look at the result before paying. Google Flow's free tier
gives them roughly five clips a day for nothing, in a tool built for exactly this,
with a preview before they commit. Handing over the prompt and the link is a
better product than billing them — so that is the primary route, and the in-app
generator stays as the "I cannot be bothered, just do it" option.

WHY NOT A DEEP LINK WITH THE PROMPT IN IT
Because there isn't one. Flow publishes no documented URL parameter that
pre-fills a prompt, and shipping an undocumented `?prompt=` that silently does
nothing looks broken. So the app copies the prompt to the clipboard at the moment
the seller clicks through, which makes it one paste on the other side.
"""
from __future__ import annotations

# The date every figure below was verified. Shown in the UI next to the numbers.
CHECKED_ON = "10 September 2026"

# Ordered best-first for the job this app has: one vertical clip in which the
# product is unmistakably the seller's own product.
VIDEO_TOOLS = [
    {
        "id": "flow",
        "name": "Google Flow",
        "url": "https://labs.google/fx/tools/flow",
        "best_for": "Recommended. The only one that lets you pin the first frame "
                    "to your own photograph, so the thing in the video is the "
                    "thing you actually sell.",
        "free": "Free tier: 50 credits a day, which is about 5 clips on the "
                "cheapest model. India included.",
        "how": [
            "Open Flow and sign in with your Google account.",
            "In the prompt box, click the model name, then choose Video → Frames.",
            "Drag your product photo onto “+ Add start frame”. This is the step "
            "that matters — it makes frame one your real product.",
            "Paste the prompt (already copied for you) and describe the movement.",
            "Set the shape to 9:16 so it fits a reel, pick 8 seconds, and Generate.",
        ],
        "watch_out": [
            "On the free tier, video generation is switched off between 7:30 and "
            "10:30 in the morning India time. If nothing happens, that is why.",
            "Desktop Flow wants Chrome or Edge. There is also a Flow app on Android.",
            "Clips come out with a visible Google mark unless you turn it off in "
            "Settings → Media Watermark. An invisible marker stays either way, so "
            "do not pass the clip off as a real camera shot.",
            "You need to be 18+ with a verified Google account.",
        ],
        "cost_note": "Free for about 5 clips a day. Paid plans start around "
                     "$5/month for more.",
        "primary": True,
    },
    {
        "id": "gemini",
        "name": "Gemini (photo to video)",
        "url": "https://gemini.google.com/veo",
        "best_for": "Simplest of the lot. Upload a photo, say what should happen, "
                    "get a clip with sound. No timeline, no model picker.",
        "free": "Needs a paid Google AI plan.",
        "how": [
            "Open the link and sign in.",
            "Upload your product photo.",
            "Paste the prompt and press go.",
        ],
        "watch_out": [
            "It gives you less control over the first frame than Flow, so the "
            "product can drift from your actual item.",
        ],
        "cost_note": "Included in a Google AI subscription.",
        "primary": False,
    },
    {
        "id": "kling",
        "name": "Kling AI",
        "url": "https://kling.ai/app",
        "best_for": "The one to use if you do not want a Google subscription at "
                    "all. Good at animating a photo.",
        "free": "Free tier: 66 credits a day, roughly 3 to 6 clips.",
        "how": [
            "Open the link and make an account.",
            "Choose image-to-video and upload your product photo.",
            "Paste the prompt and generate.",
        ],
        "watch_out": [
            "Free clips carry a Kling watermark on the picture itself, which "
            "looks wrong on a shop's own reel. Removing it needs a paid plan.",
            "Free output is capped at 720p and about 5 seconds.",
        ],
        "cost_note": "Free with a watermark; about $7/month without.",
        "primary": False,
    },
]


def tools(for_reel: bool = True) -> dict:
    """The handoff payload: where to go, how, and what to watch out for."""
    return {
        "checked_on": CHECKED_ON,
        "tools": VIDEO_TOOLS,
        "primary": next((t for t in VIDEO_TOOLS if t.get("primary")), VIDEO_TOOLS[0]),
        "note": ("These are other people's tools and their prices and free limits "
                 "change often — what is written here was checked on "
                 f"{CHECKED_ON}. Open the link for what is true today."),
    }


# ---------------------------------------------------------------------------
# Is this clip one Instagram will actually accept as a reel?
# ---------------------------------------------------------------------------
# WHY THIS EXISTS. The watermark remover re-encodes a clip properly — H.264,
# yuv420p, AAC, +faststart — but only when it actually removed something.
# `clean_video_bytes` says so plainly: "The original comes back when nothing
# was removed." So a clip with no watermark, or one where cleaning failed,
# reaches Instagram exactly as the seller's file was: possibly .mov or .webm,
# possibly VP9 or HEVC, possibly with its moov atom at the end of the file.
#
# Nothing checked any of that. The failure would arrive as one of Meta's
# numbered subcodes at the moment the post was due — 7pm on a Saturday, with a
# festival passing — and the seller would have no idea which of six things was
# wrong.
#
# So: probe the clip when it is attached, say what is wrong in words, and fix
# it where fixing is possible. A remux is seconds; a re-encode is a minute; an
# eleven-minute clip cannot be made into a reel at all and has to be said so.
import json
import os
import shutil
import subprocess

# Instagram's published reel limits. The Reels *tab* wants 9:16 and 5-90s; the
# API accepts a wider range and simply shows the post in the feed instead, so
# those two are warnings, not refusals — a seller who wants a square clip up is
# not helped by us refusing it.
REEL_MAX_BYTES = 100 * 1024 * 1024
REEL_MIN_SECONDS = 3
REEL_MAX_SECONDS = 900          # 15 min is the hard API ceiling
REEL_TAB_MIN_SECONDS = 5
REEL_TAB_MAX_SECONDS = 90
GOOD_VCODECS = {"h264", "hevc"}
GOOD_ACODECS = {"aac", "mp3"}


def _ffprobe() -> str | None:
    p = shutil.which("ffprobe")
    if p:
        return p
    # imageio-ffmpeg ships ffmpeg but not ffprobe; they live side by side when
    # a real ffmpeg is installed, so try the sibling path before giving up.
    try:
        import imageio_ffmpeg
        cand = imageio_ffmpeg.get_ffmpeg_exe().replace("ffmpeg", "ffprobe")
        return cand if os.path.exists(cand) else None
    except Exception:  # noqa: BLE001
        return None


def probe(path: str) -> dict:
    """What this file actually is. Empty dict when it cannot be read."""
    exe = _ffprobe()
    if not exe or not os.path.exists(path):
        return {}
    try:
        out = subprocess.run(
            [exe, "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", path],
            capture_output=True, text=True, timeout=60)
        d = json.loads(out.stdout or "{}")
    except Exception:  # noqa: BLE001
        return {}
    fmt = d.get("format") or {}
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in d.get("streams", []) if s.get("codec_type") == "audio"), {})
    try:
        duration = float(fmt.get("duration") or v.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    return {
        "duration": duration,
        "width": int(v.get("width") or 0),
        "height": int(v.get("height") or 0),
        "vcodec": str(v.get("codec_name") or ""),
        "acodec": str(a.get("codec_name") or ""),
        "has_audio": bool(a),
        "bytes": int(fmt.get("size") or os.path.getsize(path)),
        "container": str(fmt.get("format_name") or ""),
    }


def reel_report(path: str) -> dict:
    """Can this go out as a reel, and if not, what exactly is wrong.

    `blocking` means Instagram will refuse it. `warnings` means it will publish
    but not reach the Reels tab, which is a choice the seller gets to make
    rather than an error we impose."""
    info = probe(path)
    if not info:
        return {"ok": True, "unknown": True, "blocking": [], "warnings": [],
                "fixable": False, "info": {},
                "note": "Could not inspect this clip, so it will be sent as it is."}

    blocking, warnings, fixable = [], [], False

    if info["bytes"] > REEL_MAX_BYTES:
        blocking.append(f"The file is {info['bytes'] / 1048576:.0f} MB. "
                        f"Instagram's limit is {REEL_MAX_BYTES // 1048576} MB.")
        fixable = True                      # re-encoding usually gets under it
    if info["duration"] and info["duration"] < REEL_MIN_SECONDS:
        blocking.append(f"It is {info['duration']:.1f} seconds long. "
                        f"Instagram needs at least {REEL_MIN_SECONDS}.")
    if info["duration"] > REEL_MAX_SECONDS:
        blocking.append(f"It is {info['duration'] / 60:.0f} minutes long, "
                        "past what Instagram accepts as a reel.")
    if info["vcodec"] and info["vcodec"] not in GOOD_VCODECS:
        blocking.append(f"The video is {info['vcodec'].upper()}. Instagram needs H.264.")
        fixable = True
    if "mp4" not in (info["container"] or "") and "mov" not in (info["container"] or ""):
        blocking.append("The file is not an MP4 or MOV.")
        fixable = True
    if info["has_audio"] and info["acodec"] not in GOOD_ACODECS:
        blocking.append(f"The sound is {info['acodec'].upper()}. Instagram needs AAC.")
        fixable = True

    ratio = (info["width"] / info["height"]) if info["height"] else 0
    if ratio and abs(ratio - 9 / 16) > 0.04:
        shape = "landscape" if ratio > 1 else "square" if abs(ratio - 1) < 0.1 else "an unusual shape"
        warnings.append(f"It is {shape} ({info['width']}x{info['height']}). It will still "
                        "post, but only 9:16 clips reach the Reels tab, which is where "
                        "the reach is.")
    if info["duration"] and not (REEL_TAB_MIN_SECONDS <= info["duration"] <= REEL_TAB_MAX_SECONDS):
        warnings.append(f"It is {info['duration']:.0f} seconds. The Reels tab shows "
                        f"{REEL_TAB_MIN_SECONDS}-{REEL_TAB_MAX_SECONDS} second clips.")

    return {"ok": not blocking, "unknown": False, "blocking": blocking,
            "warnings": warnings, "fixable": fixable and bool(blocking), "info": info}


def make_reel_ready(src: str, dst: str, timeout: int = 900) -> dict:
    """Re-encode into what Instagram accepts. Returns {ok, error?}.

    `+faststart` is the one that looks optional and is not: it moves the moov
    atom to the front of the file. Meta fetches the video with a ranged request
    and gives up when the metadata is at the end, which surfaces as "could not
    fetch the media" — a message that sends you looking at your server rather
    than at the file."""
    from backend.core.watermark import ffmpeg_exe
    exe = ffmpeg_exe()
    if not exe:
        return {"ok": False, "error": "ffmpeg is not available on this server."}
    info = probe(src)
    scale = []
    if info.get("width", 0) > 1080:
        scale = ["-vf", "scale=1080:-2"]
    cmd = [exe, "-y", "-v", "error", "-i", src,
           "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
           "-preset", "veryfast", "-crf", "23", *scale,
           "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
           "-movflags", "+faststart", dst]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Converting the clip took too long."}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:160]}
    if r.returncode != 0 or not os.path.exists(dst) or os.path.getsize(dst) == 0:
        return {"ok": False, "error": (r.stderr or "ffmpeg could not convert this clip.")[:200]}
    return {"ok": True, "bytes": os.path.getsize(dst)}
