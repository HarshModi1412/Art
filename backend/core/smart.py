"""
Smart CafeX — the Odoo-style workspace layer.

This module doesn't re-implement any analytics. It sits on top of the engines
that already exist (analytics, menu_engineering, positioning, complaints,
templates) and adds the three things the Smart CafeX UI needs that the classic
app didn't have:

  1. Per-account data that survives logout  — the Sales and Review files an
     owner uploads are pickled to their account (via user_store) and reused
     until they click "Update". On load we hydrate the browser session from
     them so every existing analytics endpoint works unchanged.

  2. Actionable insights for the Approval panel — a small, ranked set of
     "do this" cards drawn from the owner's own data. Each can be Approved
     (which "executes" it — today that means producing the ready-to-use Excel:
     the win-back list + messages, the menu combos, the reputation/complaint
     action plan), Disapproved (hidden), or opened for details.

  3. A per-account task list.

Decisions and tasks live in the user's JSON state; the two dataframes live as
pickles beside it.
"""
from __future__ import annotations

import hashlib
import io

import pandas as pd

from backend.core import (analytics, complaints, content_gen, positioning, product_config,
                          templates, user_store)

SALES_KEY = "smart_sales_txns"
REVIEW_KEY = "smart_review_df"


# ---------------------------------------------------------
# Product type (what the seller sells) — drives keyword tracking everywhere
# ---------------------------------------------------------
def get_product_type(email: str) -> str:
    return product_config.normalize(user_store.get_key(email, "product_type", None))


def set_product_type(email: str, product_type: str) -> str:
    pt = product_config.normalize(product_type)
    user_store.set_key(email, "product_type", pt)
    return pt


# ---------------------------------------------------------
# Data persistence + session hydration
# ---------------------------------------------------------
def save_sales(email: str, txns: pd.DataFrame, meta: dict, mode: str = "replace") -> None:
    """Persist the account's Sales data.

    mode="replace" (default) overwrites; mode="append" adds the new rows on top
    of whatever is already saved (used by the "Add records" flow). Both frames
    are canonical Transactions frames from mapper.build_transactions, so their
    columns line up for a straight concat.
    """
    if mode == "append":
        existing = load_sales(email)
        if existing is not None and len(existing):
            txns = pd.concat([existing, txns], ignore_index=True)
    user_store.save_df(email, SALES_KEY, txns)
    st = user_store.get_key(email, "smart_data", {}) or {}
    st["sales"] = {**meta, "rows": int(len(txns)),
                   "updated_at": pd.Timestamp.now().isoformat(timespec="seconds")}
    user_store.set_key(email, "smart_data", st)


def save_review(email: str, df: pd.DataFrame, meta: dict, mode: str = "replace") -> None:
    """Persist the account's Review data.

    mode="replace" (default) overwrites; mode="append" stacks the new rows onto
    the saved reviews (the "Add records" flow). Columns are canonicalised to
    Review/Rating/Date before saving, so the concat aligns.
    """
    if mode == "append":
        existing = load_review(email)
        if existing is not None and len(existing):
            df = pd.concat([existing, df], ignore_index=True)
    user_store.save_df(email, REVIEW_KEY, df)
    st = user_store.get_key(email, "smart_data", {}) or {}
    st["review"] = {**meta, "rows": int(len(df)),
                    "updated_at": pd.Timestamp.now().isoformat(timespec="seconds")}
    user_store.set_key(email, "smart_data", st)


def load_sales(email: str):
    return user_store.load_df(email, SALES_KEY)


def load_review(email: str):
    return user_store.load_df(email, REVIEW_KEY)


def clear(email: str, kind: str) -> None:
    st = user_store.get_key(email, "smart_data", {}) or {}
    if kind == "sales":
        user_store.delete_df(email, SALES_KEY); st.pop("sales", None)
    elif kind == "review":
        user_store.delete_df(email, REVIEW_KEY); st.pop("review", None)
    user_store.set_key(email, "smart_data", st)


def data_status(email: str) -> dict:
    st = user_store.get_key(email, "smart_data", {}) or {}
    return {
        "sales": {"ready": user_store.has_df(email, SALES_KEY), **(st.get("sales") or {})},
        "review": {"ready": user_store.has_df(email, REVIEW_KEY), **(st.get("review") or {})},
    }


def hydrate_session(email: str, sess) -> dict:
    """Load the account's saved Sales data into the live browser session so the
    existing /api/analytics, /api/subcategory, /api/rfm endpoints work on it."""
    txns = load_sales(email)
    if txns is not None and len(txns):
        try:
            from backend.core import products as _products
            txns = _products.canonicalize_df(email, txns)
        except Exception:
            pass
        sess.txns_df = txns
        sess.mapped_file_id = "smart_sales"
    return data_status(email)


# ---------------------------------------------------------
# Actionable insights for the Approval panel
# ---------------------------------------------------------
def _content_suggestion_insights(email: str) -> list[dict]:
    """One 'suggested post' card in the Approval panel, pulled from the
    ranked topic bank + generated on demand when the user opens details.
    Stored in the account so the same suggestion sticks between reloads
    (a new one appears once the seller approves/dismisses the current one)."""
    stored = user_store.get_key(email, "content_current_suggestion", None)
    if not stored or stored.get("_gone"):
        pt = get_product_type(email)
        topic = content_gen.suggest_topic(pt)
        stored = {
            "id": f"content_{__import__('secrets').token_hex(4)}",
            "topic": topic,
            "product_type": pt,
            "platform": "instagram",
            "generated": False,   # only text/image once the seller opens details
            "created_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        }
        user_store.set_key(email, "content_current_suggestion", stored)
    return [{
        "id": stored["id"], "module": "content", "page": "content", "icon": "✨",
        "title": f"Suggested post: {stored['topic']}",
        "detail": ("An Instagram post idea based on what's trending for your product type. "
                   "Open Details to see the caption, hashtags and image, edit anything, "
                   "then Post now or schedule."),
        "action_label": "Approve → post to Instagram", "has_download": False,
        "content": True,
    }]


def clear_content_suggestion(email: str) -> None:
    """Marks the current suggestion as gone so the next status call regenerates one."""
    user_store.set_key(email, "content_current_suggestion", None)


def get_or_generate_content(email: str, insight_id: str, force: bool = False) -> dict | None:
    """Return the FULL suggestion (caption, hashtags, image) for the given
    Approval-panel content id, generating it on first open (or when force=True)."""
    from backend.core import content_gen as _cg
    stored = user_store.get_key(email, "content_current_suggestion", None) or {}
    if stored.get("id") != insight_id:
        return None
    if force or not stored.get("generated"):
        full = _cg.generate_suggestion(email, product_type=stored.get("product_type"),
                                       topic=stored.get("topic"),
                                       platform=stored.get("platform", "instagram"))
        # keep the original id (the one in the panel) so decisions match up
        full["id"] = stored["id"]
        stored.update(full)
        stored["generated"] = True
        user_store.set_key(email, "content_current_suggestion", stored)
    return stored


def save_content_suggestion(email: str, insight_id: str, edits: dict) -> dict | None:
    stored = user_store.get_key(email, "content_current_suggestion", None) or {}
    if stored.get("id") != insight_id:
        return None
    for k in ("caption", "hashtags", "description", "image_url", "platform", "topic"):
        if k in edits and edits[k] is not None:
            stored[k] = edits[k]
    user_store.set_key(email, "content_current_suggestion", stored)
    return stored


def build_insights(email: str, include_decided: bool = False) -> list[dict]:
    """Ranked 'do this' cards from the owner's own data.

    By default the Approval panel only shows *pending* items — approved or
    dismissed ones move to History and drop out of the active list, so the
    owner isn't looking at cards they've already answered. Pass
    include_decided=True to get every card the data currently produces
    (used by build_history to know which historic items are still valid for
    re-download).
    """
    decisions = user_store.get_key(email, "smart_decisions", {}) or {}
    out: list[dict] = []
    txns = load_sales(email)
    review = load_review(email)

    if txns is not None and len(txns):
        # 1) win-back campaign
        at_risk = analytics.at_risk_customers(txns)
        if at_risk:
            out.append({
                "id": "winback", "module": "sales", "page": "winback", "icon": "💌",
                "title": f"Win back {len(at_risk)} at-risk customers",
                "detail": (f"{len(at_risk)} regulars haven't visited in a while. Approve to generate a "
                           "ready-to-send message + personalised coupon for each, exported to Excel."),
                "action_label": "Approve → download campaign", "count": len(at_risk), "has_download": True,
            })
    if review is not None and len(review):
        pt = get_product_type(email)
        # 2) reputation / positioning
        try:
            pos = positioning.analyze_reviews(review, "en", product_type=pt)
        except Exception:
            pos = {"available": False}
        if pos.get("available") and pos.get("insights"):
            out.append({
                "id": "reputation", "module": "review", "page": "positioning", "icon": "📍",
                "title": "Act on your brand positioning",
                "detail": (f"From {pos.get('n_reviews', 0)} reviews we found {len(pos['insights'])} positioning "
                           "moves for your brand. Approve to export the prioritised action plan."),
                "action_label": "Approve → download action plan", "count": len(pos["insights"]), "has_download": True,
            })
        # 3) complaints focus
        try:
            comp = complaints.analyze_complaints(review, product_type=pt)
        except Exception:
            comp = {"actions": []}
        focus = (comp.get("focus") or {}).get("focus_now") or []
        if focus:
            out.append({
                "id": "complaints", "module": "review", "page": "complaints", "icon": "😤",
                "title": f"Fix your top {len(focus)} complaint themes",
                "detail": ("These are the complaint themes hurting you most right now. Approve to export the "
                           "fix-first action plan."),
                "action_label": "Approve → download fix plan", "count": len(focus), "has_download": True,
            })

    # 4) supply — items at/below their reorder point
    from backend.core import supply as _supply
    reorder_card = _supply.build_reorder_insight(email)
    if reorder_card:
        out.append(reorder_card)

    # 5) one 'suggested post' — a content-creator idea in the same panel
    if not include_decided:
        out.extend(_content_suggestion_insights(email))

    # attach each card's decision; hide decided ones from the active panel
    # unless the caller explicitly asked for the full list.
    visible = []
    for card in out:
        if card["id"] == "reorder":
            card["decision"] = _supply.reorder_decision_state(email)
            card["decided_at"] = None
        else:
            d = decisions.get(card["id"])
            card["decision"] = (d.get("state") if isinstance(d, dict) else d) or "pending"
            card["decided_at"] = d.get("at") if isinstance(d, dict) else None
        if include_decided:
            visible.append(card)
        elif card["decision"] == "pending":
            visible.append(card)
    return visible


def build_history(email: str) -> dict:
    """History view: everything ever approved or dismissed, newest first.
    Each entry knows if it's still *valid* (its data still produces the card)
    so the UI can offer re-download for approved items."""
    decisions = user_store.get_key(email, "smart_decisions", {}) or {}
    # a fresh snapshot of every currently-producible card, keyed by id
    live = {c["id"]: c for c in build_insights(email, include_decided=True)}
    approved, dismissed = [], []
    for iid, rec in decisions.items():
        state = rec.get("state") if isinstance(rec, dict) else rec
        at = rec.get("at") if isinstance(rec, dict) else None
        # title/icon: prefer live, fall back to remembered snapshot on the record
        snap = live.get(iid) or (rec.get("snapshot") if isinstance(rec, dict) else None) or {}
        entry = {
            "id": iid, "title": snap.get("title", iid), "icon": snap.get("icon", "•"),
            "detail": snap.get("detail", ""), "at": at,
            "valid": iid in live, "has_download": bool(snap.get("has_download")),
        }
        # tolerate the earlier "disapproved" label; "dismissed" is the new name.
        if state == "approved":
            approved.append(entry)
        elif state in ("dismissed", "disapproved"):
            dismissed.append(entry)
    # newest first (fall back to 0 when a legacy record lacks a timestamp)
    approved.sort(key=lambda e: e.get("at") or "", reverse=True)
    dismissed.sort(key=lambda e: e.get("at") or "", reverse=True)
    return {"approved": approved, "dismissed": dismissed}


def _decision_snapshot(email: str, insight_id: str) -> dict:
    """Look the insight up in the current live list so we can remember its
    title/detail even if the underlying data later changes (so History still
    reads sensibly six months later)."""
    for c in build_insights(email, include_decided=True):
        if c["id"] == insight_id:
            return {k: c[k] for k in ("title", "icon", "detail", "has_download") if k in c}
    return {}


def set_decision(email: str, insight_id: str, decision: str) -> None:
    import pandas as pd
    decisions = user_store.get_key(email, "smart_decisions", {}) or {}
    prev = decisions.get(insight_id) or {}
    snapshot = prev.get("snapshot") if isinstance(prev, dict) else None
    if not snapshot:
        snapshot = _decision_snapshot(email, insight_id)
    decisions[insight_id] = {
        "state": decision,
        "at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "snapshot": snapshot,
    }
    user_store.set_key(email, "smart_decisions", decisions)


def reset_decision(email: str, insight_id: str) -> None:
    """Undo — pull the item back into the active Approval panel."""
    decisions = user_store.get_key(email, "smart_decisions", {}) or {}
    decisions.pop(insight_id, None)
    user_store.set_key(email, "smart_decisions", decisions)


# ---------------------------------------------------------
# Approve == execute -> produce the Excel deliverable
# ---------------------------------------------------------
def _combo_message(item: str, pair: str, discount: int = 15) -> str:
    return (f"NEW combo alert! Grab a {item} + {pair} together and save {discount}%. "
            f"The perfect pair — only this week. See you at the counter!")


def insight_excel(email: str, insight_id: str) -> tuple[str, io.BytesIO] | None:
    """Build the ready-to-use Excel for an approved insight. Returns
    (filename, BytesIO) or None if the underlying data has gone."""
    if str(insight_id).startswith("reorder"):
        from backend.core import supply as _supply
        po = _supply.po_for_insight(email, insight_id)
        return _supply.po_excel(email, po) if po else None

    txns = load_sales(email)
    review = load_review(email)

    if insight_id == "winback" and txns is not None:
        rows = templates.build_winback_messages(analytics.at_risk_customers(txns))
        if not rows:
            return None
        df = pd.DataFrame(rows).rename(columns={
            "customer_id": "Customer ID", "customer_name": "Customer Name",
            "recency_days": "Days Since Last Visit", "frequency": "Total Orders",
            "monetary": "Total Spend", "last_purchase_date": "Last Purchase Date",
            "favorite_item": "Favorite Item", "price_tier": "Spend Tier",
            "coupon_code": "Coupon Code", "discount_pct": "Discount %", "message": "AI Message",
        })
        cols = ["Customer ID", "Customer Name", "Last Purchase Date", "Days Since Last Visit",
                "Total Orders", "Total Spend", "Favorite Item", "Spend Tier",
                "Coupon Code", "Discount %", "AI Message"]
        df = df[[c for c in cols if c in df.columns]]
        return "smart_cafex_winback_campaign.xlsx", _to_xlsx(df, "Win-back Campaign")

    if insight_id == "reputation" and review is not None:
        pos = positioning.analyze_reviews(review, "en", product_type=get_product_type(email))
        if not pos.get("available"):
            return None
        df = pd.DataFrame([{
            "Priority": i + 1,
            "Insight": ins.get("text", ""),
            "Recommended Action": ins.get("action", ""),
        } for i, ins in enumerate(pos.get("insights", []))])
        return "smart_cafex_positioning_plan.xlsx", _to_xlsx(df, "Positioning Plan")

    if insight_id == "complaints" and review is not None:
        comp = complaints.analyze_complaints(review, product_type=get_product_type(email))
        focus = (comp.get("focus") or {}).get("focus_now") or []
        if not focus:
            return None
        df = pd.DataFrame([{
            "Rank": i + 1, "Theme": x.get("theme", ""), "Severity": x.get("severity", ""),
            "Complaints": x.get("count", 0), "Share %": x.get("share_pct", ""),
            "Fix-First Action": x.get("action", ""),
        } for i, x in enumerate(focus)])
        return "smart_cafex_complaint_fix_plan.xlsx", _to_xlsx(df, "Complaint Fix Plan")

    return None


def _to_xlsx(df: pd.DataFrame, sheet: str) -> io.BytesIO:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet[:31])
        ws = writer.sheets[sheet[:31]]
        for i, col in enumerate(df.columns):
            width = min(70, max(12, int(df[col].astype(str).str.len().max() if len(df) else 12) + 2, len(str(col)) + 2))
            ws.column_dimensions[chr(65 + i) if i < 26 else "A"].width = width
    buf.seek(0)
    return buf


# ---------------------------------------------------------
# Task list (per account)
# ---------------------------------------------------------
def get_tasks(email: str) -> list[dict]:
    return user_store.get_key(email, "smart_tasks", []) or []


def add_task(email: str, text: str) -> list[dict]:
    text = (text or "").strip()
    if not text:
        return get_tasks(email)
    tasks = get_tasks(email)
    tid = hashlib.md5(f"{text}{pd.Timestamp.now().isoformat()}".encode()).hexdigest()[:10]
    tasks.append({"id": tid, "text": text[:280], "done": False})
    user_store.set_key(email, "smart_tasks", tasks)
    return tasks


def toggle_task(email: str, task_id: str, done: bool) -> list[dict]:
    tasks = get_tasks(email)
    for t in tasks:
        if t["id"] == task_id:
            t["done"] = bool(done)
    user_store.set_key(email, "smart_tasks", tasks)
    return tasks


def delete_task(email: str, task_id: str) -> list[dict]:
    tasks = [t for t in get_tasks(email) if t["id"] != task_id]
    user_store.set_key(email, "smart_tasks", tasks)
    return tasks
