"""
One picture per Marketing Campaign.

A discount on WhatsApp with nothing to look at is easy to scroll past; the same
offer with a picture of the shop's kind of product is the thing that gets
opened. So every campaign carries one image, drawn by OpenAI, or the seller's
own upload when that is not possible.

THE ALLOWANCE
-------------
* A seller PAYING for Pro Max draws from the same monthly picture allowance as
  everything else in the app (aicaps), so this is not a second door around it.
* Everyone else — the free trial included — gets CAMPAIGN_IMAGES_PER_MONTH
  campaign pictures a calendar month, however many campaigns they run. Enough
  for the two automatic campaigns a month (see winback_auto: every second
  Monday) to arrive with a picture.

When the allowance is used, OpenAI has no key, has run out of credit, or simply
fails, nothing breaks: the campaign comes back with `needs_upload` and the
reason, and the screen asks for a photo instead. A seller's own product photo
is often the better picture anyway.
"""
from __future__ import annotations

import base64
import logging
import os
import uuid
from datetime import datetime

from backend.core import user_store

log = logging.getLogger("campaign_image")

KEY = "campaign_images"
CAMPAIGN_IMAGES_PER_MONTH = 2
MAX_UPLOAD = 8 * 1024 * 1024
OK_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


class NeedsUpload(Exception):
    """No picture could be drawn; the reason is safe to show the seller."""


def _month() -> str:
    return datetime.now().strftime("%Y-%m")


def paid_promax(email: str) -> bool:
    try:
        from backend.core import billing
        return billing.paid_active(email) and billing.get_plan(email) == "promax"
    except Exception:  # noqa: BLE001
        return False


def _usage(email: str) -> dict:
    st = user_store.get_key(email, KEY, {}) or {}
    if not isinstance(st, dict) or st.get("month") != _month():
        st = {"month": _month(), "used": 0}
    return st


def allowance(email: str) -> dict:
    """What this seller has left this month, for the screen."""
    if paid_promax(email):
        try:
            from backend.core import aicaps
            s = aicaps.image_month_status(email)
            return {"plan": "promax", "cap": s.get("cap"), "used": s.get("used"),
                    "left": s.get("left"), "shared": True}
        except Exception:  # noqa: BLE001
            return {"plan": "promax", "cap": None, "used": 0, "left": None, "shared": True}
    st = _usage(email)
    return {"plan": "other", "cap": CAMPAIGN_IMAGES_PER_MONTH, "used": st["used"],
            "left": max(0, CAMPAIGN_IMAGES_PER_MONTH - st["used"]), "shared": False}


def _check(email: str) -> None:
    if paid_promax(email):
        from backend.core import aicaps
        try:
            aicaps.check_image_month(email)
        except aicaps.CapReached as e:
            raise NeedsUpload(str(e))
        return
    if _usage(email)["used"] >= CAMPAIGN_IMAGES_PER_MONTH:
        raise NeedsUpload(f"You have used this month's {CAMPAIGN_IMAGES_PER_MONTH} campaign "
                          f"pictures. Add a photo of your own for this one (a real photo of "
                          f"your product usually works best). It resets on the 1st.")


def _consume(email: str) -> None:
    if paid_promax(email):
        from backend.core import aicaps
        aicaps.consume_image_month(email)
        return
    st = _usage(email)
    st["used"] = int(st.get("used") or 0) + 1
    user_store.set_key(email, KEY, st)


def _openai_key(email: str) -> str:
    try:
        from backend.core import account
        own = account.ai_key(email, "openai")
        if own:
            return own
    except Exception:  # noqa: BLE001
        pass
    return (os.environ.get("OPENAI_API_KEY") or "").strip()


def prompt_for(ctx: dict) -> str:
    sells = ctx.get("sells") or "products"
    occasion = ctx.get("occasion") if ctx.get("reason") == "festival" else ""
    mood = (f"festive {occasion} mood, warm celebratory lights and tasteful festive decor"
            if occasion else "warm, welcoming, inviting mood")
    headline = ctx.get("offer_short") or ""
    text_rule = (f'Include one short headline in clean bold sans-serif type: "{headline}". '
                 f"Spell it exactly. No other text."
                 if headline else "No text, no letters, no watermark.")
    return (f"A premium marketing image for a small online shop that sells {sells}. "
            f"Show an appealing styled arrangement of {sells} as the hero, "
            f"{mood}, soft natural light, rich colour, lots of clean space, "
            f"square composition for WhatsApp and Instagram. {text_rule} "
            f"No logos, no people's faces, no brand names.")


def generate(email: str, ctx: dict) -> dict:
    """Draw the campaign picture. Returns {url, source, prompt}; raises
    NeedsUpload with a seller-readable reason when it cannot."""
    _check(email)
    key = _openai_key(email)
    if not key:
        raise NeedsUpload("AI pictures are not switched on for this account yet. "
                          "Add a photo of your own for this campaign.")
    prompt = prompt_for(ctx)
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, timeout=90)
        kwargs = {"model": os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1"),
                  "prompt": prompt, "size": "1024x1024", "n": 1}
        if kwargs["model"].startswith("gpt-image"):
            kwargs["quality"] = os.environ.get("CAMPAIGN_IMAGE_QUALITY", "medium")
        r = client.images.generate(**kwargs)
        item = r.data[0]
        if getattr(item, "b64_json", None):
            content = base64.b64decode(item.b64_json)
        elif getattr(item, "url", None):
            import requests
            content = requests.get(item.url, timeout=30).content
        else:
            raise RuntimeError("no image in the response")
    except Exception as e:  # noqa: BLE001 — quota, billing, network, policy
        msg = str(e).lower()
        log.warning("campaign image failed for %s: %s", email, e)
        if "quota" in msg or "billing" in msg or "insufficient" in msg or "429" in msg:
            raise NeedsUpload("The AI picture service has run out of credit for now. "
                              "Add a photo of your own for this campaign.")
        raise NeedsUpload("The AI picture could not be made just now. "
                          "Add a photo of your own for this campaign, or try again later.")
    from backend.core import media
    url = media.save(f"campaign_{uuid.uuid4().hex}.png", content, email=email).get("url")
    if not url:
        raise NeedsUpload("The picture was made but could not be saved. Please add one of your own.")
    _consume(email)
    return {"url": url, "source": "ai", "prompt": prompt}


def save_upload(email: str, data: bytes, content_type: str) -> dict:
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct not in OK_TYPES:
        raise ValueError("Use a PNG, JPG or WEBP picture.")
    if not data:
        raise ValueError("That file is empty.")
    if len(data) > MAX_UPLOAD:
        raise ValueError("That picture is over 8 MB. Use a smaller one.")
    from backend.core import media
    url = media.save(f"campaign_{uuid.uuid4().hex}.{OK_TYPES[ct]}", data, email=email).get("url")
    if not url:
        raise ValueError("The picture could not be saved. Please try again.")
    return {"url": url, "source": "upload"}
