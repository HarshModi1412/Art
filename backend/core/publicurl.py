"""What this app's public address actually is.

THE BUG THIS FIXES
------------------
`_public_base_url` was `f"{request.url.scheme}://{request.url.netloc}"`. On
Render, TLS is terminated at the edge and the request reaches uvicorn over plain
HTTP, so `request.url.scheme` is "http" for every single request, on a site that
is only ever served over https. uvicorn is started without `--proxy-headers`, so
it never looked at `X-Forwarded-Proto` either.

Three things broke because of that, and only one of them was visible:

  * Every canonical tag and every og:url on a seller's shop pointed at
    `http://...` while the page itself was served over `https://...`. That is a
    page telling Google its own canonical version is a different URL from the one
    being crawled, which is one of the ordinary reasons a site does not appear in
    search. Nothing logs it and nothing looks broken.
  * Meta will not fetch media over http. `publisher.remember_base_url` stored the
    http form, so the absolute image URL handed to Instagram was one the Graph
    API refuses.
  * A password-reset link mailed to a seller pointed at http, which most browsers
    now upgrade but some mail clients flag.

WHAT THIS DOES INSTEAD, in order:

  1. `PUBLIC_BASE_URL`, if the deployment sets it. This is the answer once a
     custom domain is connected: one place to say "this app lives at
     https://onetapmanager.in", and every absolute URL in the app follows,
     including the ones in emails and the ones sent to Meta.
  2. The forwarded headers a proxy sets (`X-Forwarded-Proto`, `X-Forwarded-Host`),
     which is what Render, Cloudflare and every other edge in front of this app
     actually send.
  3. The request's own scheme and host, with one correction: anything that is not
     localhost is assumed to be https, because it is. A public host on plain http
     in 2026 is a misconfiguration, not a case to support.

A seller's own custom domain is deliberately NOT handled here. Their shop is
rendered from whatever host the request arrived on, so their canonical is their
domain, which is correct: that page really does live there.
"""
from __future__ import annotations

import os

_LOCAL = ("localhost", "127.0.0.1", "0.0.0.0", "::1", "testserver")


def configured() -> str:
    """The deployment's own answer, if it has one. Empty when unset."""
    raw = (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if not raw:
        return ""
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    return raw


def is_local(host: str) -> bool:
    return (host or "").split(":")[0].lower() in _LOCAL


def scheme_for(host: str, forwarded_proto: str = "") -> str:
    """https for anything public. A PROXY's answer wins when it gives one.

    Note what does not count: the request's own scheme. Behind a TLS terminator
    that is always "http", which is exactly the value that caused this whole
    problem, so it is never consulted for a public host. Only an actual
    X-Forwarded-Proto header, set by an actual proxy, can say otherwise.
    """
    fp = (forwarded_proto or "").split(",")[0].strip().lower()
    if fp in ("http", "https"):
        return fp
    return "http" if is_local(host) else "https"


def base_url(host: str, scheme: str = "", headers=None) -> str:
    """The absolute address to put in a canonical tag, an email or a Meta call.

    `headers` is anything with a case-insensitive .get, which is what both
    Starlette's Headers and a plain dict of lowercased keys provide.
    """
    fixed = configured()
    if fixed:
        return fixed
    get = (headers.get if headers is not None else (lambda *_: ""))
    fwd_host = (get("x-forwarded-host") or "").split(",")[0].strip()
    host = fwd_host or host or ""
    # The request's own scheme is used ONLY for a local host, where it is real.
    # For a public host it is the untrustworthy value this module exists to
    # ignore, so the proxy header is the only thing that can override https.
    proto = get("x-forwarded-proto") or (scheme if is_local(host) else "")
    return f"{scheme_for(host, proto)}://{host}"


def from_request(request) -> str:
    """The Starlette flavour of base_url()."""
    return base_url(request.url.netloc, request.url.scheme, request.headers)


def should_redirect_to_https(host: str, headers=None) -> bool:
    """Whether this request arrived over plain http and should be bounced.

    Deliberately narrow. It returns True only when a proxy has SAID the original
    request was http. It never guesses from the request's own scheme, because
    behind a TLS terminator every request looks like http from in here, and a
    redirect on that basis is an infinite loop that takes the whole site down.
    That failure mode is common enough to be worth the narrower rule.
    """
    if is_local(host):
        return False
    if configured().startswith("http://"):
        return False            # a deployment that has deliberately said http
    get = (headers.get if headers is not None else (lambda *_: ""))
    proto = (get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    return proto == "http"
