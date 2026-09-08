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
VISION_MODELS = {
    "cloudflare": "@cf/meta/llama-3.2-11b-vision-instruct",
    "gemini": "gemini-2.5-flash",
    "openai": "gpt-4.1-mini",
    # Groq's free tier has no vision model we can rely on, so it is skipped
    # rather than sent a request it will refuse.
}


def _vision_order(sensitivity: str) -> list[Provider]:
    return [p for p in _order(sensitivity) if p.name in VISION_MODELS]


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
