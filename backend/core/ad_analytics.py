"""
Ad-analytics connectors — pass 1: the wiring is real (a seller connects each
platform per account, credentials are stored, status is visible), but the
metrics endpoint currently returns realistic DEMO figures rather than live
API pulls. Free platforms will move to real pulls in the next iteration;
paid ones stay demo.

Why demo now: Google Ads, Meta Ads and Instagram Insights all require an
OAuth app (developer.google.com / Meta Business App) with review, plus
per-account refresh tokens — a multi-step external setup that has to be
done before we can pull live data. The UI and adapter layer are structured
so swapping demo -> live is one function per connector.
"""
from __future__ import annotations

import hashlib
from datetime import date, timedelta
from typing import Any

from backend.core import user_store

_KEY = "ads_connections"

CONNECTORS = [
    {"id": "google_ads",         "label": "Google Ads",         "icon": "🇬", "tier": "free",
     "help": "Search + Performance Max campaign metrics.",
     "needs": ["customer_id", "developer_token", "refresh_token"]},
    {"id": "meta_ads",           "label": "Meta Ads (Facebook + Instagram)", "icon": "Ⓜ️", "tier": "free",
     "help": "Facebook / Instagram ad campaign metrics via the Marketing API.",
     "needs": ["ad_account_id", "access_token"]},
    {"id": "instagram_insights", "label": "Instagram Insights", "icon": "📸", "tier": "free",
     "help": "Organic reach, impressions and top posts. Uses your connected Instagram account.",
     "needs": []},
    {"id": "google_analytics",   "label": "Google Analytics 4", "icon": "📈", "tier": "free",
     "help": "Site sessions, conversion rate and top sources.",
     "needs": ["property_id", "refresh_token"]},
    {"id": "shopify_ads",        "label": "Shopify Marketing",  "icon": "🛒", "tier": "paid",
     "help": "Shopify Ads + marketing automation metrics.",
     "needs": ["shop_domain", "admin_api_token"]},
    {"id": "amazon_ads",         "label": "Amazon Ads",         "icon": "📦", "tier": "paid",
     "help": "Sponsored Products / Brands metrics.",
     "needs": ["profile_id", "refresh_token"]},
]


def list_connectors(email: str | None = None) -> list[dict]:
    conns = user_store.get_key(email, _KEY, {}) if email else {}
    out = []
    for c in CONNECTORS:
        info = {**c}
        stored = (conns or {}).get(c["id"]) or {}
        info["connected"] = bool(stored)
        info["connected_at"] = stored.get("connected_at")
        info["mode"] = "demo"  # will flip to "live" when real pulls are wired
        out.append(info)
    return out


def save_connection(email: str, connector_id: str, credentials: dict) -> dict:
    if not any(c["id"] == connector_id for c in CONNECTORS):
        raise ValueError(f"Unknown connector: {connector_id}")
    conns = user_store.get_key(email, _KEY, {}) or {}
    conns[connector_id] = {"credentials": credentials or {},
                           "connected_at": _now_iso()}
    user_store.set_key(email, _KEY, conns)
    return {"ok": True, "connector": connector_id, "connected_at": conns[connector_id]["connected_at"]}


def disconnect(email: str, connector_id: str) -> None:
    conns = user_store.get_key(email, _KEY, {}) or {}
    conns.pop(connector_id, None)
    user_store.set_key(email, _KEY, conns)


def get_metrics(email: str, connector_id: str, days: int = 30) -> dict:
    """Currently returns deterministic demo metrics seeded from (email, connector,
    days) so the same seller sees a stable dashboard between page loads."""
    if not any(c["id"] == connector_id for c in CONNECTORS):
        raise ValueError(f"Unknown connector: {connector_id}")
    seed = int(hashlib.md5(f"{email}|{connector_id}|{days}".encode()).hexdigest()[:8], 16)
    rng = _Rng(seed)
    today = date.today()
    days = max(7, min(90, int(days)))
    dates = [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]

    spend = [round(600 + rng.next() * 900 + i * 5, 0) for i in range(days)]
    impressions = [int(s * (55 + rng.next() * 40)) for s in spend]
    clicks = [int(im * (0.012 + rng.next() * 0.025)) for im in impressions]
    conversions = [int(c * (0.02 + rng.next() * 0.05)) for c in clicks]
    # revenue per conversion: seller AOV ~ ₹1400-3200 → ROAS lands in the
    # believable 2-6x range for the totals below (not the eye-popping 40x+
    # earlier multipliers were producing).
    revenue = [round(cv * (1400 + rng.next() * 1800), 0) for cv in conversions]

    totals = {
        "spend": int(sum(spend)),
        "impressions": int(sum(impressions)),
        "clicks": int(sum(clicks)),
        "conversions": int(sum(conversions)),
        "revenue": int(sum(revenue)),
    }
    totals["ctr_pct"] = round(totals["clicks"] / max(totals["impressions"], 1) * 100, 2)
    totals["cvr_pct"] = round(totals["conversions"] / max(totals["clicks"], 1) * 100, 2)
    totals["cpc"] = round(totals["spend"] / max(totals["clicks"], 1), 2)
    totals["roas"] = round(totals["revenue"] / max(totals["spend"], 1), 2)

    campaigns = _demo_campaigns(connector_id, rng, totals)

    return {
        "connector": connector_id,
        "mode": "demo",
        "note": ("Demo data — the seller's real API credentials aren't wired to live pulls "
                 "in this pass. The UI, structure and per-account credential storage are real."),
        "range": {"from": dates[0], "to": dates[-1], "days": days},
        "totals": totals,
        "daily": {"dates": dates, "spend": spend, "impressions": impressions,
                  "clicks": clicks, "conversions": conversions, "revenue": revenue},
        "campaigns": campaigns,
    }


def _demo_campaigns(connector_id: str, rng, totals) -> list[dict]:
    names = {
        "google_ads": ["Brand — Search", "Non-brand — Search", "PMax — Bestsellers", "Shopping — All"],
        "meta_ads":   ["IG Reels — New Drop", "FB Feed — Retargeting", "IG Story — Signature Piece", "Advantage+ Shopping"],
        "instagram_insights": ["Grid posts", "Reels", "Stories", "Explore surfaced"],
        "google_analytics":   ["Organic search", "Direct", "Instagram referral", "Email"],
        "shopify_ads":        ["Shopify Email — New Drop", "Shopify Ads — Trending"],
        "amazon_ads":         ["Sponsored Products — Rings", "Sponsored Brands — Chains", "Sponsored Display — Retargeting"],
    }.get(connector_id, ["Campaign A", "Campaign B", "Campaign C"])
    out = []
    for n in names:
        share = 0.15 + rng.next() * 0.35
        sp = int(totals["spend"] * share)
        cl = int(totals["clicks"] * (share + rng.next() * 0.05))
        cv = int(totals["conversions"] * (share + rng.next() * 0.05))
        rev = int(totals["revenue"] * (share + rng.next() * 0.05))
        out.append({"name": n, "spend": sp, "clicks": cl, "conversions": cv,
                    "revenue": rev, "roas": round(rev / max(sp, 1), 2)})
    return out


class _Rng:
    """Tiny deterministic LCG so we can seed off (email, connector) without pulling in random."""
    def __init__(self, seed: int):
        self.s = seed or 1
    def next(self) -> float:
        self.s = (self.s * 1103515245 + 12345) & 0x7FFFFFFF
        return (self.s % 100000) / 100000.0


def _now_iso() -> str:
    import pandas as pd
    return pd.Timestamp.now().isoformat(timespec="seconds")
