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
