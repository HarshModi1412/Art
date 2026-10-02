"""
Marketing Campaign — build a draft, let the seller look, then send it.

The pipeline the Marketing Campaign screen and the every-second-Monday job
(winback_auto) both run:

  reason + offer  ->  audience (analytics.campaign_audience)
                  ->  minus anyone contacted recently (cooldown)
                  ->  one real discount code each (discounts.issue)
                  ->  the words, once per campaign (campaign_writer)
                  ->  one picture (campaign_image), or a request for one
                  ->  a DRAFT the seller reviews
  approve         ->  WhatsApp (automatic when connected and Meta approved the
                      template, tap-to-send links otherwise) + email
                  ->  recorded for measurement (winback_proof), and every
                      redeemed code is counted against the campaign

Nothing reaches a customer until a person presses Send.
"""
from __future__ import annotations

import html as _html
import logging
import secrets
from datetime import date

import pandas as pd

from backend.core import campaigns, messaging, user_store, winback_proof

log = logging.getLogger("campaign_engine")

DRAFTS_KEY = "campaign_drafts"
RECORDS_KEY = "campaign_records"
MAX_DRAFTS = 4
MAX_RECORDS = 30
MAX_AUDIENCE = 150
# A holdout is how a campaign PROVES it worked: a random tenth of the audience
# is not messaged, and the analyzer compares how many of each group came back.
# Without it, "12 customers returned" might be 12 who would have anyway.
HOLDOUT_SHARE = 0.10
HOLDOUT_MIN_AUDIENCE = 20
# How long anyone contacted by ANY campaign is left alone before this kind
# may write to them again. Shorter for the ones customers welcome (a restock
# reminder, a VIP first look), longest for win-back.
COOLDOWN = {"winback": 45, "festival": 14, "second_order": 30, "cross_sell": 21,
            "restock": 14, "vip": 14, "thank_you": 30}
REASONS = tuple(COOLDOWN)
PREFIX = {"winback": "BACK", "festival": "FEST", "second_order": "NEXT", "cross_sell": "PAIR",
          "restock": "REFILL", "vip": "VIP", "thank_you": "THANKS"}
EMPTY = {
    "winback": "Nobody has gone quiet yet, so there is nobody to win back. Try a festival "
               "campaign for your best customers instead.",
    "festival": "There are no customers in your sales data yet.",
    "second_order": "Nobody placed a first order 2 to 8 weeks ago, so there is nobody to nudge "
                    "towards a second one right now.",
    "cross_sell": "Your sales do not show strong 'bought together' pairs yet. It needs more "
                  "orders with two or more products in them.",
    "restock": "Nobody is due for a restock right now: either your products are not bought "
               "again and again, or everyone has bought recently.",
    "vip": "You do not have customers in the Champions group yet.",
    "thank_you": "Nobody ordered in the last two weeks.",
}
_SAMPLE_DOMAINS = ("example.com", "example.org", "example.net")


class CampaignError(ValueError):
    """Something the seller must fix before the campaign can be built or sent."""


# ------------------------------------------------------------------- drafts
def _drafts(email: str) -> dict:
    d = user_store.get_key(email, DRAFTS_KEY, {}) or {}
    return d if isinstance(d, dict) else {}


def _save_draft(email: str, draft: dict) -> None:
    d = dict(_drafts(email))
    d[draft["id"]] = draft
    if len(d) > MAX_DRAFTS:
        order = sorted(d, key=lambda k: d[k].get("created_at") or "")
        for k in order[:len(d) - MAX_DRAFTS]:
            if k != draft["id"]:
                d.pop(k, None)
    user_store.set_key(email, DRAFTS_KEY, d)


def get_draft(email: str, draft_id: str) -> dict | None:
    d = _drafts(email).get(draft_id)
    return d if isinstance(d, dict) else None


def latest_draft(email: str) -> dict | None:
    rows = [d for d in _drafts(email).values()
            if isinstance(d, dict) and d.get("state") == "draft"]
    return max(rows, key=lambda d: d.get("created_at") or "") if rows else None


def discard(email: str, draft_id: str) -> None:
    d = dict(_drafts(email))
    if d.pop(draft_id, None) is not None:
        user_store.set_key(email, DRAFTS_KEY, d)


# ------------------------------------------------------------------ helpers
def _symbol(email: str) -> str:
    try:
        from backend.core import currency, sitebuilder
        ccy = ((sitebuilder.get_site(email) or {}).get("commerce") or {}).get("currency") or "INR"
        return currency.symbol(ccy) or "₹"
    except Exception:  # noqa: BLE001
        return "₹"


def _base() -> str:
    from backend.core import publicurl
    return (publicurl.configured() or messaging.APP_URL).rstrip("/")


def store_link(email: str) -> str:
    """The seller's live shop, or "" when it is not published (a code that
    cannot be used online is still good to show in person)."""
    try:
        from backend.core import sitebuilder
        site = sitebuilder.get_site(email) or {}
        if not site.get("published") or not site.get("handle"):
            return ""
        if site.get("custom_domain"):
            return f"https://{site['custom_domain']}/"
        return f"{_base()}/s/{site['handle']}"
    except Exception:  # noqa: BLE001
        return ""


def absolute(url: str) -> str:
    if not url or url.startswith("http"):
        return url or ""
    return f"{_base()}/{url.lstrip('/')}"


def _sells(txns, names: dict) -> str:
    """What the shop sells, in a few words, for the AI brief and the picture."""
    from backend.core import campaign_writer as cw
    for col in ("category", "subcategory"):
        if col in txns.columns:
            top = txns.groupby(col)["amount"].sum().sort_values(ascending=False).head(3)
            vals = [str(v).strip() for v in top.index
                    if str(v).strip() and str(v).lower() not in ("nan", "none", "")]
            if vals:
                return ", ".join(v.lower() for v in vals)
    if "product" in txns.columns:
        top = txns.groupby("product")["amount"].sum().sort_values(ascending=False).head(3)
        vals = [v for v in (cw.clean_product_name(x, names) for x in top.index) if v]
        if vals:
            return ", ".join(vals)
    return "products"


def upcoming_occasion(email: str, horizon: int = 30) -> dict | None:
    """The next festival worth a campaign, from the social calendar."""
    try:
        from backend.core import localtime, social
        cat = (social.get_settings(email) or {}).get("category") or ""
        fest = social.upcoming_festivals(localtime.today(email), cat, horizon_days=horizon)
        return fest[0] if fest else None
    except Exception:  # noqa: BLE001
        return None


def upcoming_occasions(email: str, horizon: int = 60) -> list[dict]:
    try:
        from backend.core import localtime, social
        cat = (social.get_settings(email) or {}).get("category") or ""
        return [{"name": f["name"], "date": f["date"], "days_away": f["days_away"]}
                for f in social.upcoming_festivals(localtime.today(email), cat,
                                                   horizon_days=horizon)][:6]
    except Exception:  # noqa: BLE001
        return []


def is_sample(addr: str) -> bool:
    a = (addr or "").lower()
    # Only the reserved example domains (RFC 2606) that the sample dataset uses.
    return a.split("@")[-1] in _SAMPLE_DOMAINS


def pitch(reason: str, product: str, occasion: str, pick: str = "") -> str:
    """The one-line middle of the WhatsApp API template (no newlines allowed)."""
    if reason == "second_order":
        return (f"We hope you are enjoying the {product}. " if product else
                "Thank you for your first order with us. ") + \
            (f"Many of our customers pick the {pick} next." if pick else "We would love to see you again.")
    if reason == "cross_sell":
        return f"Since you have the {product}, we think you would love the {pick}: our customers often pair the two."
    if reason == "restock":
        return f"It has been about the usual time since your last {product}, so it might be running low."
    if reason == "vip":
        return "You are one of our very best customers, so you hear about this first."
    if reason == "thank_you":
        return (f"Thank you for your order. We hope you love the {product}." if product
                else "Thank you for your order with us.")
    if reason == "festival":
        return (f"{occasion} is almost here, and we would love to be part of it. "
                + (f"You loved the {product}, so we think you will like what is new."
                   if product else "Here is a little something to celebrate with."))
    return ("It has been a while and we have missed you. "
            + (f"Since you liked the {product}, we saved something for your next order."
               if product else "We saved something special for your next order."))


# -------------------------------------------------------------------- build
def build(email: str, reason: str = "winback", offer: dict | None = None,
          occasion: str = "", note: str = "", with_image: bool = True,
          trigger: str = "manual", limit: int = MAX_AUDIENCE) -> dict:
    """Build a campaign draft. Raises CampaignError with a seller-facing reason."""
    from backend.core import (analytics, brandname, campaign_image, discounts, smart,
                              winback_auto)
    from backend.core import campaign_writer as cw

    reason = reason if reason in REASONS else "winback"
    try:
        offer = discounts.clean_offer(offer)
    except discounts.DiscountError as e:
        raise CampaignError(str(e))

    txns = smart.load_sales(email)
    if txns is None or not len(txns):
        raise CampaignError("Upload your sales first. A campaign is built from who bought what.")

    fest = None
    occasion = (occasion or "").strip()[:40]
    if reason == "festival" and not occasion:
        fest = upcoming_occasion(email)
        occasion = (fest or {}).get("name") or ""
        if not occasion:
            raise CampaignError("Which festival or occasion is this for? Type its name.")
    if reason == "vip" and not (note or "").strip():
        raise CampaignError("What are your VIPs getting early access to? Write it in "
                            "'Anything to mention', e.g. 'our new festive collection is live'.")

    cap = max(1, min(int(limit), MAX_AUDIENCE))
    cooling = winback_auto.recently_contacted(email, days=COOLDOWN[reason])
    # Ask for enough to still fill the campaign after the cooldown takes its
    # share, then cap: the most valuable customers NOT recently contacted.
    audience = analytics.campaign_audience(txns, reason, limit=cap + len(cooling))
    fresh = [c for c in audience if str(c.get("customer_id") or "") not in cooling]
    held_back = len(audience) - len(fresh)
    fresh = fresh[:cap]
    if not fresh:
        if held_back:
            raise CampaignError(f"Everyone this campaign would reach was contacted in the last "
                                f"{COOLDOWN[reason]} days. Give them a break and try again later.")
        raise CampaignError(EMPTY[reason])

    from backend.core import contacts
    contacts.apply(email, fresh)
    names = cw.catalogue_names(email)
    last_bought = _last_bought(txns, fresh) if reason == "thank_you" else {}
    for c in fresh:
        # what the message talks about depends on why it is being sent
        about = {"restock": c.get("due_item"), "cross_sell": c.get("pair_have"),
                 "thank_you": last_bought.get(str(c.get("customer_id")))}.get(reason) \
            or c.get("favorite_item")
        c["product_display"] = cw.clean_product_name(about, names)

    campaign_id = secrets.token_hex(6)
    if reason == "cross_sell":
        for c in fresh:
            c["pick_display"] = cw.clean_product_name(c.get("pair_pick"), names)
    elif reason in ("restock", "thank_you"):
        for c in fresh:
            c["pick_display"] = ""         # one product, one reason to write
    else:
        _add_picks(txns, fresh, names)
    # these two only make sense with the product they are about
    if reason in ("cross_sell", "restock"):
        fresh = [c for c in fresh if c["product_display"]
                 and (reason != "cross_sell" or (c.get("pick_display")
                                                 and c["pick_display"] != c["product_display"]))]
        if not fresh:
            raise CampaignError(EMPTY[reason])

    holdout = []
    if len(fresh) >= HOLDOUT_MIN_AUDIENCE:
        import random as _random
        idx = list(range(len(fresh)))
        _random.Random(campaign_id).shuffle(idx)
        keep_out = set(idx[:max(1, round(len(fresh) * HOLDOUT_SHARE))])
        holdout = [{"customer_id": str(c["customer_id"]),
                    "customer_name": c.get("customer_name") or "",
                    "monetary": c.get("monetary") or 0}
                   for i, c in enumerate(fresh) if i in keep_out]
        fresh = [c for i, c in enumerate(fresh) if i not in keep_out]
    try:
        codes = discounts.issue(email, campaign_id, fresh, offer,
                                prefix_fallback=PREFIX[reason])
    except discounts.DiscountError as e:
        raise CampaignError(str(e))
    valid_until = next(iter(codes.values()))["valid_until"] if codes else ""
    try:
        expiry_label = date.fromisoformat(valid_until).strftime("%d %b").lstrip("0")
    except ValueError:
        expiry_label = valid_until

    resolved = brandname.resolve(email)
    sym = _symbol(email)
    val = offer["value"]
    ctx = {
        "reason": reason, "occasion": occasion, "note": (note or "").strip()[:300],
        # Until the seller names the shop the preview SAYS so, rather than
        # signing a customer message "us"; send() refuses without a name.
        "brand": (resolved.get("name") if resolved.get("ready") else "") or "[your shop name]",
        "brand_ready": bool(resolved.get("ready")),
        "sells": _sells(txns, names), "offer": offer,
        "offer_label": discounts.offer_label(offer, sym),
        "offer_short": f"{val:g}% OFF" if offer["kind"] == "percent" else f"{sym}{val:g} OFF",
        "expiry_label": expiry_label, "valid_until": valid_until,
        "link": store_link(email), "symbol": sym, "campaign_id": campaign_id,
    }
    voices = cw.deal(campaign_id, len(fresh), reason)

    rows = []
    for c, voice in zip(fresh, voices):
        row = {"customer_id": str(c["customer_id"]),
               "customer_name": c.get("customer_name") or "",
               "phone": c.get("phone") or "", "email": c.get("email") or "",
               "segment": c.get("segment") or "", "monetary": c.get("monetary") or 0,
               "recency_days": c.get("recency_days") or 0,
               "favorite_item": c.get("favorite_item") or "",
               "product_display": c["product_display"],
               "pick_display": c.get("pick_display") or "",
               "voice": voice,
               "code": (codes.get(str(c["customer_id"])) or {}).get("code") or ""}
        row.update(cw.message_for(row, ctx))
        row["pitch"] = pitch(reason, row["product_display"], occasion, row.get("pick_display") or "")
        rows.append(row)

    image = {"url": "", "source": "", "needs_upload": False, "reason": ""}
    if with_image:
        try:
            image.update(campaign_image.generate(email, ctx))
        except campaign_image.NeedsUpload as e:
            image.update({"needs_upload": True, "reason": str(e)})
        except Exception as e:  # noqa: BLE001
            log.warning("campaign image crashed for %s: %s", email, e)
            image.update({"needs_upload": True,
                          "reason": "The AI picture could not be made. Add a photo of your own."})
    else:
        image.update({"needs_upload": True, "reason": "Add a picture for this campaign."})

    draft = {
        "id": campaign_id, "state": "draft", "trigger": trigger,
        "created_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "reason": reason, "occasion": occasion, "offer": offer, "ctx": ctx,
        "image": image, "rows": rows, "held_back": held_back, "holdout": holdout,
        "festival": ({"name": fest.get("name"), "date": fest.get("date"),
                      "days_away": fest.get("days_away")} if fest else None),
    }
    _save_draft(email, draft)
    return public_draft(email, draft)


def counts(rows: list[dict]) -> dict:
    phones = sum(1 for r in rows if r.get("phone"))
    emails = sum(1 for r in rows if r.get("email") and not is_sample(r["email"]))
    return {"audience": len(rows), "phone": phones, "email": emails,
            "unreachable": sum(1 for r in rows if not r.get("phone")
                               and not (r.get("email") and not is_sample(r["email"]))),
            "value": round(sum(float(r.get("monetary") or 0) for r in rows), 2)}


def public_draft(email: str, draft: dict) -> dict:
    """The draft as the screen needs it, with live counts and channel state."""
    from backend.core import campaign_image, whatsapp
    return {**draft, "counts": counts(draft.get("rows") or []),
            "whatsapp": whatsapp.status(email),
            "email_ready": messaging.smtp_configured(),
            "image_allowance": campaign_image.allowance(email)}


def update_draft(email: str, draft_id: str, patch: dict) -> dict:
    """Seller edits before sending: one customer's contact details or message,
    who is in it, the picture."""
    from backend.core import campaign_writer as cw, contacts
    draft = get_draft(email, draft_id)
    if not draft or draft.get("state") != "draft":
        raise CampaignError("That campaign is no longer a draft.")
    if patch.get("remove"):
        drop = {str(x) for x in patch["remove"]}
        draft["rows"] = [r for r in draft["rows"] if r["customer_id"] not in drop]
        if not draft["rows"]:
            raise CampaignError("That would leave nobody in the campaign.")
    edit = patch.get("row") or None
    if edit:
        cid = str(edit.get("customer_id") or "")
        row = next((r for r in draft["rows"] if r["customer_id"] == cid), None)
        if not row:
            raise CampaignError("That customer is not in this campaign.")
        if "phone" in edit or "email" in edit:
            try:
                saved = contacts.save(email, cid, edit.get("phone") if "phone" in edit else None,
                                      edit.get("email") if "email" in edit else None,
                                      row.get("customer_name") or "")
            except contacts.ContactError as e:
                raise CampaignError(str(e))
            if "phone" in edit:
                row["phone"] = saved.get("phone") or ""
            if "email" in edit:
                row["email"] = saved.get("email") or ""
        if edit.get("reset_message"):
            row.pop("message_override", None)
        elif edit.get("message") is not None:
            why = cw.valid_override(str(edit["message"]), row.get("code") or "",
                                    (draft.get("offer") or {}).get("kind") == "none")
            if why:
                raise CampaignError(why)
            row["message_override"] = str(edit["message"]).strip()
    if patch.get("image_url"):
        draft["image"] = {"url": str(patch["image_url"]),
                          "source": patch.get("image_source") or "upload",
                          "needs_upload": False, "reason": ""}
    for r in draft["rows"]:
        r.update(cw.message_for(r, draft["ctx"]))
    _save_draft(email, draft)
    return public_draft(email, draft)


def regenerate_image(email: str, draft_id: str) -> dict:
    from backend.core import campaign_image
    draft = get_draft(email, draft_id)
    if not draft or draft.get("state") != "draft":
        raise CampaignError("That campaign is no longer a draft.")
    try:
        draft["image"] = {**campaign_image.generate(email, draft["ctx"]),
                          "needs_upload": False, "reason": ""}
    except campaign_image.NeedsUpload as e:
        img = draft.get("image") or {}
        draft["image"] = {**img, "needs_upload": not img.get("url"), "reason": str(e)}
        _save_draft(email, draft)
        raise CampaignError(str(e))
    _save_draft(email, draft)
    return public_draft(email, draft)


# --------------------------------------------------------------------- send
def campaign_html(brand: str, row: dict, ctx: dict, image_url: str) -> str:
    esc = _html.escape
    link = row.get("shop_link") or ""
    paras = "".join(
        f'<p style="margin:0 0 14px;font-size:15px;line-height:1.6;color:#2b2f3a">{esc(line)}</p>'
        for line in (row.get("message") or "").replace("*", "").split("\n")
        if line.strip() and line.strip() != link)
    img = (f'<img src="{esc(image_url)}" alt="" width="472" style="display:block;width:100%;'
           f'max-width:472px;border-radius:12px;margin:0 0 22px">' if image_url else "")
    code = ""
    if row.get("code"):
        code = (f'<div style="margin:6px 0 22px;padding:16px;border:2px dashed #b08a3e;'
                f'border-radius:10px;text-align:center"><div style="font-size:12px;'
                f'letter-spacing:.12em;text-transform:uppercase;color:#6b7186">Your code · '
                f'{esc(ctx.get("offer_label") or "")}</div><div style="font-size:24px;'
                f'font-weight:700;letter-spacing:.08em;margin-top:6px;color:#1b1d24">'
                f'{esc(row["code"])}</div><div style="font-size:12px;color:#6b7186;margin-top:4px">'
                f'Valid till {esc(ctx.get("expiry_label") or "")}</div></div>')
    btn = (f'<a href="{esc(link)}" style="display:inline-block;background:#1b1d24;color:#fff;'
           f'text-decoration:none;padding:13px 26px;border-radius:999px;font-weight:600;'
           f'font-size:15px">Shop now</a>') if link else ""
    return (f'<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;'
            f'max-width:520px;margin:0 auto;padding:32px 24px"><p style="margin:0 0 22px;'
            f'font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#6b7186">'
            f'{esc(brand)}</p>{img}{paras}{code}{btn}</div>')


def send(email: str, draft_id: str, channels: tuple[str, ...] = ("whatsapp", "email")) -> dict:
    """Send an approved draft. Email goes out now; WhatsApp sends itself when
    the seller's template is approved, and comes back as tap-to-send links
    otherwise. Every outcome is reported per customer."""
    from backend.core import brandname, whatsapp
    from backend.core import campaign_writer as cw

    draft = get_draft(email, draft_id)
    if not draft:
        raise CampaignError("That campaign could not be found. Build it again.")
    if draft.get("state") == "sent":
        raise CampaignError("This campaign has already been sent.")
    try:
        brand = brandname.require(email)
    except ValueError as e:
        raise CampaignError(str(e))
    channels = tuple(c for c in channels if c in ("whatsapp", "email")) or ("whatsapp", "email")
    ctx = {**draft["ctx"], "brand": brand}
    image_url = absolute((draft.get("image") or {}).get("url") or "")
    wa = whatsapp.status(email)
    wa_auto = "whatsapp" in channels and wa["mode"] == "auto"
    if wa_auto and wa.get("template_header") and not image_url \
            and (draft.get("offer") or {}).get("kind") != "none":
        raise CampaignError("Add a picture first: your WhatsApp template sends one with every message.")

    results, n_mail, n_wa, n_links, skipped, sample = [], 0, 0, 0, 0, 0
    for r in draft["rows"]:
        r.update(cw.message_for(r, ctx))
        to = (r.get("email") or "").strip()
        phone = (r.get("phone") or "").strip()
        entry = {"customer_id": r["customer_id"], "customer_name": r.get("customer_name") or "",
                 "email": to, "phone": phone, "code": r.get("code") or "",
                 "message": r["message"], "email_sent": False, "whatsapp_sent": False,
                 "wa_link": "", "error": ""}
        reachable = False
        if "email" in channels and to:
            if is_sample(to):
                sample += 1
                entry["error"] = "sample customer, not emailed"
            else:
                reachable = True
                try:
                    res = messaging.send(
                        to_email=to,
                        subject=r.get("email_subject") or f"A little something from {brand}",
                        text=r["message"].replace("*", ""),
                        html=campaign_html(brand, r, ctx, image_url))
                    entry["email_sent"] = bool(res.get("email"))
                    n_mail += int(entry["email_sent"])
                except Exception as e:  # noqa: BLE001 — one bad address, not the batch
                    log.warning("campaign email to %s failed: %s", to, e)
        if "whatsapp" in channels and phone:
            reachable = True
            if wa_auto:
                try:
                    if (draft.get("offer") or {}).get("kind") == "none":
                        whatsapp.send_campaign_message(
                            email, phone,
                            [cw.first_name(r.get("customer_name")) or "there", brand,
                             r.get("pitch") or "", r.get("shop_link") or ctx.get("link") or "-"],
                            kind="update")
                    else:
                        whatsapp.send_campaign_message(
                            email, phone,
                            [cw.first_name(r.get("customer_name")) or "there", brand,
                             r.get("pitch") or "", r.get("code") or "",
                             ctx.get("offer_label") or "", ctx.get("expiry_label") or "",
                             r.get("shop_link") or ctx.get("link") or "-"],
                            image_url)
                    entry["whatsapp_sent"] = True
                    n_wa += 1
                except whatsapp.WhatsAppError as e:
                    entry["error"] = str(e)[:160]
                    entry["wa_link"] = campaigns.wa_link(phone, r["message"])
                    n_links += int(bool(entry["wa_link"]))
            else:
                entry["wa_link"] = campaigns.wa_link(phone, r["message"])
                n_links += int(bool(entry["wa_link"]))
        if not reachable:
            skipped += 1
            entry["error"] = entry["error"] or "no phone or email on file"
        results.append(entry)

    stamp = pd.Timestamp.now().isoformat(timespec="seconds")
    delivered = [r for r in results if r["email_sent"] or r["whatsapp_sent"]]
    prepared = [r for r in results if r["wa_link"] and not (r["email_sent"] or r["whatsapp_sent"])]
    by_id = {r["customer_id"]: r for r in draft["rows"]}
    proof_id = None
    # Tap-to-send links are NOT recorded as contacts here. A customer counts as
    # messaged when the seller taps their Send (mark_tapped), one by one, so
    # every number on screen is what actually went out.
    if delivered:
        try:
            proof_id = winback_proof.mark_sent(
                email, [by_id[c["customer_id"]] for c in delivered],
                channel="whatsapp" if n_wa else "email", state="sent",
                note=f"campaign {draft_id}").get("id")
        except Exception as e:  # noqa: BLE001
            log.warning("could not record campaign for measurement: %s", e)
    if delivered or prepared:
        log_rows = campaigns._log(email)  # noqa: SLF001 — same history, one log
        log_rows.append({
            "at": stamp, "brand": brand, "campaign_id": draft_id,
            "reason": draft["reason"], "occasion": draft.get("occasion") or "",
            "offer_label": ctx.get("offer_label") or "", "image_url": image_url,
            "recipients": len(results), "delivered": len(delivered),
            "prepared": len(prepared), "email_sent": n_mail, "whatsapp_sent": n_wa,
            "wa_links": n_links, "skipped": skipped, "channels": list(channels),
            "whatsapp_live": wa_auto, "state": "sent" if delivered else "ready",
        })
        campaigns._save_log(email, log_rows)  # noqa: SLF001
        draft["state"] = "sent"
        draft["sent_at"] = stamp
        draft["proof_id"] = proof_id
        _save_draft(email, draft)
        _save_record(email, draft, results, ctx, channels, wa_auto)

    bits = []
    if n_wa:
        bits.append(f"{n_wa} WhatsApp message{'s' if n_wa != 1 else ''} sent")
    if n_mail:
        bits.append(f"{n_mail} email{'s' if n_mail != 1 else ''} sent")
    if n_links:
        bits.append(f"{n_links} WhatsApp message{'s' if n_links != 1 else ''} ready: tap each "
                    f"one to send it")
    if skipped:
        bits.append(f"{skipped} with no phone or email")
    if sample:
        bits.append(f"{sample} sample customer{'s' if sample != 1 else ''} not emailed")
    summary = (" · ".join(bits) + ".") if bits else "Nothing went out."
    if not (delivered or prepared):
        summary = ("Nothing went out. None of these customers have a phone number or email "
                   "on file. Map those columns when you upload sales, or take orders on "
                   "your website, which collects them for you.")
    return {"sent_at": stamp, "campaign_id": draft_id, "results": results,
            "email_sent": n_mail, "whatsapp_sent": n_wa, "wa_links": n_links,
            "skipped": skipped, "sample": sample, "delivered": len(delivered),
            "prepared": len(prepared), "whatsapp_auto": wa_auto,
            "email_ready": messaging.smtp_configured(),
            "sent_now": len(delivered), "to_send": len(prepared), "summary": summary}


def history(email: str, limit: int = 30) -> list[dict]:
    """Past campaigns, each with what its codes brought back."""
    from backend.core import discounts
    out = []
    recs = _records(email)
    for h in campaigns.history(email, limit):
        cid = h.get("campaign_id")
        rec = recs.get(cid) if cid else None
        sent_n = sum(1 for t in (rec or {}).get("targets") or [] if _is_sent(t, False)) if rec else None
        out.append({**h, "codes": discounts.campaign_stats(email, cid) if cid else None,
                    "tracked": bool(rec), "sent_count": sent_n,
                    "total": len((rec or {}).get("targets") or []) if rec else None,
                    "label": label(h.get("reason") or "winback")})
    return out


# ------------------------------------------------------------------ picks
def _add_picks(txns, profiles: list[dict], names: dict) -> None:
    """For each customer, one thing to suggest: Apriori rules over the shop's
    own orders (analytics.association_rules), what people who bought what they
    bought also buy, that they have not bought themselves. Falls back to the
    shop's best sellers they do not own. Sets `pick_display` (clean name)."""
    from backend.core import analytics
    from backend.core import campaign_writer as cw
    if "product" not in txns.columns or "customer_id" not in txns.columns:
        return
    try:
        rules = analytics.association_rules(txns, "product").get("rules") or {}
    except Exception as e:  # noqa: BLE001 — a suggestion is a nice-to-have
        log.warning("association rules failed: %s", e)
        rules = {}
    sub = txns[["customer_id", "product", "amount"]].dropna(subset=["customer_id", "product"])
    best = (sub.groupby(sub["product"].astype(str))["amount"].sum()
            .sort_values(ascending=False).head(15).index.tolist())
    ids = {str(p.get("customer_id")) for p in profiles}
    sub = sub[sub["customer_id"].astype(str).isin(ids)]
    owned = sub.groupby(sub["customer_id"].astype(str))["product"].agg(
        lambda s: set(map(str, s))).to_dict()
    for p in profiles:
        bought = owned.get(str(p.get("customer_id")), set())
        bought_clean = {cw.clean_product_name(x, names) for x in bought}
        raw = analytics.recommend_for(bought, rules, best)
        pick = cw.clean_product_name(raw, names) if raw else ""
        # "you might also like the Linen Shirt" to someone who bought the blue
        # Linen Shirt reads as if the shop was not paying attention
        if pick and (pick in bought_clean or pick == p.get("product_display")):
            pick = ""
        p["pick_display"] = pick


# ---------------------------------------------------------------- records
def _records(email: str) -> dict:
    r = user_store.get_key(email, RECORDS_KEY, {}) or {}
    return r if isinstance(r, dict) else {}


def _save_record(email: str, draft: dict, results: list[dict], ctx: dict,
                 channels, wa_auto: bool) -> None:
    """What the analyzer needs long after the draft is gone: who was
    messaged on which channel, who was held out, the offer."""
    targets = []
    by_id = {r["customer_id"]: r for r in draft["rows"]}
    for x in results:
        r = by_id.get(x["customer_id"]) or {}
        targets.append({
            "customer_id": x["customer_id"], "customer_name": x.get("customer_name") or "",
            "code": x.get("code") or "", "monetary": r.get("monetary") or 0,
            "whatsapp": "sent" if x.get("whatsapp_sent") else ("tap" if x.get("wa_link") else ""),
            "email": "sent" if x.get("email_sent") else "",
            "wa_link": x.get("wa_link") or "", "tapped_at": "",
        })
    rec = {
        "id": draft["id"], "sent_at": draft.get("sent_at"), "reason": draft["reason"],
        "occasion": draft.get("occasion") or "", "offer": draft.get("offer"),
        "offer_label": ctx.get("offer_label") or "", "symbol": ctx.get("symbol") or "₹",
        "channels": list(channels), "whatsapp_auto": wa_auto,
        "image_url": (draft.get("image") or {}).get("url") or "",
        "link": ctx.get("link") or "", "valid_until": ctx.get("valid_until") or "",
        "targets": targets, "holdout": draft.get("holdout") or [],
        "pending_proof_id": draft.get("pending_proof_id"), "tap_proof_id": None,
    }
    recs = dict(_records(email))
    recs[rec["id"]] = rec
    if len(recs) > MAX_RECORDS:
        for k in sorted(recs, key=lambda k: recs[k].get("sent_at") or "")[:len(recs) - MAX_RECORDS]:
            recs.pop(k, None)
    user_store.set_key(email, RECORDS_KEY, recs)



# ---------------------------------------------------------------- analyzer
WINDOW_DAYS = 30


def records(email: str) -> list[dict]:
    return sorted(_records(email).values(), key=lambda r: r.get("sent_at") or "", reverse=True)


def _pct(a: float, b: float) -> float:
    return round(100.0 * a / b, 1) if b else 0.0


def analyze(email: str, campaign_id: str) -> dict:
    """How one campaign is doing, measured the way a campaign manager would.

    The funnel (each step from the codes themselves):
        messaged -> reached -> opened the link -> used the code -> ordered
    Money: revenue from code orders, discount spent, revenue per unit of
    discount, average order.
    Incrementality: of the customers messaged, how many bought again in the
    window by ANY route (website and uploaded sales alike), against the
    holdout who were not messaged. The difference is what the campaign caused;
    the raw count alone also includes people who were coming back anyway.
    """
    from backend.core import discounts, smart
    rec = _records(email).get(campaign_id)
    if not rec:
        raise CampaignError("That campaign could not be found.")
    by_code = discounts.campaign_codes(email, campaign_id)
    sent = pd.to_datetime(rec.get("sent_at"), errors="coerce")
    days = max(0, int((pd.Timestamp.now() - sent).days)) if not pd.isna(sent) else 0

    targets = rec.get("targets") or []
    # Tap-to-send links only count once the seller confirms they sent them:
    # a link that was never tapped reached nobody.
    taps_confirmed = False
    if rec.get("pending_proof_id"):
        try:
            taps_confirmed = any(r.get("id") == rec["pending_proof_id"] and r.get("state") == "sent"
                                 for r in winback_proof._load(email))  # noqa: SLF001
        except Exception:  # noqa: BLE001
            taps_confirmed = False
    for t in targets:
        t["reached"] = _is_sent(t, taps_confirmed)
    reached = [t for t in targets if t.get("reached")]
    rows, clicked, applied, ordered = [], 0, 0, 0
    revenue = discount = 0.0
    for t in targets:
        c = by_code.get(t.get("code") or "") or {}
        st = {"clicked": bool(c.get("clicked_at")), "applied": bool(c.get("applied_at")),
              "ordered": bool(c.get("redeemed_at"))}
        clicked += st["clicked"]
        applied += st["applied"] or st["ordered"]
        ordered += st["ordered"]
        revenue += float(c.get("order_total") or 0)
        discount += float(c.get("discount_given") or 0)
        rows.append({"customer_id": t["customer_id"], "customer_name": t.get("customer_name") or "",
                     "code": t.get("code") or "", "whatsapp": t.get("whatsapp") or "",
                     "email": t.get("email") or "", "reached": bool(t.get("reached")),
                     "clicks": int(c.get("clicks") or 0), **st,
                     "order_no": c.get("order_no") or "", "order_total": c.get("order_total") or 0,
                     "came_back": False, "spent_since": 0.0})

    hold = rec.get("holdout") or []
    back_ids, spend_by = set(), {}
    try:
        txns = smart.load_sales(email, copy=False)
    except Exception:  # noqa: BLE001
        txns = None
    if txns is not None and len(txns) and not pd.isna(sent) and "customer_id" in txns.columns:
        end = sent + pd.Timedelta(days=WINDOW_DAYS)
        d = pd.to_datetime(txns["date"], errors="coerce")
        win = txns[(d > sent) & (d <= end)]
        if len(win):
            g = win.groupby(win["customer_id"].astype(str))["amount"].sum()
            spend_by = g.to_dict()
            back_ids = set(g.index)
    for r in rows:
        r["came_back"] = r["customer_id"] in back_ids or r["ordered"]
        r["spent_since"] = round(float(spend_by.get(r["customer_id"], 0) or r["order_total"] or 0), 2)
    n_reached = len(reached) or len(rows)
    back_msg = sum(1 for r in rows if r["came_back"] and r["reached"])
    back_hold = sum(1 for h in hold if str(h["customer_id"]) in back_ids)
    rate_msg = _pct(back_msg, n_reached)
    rate_hold = _pct(back_hold, len(hold)) if hold else None
    lift_pts = round(rate_msg - rate_hold, 1) if rate_hold is not None else None
    extra = round((rate_msg - rate_hold) / 100.0 * n_reached, 1) if rate_hold is not None else None

    k = {
        "messaged": len(targets), "reached": len(reached),
        "clicked": clicked, "click_rate": _pct(clicked, n_reached),
        "applied": applied, "orders": ordered, "conversion": _pct(ordered, n_reached),
        "revenue": round(revenue, 2), "discount": round(discount, 2),
        "per_discount": round(revenue / discount, 1) if discount else None,
        "aov": round(revenue / ordered, 2) if ordered else None,
        "came_back": back_msg, "came_back_rate": rate_msg,
        "came_back_revenue": round(sum(r["spent_since"] for r in rows if r["came_back"]), 2),
        "holdout": len(hold), "holdout_back": back_hold, "holdout_rate": rate_hold,
        "lift_pts": lift_pts, "extra_customers": extra,
    }
    return {"campaign": {kk: rec.get(kk) for kk in ("id", "sent_at", "reason", "occasion", "offer_label",
                                                     "symbol", "channels", "whatsapp_auto", "image_url",
                                                     "valid_until", "link")},
            "days_since": days, "window_days": WINDOW_DAYS,
            "kpis": k,
            "funnel": [{"step": "In the campaign", "n": len(targets)},
                       {"step": "Sent", "n": len(reached)},
                       {"step": "Opened the link", "n": clicked},
                       {"step": "Used the code at checkout", "n": applied},
                       {"step": "Ordered", "n": ordered}],
            "customers": sorted(rows, key=lambda r: (not r["ordered"], not r["applied"],
                                                     not r["clicked"], not r["came_back"])),
            "to_send": [{"customer_id": t["customer_id"], "customer_name": t.get("customer_name") or "",
                         "code": t.get("code") or "", "wa_link": t.get("wa_link") or ""}
                        for t in targets if t.get("whatsapp") == "tap" and t.get("wa_link")
                        and not t.get("reached")],
            "diagnosis": _diagnose(k, days, {**rec, "taps_confirmed": taps_confirmed})}


def _diagnose(k: dict, days: int, rec: dict) -> list[str]:
    """Where the funnel leaks, and what a campaign manager would try next."""
    out = []
    if days < 3:
        out.append("It is early: most replies to a campaign come in the first 3 to 5 days. "
                   "Check back then.")
    waiting = k["messaged"] - k["reached"]
    if waiting and any(t.get("whatsapp") == "tap" for t in rec.get("targets") or []):
        out.append(f"{waiting} WhatsApp message{'s are' if waiting != 1 else ' is'} still waiting "
                   f"to be sent. Tap each one below; only the ones you send are counted.")
    if k["reached"] == 0 and not waiting:
        return out + ["Nobody was reached. Add phone numbers or emails for these customers "
                      "and send the next one."]
    if not rec.get("link"):
        out.append("Your website is not published, so nobody can click through or use a code "
                   "online. Publish it and the next campaign can be tracked end to end.")
    elif k["click_rate"] < 10 and days >= 3:
        out.append("Few people opened the link. Put the offer in the first line, use a picture "
                   "of a real product, and send around 11am or 7pm when people read WhatsApp.")
    if k["clicked"] and k["applied"] < k["clicked"] / 3:
        out.append("People opened the shop but did not get to checkout. Check that the products "
                   "they bought before are in stock and easy to find on the home page.")
    if k["applied"] and k["orders"] < k["applied"]:
        out.append("Some added the code but did not finish the order: often delivery cost or a "
                   "minimum order. Consider free delivery for campaign orders.")
    if k["lift_pts"] is not None and days >= 7:
        if k["lift_pts"] > 0:
            out.append(f"It is working: {k['came_back_rate']}% of messaged customers came back "
                       f"against {k['holdout_rate']}% of those held back, about "
                       f"{k['extra_customers']:g} extra customers because of this campaign.")
        else:
            out.append("Messaged customers are not coming back more often than the ones held "
                       "back. Try a bigger offer, or a different reason to write (a festival, a "
                       "new arrival).")
    if k["per_discount"] and k["per_discount"] >= 3:
        out.append(f"Every 1 given away in discount brought back {k['per_discount']:g} in orders.")
    return out


# ------------------------------------------------------------- campaign types
TYPES = [
    {"id": "winback", "label": "Win back quiet customers", "offer": "flat",
     "who": "customers who used to buy and have stopped",
     "why": "People who stopped buying are the cheapest customers to win: they already know you."},
    {"id": "festival", "label": "Festival offer", "offer": "percent", "needs": "occasion",
     "who": "your best customers, plus the ones drifting away",
     "why": "A festival is the most natural reason there is to get in touch."},
    {"id": "second_order", "label": "Second-order nudge", "offer": "flat",
     "who": "first-time buyers from 2 to 8 weeks ago",
     "why": "A customer who orders twice is far more likely to stay. Thank first-time buyers "
            "with a small offer on their next order."},
    {"id": "cross_sell", "label": "Goes well with what you bought", "offer": "percent",
     "who": "customers who have one half of a pair your customers often buy together",
     "why": "Your own orders show which products are bought together. Suggest the matching one "
            "to people who only have half the pair."},
    {"id": "restock", "label": "Time to restock", "offer": "none",
     "who": "customers past their usual time to buy a product again",
     "why": "For things people run out of (attars, skincare, food), a reminder when they are "
            "about due, based on how often they usually buy again."},
    {"id": "vip", "label": "VIP early access", "offer": "none", "needs": "note",
     "who": "your Champions: the customers who buy most, most often",
     "why": "A first look at something new before everyone else. No discount needed: being "
            "first is the reward."},
    {"id": "thank_you", "label": "Thank you + review request", "offer": "none",
     "who": "customers who ordered in the last two weeks",
     "why": "A short thank-you after delivery, asking for a review or a photo. Builds the "
            "reviews that make new customers trust you."},
]


def campaign_types(email: str) -> list[dict]:
    """Every campaign the seller can run, with how many customers each would
    reach right now (before anyone recently contacted is left out)."""
    from backend.core import analytics, smart
    try:
        txns = smart.load_sales(email, copy=False)
        counts = analytics.campaign_counts(txns) if txns is not None else {}
    except Exception as e:  # noqa: BLE001 — a count is never worth a broken screen
        log.warning("campaign counts failed for %s: %s", email, e)
        counts = {}
    return [{**t, "audience": int(counts.get(t["id"]) or 0), "cooldown_days": COOLDOWN[t["id"]]}
            for t in TYPES]


def label(reason: str) -> str:
    return next((t["label"] for t in TYPES if t["id"] == reason), "Campaign")


def _last_bought(txns, profiles: list[dict]) -> dict:
    """{customer_id: product of their most recent purchase} (thank-you)."""
    if "product" not in txns.columns:
        return {}
    ids = {str(p.get("customer_id")) for p in profiles}
    t = txns[txns["customer_id"].astype(str).isin(ids)].dropna(subset=["product"])
    if t.empty:
        return {}
    t = t.assign(_d=pd.to_datetime(t["date"], errors="coerce")).sort_values("_d")
    return t.groupby(t["customer_id"].astype(str))["product"].last().astype(str).to_dict()


# --------------------------------------------------------------- tap-to-send
def _is_sent(t: dict, taps_confirmed: bool = False) -> bool:
    """Did this customer actually get the message? An API or email send, or a
    tap-to-send link the seller tapped. (`taps_confirmed`: campaigns from
    before per-tap tracking, confirmed in one go.)"""
    return bool(t.get("whatsapp") in ("sent", "tapped") or t.get("email") == "sent"
                or (t.get("whatsapp") == "tap" and taps_confirmed))


def mark_tapped(email: str, campaign_id: str, customer_id: str) -> dict:
    """The seller tapped Send for one customer: from now on that customer
    counts as messaged (results, cooldown, the 'came back' measurement)."""
    recs = dict(_records(email))
    rec = recs.get(campaign_id)
    if not rec:
        raise CampaignError("That campaign could not be found.")
    rec = dict(rec)
    targets = [dict(t) for t in rec.get("targets") or []]
    t = next((x for x in targets if x["customer_id"] == str(customer_id)), None)
    if not t:
        raise CampaignError("That customer is not in this campaign.")
    if t.get("whatsapp") == "tap":
        t["whatsapp"] = "tapped"
        t["tapped_at"] = pd.Timestamp.now().isoformat(timespec="seconds")
        person = {"customer_id": t["customer_id"], "customer_name": t.get("customer_name"),
                  "monetary": t.get("monetary") or 0}
        try:
            if rec.get("tap_proof_id"):
                winback_proof.add_targets(email, rec["tap_proof_id"], [person])
            else:
                rec["tap_proof_id"] = winback_proof.mark_sent(
                    email, [person], channel="whatsapp", state="sent",
                    note=f"campaign {campaign_id}: sent by tap").get("id")
        except Exception as e:  # noqa: BLE001 — the count still moves
            log.warning("could not record tapped send: %s", e)
    rec["targets"] = targets
    recs[campaign_id] = rec
    user_store.set_key(email, RECORDS_KEY, recs)
    return {"sent": sum(1 for x in targets if _is_sent(x)), "total": len(targets)}
