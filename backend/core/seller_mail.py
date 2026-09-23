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

import ipaddress
import logging
import re
import smtplib
import socket
import ssl
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

from backend.core import secrets_store, user_store

log = logging.getLogger(__name__)

CONNECTOR = "seller_email"
META_KEY = "seller_email_meta"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# ---------------------------------------------------------------- the guide
# One row per provider a seller can pick in Account > Email, in the order the
# box shows them. THIS IS THE ONLY COPY. The browser used to keep its own host
# table (MAIL_HOSTS in smart.js), so the two drifted; now the browser reads this
# list from GET /api/mail/account and has no table of its own.
#
# Every link and step was checked against the provider's own help page in
# September 2026. When a provider changes its rules, the fix is one row here.
#
# Why steps AND a link: the link saves the seller the hunt (Google in
# particular hides its app-password page from its own menus, so the direct link
# is the only easy way in), and the written steps still work on the day a
# provider moves the page and the link goes stale.
GUIDES: list[dict] = [
    {"id": "gmail", "name": "Gmail", "host": "smtp.gmail.com", "port": 587, "works": True,
     "password_label": "Google app password (16 letters)",
     "link": "https://myaccount.google.com/apppasswords",
     "link_label": "Open Google app passwords",
     "prereq": {"label": "Turn on 2-Step Verification",
                "link": "https://myaccount.google.com/signinoptions/twosv"},
     "steps": [
         "Check that 2-Step Verification is on for this Google account. Google only shows app passwords when it is.",
         "Open Google app passwords with the button below, and sign in if Google asks.",
         "Type a name, for example One Tap Manager, and press Create.",
         "Copy the 16-letter password Google shows and paste it below. Google shows it only once.",
     ]},
    {"id": "workspace", "name": "Google Workspace", "host": "smtp.gmail.com", "port": 587, "works": True,
     "password_label": "Google app password (16 letters)",
     "link": "https://myaccount.google.com/apppasswords",
     "link_label": "Open Google app passwords",
     "prereq": {"label": "Turn on 2-Step Verification",
                "link": "https://myaccount.google.com/signinoptions/twosv"},
     "steps": [
         "Pick this if your shop address (like orders@yourshop.com) is run by Google.",
         "Check that 2-Step Verification is on, then open Google app passwords with the button below.",
         "Type a name, for example One Tap Manager, press Create, and paste the 16-letter password below.",
         "No app passwords option? Whoever set up your Google Workspace has to allow them first.",
     ]},
    {"id": "yahoo", "name": "Yahoo", "host": "smtp.mail.yahoo.com", "port": 587, "works": True,
     "password_label": "Yahoo app password",
     "link": "https://login.yahoo.com/account/security",
     "link_label": "Open Yahoo account security",
     "steps": [
         "Open Yahoo account security with the button below, and sign in if Yahoo asks.",
         "Choose Generate app password (Yahoo sometimes calls it Create app password).",
         "Type a name, for example One Tap Manager, and press Generate.",
         "Copy the password Yahoo shows and paste it below.",
     ]},
    {"id": "zoho", "name": "Zoho Mail", "host": "smtp.zoho.in", "port": 587, "works": True,
     "password_label": "Zoho app password",
     "link": "https://accounts.zoho.in/home#security/app_password",
     "link_label": "Open Zoho app passwords",
     "steps": [
         "Open Zoho app passwords with the button below, and sign in if Zoho asks.",
         "Press Generate New Password and give it a name, for example One Tap Manager.",
         "Copy the password Zoho shows and paste it below.",
         "Indian and international Zoho accounts use different servers. We try both, so you do not need to know which one you have.",
     ]},
    {"id": "icloud", "name": "iCloud", "host": "smtp.mail.me.com", "port": 587, "works": True,
     "password_label": "Apple app-specific password",
     "link": "https://account.apple.com/account/manage",
     "link_label": "Open your Apple Account",
     "steps": [
         "Open your Apple Account with the button below and sign in. Two-factor authentication has to be on.",
         "Go to Sign-In and Security, then App-Specific Passwords.",
         "Press Generate, and name it, for example One Tap Manager.",
         "Copy the password Apple shows (it looks like abcd-efgh-ijkl-mnop) and paste it below.",
     ]},
    {"id": "rediffmail", "name": "Rediffmail", "host": "smtp.rediffmail.com", "port": 587, "works": True,
     "password_label": "Your Rediffmail password",
     "link": "https://mail.rediff.com/",
     "link_label": "Open Rediffmail",
     "steps": [
         "Rediffmail does not use app passwords. You connect with your normal Rediffmail password.",
         "In Rediffmail settings, check that access from other mail apps (POP and SMTP) is turned on.",
         "Paste your Rediffmail password below.",
     ]},
    {"id": "outlook", "name": "Outlook or Hotmail", "host": "smtp-mail.outlook.com", "port": 587,
     "works": False,
     "password_label": "",
     "link": "https://accounts.google.com/signup",
     "link_label": "Make a free Gmail address",
     "note": ("Microsoft stopped letting other apps send from Outlook, Hotmail and Live "
              "addresses with a password in 2026, and app passwords stopped working with it. "
              "Only Microsoft's own sign-in works now, and we do not support that yet. Use a "
              "Gmail or Zoho address to send your orders instead. Setting one up takes about "
              "five minutes."),
     "steps": []},
    {"id": "other", "name": "Other or my own domain", "host": "", "port": 587, "works": True,
     "password_label": "App password",
     "link": "", "link_label": "",
     "steps": [
         "Look for app password in your email account's security settings. Most providers want one instead of your normal password.",
         "If your shop address is run by Google Workspace or Zoho, pick that button above instead. It fills in the right server for you.",
         "Paste the password below, and check the server under Advanced if your provider gave you one.",
     ]},
]
_GUIDE = {g["id"]: g for g in GUIDES}

# Which guide an address belongs to. Anything not listed is "other".
DOMAINS = {
    "gmail.com": "gmail", "googlemail.com": "gmail",
    "yahoo.com": "yahoo", "yahoo.in": "yahoo", "yahoo.co.in": "yahoo",
    "ymail.com": "yahoo", "rocketmail.com": "yahoo",
    "zohomail.in": "zoho", "zoho.com": "zoho", "zohomail.com": "zoho",
    "icloud.com": "icloud", "me.com": "icloud", "mac.com": "icloud",
    "rediffmail.com": "rediffmail",
    "outlook.com": "outlook", "outlook.in": "outlook", "hotmail.com": "outlook",
    "hotmail.co.uk": "outlook", "live.com": "outlook", "live.in": "outlook",
    "msn.com": "outlook",
}

# Zoho runs separate data centres and a login only works against its own
# region's server. A zohomail.in address is Indian; zoho.com and zohomail.com
# are usually international, but an account's region is set when it is created,
# not by its domain, so connect() tries the other server once before giving up.
_ZOHO_REGION = {"zohomail.in": "smtp.zoho.in", "zoho.com": "smtp.zoho.com",
                "zohomail.com": "smtp.zoho.com"}
_ZOHO_HOSTS = ("smtp.zoho.in", "smtp.zoho.com")

# Microsoft's servers refuse every password since March-April 2026, app
# passwords included. A business domain on Microsoft 365 points here too, so the
# refusal is by server as well as by address.
_MICROSOFT_HOSTS = {"smtp-mail.outlook.com", "smtp.office365.com", "smtp.live.com"}

# Ports a real mail server listens on. See _public_host_or_raise.
_MAIL_PORTS = {25, 465, 587, 2525}

# The hosts named in this file. They are public by construction, so they skip
# the DNS check (which also keeps the tests from needing a network).
_KNOWN_HOSTS = {g["host"] for g in GUIDES if g["host"]} | set(_ZOHO_HOSTS)

# Kept for anything that still reads the old shape: host, port and name by domain.
PROVIDERS = {dom: {"host": _ZOHO_REGION.get(dom, _GUIDE[gid]["host"]),
                   "port": _GUIDE[gid]["port"], "name": _GUIDE[gid]["name"]}
             for dom, gid in DOMAINS.items()}
DEFAULT_HELP = ("Most providers need an app password rather than your normal one. "
                "Look for app password in your email account's security settings.")


class _Refused(ValueError):
    """Refused before or instead of a login, with the words to show the seller."""


def _guide_view(gid: str, address: str = "") -> dict:
    """A copy of one guide, filled in for this address (server, region link)."""
    g = dict(_GUIDE.get(gid) or _GUIDE["other"])
    domain = str(address or "").split("@")[-1].strip().lower()
    if g["id"] == "zoho" and domain in _ZOHO_REGION:
        g["host"] = _ZOHO_REGION[domain]
        if g["host"].endswith(".com"):
            g["link"] = "https://accounts.zoho.com/home#security/app_password"
    if g["id"] == "other":
        g["host"] = f"smtp.{domain}" if domain else ""
    return g


def providers() -> list[dict]:
    """The guides the Account box shows, in order. Public, and safe to send."""
    return [_guide_view(g["id"]) for g in GUIDES]


def guess(address: str) -> dict:
    """SMTP host and port for an address, plus what to tell the seller."""
    domain = str(address or "").split("@")[-1].strip().lower()
    gid = DOMAINS.get(domain, "other")
    g = _guide_view(gid, address)
    known = gid != "other"
    help_text = g.get("note") or (" ".join(g["steps"][:2]) if known else DEFAULT_HELP)
    return {"host": g["host"], "port": g["port"],
            "provider": g["name"] if known else (domain or ""),
            "provider_id": gid, "works": g["works"], "help": help_text,
            "known": known, "guide": g}


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


def _public_host_or_raise(host: str, port: int) -> None:
    """Refuse anything that is not a public mail server, before a socket opens.

    THE HOLE THIS CLOSES: the seller types the server and port, and this file
    connects to them. Pointed at 127.0.0.1 or a private address, it would
    connect (verified), which let any signed-up account knock on internal ports
    and tell open from closed by the answer. Nothing leaked back, because every
    smtplib error is an OSError and collapses into one fixed message, but a
    probe is a probe. So: mail ports only, and a host typed by the seller must
    resolve only to public addresses. The hosts this file names itself skip the
    lookup, since they are public by construction.

    Known limit: a DNS answer can change between this check and the connect.
    Accepted, because nothing from the far end is ever shown back.
    """
    if int(port) not in _MAIL_PORTS:
        raise _Refused(f"Port {port} is not a mail port. Use 587, or 465 if 587 is blocked.")
    host = (host or "").strip().lower()
    if not host:
        raise _Refused("Add the mail server under Advanced. Your email provider lists it in its help pages.")
    if host in _KNOWN_HOSTS:
        return
    try:
        infos = socket.getaddrinfo(host, int(port), type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError):
        raise _Refused(f"Could not find a mail server called {host}. Check the server under Advanced.")
    for info in infos:
        ip = ipaddress.ip_address(str(info[4][0]).split("%")[0])
        if not ip.is_global or ip.is_multicast:
            raise _Refused("That is not a public mail server. Use the server your email "
                           "provider gives you, for example smtp.gmail.com.")


def _client(creds: dict):
    host, port = creds.get("host") or "", int(creds.get("port") or 587)
    _public_host_or_raise(host, port)
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
    """Say what to do, not what the library said.

    ORDER MATTERS. Every smtplib error subclasses OSError, so the OSError branch
    has to come after the specific SMTP classes. It used to come first, which
    meant the SMTPRecipientsRefused branch could never run.
    """
    if isinstance(exc, _Refused):
        return str(exc)
    g = guess(creds.get("address", ""))
    text = str(exc)
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        if "5.7.139" in text or "basic authentication is disabled" in text.lower():
            return _GUIDE["outlook"]["note"]
        name = g["provider"] if g["known"] else "Your email provider"
        fix = (f" Make a new one here: {g['guide']['link']}"
               if g["guide"].get("link") and g["known"] else f" {DEFAULT_HELP}")
        kind = g["guide"].get("password_label") or "app password"
        return (f"{name} refused that password. Paste the {kind.lower()}, "
                f"not the password you sign in with.{fix}")
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return "Your provider refused the address this was going to."
    if isinstance(exc, (smtplib.SMTPConnectError, OSError, TimeoutError)):
        return (f"Could not reach {creds.get('host')} on port {creds.get('port')}. "
                "Check the server under Advanced, or try port 465.")
    return f"{type(exc).__name__}: {exc}"[:200]


def _deliver_test(creds: dict) -> None:
    with _client(creds) as s:
        msg = EmailMessage()
        msg["Subject"] = "Your purchase orders will come from this address"
        msg["From"] = formataddr((creds["display_name"] or creds["address"], creds["address"]))
        msg["To"] = creds["address"]
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid()
        msg.set_content(
            "This is the test that connected your email.\n\n"
            "From now on, when you approve a purchase order it is sent from this "
            "address, with the order attached as a PDF, and your supplier's reply "
            "comes straight back to you here.\n")
        s.send_message(msg)


def _deliver_with_region_fallback(creds: dict) -> None:
    """Send the test; for Zoho, try the other region's server once.

    Only ever between the two Zoho servers, never to a guessed host, so the
    password is not sent anywhere the seller did not choose.
    """
    try:
        _deliver_test(creds)
    except smtplib.SMTPAuthenticationError:
        host = (creds.get("host") or "").lower()
        if host not in _ZOHO_HOSTS:
            raise
        creds["host"] = _ZOHO_HOSTS[1] if host == _ZOHO_HOSTS[0] else _ZOHO_HOSTS[0]
        _deliver_test(creds)


def _log_attempt(email: str, g: dict, creds: dict, ok: bool, err: Exception | None = None) -> None:
    """One line per connect, so "my email will not connect" can be answered later.

    Never the password, never what the far server said: provider, server, port,
    and the kind of failure is enough to tell a wrong password from Outlook from
    a blocked port.
    """
    log.info("seller mail connect account=%s provider=%s host=%s port=%s ok=%s error=%s",
             email, g.get("provider_id") or g.get("id") or "?", creds.get("host"),
             creds.get("port"), ok, "" if ok else type(err).__name__)


def connect(email: str, address: str, password: str, host: str = "", port: int = 0,
            display_name: str = "", provider: str = "") -> dict:
    """Save the account, but only after a real login and a real test mail.

    The test goes to the seller's own address, so "connected" is something they
    can see in their inbox rather than something this app claims.

    `provider` is the button the seller picked. It matters for an address on
    their own domain: orders@yourshop.com run by Google Workspace needs
    smtp.gmail.com, which nothing about the address itself says.
    """
    address = str(address or "").strip()
    if not _EMAIL_RE.match(address):
        raise ValueError("That does not look like an email address.")
    if not password:
        raise ValueError("Paste the app password from your email provider.")
    g = guess(address)
    if provider in _GUIDE and provider != g["provider_id"]:
        picked = _guide_view(provider, address)
        g = {**g, "provider_id": provider, "provider": picked["name"], "known": provider != "other",
             "works": picked["works"], "guide": picked, "host": picked["host"] or g["host"]}
    creds = {"address": address, "password": password,
             "host": (host or g["host"]).strip().lower(), "port": int(port or g["port"]),
             "display_name": str(display_name or "").strip()[:80]}
    try:
        if not g["works"] or creds["host"] in _MICROSOFT_HOSTS:
            raise _Refused(_GUIDE["outlook"]["note"])
        _deliver_with_region_fallback(creds)
    except Exception as e:  # noqa: BLE001 — every failure is the seller's to read
        reason = _friendly(e, creds)
        _log_attempt(email, g, creds, ok=False, err=e)
        user_store.set_key(email, META_KEY, {"error": reason, "provider": g["provider"]})
        raise ValueError(reason)
    _log_attempt(email, g, creds, ok=True)
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
