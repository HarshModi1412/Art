"""
The seller's own email account, used to send their purchase orders.

WHY THIS EXISTS
---------------
A purchase order that arrives from `no-reply@someapp` is an order from a
stranger. The supplier already knows the seller's address — it is the one on
their WhatsApp, their invoices, the last twenty orders — and that is the
address the PO has to come from, or it gets treated as spam and nobody rings
to confirm.

Before this, sending went through one mailbox configured on the server
(SMTP_HOST and friends). That is right for password resets, which are from the
app. It is wrong for a purchase order, which is from the shop.

HOW IT WORKS
  * The seller connects their email once: address + an app password from their
    provider. The host and port are worked out from the address (Gmail,
    Outlook, Yahoo, Zoho, iCloud, Rediff), with an override for a business
    domain that uses something else.
  * Credentials are encrypted at rest with the same Fernet key as every other
    third-party credential (backend/core/secrets_store.py) and never leave the
    server; the app never shows them again after saving.
  * Connecting runs a real login and a real send to the seller's own address,
    so "connected" means a mail actually went out — not that a form was filled.
  * The server mailbox stays the fallback, for accounts that have not connected
    one. Which was used is reported, so nobody is left guessing.

WHAT THIS IS NOT: reading the seller's mail. This is send-only (SMTP). Watching
for a supplier's reply needs IMAP and is a separate decision.
"""
from __future__ import annotations

import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

from backend.core import secrets_store, user_store

CONNECTOR = "seller_email"
META_KEY = "seller_email_meta"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# The providers a small Indian seller actually uses, and what their SMTP wants.
PROVIDERS = {
    "gmail.com": {"host": "smtp.gmail.com", "port": 587, "name": "Gmail",
                  "help": "Google account → Security → 2-Step Verification on → App passwords → "
                          "create one and paste the 16 characters here."},
    "googlemail.com": {"host": "smtp.gmail.com", "port": 587, "name": "Gmail"},
    "outlook.com": {"host": "smtp-mail.outlook.com", "port": 587, "name": "Outlook"},
    "hotmail.com": {"host": "smtp-mail.outlook.com", "port": 587, "name": "Outlook"},
    "live.com": {"host": "smtp-mail.outlook.com", "port": 587, "name": "Outlook"},
    "yahoo.com": {"host": "smtp.mail.yahoo.com", "port": 587, "name": "Yahoo"},
    "yahoo.in": {"host": "smtp.mail.yahoo.com", "port": 587, "name": "Yahoo"},
    "zoho.com": {"host": "smtp.zoho.in", "port": 587, "name": "Zoho"},
    "zohomail.in": {"host": "smtp.zoho.in", "port": 587, "name": "Zoho"},
    "icloud.com": {"host": "smtp.mail.me.com", "port": 587, "name": "iCloud"},
    "me.com": {"host": "smtp.mail.me.com", "port": 587, "name": "iCloud"},
    "rediffmail.com": {"host": "smtp.rediffmail.com", "port": 587, "name": "Rediffmail"},
}
DEFAULT_HELP = ("Most providers need an app password rather than your normal one. "
                "Look for “app password” in your email account's security settings.")


def guess(address: str) -> dict:
    """SMTP host and port for an address, plus what to tell the seller."""
    domain = str(address or "").split("@")[-1].strip().lower()
    p = PROVIDERS.get(domain)
    if p:
        return {"host": p["host"], "port": p["port"], "provider": p["name"],
                "help": p.get("help", DEFAULT_HELP), "known": True}
    # A business domain usually publishes mail.<domain> or smtp.<domain>. It is
    # a guess, so it is shown in an editable field rather than used silently.
    return {"host": f"smtp.{domain}" if domain else "", "port": 587,
            "provider": domain or "", "help": DEFAULT_HELP, "known": False}


def status(email: str) -> dict:
    """What the app may show about the connection. Never the password."""
    meta = user_store.get_key(email, META_KEY, {}) or {}
    creds = secrets_store.get_credentials(email, CONNECTOR) or {}
    if not creds.get("address"):
        return {"connected": False, "address": "", "host": "", "provider": "",
                "checked_at": "", "error": meta.get("error", "")}
    return {"connected": True, "address": creds.get("address", ""),
            "host": creds.get("host", ""), "port": creds.get("port", 587),
            "provider": meta.get("provider", ""), "checked_at": meta.get("checked_at", ""),
            "error": meta.get("error", "")}


def _client(creds: dict):
    host, port = creds.get("host") or "", int(creds.get("port") or 587)
    if port == 465:
        s = smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=25)
    else:
        s = smtplib.SMTP(host, port, timeout=25)
        s.ehlo()
        s.starttls(context=ssl.create_default_context())
        s.ehlo()
    s.login(creds.get("address") or creds.get("user") or "", creds.get("password") or "")
    return s


def _friendly(exc: Exception, creds: dict) -> str:
    """Say what to do, not what the library said."""
    g = guess(creds.get("address", ""))
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return (f"{g['provider'] or 'Your email provider'} refused that password. "
                f"{g['help']}")
    if isinstance(exc, (smtplib.SMTPConnectError, OSError, TimeoutError)):
        return (f"Could not reach {creds.get('host')} on port {creds.get('port')}. "
                "Check the server address, or try port 465.")
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return "Your provider refused the address this was going to."
    return f"{type(exc).__name__}: {exc}"[:200]


def connect(email: str, address: str, password: str, host: str = "", port: int = 0,
            display_name: str = "") -> dict:
    """Save the account — but only after a real login and a real test mail.

    The test goes to the seller's own address, so "connected" is something they
    can see in their inbox rather than something this app claims."""
    address = str(address or "").strip()
    if not _EMAIL_RE.match(address):
        raise ValueError("That does not look like an email address.")
    if not password:
        raise ValueError("Paste the app password from your email provider.")
    g = guess(address)
    creds = {"address": address, "password": password,
             "host": (host or g["host"]).strip(), "port": int(port or g["port"]),
             "display_name": str(display_name or "").strip()[:80]}
    try:
        with _client(creds) as s:
            msg = EmailMessage()
            msg["Subject"] = "Your purchase orders will come from this address"
            msg["From"] = formataddr((creds["display_name"] or address, address))
            msg["To"] = address
            msg["Date"] = formatdate(localtime=True)
            msg["Message-ID"] = make_msgid()
            msg.set_content(
                "This is the test that connected your email.\n\n"
                "From now on, when you approve a purchase order it is sent from this "
                "address, with the order attached as a PDF, and your supplier's reply "
                "comes straight back to you here.\n")
            s.send_message(msg)
    except Exception as e:  # noqa: BLE001 — every failure is the seller's to read
        reason = _friendly(e, creds)
        user_store.set_key(email, META_KEY, {"error": reason, "provider": g["provider"]})
        raise ValueError(reason)
    secrets_store.save_connection(email, CONNECTOR, creds, {"address": address})
    user_store.set_key(email, META_KEY, {
        "provider": g["provider"], "error": "",
        "checked_at": __import__("datetime").datetime.now().isoformat(timespec="seconds")})
    return status(email)


def disconnect(email: str) -> dict:
    secrets_store.delete_connection(email, CONNECTOR)
    user_store.set_key(email, META_KEY, {})
    return status(email)


def send(email: str, to: str, subject: str, text: str,
         attachments: list | None = None) -> dict:
    """Send as the seller. Returns {sent, from, reason} and never raises.

    No Reply-To: the mail IS from them, so a reply goes to their inbox by
    itself — which is also what makes a supplier's reply findable later."""
    creds = secrets_store.get_credentials(email, CONNECTOR) or {}
    if not creds.get("address"):
        return {"sent": False, "from": "", "reason": "no seller mailbox connected"}
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((creds.get("display_name") or creds["address"], creds["address"]))
    msg["To"] = to
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    msg.set_content(text)
    for att in attachments or []:
        fname, data, mime = att
        maintype, _, subtype = (mime or "application/octet-stream").partition("/")
        msg.add_attachment(data, maintype=maintype, subtype=subtype or "octet-stream",
                           filename=fname)
    try:
        with _client(creds) as s:
            s.send_message(msg)
    except Exception as e:  # noqa: BLE001
        reason = _friendly(e, creds)
        meta = user_store.get_key(email, META_KEY, {}) or {}
        user_store.set_key(email, META_KEY, {**meta, "error": reason})
        return {"sent": False, "from": creds["address"], "reason": reason}
    meta = user_store.get_key(email, META_KEY, {}) or {}
    if meta.get("error"):
        user_store.set_key(email, META_KEY, {**meta, "error": ""})
    return {"sent": True, "from": creds["address"], "reason": "",
            "message_id": msg["Message-ID"]}
