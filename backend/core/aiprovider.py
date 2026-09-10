"""
One place that decides WHICH AI writes the text, and what it costs.

WHY THIS MODULE EXISTS
----------------------
Every AI call in this app used to construct `OpenAI()` directly. That hardcoded
one vendor, one price and one privacy posture into five different files. It also
meant the app was unusable for a seller until somebody put a paid OpenAI key in
the environment.

Almost every serious inference host now speaks the OpenAI chat-completions wire
format, so the only real differences between them are three strings: a base URL,
a model name and a key. Once those are data rather than code, the same call can
be served for free by Cloudflare, fast by Groq, or privately by OpenAI, and the
choice becomes an operations decision instead of a rewrite.

THE CHAIN
---------
Providers are tried in order and the first CONFIGURED one wins. If a call to it
fails, the next configured one is tried, and so on down to a deterministic
template that needs no network at all. A seller never sees an error because an
upstream had a bad minute.

  cloudflare  free 10,000 neurons/day. Llama 3.3 70B / 3.1 8B. Default.
  groq        free 1,000 req/day. Llama 3.3 70B. Fastest first token.
  gemini      free 1,500 req/day. NOTE: Google may train on free-tier requests.
  openai      paid. No training on API data. Reserved for seller data.
  template    always available, no network, no key. Deterministic copy.

SENSITIVITY
-----------
Calls are tagged with a `sensitivity`:

  "public"   product copy, captions, site text. Nothing here is private —
             it is literally written to be published. Free tiers are fine.
  "private"  anything derived from a seller's own sales, customers or revenue.
             Only providers marked `trains=False` may see it, so the free
             Gemini tier is skipped and OpenAI is preferred.

This distinction is the whole reason `sensitivity` is a required argument rather
than an optional flag. Getting it wrong leaks a seller's revenue into somebody
else's training set, and that is not a mistake you can take back, so the caller
is made to state it every time.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request

log = logging.getLogger("aiprovider")

TIMEOUT = 30
_STATS: dict[str, dict] = {}


# ---------------------------------------------------------------- providers

class Provider:
    """A chat-completions endpoint. Nothing vendor-specific beyond three strings."""

    def __init__(self, name: str, base_url: str, key_env: str, model: str,
                 trains: bool, free: bool, note: str = ""):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.key_env = key_env
        self.model = model
        self.trains = trains          # may the vendor train on what we send?
        self.free = free
        self.note = note

    def key(self) -> str:
        return (os.environ.get(self.key_env) or "").strip()

    def configured(self) -> bool:
        return bool(self.key()) and bool(self.base_url)

    def chat(self, system: str, user: str, max_tokens: int, temperature: float) -> str:
        body = json.dumps({
            "model": os.environ.get(f"{self.name.upper()}_MODEL") or self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=body,
            headers={"Authorization": f"Bearer {self.key()}",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            payload = json.loads(r.read().decode())
        return (payload["choices"][0]["message"]["content"] or "").strip()


def _cf_base() -> str:
    """Cloudflare's OpenAI-compatible route is account-scoped, so the URL is
    only knowable once the account id is in the environment."""
    acct = (os.environ.get("CF_ACCOUNT_ID") or "").strip()
    return f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/v1" if acct else ""


PROVIDERS: list[Provider] = [
    Provider("cloudflare", _cf_base(), "CF_API_TOKEN",
             "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
             trains=False, free=True, note="10,000 neurons/day free"),
    Provider("groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY",
             "llama-3.3-70b-versatile",
             trains=False, free=True, note="1,000 requests/day free"),
    Provider("gemini", "https://generativelanguage.googleapis.com/v1beta/openai",
             "GEMINI_API_KEY", "gemini-2.5-flash",
             trains=True, free=True, note="1,500 requests/day free — trains on free tier"),
    # Hugging Face, via their OpenAI-compatible router. Worth being honest in
    # the note: the old unlimited serverless Inference API is gone, and free
    # accounts now get a small monthly credit allowance rather than a real free
    # tier. It is wired up because it opens a very large model catalogue behind
    # one key, not because it is a way to avoid paying.
    Provider("huggingface", "https://router.huggingface.co/v1", "HF_API_TOKEN",
             os.environ.get("HF_TEXT_MODEL") or "Qwen/Qwen2.5-7B-Instruct",
             trains=False, free=False,
             note="credit-metered — small monthly allowance, then paid"),
    Provider("openai", os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1",
             "OPENAI_API_KEY", os.environ.get("OPENAI_TEXT_MODEL") or "gpt-4.1-mini",
             trains=False, free=False, note="paid — no training on API data"),
]


def _order(sensitivity: str) -> list[Provider]:
    """Providers to try, best first, filtered by what this text is allowed to touch."""
    usable = [p for p in PROVIDERS if p.configured()]
    if sensitivity == "private":
        usable = [p for p in usable if not p.trains]
        # A seller's own numbers are worth paying to keep out of a training set,
        # so for private work the paid provider goes first rather than last.
        usable.sort(key=lambda p: p.free)
    return usable


# ---------------------------------------------------------------- public API

def status() -> dict:
    """What the settings screen may know. Never a key."""
    out = []
    for p in PROVIDERS:
        out.append({"name": p.name, "configured": p.configured(), "free": p.free,
                    "model": p.model, "trains": p.trains, "note": p.note,
                    "calls": _STATS.get(p.name, {}).get("ok", 0),
                    "errors": _STATS.get(p.name, {}).get("err", 0)})
    live = [p for p in out if p["configured"]]
    return {"providers": out,
            "ready": bool(live),
            "free_ready": any(p["configured"] and p["free"] for p in out),
            "private_ready": any(p["configured"] and not p["trains"] for p in out),
            "active": live[0]["name"] if live else "template"}


def generate(system: str, user: str, *, sensitivity: str,
             max_tokens: int = 400, temperature: float = 0.7,
             fallback: str = "") -> dict:
    """Write some text. Returns {text, provider, free, error}.

    Never raises. A caller that cannot show text is worse than a caller that
    shows slightly duller text, so exhausting the chain returns `fallback`
    rather than an exception."""
    if sensitivity not in ("public", "private"):
        raise ValueError("sensitivity must be 'public' or 'private'")

    errors = []
    for p in _order(sensitivity):
        started = time.time()
        try:
            text = p.chat(system, user, max_tokens, temperature)
            if text:
                s = _STATS.setdefault(p.name, {"ok": 0, "err": 0, "ms": 0})
                s["ok"] += 1
                s["ms"] = int((time.time() - started) * 1000)
                return {"text": text, "provider": p.name, "free": p.free, "error": ""}
        except urllib.error.HTTPError as e:
            detail = e.read().decode()[:200] if hasattr(e, "read") else str(e)
            # 429 means we burned through a free daily allowance. That is the
            # expected steady state, not a fault, so fall through quietly.
            errors.append(f"{p.name}: {e.code} {detail}")
            _STATS.setdefault(p.name, {"ok": 0, "err": 0})["err"] += 1
        except Exception as e:                                   # noqa: BLE001
            errors.append(f"{p.name}: {e}")
            _STATS.setdefault(p.name, {"ok": 0, "err": 0})["err"] += 1

    if errors:
        log.warning("all AI providers failed: %s", " | ".join(errors))
    return {"text": fallback, "provider": "template", "free": True,
            "error": "; ".join(errors[-2:]) if errors else "no provider configured"}


# ---------------------------------------------------------------- vision

# Vision models per provider. These are NOT the text models — asking a
# text-only model to look at a picture returns a confident description of
# nothing, which is worse than an error because it looks like it worked.
HF_VISION_DEFAULT = "Qwen/Qwen3-VL-30B-A3B-Instruct"

VISION_MODELS = {
    "cloudflare": os.environ.get("CF_VISION_MODEL")
                  or "@cf/meta/llama-3.2-11b-vision-instruct",
    "gemini": os.environ.get("GEMINI_VISION_MODEL") or "gemini-2.5-flash",
    # Groq does have usable vision on the free tier now (the older
    # llama-3.2-*-vision ids are dead; the Qwen VL line replaced them). It is
    # the fastest of the free options, so it earns a place in the chain.
    "groq": os.environ.get("GROQ_VISION_MODEL") or "qwen/qwen3.6-27b",
    "huggingface": os.environ.get("HF_VISION_MODEL") or HF_VISION_DEFAULT,
    "openai": "gpt-4.1-mini",
}

# Which provider to ASK FIRST for a picture, regardless of the text order.
#
# Vision is not text: the job here is a long, structured, art-direction reading,
# and the providers differ far more at that than they do at writing a caption.
# Gemini will write six hundred words of real detail; the smaller free vision
# models tend to stop after two lines however hard the prompt pushes, which is
# exactly the "reading is too shallow" problem. So vision gets its own order
# rather than inheriting the text chain's.
# Gemini first for READING pictures. This is not the same judgement as which
# engine should DRAW them: describing a brand's photography well means writing
# six hundred words of genuine art direction, and the models differ far more at
# that than at anything else in this app. Gemini does it best and its free tier
# is generous enough to carry the whole feature.
#
# Hugging Face dropped down the list once its credit allowance proved to be
# about $0.10 a month — enough to prove the wiring works, not enough to run on.
VISION_PREFERENCE = ["gemini", "openai", "groq", "cloudflare", "huggingface"]


def _vision_order(sensitivity: str) -> list[Provider]:
    usable = [p for p in _order(sensitivity) if p.name in VISION_MODELS]
    # Private work keeps _order's own ranking: it has already dropped every
    # provider that trains on its input and put the paid one first, and a
    # preference for prettier prose is not a reason to disturb that.
    if sensitivity == "private":
        return usable
    rank = {n: i for i, n in enumerate(VISION_PREFERENCE)}
    return sorted(usable, key=lambda p: rank.get(p.name, 99))


def describe_image(image_bytes: bytes, content_type: str, *, system: str,
                   user: str, sensitivity: str = "public",
                   max_tokens: int = 500) -> dict:
    """Look at a picture and write about it.

    The image is sent inline as a base64 data URL rather than as a link.
    Uploaded media lives in a private bucket, so a public URL either does not
    exist or would mean making a seller's product photos world-readable to
    describe them. Inline costs more tokens and is the only correct option.

    Returns {text, provider, error} and never raises, on the same principle as
    generate(): a missing description degrades the prompt, it should not break
    the upload the seller just made."""
    import base64
    if not image_bytes:
        return {"text": "", "provider": "", "error": "no image"}

    b64 = base64.b64encode(image_bytes).decode()
    data_url = f"data:{content_type or 'image/jpeg'};base64,{b64}"
    errors = []

    for p in _vision_order(sensitivity):
        body = json.dumps({
            "model": VISION_MODELS[p.name],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": [
                    {"type": "text", "text": user},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ]},
            ],
            "max_tokens": max_tokens,
        }).encode()
        req = urllib.request.Request(
            f"{p.base_url}/chat/completions", data=body,
            headers={"Authorization": f"Bearer {p.key()}",
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                payload = json.loads(r.read().decode())
            text = (payload["choices"][0]["message"]["content"] or "").strip()
            if text:
                _STATS.setdefault(p.name, {"ok": 0, "err": 0})["ok"] += 1
                return {"text": text, "provider": p.name, "error": ""}
        except Exception as e:                                   # noqa: BLE001
            errors.append(f"{p.name}: {e}")
            _STATS.setdefault(p.name, {"ok": 0, "err": 0})["err"] += 1

    if errors:
        log.warning("vision failed: %s", " | ".join(errors))
    return {"text": "", "provider": "",
            "error": "; ".join(errors[-2:]) if errors
                     else "no vision-capable provider configured"}


def vision_ready(sensitivity: str = "public") -> bool:
    return bool(_vision_order(sensitivity))


# ---------------------------------------------------------------- images

CF_IMAGE_MODEL = os.environ.get("CF_IMAGE_MODEL") or "@cf/black-forest-labs/flux-1-schnell"


def image_ready() -> bool:
    return bool((os.environ.get("CF_ACCOUNT_ID") or "").strip()
                and (os.environ.get("CF_API_TOKEN") or "").strip())


def _cf_run(model: str, payload: dict, timeout: int = 90) -> dict | None:
    """POST to a Cloudflare Workers AI model and return the parsed body."""
    if not image_ready():
        return None
    acct = os.environ["CF_ACCOUNT_ID"].strip()
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{model}",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {os.environ['CF_API_TOKEN'].strip()}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
    except Exception as e:                                       # noqa: BLE001
        log.warning("cloudflare %s failed: %s", model, e)
        return None
    # Some image models return raw bytes rather than JSON.
    if raw[:1] not in (b"{", b"["):
        return {"_raw": raw}
    try:
        return json.loads(raw.decode())
    except Exception:                                            # noqa: BLE001
        return {"_raw": raw}


def _image_bytes(payload: dict | None) -> bytes | None:
    if not payload:
        return None
    if payload.get("_raw"):
        return payload["_raw"]
    import base64
    result = payload.get("result") or {}
    b64 = result.get("image") or (result.get("images") or [None])[0]
    if not b64:
        return None
    try:
        return base64.b64decode(b64)
    except Exception:                                            # noqa: BLE001
        return None


def generate_image(prompt: str, steps: int = 4) -> bytes | None:
    """Flux Schnell, text to image. ~19 neurons per 1024x1024, so the free
    10,000/day works out to roughly 500 images a day at no cost.

    Returns raw bytes, or None. Callers must treat None as "no image today" and
    still produce the post — an Instagram caption without a picture is worth
    more than an error page."""
    return _image_bytes(_cf_run(
        CF_IMAGE_MODEL,
        {"prompt": prompt[:2000], "steps": max(1, min(8, steps))}, timeout=60))


CF_IMG2IMG_MODEL = (os.environ.get("CF_IMG2IMG_MODEL")
                    or "@cf/runwayml/stable-diffusion-v1-5-img2img")

# How far the output may drift from the seller's own photograph.
#
# This number decides whether the picture still shows the product that ships.
# At 0.35 the shape, colour and pattern survive and the lighting and setting
# change; by 0.7 the model has effectively redrawn the item and the embroidery,
# stones and hardware are its invention rather than the seller's.
#
# It is capped rather than merely defaulted, because a seller dragging a slider
# to "more creative" is not consenting to misrepresenting their own stock to
# customers — they are just trying to get a nicer picture.
STRENGTH_DEFAULT = 0.35
STRENGTH_MAX = 0.55


def restyle_image(source: bytes, prompt: str, strength: float | None = None,
                  negative: str = "") -> bytes | None:
    """Re-shoot the seller's own photograph: same product, new setting.

    This is image-to-image, not generation. The source photo is the starting
    point, so the thing in the output is the thing in the input — which is the
    whole difference between a picture a seller can honestly post and one that
    shows a product they do not sell."""
    if not source:
        return None
    import base64
    st = STRENGTH_DEFAULT if strength is None else float(strength)
    st = max(0.05, min(STRENGTH_MAX, st))
    payload = {
        "prompt": prompt[:2000],
        "image_b64": base64.b64encode(source).decode(),
        "strength": st,
        "num_steps": 20,
        "guidance": 7.5,
    }
    if negative:
        payload["negative_prompt"] = negative[:500]
    return _image_bytes(_cf_run(CF_IMG2IMG_MODEL, payload))


# ----------------------------------------------------- Hugging Face imagery
#
# The seller asked for Hugging Face and nothing else, so this is the primary
# path for drawing and for video. Three things about it are worth knowing
# before reading the code, because they shaped it:
#
#   1. There is NO `/v1/images/generations` on the HF router. Its OpenAI-shaped
#      surface is chat-only. Images and video are routed per-provider, and the
#      provider's own model slug is not the Hub repo id — the mapping lives in
#      HF's API. Hand-rolling those URLs breaks whenever HF re-routes a model,
#      so this goes through huggingface_hub's InferenceClient, which resolves
#      the provider, submits the job and polls it.
#
#   2. Video is a QUEUE job on fal-ai, not a request. It takes around a minute,
#      which is longer than a web request should ever block for — so the caller
#      runs it in the background and the seller is told to come back.
#
#   3. It is NOT free, and the code says so out loud rather than letting a
#      seller discover it. See HF_COSTS below.
HF_IMAGE_MODEL = (os.environ.get("HF_IMAGE_MODEL")
                  or "black-forest-labs/FLUX.1-schnell")
# Instruction-edit models condition on the source image instead of redrawing
# it, which is the whole requirement for a re-shoot: the wallet has to stay
# the wallet. Qwen-Image-Edit holds identity best of the served set.
HF_EDIT_MODEL = (os.environ.get("HF_EDIT_MODEL")
                 or "Qwen/Qwen-Image-Edit-2511")
HF_VIDEO_MODEL = (os.environ.get("HF_VIDEO_MODEL")
                  or "Wan-AI/Wan2.2-I2V-A14B")

# Roughly what each call costs, so the app can warn honestly instead of
# letting a seller find out from a bill. Figures are provider pass-through
# rates; HF adds no markup. A free account gets about $0.10 of credit a month
# and PRO about $2.00 — which is why video is gated behind an explicit opt-in.
HF_COSTS = {"vision": 0.002, "image": 0.003, "edit": 0.025, "video": 0.20}


def hf_ready() -> bool:
    return bool((os.environ.get("HF_API_TOKEN") or "").strip())


def _hf_client():
    """An InferenceClient, or None when the token or the library is missing.

    huggingface_hub is imported lazily: it is only needed by sellers who have
    actually connected Hugging Face, and a missing optional dependency must
    degrade one feature rather than stop the app importing."""
    token = (os.environ.get("HF_API_TOKEN") or "").strip()
    if not token:
        return None
    try:
        from huggingface_hub import InferenceClient
        return InferenceClient(api_key=token)
    except Exception as e:  # noqa: BLE001
        log.warning("huggingface_hub unavailable: %s", e)
        return None


def hf_image(prompt: str, reference: bytes | None = None) -> bytes | None:
    """One picture from Hugging Face — drawn, or the seller's own photo edited.

    With a reference this is an instruction EDIT, not a generation: the source
    image conditions the model, so the product in the output is the product in
    the input. Without one it is plain text-to-image on a cheaper model.

    Returns raw image bytes, or None so the caller falls through to whatever
    engine is next. Never raises."""
    client = _hf_client()
    if not client or not prompt:
        return None
    try:
        if reference:
            img = client.image_to_image(reference, prompt=prompt[:2000],
                                        model=HF_EDIT_MODEL)
        else:
            img = client.text_to_image(prompt[:2000], model=HF_IMAGE_MODEL)
        out = _pil_to_png(img)
        if out:
            _STATS.setdefault("huggingface", {"ok": 0, "err": 0})["ok"] += 1
        return out
    except Exception as e:  # noqa: BLE001 — caller falls through
        _STATS.setdefault("huggingface", {"ok": 0, "err": 0})["err"] += 1
        log.warning("hf image failed (%s): %s",
                    HF_EDIT_MODEL if reference else HF_IMAGE_MODEL, e)
        return None


def hf_video(image: bytes, prompt: str = "", frames: int = 81) -> bytes | None:
    """A short clip from the seller's own product photo.

    Image-to-video, not text-to-video, and deliberately so: the point is that
    the thing moving on screen is the thing that ships. About a minute per
    call, roughly five seconds of 480p out.

    Honest about its limits, because they matter to whoever ships this: the
    model animates the input frame, so identity holds for the first couple of
    seconds and then texture and any lettering start to drift. It is right for
    a slow push-in or a fabric ripple, and wrong for anything with real
    motion.

    Returns MP4 bytes, or None. Never raises."""
    client = _hf_client()
    if not client or not image:
        return None
    try:
        video = client.image_to_video(
            image, model=HF_VIDEO_MODEL,
            prompt=(prompt or "slow gentle push-in, steady shot, soft light")[:1000])
        data = video if isinstance(video, (bytes, bytearray)) else None
        if data:
            _STATS.setdefault("huggingface", {"ok": 0, "err": 0})["ok"] += 1
            return bytes(data)
        log.warning("hf video returned no bytes (%s)", type(video).__name__)
    except Exception as e:  # noqa: BLE001
        _STATS.setdefault("huggingface", {"ok": 0, "err": 0})["err"] += 1
        log.warning("hf video failed (%s): %s", HF_VIDEO_MODEL, e)
    return None


def _pil_to_png(img) -> bytes | None:
    """InferenceClient hands back a PIL image; media.save wants bytes."""
    if img is None:
        return None
    if isinstance(img, (bytes, bytearray)):
        return bytes(img)
    try:
        import io as _io
        buf = _io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:  # noqa: BLE001
        log.warning("could not encode the returned image: %s", e)
        return None


# --------------------------------------------------------- Gemini imagery
#
# WHY THIS IS HERE: the whole value of "Re-shoot my photo" is that the wallet in
# the output is the wallet that ships. Stable Diffusion 1.5 img2img — the only
# image-to-image model on the Cloudflare free tier — is a 2022 model, and at any
# strength high enough to change the setting it also redraws the hardware, the
# stitching and any brand marking. Gemini's image models were built for exactly
# this: hand them the reference and they keep the object's identity, including
# lettering, while changing everything around it.
#
# It also takes the SAME key as the text provider, so a seller who has already
# set GEMINI_API_KEY gets the better path with no extra setup.
GEMINI_IMAGE_MODEL = (os.environ.get("GEMINI_IMAGE_MODEL")
                      or "gemini-2.5-flash-image")
_GEMINI_IMAGE_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


# Veo, through the Gemini API. A different shape from every other call in this
# file: it is a long-running operation, so you POST once, get an operation name
# back, and poll until a file URI appears. Model id is env-overridable because
# Google renames and retires these faster than anything else here.
GEMINI_VIDEO_MODEL = (os.environ.get("GEMINI_VIDEO_MODEL")
                      or "veo-3.0-fast-generate-preview")
GEMINI_VIDEO_POLL_SECONDS = int(os.environ.get("GEMINI_VIDEO_POLL_SECONDS") or 240)
_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"


def gemini_video_ready() -> bool:
    """A key is present. NOT a promise that this key has Veo access.

    Veo is gated to paid accounts and its availability varies by region and by
    preview cohort, and there is no cheap way to ask in advance. So this is
    optimistic on purpose, and generate_video() reports the refusal in the
    seller's own words if the account cannot in fact use it — which is better
    than hiding the option from someone whose key does work.
    """
    return bool((os.environ.get("GEMINI_API_KEY") or "").strip())


def gemini_video(image: bytes, prompt: str,
                 content_type: str = "image/jpeg") -> bytes | None:
    """One short clip, animated FROM the seller's own photograph.

    Image-to-video for the same reason the still path prefers a re-shoot: a
    text-to-video model invents a product, and a clip of a wallet the seller
    does not sell is worse than no clip.

    Never raises. Returns raw mp4 bytes, or None with the reason logged.
    """
    key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not key or not image or not prompt:
        return None
    import base64
    import time as _time

    body = json.dumps({
        "instances": [{
            "prompt": prompt[:2000],
            "image": {"bytesBase64Encoded": base64.b64encode(image).decode(),
                      "mimeType": content_type or "image/jpeg"},
        }],
        "parameters": {"aspectRatio": "9:16"},
    }).encode()
    start = f"{_GEMINI_BASE}/models/{GEMINI_VIDEO_MODEL}:predictLongRunning?key={key}"
    try:
        req = urllib.request.Request(start, data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as r:
            op = json.loads(r.read().decode())
        name = op.get("name")
        if not name:
            log.warning("gemini video: no operation name in response")
            return None

        deadline = _time.time() + GEMINI_VIDEO_POLL_SECONDS
        uri = ""
        while _time.time() < deadline:
            _time.sleep(10)
            with urllib.request.urlopen(
                    f"{_GEMINI_BASE}/{name}?key={key}", timeout=60) as r:
                st = json.loads(r.read().decode())
            if st.get("error"):
                log.warning("gemini video failed: %s", st["error"])
                return None
            if not st.get("done"):
                continue
            resp = st.get("response") or {}
            for vid in (resp.get("generatedVideos")
                        or resp.get("generated_videos") or []):
                v = vid.get("video") or {}
                uri = v.get("uri") or v.get("fileUri") or ""
                if uri:
                    break
            break
        if not uri:
            log.warning("gemini video: timed out or returned no file")
            return None

        sep = "&" if "?" in uri else "?"
        with urllib.request.urlopen(f"{uri}{sep}key={key}", timeout=180) as r:
            data = r.read()
        if data:
            _STATS.setdefault("gemini", {"ok": 0, "err": 0})["ok"] += 1
            return data
    except Exception as e:  # noqa: BLE001 — reported to the seller by the caller
        _STATS.setdefault("gemini", {"ok": 0, "err": 0})["err"] += 1
        log.warning("gemini video failed: %s", e)
    return None


def gemini_image_ready() -> bool:
    return bool((os.environ.get("GEMINI_API_KEY") or "").strip())


def gemini_image(prompt: str, reference: bytes | None = None,
                 content_type: str = "image/jpeg") -> bytes | None:
    """One picture from Gemini — text-to-image, or reference-preserving edit.

    Passing `reference` is what makes this an edit rather than an invention:
    the image goes in alongside the prompt and the model is asked to keep the
    product and change the setting. Returns raw image bytes, or None so the
    caller can fall through to the next engine exactly as it already does.
    Never raises — an image failure must not break the request that asked for
    it."""
    key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not key or not prompt:
        return None
    import base64
    parts: list[dict] = [{"text": prompt[:4000]}]
    if reference:
        parts.append({"inline_data": {
            "mime_type": content_type or "image/jpeg",
            "data": base64.b64encode(reference).decode()}})
    body = json.dumps({"contents": [{"parts": parts}]}).encode()
    url = f"{_GEMINI_IMAGE_BASE}/{GEMINI_IMAGE_MODEL}:generateContent?key={key}"
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            payload = json.loads(r.read().decode())
        for cand in payload.get("candidates") or []:
            for part in (cand.get("content") or {}).get("parts") or []:
                # The API has used both spellings over its life; accept either
                # rather than silently returning None on a working response.
                blob = part.get("inline_data") or part.get("inlineData")
                if blob and blob.get("data"):
                    _STATS.setdefault("gemini", {"ok": 0, "err": 0})["ok"] += 1
                    return base64.b64decode(blob["data"])
        log.warning("gemini image returned no image part")
    except Exception as e:  # noqa: BLE001 — caller falls through to the next engine
        _STATS.setdefault("gemini", {"ok": 0, "err": 0})["err"] += 1
        log.warning("gemini image failed: %s", e)
    return None
