"""
Email intake — the "connect your POS" that actually removes the upload step.

WHY THIS EXISTS: PetPooja's own dashboard already lets an owner "automate
report alerts and get updates on your email" (their words, from their own
reports-and-analytics page). Toast, Square, Posist, and basically every POS
have an equivalent scheduled-report-to-email feature — restaurant owners set
these up for their accountant all the time. That means an owner doesn't have
to learn a new habit at all: they add ONE more email address (ours) to a
report they're already scheduling, once, and never open a website again.

HOW IT WORKS (self-serve, no partner deal with anyone):
  1. Founder signs up for a free inbound-email service (SendGrid Inbound Parse
     or Mailgun Routes both have free tiers). This is a founder-side account,
     like signing up for any SaaS — not a negotiation with PetPooja/Toast.
  2. Founder points ONE subdomain's MX record at that service (e.g.
     reports.cafex.app -> mx.sendgrid.net) and tells the service to POST
     incoming mail to /api/intake/email on this server. One-time DNS change,
     not per-café.
  3. Each café owner is given a single email address to CC or set as their
     POS's scheduled-report recipient: reports@reports.cafex.app. From then
     on their existing daily/weekly report just arrives here automatically.

WHAT'S REAL vs WHAT NEEDS SETUP:
  - Parsing, POS-format detection, analytics, PDF generation below: fully
    real and tested end-to-end with a synthetic inbound-parse payload.
  - Actually receiving mail requires the founder's own inbound-email service
    account + one DNS record (a business decision, ~10 minutes, free tier).
    Sending the finished report back by email requires SMTP credentials
    (SENDGRID_API_KEY or SMTP_* env vars) — until those are set, the endpoint
    still processes everything and returns a magic link, it just can't push
    an email itself. This mirrors how we handled PetPooja/Toast earlier:
    the moving parts are honestly labelled, not faked.
"""
import io
import os
import secrets
import time

import pandas as pd

from backend.core import analytics, i18n, mapper, pos_formats, report_pdf

# very small in-memory store: token -> {pdf_bytes, created, sender, meta}
# A real deployment would use the same persistent disk as purchases.csv;
# in-memory is enough to prove the pipeline and survives one process lifetime.
_REPORTS: dict[str, dict] = {}
_TOKEN_TTL_SECONDS = 14 * 24 * 3600  # magic links live 14 days


class IntakeError(ValueError):
    """Message safe to show/log — bad attachment, unreadable file, etc."""


def _pick_best_attachment(attachments: list[tuple[str, bytes]]) -> tuple[str, pd.DataFrame]:
    """A scheduled POS report email may attach a CSV/XLSX (sometimes alongside
    a logo image or a PDF summary) — pick the largest tabular attachment."""
    candidates = []
    for filename, content in attachments:
        ext = os.path.splitext(filename)[1].lower()
        try:
            if ext == ".csv":
                df = pd.read_csv(io.BytesIO(content))
            elif ext in (".xlsx", ".xls"):
                df = pd.read_excel(io.BytesIO(content))
            elif ext == ".tsv":
                df = pd.read_csv(io.BytesIO(content), sep="\t")
            else:
                continue
        except Exception:
            continue
        if len(df.columns) >= 2:
            candidates.append((filename, df))
    if not candidates:
        raise IntakeError(
            "No readable CSV/Excel attachment found in that email. "
            "Make sure your POS's scheduled report is attached as a file, not just in the email body."
        )
    return max(candidates, key=lambda t: len(t[1]))


def process_inbound_email(sender: str, attachments: list[tuple[str, bytes]],
                          lang: str = "en") -> dict:
    """Main entry point: raw email attachments in -> stored PDF + magic link out.

    Returns {"token", "pos_format", "rows", "revenue", "warnings"}.
    """
    filename, df = _pick_best_attachment(attachments)

    fmt = pos_formats.detect_format(df)
    warnings = []
    if fmt and fmt["mapping"].get("date") and fmt["mapping"].get("amount"):
        mapping = fmt["mapping"]
        pos_label = fmt["label"]
        if fmt["note"]:
            warnings.append(fmt["note"])
    else:
        mapping = mapper.suggest_mapping(df)
        pos_label = None
        warnings.append(
            "Didn't recognise this as a known POS export — used best-guess column "
            "mapping instead. Numbers may need a manual check the first time."
        )
        if not (mapping.get("date") and mapping.get("amount")):
            raise IntakeError(
                f"Couldn't find date/amount columns in '{filename}'. "
                "This may not be a sales report — forward the itemised sales export instead."
            )

    txns, diag = mapper.build_transactions(df, mapping)
    if txns.empty:
        raise IntakeError(f"'{filename}' had no usable rows after cleaning (check date/amount format).")
    if "customer_id" not in txns.columns or txns["customer_id"].isna().all():
        warnings.append("No customer column found — win-back and RFM features need a customer ID or phone column.")

    data = analytics.sales_analytics(txns)
    rendered = i18n.render_all(data["insights"], lang)
    pdf_bytes = report_pdf.build_sales_report(data, rendered, cafe_label=sender or "Your Café")

    token = secrets.token_urlsafe(18)
    _REPORTS[token] = {
        "pdf": pdf_bytes, "created": time.time(), "sender": sender,
        "pos_format": pos_label, "rows": int(len(txns)),
        "revenue": float(data["kpis"]["revenue"]), "filename": filename,
    }
    _gc_expired()
    return {
        "token": token, "pos_format": pos_label, "rows": int(len(txns)),
        "revenue": float(data["kpis"]["revenue"]), "warnings": warnings,
    }


def get_report(token: str) -> bytes | None:
    entry = _REPORTS.get(token)
    if not entry or (time.time() - entry["created"]) > _TOKEN_TTL_SECONDS:
        return None
    return entry["pdf"]


def _gc_expired() -> None:
    stale = [t for t, e in _REPORTS.items() if time.time() - e["created"] > _TOKEN_TTL_SECONDS]
    for t in stale:
        _REPORTS.pop(t, None)


def send_report_email(to_addr: str, token: str, report_url: str) -> bool:
    """Email the magic link back to whoever's report we just processed.
    Returns False (without raising) when no email-sending credentials are
    configured — the report is still safely stored and reachable via the
    link, so a missing SMTP key degrades gracefully rather than breaking
    the whole pipeline."""
    api_key = os.getenv("SENDGRID_API_KEY")
    if not api_key or not to_addr:
        return False
    try:
        import requests
        requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "personalizations": [{"to": [{"email": to_addr}]}],
                "from": {"email": os.getenv("SENDGRID_FROM", "reports@cafex.app"), "name": "Cafe_X"},
                "subject": "Your Cafe_X sales report is ready",
                "content": [{"type": "text/plain",
                            "value": f"Your latest report is ready: {report_url}\n\nThis link works for 14 days."}],
            }, timeout=15,
        )
        return True
    except Exception:
        return False
