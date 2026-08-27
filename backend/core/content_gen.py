"""
Content creator for a small social-media seller.

Generates a suggested post (caption, hashtags, description, image, platform)
that surfaces in the Smart Approval panel. The seller can Approve to post
immediately, or open Details, edit anything, and either post or schedule.

Two engines, picked automatically:
  * If OPENAI_API_KEY is set, we call OpenAI:
      - chat completion for caption + hashtags + description
      - images.generate (DALL-E) for a matching image
    The image URL is temporary, so we download it and save under
    data/generated_images/<uuid>.png, then serve it publicly via the
    /generated_images/<uuid>.png static route so Instagram's Graph API
    can fetch it.
  * If OPENAI_API_KEY is not set, we return a template-based suggestion so
    the whole UI still works end-to-end for demo/dev.

Every suggestion carries a stable id starting with "content_" so the
frontend and the Approval panel can route it correctly.
"""
from __future__ import annotations

import os
import secrets
import time
import uuid
from typing import Any

import requests

from backend.core import product_config, user_store

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
IMG_DIR = os.path.join(DATA_DIR, "generated_images")
os.makedirs(IMG_DIR, exist_ok=True)


# ---------------------------------------------------------
# Public helpers
# ---------------------------------------------------------
def is_openai_available() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


# Simple bank of "trending" topics per product type — a stand-in for real
# social-listening; each topic biases the AI (or template) toward one angle.
_TOPIC_BANK: dict[str, list[str]] = {
    "jewellery": [
        "Everyday minimalist gold pieces trending on Instagram this week",
        "Statement earrings that are going viral in wedding-season reels",
        "Silver stackable rings — the aesthetic trend blowing up right now",
        "Traditional Kundan pieces getting modern styling on trending reels",
    ],
    "clothes": [
        "Oversized fits taking over the summer feed",
        "Co-ord sets that are trending across creator reels this week",
        "Handloom + street styling — the fusion look going viral",
        "Monochrome outfits — the aesthetic trend right now",
    ],
    "perfumes": [
        "Long-lasting summer fragrances everyone's talking about",
        "Vanilla-based scents trending in fragrance reels this week",
        "Signature-scent Instagram content that's going viral",
        "Layering perfumes — the trend blowing up right now",
    ],
    "generic": [
        "This week's trending product-content angle for small brands",
        "The aesthetic reel format your audience is watching right now",
    ],
}


def suggest_topic(product_type: str | None) -> str:
    pt = product_config.normalize(product_type)
    topics = _TOPIC_BANK.get(pt) or _TOPIC_BANK["generic"]
    # deterministic-ish rotation by day so a returning seller sees fresh ideas
    idx = int(time.time() // 3600) % len(topics)
    return topics[idx]


def generate_suggestion(email: str, product_type: str | None = None,
                        topic: str | None = None, platform: str = "instagram",
                        with_image: bool = True) -> dict:
    """Return a ready-to-review post: {id, topic, platform, caption, hashtags,
    description, image_url, engine}."""
    pt = product_config.normalize(product_type)
    topic = topic or suggest_topic(pt)
    engine = "openai" if is_openai_available() else "template"

    if engine == "openai":
        try:
            copy = _openai_copy(pt, topic)
            image_url = _openai_image(pt, topic) if with_image else None
        except Exception as e:
            # never fail the whole call — fall back so the panel keeps working
            copy = _template_copy(pt, topic)
            image_url = None
            engine = f"template (openai_error: {str(e)[:80]})"
    else:
        copy = _template_copy(pt, topic)
        image_url = None

    return {
        "id": f"content_{secrets.token_hex(4)}",
        "topic": topic,
        "platform": platform,
        "product_type": pt,
        "caption": copy["caption"],
        "hashtags": copy["hashtags"],
        "description": copy["description"],
        "image_url": image_url,
        "engine": engine,
        "created_at": _now_iso(),
    }


# ---------------------------------------------------------
# OpenAI engines
# ---------------------------------------------------------
def _openai_copy(product_type: str, topic: str) -> dict:
    import json
    from openai import OpenAI
    client = OpenAI()
    system = ("You write short, conversion-friendly Instagram posts for small "
              "product sellers. Voice: warm, confident, human, never salesy. "
              "Return ONLY JSON with keys caption (<=220 chars), hashtags "
              "(list of 10-15 lowercase strings without #), description "
              "(1-2 sentence Product Description).")
    user = (f"Product type: {product_type}. Trend / topic to lean on: {topic}. "
            f"Write one Instagram post.")
    resp = client.chat.completions.create(
        model=os.environ.get("OPENAI_TEXT_MODEL", "gpt-4o-mini"),
        temperature=0.8,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
    )
    data = json.loads(resp.choices[0].message.content)
    tags = data.get("hashtags") or []
    if isinstance(tags, str):
        tags = [t.strip().lstrip("#") for t in tags.split() if t.strip()]
    return {
        "caption": str(data.get("caption", "")).strip()[:2100],
        "hashtags": [str(t).strip().lstrip("#").lower() for t in tags if str(t).strip()][:20],
        "description": str(data.get("description", "")).strip(),
    }


def _openai_image(product_type: str, topic: str) -> str | None:
    """Generate an image with OpenAI and save it locally so it survives past
    the temporary URL Meta would otherwise fail to fetch."""
    from openai import OpenAI
    client = OpenAI()
    style = {
        "jewellery": "clean minimal studio photograph, soft warm lighting, marble backdrop",
        "clothes":   "flat-lay lifestyle photograph, natural sunlight, neutral linen backdrop",
        "perfumes":  "moody product photograph, soft rim light, dark stone surface",
    }.get(product_type, "clean minimal product photograph, natural lighting, neutral backdrop")
    prompt = (f"Instagram-ready {product_type} product photograph. Topic: {topic}. "
              f"Style: {style}. Bright, aspirational, on-trend. No text, no watermark.")
    r = client.images.generate(
        model=os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1"),
        prompt=prompt, size="1024x1024", n=1,
    )
    # gpt-image-1 returns b64_json by default; dall-e-3 returns url.
    item = r.data[0]
    if getattr(item, "b64_json", None):
        import base64
        content = base64.b64decode(item.b64_json)
    elif getattr(item, "url", None):
        content = requests.get(item.url, timeout=30).content
    else:
        return None
    fname = f"{uuid.uuid4().hex}.png"
    with open(os.path.join(IMG_DIR, fname), "wb") as f:
        f.write(content)
    return f"/generated_images/{fname}"


# ---------------------------------------------------------
# Template fallback (no OpenAI needed)
# ---------------------------------------------------------
def _template_copy(product_type: str, topic: str) -> dict:
    tag_bank = {
        "jewellery": ["jewellery", "handmadejewellery", "instajewellery", "silverjewellery",
                      "goldjewellery", "kundan", "everydayjewellery", "smallbusiness",
                      "supportsmall", "shopsmall", "indianjewellery", "instaindia"],
        "clothes": ["ootd", "instafashion", "streetstyle", "sustainablefashion",
                    "handloom", "coordset", "instalook", "smallbusiness",
                    "shopsmall", "indianfashion", "wearithow"],
        "perfumes": ["perfume", "fragrance", "perfumelover", "eaudeparfum", "scentoftheday",
                     "instaparfum", "longlasting", "signaturescent", "smallbusiness"],
        "generic": ["smallbusiness", "supportsmall", "shopsmall", "instabrand", "newpost",
                    "trending", "shoppingtime"],
    }.get(product_type, ["smallbusiness", "supportsmall", "shopsmall", "trending"])
    caption = (f"✨ {topic}\n\n"
               f"Pick your favourite piece before it's gone — a small drop, made with care. "
               f"Comment your favourite emoji below 👇")
    description = (f"On-trend {product_type} piece, made in a small batch. "
                   f"Perfect for anyone loving this week's aesthetic.")
    return {"caption": caption, "hashtags": tag_bank, "description": description}


# ---------------------------------------------------------
# Scheduling
# ---------------------------------------------------------
_SCH_KEY = "scheduled_posts"


def schedule_post(email: str, post: dict, at_iso: str) -> dict:
    """Save a post to publish at `at_iso`. Returns the stored entry (with id)."""
    entry = {"id": secrets.token_hex(8), "post": post, "at": at_iso,
             "status": "pending", "created_at": _now_iso()}
    lst = user_store.get_key(email, _SCH_KEY, []) or []
    lst.append(entry)
    user_store.set_key(email, _SCH_KEY, lst)
    return entry


def list_scheduled(email: str) -> list[dict]:
    lst = user_store.get_key(email, _SCH_KEY, []) or []
    # newest first
    return sorted(lst, key=lambda e: e.get("at") or "", reverse=True)


def delete_scheduled(email: str, entry_id: str) -> list[dict]:
    lst = user_store.get_key(email, _SCH_KEY, []) or []
    lst = [e for e in lst if e.get("id") != entry_id]
    user_store.set_key(email, _SCH_KEY, lst)
    return lst


def run_due_posts(base_public_url: str = "") -> list[dict]:
    """Iterate every account with scheduled posts and publish those whose
    `at` has passed. Returns a summary list. Designed to be called by a
    cron/background scheduler; a fresh call at any time is safe."""
    import pandas as pd
    from backend.core import auth as _auth, instagram as _ig
    now = pd.Timestamp.now()
    fired = []
    users = _auth.load_users()
    for email in users:
        lst = user_store.get_key(email, _SCH_KEY, []) or []
        changed = False
        for e in lst:
            if e.get("status") != "pending":
                continue
            try:
                due = pd.Timestamp(e.get("at")) <= now
            except Exception:
                continue
            if not due:
                continue
            post = e.get("post") or {}
            image_url = post.get("image_url") or ""
            if image_url.startswith("/") and base_public_url:
                image_url = base_public_url.rstrip("/") + image_url
            caption = _compose_caption(post)
            try:
                result = _ig.post_image(email, image_url, caption)
            except Exception as ex:
                result = {"ok": False, "error": str(ex)}
            e["status"] = "posted" if result.get("ok") else "failed"
            e["result"] = result
            e["fired_at"] = _now_iso()
            fired.append({"email": email, "id": e["id"], "ok": bool(result.get("ok"))})
            changed = True
        if changed:
            user_store.set_key(email, _SCH_KEY, lst)
    return fired


def _compose_caption(post: dict) -> str:
    caption = str(post.get("caption") or "").strip()
    tags = post.get("hashtags") or []
    if tags:
        caption = caption + "\n\n" + " ".join("#" + str(t).strip().lstrip("#") for t in tags)
    return caption


def _now_iso() -> str:
    import pandas as pd
    return pd.Timestamp.now().isoformat(timespec="seconds")
