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
import io
import json
import os
import secrets

import pandas as pd
from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.core import (ad_analytics, ai, analytics, auth, billing, complaints, connectors,
                          content_gen, email_intake, i18n, instagram, joiner, mapper,
                          pos_formats, position_strategy, positioning, pricing, product_config,
                          report_pdf, smart, templates, user_store)
from backend.core import commerce, secrets_store, db, supply, products

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


@app.middleware("http")
async def _no_cache_frontend(request, call_next):
    """Never let the browser cache the app shell / JS / CSS. This is what
    prevents an old smart.js from sticking around after an update (the cause of
    the 'upload shows Uploading then nothing / no mapping popup' reports)."""
    resp = await call_next(request)
    path = request.url.path
    if (path.startswith("/smart") or path.startswith("/static") or path == "/app"
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


def _paywall(product_id: str, message: str) -> HTTPException:
    """402 with a structured detail the frontend recognises to open the pricing modal."""
    return HTTPException(status_code=402, detail={
        "code": "paywall", "product": product_id, "message": message,
    })


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
    Free during launch; ₹249/report after (included in Chain)."""
    sess = get_session(x_session_id)
    if not pricing.launch_mode():
        email = require_user(authorization)
        if not billing.check_and_consume(email, "complaints_report"):
            raise _paywall(
                "complaints_report",
                "The Complaint Trends Report is ₹249 per report — a fix-first action plan "
                "plus complaint trends and a severity quadrant from your own reviews.",
            )
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
    fname = f"{_uuid.uuid4().hex}{ext}"
    fpath = os.path.join(_IMG_DIR, fname)
    with open(fpath, "wb") as out:
        out.write(content)
    public_url = f"/generated_images/{fname}"
    # Attach to the current suggestion so refreshing keeps the uploaded image.
    if insight_id:
        smart.save_content_suggestion(email, insight_id, {"image_url": public_url})
    return {"ok": True, "image_url": public_url, "filename": f.filename}


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
# Serve locally-generated post images so Instagram can fetch them.
# ---------------------------------------------------------
_IMG_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "generated_images")
os.makedirs(_IMG_DIR, exist_ok=True)
app.mount("/generated_images", StaticFiles(directory=_IMG_DIR), name="generated_images")


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
def load_demo(x_session_id: str | None = Header(default=None)):
    """Load 90 days of realistic sample café transactions into the session,
    pre-mapped, so a visitor sees full value before uploading anything."""
    sess = get_session(x_session_id)
    if not os.path.exists(SAMPLE_FILE):
        raise HTTPException(503, "Sample dataset missing on the server.")
    df = pd.read_csv(SAMPLE_FILE)
    fid = secrets.token_hex(6)
    sess.raw_dfs[fid] = df
    sess.file_names[fid] = "Sample Café (90 days)"
    identity = {c: c for c in ["date", "customer_id", "customer_name", "order_id",
                               "product", "category", "subcategory", "quantity", "amount"]}
    sess.txns_df, _ = mapper.build_transactions(df, identity)
    sess.mapped_file_id = fid
    return {"files": [_file_info(fid, sess)], "mapped": True}


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
    GTM gate: this is the moat product (₹349/report) once launch mode ends —
    free for everyone (no login) during launch, included in the Chain plan."""
    get_session(x_session_id)
    if not pricing.launch_mode():
        email = require_user(authorization)
        if not billing.check_and_consume(email, "positioning_report"):
            raise _paywall(
                "positioning_report",
                "The Market Position & Reputation Report is ₹349 per report — see how "
                "customers rank you vs. nearby cafés, straight from review language.",
            )
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

    customers = analytics.at_risk_customers(txns)
    if not customers:
        return {"customers": [], "usage": _usage(email)}

    # GTM gate: the at-risk LIST (RFM page) is free forever; generating the
    # ready-to-send campaign is the paid action (₹199/campaign) once launch
    # mode ends. Chain plan includes unlimited campaigns.
    if not billing.check_and_consume(email, "winback_campaign"):
        raise _paywall(
            "winback_campaign",
            "Your at-risk list is free — generating the ready-to-send campaign is ₹199. "
            "One campaign round: personalized messages + coupons + Excel export.",
        )

    # template + market-basket-analysis based — no OpenAI call, no rate limit needed
    results = templates.build_winback_messages(customers)

    _winback_cache.setdefault(x_session_id, WinbackSession()).rows = results
    return {"customers": results, "usage": _usage(email)}


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
    Launch mode and the Chain plan are unlimited."""
    if pricing.launch_mode() or billing.is_unlimited(email):
        auth.check_usage_limit(email, feature)  # still log usage for analytics; never blocks here
        return
    if auth.check_usage_limit(email, feature):
        return
    if billing.consume_credit(email, "ai_topup"):
        return
    raise _paywall(
        "ai_topup",
        "You've used today's 5 free AI runs. Add 10 more for ₹99 (used automatically), "
        "come back tomorrow, or go unlimited with the Chain plan.",
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
    product: str  # catalog product_id: winback_campaign | positioning_report | ai_topup | chain_monthly


class VerifyBody(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    product: str | None = None  # server-side pending-order record takes precedence


@app.post("/api/pay/create-order")
def create_order(body: OrderBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    if body.product == "chain_monthly" and billing.get_plan(email) == "chain":
        raise HTTPException(400, "You are already on the Chain plan 🎉")
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
def smart_state(x_session_id: str | None = Header(default=None),
                authorization: str | None = Header(default=None)):
    email = require_user(authorization)
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
        fpath = os.path.join(_IMG_DIR, os.path.basename(url))
        if os.path.exists(fpath):
            with open(fpath, "rb") as f:
                data = f.read()
            ext = (os.path.splitext(fpath)[1].lstrip(".") or "png").lower()
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


@app.get("/api/supply/state")
def supply_state(authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    return _supply_payload(email)


@app.post("/api/supply/item")
def supply_item(body: SupplyItemBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
    try:
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
    try:
        products.upsert_product(email, body.dict())
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _products_payload(email)


@app.post("/api/products/item/delete")
def products_item_delete(body: ProductIdBody, authorization: str | None = Header(default=None)):
    email = require_user(authorization)
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


# ---------------------------------------------------------
# Frontend
# ---------------------------------------------------------
if os.path.isdir(SMART_DIR):
    app.mount("/smart-static", StaticFiles(directory=SMART_DIR), name="smart-static")


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
