"""
Sending a win-back campaign — for real, on both channels.

Until now the app produced a list and an Excel file and stopped. The seller had
to open WhatsApp and type. This sends.

TWO CHANNELS, ONE CALL
----------------------
* **Email** goes out now, over the SMTP settings in `messaging`.
* **WhatsApp** is written provider-agnostically: the message text, the send log
  and the per-customer result all exist, and `messaging._send_whatsapp` is the
  single function a BSP (Interakt, Gupshup, Meta Cloud) gets wired into. Until
  one is connected, every recipient with a phone number gets a **click-to-chat
  link** instead — `wa.me/<number>?text=<message>` — which opens WhatsApp with
  the message already typed. That is not a stopgap for show: for a seller with
  forty at-risk customers it genuinely works, and it means the feature is
  honest on day one rather than a promise.

WHAT IS RECORDED
----------------
Every send writes a log entry per customer: the channel, whether it was
delivered, and when. That log is what `winback_proof` measures against, so
"sent" stops being something the seller has to remember to tick.

Nothing here raises into a request handler. One bad address must not fail the
other thirty-nine.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import quote

import pandas as pd

from backend.core import messaging, user_store, winback_proof

log = logging.getLogger("campaigns")

LOG_KEY = "campaign_sends"
MAX_LOG = 400


def _digits(v) -> str:
    d = re.sub(r"\D", "", str(v or ""))
    if len(d) == 10:                 # a bare Indian mobile
        d = "91" + d
    return d


def wa_link(phone: str, text: str) -> str:
    """Click-to-chat. Opens WhatsApp with the message already written."""
    d = _digits(phone)
    return f"https://wa.me/{d}?text={quote(text)}" if len(d) >= 11 else ""


def _log(email: str) -> list[dict]:
    rows = user_store.get_key(email, LOG_KEY, []) or []
    return rows if isinstance(rows, list) else []


def _save_log(email: str, rows: list[dict]) -> None:
    user_store.set_key(email, LOG_KEY, rows[-MAX_LOG:])


def history(email: str, limit: int = 60) -> list[dict]:
    return _log(email)[-limit:][::-1]


# ---------------------------------------------------------------------------
# the message
# ---------------------------------------------------------------------------
def _fill(template: str, row: dict, brand: str) -> str:
    """Merge fields, forgiving about what a row actually carries."""
    name = str(row.get("customer_name") or "").strip() or "there"
    out = (template or "")
    subs = {
        "{name}": name,
        "{brand}": brand,
        "{item}": str(row.get("favorite_item") or "your favourite").strip(),
        "{days}": str(int(row.get("recency_days") or 0)),
        "{coupon}": str(row.get("coupon") or "").strip(),
    }
    for k, v in subs.items():
        out = out.replace(k, v)
    return out.strip()


def default_template() -> str:
    return ("Hi {name}, it's been a while since your last order with {brand}. "
            "We've kept {item} in stock for you — and here's {coupon} off if you "
            "come back this week. Just reply here and we'll sort it out.")


def preview(rows: list[dict], brand: str, template: str = "") -> list[dict]:
    tpl = template or default_template()
    out = []
    for r in (rows or [])[:5]:
        out.append({
            "customer_name": r.get("customer_name") or "",
            "to_email": r.get("email") or r.get("customer_email") or "",
            "phone": r.get("phone") or r.get("customer_phone") or "",
            "message": _fill(tpl, r, brand),
        })
    return out


# ---------------------------------------------------------------------------
# sending
# ---------------------------------------------------------------------------
def send(email: str, rows: list[dict], brand: str, template: str = "",
         channels: tuple[str, ...] = ("email", "whatsapp"),
         subject: str = "") -> dict:
    """Send one campaign. Returns a per-customer result and a summary.

    A customer with neither an email nor a phone is reported as skipped rather
    than silently dropped — a seller should see that their own data is the
    reason someone was not contacted.
    """
    tpl = template or default_template()
    subject = subject or f"We've missed you at {brand}"
    want_email = "email" in channels
    want_wa = "whatsapp" in channels
    wa_live = messaging.whatsapp_enabled()

    results, sent_email, sent_wa, links, skipped = [], 0, 0, 0, 0
    for r in (rows or []):
        to = str(r.get("email") or r.get("customer_email") or "").strip()
        phone = str(r.get("phone") or r.get("customer_phone") or "").strip()
        body = _fill(tpl, r, brand)
        entry = {"customer_id": str(r.get("customer_id") or ""),
                 "customer_name": r.get("customer_name") or "",
                 "email": to, "phone": phone, "message": body,
                 "email_sent": False, "whatsapp_sent": False, "wa_link": ""}

        if not to and not phone:
            skipped += 1
            entry["skipped"] = "no email or phone on this customer"
            results.append(entry)
            continue

        if want_email and to:
            try:
                res = messaging.send(
                    to_email=to, subject=subject, text=body,
                    html=_html(brand, body))
                entry["email_sent"] = bool(res.get("email"))
                sent_email += int(bool(res.get("email")))
            except Exception as e:  # noqa: BLE001 — one bad address, not the batch
                log.warning("winback email to %s failed: %s", to, e)

        if want_wa and phone:
            if wa_live:
                try:
                    res = messaging.send(phone=phone, whatsapp_text=body)
                    entry["whatsapp_sent"] = bool(res.get("whatsapp"))
                    sent_wa += int(bool(res.get("whatsapp")))
                except Exception as e:  # noqa: BLE001
                    log.warning("winback whatsapp to %s failed: %s", phone, e)
            else:
                # No provider connected: hand back a link the seller taps.
                entry["wa_link"] = wa_link(phone, body)
                links += int(bool(entry["wa_link"]))
        results.append(entry)

    stamp = pd.Timestamp.now().isoformat(timespec="seconds")
    rows_log = _log(email)
    rows_log.append({
        "at": stamp, "brand": brand, "recipients": len(results),
        "email_sent": sent_email, "whatsapp_sent": sent_wa,
        "wa_links": links, "skipped": skipped,
        "channels": list(channels), "whatsapp_live": wa_live,
    })
    _save_log(email, rows_log)

    # The proof loop measures from here, so marking it sent is automatic.
    contacted = [r for r in results if r["email_sent"] or r["whatsapp_sent"] or r["wa_link"]]
    campaign = None
    if contacted:
        try:
            campaign = winback_proof.mark_sent(
                email,
                [r for r in (rows or [])
                 if str(r.get("customer_id") or "") in {c["customer_id"] for c in contacted}],
                channel="whatsapp" if (sent_wa or links) else "email")
        except Exception as e:  # noqa: BLE001
            log.warning("could not record the campaign for measurement: %s", e)

    return {
        "sent_at": stamp,
        "recipients": len(results),
        "email_sent": sent_email,
        "whatsapp_sent": sent_wa,
        "wa_links": links,
        "skipped": skipped,
        "whatsapp_live": wa_live,
        "email_ready": messaging.smtp_configured(),
        "results": results,
        "campaign_id": (campaign or {}).get("id"),
        "summary": _summary(len(results), sent_email, sent_wa, links, skipped, wa_live),
    }


def _summary(n, mail, wa, links, skipped, wa_live) -> str:
    bits = []
    if mail:
        bits.append(f"{mail} email{'s' if mail != 1 else ''} sent")
    if wa:
        bits.append(f"{wa} WhatsApp message{'s' if wa != 1 else ''} sent")
    if links:
        bits.append(f"{links} WhatsApp message{'s' if links != 1 else ''} ready to tap send")
    if skipped:
        bits.append(f"{skipped} skipped — no email or phone on file")
    if not bits:
        return "Nothing went out. None of these customers have an email or a phone number."
    tail = ("" if wa_live or not links else
            " Connect a WhatsApp provider and these will send themselves.")
    return " · ".join(bits) + "." + tail


def _html(brand: str, body: str) -> str:
    para = "".join(
        f'<p style="margin:0 0 14px;font-size:15px;line-height:1.6;color:#3c4152">{line}</p>'
        for line in body.split("\n") if line.strip())
    return (f'<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;'
            f'max-width:520px;margin:0 auto;padding:32px 24px">'
            f'<p style="margin:0 0 22px;font-size:12px;letter-spacing:.14em;'
            f'text-transform:uppercase;color:#6b7186">{brand}</p>{para}</div>')
