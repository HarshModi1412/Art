"""
Cafe_X — standalone web application (migrated from Streamlit).

Run:  uvicorn backend.main:app --reload
Then open http://localhost:8000

What replaced what:
  st.session_state           -> per-browser session (X-Session-Id header) + login token
  st.file_uploader           -> POST /api/upload
  sidebar radio navigation   -> frontend router (single-page app)
  st.secrets["OPENAI_..."]   -> OPENAI_API_KEY environment variable
  st.plotly_chart            -> JSON chart data rendered with Plotly.js
"""
import hashlib
import io
import json
import os
import secrets

import pandas as pd
import logging

from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import Response, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel

from backend.core import (ad_analytics, ai, analytics, auth, billing, complaints, connectors,
                          content_gen, email_intake, i18n, instagram, joiner, mapper,
                          pos_formats, position_strategy, positioning, pricing, product_config,
                          report_pdf, smart, templates, user_store)
from backend.core import commerce, secrets_store, db, supply, products
from backend.core import sitebuilder, storefront
from backend.core import messaging, password_reset, today as today_mod
from backend.core import winback_proof
from backend.core import media
from backend.core import cache
from backend.core import cancellations
from backend.core import store_payments
from backend.core import campaigns
from backend.core import studio
from backend.core import aiprovider
from backend.core import gst, invoices, invoice_pdf
from backend.core import labels
from backend.core import cancel_requests
from backend.core import social
from backend.core import personas
from backend.core import playbook

# ---------------------------------------------------------
# numpy/pandas JSON safety net
# ---------------------------------------------------------
# Several analytics outputs carry numpy scalar types (np.int64 / np.float64) —
# e.g. the sales forecast series. Older FastAPI versions serialized these
# silently; newer ones raise "Object of type int64 is not JSON serializable"
# during response encoding, which would 500 the analytics/RFM pages after a
# routine `pip install -r requirements.txt` (fastapi is unpinned) on redeploy.
# Registering encoders here makes every endpoint numpy-safe regardless of the
# installed FastAPI/numpy versions. Purely additive — never removes behaviour.
try:
    import numpy as _np
    from fastapi import encoders as _enc
    _enc.ENCODERS_BY_TYPE[_np.integer] = int
    _enc.ENCODERS_BY_TYPE[_np.floating] = float
    _enc.ENCODERS_BY_TYPE[_np.bool_] = bool
    _enc.ENCODERS_BY_TYPE[_np.ndarray] = lambda a: a.tolist()
    if hasattr(_enc, "generate_encoders_by_class_tuples"):
        _enc.encoders_by_class_tuples = _enc.generate_encoders_by_class_tuples(_enc.ENCODERS_BY_TYPE)
except Exception:
    pass

app = FastAPI(title="Cafe_X Intelligence Platform")

# ---------------------------------------------------------------------------
# Wire-level performance.
#
# The app shipped 404 KB of uncompressed JavaScript and CSS on every single
# load. On a phone on a shop's 4G that is several seconds of blank screen
# before anything renders, and it is the actual reason the app felt slow — the
# API itself answers in single-digit milliseconds.
#
# gzip takes that 404 KB to about 103 KB. Nothing else in this file will ever
# buy a 4x improvement for one line.
# ---------------------------------------------------------------------------
app.add_middleware(GZipMiddleware, minimum_size=800, compresslevel=6)


log = logging.getLogger("onetap")


# ---------------------------------------------------------------------------
# One account read per request, not fifty
# ---------------------------------------------------------------------------
# In Supabase mode every user_store.load_state() is an HTTPS round trip. The
# modules each read a few keys and none of them knew what the others were
# doing, so one home screen made roughly 48 of them: ~2.5s of pure waiting on
# a good connection, and a visible failure whenever one of them timed out.
#
# The window has to be the request. Anything longer needs a TTL and can serve
# one Render instance's stale copy to another; anything shorter does not help.
# ---------------------------------------------------------------------------
@app.middleware("http")
async def _state_scope(request, call_next):
    with user_store.request_scope():
        return await call_next(request)


# ---------------------------------------------------------------------------
# An error the seller can read
# ---------------------------------------------------------------------------
# An unhandled exception used to leave FastAPI to return the string
# "Internal Server Error" as text/plain. The frontend parses JSON, got nothing,
# and fell back to response.statusText - which is ALWAYS empty over HTTP/2,
# which is what Render serves. The seller saw an empty bordered box and no
# clue what had happened.
#
# So: always JSON, always a sentence, and the traceback goes to the Render log
# with the path attached so the cause is findable.
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong on our side. Try that again in a moment."},
    )





@app.middleware("http")
async def _cache_policy(request, call_next):
    """Two rules, and the distinction between them is load-bearing.

    **The HTML shell is never cached.** An old index.html pins a seller to an
    old bundle forever, which is the classic way to ship a bug you cannot fix
    remotely. This is what the original blanket no-store rule was protecting
    against, and it stays.

    **A VERSIONED asset is cached for a year.** `smart.js?v=30` is immutable —
    bumping to v=31 is a different URL, so the browser re-fetches on its own.
    Blanket no-store meant re-downloading 404 KB of JavaScript on every single
    page load, which on a phone in a shop is several seconds of blank screen.
    That was the real reason the app felt slow; the API answers in single-digit
    milliseconds.

    The `v=` check is what makes this safe: an unversioned request for the same
    file still gets no-store, so nothing can be pinned by accident."""
    resp = await call_next(request)
    path = request.url.path
    versioned = bool(request.query_params.get("v"))
    is_asset = path.endswith((".js", ".css", ".woff2", ".woff", ".svg"))

    if is_asset and versioned:
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        # MutableHeaders has no .pop(); del is the supported removal.
        for h in ("pragma", "expires"):
            if h in resp.headers:
                del resp.headers[h]
    elif (path.startswith("/smart") or path.startswith("/static") or path == "/app"
            or path.startswith("/s/") or path.startswith("/store-static")
            or path.endswith((".js", ".css", ".html"))):
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
    return resp


def _seed_data_dir():
    """On a fresh persistent disk (first deploy), copy the starter user.csv over
    so login works immediately. Never overwrites an existing file — real
    signups on the disk are always left alone."""
    import shutil
    if db.SUPABASE_ENABLED:
        return  # accounts live in Supabase; nothing to seed on disk
    target_dir = auth.BASE_DIR
    os.makedirs(target_dir, exist_ok=True)
    target_users = os.path.join(target_dir, "user.csv")
    seed_users = os.path.join(os.path.dirname(__file__), "..", "data", "user.csv")
    if not os.path.exists(target_users) and os.path.exists(seed_users):
        shutil.copy(seed_users, target_users)

_seed_data_dir()

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# ---------------------------------------------------------
# Per-browser data store (replaces st.session_state's raw_dfs / txns_df)
# ---------------------------------------------------------
class SessionData:
    def __init__(self):
        self.raw_dfs: dict[str, pd.DataFrame] = {}
        self.file_names: dict[str, str] = {}
        self.txns_df: pd.DataFrame | None = None
        self.mapped_file_id: str | None = None
        self.chat_messages: list[dict] = []
        self.used_initial_prompt = False

_data_sessions: dict[str, SessionData] = {}


def get_session(session_id: str | None) -> SessionData:
    if not session_id:
        raise HTTPException(400, "Missing X-Session-Id header")
    if session_id not in _data_sessions:
        _data_sessions[session_id] = SessionData()
    return _data_sessions[session_id]


def require_user(authorization: str | None) -> str:
    token = (authorization or "").removeprefix("Bearer ").strip()
    email = auth.user_from_token(token)
    if not email:
        raise HTTPException(401, "Login required")
    return email


def optional_user(authorization: str | None) -> str | None:
    """Email if a valid token is present, else None (never raises)."""
    token = (authorization or "").removeprefix("Bearer ").strip()
    return auth.user_from_token(token) if token else None


# ---------------------------------------------------------
# Schemas
# ---------------------------------------------------------
class LoginBody(BaseModel):
    email: str
    password: str

class RegisterBody(BaseModel):
    email: str
    password: str
    plan: str = "free"

class ForgotBody(BaseModel):
    email: str


class ResetBody(BaseModel):
    email: str
    token: str
    password: str


class DigestBody(BaseModel):
    enabled: bool | None = None
    email: str | None = None
    phone: str | None = None
    hour: int | None = None


class WinbackSentBody(BaseModel):
    customers: list[dict] = []
    channel: str | None = "whatsapp"
    note: str | None = ""


class WinbackUnsentBody(BaseModel):
    campaign_id: str


class StoreGatewayBody(BaseModel):
    key_id: str
    key_secret: str


class ShopPayBody(BaseModel):
    lines: list[dict] = []
    payment: str = "cod"


class SupplierBody(BaseModel):
    name: str
    patch: dict = {}


class CampaignBody(BaseModel):
    rows: list[dict] = []
    template: str | None = ""
    subject: str | None = ""
    channels: list[str] = ["email", "whatsapp"]


class BrandBody(BaseModel):
    patch: dict = {}


class MaterialBody(BaseModel):
    product_id: str
    patch: dict = {}


class StudioPostBody(BaseModel):
    product_id: str
    angle: str | None = ""
    generate_image: bool = False



# --- GST / invoicing -----------------------------------------------------
class GstSettingsBody(BaseModel):
    patch: dict = {}


class IssueInvoiceBody(BaseModel):
    order_id: str
    force: bool = False


class CancelInvoiceBody(BaseModel):
    invoice_id: str
    reason: str | None = ""


# --- labels --------------------------------------------------------------
class LabelBody(BaseModel):
    order_ids: list[str] = []


# --- cancellation requests ----------------------------------------------
class CancelRequestBody(BaseModel):
    order_id: str
    reason_code: str
    reason_text: str | None = ""


class ResolveCancelBody(BaseModel):
    request_id: str
    decision: str
    note: str | None = ""


class PoCancelRequestBody(BaseModel):
    po_number: str
    reason_code: str
    reason_text: str | None = ""


# --- purchase orders -----------------------------------------------------
class ManualPoBody(BaseModel):
    supplier: dict = {}
    lines: list[dict] = []
    expected_on: str | None = ""
    terms: str | None = ""
    note: str | None = ""


class PoStatusBody(BaseModel):
    po_number: str
    status: str
    note: str | None = ""


# --- social media manager ------------------------------------------------
class SocialSettingsBody(BaseModel):
    patch: dict = {}


class SocialWeekBody(BaseModel):
    regenerate: bool = False
    weeks: int = 1


class SocialPostBody(BaseModel):
    post_id: str
    patch: dict = {}


class SocialStateBody(BaseModel):
    post_id: str
    state: str


class SocialCloneBody(BaseModel):
    post_id: str


class FestivalCampaignBody(BaseModel):
    festival: str



# --- Product Studio: design language + generation ------------------------
class StudioRefBody(BaseModel):
    url: str


class StudioReadShotsBody(BaseModel):
    product_id: str


class StudioImageOnlyBody(BaseModel):
    product_id: str
    pillar: str | None = ""
    format: str | None = ""
    angle: str | None = ""
    post_id: str | None = ""
    use_reference: bool = True
    strength: float | None = None
    # Which archetype of photograph this beat wants (studio.SHOT_TYPES). Sent
    # by the editor; also resolved from the post when a post_id is given.
    shot_type: str | None = ""
    # Which AI the seller picked for THIS generation. Empty means "use the
    # default"; a named engine that is not usable is an error, never a silent
    # substitution onto a different vendor at a different price.
    engine: str | None = ""


class SocialAttachBody(BaseModel):
    post_id: str
    url: str


class MappingBody(BaseModel):
    file_id: str
    mapping: dict

class ChatBody(BaseModel):
    message: str


# ---------------------------------------------------------
# Auth
# ---------------------------------------------------------
@app.post("/api/login")
def login(body: LoginBody):
    if not auth.load_users():
        raise HTTPException(401, "No user accounts found. Create user.csv (columns: email,password) in the data/ folder or project root.")
    token = auth.login(body.email, body.password)
    if not token:
        raise HTTPException(401, "Invalid credentials")
    email = body.email.strip().lower()
    return {"token": token, "email": email, "usage": _usage(email), "plan": billing.get_plan(email)}


@app.post("/api/register")
def register(body: RegisterBody):
    """Signup from the landing page — free trial, no card. Writes to user.csv with plan column."""
    try:
        auth.register(body.email, body.password, body.plan)
    except ValueError as e:
        raise HTTPException(400, str(e))
    token = auth.login(body.email, body.password)
    email = body.email.strip().lower()
    return {"token": token, "email": email, "usage": _usage(email), "plan": billing.get_plan(email)}


@app.post("/api/forgot")
def forgot_password(body: ForgotBody, request: Request):
    """Always answers the same way, whether or not the address has an account —
    telling an attacker which emails exist is not a feature."""
    return password_reset.request_seller(body.email, _public_base_url(request))


@app.post("/api/reset")
def reset_password(body: ResetBody):
    try:
        return password_reset.reset_seller(body.email, body.token, body.password)
    except password_reset.ResetError as e:
        raise HTTPException(400, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/today")
def today_strip(authorization: str | None = Header(default=None)):
    """The three things worth the seller's time. Same rows the digest sends."""
    email = require_user(authorization)
    items = today_mod.build(email, limit=4)
    return {"items": items,
            "empty": today_mod.empty_state(email) if not items else None,
            "digest": today_mod.get_prefs(email)}


@app.post("/api/digest")
def digest_settings(body: DigestBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    patch = {k: v for k, v in body.dict().items() if v is not None}
    return {"digest": today_mod.set_prefs(email, patch),
            "email_ready": messaging.smtp_configured(),
            "whatsapp_ready": messaging.whatsapp_enabled()}


@app.post("/api/digest/test")
def digest_test(authorization: str | None = Header(default=None)):
    """Send one now, so a seller can see the digest before trusting it."""
    return today_mod.send_digest(require_user(authorization), force=True)


@app.post("/api/digest/run")
def digest_run(hour: int | None = None):
    """Cron target: send every seller whose digest hour is now."""
    return today_mod.run_due(hour)


@app.get("/api/dev/outbox")
def dev_outbox():
    """What we tried to send but had nowhere to send it — visible only while
    SMTP is unconfigured, so a first deploy can still test password reset."""
    if messaging.smtp_configured():
        raise HTTPException(404, "Not available once SMTP is configured.")
    return {"outbox": messaging.outbox()}


@app.post("/api/logout")
def logout(authorization: str | None = Header(default=None)):
    auth.logout((authorization or "").removeprefix("Bearer ").strip())
    return {"ok": True}


def _usage(email: str) -> dict:
    return {
        "chatbot": auth.get_remaining_usage(email, "chatbot"),
        "analyst_ai": auth.get_remaining_usage(email, "analyst_ai"),
        "ai_credits": billing.credit_balance(email, "ai_topup"),
        "winback_credits": billing.credit_balance(email, "winback_campaign"),
        "positioning_credits": billing.credit_balance(email, "positioning_report"),
        "plan": billing.get_plan(email),
        "launch_mode": pricing.launch_mode(),
    }


def _paywall(product_id: str, message: str = "") -> HTTPException:
    """402 with a structured detail the frontend recognises to open the pricing
    modal. The body names BOTH ways past it — the tier that includes this, and
    what it costs in credits — because a seller who works in bursts should not
    be told a monthly subscription is their only option."""
    detail = billing.paywall(product_id)
    if message:
        detail["message"] = message
    return HTTPException(status_code=402, detail=detail)


@app.post("/api/cache/clear")
def cache_clear(authorization: str | None = Header(default=None)):
    """What the Refresh button on every page calls first.

    Without this, Refresh would re-read the same cached computations and the
    seller would be told their data is "up to date" when nothing had been
    recomputed. Scoped to the caller's own account.
    """
    email = require_user(authorization)
    return {"cleared": cache.clear(email)}


# ---------------------------------------------------------
# Product Studio
# ---------------------------------------------------------
@app.get("/api/studio/state")
def studio_state(authorization: str | None = Header(default=None)):
    """The brand profile plus every product with how much material it has.

    The completeness score is not decoration: it decides which product is worth
    posting about next, and names the one missing piece that would help most.
    """
    email = require_user(authorization)
    brand = studio.get_brand(email)
    rows = []
    for p in products.get_products(email):
        mat = studio.get_material(email, p["id"])
        rows.append({
            "id": p["id"], "name": p["name"], "category": p.get("category") or "",
            "price": p.get("price"), "image_url": p.get("image_url") or "",
            "material": mat,
            "completeness": studio.completeness(p, mat),
        })
    rows.sort(key=lambda r: r["completeness"]["score"], reverse=True)
    return {
        "brand": brand,
        "brand_ready": studio.brand_ready(brand),
        "looks": studio.LOOKS,
        "voices": studio.VOICES,
        "products": rows,
        "ai_ready": studio.openai_ready(),
        "media_durable": media.durable(),
    }


@app.post("/api/studio/brand")
def studio_brand(body: BrandBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    cache.clear(email)
    return {"brand": studio.save_brand(email, body.patch or {})}


@app.get("/api/studio/product")
def studio_product(product_id: str, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    p = next((x for x in products.get_products(email) if x["id"] == product_id), None)
    if not p:
        raise HTTPException(404, "That product no longer exists.")
    mat = studio.get_material(email, product_id)
    return {"product": p, "material": mat,
            "completeness": studio.completeness(p, mat),
            "angles": studio.angles(p, mat)}


@app.post("/api/studio/product")
def studio_product_save(body: MaterialBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    cache.clear(email)
    mat = studio.save_material(email, body.product_id, body.patch or {})
    p = next((x for x in products.get_products(email) if x["id"] == body.product_id), {})
    return {"material": mat, "completeness": studio.completeness(p, mat),
            "angles": studio.angles(p, mat)}


@app.post("/api/studio/post")
def studio_post(body: StudioPostBody, authorization: str | None = Header(default=None)):
    """One ready-to-post draft, generated against the brand profile."""
    email = require_user(authorization)
    try:
        return studio.make_post(email, body.product_id, body.angle or "",
                                bool(body.generate_image))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(503, str(e))


@app.get("/api/icons")
def icon_set():
    """The one stroke icon set, shared by the app and every storefront it
    publishes. The app used to draw its modules with emoji while the sites it
    produced used these — which is why the published site looked like software
    and the app looked like a prototype."""
    return {"icons": sitebuilder.ICONS}


@app.get("/api/pricing")
def get_pricing():
    """Public catalog + launch-mode flag — drives both landing page and in-app pricing UI."""
    return pricing.public_catalog()


@app.get("/api/connectors")
def list_connectors():
    """POS connectors available, plus which file exports we auto-recognise."""
    return {"connectors": connectors.available(),
            "supported_exports": pos_formats.describe_supported()}


@app.post("/api/intake/email")
async def intake_email(request: Request):
    """Inbound-email webhook — SendGrid Inbound Parse / Mailgun Routes both
    POST multipart/form-data with roughly this shape (field names differ
    slightly between providers; both send 'from'/'sender' + attachmentN
    files, which is what we read here). This is where a café's POS-scheduled
    report lands once its recipient is set to our address — zero upload,
    zero login, the owner never touches this product's UI at all.
    """
    form = await request.form()
    sender = str(form.get("from") or form.get("sender") or "")
    attachments = []
    for key, value in form.multi_items():
        if hasattr(value, "filename") and value.filename:
            attachments.append((value.filename, await value.read()))
    if not attachments:
        raise HTTPException(400, "No attachments found in the inbound email.")
    try:
        result = email_intake.process_inbound_email(sender, attachments)
    except email_intake.IntakeError as e:
        raise HTTPException(422, str(e))
    report_url = f"/api/intake/report/{result['token']}"
    email_intake.send_report_email(sender, result["token"], report_url)
    return {**result, "report_url": report_url}


@app.get("/api/intake/report/{token}")
def intake_report(token: str):
    """Magic link: the café owner (or whoever the report was emailed to)
    opens this to view/download their processed PDF — no account needed."""
    pdf_bytes = email_intake.get_report(token)
    if not pdf_bytes:
        raise HTTPException(404, "This report link has expired or doesn't exist.")
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": 'inline; filename="cafex_sales_report.pdf"'})


class PullBody(BaseModel):
    connector: str
    credentials: dict = {}
    days: int = 90


@app.post("/api/connectors/pull")
def connector_pull(body: PullBody, x_session_id: str | None = Header(default=None),
                   authorization: str | None = Header(default=None)):
    """Pull orders from a POS into this session, exactly as if a file had been
    uploaded — the data lands in the same place, so every existing feature
    (analytics, RFM, menu engineering) works on it unchanged."""
    from datetime import date, timedelta
    sess = get_session(x_session_id)
    end = date.today()
    start = end - timedelta(days=max(1, min(body.days, 730)))
    try:
        df = connectors.pull(body.connector, body.credentials, start, end)
    except connectors.ConnectorError as e:
        raise HTTPException(400, str(e))
    fid = "pos_" + body.connector
    sess.raw_dfs[fid] = df
    sess.file_names[fid] = f"🔌 {body.connector} ({start} → {end})"
    # already canonical, so map it straight through — no mapping step for the user
    sess.txns_df, _ = mapper.build_transactions(df, {c: c for c in df.columns})
    # SHARED DATA: persist to the account so Smart mode sees it too.
    email = optional_user(authorization)
    if email:
        smart.save_sales(email, sess.txns_df, {"files": sess.file_names[fid]})
    return {"file": _file_info(fid, sess), "rows": int(len(df)),
            "from": start.isoformat(), "to": end.isoformat(), "mapped": True}


@app.get("/api/report/pdf")
def download_report(lang: str = "en", x_session_id: str | None = Header(default=None),
                    authorization: str | None = Header(default=None)):
    """Proper PDF report of the dashboard: prescriptive actions first, KPIs,
    forecast, charts — disclaimer on every page."""
    sess = get_session(x_session_id)
    txns = _require_txns(sess, authorization)
    data = analytics.sales_analytics(txns)
    rendered = i18n.render_all(data["insights"], lang)
    try:
        pdf_bytes = report_pdf.build_sales_report(data, rendered)
    except ImportError:
        raise HTTPException(503, "PDF engine not installed on the server — run: pip install reportlab matplotlib")
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="cafex_sales_report.pdf"'})


@app.post("/api/complaints/pdf")
async def complaints_pdf(product_type: str | None = None,
                         files: list[UploadFile] = File(...),
                         x_session_id: str | None = Header(default=None),
                         authorization: str | None = Header(default=None)):
    """PDF of the Complaint Trends page — Focus Framework, monthly volume, table."""
    pt = _resolve_product_type(authorization, product_type)
    f = files[0]
    content = await f.read()
    try:
        parsed = _read_any_table(f.filename or "reviews", content)
        if not parsed:
            raise ValueError("Could not read the file.")
        data = complaints.analyze_complaints(parsed[0][1], product_type=pt)
        pdf_bytes = report_pdf.build_complaints_report(data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except ImportError:
        raise HTTPException(503, "PDF engine not installed — run: pip install reportlab matplotlib")
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="cafex_complaint_report.pdf"'})


@app.post("/api/positioning/pdf")
async def positioning_pdf(lang: str = "en", product_type: str | None = None,
                          files: list[UploadFile] = File(...),
                          x_session_id: str | None = Header(default=None),
                          authorization: str | None = Header(default=None)):
    """PDF of the Positioning page — actions first, theme share for your brand."""
    pt = _resolve_product_type(authorization, product_type)
    f = files[0]
    content = await f.read()
    try:
        parsed = _read_any_table(f.filename or "reviews", content)
        if not parsed:
            raise ValueError("Could not read the file.")
        data = positioning.analyze_reviews(parsed[0][1], lang, product_type=pt)
        if not data.get("available"):
            raise ValueError(data.get("reason", "Not enough data for a positioning report."))
        pdf_bytes = report_pdf.build_positioning_report(data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except ImportError:
        raise HTTPException(503, "PDF engine not installed — run: pip install reportlab matplotlib")
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="cafex_positioning_report.pdf"'})


@app.post("/api/complaints")
async def analyze_complaints_endpoint(product_type: str | None = None,
                                      files: list[UploadFile] = File(...),
                                      x_session_id: str | None = Header(default=None),
                                      authorization: str | None = Header(default=None)):
    """Complaint Trends Report (premium): raw reviews in -> prescriptive
    fix-first actions, monthly complaint trends, severity quadrant, deep table.
    Free during launch; included in Semi Pro and Pro, or 12 credits, after."""
    sess = get_session(x_session_id)
    if not pricing.launch_mode():
        email = require_user(authorization)
        if not billing.check_and_consume(email, "complaints"):
            raise _paywall("complaints")
    pt = _resolve_product_type(authorization, product_type)
    f = files[0]
    content = await f.read()
    try:
        parsed = _read_any_table(f.filename or "reviews", content)
        if not parsed:
            raise ValueError("Could not read the file — use CSV, Excel, TSV or JSON.")
        _, df = parsed[0]
        # SHARED DATA: save reviews to the account so Smart mode sees them too.
        email = optional_user(authorization)
        if email:
            smart.save_review(email, df, {})
        return complaints.analyze_complaints(df, product_type=pt)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/me")
def me(authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    return {"email": email, "usage": _usage(email), "plan": billing.get_plan(email),
            "product_type": smart.get_product_type(email)}


# ---------------------------------------------------------
# Product type — what the seller sells (drives keyword tracking)
# ---------------------------------------------------------
# ---------------------------------------------------------
# Instagram (real Meta Graph API integration)
#
# Two connection paths:
#   1) OAuth via the platform's own Meta Business App  (recommended for end users)
#      — enabled when META_APP_ID + META_APP_SECRET are set as env vars.
#      The seller clicks "Connect Instagram" and never sees a token.
#   2) Manual paste  (fallback when env vars aren't set, or for dev/testing).
#      Same UI as before — an access token + IG user id form.
# ---------------------------------------------------------
class IGConnectBody(BaseModel):
    access_token: str
    ig_user_id: str


# Short-lived state → email map for the OAuth handshake. Kept in-memory
# because it lasts seconds; a restart during a user's login just makes them
# click Connect again.
_ig_oauth_state: dict[str, dict] = {}


def _ig_redirect_url(request: Request) -> str:
    """Where Meta should send the browser back to after login.
    Env var wins (so a Render app can pin a stable HTTPS URL); otherwise we
    derive it from the incoming request."""
    from os import environ as _env
    from_env = _env.get("META_REDIRECT_URL")
    if from_env:
        return from_env
    return f"{request.url.scheme}://{request.url.netloc}/api/instagram/oauth/callback"


@app.get("/api/instagram/status")
def instagram_status(authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    return {**instagram.status(email), "oauth_available": instagram.oauth_configured()}


@app.get("/api/instagram/oauth/start")
def instagram_oauth_start(request: Request,
                          authorization: str | None = Header(default=None)):
    """Start the OAuth handshake. The frontend opens this in a popup; we
    reply with the Facebook login URL to redirect the popup to."""
    email = require_user(authorization)
    if not instagram.oauth_configured():
        raise HTTPException(400, "OAuth isn't configured on this server yet — the admin needs to set META_APP_ID and META_APP_SECRET.")
    state = secrets.token_urlsafe(16)
    _ig_oauth_state[state] = {"email": email,
                              "created_at": pd.Timestamp.now().isoformat()}
    # prune old states so this dict never grows unbounded
    _prune_states()
    redirect_url = _ig_redirect_url(request)
    return {"login_url": instagram.build_login_url(redirect_url, state),
            "redirect_url": redirect_url}


def _prune_states() -> None:
    cutoff = pd.Timestamp.now() - pd.Timedelta(minutes=15)
    for k in list(_ig_oauth_state.keys()):
        try:
            if pd.Timestamp(_ig_oauth_state[k]["created_at"]) < cutoff:
                _ig_oauth_state.pop(k, None)
        except Exception:
            _ig_oauth_state.pop(k, None)


@app.get("/api/instagram/oauth/callback")
def instagram_oauth_callback(request: Request, code: str | None = None,
                             state: str | None = None, error: str | None = None,
                             error_description: str | None = None):
    """Meta redirects the popup here after the seller approves. We exchange
    the code for a long-lived user token, find their IG Business account
    via the connected Facebook Page, save the Page access token + IG user id
    to their account, then close the popup with a postMessage the parent
    picks up to refresh the status card."""
    from fastapi.responses import HTMLResponse

    def _reply(ok: bool, message: str, username: str | None = None) -> HTMLResponse:
        # Post the result back to the parent (the Instagram module in Smart)
        # and self-close. `*` for targetOrigin is safe here because the popup
        # was opened by us and we don't send any secrets in the message.
        payload = {"ok": ok, "message": message, "username": username}
        html = f"""<!doctype html><meta charset='utf-8'><title>Instagram connect</title>
<style>body{{font:14px/1.5 Inter,system-ui,sans-serif;padding:40px;text-align:center;color:#111827}}
.ok{{color:#0a7a4d}}.err{{color:#c02626}}</style>
<h2 class='{'ok' if ok else 'err'}'>{'✅' if ok else '⚠️'} {message}</h2>
<p class='muted'>{('You can close this window.' if ok else 'You can close this window and try again.')}</p>
<script>
try {{ if (window.opener) {{ window.opener.postMessage({{type:'ig-oauth', payload:{json.dumps(payload)}}}, '*'); }} }} catch(e){{}}
setTimeout(function(){{ try{{window.close();}}catch(e){{}} }}, 900);
</script>"""
        return HTMLResponse(html)

    if error:
        return _reply(False, error_description or error)
    if not code or not state:
        return _reply(False, "Missing code or state from Instagram.")
    st = _ig_oauth_state.pop(state, None)
    if not st:
        return _reply(False, "This login attempt expired — please try again from the app.")
    email = st["email"]
    redirect_url = _ig_redirect_url(request)

    tok = instagram.exchange_code(code, redirect_url)
    if not tok.get("ok"):
        return _reply(False, tok.get("error", "Could not exchange the code with Instagram."))
    user_token = tok["access_token"]
    ig_user_id = tok.get("user_id")
    if not ig_user_id:
        return _reply(False, "Instagram didn't return an account id. Make sure the account is "
                             "switched to Business or Creator (Instagram app > Settings > "
                             "Account type and tools), then try again.")

    # Instagram Login's token response already tells us the account — no
    # Facebook Pages lookup needed. Just confirm it and grab the username.
    check = instagram.test_connection(user_token, ig_user_id)
    if not check.get("ok"):
        return _reply(False, check.get("error", "Could not verify the connected account."))
    instagram.save_credentials(email, user_token, ig_user_id,
                               account_username=check.get("username"))
    return _reply(True, f"Connected @{check.get('username','—')}", username=check.get("username"))


# ---------------------------------------------------------
# Instagram Webhook — required by Meta's "Instagram" product setup even
# though this app doesn't act on realtime events yet. Meta needs:
#   1. A GET handshake to prove we own this URL (the "Verify Token" step).
#   2. A POST receiver for actual events (deauthorization, data-deletion
#      requests, comments, etc.) — we just log & acknowledge for now.
# The Verify Token is a secret string YOU choose (not given by Meta) — set
# it as the IG_WEBHOOK_VERIFY_TOKEN env var, then paste that exact string
# into Meta's "Verify token" field alongside this callback URL:
#   https://<your-domain>/api/instagram/webhook
# ---------------------------------------------------------
@app.get("/api/instagram/webhook")
def instagram_webhook_verify(request: Request):
    from fastapi.responses import PlainTextResponse
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    expected = os.environ.get("IG_WEBHOOK_VERIFY_TOKEN", "")
    if mode == "subscribe" and expected and token == expected:
        return PlainTextResponse(challenge or "")
    raise HTTPException(403, "Verification token mismatch.")


@app.post("/api/instagram/webhook")
async def instagram_webhook_receive(request: Request):
    """Meta expects a fast 200 OK (within a few seconds) or it'll retry and
    eventually flag the webhook as unhealthy. We just log the payload for
    now — nothing in the product currently reacts to these events."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        print(f"[instagram webhook] {json.dumps(body)[:2000]}")
    except Exception:
        pass
    return {"ok": True}


@app.post("/api/instagram/test")
def instagram_test(body: IGConnectBody, authorization: str | None = Header(default=None)):
    require_user(authorization)
    return instagram.test_connection(body.access_token, body.ig_user_id)


@app.post("/api/instagram/connect")
def instagram_connect(body: IGConnectBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    check = instagram.test_connection(body.access_token, body.ig_user_id)
    if not check.get("ok"):
        raise HTTPException(400, check.get("error") or "Could not verify these credentials with Meta.")
    creds = instagram.save_credentials(email, body.access_token, body.ig_user_id,
                                       account_username=check.get("username"))
    return {"ok": True, "status": instagram.status(email), "username": creds.get("account_username")}


@app.post("/api/instagram/disconnect")
def instagram_disconnect(authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    instagram.clear_credentials(email)
    return {"ok": True}


class IGPostBody(BaseModel):
    image_url: str
    caption: str


def _public_base_url(request: Request) -> str:
    return f"{request.url.scheme}://{request.url.netloc}"


@app.post("/api/instagram/post")
def instagram_post(body: IGPostBody, request: Request,
                   authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    url = body.image_url
    if url.startswith("/"):
        url = _public_base_url(request) + url
    try:
        result = instagram.post_image(email, url, body.caption)
    except instagram.InstagramError as e:
        raise HTTPException(400, str(e))
    if not result.get("ok"):
        raise HTTPException(400, f"Instagram error at {result.get('step','')}: {result.get('error')}")
    return result


# ---------------------------------------------------------
# Content creator / auto-publish
# ---------------------------------------------------------
class ContentGenBody(BaseModel):
    topic: str | None = None
    platform: str | None = "instagram"
    with_image: bool = True


@app.get("/api/content/suggestion")
def content_current_suggestion(authorization: str | None = Header(default=None)):
    """The current 'suggested post' shown in the Approval panel — generated
    lazily on first Details open."""
    email = require_user(authorization)
    stored = user_store.get_key(email, "content_current_suggestion", None) or {}
    return {"suggestion": stored, "openai": content_gen.is_openai_available()}


@app.post("/api/content/suggestion/generate")
def content_suggestion_generate(insight_id: str,
                                authorization: str | None = Header(default=None)):
    """Fill in caption/hashtags/image for a panel content_XXXX id on demand."""
    email = require_user(authorization)
    full = smart.get_or_generate_content(email, insight_id, force=False)
    if not full:
        raise HTTPException(404, "That suggestion is no longer active — refresh the panel.")
    return {"suggestion": full, "openai": content_gen.is_openai_available()}


class ContentEditBody(BaseModel):
    caption: str | None = None
    hashtags: list[str] | None = None
    description: str | None = None
    image_url: str | None = None
    platform: str | None = None
    topic: str | None = None


@app.post("/api/content/suggestion/{insight_id}/edit")
def content_suggestion_edit(insight_id: str, body: ContentEditBody,
                            authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    updated = smart.save_content_suggestion(email, insight_id, body.dict(exclude_none=True))
    if not updated:
        raise HTTPException(404, "That suggestion is no longer active — refresh the panel.")
    return {"ok": True, "suggestion": updated}


@app.post("/api/content/upload-image")
async def content_upload_image(insight_id: str = "",
                               files: list[UploadFile] = File(...),
                               authorization: str | None = Header(default=None)):
    """Accept a user-picked image file, save it under data/generated_images/
    (same folder we serve publicly so Instagram can fetch it), stash the URL
    on the current content suggestion, and return the URL."""
    email = require_user(authorization)
    if not files:
        raise HTTPException(400, "No file uploaded.")
    f = files[0]
    ext = os.path.splitext(f.filename or "")[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        raise HTTPException(400, "Use a PNG, JPG or WEBP image.")
    content = await f.read()
    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(400, "Image is over 8MB — please compress or use a smaller one.")
    import uuid as _uuid
    saved = media.save(f"{_uuid.uuid4().hex}{ext}", content, email)
    public_url = saved["url"]
    # Attach to the current suggestion so refreshing keeps the uploaded image.
    if insight_id:
        smart.save_content_suggestion(email, insight_id, {"image_url": public_url})
    return {"ok": True, "image_url": public_url, "filename": f.filename,
            "durable": saved["durable"], "warning": saved["warning"]}


@app.post("/api/content/regenerate-image")
def content_regenerate_image(insight_id: str,
                             authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    stored = user_store.get_key(email, "content_current_suggestion", None) or {}
    if stored.get("id") != insight_id:
        raise HTTPException(404, "That suggestion is no longer active.")
    try:
        new_url = content_gen._openai_image(stored.get("product_type", "generic"),
                                            stored.get("topic", ""))
    except Exception as e:
        raise HTTPException(400, f"Image generation failed: {e}")
    if not new_url:
        raise HTTPException(400, "Image generation returned no image.")
    stored["image_url"] = new_url
    user_store.set_key(email, "content_current_suggestion", stored)
    return {"ok": True, "image_url": new_url}


class ContentPostBody(BaseModel):
    insight_id: str
    caption: str
    hashtags: list[str] = []
    image_url: str
    platform: str = "instagram"


def _compose_ig_caption(caption: str, hashtags: list[str]) -> str:
    tags = " ".join("#" + str(t).strip().lstrip("#") for t in (hashtags or []) if str(t).strip())
    return (caption + ("\n\n" + tags if tags else "")).strip()


@app.post("/api/content/post-now")
def content_post_now(body: ContentPostBody, request: Request,
                     authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    url = body.image_url
    if url.startswith("/"):
        url = _public_base_url(request) + url
    try:
        result = instagram.post_image(email, url, _compose_ig_caption(body.caption, body.hashtags))
    except instagram.InstagramError as e:
        raise HTTPException(400, str(e))
    if not result.get("ok"):
        raise HTTPException(400, f"Instagram error at {result.get('step','')}: {result.get('error')}")
    # move suggestion to History (approved) and rotate the panel
    smart.set_decision(email, body.insight_id, "approved")
    smart.clear_content_suggestion(email)
    return {"ok": True, "result": result,
            "insights": smart.build_insights(email),
            "history": smart.build_history(email)}


class ContentScheduleBody(BaseModel):
    insight_id: str
    caption: str
    hashtags: list[str] = []
    image_url: str
    platform: str = "instagram"
    at: str   # ISO timestamp


@app.post("/api/content/schedule")
def content_schedule(body: ContentScheduleBody,
                     authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    entry = content_gen.schedule_post(email, {
        "caption": body.caption, "hashtags": body.hashtags,
        "image_url": body.image_url, "platform": body.platform,
        "source_insight_id": body.insight_id,
    }, body.at)
    smart.set_decision(email, body.insight_id, "approved")
    smart.clear_content_suggestion(email)
    return {"ok": True, "scheduled": entry,
            "insights": smart.build_insights(email),
            "history": smart.build_history(email)}


@app.get("/api/content/scheduled")
def content_list_scheduled(authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    return {"scheduled": content_gen.list_scheduled(email)}


@app.delete("/api/content/scheduled/{entry_id}")
def content_delete_scheduled(entry_id: str,
                             authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    return {"ok": True, "scheduled": content_gen.delete_scheduled(email, entry_id)}


@app.post("/api/content/scheduled/run")
def content_run_scheduled(request: Request,
                          authorization: str | None = Header(default=None)):
    """Manually fire due scheduled posts (a cron would call this too)."""
    require_user(authorization)
    fired = content_gen.run_due_posts(base_public_url=_public_base_url(request))
    return {"ok": True, "fired": fired}


# ---------------------------------------------------------
# Ads analytics connectors
# ---------------------------------------------------------
class AdsConnectBody(BaseModel):
    connector: str
    credentials: dict = {}


@app.get("/api/ads/connectors")
def ads_connectors_list(authorization: str | None = Header(default=None)):
    email = optional_user(authorization)
    return {"connectors": ad_analytics.list_connectors(email)}


@app.post("/api/ads/connect")
def ads_connect(body: AdsConnectBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    try:
        return ad_analytics.save_connection(email, body.connector, body.credentials)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/ads/disconnect")
def ads_disconnect(body: AdsConnectBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    ad_analytics.disconnect(email, body.connector)
    return {"ok": True}


@app.get("/api/ads/metrics")
def ads_metrics(connector: str, days: int = 30,
                authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    try:
        return ad_analytics.get_metrics(email, connector, days=days)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ---------------------------------------------------------
# Uploaded media
#
# Everything a seller uploads keeps the URL it has always had —
# /generated_images/<file> — but the bytes now come from backend.core.media,
# which keeps the durable copy in Supabase Storage and a local cache under the
# writable data dir. The old behaviour wrote into the checked-out repository,
# so every deploy rebuilt that folder from git and silently deleted every image
# and video a seller had ever uploaded. Nothing needs migrating: a file still
# in the old folder is served from there and copied up to storage as it is read.
# ---------------------------------------------------------
_IMG_DIR = media.cache_dir()


# Uploads are content-addressed — a fresh uuid per file — so the bytes behind a
# URL never change and the browser can keep them forever. That one header is
# what stops a storefront re-downloading every photo on every page view.
_MEDIA_CACHE_HEADERS = {"Cache-Control": "public, max-age=31536000, immutable"}


@app.get("/generated_images/{filename}")
def serve_media(filename: str, request: Request):
    # A conditional request costs nothing to answer.
    if request.headers.get("if-none-match") == f'"{filename}"':
        return Response(status_code=304, headers={**_MEDIA_CACHE_HEADERS,
                                                  "ETag": f'"{filename}"'})
    path = media.local_path(filename)
    if path:
        # stream from disk rather than reading the whole file into memory
        return FileResponse(path, media_type=media.content_type_for(filename),
                            headers={**_MEDIA_CACHE_HEADERS, "ETag": f'"{filename}"'})
    got = media.read(filename)
    if not got:
        raise HTTPException(404, "That file is no longer available.")
    data, ctype = got
    return Response(content=data, media_type=ctype,
                    headers={**_MEDIA_CACHE_HEADERS, "ETag": f'"{filename}"'})


@app.post("/api/media/backfill")
def media_backfill(authorization: str | None = Header(default=None)):
    """One-shot rescue: push anything still sitting only in the old repo folder
    into durable storage before the next deploy erases it."""
    require_user(authorization)
    return media.backfill()


@app.get("/api/media/status")
def media_status(authorization: str | None = Header(default=None)):
    """Is uploaded media actually safe here? The builder shows this, because a
    seller should not find out at the next redeploy."""
    require_user(authorization)
    # health() actually probes Storage and creates the bucket if it is missing,
    # rather than inferring safety from an environment variable being set.
    # "Configured but the bucket does not exist" looks identical to "working"
    # from the outside and loses every upload, which is the exact failure this
    # endpoint exists to catch.
    return media.health()


@app.get("/api/product-types")
def product_types():
    """Public list for the product-type picker (jewellery / clothes / …)."""
    return {"types": product_config.public_types()}


class ProductTypeBody(BaseModel):
    product_type: str


@app.get("/api/product-type")
def get_product_type(authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    return {"product_type": smart.get_product_type(email),
            "types": product_config.public_types()}


@app.post("/api/product-type")
def set_product_type(body: ProductTypeBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    return {"ok": True, "product_type": smart.set_product_type(email, body.product_type)}


def _resolve_product_type(authorization: str | None, product_type: str | None) -> str:
    """Prefer an explicit value (and persist it if logged in); else the saved
    account value; else the generic default."""
    email = optional_user(authorization)
    if product_type:
        if email:
            smart.set_product_type(email, product_type)
        return product_config.normalize(product_type)
    if email:
        return smart.get_product_type(email)
    return product_config.DEFAULT_TYPE


# ---------------------------------------------------------
# Upload + mapping
# ---------------------------------------------------------
SUPPORTED_EXTENSIONS = {".csv", ".tsv", ".txt", ".xlsx", ".xls", ".json"}


def _read_any_table(filename: str, content: bytes) -> list[tuple[str, "pd.DataFrame"]]:
    """
    Parse an uploaded file of (almost) any common tabular format into one or
    more (label, DataFrame) pairs. Excel workbooks with multiple sheets
    produce one entry per sheet so each can be mapped independently.
    """
    ext = os.path.splitext(filename)[1].lower()
    buf = io.BytesIO(content)

    if ext in (".xlsx", ".xls"):
        sheets = pd.read_excel(buf, sheet_name=None)  # dict of {sheet_name: df}
        if len(sheets) == 1:
            only_df = next(iter(sheets.values()))
            return [(filename, only_df)]
        return [(f"{filename} — {sheet}", df) for sheet, df in sheets.items()]

    if ext == ".json":
        try:
            df = pd.read_json(buf)
        except ValueError:
            buf.seek(0)
            df = pd.json_normalize(pd.read_json(buf, typ="series"))
        return [(filename, df)]

    if ext == ".tsv":
        return [(filename, pd.read_csv(buf, sep="\t"))]

    # .csv, .txt, or unknown — try comma first, then auto-detect the delimiter
    try:
        return [(filename, pd.read_csv(buf))]
    except Exception:
        buf.seek(0)
        return [(filename, pd.read_csv(buf, sep=None, engine="python"))]


@app.post("/api/upload")
async def upload(files: list[UploadFile] = File(...), x_session_id: str | None = Header(default=None)):
    if len(files) > 100:
        raise HTTPException(400, "Please upload at most 100 files at a time.")
    sess = get_session(x_session_id)
    out = []
    for f in files:
        ext = os.path.splitext(f.filename or "")[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise HTTPException(400, f"{f.filename}: unsupported file type. Supported: CSV, TSV, TXT, XLSX, XLS, JSON.")
        content = await f.read()
        try:
            parsed = _read_any_table(f.filename or "file", content)
        except Exception as e:
            raise HTTPException(400, f"Could not read {f.filename}: {e}")
        for label, df in parsed:
            if df.empty or len(df.columns) == 0:
                continue
            fid = secrets.token_hex(6)
            sess.raw_dfs[fid] = df
            sess.file_names[fid] = label
            out.append(_file_info(fid, sess))
    if not out:
        raise HTTPException(400, "No readable data found in the uploaded file(s).")
    # multi-file? try to auto-join into one dataset for mapping & insights
    join_info = None
    user_fids = {f: d for f, d in sess.raw_dfs.items() if f != "joined_auto"}
    if len(user_fids) >= 2:
        result = joiner.auto_join(user_fids, sess.file_names)
        if result:
            joined_df, join_report = result
            sess.raw_dfs["joined_auto"] = joined_df
            sess.file_names["joined_auto"] = "🔗 Joined dataset (auto)"
            join_info = {**join_report, "file": _file_info("joined_auto", sess)}
    return {"files": out, "join": join_info}


def _file_info(fid: str, sess: SessionData) -> dict:
    df = sess.raw_dfs[fid]
    # If this is a recognised POS export (PetPooja, Toast, Square, Posist...),
    # use its known column layout instead of the generic guesser — no mapping
    # step needed and no chance of picking unit price over line total.
    pos = pos_formats.detect_format(df)
    suggested = mapper.suggest_mapping(df)
    if pos and pos["mapping"].get("date") and pos["mapping"].get("amount"):
        suggested = {**suggested, **pos["mapping"]}
    return {
        "id": fid,
        "name": sess.file_names[fid],
        "rows": int(len(df)),
        "columns": [str(c) for c in df.columns],
        "kind": mapper.classify_file(df),
        "suggested_mapping": suggested,
        "pos_format": ({"label": pos["label"], "note": pos["note"],
                        "confidence": pos["confidence"]} if pos else None),
        "preview": df.head(8).astype(str).values.tolist(),
    }


@app.get("/api/files")
def list_files(x_session_id: str | None = Header(default=None)):
    sess = get_session(x_session_id)
    return {"files": [_file_info(fid, sess) for fid in sess.raw_dfs],
            "mapped": sess.txns_df is not None}


@app.delete("/api/files/{file_id}")
def delete_file(file_id: str, x_session_id: str | None = Header(default=None)):
    sess = get_session(x_session_id)
    if file_id not in sess.raw_dfs:
        raise HTTPException(404, "File not found")
    sess.raw_dfs.pop(file_id)
    name = sess.file_names.pop(file_id, file_id)
    if sess.mapped_file_id == file_id:
        sess.txns_df = None
        sess.mapped_file_id = None
    return {"ok": True, "deleted": name, "mapped": sess.txns_df is not None}


@app.post("/api/mapping")
def confirm_mapping(body: MappingBody, x_session_id: str | None = Header(default=None),
                    authorization: str | None = Header(default=None)):
    sess = get_session(x_session_id)
    if body.file_id not in sess.raw_dfs:
        raise HTTPException(404, "File not found — upload it first")
    try:
        sess.txns_df, diagnostics = mapper.build_transactions(sess.raw_dfs[body.file_id], body.mapping)
        sess.mapped_file_id = body.file_id
    except ValueError as e:
        raise HTTPException(400, str(e))

    if diagnostics["rows_after"] == 0:
        sess.txns_df = None
        sess.mapped_file_id = None
        raise HTTPException(
            400,
            f"None of the {diagnostics['rows_before']} rows had a readable date and amount. "
            f"Check that the Date and Amount columns you mapped actually contain dates/numbers "
            f"(not blank, header, or text rows)."
        )

    warning = None
    if diagnostics["dropped_rows"] > 0:
        pct = round(diagnostics["dropped_rows"] / diagnostics["rows_before"] * 100, 1)
        reasons = []
        if diagnostics["dropped_bad_date"]:
            reasons.append(f"{diagnostics['dropped_bad_date']} unreadable date(s)")
        if diagnostics["dropped_bad_amount"]:
            reasons.append(f"{diagnostics['dropped_bad_amount']} unreadable amount(s)")
        warning = (
            f"{diagnostics['dropped_rows']} of {diagnostics['rows_before']} rows ({pct}%) were skipped — "
            + " and ".join(reasons) + "."
        )

    # SHARED DATA: persist to the logged-in account so Smart mode (and other
    # devices) see the same sales without a re-upload.
    email = optional_user(authorization)
    if email:
        smart.save_sales(email, sess.txns_df, {"files": sess.file_names.get(body.file_id, "Sales upload")})

    return {"ok": True, "rows": diagnostics["rows_after"],
            "columns": [str(c) for c in sess.txns_df.columns], "warning": warning}


def _require_txns(sess: SessionData, authorization: str | None = None) -> pd.DataFrame:
    """Return this session's mapped transactions. SHARED DATA: if the browser
    session has none but the logged-in account has saved sales (uploaded in
    Smart mode, or another device), hydrate from the account so Classic and
    Smart always see the same data — upload once, use everywhere."""
    if sess.txns_df is None:
        email = optional_user(authorization)
        if email:
            saved = smart.load_sales(email)
            if saved is not None and len(saved):
                sess.txns_df = saved
                sess.mapped_file_id = "shared_account_sales"
    if sess.txns_df is None:
        raise HTTPException(400, "No sales data yet — upload a sales file and confirm the mapping first (in Classic or Smart — it's shared).")
    return sess.txns_df


# ---------------------------------------------------------
# Sample data (one-click demo — activation without an upload)
# ---------------------------------------------------------
SAMPLE_FILE = os.path.join(_ROOT_DATA_DIR := os.path.join(os.path.dirname(__file__), "..", "data"),
                           "sample_transactions.csv")


@app.post("/api/demo")
def load_demo(x_session_id: str | None = Header(default=None),
              authorization: str | None = Header(default=None)):
    """Load 90 days of realistic sample transactions, pre-mapped, so nobody has
    to find a CSV on this laptop before they can see what the app does.

    Loads into BOTH stores: the guest session (which is what the landing page
    and Classic mode read) and, when someone is signed in, their Smart account
    store — otherwise "See it with sample data" appears to do nothing in the
    mode most people are actually using.
    """
    sess = get_session(x_session_id)
    if not os.path.exists(SAMPLE_FILE):
        raise HTTPException(503, "Sample dataset missing on the server.")
    df = pd.read_csv(SAMPLE_FILE)
    fid = secrets.token_hex(6)
    sess.raw_dfs[fid] = df
    sess.file_names[fid] = "Sample data (90 days)"
    identity = {c: c for c in ["date", "customer_id", "customer_name", "order_id",
                               "product", "category", "subcategory", "quantity", "amount"]}
    sess.txns_df, _ = mapper.build_transactions(df, identity)
    sess.mapped_file_id = fid

    saved_to_account = False
    email = optional_user(authorization)
    if email and not (smart.data_status(email).get("sales") or {}).get("ready"):
        # never overwrite real data someone has already uploaded
        try:
            smart.save_sales(email, sess.txns_df,
                             {"source": "sample", "name": "Sample data (90 days)"},
                             mode="replace")
            saved_to_account = True
        except Exception:  # noqa: BLE001 — the session copy is still usable
            pass
    return {"files": [_file_info(fid, sess)], "mapped": True,
            "saved_to_account": saved_to_account}


# ---------------------------------------------------------
# Pricing feedback ("would you pay this?") — GTM validation data
# ---------------------------------------------------------
class FeedbackBody(BaseModel):
    product: str
    vote: str  # "yes" | "no"


@app.post("/api/feedback")
def pricing_feedback(body: FeedbackBody, authorization: str | None = Header(default=None)):
    """One-tap pricing validation from the pricing modal. Answers the GTM
    question ('would anyone pay?') with behaviour instead of guesses —
    review data/feedback.csv weekly."""
    if body.vote not in ("yes", "no") or not pricing.get_product(body.product):
        raise HTTPException(400, "Invalid feedback")
    email = auth.user_from_token((authorization or "").removeprefix("Bearer ").strip()) or "guest"
    if db.SUPABASE_ENABLED:
        db.insert("feedback", {"email": email, "product": body.product, "vote": body.vote})
        return {"ok": True}
    fb_file = os.path.join(auth.BASE_DIR, "feedback.csv")
    os.makedirs(os.path.dirname(fb_file), exist_ok=True)
    header = not os.path.exists(fb_file)
    pd.DataFrame([{"email": email, "product": body.product, "vote": body.vote,
                   "timestamp": pd.Timestamp.now().isoformat()}]) \
        .to_csv(fb_file, mode="a", header=header, index=False)
    return {"ok": True}


# ---------------------------------------------------------
# Analytics / SubCategory / RFM  (no login needed, same as original)
# ---------------------------------------------------------
@app.get("/api/languages")
def get_languages():
    return {"languages": i18n.LANGUAGES}


@app.get("/api/analytics")
def get_analytics(lang: str = "en", x_session_id: str | None = Header(default=None),
                  authorization: str | None = Header(default=None)):
    result = analytics.sales_analytics(_require_txns(get_session(x_session_id), authorization))
    result["insights"] = i18n.render_all(result["insights"], lang)
    return result


@app.get("/api/subcategory")
def get_subcategory(lang: str = "en", x_session_id: str | None = Header(default=None),
                    authorization: str | None = Header(default=None)):
    result = analytics.subcategory_trends(_require_txns(get_session(x_session_id), authorization))
    if result.get("insights"):
        result["insights"] = i18n.render_all(result["insights"], lang)
    return result


@app.post("/api/positioning")
async def analyze_positioning(lang: str = "en", product_type: str | None = None,
                              files: list[UploadFile] = File(...),
                              x_session_id: str | None = Header(default=None),
                              authorization: str | None = Header(default=None)):
    """Upload a café's own reviews file -> brand positioning vs the benchmark cafés.
    GTM gate: free for everyone during launch; afterwards it is included in
    Semi Pro and Pro, or costs 15 credits on the usage plan."""
    get_session(x_session_id)
    if not pricing.launch_mode():
        email = require_user(authorization)
        if not billing.check_and_consume(email, "positioning"):
            raise _paywall("positioning")
    f = files[0]
    ext = os.path.splitext(f.filename or "")[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(400, f"{f.filename}: unsupported file type. Supported: CSV, TSV, TXT, XLSX, XLS, JSON.")
    pt = _resolve_product_type(authorization, product_type)
    content = await f.read()
    try:
        parsed = _read_any_table(f.filename or "reviews", content)
    except Exception as e:
        raise HTTPException(400, f"Could not read {f.filename}: {e}")
    if not parsed:
        raise HTTPException(400, "No readable data found in that file.")
    # SHARED DATA: save reviews to the account so Smart mode sees them too.
    email = optional_user(authorization)
    if email:
        smart.save_review(email, parsed[0][1], {})
    return positioning.analyze_reviews(parsed[0][1], lang, product_type=pt)


@app.get("/api/subcategory/detail")
def get_subcategory_detail(value: str, lang: str = "en", x_session_id: str | None = Header(default=None),
                           authorization: str | None = Header(default=None)):
    result = analytics.subcategory_detail(_require_txns(get_session(x_session_id), authorization), value)
    if result.get("insights"):
        result["insights"] = i18n.render_all(result["insights"], lang)
    return result


@app.get("/api/rfm")
def get_rfm(x_session_id: str | None = Header(default=None),
            authorization: str | None = Header(default=None)):
    return analytics.calculate_rfm(_require_txns(get_session(x_session_id), authorization))


class WinbackSession:
    """Holds the last generated batch of win-back messages so the Excel
    download endpoint doesn't have to regenerate them (and doesn't burn
    another AI call just to produce the file)."""
    def __init__(self):
        self.rows: list[dict] = []

_winback_cache: dict[str, WinbackSession] = {}


@app.post("/api/rfm/winback")
def generate_winback(x_session_id: str | None = Header(default=None),
                     authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    sess = get_session(x_session_id)
    txns = _require_txns(sess, authorization)

    customers = analytics.at_risk_cached(email, txns)
    if not customers:
        return {"customers": [], "usage": _usage(email)}

    # The at-risk LIST is free forever. Generating the ready-to-send campaign is
    # included from Semi Pro upwards — deliberately NOT charged per campaign,
    # because charging per campaign taxes the exact behaviour that proves the
    # product works and creates the habit worth renewing.
    if not billing.check_and_consume(email, "winback_campaign"):
        raise _paywall("winback_campaign")

    # template + market-basket-analysis based — no OpenAI call, no rate limit needed
    results = templates.build_winback_messages(customers)

    _winback_cache.setdefault(x_session_id, WinbackSession()).rows = results
    return {"customers": results, "usage": _usage(email)}


@app.post("/api/rfm/winback/send")
def winback_send(body: CampaignBody,
                 x_session_id: str | None = Header(default=None),
                 authorization: str | None = Header(default=None)):
    """Actually send the campaign — email now, WhatsApp through a provider when
    one is connected and as tap-to-send links until then. Recording it for
    measurement happens automatically, so the seller never has to remember."""
    email = require_user(authorization)
    rows = body.rows or []
    if not rows:
        cached = _winback_cache.get(x_session_id)
        rows = (cached.rows if cached else []) or []
    if not rows:
        raise HTTPException(400, "Generate the campaign first, then send it.")
    site = sitebuilder.get_site(email) or {}
    brand = str(site.get("brand") or email.split("@")[0]).strip()
    cache.clear(email)
    return campaigns.send(email, rows, brand, body.template or "",
                          tuple(body.channels or ("email", "whatsapp")),
                          body.subject or "")


@app.post("/api/rfm/winback/preview")
def winback_preview(body: CampaignBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    site = sitebuilder.get_site(email) or {}
    brand = str(site.get("brand") or email.split("@")[0]).strip()
    return {"preview": campaigns.preview(body.rows or [], brand, body.template or ""),
            "template": body.template or campaigns.default_template(),
            "whatsapp_live": messaging.whatsapp_enabled(),
            "email_ready": messaging.smtp_configured(),
            "brand": brand}


@app.get("/api/rfm/winback/sends")
def winback_sends(authorization: str | None = Header(default=None)):
    return {"sends": campaigns.history(require_user(authorization))}


@app.get("/api/rfm/winback/proof")
def winback_proof_summary(authorization: str | None = Header(default=None)):
    """What every campaign actually recovered — the renewal conversation."""
    return winback_proof.summary(require_user(authorization))


@app.post("/api/rfm/winback/sent")
def winback_mark_sent(body: WinbackSentBody,
                      x_session_id: str | None = Header(default=None),
                      authorization: str | None = Header(default=None)):
    """One tick: this campaign went out. From here the app can measure it."""
    email = require_user(authorization)
    rows = body.customers or []
    if not rows:
        cached = _winback_cache.get(x_session_id)
        rows = (cached.rows if cached else []) or []
    try:
        winback_proof.mark_sent(email, rows, body.channel or "whatsapp", body.note or "")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return winback_proof.summary(email)


@app.post("/api/rfm/winback/unsent")
def winback_unmark(body: WinbackUnsentBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    winback_proof.unmark(email, body.campaign_id)
    return winback_proof.summary(email)


@app.get("/api/rfm/winback/download")
def download_winback(x_session_id: str | None = Header(default=None),
                     authorization: str | None = Header(default=None)):
    require_user(authorization)
    cached = _winback_cache.get(x_session_id)
    if not cached or not cached.rows:
        raise HTTPException(400, "Generate the messages first, then download.")

    df = pd.DataFrame(cached.rows).rename(columns={
        "customer_id": "Customer ID",
        "customer_name": "Customer Name",
        "recency_days": "Days Since Last Visit",
        "frequency": "Total Orders",
        "monetary": "Total Spend",
        "last_purchase_date": "Last Purchase Date",
        "favorite_item": "Favorite Item",
        "favorite_category": "Favorite Category",
        "price_tier": "Spend Tier",
        "preferred_day": "Preferred Day",
        "trend": "Purchase Trend",
        "coupon_code": "Coupon Code",
        "discount_pct": "Discount %",
        "message": "Win-back Message",
    })
    col_order = ["Customer ID", "Customer Name", "Last Purchase Date", "Days Since Last Visit",
                 "Total Orders", "Total Spend", "Favorite Item", "Favorite Category",
                 "Spend Tier", "Preferred Day", "Purchase Trend", "Coupon Code", "Discount %",
                 "Win-back Message"]
    df = df[[c for c in col_order if c in df.columns]]

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="At-Risk Win-back")
        ws = writer.sheets["At-Risk Win-back"]
        widths = {"A": 16, "B": 18, "C": 16, "D": 14, "E": 12, "F": 14, "G": 20, "H": 18,
                  "I": 12, "J": 14, "K": 26, "L": 14, "M": 11, "N": 65}
        for col, w in widths.items():
            ws.column_dimensions[col].width = w
    buf.seek(0)

    from fastapi.responses import Response, StreamingResponse
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=winback_messages.xlsx"},
    )


class WinbackExportBody(BaseModel):
    # the win-back popup lets the seller edit/remove/add rows before export;
    # we just render whatever they send to a tidy Excel.
    rows: list[dict]


@app.post("/api/rfm/winback/export")
def export_winback_edited(body: WinbackExportBody,
                          authorization: str | None = Header(default=None)):
    """Export the win-back list AS EDITED in the popup — edited fields, removed
    rows, and manually added rows all come through here."""
    require_user(authorization)
    if not body.rows:
        raise HTTPException(400, "Nothing to export — the list is empty.")
    df = pd.DataFrame(body.rows)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Win-back")
        ws = writer.sheets["Win-back"]
        for i, col in enumerate(df.columns):
            try:
                width = min(70, max(12, int(df[col].astype(str).str.len().max()) + 2, len(str(col)) + 2))
            except Exception:
                width = 18
            ws.column_dimensions[chr(65 + i) if i < 26 else "A"].width = width
    buf.seek(0)
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=winback_messages.xlsx"})


# ---------------------------------------------------------
# AI features (login + rate limit, same as original)
# ---------------------------------------------------------
def _consume_ai_use(email: str, feature: str) -> None:
    """Daily free quota first, then paid top-up credits, else paywall.
    Launch mode and Pro are unlimited."""
    if pricing.launch_mode() or billing.is_unlimited(email):
        auth.check_usage_limit(email, feature)  # still log usage for analytics; never blocks here
        return
    if auth.check_usage_limit(email, feature):
        return
    if billing.spend_credits(email, pricing.credits_for("ai_use")):
        return
    quota = pricing.ai_quota(billing.get_plan(email))
    raise _paywall(
        "ai_use",
        f"You've used today's {quota} free AI runs. Semi Pro raises it to 50 a day and Pro "
        f"removes the limit — or spend credits, which never expire.",
    )


@app.post("/api/analyst")
def run_analyst(x_session_id: str | None = Header(default=None),
                authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    sess = get_session(x_session_id)
    if not sess.raw_dfs:
        raise HTTPException(400, "Upload files first")
    _consume_ai_use(email, "analyst_ai")
    named = {sess.file_names[fid]: df for fid, df in sess.raw_dfs.items()}
    try:
        results = ai.run_business_analyst(named)
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    return {"results": results, "usage": _usage(email)}


@app.post("/api/chat")
def chat(body: ChatBody, x_session_id: str | None = Header(default=None),
         authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    sess = get_session(x_session_id)
    _consume_ai_use(email, "chatbot")

    sess.chat_messages.append({"role": "user", "content": body.message})
    first = not sess.used_initial_prompt
    try:
        result = ai.run_chat(sess.raw_dfs, sess.chat_messages, first_time=first)
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    sess.used_initial_prompt = True
    sess.chat_messages.append({"role": "assistant", "content": result["reply"]})
    return {**result, "usage": _usage(email)}


@app.get("/api/chat/history")
def chat_history(x_session_id: str | None = Header(default=None)):
    return {"messages": get_session(x_session_id).chat_messages}


# ---------------------------------------------------------
# Billing / Payments (Razorpay)
# ---------------------------------------------------------
class OrderBody(BaseModel):
    product: str  # a plan id (semipro | pro) or a credit pack (credits_100 | ...)


class VerifyBody(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    product: str | None = None  # server-side pending-order record takes precedence


@app.post("/api/pay/create-order")
def create_order(body: OrderBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    current = billing.get_plan(email)
    if body.product == current:
        raise HTTPException(400, f"You are already on {pricing.get_plan(current)['name']}.")
    if body.product == "semipro" and current == "pro":
        raise HTTPException(400, "Pro already includes everything in Semi Pro.")
    try:
        return billing.create_order(email, body.product)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(503, str(e))


@app.post("/api/pay/verify")
def verify_payment(body: VerifyBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    granted = billing.verify_payment(email, body.razorpay_order_id, body.razorpay_payment_id,
                                     body.razorpay_signature, body.product)
    if not granted:
        raise HTTPException(400, "Payment signature verification failed — contact support if an amount was deducted.")
    return {"ok": True, "product": granted, "usage": _usage(email)}


# ---------------------------------------------------------
# Position Strategy  (login required; state persisted per account)
# ---------------------------------------------------------
def _ps_view(email: str) -> dict:
    """Assemble everything the Position Strategy page needs from saved state."""
    st = user_store.get_key(email, "position_strategy", {}) or {}
    current_id = st.get("current_id")
    out = {
        "detected": bool(current_id),
        "current_id": current_id,
        "n_reviews": st.get("n_reviews"),
        "detected_at": st.get("detected_at"),
        "current": position_strategy.position_card(current_id) if current_id else None,
        "options": position_strategy.target_options(current_id) if current_id else [],
        "target_id": st.get("target_id"),
        "plan": None,
    }
    target_id = st.get("target_id")
    # target may now equal current (a "stay & strengthen" plan)
    if current_id and target_id:
        try:
            plan = position_strategy.build_plan(current_id, target_id)
        except ValueError:
            plan = None
        if plan:
            checked = set(st.get("checked", []))
            for item in plan["checklist"]:
                item["done"] = item["id"] in checked
            done = sum(1 for i in plan["checklist"] if i["done"])
            plan["progress"] = {"done": done, "total": len(plan["checklist"])}
            # per-level progress, so the UI can gate Level N+1 on Level N
            level_prog = {}
            for it in plan["checklist"]:
                lv = it.get("level", 1)
                d = level_prog.setdefault(lv, {"done": 0, "total": 0})
                d["total"] += 1
                if it["done"]:
                    d["done"] += 1
            plan["level_progress"] = level_prog
            out["plan"] = plan
    return out


@app.get("/api/position-strategy")
def ps_get(authorization: str | None = Header(default=None)):
    return _ps_view(require_user(authorization))


@app.post("/api/position-strategy/detect")
async def ps_detect(lang: str = "en", files: list[UploadFile] = File(...),
                    authorization: str | None = Header(default=None)):
    """Auto-detect the café's current position from its reviews, reusing the
    Positioning engine, and persist it to the account."""
    email = require_user(authorization)
    f = files[0]
    ext = os.path.splitext(f.filename or "")[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(400, f"{f.filename}: unsupported file type. Supported: CSV, TSV, TXT, XLSX, XLS, JSON.")
    pt = _resolve_product_type(authorization, None)
    content = await f.read()
    try:
        parsed = _read_any_table(f.filename or "reviews", content)
    except Exception as e:
        raise HTTPException(400, f"Could not read {f.filename}: {e}")
    if not parsed:
        raise HTTPException(400, "No readable data found in that file.")
    # SHARED DATA: save reviews to the account so Smart mode sees them too.
    smart.save_review(email, parsed[0][1], {})
    data = positioning.analyze_reviews(parsed[0][1], lang, product_type=pt)
    if not data.get("available"):
        raise HTTPException(400, data.get("reason", "Not enough review data to detect a position."))
    quadrant = (data.get("perceptual_map", {}).get("you", {}) or {}).get("quadrant")
    current_id = position_strategy.QUADRANT_TO_ID.get(quadrant)
    if not current_id:
        raise HTTPException(400, "Couldn't map your reviews to a position — try a file with more reviews.")

    st = user_store.get_key(email, "position_strategy", {}) or {}
    # a fresh detection that lands in a different position invalidates an old
    # target/checklist; a re-detection to the same position keeps the progress.
    if st.get("current_id") != current_id:
        st["target_id"] = None
        st["checked"] = []
    st.update({
        "current_id": current_id,
        "n_reviews": data.get("n_reviews"),
        "detected_at": pd.Timestamp.now().isoformat(timespec="seconds"),
    })
    user_store.set_key(email, "position_strategy", st)
    return _ps_view(email)


class PSTargetBody(BaseModel):
    target_id: str


@app.post("/api/position-strategy/target")
def ps_target(body: PSTargetBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    st = user_store.get_key(email, "position_strategy", {}) or {}
    if not st.get("current_id"):
        raise HTTPException(400, "Detect your current position first.")
    try:
        # target may equal current (strengthen-in-place)
        position_strategy.build_plan(st["current_id"], body.target_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    # switching target starts a fresh checklist
    if st.get("target_id") != body.target_id:
        st["checked"] = []
    st["target_id"] = body.target_id
    user_store.set_key(email, "position_strategy", st)
    return _ps_view(email)


class PSCheckBody(BaseModel):
    item_id: str
    done: bool


@app.post("/api/position-strategy/check")
def ps_check(body: PSCheckBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    st = user_store.get_key(email, "position_strategy", {}) or {}
    checked = set(st.get("checked", []))
    if body.done:
        checked.add(body.item_id)
    else:
        checked.discard(body.item_id)
    st["checked"] = sorted(checked)
    user_store.set_key(email, "position_strategy", st)
    return {"ok": True, "checked_count": len(checked)}


@app.post("/api/position-strategy/reset")
def ps_reset(authorization: str | None = Header(default=None)):
    """Clear the saved position strategy for this account (start over)."""
    email = require_user(authorization)
    user_store.set_key(email, "position_strategy", {})
    return {"ok": True}


# ---------------------------------------------------------
# Smart CafeX  (Odoo-style workspace — login required, data persisted)
# ---------------------------------------------------------
SMART_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Smart CafeX")

REVIEW_ROLES = ("review", "rating", "date")


def _smart_status_payload(email: str, sess) -> dict:
    smart.hydrate_session(email, sess)
    return {
        "email": email,
        "data": smart.data_status(email),
        "insights": smart.build_insights(email),
        "history": smart.build_history(email),
        "tasks": smart.get_tasks(email),
    }


@app.get("/api/smart/state")
def smart_state(response: Response,
                x_session_id: str | None = Header(default=None),
                if_none_match: str | None = Header(default=None),
                authorization: str | None = Header(default=None)):
    """The home screen's payload, with a conditional GET on top.

    WHY: this is the first thing every page load asks for, and a browser that
    reclaims the tab (switch apps on a phone, come back) throws the whole page
    away and asks again. cache.stamp() is already an exact fingerprint of the
    account's data — row counts, updated_at, order count — so it makes a
    correct ETag for free: when nothing has changed the browser gets a 304 with
    no body, and the app repaints from what it already had instead of
    re-downloading and re-rendering the same screen.

    The stamp changes the moment a dataset, an order or an upload changes, so
    a seller can never be shown a stale figure waiting for a timer."""
    email = require_user(authorization)
    tag = f'W/"{hashlib.md5(cache.stamp(email).encode()).hexdigest()}"'
    # Private: this is one seller's data and must never be held by a shared
    # proxy. no-cache means "revalidate every time", not "do not store" — the
    # browser keeps the body and we answer 304 when it is still good.
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["ETag"] = tag
    if if_none_match and if_none_match.strip() == tag:
        return Response(status_code=304, headers={
            "ETag": tag, "Cache-Control": "private, no-cache"})
    return _smart_status_payload(email, get_session(x_session_id))


@app.get("/api/smart/history")
def smart_history(authorization: str | None = Header(default=None)):
    """Full approved + dismissed history, newest first."""
    email = require_user(authorization)
    return smart.build_history(email)


@app.post("/api/smart/upload")
async def smart_upload(kind: str, files: list[UploadFile] = File(...),
                       x_session_id: str | None = Header(default=None),
                       authorization: str | None = Header(default=None)):
    """Stage one or more Sales (or Review) files for mapping. Multiple files are
    combined: Sales via the auto-joiner, Reviews by stacking rows."""
    email = require_user(authorization)
    if kind not in ("sales", "review", "supply_sales"):
        raise HTTPException(400, "kind must be 'sales', 'supply_sales' or 'review'")
    if len(files) > 100:
        raise HTTPException(400, "Please upload at most 100 files at a time.")
    sess = get_session(x_session_id)
    dfs = []
    names = []
    for f in files:
        ext = os.path.splitext(f.filename or "")[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise HTTPException(400, f"{f.filename}: unsupported type. Use CSV, TSV, Excel or JSON.")
        content = await f.read()
        try:
            parsed = _read_any_table(f.filename or "file", content)
        except Exception as e:
            raise HTTPException(400, f"Could not read {f.filename}: {e}")
        for label, df in parsed:
            if df.empty or len(df.columns) == 0:
                continue
            dfs.append(df)
            names.append(label)
    if not dfs:
        raise HTTPException(400, "No readable data found in the uploaded file(s).")

    if kind in ("sales", "supply_sales"):
        if len(dfs) == 1:
            combined = dfs[0]
        else:
            raw = {f"f{i}": d for i, d in enumerate(dfs)}
            nm = {f"f{i}": names[i] for i in range(len(dfs))}
            joined = joiner.auto_join(raw, nm)
            combined = joined[0] if joined else pd.concat(dfs, ignore_index=True)
        pending_key = "smart_pending_supply_sales" if kind == "supply_sales" else "smart_pending_sales"
        sess.raw_dfs[pending_key] = combined
        pos = pos_formats.detect_format(combined)
        suggested = mapper.suggest_mapping(combined)
        if pos and pos["mapping"].get("date") and pos["mapping"].get("amount"):
            suggested = {**suggested, **pos["mapping"]}
        try:
            _st = smart.data_status(email).get(kind, {})
            existing_rows = int(_st.get("rows", 0)) if _st.get("ready") else 0
        except Exception:
            existing_rows = 0
        return {"kind": kind, "files": names, "rows": int(len(combined)),
                "columns": [str(c) for c in combined.columns],
                "roles": list(mapper.ROLE_KEYWORDS), "required": ["date", "amount"],
                "suggested_mapping": suggested, "existing_rows": existing_rows,
                # Named when we recognised the export outright, so the mapping
                # screen can say "this is a Shopify export, here is the whole
                # mapping" instead of showing column-by-column guesses.
                "preset": suggested.get("_preset_name", ""),
                "preview": combined.head(6).astype(str).values.tolist()}
    else:
        combined = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
        sess.raw_dfs["smart_pending_review"] = combined
        suggested = {
            "review": positioning.detect_review_column(combined),
            "rating": positioning.detect_rating_column(combined),
            "date": None,
        }
        for c in combined.columns:
            if "date" in str(c).lower():
                suggested["date"] = str(c); break
        try:
            _st = smart.data_status(email).get("review", {})
            existing_rows = int(_st.get("rows", 0)) if _st.get("ready") else 0
        except Exception:
            existing_rows = 0
        return {"kind": "review", "files": names, "rows": int(len(combined)),
                "columns": [str(c) for c in combined.columns],
                "roles": REVIEW_ROLES, "required": ["review"],
                "suggested_mapping": suggested, "existing_rows": existing_rows,
                "preview": combined.head(6).astype(str).values.tolist()}


class SmartMapBody(BaseModel):
    kind: str
    mapping: dict
    mode: str = "replace"   # "replace" overwrites saved data; "append" adds records


@app.post("/api/smart/map")
def smart_map(body: SmartMapBody, x_session_id: str | None = Header(default=None),
              authorization: str | None = Header(default=None)):
    """Confirm the mapping, build the dataset and persist it to the account."""
    email = require_user(authorization)
    sess = get_session(x_session_id)
    if body.kind in ("sales", "supply_sales"):
        is_supply = body.kind == "supply_sales"
        pending_key = "smart_pending_supply_sales" if is_supply else "smart_pending_sales"
        pending = sess.raw_dfs.get(pending_key)
        if pending is None:
            raise HTTPException(400, "Upload a sales file first.")
        try:
            txns, diag = mapper.build_transactions(pending, body.mapping)
        except ValueError as e:
            raise HTTPException(400, str(e))
        if diag["rows_after"] == 0:
            raise HTTPException(400, "None of the rows had a readable date and amount — check your mapping.")
        if is_supply:
            smart.save_supply_sales(email, txns,
                                    {"files": sess.file_names.get(pending_key, "Supply sales upload")},
                                    mode=body.mode)
            combined = smart.load_supply_sales(email)
            total = int(len(combined)) if combined is not None else diag["rows_after"]
        else:
            smart.save_sales(email, txns,
                             {"files": sess.file_names.get(pending_key, "Sales upload")},
                             mode=body.mode)
            combined = smart.load_sales(email)
            sess.txns_df = combined if combined is not None else txns
            sess.mapped_file_id = "smart_sales"
            total = int(len(sess.txns_df)) if sess.txns_df is not None else diag["rows_after"]
        sess.raw_dfs.pop(pending_key, None)
        return {"ok": True, "kind": body.kind, "rows": total,
                "added": diag["rows_after"], "mode": body.mode,
                "data": smart.data_status(email), "insights": smart.build_insights(email)}
    elif body.kind == "review":
        pending = sess.raw_dfs.get("smart_pending_review")
        if pending is None:
            raise HTTPException(400, "Upload a Review file first.")
        m = body.mapping or {}
        if not m.get("review"):
            raise HTTPException(400, "Map the review-text column (required).")
        rename = {}
        if m.get("review"): rename[m["review"]] = "Review"
        if m.get("rating"): rename[m["rating"]] = "Rating"
        if m.get("date"): rename[m["date"]] = "Date"
        df = pending.copy()
        # When re-mapping already-saved data, drop stale canonical columns so
        # we don't end up with two columns both named "Review"/"Rating"/"Date".
        for src, tgt in ((m.get("review"), "Review"), (m.get("rating"), "Rating"), (m.get("date"), "Date")):
            if tgt in df.columns and src != tgt:
                df = df.drop(columns=[tgt])
        df = df.rename(columns=rename)
        smart.save_review(email, df, {}, mode=body.mode)
        sess.raw_dfs.pop("smart_pending_review", None)
        combined = smart.load_review(email)
        total = int(len(combined)) if combined is not None else int(len(df))
        return {"ok": True, "kind": "review", "rows": total,
                "added": int(len(df)), "mode": body.mode,
                "data": smart.data_status(email), "insights": smart.build_insights(email)}
    raise HTTPException(400, "kind must be 'sales' or 'review'")


@app.get("/api/smart/remap")
def smart_remap(kind: str, x_session_id: str | None = Header(default=None),
                authorization: str | None = Header(default=None)):
    """Re-open the column mapping for data already saved to the account, so the
    user can adjust which column is which later without re-uploading a file."""
    email = require_user(authorization)
    sess = get_session(x_session_id)
    if kind in ("sales", "supply_sales"):
        df = smart.load_supply_sales(email) if kind == "supply_sales" else smart.load_sales(email)
        if df is None or getattr(df, "empty", True):
            raise HTTPException(400, "Upload a sales file first.")
        sess.raw_dfs["smart_pending_supply_sales" if kind == "supply_sales" else "smart_pending_sales"] = df
        suggested = mapper.suggest_mapping(df)
        pos = pos_formats.detect_format(df)
        if pos and pos["mapping"].get("date") and pos["mapping"].get("amount"):
            suggested = {**suggested, **pos["mapping"]}
        return {"kind": kind, "files": [], "rows": int(len(df)),
                "columns": [str(c) for c in df.columns],
                "roles": list(mapper.ROLE_KEYWORDS), "required": ["date", "amount"],
                "suggested_mapping": suggested,
                "preview": df.head(6).astype(str).values.tolist()}
    elif kind == "review":
        df = smart.load_review(email)
        if df is None or getattr(df, "empty", True):
            raise HTTPException(400, "Upload a Review file first.")
        sess.raw_dfs["smart_pending_review"] = df
        suggested = {
            "review": positioning.detect_review_column(df),
            "rating": positioning.detect_rating_column(df),
            "date": None,
        }
        for c in df.columns:
            if "date" in str(c).lower():
                suggested["date"] = str(c); break
        return {"kind": "review", "files": [], "rows": int(len(df)),
                "columns": [str(c) for c in df.columns],
                "roles": REVIEW_ROLES, "required": ["review"],
                "suggested_mapping": suggested,
                "preview": df.head(6).astype(str).values.tolist()}
    raise HTTPException(400, "kind must be 'sales' or 'review'")


@app.post("/api/smart/clear")
def smart_clear(kind: str, x_session_id: str | None = Header(default=None),
                authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    smart.clear(email, kind)
    # Cascade: also wipe the data from the live browser session so it disappears
    # from every module immediately, not just from the saved copy.
    try:
        sess = get_session(x_session_id)
        if kind == "sales":
            sess.txns_df = None
            sess.mapped_file_id = None
            for k in list(sess.raw_dfs.keys()):
                if k.startswith("smart_pending_sales") or k.startswith("pos_"):
                    sess.raw_dfs.pop(k, None)
        elif kind == "review":
            sess.raw_dfs.pop("smart_pending_review", None)
        elif kind == "supply_sales":
            sess.raw_dfs.pop("smart_pending_supply_sales", None)
    except HTTPException:
        pass
    return {"ok": True, "data": smart.data_status(email)}


# ---------------------------------------------------------
# Manual record entry — type new rows into the saved schema and append them
# ---------------------------------------------------------
def _smart_columns(df) -> list[dict]:
    """Describe a saved dataset's columns for the Add-record grid."""
    cols = []
    for c in df.columns:
        srs = df[c]
        if pd.api.types.is_datetime64_any_dtype(srs):
            t = "date"
        elif pd.api.types.is_numeric_dtype(srs):
            t = "number"
        else:
            t = "text"
        cols.append({"name": str(c), "type": t})
    return cols


@app.get("/api/smart/schema")
def smart_schema(kind: str, authorization: str | None = Header(default=None)):
    """Columns of the account's saved Sales/Review data, for the type-in grid."""
    email = require_user(authorization)
    if kind not in ("sales", "review"):
        raise HTTPException(400, "kind must be 'sales' or 'review'")
    df = smart.load_sales(email) if kind == "sales" else smart.load_review(email)
    if df is None or getattr(df, "empty", True):
        raise HTTPException(400, "No saved data yet — upload a file first.")
    required = ["date", "amount"] if kind == "sales" else ["Review"]
    return {"kind": kind, "columns": _smart_columns(df),
            "required": [r for r in required if r in df.columns]}


class SmartRecordsBody(BaseModel):
    kind: str
    rows: list[dict]


@app.post("/api/smart/records/add")
def smart_records_add(body: SmartRecordsBody,
                      x_session_id: str | None = Header(default=None),
                      authorization: str | None = Header(default=None)):
    """Append manually-typed rows to the saved Sales/Review dataset."""
    email = require_user(authorization)
    if body.kind not in ("sales", "review"):
        raise HTTPException(400, "kind must be 'sales' or 'review'")
    saved = smart.load_sales(email) if body.kind == "sales" else smart.load_review(email)
    if saved is None or getattr(saved, "empty", True):
        raise HTTPException(400, "No saved data yet — upload a file first.")

    cols = list(saved.columns)
    clean = []
    for r in (body.rows or []):
        row = {c: (r.get(str(c)) if r.get(str(c)) not in ("", None) else None) for c in cols}
        if all(v is None for v in row.values()):
            continue
        clean.append(row)
    if not clean:
        raise HTTPException(400, "Please fill in at least one row.")
    new_df = pd.DataFrame(clean, columns=cols)

    if body.kind == "sales":
        if "date" in new_df.columns:
            new_df["date"] = mapper._parse_dates_robust(new_df["date"])
        if "amount" in new_df.columns:
            new_df["amount"] = mapper._clean_numeric(new_df["amount"])
        if "quantity" in new_df.columns:
            new_df["quantity"] = mapper._clean_numeric(new_df["quantity"])
        need = [c for c in ("date", "amount") if c in new_df.columns]
        if need:
            new_df = new_df.dropna(subset=need)
        if new_df.empty:
            raise HTTPException(400, "Each row needs a valid date and amount.")
        smart.save_sales(email, new_df, {"files": "Manual entry"}, mode="append")
        combined = smart.load_sales(email)
        try:
            sess = get_session(x_session_id)
            sess.txns_df = combined
            sess.mapped_file_id = "smart_sales"
        except HTTPException:
            pass
    else:
        if "Rating" in new_df.columns:
            new_df["Rating"] = pd.to_numeric(new_df["Rating"], errors="coerce")
        if "Review" in new_df.columns:
            new_df = new_df[new_df["Review"].astype(str).str.strip() != ""]
        if new_df.empty:
            raise HTTPException(400, "Each row needs review text.")
        smart.save_review(email, new_df, {}, mode="append")
        combined = smart.load_review(email)

    total = int(len(combined)) if combined is not None else int(len(new_df))
    return {"ok": True, "kind": body.kind, "added": int(len(new_df)), "rows": total,
            "data": smart.data_status(email), "insights": smart.build_insights(email)}


# ---------------------------------------------------------
# Commerce connectors (Shopify / Amazon) — encrypted, per-account linking
# ---------------------------------------------------------
class CommerceConnectBody(BaseModel):
    connector: str
    credentials: dict


class CommercePullBody(BaseModel):
    connector: str
    days: int = 90


@app.get("/api/commerce/status")
def commerce_status(authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    out = []
    for c in commerce.catalog():
        meta = secrets_store.connection_meta(email, c["id"]) or {}
        out.append({**c, "connected": secrets_store.is_connected(email, c["id"]),
                    "account": meta.get("account"), "connected_at": meta.get("connected_at")})
    return {"connectors": out}


@app.post("/api/commerce/connect")
def commerce_connect(body: CommerceConnectBody,
                     authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    creds = {k: (str(v).strip() if v is not None else "") for k, v in (body.credentials or {}).items()}
    try:
        info = commerce.test_connection(body.connector, creds)
    except commerce.CommerceError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(400, f"Could not reach {body.connector}: {e}")
    secrets_store.save_connection(email, body.connector, creds, {
        "account": info.get("account") or info.get("name"),
        "connected_at": pd.Timestamp.now().isoformat(timespec="seconds"),
    })
    return {"ok": True, "connector": body.connector, "account": info.get("account") or info.get("name")}


@app.post("/api/commerce/disconnect")
def commerce_disconnect(body: CommerceConnectBody,
                        authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    secrets_store.delete_connection(email, body.connector)
    return {"ok": True}


@app.post("/api/commerce/pull")
def commerce_pull(body: CommercePullBody, x_session_id: str | None = Header(default=None),
                  authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    creds = secrets_store.get_credentials(email, body.connector)
    if not creds:
        raise HTTPException(400, f"Connect {body.connector} first.")
    try:
        df = commerce.pull_orders(body.connector, creds, days=body.days)
    except commerce.CommerceError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(400, f"Pull failed: {e}")
    # Build canonical transactions and save as the account's Sales dataset.
    mapping = {c: c for c in df.columns}
    try:
        txns, diag = mapper.build_transactions(df, mapping)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if diag["rows_after"] == 0:
        raise HTTPException(400, "Orders pulled but none had a usable date + amount.")
    smart.save_sales(email, txns, {"files": f"🔌 {body.connector} ({body.days}d)"})
    sess = get_session(x_session_id)
    sess.txns_df = txns
    sess.mapped_file_id = "smart_sales"
    return {"ok": True, "connector": body.connector, "rows": diag["rows_after"],
            "data": smart.data_status(email), "insights": smart.build_insights(email)}


# ---------------------------------------------------------
# Content — export the approved post to the seller's device (image + caption)
# ---------------------------------------------------------
@app.get("/api/content/asset")
def content_asset(insight_id: str, kind: str = "image", request: Request = None,
                  authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    sug = smart.get_or_generate_content(email, insight_id, force=False)
    if not sug:
        raise HTTPException(404, "That suggestion is no longer active — refresh the panel.")
    topic = (sug.get("topic") or "post").strip().replace(" ", "_")[:40] or "post"
    if kind == "text":
        tags = " ".join("#" + str(t).strip().lstrip("#") for t in (sug.get("hashtags") or []) if str(t).strip())
        body = (sug.get("caption") or "")
        if tags:
            body += "\n\n" + tags
        if sug.get("description"):
            body += "\n\n---\n" + sug["description"]
        return Response(content=body.strip() + "\n", media_type="text/plain; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{topic}.txt"'})
    # image
    url = sug.get("image_url") or ""
    if not url:
        raise HTTPException(400, "This post has no image yet — open the editor to generate or upload one.")
    data = None
    ctype = "image/png"
    ext = "png"
    if url.startswith("/generated_images/"):
        got = media.read(os.path.basename(url))
        if got:
            data, _ct = got
            ext = (os.path.splitext(url)[1].lstrip(".") or "png").lower()
    if data is None:
        # remote or app-absolute URL — fetch it server-side
        try:
            import requests as _rq
            full = url if url.startswith("http") else (_public_base_url(request) + url if request else url)
            rr = _rq.get(full, timeout=25)
            rr.raise_for_status()
            data = rr.content
            ctype = rr.headers.get("Content-Type", "image/png").split(";")[0]
            ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}.get(ctype, "png")
        except Exception as e:
            raise HTTPException(400, f"Could not fetch the image: {e}")
    ctype = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, ctype)
    return Response(content=data, media_type=ctype,
                    headers={"Content-Disposition": f'attachment; filename="{topic}.{ext}"'})


@app.get("/api/smart/positioning")
def smart_positioning(lang: str = "en", authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    df = smart.load_review(email)
    if df is None:
        raise HTTPException(400, "Upload a Review file in Review Analytics first.")
    return positioning.analyze_reviews(df, lang, product_type=smart.get_product_type(email))


@app.get("/api/smart/complaints")
def smart_complaints(authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    df = smart.load_review(email)
    if df is None:
        raise HTTPException(400, "Upload a Review file in Review Analytics first.")
    return complaints.analyze_complaints(df, product_type=smart.get_product_type(email))


@app.post("/api/smart/strategy/detect")
def smart_strategy_detect(lang: str = "en", authorization: str | None = Header(default=None)):
    """Auto-detect the current position from the account's SAVED reviews
    (no re-upload) and persist it, then return the full strategy view."""
    email = require_user(authorization)
    df = smart.load_review(email)
    if df is None:
        raise HTTPException(400, "Upload a Review file in Review Analytics first.")
    data = positioning.analyze_reviews(df, lang, product_type=smart.get_product_type(email))
    if not data.get("available"):
        raise HTTPException(400, data.get("reason", "Not enough review data to detect a position."))
    quadrant = (data.get("perceptual_map", {}).get("you", {}) or {}).get("quadrant")
    current_id = position_strategy.QUADRANT_TO_ID.get(quadrant)
    if not current_id:
        raise HTTPException(400, "Couldn't map your reviews to a position.")
    st = user_store.get_key(email, "position_strategy", {}) or {}
    if st.get("current_id") != current_id:
        st["target_id"] = None
        st["checked"] = []
    st.update({"current_id": current_id, "n_reviews": data.get("n_reviews"),
               "detected_at": pd.Timestamp.now().isoformat(timespec="seconds")})
    user_store.set_key(email, "position_strategy", st)
    return _ps_view(email)


class SmartDecisionBody(BaseModel):
    decision: str  # approve | disapprove | reset


@app.post("/api/smart/insight/{insight_id}/decision")
def smart_decision(insight_id: str, body: SmartDecisionBody,
                   authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    # Social posts are decided here too (one Approval panel, not two), but
    # their state lives in social.py's own post store, not smart_decisions --
    # the post's state field IS the decision, so there's nothing to snapshot
    # into History and no "insight" bookkeeping to do. Both branches return
    # early with the same shape the normal path returns.
    if str(insight_id).startswith("post_"):
        post_id = insight_id[len("post_"):]
        if body.decision == "approve":
            p = social.set_state(email, post_id, "scheduled")
        elif body.decision == "disapprove":
            p = social.set_state(email, post_id, "failed")
        else:
            return {"ok": True, "insights": smart.build_insights(email),
                    "history": smart.build_history(email)}
        if p.get("error"):
            raise HTTPException(404, p["error"])
        return {"ok": True, "download": False, "download_url": None,
                "insights": smart.build_insights(email),
                "history": smart.build_history(email),
                "tasks": smart.get_tasks(email)}
    if body.decision == "approve":
        # Capture the title BEFORE flipping the state, because after set_decision
        # this insight is no longer in the active list.
        title = next((i["title"] for i in smart.build_insights(email) if i["id"] == insight_id), None)
        if insight_id == "reorder":
            supply.create_po(email, insight_id)   # persist the PO + mark reorder handled
        smart.set_decision(email, insight_id, "approved")
        if str(insight_id).startswith("content_"):
            smart.clear_content_suggestion(email)   # rotate a fresh suggestion in
        if title:
            smart.add_task(email, f"Execute: {title}")
        has_file = smart.insight_excel(email, insight_id) is not None
        return {"ok": True, "download": has_file,
                "download_url": f"/api/smart/insight/{insight_id}/download" if has_file else None,
                "insights": smart.build_insights(email),
                "history": smart.build_history(email),
                "tasks": smart.get_tasks(email)}
    elif body.decision == "disapprove":
        if insight_id == "reorder":
            supply.mark_reorder_handled(email, "dismissed")
        smart.set_decision(email, insight_id, "dismissed")
        return {"ok": True,
                "insights": smart.build_insights(email),
                "history": smart.build_history(email)}
    else:
        if insight_id == "reorder":
            supply.clear_reorder_handled(email)
        smart.reset_decision(email, insight_id)
        return {"ok": True,
                "insights": smart.build_insights(email),
                "history": smart.build_history(email)}


@app.get("/api/smart/insight/{insight_id}/download")
def smart_insight_download(insight_id: str, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    result = smart.insight_excel(email, insight_id)
    if not result:
        raise HTTPException(400, "Nothing to export for this insight — the data may have changed.")
    filename, buf = result
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"})


class SmartTaskBody(BaseModel):
    action: str          # add | toggle | delete
    text: str | None = None
    task_id: str | None = None
    done: bool | None = None


@app.post("/api/smart/tasks")
def smart_tasks(body: SmartTaskBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    if body.action == "add":
        tasks = smart.add_task(email, body.text or "")
    elif body.action == "toggle":
        tasks = smart.toggle_task(email, body.task_id or "", bool(body.done))
    elif body.action == "delete":
        tasks = smart.delete_task(email, body.task_id or "")
    else:
        raise HTTPException(400, "action must be add, toggle or delete")
    return {"ok": True, "tasks": tasks}


# ---------------------------------------------------------
# Supply Management  (inventory -> EOQ/MOQ reorder -> purchase order PDF)
# ---------------------------------------------------------
class SupplyItemBody(BaseModel):
    id: str | None = None
    name: str
    category: str | None = ""
    unit_label: str | None = "unit"
    current_stock: float | None = 0
    lead_time_days: float | None = 0
    safety_stock: float | None = 0
    moq: float | None = 0
    ordering_cost: float | None = None
    holding_cost: float | None = None
    unit_cost: float | None = None
    reorder_qty: float | None = None
    supplier_name: str | None = ""
    supplier_phone: str | None = ""
    supplier_email: str | None = ""


class SupplyIdBody(BaseModel):
    id: str


class SupplyWasteBody(BaseModel):
    inventory_id: str
    qty: float
    reason: str | None = ""


class SupplyMapBody(BaseModel):
    product: str
    inventory_id: str
    qty_per_unit: float | None = 1


class SupplyMapIdBody(BaseModel):
    id: str


class SupplyPOBody(BaseModel):
    item_ids: list[str] | None = None


def _supply_payload(email: str) -> dict:
    comp = supply.compute_inventory(email)
    return {
        "inventory": comp["items"], "below": comp["below"], "meta": comp["meta"],
        "n_below": comp["n_below"],
        "suggestions": comp["below"],
        "products": supply.get_products(email),
        "maps": supply.get_maps(email),
        "waste": supply.get_waste(email),
        "purchase_orders": supply.get_purchase_orders(email),
        "insights": smart.build_insights(email),
    }


@app.get("/api/supply/suppliers")
def supply_suppliers(authorization: str | None = Header(default=None)):
    """Suppliers, derived from the inventory items they stock."""
    return {"suppliers": supply.get_suppliers(require_user(authorization))}


@app.post("/api/supply/supplier")
def supply_supplier_save(body: SupplierBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    cache.clear(email)
    try:
        return {"suppliers": supply.upsert_supplier(email, body.name, body.patch or {})}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/supply/supplier/detach")
def supply_supplier_detach(body: SupplierBody, authorization: str | None = Header(default=None)):
    """Clears the supplier from every item and hands back the ids, so the undo
    can put them back — once the last item is cleared there is no supplier left
    to look up by name."""
    email = require_user(authorization)
    cache.clear(email)
    return supply.detach_supplier(email, body.name)


@app.post("/api/supply/supplier/attach")
def supply_supplier_attach(body: SupplierBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    cache.clear(email)
    ids = (body.patch or {}).get("item_ids") or []
    return {"suppliers": supply.attach_supplier(email, ids, body.patch or {})}


@app.get("/api/supply/state")
def supply_state(authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    return _supply_payload(email)


@app.post("/api/supply/item")
def supply_item(body: SupplyItemBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    try:
        cache.clear(email)
        supply.upsert_item(email, body.dict())
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _supply_payload(email)


@app.post("/api/supply/item/delete")
def supply_item_delete(body: SupplyIdBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    supply.delete_item(email, body.id)
    return _supply_payload(email)


@app.post("/api/supply/import-products")
def supply_import_products(authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    supply.import_products_from_sales(email)
    return _supply_payload(email)


@app.post("/api/supply/waste")
def supply_waste(body: SupplyWasteBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    try:
        supply.record_waste(email, body.inventory_id, body.qty, body.reason or "")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _supply_payload(email)


@app.post("/api/supply/map")
def supply_map(body: SupplyMapBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    try:
        supply.upsert_map(email, body.product, body.inventory_id, body.qty_per_unit)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _supply_payload(email)


@app.post("/api/supply/map/delete")
def supply_map_delete(body: SupplyMapIdBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    supply.delete_map(email, body.id)
    return _supply_payload(email)


@app.post("/api/supply/reorder/generate")
def supply_generate_po(authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    po = supply.create_po(email)
    if not po:
        raise HTTPException(400, "No items are below their reorder point right now.")
    smart.set_decision(email, "reorder", "approved")
    smart.add_task(email, f"Execute: Purchase order {po['po_number']}")
    payload = _supply_payload(email)
    payload["po_number"] = po["po_number"]
    payload["download_url"] = f"/api/supply/po/{po['po_number']}/pdf"
    payload["excel_url"] = f"/api/supply/po/{po['po_number']}/download"
    return payload


@app.post("/api/supply/po/create")
def supply_po_create(body: SupplyPOBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    po = supply.create_po(email, item_ids=body.item_ids or None)
    if not po:
        raise HTTPException(400, "Nothing to order for the selected item(s).")
    smart.add_task(email, f"Execute: Purchase order {po['po_number']}")
    payload = _supply_payload(email)
    payload["po_number"] = po["po_number"]
    payload["download_url"] = f"/api/supply/po/{po['po_number']}/pdf"
    payload["excel_url"] = f"/api/supply/po/{po['po_number']}/download"
    return payload


@app.get("/api/supply/po/{po_number}/pdf")
def supply_po_pdf(po_number: str, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    po = supply.get_po(email, po_number)
    if not po:
        raise HTTPException(404, "Purchase order not found.")
    fname, buf = supply.po_pdf_bytes(email, po)
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        buf, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={fname}"})


@app.get("/api/supply/po/{po_number}/download")
def supply_po_download(po_number: str, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    po = supply.get_po(email, po_number)
    if not po:
        raise HTTPException(404, "Purchase order not found.")
    fname, buf = supply.po_excel(email, po)
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={fname}"})


# ---------------------------------------------------------
# Product Management  (canonical products + platform aliases)
# ---------------------------------------------------------
class ProductBody(BaseModel):
    id: str | None = None
    name: str
    category: str | None = ""
    sku: str | None = ""
    price: float | None = None
    unit_cost: float | None = None
    status: str | None = "active"
    # ---- storefront (Website Builder) ----
    description: str | None = ""
    image_url: str | None = ""
    images: list[str] = []
    highlights: list[str] = []
    mrp: float | None = None
    stock: int | None = 0
    track_stock: bool | None = True
    listed: bool | None = True
    unit_label: str | None = ""
    video_url: str | None = ""
    # ---- variants ----
    # `options` are the axes (Size, Colour); `variants` is the matrix they
    # expand into. The seller sends whichever they edited — the backend
    # rebuilds the matrix from the axes and carries existing cells over.
    options: list[dict] = []
    variants: list[dict] = []
    # which sections of the storefront this product appears in
    featured: bool | None = False
    spotlight: bool | None = False


class ProductIdBody(BaseModel):
    id: str


class AliasBody(BaseModel):
    product_id: str
    alias: str
    platform: str | None = ""


class AliasIdBody(BaseModel):
    id: str


def _products_payload(email: str) -> dict:
    return {
        "products": products.get_products(email),
        "unmatched": products.unmatched_sales_names(email),
        "sales_products": products.sales_product_names(email),
    }


@app.get("/api/products/state")
def products_state(authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    return _products_payload(email)


@app.post("/api/products/item")
def products_item(body: ProductBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    cache.clear(email)
    try:
        products.upsert_product(email, body.dict())
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _products_payload(email)


@app.post("/api/products/item/delete")
def products_item_delete(body: ProductIdBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    cache.clear(email)
    products.delete_product(email, body.id)
    return _products_payload(email)


@app.post("/api/products/alias")
def products_alias(body: AliasBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    try:
        products.add_alias(email, body.product_id, body.alias, body.platform or "")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _products_payload(email)


@app.post("/api/products/alias/delete")
def products_alias_delete(body: AliasIdBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    products.delete_alias(email, body.id)
    return _products_payload(email)


# =========================================================================
# WEBSITE BUILDER — seller side (Site Management module)
# =========================================================================
class SiteSaveBody(BaseModel):
    site: dict


class PublishBody(BaseModel):
    published: bool


class ChannelBody(BaseModel):
    channel: str
    enabled: bool


class OrderStatusBody(BaseModel):
    order_id: str
    status: str
    reason: str | None = ""


class ListedBody(BaseModel):
    id: str
    listed: bool


def _site_state(email: str) -> dict:
    site = sitebuilder.get_site(email)
    listed = products.listed_products(email)
    all_prods = products.get_products(email)
    return {
        "site": site,
        "themes": sitebuilder.theme_catalog(),
        "fonts": sitebuilder.FONTS,
        "resolved": sitebuilder.resolved_style(site),
        "suggested_handle": site.get("handle") or sitebuilder.suggest_handle(
            site.get("brand") or "", email),
        "counts": {
            "listed": len(listed),
            "products": len(all_prods),
            "no_image": len([p for p in listed if not p.get("image_url")]),
            "no_price": len([p for p in listed if p.get("price") in (None, "")]),
        },
        "icons": sitebuilder.ICONS,
        "promise_icons": sitebuilder.PROMISE_ICONS,
        "stats": storefront.order_stats(email),
        "public_path": f"/s/{site.get('handle')}" if site.get("handle") else "",
    }


@app.get("/api/site/state")
def site_state(authorization: str | None = Header(default=None)):
    return _site_state(require_user(authorization))


@app.get("/api/site/gateway")
def site_gateway(authorization: str | None = Header(default=None)):
    """Whether this seller has connected their own Razorpay. Never returns the
    secret — only whether one is stored and its last four characters."""
    return store_payments.status(require_user(authorization))


@app.post("/api/site/gateway")
def site_gateway_save(body: StoreGatewayBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    try:
        return store_payments.save_keys(email, body.key_id, body.key_secret)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/site/gateway/disconnect")
def site_gateway_disconnect(authorization: str | None = Header(default=None)):
    return store_payments.disconnect(require_user(authorization))


@app.get("/api/site/pairings")
def site_pairings(theme: str = "", authorization: str | None = Header(default=None)):
    """Curated font pairings, the ones suiting this theme first."""
    require_user(authorization)
    return {"pairings": sitebuilder.pairings_for(theme), "fonts": sitebuilder.FONTS}


@app.post("/api/site/seed")
def site_seed(authorization: str | None = Header(default=None), force: bool = False):
    """Fill an untouched site from the seller's own catalogue, so the builder
    opens on a finished site rather than five steps of blank fields. Only
    writes where the seller has left a field empty."""
    email = require_user(authorization)
    was = bool(sitebuilder.get_site(email).get("seeded"))
    try:
        sitebuilder.seed_from_catalogue(email, force=force)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {**_site_state(email), "seeded_now": (not was) or bool(force)}


@app.post("/api/site/save")
def site_save(body: SiteSaveBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    cache.clear(email)
    try:
        sitebuilder.save_site(email, body.site or {})
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _site_state(email)


@app.post("/api/site/publish")
def site_publish(body: PublishBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    cache.clear(email)
    try:
        sitebuilder.set_published(email, body.published)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _site_state(email)


@app.post("/api/site/resolve")
def site_resolve(body: SiteSaveBody, authorization: str | None = Header(default=None)):
    """Resolve a draft site to its final palette, fonts and motion WITHOUT
    saving it. The builder calls this as the seller types so the live canvas
    repaints from the same resolver the published site uses — no guessing in
    the browser, and no half-finished edit ever reaching the database."""
    email = require_user(authorization)
    draft = body.site or {}
    return {
        "style": sitebuilder.resolved_style(draft),
        "categories": sitebuilder._payload(email, draft)["categories"],
    }


@app.get("/api/site/handle-check")
def site_handle_check(handle: str, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    h = sitebuilder.normalise_handle(handle)
    return {"handle": h, "available": sitebuilder.handle_available(h, email)}


@app.get("/api/site/preview")
def site_preview(authorization: str | None = Header(default=None)):
    return sitebuilder.preview_site(require_user(authorization))


_IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".avif")
_VIDEO_EXT = (".mp4", ".webm", ".mov", ".m4v")


@app.post("/api/site/image")
async def site_image(files: list[UploadFile] = File(...),
                     authorization: str | None = Header(default=None)):
    """One upload endpoint for every piece of media the seller adds — logos,
    hero art, hero video, story stills, lookbook clips and product photos —
    stored durably by backend.core.media so a redeploy cannot erase it.

    Video is allowed and gets a larger budget than stills: a background clip is
    the single biggest upgrade a storefront can have, and asking sellers to host
    it somewhere else is how that never happens."""
    email = require_user(authorization)
    if not files:
        raise HTTPException(400, "No file uploaded.")
    f = files[0]
    ext = os.path.splitext(f.filename or "")[1].lower()
    is_video = ext in _VIDEO_EXT
    if ext not in _IMAGE_EXT and not is_video:
        raise HTTPException(400, "Use a PNG, JPG, WEBP, GIF or SVG image, or an MP4/WEBM video.")
    content = await f.read()
    cap = 48 * 1024 * 1024 if is_video else 10 * 1024 * 1024
    if len(content) > cap:
        raise HTTPException(400, f"That file is over {cap // (1024 * 1024)}MB — "
                                 f"{'compress the clip (1080p, ~8 seconds is plenty)' if is_video else 'please compress it first'}.")
    import uuid as _uuid
    saved = media.save(f"{_uuid.uuid4().hex}{ext}", content, email)
    url = saved["url"]
    return {"ok": True, "image_url": url, "url": url,
            "kind": "video" if is_video else "image", "filename": f.filename,
            "durable": saved["durable"], "warning": saved["warning"]}


@app.post("/api/products/listed")
def products_listed(body: ListedBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    try:
        cache.clear(email)
        products.set_listed(email, body.id, body.listed)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _products_payload(email)


# ---------------------------------------------------------
# Listed Platforms strip
# ---------------------------------------------------------
@app.get("/api/channels")
def channels_state(authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    site = sitebuilder.get_site(email)
    connected = {}
    try:
        for c in commerce.catalog():
            connected[c["id"]] = bool(secrets_store.get_credentials(email, c["id"]))
    except Exception:  # noqa: BLE001
        connected = {}
    rows = [{
        "id": "site", "label": site.get("brand") or "My website", "icon": "🏬",
        "kind": "own", "status": "live" if site.get("published") else "draft",
        "detail": (f"/s/{site['handle']}" if site.get("handle") else "Not set up yet"),
        "enabled": storefront.channel_enabled(email, "site"),
        "toggleable": bool(site.get("handle")),
        "orders": storefront.order_stats(email)["orders"],
    }]
    for cid, label, icon in (("shopify", "Shopify", "🛍️"), ("amazon", "Amazon", "📦")):
        rows.append({
            "id": cid, "label": label, "icon": icon, "kind": "marketplace",
            "status": "connected" if connected.get(cid) else "available",
            "detail": "Connected - pulling orders" if connected.get(cid) else "Connect to pull orders",
            "enabled": storefront.channel_enabled(email, cid),
            "toggleable": bool(connected.get(cid)), "orders": None,
        })
    # Flipkart / Myntra rows removed -- "yet to come" placeholders were
    # taking up space without anything a seller could act on. Re-add them
    # here (same shape as the shopify/amazon loop above) once they're real.
    return {"channels": rows}


@app.post("/api/channels/toggle")
def channels_toggle(body: ChannelBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    cache.clear(email)
    storefront.set_channel(email, body.channel, body.enabled)
    return channels_state(authorization)


# ---------------------------------------------------------
# Orders module (seller side)
# ---------------------------------------------------------
@app.get("/api/store/orders")
def store_orders(status: str = "", authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    return {
        "orders": storefront.get_orders(email, status=status),
        "stats": storefront.order_stats(email),
        "statuses": [{"id": s, "label": storefront.STATUS_LABELS[s]} for s in storefront.STATUSES],
        "site": {"handle": sitebuilder.get_site(email).get("handle"),
                 "published": sitebuilder.get_site(email).get("published")},
    }


@app.post("/api/store/orders/status")
def store_order_status(body: OrderStatusBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    try:
        cache.clear(email)
        storefront.set_status(email, body.order_id, body.status, reason=body.reason or "")
    except storefront.StoreError as e:
        raise HTTPException(400, str(e))
    return store_orders("", authorization)


@app.get("/api/store/orders/export")
def store_orders_export(authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    csv = storefront.orders_csv(email)
    return Response(content=csv, media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=site_orders.csv"})


@app.get("/api/cancellations")
def cancellation_analysis(authorization: str | None = Header(default=None)):
    """Cancellations, from the seller's own storefront orders.

    Cancelled orders are already excluded from the sales dataset and from every
    insight built on it — this is the one place they are counted, which is why
    the numbers here will not tie to Sales Analytics and should not.
    """
    email = require_user(authorization)
    res = cache.memo(
        "cancellations", email,
        lambda: cancellations.analyse(storefront.get_orders(email, status="all")),
        ttl=120)
    return {**res, "headline": cancellations.headline(res),
            "reason_options": cancellations.REASONS}


@app.get("/api/store/customers")
def store_customers(authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    rows = [storefront._public_customer(c) for c in storefront._customers(email)]
    orders = storefront.get_orders(email)
    spend: dict = {}
    for o in orders:
        if o.get("status") == "cancelled":
            continue
        cid = o.get("customer_id")
        agg = spend.setdefault(cid, {"orders": 0, "spend": 0.0, "last": ""})
        agg["orders"] += 1
        agg["spend"] += float(o.get("total") or 0)
        agg["last"] = max(agg["last"], o.get("created_at") or "")
    for r in rows:
        r.update(spend.get(r["id"], {"orders": 0, "spend": 0.0, "last": ""}))
    rows.sort(key=lambda r: r.get("spend") or 0, reverse=True)
    return {"customers": rows}


# =========================================================================
# STOREFRONT — public, shopper side
# =========================================================================
class ShopAuthBody(BaseModel):
    email: str
    password: str
    name: str | None = ""
    phone: str | None = ""


class ShopCartBody(BaseModel):
    lines: list[dict] = []


class ShopOrderBody(BaseModel):
    lines: list[dict] = []
    address: dict = {}
    payment: str = "cod"
    note: str | None = ""
    # Guest checkout: a shopper with no account still gives us these, because
    # the parcel cannot be delivered without them.
    guest: bool = False
    name: str | None = ""
    phone: str | None = ""
    email: str | None = ""
    # Razorpay hands these back after a successful payment; the server verifies
    # the signature against the seller's own secret before any order is created.
    razorpay_order_id: str | None = ""
    razorpay_payment_id: str | None = ""
    razorpay_signature: str | None = ""



class ShopForgotBody(BaseModel):
    email: str


class ShopResetBody(BaseModel):
    token: str
    password: str



def _seller_for(handle: str) -> str:
    owner = sitebuilder.resolve_handle(handle)
    if not owner:
        raise HTTPException(404, "No store at this address.")
    site = sitebuilder.get_site(owner)
    if not site.get("published"):
        raise HTTPException(404, "This store is not open yet.")
    return owner


def _shopper(handle: str, x_store_token: str | None):
    seller = _seller_for(handle)
    cust = storefront.customer_from_token(seller, (x_store_token or "").strip())
    if not cust:
        raise HTTPException(401, "Log in to continue.")
    return seller, cust


@app.get("/api/shop/{handle}/site")
def shop_site(handle: str, x_preview_token: str | None = Header(default=None)):
    """The storefront's own data. Normally only a published site answers; the
    owner's live preview passes their session token so they can see the site
    exactly as shoppers will before switching it on."""
    owner = sitebuilder.resolve_handle(handle)
    if not owner:
        raise HTTPException(404, "No store at this address.")
    if x_preview_token and auth.user_from_token(x_preview_token.strip()) == owner:
        payload = sitebuilder.preview_site(owner)
    else:
        payload = sitebuilder.public_site(handle)
    if not payload:
        raise HTTPException(404, "This store is not open yet.")
    payload.pop("seller", None)
    return payload


@app.post("/api/shop/{handle}/register")
def shop_register(handle: str, body: ShopAuthBody):
    seller = _seller_for(handle)
    try:
        cust = storefront.register(seller, body.email, body.password,
                                   body.name or "", body.phone or "")
    except storefront.StoreError as e:
        raise HTTPException(400, str(e))
    return {"token": storefront.issue_token(seller, cust["id"]),
            "customer": storefront._public_customer(cust)}


@app.post("/api/shop/{handle}/login")
def shop_login(handle: str, body: ShopAuthBody):
    seller = _seller_for(handle)
    try:
        cust = storefront.login(seller, body.email, body.password)
    except storefront.StoreError as e:
        raise HTTPException(401, str(e))
    return {"token": storefront.issue_token(seller, cust["id"]),
            "customer": storefront._public_customer(cust)}


@app.post("/api/shop/{handle}/logout")
def shop_logout(handle: str, x_store_token: str | None = Header(default=None)):
    seller = _seller_for(handle)
    storefront.revoke_token(seller, x_store_token or "")
    return {"ok": True}


@app.get("/api/shop/{handle}/me")
def shop_me(handle: str, x_store_token: str | None = Header(default=None)):
    seller, cust = _shopper(handle, x_store_token)
    return {"customer": storefront._public_customer(cust),
            "orders": _flag_cancel_requests(seller,
                storefront.get_orders(seller, customer_id=cust["id"]))}


@app.post("/api/shop/{handle}/cart")
def shop_cart(handle: str, body: ShopCartBody):
    seller = _seller_for(handle)
    return storefront.price_cart(seller, body.lines or [])


@app.post("/api/shop/{handle}/pay")
def shop_pay(handle: str, body: ShopPayBody):
    """Open a payment on the seller's own Razorpay account.

    Priced server-side from the same cart resolver checkout uses, so the amount
    can never be set by the browser. Returns only what Razorpay's checkout
    widget needs — the seller's public key id and the order id.
    """
    seller = _seller_for(handle)
    site = sitebuilder.get_site(seller)
    priced = storefront.price_cart(seller, body.lines or [])
    if not priced["items"]:
        raise HTTPException(400, "Your cart is empty.")
    pay = "prepaid" if body.payment == "prepaid" else "cod"
    due = store_payments.split_due(site["commerce"], priced["total"], pay)
    if due["online"] <= 0:
        raise HTTPException(400, "Nothing to pay online for this order.")
    try:
        out = store_payments.create_order(
            seller, due["online"], handle,
            note="advance" if due["kind"] == "cod_advance" else "full")
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))
    return {**out, "due": due, "brand": site.get("brand") or handle,
            "total": priced["total"]}


@app.post("/api/shop/{handle}/order")
def shop_order(handle: str, body: ShopOrderBody,
               x_store_token: str | None = Header(default=None)):
    """Place an order — signed in, or as a guest.

    A guest is not a lesser record: they become a real customer keyed on the
    phone number they had to give us anyway, and they show up in the seller's
    RFM and Win-Back lists like anyone else. They can claim the account later
    by setting a password.
    """
    seller = _seller_for(handle)
    cust = storefront.customer_from_token(seller, (x_store_token or "").strip())
    if not cust:
        addr = body.address or {}
        try:
            cust = storefront.guest_customer(
                seller,
                name=body.name or addr.get("name") or "",
                phone=body.phone or addr.get("phone") or "",
                email=body.email or addr.get("email") or "",
            )
        except storefront.StoreError as e:
            raise HTTPException(400, str(e))
    # Verify the payment here, server-side, against the seller's own secret —
    # everything the browser sent is attacker-controlled until this passes.
    paid = False
    if body.razorpay_payment_id:
        paid = store_payments.verify(seller, body.razorpay_order_id or "",
                                     body.razorpay_payment_id or "",
                                     body.razorpay_signature or "")
        if not paid:
            raise HTTPException(400, "We could not verify that payment. "
                                     "Nothing has been charged twice — please try again.")
    try:
        order = storefront.place_order(seller, cust, body.lines or [], body.address or {},
                                       body.payment or "cod", body.note or "",
                                       payment_ok=paid,
                                       payment_ref=body.razorpay_payment_id or "")
    except storefront.StoreError as e:
        raise HTTPException(400, str(e))
    # a guest gets a session too, so "your orders" works on the thank-you page
    token = (x_store_token or "").strip() or storefront.issue_token(seller, cust["id"])
    return {"order": order, "token": token,
            "customer": storefront._public_customer(cust)}


@app.post("/api/shop/{handle}/forgot")
def shop_forgot(handle: str, body: ShopForgotBody, request: Request):
    seller = _seller_for(handle)
    site = sitebuilder.get_site(seller) or {}
    return password_reset.request_shopper(
        seller, body.email, _public_base_url(request), handle,
        store_name=(site.get("brand") or {}).get("name") if isinstance(site.get("brand"), dict)
        else str(site.get("brand") or handle))


@app.post("/api/shop/{handle}/reset")
def shop_reset(handle: str, body: ShopResetBody):
    seller = _seller_for(handle)
    try:
        return password_reset.reset_shopper(seller, body.token, body.password)
    except password_reset.ResetError as e:
        raise HTTPException(400, str(e))


# ---------------------------------------------------------
# Frontend
# ---------------------------------------------------------
if os.path.isdir(SMART_DIR):
    app.mount("/smart-static", StaticFiles(directory=SMART_DIR), name="smart-static")


STORE_DIR = os.path.join(SMART_DIR, "storefront")
if os.path.isdir(STORE_DIR):
    app.mount("/store-static", StaticFiles(directory=STORE_DIR), name="store-static")


def _meta_tags(meta: dict, url: str) -> str:
    """The head a crawler and a WhatsApp link preview actually read.

    The storefront is a one-page app, so without this every page of every store
    is `<title>Store</title>` and a pasted link arrives as naked grey text —
    which, in a market where the share sheet is the shopfront, is the whole
    difference between a link that sells and one that does not.
    """
    def esc(v: str) -> str:
        return (str(v or "").replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))

    img = meta.get("image") or ""
    if img and img.startswith("/"):
        img = url.split("/s/")[0].rstrip("/") + img
    tags = [
        f"<title>{esc(meta['title'])}</title>",
        f'<meta name="description" content="{esc(meta["description"])}" />',
        f'<link rel="canonical" href="{esc(url)}" />',
        f'<meta property="og:type" content="website" />',
        f'<meta property="og:site_name" content="{esc(meta["site_name"])}" />',
        f'<meta property="og:title" content="{esc(meta["title"])}" />',
        f'<meta property="og:description" content="{esc(meta["description"])}" />',
        f'<meta property="og:url" content="{esc(url)}" />',
        f'<meta name="twitter:card" content="{"summary_large_image" if img else "summary"}" />',
        f'<meta name="twitter:title" content="{esc(meta["title"])}" />',
        f'<meta name="twitter:description" content="{esc(meta["description"])}" />',
    ]
    if img:
        tags.append(f'<meta property="og:image" content="{esc(img)}" />')
        tags.append(f'<meta name="twitter:image" content="{esc(img)}" />')
    if meta.get("keywords"):
        tags.append(f'<meta name="keywords" content="{esc(meta["keywords"])}" />')
    return "\n".join(tags)


def _render_store(handle: str, request: Request, product_id: str = "") -> Response:
    index = os.path.join(STORE_DIR, "store.html")
    if not os.path.exists(index):
        raise HTTPException(404, "Storefront UI not found.")
    owner = sitebuilder.resolve_handle(handle)
    if not owner:
        raise HTTPException(404, "No store at this address.")

    site = sitebuilder.get_site(owner)
    product = None
    if product_id:
        product = next((p for p in products.storefront_payload(owner)
                        if p["id"] == product_id), None)
    meta = sitebuilder.seo_meta(handle, site, product)
    url = f"{_public_base_url(request)}/s/{handle}" + (f"/p/{product_id}" if product else "")

    with open(index, encoding="utf-8") as fh:
        html = fh.read()
    html = html.replace("<title>Store</title>", _meta_tags(meta, url))
    return Response(content=html, media_type="text/html",
                    headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"})


@app.get("/s/{handle}")
def storefront_page(handle: str, request: Request):
    """A seller's own website. One page app; it fetches /api/shop/<handle>/site."""
    return _render_store(handle, request)


@app.get("/s/{handle}/p/{product_id}")
def storefront_product_page(handle: str, product_id: str, request: Request):
    """A product's own address, so a shopper can share the thing, not the shop."""
    return _render_store(handle, request, product_id)


@app.get("/s/{handle}/sitemap.xml")
def storefront_sitemap(handle: str, request: Request):
    owner = sitebuilder.resolve_handle(handle)
    if not owner or not sitebuilder.get_site(owner).get("published"):
        raise HTTPException(404, "No store at this address.")
    base = f"{_public_base_url(request)}/s/{handle}"
    urls = [base] + [f"{base}/p/{p['id']}" for p in products.storefront_payload(owner)]
    body = "".join(f"<url><loc>{u}</loc></url>" for u in urls)
    return Response(
        content=f'<?xml version="1.0" encoding="UTF-8"?>'
                f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>',
        media_type="application/xml")


@app.get("/robots.txt")
def robots(request: Request):
    return Response(content=f"User-agent: *\nAllow: /\nSitemap: {_public_base_url(request)}/sitemap.xml\n",
                    media_type="text/plain")


@app.get("/smart")
def smart_page():
    index = os.path.join(SMART_DIR, "smart.html")
    if not os.path.exists(index):
        raise HTTPException(404, "Smart CafeX UI not found.")
    return FileResponse(index, headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"})


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def landing():
    return FileResponse(os.path.join(STATIC_DIR, "landing.html"))


@app.get("/app")
def app_page():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/privacy")
def privacy_page():
    return FileResponse(os.path.join(STATIC_DIR, "privacy.html"))


# =========================================================================
# GST, invoicing and shipping labels
# =========================================================================
def _flag_cancel_requests(seller: str, orders: list[dict]) -> list[dict]:
    """Mark orders that already have an open cancellation request.

    Both the shopper's order list and the seller's Orders module read this, so
    a shopper cannot fire off five requests for the same parcel and the seller
    is never shown a Cancel control for something already in the inbox."""
    try:
        open_ids = {r["ref_id"] for r in cancel_requests.open_requests(seller)}
    except Exception:  # noqa: BLE001
        return orders
    for o in orders:
        o["cancel_requested"] = o.get("id") in open_ids
    return orders


def _seller_profile(email: str) -> dict:
    """The seller identity a label or invoice needs, assembled from GST
    settings with the site as a fallback for the trading name."""
    s = invoices.get_settings(email)
    site = sitebuilder.get_site(email)
    return {**s, "business_name": s.get("legal_name") or site.get("name") or ""}


@app.get("/api/gst/settings")
def gst_settings(authorization: str | None = Header(default=None)):
    return invoices.settings_status(require_user(authorization))


@app.post("/api/gst/settings")
def gst_settings_save(body: GstSettingsBody,
                      authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    invoices.save_settings(email, body.patch or {})
    return invoices.settings_status(email)


@app.get("/api/gst/check")
def gst_check(gstin: str = "", authorization: str | None = Header(default=None)):
    require_user(authorization)
    return gst.describe_gstin(gstin)


@app.get("/api/gst/rate")
def gst_rate(hsn: str = "", price: float = 0, name: str = "",
             authorization: str | None = Header(default=None)):
    """Live rate preview while a seller types an HSN into the product form."""
    require_user(authorization)
    return gst.resolve_rate(hsn, int(round(price * 100)), name, inclusive=True)


@app.get("/api/gst/suggest-hsn")
def gst_suggest(category: str = "", name: str = "",
                authorization: str | None = Header(default=None)):
    require_user(authorization)
    return {"hsn": gst.suggest_hsn(category, name)}


@app.get("/api/invoices")
def invoice_list(fy: str = "", authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    return {"invoices": invoices.listing(email, fy),
            "fy": fy or gst.financial_year(),
            "settings": invoices.settings_status(email)}


@app.get("/api/invoices/preview")
def invoice_preview(order_id: str, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    order = next((o for o in storefront.get_orders(email) if o.get("id") == order_id), None)
    if not order:
        raise HTTPException(404, "Order not found")
    existing = invoices.for_order(email, order_id)
    return {"preview": invoices.build_from_order(email, order), "existing": existing}


@app.post("/api/invoices/issue")
def invoice_issue(body: IssueInvoiceBody,
                  authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    order = next((o for o in storefront.get_orders(email) if o.get("id") == body.order_id), None)
    if not order:
        raise HTTPException(404, "Order not found")
    return invoices.issue(email, order, force=body.force)


@app.post("/api/invoices/cancel")
def invoice_cancel(body: CancelInvoiceBody,
                   authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    return invoices.cancel(email, body.invoice_id, body.reason or "")


@app.get("/api/invoices/{invoice_id}/pdf")
def invoice_download(invoice_id: str, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    inv = invoices.get(email, invoice_id)
    if not inv:
        raise HTTPException(404, "Invoice not found")
    pdf = invoice_pdf.build(inv)
    name = (inv.get("number") or invoice_id).replace("/", "-")
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}.pdf"'})


@app.get("/api/gstr1")
def gstr1_view(fy: str = "", authorization: str | None = Header(default=None)):
    return invoices.gstr1(require_user(authorization), fy)


@app.get("/api/gstr1.csv")
def gstr1_csv(fy: str = "", authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    csv = invoices.gstr1_csv(email, fy)
    return Response(content=csv, media_type="text/csv",
                    headers={"Content-Disposition":
                             f'attachment; filename="gstr1-{fy or gst.financial_year()}.csv"'})


@app.post("/api/orders/labels")
def order_labels(body: LabelBody, authorization: str | None = Header(default=None)):
    """The Generate Bill Sticker button. Takes one order or a whole morning's
    dispatch and returns a single print-ready PDF."""
    email = require_user(authorization)
    wanted = set(body.order_ids or [])
    rows = [o for o in storefront.get_orders(email) if not wanted or o.get("id") in wanted]
    if not rows:
        raise HTTPException(404, "No matching orders")
    pdf = labels.build_many(rows, _seller_profile(email), sitebuilder.get_site(email))
    fname = ("label-" + rows[0].get("order_no", "order")) if len(rows) == 1 else \
            f"labels-{len(rows)}-orders"
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}.pdf"'})


# =========================================================================
# Cancellation requests — the WhatsApp conversation, not a fired action
# =========================================================================
@app.post("/api/shop/{handle}/cancel-request")
def shopper_cancel_request(handle: str, body: CancelRequestBody, request: Request):
    """Called from the shopper's own order page. Deliberately does NOT cancel."""
    seller = sitebuilder.resolve_handle(handle)
    if not seller:
        raise HTTPException(404, "Store not found")
    order = next((o for o in storefront.get_orders(seller) if o.get("id") == body.order_id), None)
    if not order:
        raise HTTPException(404, "Order not found")
    if order.get("status") in ("delivered", "cancelled"):
        return {"ok": False,
                "message": "This order is already " + str(order.get("status")) + "."}

    req = cancel_requests.raise_request(
        seller, kind="order", ref_id=order["id"], ref_no=order.get("order_no", ""),
        reason_code=body.reason_code, reason_text=body.reason_text or "",
        raised_by="shopper",
        counterparty={"name": order.get("customer_name"), "phone": order.get("phone")})

    site = sitebuilder.get_site(seller)
    payload = cancel_requests.notify_payload(
        seller, req, site.get("name") or "the store",
        (invoices.get_settings(seller).get("pickup_address") or {}).get("phone")
        or site.get("contact_phone") or "")

    try:
        messaging.send(to_email=seller,
                       subject=f"Cancellation request - order {order.get('order_no')}",
                       text=payload["seller_text"])
    except Exception:  # noqa: BLE001
        # A failed email must never lose the request itself. The seller still
        # sees it in Orders, and the WhatsApp link still works.
        pass
    cancel_requests.mark_notified(seller, req["id"])
    cache.clear(seller)

    return {"ok": True, "request": req,
            "message": "We've told the seller. Nothing is cancelled yet — they "
                       "will message you on WhatsApp shortly.",
            "seller_wa": payload["seller_wa"]}


@app.get("/api/cancel-requests")
def cancel_request_list(authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    site = sitebuilder.get_site(email)
    rows = cancel_requests.open_requests(email)
    for r in rows:
        r["links"] = cancel_requests.notify_payload(email, r, site.get("name") or "our store", "")
    return {"open": rows, "history": cancel_requests.history(email, 60),
            "summary": cancel_requests.summary(email)}


@app.post("/api/cancel-requests/resolve")
def cancel_request_resolve(body: ResolveCancelBody,
                           authorization: str | None = Header(default=None)):
    """Approving is the ONLY thing that actually cancels."""
    email = require_user(authorization)
    req = cancel_requests.resolve(email, body.request_id, body.decision, body.note or "")
    if req.get("error"):
        raise HTTPException(404, req["error"])
    if body.decision == "approved":
        if req.get("kind") == "po":
            supply.set_po_status(email, req["ref_id"], "cancelled",
                                 note=req.get("reason_label", ""))
        else:
            storefront.set_status(email, req["ref_id"], "cancelled", by="shopper",
                                  reason=req.get("reason_code") or "requested")
    cache.clear(email)
    return {"request": req, "summary": cancel_requests.summary(email)}


@app.post("/api/purchase-orders/cancel-request")
def po_cancel_request(body: PoCancelRequestBody,
                      authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    po = supply.get_po(email, body.po_number)
    if not po:
        raise HTTPException(404, "Purchase order not found")
    sup = po.get("supplier") or {}
    req = cancel_requests.raise_request(
        email, kind="po", ref_id=str(po.get("po_number")), ref_no=str(po.get("po_number")),
        reason_code=body.reason_code, reason_text=body.reason_text or "",
        raised_by="seller",
        counterparty={"name": sup.get("name"), "phone": sup.get("phone")})
    site = sitebuilder.get_site(email)
    return {"request": req,
            "links": cancel_requests.notify_payload(email, req,
                                                    site.get("name") or "our store", "")}


# =========================================================================
# Purchase orders — the manual path
# =========================================================================
@app.post("/api/purchase-orders/manual")
def po_manual(body: ManualPoBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    try:
        po = supply.create_manual_po(email, body.supplier or {}, body.lines or [],
                                     body.expected_on or "", body.terms or "",
                                     body.note or "")
    except ValueError as e:
        raise HTTPException(400, str(e))
    cache.clear(email)
    return po


@app.post("/api/purchase-orders/status")
def po_status(body: PoStatusBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    try:
        po = supply.set_po_status(email, body.po_number, body.status, body.note or "")
    except ValueError as e:
        raise HTTPException(400, str(e))
    if po is None:
        raise HTTPException(404, "Purchase order not found")
    cache.clear(email)
    return po


# =========================================================================
# Social Media Manager
# =========================================================================
def _social_catalogue(email: str) -> list[dict]:
    out = []
    for p in products.listed_products(email):
        out.append({"id": p.get("id"), "name": p.get("name"), "price": p.get("price"),
                    "description": p.get("description"), "category": p.get("category"),
                    "stock": p.get("stock")})
    return out


@app.get("/api/social")
def social_home(authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    return {
        "settings": social.get_settings(email),
        "pillars": social.PILLARS,
        "cadence": social.CADENCE,
        "formats": social.FORMATS,
        "languages": social.LANGUAGES,
        "week": social.week(email),
        "radar": social.radar(email),
        "working": social.whats_working(email),
        "ai": aiprovider.status(),
        "offer_cap": social.OFFER_CAP_PERCENT,
        "catalogue_size": len(_social_catalogue(email)),
    }


@app.post("/api/social/settings")
def social_settings(body: SocialSettingsBody,
                    authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    return social.save_settings(email, body.patch or {})


@app.post("/api/social/week")
def social_week(body: SocialWeekBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    cat = _social_catalogue(email)
    if not cat:
        raise HTTPException(400, "Add a product first — there is nothing to post about.")
    # Replaces this window's undecided drafts rather than appending to them.
    # Without that, pressing Plan my week twice produced two posts at the same
    # day and time and the week doubled on every press.
    made = (social.plan_ahead(email, cat, body.weeks)
            if body.weeks and body.weeks > 1 else social.build_week(email, cat))
    return {"posts": made, "week": social.week(email)}


@app.post("/api/social/approve-all")
def social_approve(authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    return {**social.approve_all(email), "week": social.week(email)}


@app.get("/api/social/post/{post_id}")
def social_post_get(post_id: str, authorization: str | None = Header(default=None)):
    """One post by id -- lets the Approval panel's 'Details' open the editor
    for a post that isn't necessarily in the currently-loaded calendar month
    (the panel only shows the next 7 days; the post itself can be further out)."""
    email = require_user(authorization)
    p = social.get_post(email, post_id)
    if not p:
        raise HTTPException(404, "That post no longer exists.")
    return p


@app.post("/api/social/clear")
def social_clear(authorization: str | None = Header(default=None)):
    """The full reset: every planned post and tracked campaign, gone. For
    walking away from a plan entirely rather than deciding it post by post."""
    email = require_user(authorization)
    n = social.clear_plan(email)
    cache.clear(email)
    return {"cleared": n}


@app.post("/api/social/post")
def social_post_update(body: SocialPostBody,
                       authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    p = social.update_post(email, body.post_id, body.patch or {})
    if p.get("error"):
        raise HTTPException(404, p["error"])
    return p


@app.post("/api/social/state")
def social_post_state(body: SocialStateBody,
                      authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    p = social.set_state(email, body.post_id, body.state)
    if p.get("error"):
        raise HTTPException(400, p["error"])
    return p


@app.post("/api/social/regenerate")
def social_regenerate(body: SocialCloneBody,
                      authorization: str | None = Header(default=None)):
    """Rewrite one post's caption without touching the rest of the week."""
    email = require_user(authorization)
    post = next((p for p in social.week(email) if p.get("id") == body.post_id), None)
    if not post:
        raise HTTPException(404, "Post not found")
    cat = {p["id"]: p for p in _social_catalogue(email)}
    product = cat.get(post.get("product_id")) or {"name": post.get("product_name")}
    cap = social.write_caption(email, product, post.get("pillar") or "detail")
    return social.update_post(email, body.post_id, {
        "hook": cap.get("hook"), "body": cap.get("body"),
        "question": cap.get("question"), "cta": cap.get("cta"),
        "tags": cap.get("tags")})


@app.post("/api/social/regenerate-script")
def social_regenerate_script(body: SocialCloneBody,
                             authorization: str | None = Header(default=None)):
    """Rewrite one reel's shot list without touching the rest of the week.

    Also the way a reel planned before scripts existed gets one: the editor
    offers this same action whenever a reel post's script is empty."""
    email = require_user(authorization)
    post = next((p for p in social.week(email) if p.get("id") == body.post_id), None)
    if not post:
        raise HTTPException(404, "Post not found")
    if post.get("format") != "reel":
        raise HTTPException(400, "Only reel-format posts get a script.")
    cat = {p["id"]: p for p in _social_catalogue(email)}
    product = cat.get(post.get("product_id")) or {"name": post.get("product_name")}
    occasion = ({"name": post["occasion"], "days_away": post.get("occasion_days") or 0}
               if post.get("occasion") else None)
    script = social.write_reel_script(email, product, post.get("pillar") or "detail",
                                      occasion=occasion,
                                      shot_type=post.get("shot_type") or "",
                                      theme=post.get("theme_note") or "")
    return social.update_post(email, body.post_id, {"script": script})


@app.post("/api/social/clone")
def social_clone(body: SocialCloneBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    p = social.clone_winner(email, body.post_id, _social_catalogue(email))
    if p.get("error"):
        raise HTTPException(400, p["error"])
    return p


@app.get("/api/social/shoot-list")
def social_shoot(authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    return social.shoot_list(email, _social_catalogue(email))


# =========================================================================
# AI provider status — so a seller can see what is writing their copy
# =========================================================================
@app.get("/api/ai/providers")
def ai_providers(authorization: str | None = Header(default=None)):
    require_user(authorization)
    st = aiprovider.status()
    st["storage_durable"] = media.durable()
    return st


# =========================================================================
# Product Studio — design language and image generation
# =========================================================================
@app.get("/api/studio/design-language")
def studio_design_language(authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    brand = studio.get_brand(email)
    return {"refs": brand.get("refs") or [], "aesthetic": brand.get("aesthetic") or "",
            "aesthetic_from": brand.get("aesthetic_from") or 0,
            "vision_ready": aiprovider.vision_ready(),
            "image_engine": studio.image_engine()}


@app.post("/api/studio/design-language/add")
def studio_ref_add(body: StudioRefBody,
                   authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    return studio.add_ref(email, body.url)


@app.post("/api/studio/design-language/remove")
def studio_ref_remove(body: StudioRefBody,
                      authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    return studio.remove_ref(email, body.url)


@app.post("/api/studio/design-language/read")
def studio_read_aesthetic(authorization: str | None = Header(default=None)):
    """Look at the reference images and write what they have in common."""
    email = require_user(authorization)
    res = studio.read_aesthetic(email)
    if not res.get("ok"):
        raise HTTPException(400, res.get("reason", "Could not read the references."))
    cache.clear(email)
    return res


@app.post("/api/studio/read-shots")
def studio_read_shots(body: StudioReadShotsBody,
                      authorization: str | None = Header(default=None)):
    """Look at a product's own photographs and write what the thing is.

    This is the step that makes generated imagery resemble the actual product
    rather than a plausible invention of one."""
    email = require_user(authorization)
    res = studio.read_product_shots(email, body.product_id)
    if not res.get("ok"):
        raise HTTPException(400, res.get("reason", "Could not read the photos."))
    return res


@app.post("/api/studio/image")
def studio_image_only(body: StudioImageOnlyBody,
                      authorization: str | None = Header(default=None)):
    """Generate a picture and nothing else — no caption rewritten over the top.

    When `post_id` is given the image is attached to that planned post, so it
    shows up in the Social Media Manager's week -- and, if the post is tied
    to a festival, that festival's colours and motifs are worked into the
    photo too (see studio.guidance_for). Without this the picture had no way
    to know it was a Ganesh Chaturthi post at all; only the caption did."""
    email = require_user(authorization)
    occasion_key = ""
    shot_type = body.shot_type or ""
    if body.post_id:
        post = social.get_post(email, body.post_id)
        if post:
            occasion_key = post.get("occasion_key") or ""
            # The beat already knows what kind of photograph it is; an explicit
            # shot_type on the request still wins, so the editor can override.
            shot_type = shot_type or post.get("shot_type") or ""
    try:
        img = studio.generate_image_only(email, body.product_id,
                                         body.pillar or "", body.format or "",
                                         body.angle or "",
                                         use_reference=body.use_reference,
                                         strength=body.strength,
                                         occasion_key=occasion_key,
                                         shot_type=shot_type,
                                         engine=body.engine or "")
    except (RuntimeError, ValueError) as e:
        raise HTTPException(400, str(e))
    if body.post_id:
        social.attach_image(email, body.post_id, img["url"], True, img.get("prompt", ""))
    cache.clear(email)
    return img


@app.post("/api/social/attach-image")
def social_attach(body: SocialAttachBody,
                  authorization: str | None = Header(default=None)):
    """Attach any image — generated, uploaded, or exported from elsewhere."""
    email = require_user(authorization)
    p = social.attach_image(email, body.post_id, body.url, False, "")
    if p.get("error"):
        raise HTTPException(404, p["error"])
    return p


class SocialReadyBody(BaseModel):
    post_id: str
    # A reel is filmed or generated, never drawn — so "make the media for me"
    # means different things per format and the caller says which it wants.
    generate: bool = True


@app.post("/api/social/approve-ready")
def social_approve_ready(body: SocialReadyBody,
                         authorization: str | None = Header(default=None)):
    """Approve a post AND give it the media it needs, in one action.

    WHY: the Approval panel's Approve button scheduled a post that had no
    picture on it. The seller then had to find that post again in the calendar,
    open it, generate a picture and save — three steps later, for something
    they had already said yes to. Approving now means "yes, and make it ready".

    The two formats need different things and get them:
      * an IMAGE post has its picture generated here and is then scheduled;
      * a REEL cannot be — there is no single photograph that is a video — so
        its shot list and paste-ready prompt are returned instead, and it is
        scheduled as ready-to-film rather than pretending it is finished.

    A generation failure does NOT block the approval. The seller's decision is
    the valuable part and it is honoured either way; the reason is reported so
    the panel can say what still needs doing."""
    email = require_user(authorization)
    post = social.get_post(email, body.post_id)
    if not post:
        raise HTTPException(404, "Post not found")

    is_reel = post.get("format") == "reel"
    made, media_error, script = None, "", None

    if is_reel:
        # Nothing to draw. Hand back what the seller actually needs to produce
        # the clip: the beats to film, and the prompt to paste into a video AI.
        script = post.get("script") or None
        if not script or not (script.get("beats") or []):
            cat = {p["id"]: p for p in _social_catalogue(email)}
            product = cat.get(post.get("product_id")) or {"name": post.get("product_name")}
            occasion = ({"name": post["occasion"],
                         "days_away": post.get("occasion_days") or 0}
                        if post.get("occasion") else None)
            script = social.write_reel_script(
                email, product, post.get("pillar") or "detail", occasion=occasion,
                shot_type=post.get("shot_type") or "",
                theme=post.get("theme_note") or "")
            social.update_post(email, body.post_id, {"script": script})
    elif body.generate and not post.get("image_url"):
        try:
            made = studio.generate_image_only(
                email, post.get("product_id") or "",
                post.get("pillar") or "", post.get("format") or "",
                use_reference=True,
                occasion_key=post.get("occasion_key") or "",
                shot_type=post.get("shot_type") or "")
            social.attach_image(email, body.post_id, made["url"], True,
                               made.get("prompt", ""))
        except (RuntimeError, ValueError) as e:
            media_error = str(e)

    p = social.set_state(email, body.post_id, "scheduled")
    if p.get("error"):
        raise HTTPException(400, p["error"])
    cache.clear(email)
    return {"post": social.get_post(email, body.post_id),
            "image": made, "script": script, "is_reel": is_reel,
            "media_error": media_error,
            "ready": social.post_ready(social.get_post(email, body.post_id) or {})}


@app.get("/api/studio/video-engine")
def studio_video_engine(authorization: str | None = Header(default=None)):
    """Whether clips can be generated, what one costs, and every engine the
    seller may choose between — asked before the button does anything, so the
    price is never a surprise."""
    require_user(authorization)
    return {**studio.video_engine(), "engines": studio.video_engines()}


@app.get("/api/studio/image-engines")
def studio_image_engines(reshoot: bool = False,
                         authorization: str | None = Header(default=None)):
    """Every drawing engine this server can offer, so the seller picks rather
    than inheriting whatever the server preferred.

    `reshoot=true` drops the engines that cannot start from the seller's own
    photograph. Offering one there would mean quietly returning a picture of a
    product they do not sell."""
    require_user(authorization)
    rows = studio.image_engines(for_reshoot=reshoot)
    return {"engines": rows, "default": rows[0]["id"] if rows else ""}


class StudioVideoBody(BaseModel):
    product_id: str
    post_id: str | None = ""
    prompt: str | None = ""
    engine: str | None = ""


@app.post("/api/studio/video")
def studio_video(body: StudioVideoBody,
                 authorization: str | None = Header(default=None)):
    """Generate a short clip from the seller's own product photograph.

    Slow — around a minute — and it costs real money per call, so the UI
    confirms the price first and warns that the tab can be left alone."""
    email = require_user(authorization)
    try:
        vid = studio.generate_video(email, body.product_id, body.prompt or "",
                                    engine=body.engine or "")
    except (RuntimeError, ValueError) as e:
        raise HTTPException(400, str(e))
    if body.post_id:
        social.attach_video(email, body.post_id, vid["url"])
    cache.clear(email)
    return vid


@app.post("/api/social/attach-video")
def social_attach_video(body: SocialAttachBody,
                        authorization: str | None = Header(default=None)):
    """Attach the finished clip to a planned post — filmed on a phone, or
    generated from the shot-list prompt and downloaded.

    Upload the file through /api/site/image first (it already takes MP4 and
    WEBM up to 48MB and stores them durably); this endpoint only records which
    clip belongs to which post. Sending an empty url takes the clip off again,
    so a wrong upload is one action to undo rather than a reason to delete a
    post the seller has already written and scheduled."""
    email = require_user(authorization)
    p = social.attach_video(email, body.post_id, body.url)
    if p.get("error"):
        raise HTTPException(404, p["error"])
    cache.clear(email)
    return p


@app.get("/api/managers")
def manager_desks(authorization: str | None = Header(default=None)):
    """Who is on the team and what each of them has waiting."""
    email = require_user(authorization)
    cards = smart.build_insights(email)
    return {"managers": list(personas.MANAGERS.values()),
            "desks": personas.desks(cards), "pending": len(cards)}


@app.get("/api/social/month")
def social_month(year: int = 0, month: int = 0,
                 authorization: str | None = Header(default=None)):
    """One month of the plan, laid out as a calendar.

    Festivals come back whether or not anything is planned for them — the empty
    ones are the point. A seller flipping to October should see Navratri and
    Diwali sitting there with nothing against them."""
    email = require_user(authorization)
    from datetime import date as _date
    t = _date.today()
    return social.month(email, year or t.year, month or t.month)


@app.get("/api/social/upcoming")
def social_upcoming(days: int = 5, authorization: str | None = Header(default=None)):
    """The next few days, for the home screen."""
    email = require_user(authorization)
    rows = social.upcoming(email, days)
    return {"posts": rows,
            "needs_decision": len([p for p in rows if p.get("state") == "draft"])}


# =========================================================================
# Festival campaigns — a plan with a shape, not a queue of suggestions
# =========================================================================
@app.get("/api/social/festivals")
def social_festivals(authorization: str | None = Header(default=None)):
    """The festivals worth this seller's time, best first.

    Filtered by category weight rather than listed exhaustively: a perfume
    seller offered Dhanteras learns quickly that the suggestions are not
    thought through."""
    email = require_user(authorization)
    s = social.get_settings(email)
    cat = s.get("category") or "clothing"
    live = {c["key"]: c for c in social.campaigns(email)}
    out = []
    for f in playbook.for_category(cat):
        prev = social.campaign_preview(email, f["key"])
        out.append({
            "key": f["key"], "name": f["name"], "weight": f["weight_for"],
            "core": f["core"], "buys_for": f["buys_for"],
            "date": prev.get("date", ""), "days_out": prev.get("days_out"),
            "undated": bool(prev.get("undated")),
            "late": bool(prev.get("late")),
            "running": f["key"] in live,
            "note": f.get("note", ""),
        })
    return {"category": cat, "festivals": out,
            "campaigns": social.campaigns(email)}


@app.get("/api/social/campaign")
def social_campaign_preview(festival: str,
                            authorization: str | None = Header(default=None)):
    """What the campaign would be, before anything is created."""
    email = require_user(authorization)
    return social.campaign_preview(email, festival)


@app.post("/api/social/campaign")
def social_campaign_start(body: FestivalCampaignBody,
                          authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    cat = _social_catalogue(email)
    if not cat:
        raise HTTPException(400, "Add a product first — there is nothing to post about.")
    res = social.start_campaign(email, body.festival, cat)
    if res.get("error"):
        raise HTTPException(400, res["error"])
    cache.clear(email)
    return res


@app.get("/api/social/playbook")
def social_playbook(festival: str, authorization: str | None = Header(default=None)):
    """The full content library entry — angles, taglines, cautions, what people
    actually buy. Shown to the seller, not just fed to the model."""
    email = require_user(authorization)
    s = social.get_settings(email)
    b = playbook.brief(festival, s.get("category") or "clothing")
    if not b:
        raise HTTPException(404, "No playbook for that festival")
    return b
