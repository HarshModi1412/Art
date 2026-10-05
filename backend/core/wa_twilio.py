"""
WhatsApp through the seller's own Twilio account: the paid, automatic option.

WHY TWILIO
----------
Sending WhatsApp automatically means the official WhatsApp Business Platform,
and the direct Meta route needs this app to be an approved Meta Tech Provider
(a registered, verified business). Twilio already is one. A seller who opens a
Twilio account and adds their WhatsApp number there can send from this app by
pasting three values: Account SID, Auth Token and that number. Twilio bills
the seller directly (Twilio's fee plus Meta's per-message fee); we never touch
the money.

FREE VS PAID
------------
Free is tap-to-send (campaign_engine + send mode): one tap per customer from
the seller's own phone, nothing to pay. Paid is this module: approved
campaigns go out by themselves. The seller picks which one, as a default in
Account -> WhatsApp and again on every campaign.

TEMPLATES
---------
WhatsApp only lets a business start a conversation with an approved template.
On connect we create this app's two templates in the seller's Twilio account
(Content API) and submit them to WhatsApp for approval: one with a code and
offer, one without (restock, VIP, thank-you). Until they are approved, the
campaign falls back to tap-to-send.

THE SANDBOX
-----------
Twilio's WhatsApp Sandbox (+1 415 523 8886) needs no business and no approved
template, but only reaches phones that joined it by texting the sandbox's join
code. Good for trying it out: with the sandbox number we send the full
personal message as plain text.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime

import requests

from backend.core import secrets_store, user_store

log = logging.getLogger("wa_twilio")

CONNECTOR = "whatsapp_twilio"
CFG_KEY = "whatsapp_config"          # shared with whatsapp.py, under "twilio"
API = "https://api.twilio.com/2010-04-01"
CONTENT = "https://content.twilio.com/v1"
SANDBOX = "14155238886"
TIMEOUT = 25

OFFER_NAME = "otm_tw_offer_v1"
UPDATE_NAME = "otm_tw_update_v1"
FOOTER = "Reply STOP to stop offers from us."
OFFER_BODY = (
    "Hi {{1}}, {{2}} has something for you.\n\n"
    "{{3}}\n\n"
    "Your personal code *{{4}}* gives you {{5}}. Valid till {{6}}.\n\n"
    "Shop here: {{7}} (the code applies automatically).\n\n" + FOOTER
)
UPDATE_BODY = (
    "Hi {{1}}, it's {{2}}.\n\n"
    "{{3}}\n\n"
    "Have a look here: {{4}}\n\n"
    "Thank you for shopping with us. " + FOOTER
)
OFFER_EXAMPLE = ["Priya", "Rang Studio",
                 "It has been a while, and we saved something special for your next order.",
                 "PRIYA-7K2PQ", "Rs 200 off", "16 Oct",
                 "https://onetapmanager.com/s/rangstudio?code=PRIYA-7K2PQ"]
UPDATE_EXAMPLE = ["Priya", "Rang Studio",
                  "It has been about the usual time since your last Mogra Attar, so it might be running low.",
                  "https://onetapmanager.com/s/rangstudio?ref=PRIYA-7K2PQ"]

# What one marketing message costs the seller: Meta's marketing rate for the
# country plus Twilio's $0.005. Approximate, shown as "about".
PRICE_EACH = {"91": ("₹", 1.3), "1": ("$", 0.03)}
PRICE_DEFAULT = ("$", 0.06)


class TwilioError(Exception):
    """Something the seller needs to fix, said plainly."""


# ------------------------------------------------------------------ config
def _all_cfg(email: str) -> dict:
    c = user_store.get_key(email, CFG_KEY, {}) or {}
    return c if isinstance(c, dict) else {}


def _cfg(email: str) -> dict:
    t = _all_cfg(email).get("twilio") or {}
    return t if isinstance(t, dict) else {}


def _save(email: str, patch: dict) -> dict:
    c = _all_cfg(email)
    c["twilio"] = {**(c.get("twilio") or {}), **patch}
    user_store.set_key(email, CFG_KEY, c)
    return c["twilio"]


def _creds(email: str) -> tuple[str, str]:
    try:
        cr = secrets_store.get_credentials(email, CONNECTOR) or {}
    except Exception:  # noqa: BLE001 — a key rotation must not 500 the page
        cr = {}
    return cr.get("sid") or "", cr.get("token") or ""


def _digits(phone) -> str:
    d = re.sub(r"\D", "", str(phone or ""))
    return d[2:] if d.startswith("00") else d


# ------------------------------------------------------------------- http
def _req(method: str, url: str, sid: str, token: str, **kw) -> dict:
    try:
        r = requests.request(method, url, auth=(sid, token), timeout=TIMEOUT, **kw)
    except requests.RequestException as e:
        raise TwilioError(f"Could not reach Twilio ({type(e).__name__}). Try again in a minute.")
    try:
        body = r.json() if r.content else {}
    except ValueError:
        body = {}
    if r.status_code == 401:
        raise TwilioError("Twilio did not accept that Account SID and Auth Token. Copy both again "
                          "from the Twilio Console home page.")
    if r.status_code >= 400:
        msg = body.get("message") or body.get("detail") or f"Twilio said {r.status_code}"
        code = body.get("code")
        raise TwilioError(f"{msg}{f' (Twilio error {code})' if code else ''}")
    return body if isinstance(body, dict) else {}


# --------------------------------------------------------------- connect
def connect(email: str, account_sid: str, auth_token: str, from_number: str) -> dict:
    sid = (account_sid or "").strip()
    token = (auth_token or "").strip()
    frm = _digits(from_number)
    if not re.fullmatch(r"AC[0-9a-fA-F]{32}", sid):
        raise TwilioError("The Account SID starts with AC and is 34 characters. It is on the Twilio Console home page.")
    if len(token) < 20:
        raise TwilioError("Paste the Auth Token from the Twilio Console home page (press Show to copy it).")
    if not (10 <= len(frm) <= 15):
        raise TwilioError("Enter the WhatsApp number on your Twilio account, with country code "
                          "(e.g. +1 415 523 8886 for the Sandbox).")
    acct = _req("GET", f"{API}/Accounts/{sid}.json", sid, token)
    secrets_store.save_connection(email, CONNECTOR, {"sid": sid, "token": token},
                                  meta={"connected_at": datetime.now().isoformat(timespec="seconds")})
    _save(email, {"from": frm, "account_name": acct.get("friendly_name") or "",
                  "trial": (acct.get("type") or "").lower() == "trial",
                  "error": "", "connected_at": datetime.now().isoformat(timespec="seconds")})
    if frm != SANDBOX:
        submit_templates(email)
    return status(email)


def disconnect(email: str) -> dict:
    secrets_store.delete_connection(email, CONNECTOR)
    c = _all_cfg(email)
    c.pop("twilio", None)
    user_store.set_key(email, CFG_KEY, c)
    return status(email)


# -------------------------------------------------------------- templates
def _content_payload(name: str, body: str, example: list) -> dict:
    return {"friendly_name": name, "language": "en",
            "variables": {str(i + 1): v for i, v in enumerate(example)},
            "types": {"twilio/text": {"body": body}}}


def _ensure_template(sid: str, token: str, name: str, body: str, example: list) -> str:
    """The Content SID of our template in this account, created once."""
    page = _req("GET", f"{CONTENT}/Content", sid, token, params={"PageSize": 200})
    for c in page.get("contents") or []:
        if c.get("friendly_name") == name:
            return c.get("sid") or ""
    made = _req("POST", f"{CONTENT}/Content", sid, token, json=_content_payload(name, body, example))
    return made.get("sid") or ""


def _approval(sid: str, token: str, content_sid: str) -> tuple[str, str]:
    body = _req("GET", f"{CONTENT}/Content/{content_sid}/ApprovalRequests", sid, token)
    wa = body.get("whatsapp") or {}
    return str(wa.get("status") or "").lower(), wa.get("rejection_reason") or ""


def submit_templates(email: str) -> dict:
    """Create both templates in the seller's Twilio account and ask WhatsApp
    to approve them. Safe to repeat: existing ones are reused."""
    sid, token = _creds(email)
    if not (sid and token):
        raise TwilioError("Connect Twilio first.")
    patch = {"error": ""}
    for key, name, body, ex in (("offer", OFFER_NAME, OFFER_BODY, OFFER_EXAMPLE),
                                ("update", UPDATE_NAME, UPDATE_BODY, UPDATE_EXAMPLE)):
        try:
            csid = _ensure_template(sid, token, name, body, ex)
            st, why = _approval(sid, token, csid)
            if st in ("", "unsubmitted"):
                _req("POST", f"{CONTENT}/Content/{csid}/ApprovalRequests/whatsapp", sid, token,
                     json={"name": name, "category": "MARKETING"})
                st, why = "pending", ""
            patch.update({f"{key}_sid": csid, f"{key}_status": st, f"{key}_reason": why})
        except TwilioError as e:
            log.info("twilio template %s not submitted for %s: %s", name, email, e)
            patch["error"] = str(e)
    _save(email, patch)
    return status(email)


def refresh(email: str) -> dict:
    """Ask Twilio where the WhatsApp approvals are."""
    sid, token = _creds(email)
    c = _cfg(email)
    if not (sid and token):
        return status(email)
    if c.get("from") != SANDBOX and not (c.get("offer_sid") and c.get("update_sid")):
        return submit_templates(email)
    patch = {"error": ""}
    for key in ("offer", "update"):
        if c.get(f"{key}_sid"):
            try:
                st, why = _approval(sid, token, c[f"{key}_sid"])
                patch.update({f"{key}_status": st, f"{key}_reason": why})
            except TwilioError as e:
                patch["error"] = str(e)
    patch["checked_at"] = datetime.now().isoformat(timespec="seconds")
    _save(email, patch)
    return status(email)


# ------------------------------------------------------------------ status
def price_each(cc: str) -> dict:
    sym, amt = PRICE_EACH.get(cc, PRICE_DEFAULT)
    return {"symbol": sym, "amount": amt}


def status(email: str) -> dict:
    c = _cfg(email)
    sid, token = _creds(email)
    connected = bool(sid and token and c.get("from"))
    sandbox = c.get("from") == SANDBOX
    offer, update = c.get("offer_status") or "", c.get("update_status") or ""
    ready = connected and (sandbox or offer == "approved")
    try:
        from backend.core import whatsapp
        cc = whatsapp.default_cc(email)
    except Exception:  # noqa: BLE001
        cc = "91"
    if not connected:
        line = "Not connected."
    elif sandbox:
        line = ("Connected to the Twilio Sandbox. Only phones that joined your sandbox get messages: "
                "fine for trying it, not for customers.")
    elif ready:
        line = "Ready: campaigns you send as Paid go out on WhatsApp by themselves."
    elif "rejected" in (offer, update):
        line = ("WhatsApp rejected a message template"
                f"{': ' + (c.get('offer_reason') or c.get('update_reason')) if (c.get('offer_reason') or c.get('update_reason')) else ''}. "
                "Paid campaigns use tap-to-send until it is fixed.")
    else:
        line = ("Connected. WhatsApp is reviewing your message templates (usually minutes, at most a "
                "day). Until then, campaigns use free tap-to-send.")
    return {"connected": connected, "from": c.get("from") or "", "sandbox": sandbox,
            "account_name": c.get("account_name") or "", "trial": bool(c.get("trial")),
            "offer_status": offer, "update_status": update,
            "error": c.get("error") or "", "ready": ready, "headline": line,
            "price_each": price_each(cc)}


def ready(email: str) -> bool:
    return status(email)["ready"]


# -------------------------------------------------------------------- send
def _param(v) -> str:
    """Template values may not hold newlines, tabs or 4+ spaces."""
    return re.sub(r"\s+", " ", str(v or "")).strip()[:900] or "-"


def send(email: str, phone: str, values: list, kind: str = "offer", text: str = "") -> str:
    """Send one WhatsApp message through the seller's Twilio account.
    Returns Twilio's message SID. `values` fill the approved template;
    `text` is the full personal message, used as-is on the Sandbox."""
    sid, token = _creds(email)
    c = _cfg(email)
    if not (sid and token and c.get("from")):
        raise TwilioError("Twilio is not connected.")
    from backend.core import whatsapp
    to = whatsapp.digits(phone, whatsapp.default_cc(email))   # bare 10-digit numbers get the shop's country code
    if len(to) < 11:
        raise TwilioError("not a full phone number")
    data = {"From": f"whatsapp:+{c['from']}", "To": f"whatsapp:+{to}"}
    if c["from"] == SANDBOX:
        data["Body"] = (text or "\n".join(_param(v) for v in values))[:1500]
    else:
        key = "update" if kind == "update" else "offer"
        if c.get(f"{key}_status") != "approved" or not c.get(f"{key}_sid"):
            raise TwilioError("this message is still waiting for WhatsApp's approval")
        data["ContentSid"] = c[f"{key}_sid"]
        data["ContentVariables"] = json.dumps({str(i + 1): _param(v) for i, v in enumerate(values)})
    body = _req("POST", f"{API}/Accounts/{sid}/Messages.json", sid, token, data=data)
    return body.get("sid") or ""
