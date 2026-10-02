"""
WhatsApp for a seller: the number they send from, and — when they connect it —
automatic sending through Meta's WhatsApp Cloud API.

TWO LEVELS, BOTH REAL
---------------------
1. **Tap-to-send.** The seller saves the WhatsApp number they use for the shop.
   Every campaign message becomes a link that opens WhatsApp with the text
   already typed; they tap send. Works the minute the number is saved, with no
   Meta account at all. Fine for a few dozen customers.

2. **Automatic.** WhatsApp only lets a business message customers who have not
   written to it in the last 24 hours through the official Business Platform,
   with a message TEMPLATE Meta has approved. So connecting means three values
   from the seller's Meta app (Phone Number ID, WhatsApp Business Account ID,
   a permanent access token). We check them, submit this app's campaign
   template to Meta for approval, and once Meta approves it, approving a
   campaign sends every WhatsApp message by itself, picture included.

THE TEMPLATE
------------
One template per seller, written so Meta's reviewers pass it: a picture
header, a body with numbered variables never at the very start or end, and an
opt-out footer. Variable values may not contain newlines, so the API path uses
a one-line pitch per customer (campaign_writer) rather than the full message.

The access token is stored encrypted (secrets_store). Nothing in here raises
into a request handler without a message a seller can act on.
"""
from __future__ import annotations

import io
import logging
import os
import re
from datetime import datetime

import requests

from backend.core import secrets_store, user_store

log = logging.getLogger("whatsapp")

CFG_KEY = "whatsapp_config"
CONNECTOR = "whatsapp_cloud"
GRAPH = "https://graph.facebook.com/" + os.environ.get("WHATSAPP_GRAPH_VERSION", "v21.0")
TEMPLATE_NAME = "otm_campaign_offer_v1"
TEMPLATE_TEXT_NAME = "otm_campaign_offer_text_v1"
TIMEOUT = 25

TEMPLATE_BODY = (
    "Hi {{1}}, {{2}} has something for you.\n\n"
    "{{3}}\n\n"
    "Your personal code *{{4}}* gives you {{5}}. Valid till {{6}}.\n\n"
    "Shop here: {{7}} (the code applies automatically)."
)
TEMPLATE_FOOTER = "Reply STOP to stop offers from us"
EXAMPLE = ["Priya", "Rang Studio",
           "It has been a while, and we saved something special for your next order.",
           "PRIYA-7K2PQ", "Rs 200 off", "16 Oct",
           "https://onetapmanager.com/s/rangstudio?code=PRIYA-7K2PQ"]


class WhatsAppError(Exception):
    """Something the seller needs to fix, said plainly."""


# ------------------------------------------------------------------ config
def _cfg(email: str) -> dict:
    c = user_store.get_key(email, CFG_KEY, {}) or {}
    return c if isinstance(c, dict) else {}


def _save_cfg(email: str, patch: dict) -> dict:
    c = {**_cfg(email), **patch}
    user_store.set_key(email, CFG_KEY, c)
    return c


def _token(email: str) -> str:
    try:
        return (secrets_store.get_credentials(email, CONNECTOR) or {}).get("token") or ""
    except Exception:  # noqa: BLE001 — a key rotation must not 500 the page
        return ""


def digits(phone, default_cc: str = "") -> str:
    d = re.sub(r"\D", "", str(phone or ""))
    if d.startswith("00"):
        d = d[2:]
    if len(d) == 11 and d.startswith("0") and default_cc == "91":
        d = d[1:]
    if len(d) == 10 and default_cc:
        d = default_cc + d
    return d


def default_cc(email: str) -> str:
    """Country code for bare 10-digit numbers, from the shop's currency."""
    try:
        from backend.core import sitebuilder
        ccy = ((sitebuilder.get_site(email) or {}).get("commerce") or {}).get("currency") or ""
    except Exception:  # noqa: BLE001
        ccy = ""
    return {"INR": "91", "USD": "1", "CAD": "1"}.get(str(ccy).upper(), "91")


def save_number(email: str, number: str) -> dict:
    d = digits(number, default_cc(email))
    if not (10 <= len(d) <= 15):
        raise WhatsAppError("Enter the full WhatsApp number, with country code (e.g. +91 98765 43210).")
    _save_cfg(email, {"number": d, "number_saved_at": datetime.now().isoformat(timespec="seconds")})
    return status(email)


# ------------------------------------------------------------------- graph
def _req(method: str, path: str, token: str, **kw) -> dict:
    url = path if path.startswith("http") else f"{GRAPH}/{path.lstrip('/')}"
    headers = {"Authorization": f"Bearer {token}", **(kw.pop("headers", {}) or {})}
    try:
        r = requests.request(method, url, headers=headers, timeout=TIMEOUT, **kw)
    except requests.RequestException as e:
        raise WhatsAppError(f"Could not reach WhatsApp just now ({e.__class__.__name__}). Try again.")
    try:
        body = r.json()
    except ValueError:
        body = {}
    if r.status_code >= 400 or (isinstance(body, dict) and body.get("error")):
        err = (body or {}).get("error") or {}
        msg = err.get("error_user_msg") or err.get("message") or f"HTTP {r.status_code}"
        code = err.get("code")
        if code in (190, 102) or r.status_code == 401:
            msg = "That access token is not valid or has expired. Create a permanent (System User) token and paste it again."
        raise WhatsAppError(f"WhatsApp said: {msg}")
    return body if isinstance(body, dict) else {}


def connect(email: str, phone_number_id: str, waba_id: str, token: str) -> dict:
    """Check the three values against Meta, store them, submit the template."""
    pnid = re.sub(r"\D", "", phone_number_id or "")
    waba = re.sub(r"\D", "", waba_id or "")
    token = (token or "").strip()
    if not (pnid and waba and token):
        raise WhatsAppError("All three are needed: Phone Number ID, WhatsApp Business Account ID and the access token.")
    info = _req("GET", f"{pnid}", token,
                params={"fields": "display_phone_number,verified_name,quality_rating"})
    secrets_store.save_connection(email, CONNECTOR, {"token": token},
                                  {"connected_at": datetime.now().isoformat(timespec="seconds")})
    shown = info.get("display_phone_number") or ""
    _save_cfg(email, {
        "phone_number_id": pnid, "waba_id": waba,
        "display_number": shown, "verified_name": info.get("verified_name") or "",
        "number": _cfg(email).get("number") or digits(shown),
        "connected_at": datetime.now().isoformat(timespec="seconds"),
        "template": "", "template_status": "", "template_error": "",
    })
    try:
        submit_template(email)
    except WhatsAppError as e:
        _save_cfg(email, {"template_error": str(e)})
    return status(email)


# ------------------------------------------------------- Embedded Signup
# The way a non-technical seller connects: Meta's own popup. They log in with
# Facebook, pick or create their business, and confirm their number with an
# SMS code. We get back a short-lived code plus the account and number ids,
# and do the rest here. Until Meta approves this app as a Tech Provider, only
# people with a role on the app (testers, added by the platform admin, exactly
# like Instagram) can complete it.
#
# Admin env, once:
#   WHATSAPP_APP_ID      the Meta app's App ID (Settings -> Basic)
#   WHATSAPP_APP_SECRET  its App Secret
#   WHATSAPP_CONFIG_ID   Facebook Login for Business -> Configurations ->
#                        a "WhatsApp Embedded Signup" configuration
def embedded_config() -> dict:
    app_id = (os.environ.get("WHATSAPP_APP_ID") or "").strip()
    cfg = (os.environ.get("WHATSAPP_CONFIG_ID") or "").strip()
    secret = (os.environ.get("WHATSAPP_APP_SECRET") or "").strip()
    return {"available": bool(app_id and cfg and secret), "app_id": app_id, "config_id": cfg,
            "graph_version": GRAPH.rsplit("/", 1)[-1]}


def complete_embedded(email: str, code: str, waba_id: str = "", phone_number_id: str = "",
                      coexistence: bool = False) -> dict:
    """Finish Embedded Signup: swap the code for the seller's business token,
    subscribe to their account, make the number ready to send, store it all
    and submit the campaign template."""
    cfg = embedded_config()
    if not cfg["available"]:
        raise WhatsAppError("WhatsApp sign-in is not switched on for this app yet.")
    if not code:
        raise WhatsAppError("The WhatsApp sign-in did not finish. Please try again.")
    waba = re.sub(r"\D", "", waba_id or "")
    if not waba:
        raise WhatsAppError("Meta did not say which WhatsApp account you picked. Please try again.")
    try:
        r = requests.get(f"{GRAPH}/oauth/access_token", timeout=TIMEOUT, params={
            "client_id": cfg["app_id"], "client_secret": os.environ.get("WHATSAPP_APP_SECRET", ""),
            "code": code})
        body = r.json() if r.content else {}
    except (requests.RequestException, ValueError) as e:
        raise WhatsAppError(f"Could not reach Meta just now ({e.__class__.__name__}). Try again.")
    token = (body or {}).get("access_token") or ""
    if not token:
        err = ((body or {}).get("error") or {}).get("message") or "no token"
        raise WhatsAppError(f"Meta did not accept the sign-in ({err}). It expires in 30 seconds, "
                            f"so please try once more.")

    pnid = re.sub(r"\D", "", phone_number_id or "")
    if not pnid:
        # coexistence onboarding does not send the number id; ask for it
        nums = _req("GET", f"{waba}/phone_numbers", token,
                    params={"fields": "id,display_phone_number,verified_name"})
        first = (nums.get("data") or [{}])[0]
        pnid = re.sub(r"\D", "", str(first.get("id") or ""))
        if not pnid:
            raise WhatsAppError("No phone number was found on that WhatsApp account.")
    _req("POST", f"{waba}/subscribed_apps", token)
    if coexistence:
        # The number stays on the WhatsApp Business app; Meta asks for both
        # syncs within 24 hours. Best effort: a failed sync does not undo the
        # connection, it is retried by reconnecting.
        for kind in ("smb_app_state_sync", "history"):
            try:
                _req("POST", f"{pnid}/smb_app_data", token,
                     json={"messaging_product": "whatsapp", "sync_type": kind})
            except WhatsAppError as e:
                log.info("coexistence %s sync for %s failed: %s", kind, email, e)
    else:
        import secrets as _s
        pin = "".join(_s.choice("0123456789") for _ in range(6))
        try:
            _req("POST", f"{pnid}/register", token,
                 json={"messaging_product": "whatsapp", "pin": pin})
        except WhatsAppError as e:
            if "already" not in str(e).lower():
                raise
        secrets_store.save_connection(email, CONNECTOR + "_pin", {"pin": pin})

    info = _req("GET", f"{pnid}", token,
                params={"fields": "display_phone_number,verified_name"})
    secrets_store.save_connection(email, CONNECTOR, {"token": token},
                                  {"connected_at": datetime.now().isoformat(timespec="seconds"),
                                   "via": "embedded"})
    shown = info.get("display_phone_number") or ""
    _save_cfg(email, {
        "phone_number_id": pnid, "waba_id": waba, "display_number": shown,
        "verified_name": info.get("verified_name") or "",
        "number": digits(shown) or _cfg(email).get("number") or "",
        "connected_at": datetime.now().isoformat(timespec="seconds"),
        "via": "embedded", "coexistence": bool(coexistence),
        "template": "", "template_status": "", "template_error": "",
    })
    try:
        submit_template(email)
    except WhatsAppError as e:
        _save_cfg(email, {"template_error": str(e)})
    return status(email)


def disconnect(email: str) -> dict:
    try:
        secrets_store.delete_connection(email, CONNECTOR)
    except Exception:  # noqa: BLE001
        pass
    c = _cfg(email)
    keep = {"number": c.get("number"), "number_saved_at": c.get("number_saved_at")}
    user_store.set_key(email, CFG_KEY, {k: v for k, v in keep.items() if v})
    return status(email)


def _example_png() -> bytes:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (800, 800), (246, 239, 228))
    d = ImageDraw.Draw(img)
    d.rectangle([60, 60, 740, 740], outline=(150, 112, 47), width=10)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _header_handle(token: str) -> str:
    """Upload an example picture through the Resumable Upload API: Meta wants
    one to approve a template with a picture header."""
    app = _req("GET", "app", token)
    app_id = app.get("id")
    if not app_id:
        raise WhatsAppError("Could not find the Meta app this token belongs to.")
    data = _example_png()
    sess = _req("POST", f"{app_id}/uploads", token,
                params={"file_name": "example.png", "file_length": len(data),
                        "file_type": "image/png"})
    up = _req("POST", sess["id"], token, data=data,
              headers={"Authorization": f"OAuth {token}", "file_offset": "0"})
    h = up.get("h")
    if not h:
        raise WhatsAppError("Meta did not accept the example picture.")
    return h


def template_payload(name: str, header_handle: str = "") -> dict:
    comps = []
    if header_handle:
        comps.append({"type": "HEADER", "format": "IMAGE",
                      "example": {"header_handle": [header_handle]}})
    comps.append({"type": "BODY", "text": TEMPLATE_BODY,
                  "example": {"body_text": [EXAMPLE]}})
    comps.append({"type": "FOOTER", "text": TEMPLATE_FOOTER})
    return {"name": name, "language": "en", "category": "MARKETING", "components": comps}


def submit_template(email: str) -> dict:
    """Ask Meta to approve the campaign template (picture header if we can,
    text-only otherwise). Safe to call again: an existing one is reused."""
    c, token = _cfg(email), _token(email)
    if not (c.get("waba_id") and token):
        raise WhatsAppError("Connect WhatsApp first.")
    existing = _templates(email)
    for name in (TEMPLATE_NAME, TEMPLATE_TEXT_NAME):
        if name in existing:
            _save_cfg(email, {"template": name, "template_status": existing[name],
                              "template_header": name == TEMPLATE_NAME, "template_error": ""})
            return status(email)
    name, handle = TEMPLATE_NAME, ""
    try:
        handle = _header_handle(token)
    except WhatsAppError as e:
        log.info("picture header unavailable for %s, using text template: %s", email, e)
        name = TEMPLATE_TEXT_NAME
    res = _req("POST", f"{c['waba_id']}/message_templates", token,
               json=template_payload(name, handle))
    _save_cfg(email, {"template": name, "template_status": (res.get("status") or "PENDING").upper(),
                      "template_header": bool(handle), "template_error": "",
                      "template_submitted_at": datetime.now().isoformat(timespec="seconds")})
    return status(email)


def _templates(email: str) -> dict:
    c, token = _cfg(email), _token(email)
    if not (c.get("waba_id") and token):
        return {}
    body = _req("GET", f"{c['waba_id']}/message_templates", token,
                params={"fields": "name,status", "limit": 100})
    return {t.get("name"): str(t.get("status") or "").upper()
            for t in body.get("data") or [] if t.get("name")}


def refresh(email: str) -> dict:
    """Ask Meta where the template is (pending -> approved / rejected)."""
    c = _cfg(email)
    if c.get("template"):
        try:
            st = _templates(email).get(c["template"])
            if st:
                _save_cfg(email, {"template_status": st, "template_checked_at":
                                  datetime.now().isoformat(timespec="seconds")})
        except WhatsAppError as e:
            _save_cfg(email, {"template_error": str(e)})
    return status(email)


# ------------------------------------------------------------------- status
def status(email: str) -> dict:
    c = _cfg(email)
    connected = bool(c.get("phone_number_id") and _token(email))
    tstat = (c.get("template_status") or "").upper()
    mode = ("auto" if connected and tstat == "APPROVED"
            else "waiting" if connected
            else "tap" if c.get("number") else "off")
    return {
        "mode": mode,
        "number": c.get("number") or "",
        "display_number": c.get("display_number") or "",
        "verified_name": c.get("verified_name") or "",
        "connected": connected,
        "template": c.get("template") or "",
        "template_status": tstat,
        "template_header": bool(c.get("template_header")),
        "template_error": c.get("template_error") or "",
        "via": c.get("via") or ("manual" if connected else ""),
        "coexistence": bool(c.get("coexistence")),
        "embedded": embedded_config(),
        "headline": {
            "auto": "Automatic: approved campaigns send on WhatsApp by themselves.",
            "waiting": ("Connected. Waiting for Meta to approve your message template "
                        "(usually minutes, sometimes up to a day). Until then, messages "
                        "open in WhatsApp for you to tap send."
                        if tstat != "REJECTED" else
                        "Meta rejected the message template. Messages open in WhatsApp "
                        "for you to tap send; contact us and we will resubmit it."),
            "tap": "Tap-to-send: each message opens in WhatsApp already written, you tap send. Connect WhatsApp to send automatically.",
            "off": "Add the WhatsApp number you use for your shop.",
        }[mode],
    }


def live(email: str) -> bool:
    return status(email)["mode"] == "auto"


# --------------------------------------------------------------------- send
def _param(v) -> str:
    """Template parameters may not hold newlines, tabs or 4+ spaces."""
    return re.sub(r"\s+", " ", str(v or "")).strip()[:900] or "-"


def send_campaign_message(email: str, phone: str, values: list, image_url: str = "") -> str:
    """Send one approved-template message. Returns Meta's message id."""
    c, token = _cfg(email), _token(email)
    if not (c.get("phone_number_id") and token and c.get("template")):
        raise WhatsAppError("WhatsApp is not connected for automatic sending.")
    to = digits(phone, default_cc(email))
    if len(to) < 11:
        raise WhatsAppError("not a full phone number")
    comps = []
    if c.get("template_header"):
        if not image_url:
            raise WhatsAppError("this campaign needs a picture to send on WhatsApp")
        comps.append({"type": "header", "parameters": [{"type": "image", "image": {"link": image_url}}]})
    comps.append({"type": "body", "parameters": [{"type": "text", "text": _param(v)} for v in values]})
    body = _req("POST", f"{c['phone_number_id']}/messages", token, json={
        "messaging_product": "whatsapp", "to": to, "type": "template",
        "template": {"name": c["template"], "language": {"code": "en"}, "components": comps}})
    msgs = body.get("messages") or [{}]
    return msgs[0].get("id") or ""
