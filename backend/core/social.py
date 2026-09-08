"""
Social Media Manager — planning, writing and scheduling, for a seller with
twenty minutes a week and no marketing training.

THE FINDING THAT SHAPES EVERYTHING HERE
---------------------------------------
Liadeli, Sotgiu & Verlegh (Journal of Marketing, 2023) pooled 1,641 elasticities
from 86 studies and 95 million observations. The result that matters:

    content type          -> engagement      -> SALES
    emotional / hedonic       +0.266             -0.073
    informational              +0.018            +0.580
    deals / promotional          --              negative

**The content mix that maximises likes is close to the inverse of the mix that
maximises revenue.** A module that optimises for engagement actively misleads a
seller who is trying to make money.

Two consequences run through this file:

  * The default pillar mix is weighted to INFORMATIONAL product content, and
    offers are capped at 5% with the cap explained rather than silently applied.
    Sellers will want to post discounts constantly. The honest thing is to make
    that friction-ful.
  * "What's working" reports reach rate, saves, sends and DMs. Follower count
    and likes are shown small and labelled as not being sales signals — because
    only 21% of sub-10K accounts grew at all last year, and a seller measuring
    themselves on followers will conclude they are failing while selling fine.

OTHER EVIDENCE ENCODED HERE
---------------------------
  * Instagram capped hashtags at 5 (January 2026). Anything that generates 30
    is broken tooling. Keywords in the caption now do what hashtags used to.
  * Captions under 30 words engage best (Socialinsider, 9.1M posts). The first
    125 characters are all that show before "... more".
  * A comment-focused CTA is worth +202% comments and a question +36%
    (Metricool, 24.3M posts) — the single highest-leverage caption element
    measured anywhere.
  * Reels out-reach everything, but only below ~50K followers — which is
    exactly this app's users. Carousels win on saves, 9x over single images.
  * Posting more does NOT cannibalise reach per post; it rises with frequency.
    The binding constraint is the seller's production capacity, which is why
    the Shoot List and atomisation matter more than the scheduler.
  * Indian D2C converts in DMs and on WhatsApp, not at a link-in-bio checkout
    (Meta/YouGov: 66% more likely to buy from a business offering instant
    messaging; 76% prefer local-language advertising). Every CTA ends in a
    conversation.
"""
from __future__ import annotations

import re
import secrets
from datetime import date, datetime, timedelta, timezone

from backend.core import aiprovider, user_store

PLAN_KEY = "social_plan"
POSTS_KEY = "social_posts"
SETTINGS_KEY = "social_settings"


# --------------------------------------------------------------- vocabulary

PILLARS = [
    {"id": "detail", "name": "Product in detail", "type": "informational", "share": 40,
     "why": "Fabric, weight, karat, sizing, notes, care. Dull to write, and the "
            "single strongest driver of sales in the research (+0.580).",
     "prompts": ["What is it made of?", "How does it fit?", "How do you care for it?"]},
    {"id": "new", "name": "New arrival", "type": "informational", "share": 20,
     "why": "New products show a larger effect than existing ones, so a drop "
            "cadence is doing real work, not filling space.",
     "prompts": ["What just landed?", "How many pieces?", "When does it ship?"]},
    {"id": "proof", "name": "Proof", "type": "social", "share": 20,
     "why": "Customer photos, reviews, unboxings, 'we shipped 50 today'. Builds "
            "trust and cannot be copied by a competitor.",
     "prompts": ["Who wore it?", "What did they say?", "How many went out?"]},
    {"id": "founder", "name": "Behind the scenes", "type": "emotional", "share": 15,
     "why": "The studio, the karigar, the packing table. Drives the reach that "
            "carries your product posts — but on its own it does not sell.",
     "prompts": ["Who made it?", "What went wrong today?", "Where do you source?"]},
    {"id": "offer", "name": "Offer", "type": "deals", "share": 5,
     "why": "Capped deliberately. Deals content is NEGATIVELY associated with "
            "sales in the research. Posting discounts feels productive and is "
            "the most common way small sellers train their audience to wait.",
     "prompts": ["What is the offer?", "When does it end?"]},
]
PILLAR_BY_ID = {p["id"]: p for p in PILLARS}
OFFER_CAP_PERCENT = 5

CADENCE = {
    "survival": {"label": "Survival", "posts": 2, "stories": 2,
                 "hours": "under 1 hour a week",
                 "why": "Below this an account shrinks — dormant accounts lose "
                        "0.08% of followers a week."},
    "standard": {"label": "Standard", "posts": 4, "stories": 4,
                 "hours": "about 2 hours a week",
                 "why": "3-5 posts a week roughly doubles growth versus 1-2, and "
                        "reach per post goes UP, not down."},
    "growth":   {"label": "Growth", "posts": 6, "stories": 5,
                 "hours": "about 4 hours a week",
                 "why": "6-9 a week is where growth compounds. Only take this on "
                        "if you can actually shoot enough."},
}

FORMATS = {
    "reel": {"label": "Reel", "why": "Highest reach rate below 50K followers "
                                     "(9.8% at 1-5K). 30-60 seconds is the sweet spot.",
             "target_seconds": 45},
    "carousel": {"label": "Carousel", "why": "9x the saves of a single image. A save "
                                             "on a Rs 4,000 lehenga is purchase intent.",
                 "slides": 5},
    "story": {"label": "Story", "why": "Retention, not reach. Story replies are up "
                                       "88% year on year and a reply is a sales lead."},
    "image": {"label": "Single image", "why": "Reach down 22% and engagement down 46% "
                                              "year on year. Use sparingly.",
              "deprecated": True},
}

LANGUAGES = {
    "hinglish": "Hinglish written in Roman script",
    "english": "English",
    "hindi": "Hindi in Devanagari script",
}

# Verified against panchang-based sources rather than marketing blogs, which
# routinely get these wrong by a week. Lunisolar dates shift every year, so this
# table is DATED and must be refreshed — never extrapolate it forward.
FESTIVALS_2026 = [
    {"date": "2026-10-11", "name": "Navratri begins", "lead": 3,
     "categories": ["clothing", "jewellery"],
     "note": "Peak clothing window. Chaniya choli, lehenga, ethnic sets."},
    {"date": "2026-10-20", "name": "Dussehra", "lead": 2, "categories": ["clothing"]},
    {"date": "2026-11-06", "name": "Dhanteras", "lead": 5, "categories": ["jewellery"],
     "note": "The single biggest jewellery-buying day of the Indian year."},
    {"date": "2026-11-08", "name": "Diwali", "lead": 17, "categories": ["clothing", "jewellery", "perfume"],
     "note": "Start pre-campaign around 22 Oct. Meta and Google CPMs climb hard "
             "from mid-September, so build the audience in August, not November."},
    {"date": "2026-11-11", "name": "Bhai Dooj", "lead": 3, "categories": ["jewellery", "clothing"]},
    {"date": "2026-12-25", "name": "Christmas", "lead": 10, "categories": ["clothing", "perfume"]},
    {"date": "2026-12-31", "name": "New Year's Eve", "lead": 5, "categories": ["clothing", "perfume"]},
]

# Wedding demand runs on a different rhythm from festivals: Chaturmas means no
# auspicious dates Aug-Oct, and January has none either. Together the two
# calendars cover most of the year, leaving January as the only genuinely slack
# month — which is when the module should push evergreen catalogue work.
WEDDING_MONTHS = {2: "high", 3: "high", 4: "medium", 5: "medium", 6: "medium",
                  7: "low", 8: "none", 9: "none", 10: "none",
                  11: "high", 12: "high", 1: "none"}


# --------------------------------------------------------------- settings

def blank_settings() -> dict:
    return {"category": "clothing", "language": "hinglish", "cadence": "standard",
            "pillars": [p["id"] for p in PILLARS], "whatsapp": "",
            "brand_hashtag": "", "handle": "", "city": "",
            "order_cta": "DM us to order"}


def get_settings(email: str) -> dict:
    s = blank_settings()
    s.update(user_store.get_key((email or "").lower(), SETTINGS_KEY, {}) or {})
    return s


def save_settings(email: str, patch: dict) -> dict:
    s = get_settings(email)
    for k, v in (patch or {}).items():
        if k in s:
            s[k] = v
    if s["cadence"] not in CADENCE:
        s["cadence"] = "standard"
    if s["language"] not in LANGUAGES:
        s["language"] = "hinglish"
    user_store.set_key((email or "").lower(), SETTINGS_KEY, s)
    return s


# --------------------------------------------------------------- planning

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slate_shape(cadence: str) -> list[dict]:
    """Which pillar and format each slot in the week gets.

    Format mix follows the reach data: Reels for new customers, carousels for
    saves and consideration, single images essentially retired."""
    n = CADENCE.get(cadence, CADENCE["standard"])["posts"]
    order = ["detail", "new", "proof", "detail", "founder", "detail", "proof", "offer"]
    fmts = ["reel", "carousel", "reel", "carousel", "reel", "carousel", "reel", "carousel"]
    slots = []
    for i in range(n):
        pid = order[i % len(order)]
        # Enforce the offer cap by slot count rather than by nagging.
        if pid == "offer" and (i + 1) / n * 100 > OFFER_CAP_PERCENT and n < 20:
            pid = "detail"
        slots.append({"slot": i + 1, "pillar": pid, "format": fmts[i % len(fmts)]})
    return slots


def upcoming_festivals(today: date | None = None, category: str = "",
                       horizon_days: int = 90) -> list[dict]:
    today = today or date.today()
    out = []
    for f in FESTIVALS_2026:
        d = date.fromisoformat(f["date"])
        days = (d - today).days
        if not (0 <= days <= horizon_days):
            continue
        if category and f.get("categories") and category not in f["categories"]:
            continue
        start = d - timedelta(days=f.get("lead", 7))
        out.append({**f, "days_away": days, "start_on": start.isoformat(),
                    "start_in_days": (start - today).days,
                    "act_now": (start - today).days <= 0})
    return sorted(out, key=lambda x: x["days_away"])


def radar(email: str, today: date | None = None) -> dict:
    s = get_settings(email)
    today = today or date.today()
    fest = upcoming_festivals(today, s.get("category") or "")
    wed = WEDDING_MONTHS.get(today.month, "low")
    lines = []
    for f in fest[:3]:
        if f["act_now"]:
            lines.append(f"{f['name']} is {f['days_away']} days away. "
                         f"You should already be posting for it.")
        else:
            lines.append(f"{f['name']} is {f['days_away']} days away. "
                         f"Start posting on {f['start_on']}.")
    if wed in ("high", "medium") and (s.get("category") in ("clothing", "jewellery")):
        lines.append(f"Wedding demand is {wed} this month — a second, independent "
                     f"driver from the festival calendar.")
    if today.month == 1:
        lines.append("January is the one genuinely slack month: no festivals, no "
                     "wedding dates. Good time to build catalogue and collect reviews.")
    return {"festivals": fest, "wedding_density": wed, "headline": lines,
            "dates_note": "Festival dates are lunisolar and shift every year. "
                          "This table is for 2026 and must be refreshed, not "
                          "extrapolated."}


# --------------------------------------------------------------- writing

def _caption_system(settings: dict) -> str:
    lang = LANGUAGES.get(settings.get("language") or "hinglish")
    return f"""You write Instagram captions for a small Indian D2C seller.

Write in {lang}.

Structure, in this exact order:
1. A hook line of at most 125 characters. Instagram truncates there, so this line
   must carry the product and a reason to care. No greeting, no throat-clearing.
2. Two or three lines of SPECIFIC, factual detail — fabric, weight, karat, notes,
   sizing, care, how many pieces exist. Concrete beats evocative.
3. One question that invites a COMMENT, not a like.
4. One line telling them how to order.

Hard rules:
- The body after the hook must be under 30 words. Short captions engage best.
- Exactly 5 hashtags, no more. Instagram capped them at 5 in January 2026.
- Include the product category as plain words in the hook, because Instagram now
  ranks on caption keywords rather than hashtags.
- No emoji spam. At most two, and only if they aid scanning.
- Never invent a discount, a price, a delivery time or a material that you were
  not given.

Return exactly this, nothing else:
HOOK: <one line>
BODY: <two or three short lines>
QUESTION: <one question>
CTA: <one line>
TAGS: <5 hashtags separated by spaces>"""


def _parse_caption(text: str) -> dict:
    out = {"hook": "", "body": "", "question": "", "cta": "", "tags": []}
    cur = None
    for raw in (text or "").splitlines():
        line = raw.strip()
        m = re.match(r"^(HOOK|BODY|QUESTION|CTA|TAGS)\s*:\s*(.*)$", line, re.I)
        if m:
            cur = m.group(1).lower()
            val = m.group(2).strip()
            if cur == "tags":
                out["tags"] = re.findall(r"#[\w]+", val)
            else:
                out[cur] = val
        elif cur == "body" and line:
            out["body"] = f"{out['body']}\n{line}".strip()
        elif cur == "tags" and line:
            out["tags"] += re.findall(r"#[\w]+", line)
    out["tags"] = out["tags"][:5]
    return out


def _fallback_caption(product: dict, pillar: dict, settings: dict) -> dict:
    """No AI configured, or every provider down. Still produces something a
    seller can post — a duller caption beats an error message."""
    name = product.get("name") or "this piece"
    cat = settings.get("category") or "piece"
    price = product.get("price")
    hook = f"New in: {name}" if pillar["id"] == "new" else f"{name} — the details"
    if price:
        hook = f"{hook} · Rs {int(float(price))}"
    body = product.get("description") or f"Handpicked {cat}. Limited pieces."
    return {"hook": hook[:125], "body": body[:160],
            "question": "Which colour should we restock first?",
            "cta": settings.get("order_cta") or "DM us to order",
            "tags": [f"#{re.sub(r'[^a-z]', '', cat.lower())}", "#indianfashion",
                     "#smallbusinessindia", "#handmade", "#shoplocal"][:5],
            "generated_by": "template"}


def write_caption(email: str, product: dict, pillar_id: str,
                  angle: str = "") -> dict:
    s = get_settings(email)
    pillar = PILLAR_BY_ID.get(pillar_id) or PILLARS[0]
    facts = {k: product.get(k) for k in
             ("name", "price", "description", "fabric", "sizes", "care", "stock", "category")
             if product.get(k)}
    user = (f"Pillar: {pillar['name']} ({pillar['type']}).\n"
            f"Angle: {angle or pillar['prompts'][0]}\n"
            f"Seller city: {s.get('city') or 'India'}\n"
            f"How to order: {s.get('order_cta')}\n"
            f"Product facts (use only these):\n"
            + "\n".join(f"- {k}: {v}" for k, v in facts.items()))

    fb = _fallback_caption(product, pillar, s)
    res = aiprovider.generate(_caption_system(s), user, sensitivity="public",
                              max_tokens=400, temperature=0.8,
                              fallback="")
    if not res["text"]:
        return {**fb, "provider": "template", "free": True, "error": res.get("error", "")}
    parsed = _parse_caption(res["text"])
    if not parsed["hook"]:
        return {**fb, "provider": "template", "free": True,
                "error": "model did not return the expected shape"}
    return {**parsed, "provider": res["provider"], "free": res["free"], "error": ""}


def assemble(caption: dict) -> str:
    """The caption as it will actually be pasted into Instagram."""
    parts = [caption.get("hook", "")]
    if caption.get("body"):
        parts += ["", caption["body"]]
    if caption.get("question"):
        parts += ["", caption["question"]]
    if caption.get("cta"):
        parts += ["", caption["cta"]]
    if caption.get("tags"):
        parts += ["", " ".join(caption["tags"][:5])]
    return "\n".join(parts).strip()


def caption_check(caption: dict, settings: dict) -> list[dict]:
    """Warnings, not blocks. The seller can post anyway — this just tells them
    what the evidence says they are giving up."""
    out = []
    hook = caption.get("hook") or ""
    if len(hook) > 125:
        out.append({"level": "warn", "text":
                    f"The hook is {len(hook)} characters. Instagram cuts at 125, "
                    f"so the rest is hidden behind '... more'."})
    words = len((caption.get("body") or "").split())
    if words > 30:
        out.append({"level": "info", "text":
                    f"The body is {words} words. Captions under 30 words engage "
                    f"best across 9 million posts studied."})
    if not (caption.get("question") or "").strip():
        out.append({"level": "warn", "text":
                    "No question. A comment-focused prompt is worth about 200% "
                    "more comments — the biggest single lever in a caption."})
    n = len(caption.get("tags") or [])
    if n > 5:
        out.append({"level": "error", "text":
                    f"{n} hashtags. Instagram capped them at 5 in January 2026."})
    elif n == 0:
        out.append({"level": "info", "text":
                    "No hashtags. They are only worth about +2% reach now, so this "
                    "is fine — but make sure your category words are in the hook, "
                    "because that is what search ranks on."})
    return out


# --------------------------------------------------------------- posts

STATES = ["draft", "ready", "scheduled", "published", "failed"]


def _posts(email: str) -> list[dict]:
    rows = user_store.get_key((email or "").lower(), POSTS_KEY, []) or []
    return rows if isinstance(rows, list) else []


def _save_posts(email: str, rows: list[dict]) -> None:
    user_store.set_key((email or "").lower(), POSTS_KEY, rows[-400:])


def build_week(email: str, catalogue: list[dict], start: date | None = None) -> list[dict]:
    """Generate this week's slate. One product per slot, cycling the catalogue
    so the same three products do not carry every post."""
    s = get_settings(email)
    start = start or date.today()
    shape = slate_shape(s.get("cadence") or "standard")
    pool = [p for p in catalogue if p.get("name")] or [{"name": "your product"}]
    rows = _posts(email)
    made = []

    # Best slots from 9.6M posts: Wed and Thu strongest, evenings 6-11pm,
    # Fri/Sat weakest. Local time — no India-specific adjustment needed.
    best_hours = [18, 12, 19, 9, 20, 18]
    day_offsets = [2, 3, 0, 4, 1, 5]

    for i, slot in enumerate(shape):
        product = pool[i % len(pool)]
        cap = write_caption(email, product, slot["pillar"])
        when = datetime.combine(start + timedelta(days=day_offsets[i % len(day_offsets)]),
                                datetime.min.time()).replace(hour=best_hours[i % len(best_hours)])
        post = {
            "id": secrets.token_hex(6),
            "created_at": _now(),
            "product_id": product.get("id") or "",
            "product_name": product.get("name") or "",
            "pillar": slot["pillar"],
            "pillar_name": PILLAR_BY_ID[slot["pillar"]]["name"],
            "format": slot["format"],
            "caption": cap,
            "text": assemble(cap),
            "checks": caption_check(cap, s),
            "scheduled_at": when.isoformat(timespec="minutes"),
            "state": "draft",
            "provider": cap.get("provider", "template"),
            "metrics": {},
        }
        made.append(post)
        rows.append(post)

    _save_posts(email, rows)
    return made


def week(email: str) -> list[dict]:
    live = [p for p in _posts(email) if p.get("state") in ("draft", "ready", "scheduled")]
    return sorted(live, key=lambda p: p.get("scheduled_at") or "")


def set_state(email: str, post_id: str, state: str) -> dict:
    if state not in STATES:
        return {"error": "bad state"}
    rows = _posts(email)
    for p in rows:
        if p.get("id") == post_id:
            p["state"] = state
            p["state_at"] = _now()
            _save_posts(email, rows)
            return p
    return {"error": "not found"}


def approve_all(email: str) -> dict:
    """The one tap that matters. Everything in draft becomes scheduled."""
    rows = _posts(email)
    n = 0
    for p in rows:
        if p.get("state") == "draft":
            p["state"] = "scheduled"
            p["state_at"] = _now()
            n += 1
    _save_posts(email, rows)
    return {"scheduled": n}


def update_post(email: str, post_id: str, patch: dict) -> dict:
    rows = _posts(email)
    s = get_settings(email)
    for p in rows:
        if p.get("id") == post_id:
            cap = dict(p.get("caption") or {})
            for k in ("hook", "body", "question", "cta"):
                if k in (patch or {}):
                    cap[k] = str(patch[k])[:600]
            if "tags" in (patch or {}):
                cap["tags"] = [t if t.startswith("#") else f"#{t}"
                               for t in (patch["tags"] or [])][:5]
            p["caption"] = cap
            p["text"] = assemble(cap)
            p["checks"] = caption_check(cap, s)
            if "scheduled_at" in (patch or {}):
                p["scheduled_at"] = str(patch["scheduled_at"])[:20]
            if "format" in (patch or {}) and patch["format"] in FORMATS:
                p["format"] = patch["format"]
            _save_posts(email, rows)
            return p
    return {"error": "not found"}


# --------------------------------------------------------------- shoot list

def shoot_list(email: str, catalogue: list[dict], n: int = 3) -> dict:
    """The highest-value screen in the module.

    Reach per post rises with frequency and does not cannibalise, so the only
    thing limiting a seller is how much material they have. One 20-minute shoot
    of three products atomises into roughly nine assets, which is two to three
    weeks of the recommended cadence."""
    picks = [p for p in catalogue if p.get("name")][:n]
    return {
        "products": [{"id": p.get("id"), "name": p.get("name")} for p in picks],
        "minutes": 20,
        "per_product": ["6-10 stills on a plain backdrop, front / detail / worn",
                        "60 seconds of video, slow pan then a wear test",
                        "One 10-second clip of it being packed"],
        "yields": [
            {"asset": "Reel 1", "from": "video", "angle": "product detail, 30-60s"},
            {"asset": "Reel 2", "from": "same video", "angle": "styling or wear test"},
            {"asset": "Carousel A", "from": "5 stills", "angle": "fabric, sizing, care"},
            {"asset": "Carousel B", "from": "same stills", "angle": "3 ways to style"},
            {"asset": "Story set 1", "from": "behind the scenes", "angle": "colour poll"},
            {"asset": "Story set 2", "from": "packing clip", "angle": "drop countdown"},
            {"asset": "Highlight", "from": "best frames", "angle": "catalogue"},
            {"asset": "Reel 3 (later)", "from": "customer photos", "angle": "proof"},
            {"asset": "Carousel C (later)", "from": "reviews", "angle": "proof"},
        ],
        "note": "Nine assets from one session covers two to three weeks. Batching "
                "is the only way the arithmetic works at this cadence.",
    }


# --------------------------------------------------------------- metrics

def whats_working(email: str) -> dict:
    """Four numbers, and an honest label on the two everyone else features."""
    rows = [p for p in _posts(email) if p.get("state") == "published"]
    agg = {"reach": 0, "saves": 0, "sends": 0, "dms": 0, "likes": 0, "posts": len(rows)}
    for p in rows:
        m = p.get("metrics") or {}
        for k in ("reach", "saves", "sends", "dms", "likes"):
            agg[k] += int(m.get(k) or 0)

    best = None
    if rows:
        best = max(rows, key=lambda p: int((p.get("metrics") or {}).get("saves") or 0))

    return {
        "headline": [
            {"key": "reach_rate", "label": "Reach rate", "value": None,
             "benchmark": "9.8% is typical for Reels on a 1-5K account",
             "matters": True},
            {"key": "saves", "label": "Saves", "value": agg["saves"], "matters": True,
             "why": "A save on a considered purchase is deferred buying intent."},
            {"key": "sends", "label": "Sends", "value": agg["sends"], "matters": True,
             "why": "The heaviest-weighted signal in Instagram's ranking, and "
                    "usually a purchase conversation starting."},
            {"key": "dms", "label": "DMs started", "value": agg["dms"], "matters": True,
             "why": "In India this is where the sale actually happens."},
        ],
        "muted": [
            {"key": "likes", "label": "Likes", "value": agg["likes"],
             "note": "Not a sales signal. Likes correlate with engagement and "
                     "mildly NEGATIVELY with sales."},
            {"key": "followers", "label": "Followers", "value": None,
             "note": "Not a sales signal. Only 21% of accounts under 10,000 "
                     "followers grew at all last year — measuring yourself on "
                     "this will tell you you are failing while you are selling fine."},
        ],
        "best_post": ({"id": best["id"], "product": best.get("product_name"),
                       "pillar": best.get("pillar_name"), "format": best.get("format")}
                      if best else None),
        "posts": agg["posts"],
        "enough_data": agg["posts"] >= 8,
    }


def clone_winner(email: str, post_id: str, catalogue: list[dict]) -> dict:
    """'Make more like this' — reuse the winning pillar and format on the next
    product, rather than asking the seller to work out why it worked."""
    src = next((p for p in _posts(email) if p.get("id") == post_id), None)
    if not src:
        return {"error": "not found"}
    pool = [p for p in catalogue if p.get("id") != src.get("product_id")] or catalogue
    if not pool:
        return {"error": "no products"}
    product = pool[0]
    cap = write_caption(email, product, src.get("pillar") or "detail")
    s = get_settings(email)
    post = {"id": secrets.token_hex(6), "created_at": _now(),
            "product_id": product.get("id") or "", "product_name": product.get("name") or "",
            "pillar": src.get("pillar"), "pillar_name": src.get("pillar_name"),
            "format": src.get("format"), "caption": cap, "text": assemble(cap),
            "checks": caption_check(cap, s),
            "scheduled_at": "", "state": "draft", "cloned_from": post_id,
            "provider": cap.get("provider", "template"), "metrics": {}}
    rows = _posts(email)
    rows.append(post)
    _save_posts(email, rows)
    return post
