"""
AI writing on the seller's own ChatGPT plan.

Once a seller has signed in with ChatGPT and allowed it (chatgpt_auth.py), their
OAuth access token stands in for an API key on POST https://api.openai.com/v1/
responses, and the request counts against the usage included in THEIR ChatGPT
Plus or Pro plan, or against their ChatGPT credits if they allowed apps to use
them. We pay nothing for it and meter none of it.

OPENAI'S RULES FOR THIS ROUTE ("Preview limitations", developers.openai.com/siwc)
  * `store: false` and `stream: true` on every request; `input` is an array; the
    system prompt goes in `instructions` (a system-role input item is refused);
  * `temperature`, `max_output_tokens`, `metadata`, `user`, `truncation`,
    `previous_response_id` and several other fields are refused, so they are
    never sent. Length is held by the prompts, which already ask for it;
  * no hosted tools, and in particular NO IMAGE GENERATION. Pictures stay on
    the image engines in studio.py. Reading a picture is fine, image INPUT is
    supported, so describing a product photo can run here;
  * the only success is `response.completed`. A usage limit can arrive as an
    HTTP 429 before the stream opens, or as `response.failed` half way through.

THE MODEL
  GPT-6 Luna, OpenAI's "most efficient model for focused, high-volume tasks",
  at low reasoning effort. Every call spends the seller's own plan, and a
  caption does not need a flagship model thinking hard about it. It has to be a
  model the seller's account can use, so the choice is checked against their
  own catalogue (GET /v1/models with their token). CHATGPT_PLAN_MODEL and
  CHATGPT_PLAN_REASONING change it per deployment.

WHEN THEIR USAGE RUNS OUT
  A usage-limit error pauses plan requests for this seller (for as long as a
  Retry-After header says, otherwise ten minutes) and raises LimitReached. The
  browser then offers "Manage usage", which opens ChatGPT's own usage page where
  the reset time, the app's weekly limit and credits all are, and "Use One Tap
  Manager AI this time". No reset time is invented here: OpenAI says outright
  that one cannot be inferred from the error, because the limit that was hit may
  be the seller's own cap for this app rather than their plan.
"""
from __future__ import annotations

import base64
import logging
import os
import threading
import time
from email.utils import parsedate_to_datetime

from backend.core import chatgpt_auth, user_store

log = logging.getLogger("chatgpt_plan")

API_BASE = chatgpt_auth.RESOURCE
DEFAULT_MODEL = "gpt-6-luna"
# If the seller's account does not list Luna, the cheapest others OpenAI
# publishes, in order. Only ever a fallback; the catalogue decides.
FALLBACK_MODELS = ("gpt-6-luna", "gpt-5.6-luna", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-5-mini")
DEFAULT_EFFORT = "low"

STATE_KEY = "chatgpt_plan_state"
DEFAULT_PAUSE = 600                 # seconds, when OpenAI does not say how long
MAX_PAUSE = 7 * 86400
STREAM_DEADLINE = 120               # a caption that takes two minutes is a failure
LIMIT_CODES = {"subscription_sharing_usage_limit_exceeded"}
TEMPORARY_CODES = {"subscription_sharing_usage_unavailable",
                   "subscription_sharing_user_unavailable"}


class LimitReached(Exception):
    """The seller's ChatGPT usage, or the limit they set for this app, is used
    up. Deliberately not a RuntimeError or ValueError: the routes that turn
    those into a 400 or 503 must let this one through to its own handler."""

    def __init__(self, message: str, retry_after: int | None = None,
                 paused_until: float = 0.0, code: str = ""):
        super().__init__(message)
        self.retry_after = retry_after
        self.paused_until = paused_until
        self.code = code

    def public(self) -> dict:
        """What the browser needs to draw the limit screen."""
        return {"manage_url": chatgpt_auth.MANAGE_USAGE_URL,
                "help_url": chatgpt_auth.HELP_URL,
                "retry_after": self.retry_after,
                "paused_until": chatgpt_auth._iso(self.paused_until) if self.paused_until else ""}


class Unavailable(Exception):
    """The plan cannot be used for this request. The caller falls back to the
    app's own AI, which is what the owner chose for this case."""

    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}{': ' + detail if detail else ''}")
        self.reason = reason
        self.detail = detail


class _Failure(Exception):
    def __init__(self, status: int, code: str, message: str = "", param=None,
                 request_id: str = "", retry_after: int | None = None):
        super().__init__(f"{status} {code} {message}".strip())
        self.status = status
        self.code = code or ""
        self.message = message or ""
        self.param = param
        self.request_id = request_id
        self.retry_after = retry_after


# ---------------------------------------------------------------- state ----
# Per seller, not secret: whether their account can share its plan at all, and
# whether plan requests are paused. Written only when something CHANGES, so a
# successful call costs no write.
def _state(email: str) -> dict:
    st = user_store.get_key(email, STATE_KEY, {}) or {}
    return st if isinstance(st, dict) else {}


def _save(email: str, st: dict) -> None:
    user_store.set_key(email, STATE_KEY, st)


def clear_state(email: str) -> None:
    user_store.set_key(email, STATE_KEY, {})


def retry_now(email: str) -> dict:
    """The seller pressed "Try again": they may have raised their limit in
    ChatGPT, or upgraded. Lift every pause; the next request finds out."""
    st = _state(email)
    for k in ("paused_until", "paused_reason", "retry_after", "backoff_until",
              "failures", "blocked_until", "blocked_reason", "eligible"):
        st.pop(k, None)
    _save(email, st)
    return public_state(email)


def after_new_grant(email: str) -> None:
    """A fresh ChatGPT connection. It may be a different account, or the same
    one after an upgrade to Plus, so "not eligible" and any hold-off are
    forgotten. A usage-limit pause is NOT: OpenAI is clear that signing in
    again does not restore usage, so asking again at once would only fail."""
    st = _state(email)
    changed = False
    for k in ("eligible", "eligible_at", "backoff_until", "failures",
              "blocked_until", "blocked_reason"):
        if k in st:
            st.pop(k)
            changed = True
    if changed:
        _save(email, st)
    forget_models(email)


def public_state(email: str) -> dict:
    st = _state(email)
    now = time.time()
    limit = None
    if st.get("paused_until", 0) > now:
        limit = {"paused_until": chatgpt_auth._iso(st["paused_until"]),
                 "retry_after": st.get("retry_after"),
                 "since": chatgpt_auth._iso(st.get("limit_at") or now)}
    return {"eligible": st.get("eligible"), "limit": limit,
            "paused_reason": st.get("paused_reason") or "",
            "blocked": bool(st.get("blocked_until", 0) > now),
            "blocked_reason": st.get("blocked_reason") or "",
            "model": st.get("model") or ""}


def ready(email: str) -> bool:
    """Should this seller's writing try their ChatGPT plan first?

    A limit pause does NOT make this False: while paused, run() raises
    LimitReached straight away, so a person waiting sees the limit screen and
    the background planner falls back, without a request going to OpenAI."""
    if not email or not chatgpt_auth.plan_usage_offered():
        return False
    if not chatgpt_auth.plan_connected(email):
        return False
    st = _state(email)
    now = time.time()
    # Not a Plus or Pro account: asking again on every caption would only fail
    # again. Checked once a day, and "Try again" asks at once.
    if st.get("eligible") is False and now - st.get("eligible_at", 0) < 86400:
        return False
    if st.get("blocked_until", 0) > now or st.get("backoff_until", 0) > now:
        return False
    return True


def preferred_model() -> str:
    return (os.environ.get("CHATGPT_PLAN_MODEL") or DEFAULT_MODEL).strip()


def _effort() -> str:
    return (os.environ.get("CHATGPT_PLAN_REASONING") or DEFAULT_EFFORT).strip().lower()


# --------------------------------------------------------------- models ----
_models_lock = threading.Lock()
_models: dict[str, tuple[float, list[dict]]] = {}
_MODELS_TTL = 3600


def models(email: str, token: str | None = None) -> list[dict]:
    """The models this seller's ChatGPT account may use here, in OpenAI's order
    (only the ones marked for display). Cached for an hour per account."""
    key = (email or "").strip().lower()
    with _models_lock:
        hit = _models.get(key)
    if hit and time.time() - hit[0] < _MODELS_TTL:
        return hit[1]
    token = token or chatgpt_auth.access_token(email)
    if not token:
        raise Unavailable("not_connected")
    import requests
    try:
        r = requests.get(f"{API_BASE}/models", headers={"Authorization": f"Bearer {token}"},
                         timeout=10)
    except Exception as e:  # noqa: BLE001
        raise Unavailable("network", type(e).__name__) from e
    if r.status_code != 200:
        raise Unavailable(f"models_http_{r.status_code}")
    try:
        data = r.json() or {}
    except ValueError:
        raise Unavailable("models_bad_json")
    rows = data.get("models") if isinstance(data.get("models"), list) else (data.get("data") or [])
    out = []
    for m in rows:
        if not isinstance(m, dict):
            continue
        slug = str(m.get("slug") or m.get("id") or "").strip()
        if not slug:
            continue
        if "visibility" in m and m.get("visibility") != "list":
            continue
        out.append({"slug": slug, "display_name": str(m.get("display_name") or slug)})
    with _models_lock:
        _models[key] = (time.time(), out)
    return out


def forget_models(email: str) -> None:
    with _models_lock:
        _models.pop((email or "").strip().lower(), None)


def pick_model(email: str, token: str) -> str:
    """The efficient default if the seller's account lists it, else the first
    cheap model it does list, else the first model it lists at all. If the list
    cannot be read the default is tried, and the request itself decides."""
    want = preferred_model()
    try:
        catalogue = [m["slug"] for m in models(email, token)]
    except Unavailable:
        return want
    if not catalogue or want in catalogue:
        return want
    for m in FALLBACK_MODELS:
        if m in catalogue:
            return m
    return catalogue[0]


# ------------------------------------------------------------ the request ----
def _retry_after(value) -> int | None:
    """Seconds from a Retry-After header, in either of its two HTTP forms."""
    if not value:
        return None
    v = str(value).strip()
    if v.isdigit():
        return int(v)
    try:
        when = parsedate_to_datetime(v)
        return max(0, int(when.timestamp() - time.time()))
    except (TypeError, ValueError, IndexError):
        return None


def _failure_from_http(r, request_id: str) -> _Failure:
    try:
        body = r.json() or {}
    except ValueError:
        body = {"detail": (r.text or "")[:300]}
    if not isinstance(body, dict):
        body = {}
    err = body.get("error") if isinstance(body.get("error"), dict) else {}
    # Admission can answer {"detail": "..."} before a Responses request even
    # starts. That text is for a person reading logs, not a code to branch on.
    return _Failure(r.status_code, str(err.get("code") or err.get("type") or ""),
                    str(err.get("message") or body.get("detail") or "")[:300],
                    param=err.get("param"), request_id=request_id,
                    retry_after=_retry_after(r.headers.get("retry-after")))


def _text_from_response(resp: dict) -> str:
    out = []
    for item in (resp or {}).get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for part in item.get("content") or []:
            if isinstance(part, dict) and part.get("type") == "output_text":
                out.append(str(part.get("text") or ""))
    return "".join(out)


def _event(payload: str) -> dict | None:
    import json
    try:
        ev = json.loads(payload)
    except ValueError:
        return None
    return ev if isinstance(ev, dict) else None


def _stream(token: str, body: dict) -> str:
    """POST the request and read the event stream through to its end. Returns
    the text only on `response.completed`; everything else raises _Failure."""
    import requests
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json",
               "Accept": "text/event-stream"}
    try:
        r = requests.post(f"{API_BASE}/responses", json=body, headers=headers,
                          stream=True, timeout=(10, 90))
    except Exception as e:  # noqa: BLE001
        raise _Failure(0, "network", type(e).__name__) from e
    with r:
        rid = r.headers.get("x-request-id") or r.headers.get("openai-request-id") or ""
        if r.status_code != 200:
            raise _failure_from_http(r, rid)
        started = time.time()
        parts: list[str] = []
        completed = None
        data_lines: list[str] = []

        def dispatch() -> bool:
            """Handle one complete event. True once the stream is finished."""
            nonlocal completed
            if not data_lines:
                return False
            ev = _event("\n".join(data_lines))
            data_lines.clear()
            if not ev:
                return False
            kind = ev.get("type") or ""
            if kind == "response.output_text.delta":
                parts.append(str(ev.get("delta") or ""))
            elif kind == "response.completed":
                completed = ev.get("response") or {}
                return True
            elif kind == "response.failed":
                err = ((ev.get("response") or {}).get("error")) or {}
                raise _Failure(200, str(err.get("code") or "response_failed"),
                               str(err.get("message") or "")[:300], request_id=rid)
            elif kind == "response.incomplete":
                why = ((ev.get("response") or {}).get("incomplete_details") or {}).get("reason")
                raise _Failure(200, "incomplete", str(why or ""), request_id=rid)
            elif kind == "error":
                err = ev.get("error") if isinstance(ev.get("error"), dict) else ev
                raise _Failure(200, str(err.get("code") or "stream_error"),
                               str(err.get("message") or "")[:300],
                               param=err.get("param"), request_id=rid)
            return False

        def feed(line: str) -> bool:
            """One line of the event stream. True once the stream is finished."""
            if line == "":
                return dispatch()
            if line.startswith(":"):
                return False                    # a comment, or a keep-alive
            field, _, value = line.partition(":")
            if value.startswith(" "):
                value = value[1:]
            if field == "data":
                data_lines.append(value)
            return False

        # Lines are split on the newline BYTE, not with str.splitlines(): that
        # also breaks on U+2028, U+0085 and friends, which can sit unescaped
        # inside a JSON string in the middle of a line of generated text, and
        # would cut the event in half. 0x0A never occurs inside a UTF-8
        # multi-byte character, so this split is always safe.
        try:
            buf, done = b"", False
            for chunk in r.iter_content(chunk_size=None):
                if time.time() - started > STREAM_DEADLINE:
                    raise _Failure(0, "timeout", "the stream ran past its deadline",
                                   request_id=rid)
                if not chunk:
                    continue
                buf += chunk
                while b"\n" in buf and not done:
                    raw, buf = buf.split(b"\n", 1)
                    done = feed(raw.rstrip(b"\r").decode("utf-8", "replace"))
                if done:
                    break
            if not done:
                # The last line may not end in a newline, and the last event may
                # not be followed by the blank line that normally ends one.
                if buf:
                    feed(buf.rstrip(b"\r").decode("utf-8", "replace"))
                dispatch()
        except _Failure:
            raise
        except Exception as e:  # noqa: BLE001 — a dropped connection mid-stream
            raise _Failure(0, "interrupted", type(e).__name__, request_id=rid) from e
        if completed is None:
            raise _Failure(0, "interrupted", "the stream ended before response.completed",
                           request_id=rid)
        text = "".join(parts).strip() or _text_from_response(completed).strip()
        if not text:
            raise _Failure(200, "empty", "the response had no text", request_id=rid)
        return text


def _limit_message() -> str:
    return ("You have reached your ChatGPT usage limit, or the limit you set for "
            "One Tap Manager in ChatGPT. ChatGPT's usage page shows exactly when it "
            "resets, and lets you allow credits if you want to keep going now.")


def _pause(email: str, st: dict, f: _Failure) -> LimitReached:
    now = time.time()
    secs = f.retry_after if (f.retry_after and 0 < f.retry_after <= MAX_PAUSE) else DEFAULT_PAUSE
    st.update(paused_until=now + secs, limit_at=now, retry_after=f.retry_after,
              paused_reason=f.code or "usage_limit")
    _save(email, st)
    log.info("ChatGPT plan limit for a seller (request %s), paused %ss", f.request_id, secs)
    return LimitReached(_limit_message(), retry_after=f.retry_after,
                        paused_until=st["paused_until"], code=f.code)


def _backoff(email: str, st: dict, reason: str) -> None:
    """Temporary trouble: skip the plan for a little while, doubling up to five
    minutes, so a bad patch at OpenAI is not hit on every single caption."""
    n = int(st.get("failures") or 0) + 1
    st.update(failures=n, backoff_until=time.time() + min(300, 15 * (2 ** (n - 1))),
              last_error=reason)
    _save(email, st)


def _succeeded(email: str, st: dict, model: str) -> None:
    changed = False
    for k in ("paused_until", "paused_reason", "retry_after", "backoff_until",
              "failures", "blocked_until", "blocked_reason", "last_error"):
        if k in st:
            st.pop(k)
            changed = True
    if st.get("eligible") is not True:
        st["eligible"] = True
        st["eligible_at"] = time.time()
        changed = True
    # Which model actually wrote, so Account says the truth when the seller's
    # catalogue did not have the preferred one.
    if st.get("model") != model:
        st["model"] = model
        changed = True
    if changed:
        _save(email, st)


def run(email: str, instructions: str, user: str = "", *, image: tuple[bytes, str] | None = None,
        messages: list[dict] | None = None) -> dict:
    """One piece of writing on the seller's ChatGPT plan.

    Returns {"text", "model"}. Raises LimitReached when their usage is spent
    (the caller decides whether a person sees it), Unavailable when the plan
    cannot be used for this request and the caller should fall back."""
    st = _state(email)
    now = time.time()
    if st.get("paused_until", 0) > now:
        raise LimitReached(_limit_message(), retry_after=st.get("retry_after"),
                           paused_until=st["paused_until"], code="paused")
    try:
        token = chatgpt_auth.access_token(email)
    except chatgpt_auth.TokenError as e:
        if e.temporary:
            _backoff(email, st, f"refresh:{e.code}")
        raise Unavailable("token", e.code) from e
    if not token:
        raise Unavailable("not_connected")

    if messages:
        items = [{"role": m["role"], "content": str(m.get("content") or "")}
                 for m in messages if m.get("role") in ("user", "assistant")]
    elif image:
        data, ctype = image
        url = f"data:{ctype or 'image/jpeg'};base64,{base64.b64encode(data).decode()}"
        items = [{"role": "user", "content": [
            {"type": "input_text", "text": user or ""},
            {"type": "input_image", "image_url": url, "detail": "auto"}]}]
    else:
        items = [{"role": "user", "content": user or ""}]
    if not items:
        raise Unavailable("empty_input")

    model = pick_model(email, token)
    body = {"model": model, "input": items, "store": False, "stream": True}
    if (instructions or "").strip():
        body["instructions"] = instructions
    effort = _effort()
    if effort and effort not in ("default", "off"):
        body["reasoning"] = {"effort": effort}

    refreshed = False
    for _ in range(3):
        try:
            text = _stream(token, body)
        except _Failure as f:
            code = f.code
            # Only OpenAI's own usage-limit code is a usage limit. Any other 429
            # is ordinary throttling and is handled as temporary trouble below,
            # because telling a seller their plan ran out when it did not would
            # send them to buy credits they do not need.
            if code in LIMIT_CODES:
                raise _pause(email, st, f)
            if code == "subscription_sharing_user_not_eligible":
                st.update(eligible=False, eligible_at=time.time())
                _save(email, st)
                raise Unavailable("not_eligible")
            if f.status == 401 or code == "subscription_sharing_invalid_user":
                if not refreshed:
                    refreshed = True
                    try:
                        token = chatgpt_auth.access_token(email, force_refresh=True) or ""
                    except chatgpt_auth.TokenError as e:
                        raise Unavailable("token", e.code) from e
                    if token:
                        continue
                # Not proof the connection is dead (OpenAI asks for a confirmed
                # revocation or a refused refresh before asking the seller to
                # sign in again), so pause the plan for a while, keep the
                # tokens, and note the request id for whoever looks.
                st.update(blocked_until=time.time() + 600, blocked_reason="rejected")
                _save(email, st)
                log.warning("ChatGPT plan request refused (401 %s, request %s)",
                            code, f.request_id)
                raise Unavailable("rejected", code)
            if f.status == 400 and str(f.param or "").startswith("reasoning") \
                    and "reasoning" in body:
                # The model in the seller's catalogue does not take a reasoning
                # setting. OpenAI: remove what error.param names and send a
                # DIFFERENT body, never the same one again.
                body.pop("reasoning")
                continue
            if code in TEMPORARY_CODES or f.status in (0, 429, 500, 502, 503, 504):
                _backoff(email, st, code or f"http_{f.status}")
                raise Unavailable("temporary", code or str(f.status))
            if f.status == 403:
                # Region, workspace policy or permission: it will not fix itself
                # in the next minute, so hold off for an hour and say why.
                st.update(blocked_until=time.time() + 3600, blocked_reason=code or "forbidden")
                _save(email, st)
                log.warning("ChatGPT plan request forbidden (%s, request %s): %s",
                            code, f.request_id, f.message)
                raise Unavailable("forbidden", code)
            if f.status == 400 and f.param == "model":
                forget_models(email)
            log.warning("ChatGPT plan request failed (%s %s, request %s): %s",
                        f.status, code, f.request_id, f.message)
            raise Unavailable("failed", code or str(f.status))
        _succeeded(email, st, model)
        return {"text": text, "model": model}
    raise Unavailable("failed", "retries")
