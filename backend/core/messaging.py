"""
Outbound messages — one door for everything the app sends a human.

Two channels behind one function:

  * EMAIL, live now. Configure SMTP_HOST / SMTP_PORT / SMTP_USER /
    SMTP_PASSWORD / SMTP_FROM (and SMTP_TLS=false for a plain relay). With no
    SMTP_HOST set, sends are recorded to the outbox instead of raised — so a
    dev box, and a first deploy without credentials, never 500 on a password
    reset. The outbox is readable at /api/dev/outbox for exactly that reason.

  * WHATSAPP, stubbed behind WHATSAPP_ENABLED. Indian sellers and their
    shoppers live on WhatsApp, not email, so every message here already carries
    a `whatsapp` variant of its text. The moment a BSP (Gupshup, Interakt,
    Meta Cloud API) is connected, implement `_send_whatsapp` and flip the flag:
    no caller changes, because callers ask for a MESSAGE, not a channel.

Nothing in here raises into a request handler. A failed send is logged and
reported back as a boolean — a digest that could not go out must never take
down the page that triggered it.
"""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

log = logging.getLogger("messaging")

BRAND = os.environ.get("BRAND_NAME", "One Tap Manager")
APP_URL = (os.environ.get("APP_BASE_URL") or "http://localhost:8000").rstrip("/")

# Sends that had nowhere to go. Bounded — this is a dev aid, not a queue.
_OUTBOX: list[dict] = []
_OUTBOX_MAX = 60


def smtp_configured() -> bool:
    return bool(os.environ.get("SMTP_HOST"))


def whatsapp_enabled() -> bool:
    return os.environ.get("WHATSAPP_ENABLED", "").strip().lower() in ("1", "true", "yes", "on")


def outbox(limit: int = 30) -> list[dict]:
    return _OUTBOX[-limit:][::-1]


def _remember(kind: str, to: str, subject: str, body: str, reason: str) -> None:
    _OUTBOX.append({"channel": kind, "to": to, "subject": subject,
                    "body": body, "reason": reason})
    del _OUTBOX[:-_OUTBOX_MAX]


# ---------------------------------------------------------------------------
# channels
# ---------------------------------------------------------------------------
def _send_email(to: str, subject: str, text: str, html: str = "") -> bool:
    if not smtp_configured():
        _remember("email", to, subject, text, "SMTP_HOST not set")
        log.info("email to %s not sent (no SMTP configured): %s", to, subject)
        return False

    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT") or 587)
    user = os.environ.get("SMTP_USER") or ""
    password = os.environ.get("SMTP_PASSWORD") or ""
    sender = os.environ.get("SMTP_FROM") or user or "no-reply@onetapmanager.app"
    use_tls = (os.environ.get("SMTP_TLS", "true").strip().lower()
               not in ("false", "0", "no"))

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((BRAND, sender))
    msg["To"] = to
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(),
                                  timeout=20) as s:
                if user:
                    s.login(user, password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as s:
                if use_tls:
                    s.starttls(context=ssl.create_default_context())
                if user:
                    s.login(user, password)
                s.send_message(msg)
        return True
    except Exception as e:  # noqa: BLE001 — a send must never break a request
        log.warning("email to %s failed: %s", to, e)
        _remember("email", to, subject, text, f"send failed: {e}")
        return False


def _send_whatsapp(phone: str, text: str) -> bool:
    """Not wired yet — see the module docstring.

    When a BSP is connected this becomes one POST. Everything above it already
    passes a WhatsApp-shaped message, so nothing else in the app changes.
    """
    _remember("whatsapp", phone, "", text, "WhatsApp sender not implemented yet")
    log.info("whatsapp to %s queued (no provider connected)", phone)
    return False


def send(to_email: str = "", subject: str = "", text: str = "", html: str = "",
         phone: str = "", whatsapp_text: str = "") -> dict:
    """Deliver one message on every channel we have an address for.

    Returns {email: bool, whatsapp: bool, delivered: bool} — `delivered` is
    true when at least one channel accepted it.
    """
    out = {"email": False, "whatsapp": False}
    if to_email and subject:
        out["email"] = _send_email(to_email, subject, text, html)
    if phone and whatsapp_enabled():
        out["whatsapp"] = _send_whatsapp(phone, whatsapp_text or text)
    out["delivered"] = out["email"] or out["whatsapp"]
    return out


# ---------------------------------------------------------------------------
# the messages themselves
# ---------------------------------------------------------------------------
def _shell(title: str, lines: list[str], cta_label: str = "", cta_url: str = "") -> str:
    body = "".join(
        f'<p style="margin:0 0 14px;font-size:15px;line-height:1.6;color:#3c4152">{l}</p>'
        for l in lines)
    button = (
        f'<a href="{cta_url}" style="display:inline-block;margin-top:8px;padding:12px 22px;'
        f'background:#3a4a86;color:#fff;text-decoration:none;border-radius:4px;'
        f'font-size:14px;font-weight:600">{cta_label}</a>' if cta_label and cta_url else "")
    return (
        f'<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;'
        f'max-width:520px;margin:0 auto;padding:32px 24px">'
        f'<p style="margin:0 0 22px;font-size:12px;letter-spacing:.14em;text-transform:uppercase;'
        f'color:#6b7186">{BRAND}</p>'
        f'<h1 style="margin:0 0 18px;font-size:24px;line-height:1.25;color:#171922">{title}</h1>'
        f'{body}{button}'
        f'<p style="margin:28px 0 0;padding-top:18px;border-top:1px solid #e7e9f1;'
        f'font-size:12px;color:#8d93a6">If you did not expect this email you can ignore it.</p>'
        f'</div>')


def send_password_reset(to_email: str, reset_url: str, who: str = "",
                        store_name: str = "", phone: str = "") -> dict:
    """One reset mail for both audiences: a seller, or a shopper on a seller's
    store. `store_name` picks which voice it speaks in."""
    brand = store_name or BRAND
    hello = f"Hi {who}," if who else "Hi,"
    lines = [
        hello,
        f"Someone asked to reset the password for your {brand} account. "
        f"The link below works once and expires in 60 minutes.",
        f'<a href="{reset_url}" style="color:#3a4a86">{reset_url}</a>',
    ]
    text = (f"{hello}\n\nReset your {brand} password using this link "
            f"(valid for 60 minutes, single use):\n\n{reset_url}\n\n"
            f"If you did not ask for this, ignore this email — nothing changes.")
    return send(
        to_email=to_email,
        subject=f"Reset your {brand} password",
        text=text,
        html=_shell(f"Reset your {brand} password", lines, "Set a new password", reset_url),
        phone=phone,
        whatsapp_text=f"{brand}: reset your password here (valid 60 min): {reset_url}",
    )


def send_digest(to_email: str, items: list[dict], seller_name: str = "",
                phone: str = "") -> dict:
    """The thing that arrives without opening the app.

    `items` are the same rows the Today strip renders — one shape, two
    surfaces, so the digest can never disagree with the home screen.
    """
    if not items:
        return {"email": False, "whatsapp": False, "delivered": False}

    hello = f"Morning{', ' + seller_name if seller_name else ''} —"
    lines = [hello, "Three things worth your time today."]
    for it in items[:6]:
        lines.append(
            f'<b style="color:#171922">{it.get("title", "")}</b><br>'
            f'<span style="color:#6b7186">{it.get("detail", "")}</span>')

    plain = [hello, ""]
    for it in items[:6]:
        plain.append(f"• {it.get('title','')} — {it.get('detail','')}")
    plain.append("")
    plain.append(f"Open {BRAND}: {APP_URL}/app")

    wa = f"*{BRAND}* — today\n\n" + "\n".join(
        f"• {it.get('title','')}: {it.get('detail','')}" for it in items[:6]
    ) + f"\n\n{APP_URL}/app"

    return send(
        to_email=to_email,
        subject=f"{len(items)} things worth your time today",
        text="\n".join(plain),
        html=_shell("Today", lines, f"Open {BRAND}", f"{APP_URL}/app"),
        phone=phone,
        whatsapp_text=wa,
    )


def send_order_update(to_email: str, order_no: str, status_label: str,
                      store_name: str, track_url: str = "", phone: str = "") -> dict:
    lines = [f"Your order <b>{order_no}</b> is now <b>{status_label.lower()}</b>."]
    if track_url:
        lines.append(f'<a href="{track_url}" style="color:#3a4a86">Track it here</a>')
    text = f"{store_name}: order {order_no} is now {status_label.lower()}."
    if track_url:
        text += f"\n\nTrack it: {track_url}"
    return send(
        to_email=to_email,
        subject=f"{store_name} — order {order_no} is {status_label.lower()}",
        text=text,
        html=_shell(f"Order {order_no}", lines,
                    "Track your order" if track_url else "", track_url),
        phone=phone,
        whatsapp_text=text,
    )
