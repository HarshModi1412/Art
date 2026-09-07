"""
Win-back proof loop — did the campaign actually work?

Today the app generates a list of customers who have gone quiet, hands over an
Excel file, and never learns what happened. That is the single biggest hole in
the value story: at renewal time the seller has no number to weigh against the
subscription, so the subscription looks like a cost.

So: one tick. The seller marks a campaign SENT, which snapshots exactly which
customer ids were targeted and on what date. From then on every refresh of the
sales data answers a question nobody else can answer for them —

    of the 84 customers you contacted on 3 August, 19 came back and spent
    ₹42,300 in the 30 days after.

Attribution is deliberately simple and stated plainly on screen: a customer
counts as recovered if they bought at all in the window after the campaign,
having been silent before it. It is not a controlled experiment and the UI must
never call it one. It is, however, the honest number, computed from the
seller's own transactions rather than from anything we ask them to believe.
"""
from __future__ import annotations

import secrets

import pandas as pd

CAMPAIGNS_KEY = "winback_campaigns"
DEFAULT_WINDOW_DAYS = 30


def _now_iso() -> str:
    return pd.Timestamp.now().isoformat(timespec="seconds")


def _load(email: str) -> list[dict]:
    from backend.core import user_store
    rows = user_store.get_key(email, CAMPAIGNS_KEY, []) or []
    return rows if isinstance(rows, list) else []


def _save(email: str, rows: list[dict]) -> None:
    from backend.core import user_store
    user_store.set_key(email, CAMPAIGNS_KEY, rows[-60:])


def mark_sent(email: str, customers: list[dict], channel: str = "whatsapp",
              note: str = "") -> dict:
    """Record that this campaign went out. `customers` is what the generator
    produced — we keep only the ids, the names and what they were worth."""
    targets = []
    for c in (customers or []):
        cid = str(c.get("customer_id") or c.get("id") or "").strip()
        if not cid:
            continue
        targets.append({
            "customer_id": cid,
            "name": str(c.get("customer_name") or c.get("name") or "").strip()[:80],
            "prior_value": float(c.get("monetary") or c.get("value") or 0),
        })
    if not targets:
        raise ValueError("Nothing to mark — generate the campaign first.")

    row = {
        "id": secrets.token_hex(6),
        "sent_at": _now_iso(),
        "channel": (channel or "whatsapp").strip()[:20],
        "note": str(note or "").strip()[:160],
        "window_days": DEFAULT_WINDOW_DAYS,
        "targets": targets,
        "n_targets": len(targets),
        "prior_value": round(sum(t["prior_value"] for t in targets), 2),
    }
    rows = _load(email)
    rows.append(row)
    _save(email, rows)
    return row


def unmark(email: str, campaign_id: str) -> list[dict]:
    """Undo — a mis-click on 'sent' must not permanently poison the number."""
    rows = [r for r in _load(email) if r.get("id") != campaign_id]
    _save(email, rows)
    return rows


def _measure(email: str, campaign: dict, txns) -> dict:
    sent = pd.to_datetime(campaign.get("sent_at"), errors="coerce")
    window = int(campaign.get("window_days") or DEFAULT_WINDOW_DAYS)
    out = {**{k: v for k, v in campaign.items() if k != "targets"},
           "returned": 0, "recovered": 0.0, "measurable": False,
           "days_elapsed": 0, "window_days": window}
    if txns is None or not len(txns) or pd.isna(sent):
        return out

    df = txns.copy()
    if "date" not in df.columns or "customer_id" not in df.columns:
        return out
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    if df.empty:
        return out

    end = sent + pd.Timedelta(days=window)
    latest = df["date"].max()
    out["days_elapsed"] = max(0, int((min(latest, end) - sent).days))
    out["measurable"] = latest > sent

    ids = {t["customer_id"] for t in (campaign.get("targets") or [])}
    after = df[(df["date"] > sent) & (df["date"] <= end)]
    after = after[after["customer_id"].astype(str).isin(ids)]
    if after.empty:
        return out

    amount_col = "amount" if "amount" in after.columns else None
    out["returned"] = int(after["customer_id"].astype(str).nunique())
    out["recovered"] = round(float(after[amount_col].sum()), 2) if amount_col else 0.0
    return out


def summary(email: str) -> dict:
    """Every campaign with its result, plus the one line worth putting on the
    home screen and in the renewal email."""
    from backend.core import smart

    campaigns = _load(email)
    if not campaigns:
        return {"campaigns": [], "totals": None,
                "headline": "", "window_days": DEFAULT_WINDOW_DAYS}

    txns = smart.load_sales(email)
    measured = [_measure(email, c, txns) for c in campaigns]
    measured.sort(key=lambda r: r.get("sent_at") or "", reverse=True)

    contacted = sum(r["n_targets"] for r in measured)
    returned = sum(r["returned"] for r in measured)
    recovered = round(sum(r["recovered"] for r in measured), 2)
    ready = [r for r in measured if r["measurable"]]

    headline = ""
    if recovered > 0:
        first = min((r.get("sent_at") or "" for r in measured if r.get("sent_at")), default="")
        since = pd.to_datetime(first, errors="coerce")
        when = f" since {since:%B}" if not pd.isna(since) else ""
        headline = (f"₹{recovered:,.0f} recovered from win-backs{when} — "
                    f"{returned} of {contacted} customers you contacted came back.")
    elif ready:
        headline = (f"{contacted} customers contacted. None have come back yet — "
                    f"it is still early for {len(measured)} campaign"
                    f"{'s' if len(measured) != 1 else ''}.")
    else:
        headline = (f"{contacted} customers contacted. Upload fresher sales data "
                    f"and this will tell you how many came back.")

    return {
        "campaigns": measured,
        "totals": {"campaigns": len(measured), "contacted": contacted,
                   "returned": returned, "recovered": recovered,
                   "return_rate": round(returned / contacted * 100, 1) if contacted else 0.0},
        "headline": headline,
        "window_days": DEFAULT_WINDOW_DAYS,
        "method": "A customer counts as recovered if they bought within "
                  f"{DEFAULT_WINDOW_DAYS} days of the campaign going out. "
                  "It is not a controlled test — it is what your own sales data says.",
    }
