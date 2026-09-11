"""
Order-triggered replenishment — every order placed checks the raw materials it
used, and anything running short gets a purchase order drafted for approval.

THE WORKFLOW
------------
  1. **Trigger.** Every order placed on the seller's website (and the manual
     "Check now" button, and approving the "running low" card).
  2. **Check.** For each raw material the ordered products use, work out the
     new days of supply (DOS = current stock ÷ average daily consumption) and
     compare it with 1.2 × that material's lead time.
       * DOS ≥ 1.2 × lead time → nothing to do.
       * DOS < 1.2 × lead time → it needs ordering.
  3. **Draft the PO.** Materials that need ordering are grouped by supplier
     and each group becomes one DRAFT purchase order at each material's DOQ,
     addressed to the supplier on file in the Supplier module. A material that
     is already on an order in flight (draft, open, sent, shipped) is not
     ordered twice; a new material for a supplier who already has a draft
     waiting is added to that draft instead of starting a second one.
  4. **Approval panel.** Each draft is a card with Approve / Details / Cancel.
     Approve has the content writer draft the email, attaches the PO as a PDF
     and sends it to the supplier (see `send_po`). Details shows the lines,
     the maths behind each quantity and the email, all editable first.

Nothing here raises into the order path. A shopper's order must never fail
because a purchase order could not be drafted.
"""
from __future__ import annotations

import logging
import re

import pandas as pd

from backend.core import supply, user_store

log = logging.getLogger("replenish")

DOQ_KEY = "supply_doq_table"
LOG_KEY = "replenish_log"
EMAIL_KEY = "po_email_drafts"


def _now() -> str:
    return pd.Timestamp.now().isoformat(timespec="seconds")


def _norm(s) -> str:
    return str(s or "").strip().lower()


# --------------------------------------------------------------- DOQ table
def save_doq_table(email: str, rows: list[dict]) -> dict:
    """The DOQ worked out for every raw material, saved to the account.

    Kept as its own small table rather than extra columns on the inventory
    rows, so an existing Supabase inventory table needs no migration. The
    seller's own override lives on the item itself (`reorder_qty`)."""
    table = {}
    for r in rows:
        table[r["id"]] = {
            "name": r.get("name"), "doq": r.get("doq"), "basis": r.get("doq_basis"),
            "eoq": r.get("eoq"), "moq": r.get("moq"), "dos": r.get("dos"),
            "lead_time_days": r.get("effective_lead_time_days"),
            "avg_daily": r.get("avg_daily_consumption"),
            "annual_demand": r.get("annual_demand"),
            "override": r.get("doq_override"), "updated_at": _now(),
        }
    user_store.set_key(supply._email(email), DOQ_KEY, table)
    return table


def doq_table(email: str) -> dict:
    t = user_store.get_key(supply._email(email), DOQ_KEY, {}) or {}
    return t if isinstance(t, dict) else {}


# --------------------------------------------------------------- in flight
def covered_item_ids(email: str) -> set[str]:
    """Raw materials already on a purchase order that has not arrived."""
    out: set[str] = set()
    for po in supply.get_purchase_orders(email):
        if po.get("status") not in supply.ACTIVE_PO_STATUSES:
            continue
        for ln in po.get("lines") or []:
            if ln.get("inventory_id"):
                out.add(ln["inventory_id"])
    return out


def draft_pos(email: str) -> list[dict]:
    return [p for p in supply.get_purchase_orders(email)
            if p.get("status") == "draft" and p.get("source") == "auto"]


def _supplier_of(row: dict) -> dict:
    return {"name": (row.get("supplier_name") or "").strip(),
            "phone": (row.get("supplier_phone") or "").strip(),
            "email": (row.get("supplier_email") or "").strip()}


# --------------------------------------------------------------- the check
def items_for_products(email: str, product_names: list[str]) -> set[str]:
    """Raw materials a set of products use — through the recipe links, or an
    inventory item named like the product itself (a reseller's case)."""
    wanted = {_norm(p) for p in product_names if p}
    ids = {m["inventory_id"] for m in supply.get_maps(email) if _norm(m["product"]) in wanted}
    for it in supply.get_inventory(email):
        if _norm(it.get("name")) in wanted:
            ids.add(it["id"])
    return ids


def check(email: str, trigger: str = "order", product_names: list[str] | None = None,
          ref: str = "") -> dict:
    """Run the DOS rule and draft purchase orders where it fails.

    `product_names` narrows the check to the materials those products use —
    the order-placement case. None checks every raw material."""
    email = supply._email(email)
    comp = supply.compute_inventory(email)
    rows = comp["items"]
    save_doq_table(email, rows)

    scope = (items_for_products(email, product_names) if product_names is not None
             else {r["id"] for r in rows})
    checked = [r for r in rows if r["id"] in scope]
    low = [r for r in checked if r.get("needs_po")]
    covered = covered_item_ids(email)
    fresh = [r for r in low if r["id"] not in covered]

    groups: dict[str, list[dict]] = {}
    for r in fresh:
        key = _norm(r.get("supplier_name")) or "__none__"
        groups.setdefault(key, []).append(r)

    created, appended = [], []
    waiting = {(_norm((p.get("supplier") or {}).get("name")) or "__none__"): p
               for p in draft_pos(email)}
    label = {"order": f"Order {ref} placed" if ref else "An order was placed",
             "manual": "Checked by hand", "insight": "Approved from the running-low card",
             "sales": "New sales data"}.get(trigger, trigger)
    for key, grp in sorted(groups.items()):
        names = ", ".join(f"{r['name']} ({r['dos']:g} days left, needs {r['dos_threshold']:g})"
                          for r in grp)
        note = f"{label}: {names}."
        if key in waiting:
            po = supply.append_to_po(email, waiting[key]["po_number"], grp, note)
            if po:
                appended.append(po["po_number"])
            continue
        po = supply.create_auto_po(email, grp, _supplier_of(grp[0]), note=note, trigger=note)
        created.append(po["po_number"])

    result = {"at": _now(), "trigger": trigger, "ref": ref,
              "checked": [{"id": r["id"], "name": r["name"], "dos": r.get("dos"),
                           "threshold": r.get("dos_threshold"),
                           "ok": not r.get("needs_po")} for r in checked],
              "low": [r["name"] for r in low],
              "already_ordered": [r["name"] for r in low if r["id"] in covered],
              "created": created, "appended": appended}
    logs = user_store.get_key(email, LOG_KEY, []) or []
    logs.append({k: result[k] for k in ("at", "trigger", "ref", "low", "created", "appended")})
    user_store.set_key(email, LOG_KEY, logs[-50:])
    if created or appended:
        try:
            from backend.core import cache
            cache.clear(email)
        except Exception:  # noqa: BLE001
            pass
    return result


def after_order(seller: str, order: dict) -> dict | None:
    """Hook for the order path. Never raises."""
    try:
        names = [str(it.get("name") or "") for it in (order or {}).get("items") or []]
        return check(seller, "order", names, ref=str((order or {}).get("order_no") or ""))
    except Exception as e:  # noqa: BLE001 — never lose an order over this
        log.warning("replenishment check failed after order: %s", e)
        return None


def recent_log(email: str, limit: int = 10) -> list[dict]:
    rows = user_store.get_key(supply._email(email), LOG_KEY, []) or []
    return list(reversed(rows[-limit:]))


# --------------------------------------------------------------- approval cards
def insight_cards(email: str) -> list[dict]:
    """One Approval-panel card per draft purchase order."""
    out = []
    for po in draft_pos(email):
        sup = po.get("supplier") or {}
        lines = po.get("lines") or []
        names = ", ".join(f"{ln.get('name')} × {ln.get('order_qty')} {ln.get('unit_label') or ''}".strip()
                          for ln in lines[:3])
        if len(lines) > 3:
            names += f" +{len(lines) - 3} more"
        tightest = min((ln.get("dos") for ln in lines if ln.get("dos") is not None), default=None)
        has_mail = bool(sup.get("email"))
        out.append({
            "id": f"po_{po['po_number']}", "module": "supply", "page": "supply",
            "title": f"Order from {sup.get('name') or 'a supplier'} — {len(lines)} item{'s' if len(lines) != 1 else ''}",
            "detail": names, "po_number": po["po_number"],
            "supplier_name": sup.get("name") or "", "supplier_email": sup.get("email") or "",
            "has_email": has_mail, "n_items": len(lines),
            "total_amount": po.get("total_amount"), "tightest_dos": tightest,
            "reason": po.get("note") or "",
            "cta": "Approve & email the supplier" if has_mail else "Approve & download the PO",
            "has_download": False, "purchase_order": True,
            "count": 500 + len(lines),
        })
    return out


# --------------------------------------------------------------- sending
def _supplier_email(po: dict) -> str:
    sup = po.get("supplier") or {}
    if sup.get("email"):
        return sup["email"]
    return next((ln.get("supplier_email") for ln in po.get("lines") or []
                 if ln.get("supplier_email")), "")


def email_draft(email: str, po_number: str, refresh: bool = False) -> dict:
    """The email that will go with this PO — written once by the content
    writer and kept, so opening Details twice does not rewrite it."""
    drafts = user_store.get_key(supply._email(email), EMAIL_KEY, {}) or {}
    if not refresh and po_number in drafts and drafts[po_number].get("body"):
        return drafts[po_number]
    po = supply.get_po(email, po_number)
    if not po:
        raise ValueError("Purchase order not found.")
    from backend.core import writer
    d = writer.po_email(email, po)
    d["to"] = _supplier_email(po)
    drafts[po_number] = d
    user_store.set_key(supply._email(email), EMAIL_KEY, dict(list(drafts.items())[-40:]))
    return d


def save_email_draft(email: str, po_number: str, patch: dict) -> dict:
    drafts = user_store.get_key(supply._email(email), EMAIL_KEY, {}) or {}
    cur = drafts.get(po_number) or {}
    for k in ("subject", "body", "to"):
        if k in (patch or {}) and patch[k] is not None:
            cur[k] = str(patch[k])[:5000]
    drafts[po_number] = cur
    user_store.set_key(supply._email(email), EMAIL_KEY, drafts)
    return cur


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def send_po(email: str, po_number: str, subject: str = "", body: str = "",
            to: str = "") -> dict:
    """Approve: write the email (or use the one the seller edited), attach the
    PO PDF and send it to the supplier. The PO becomes "sent" only when the
    mail was actually accepted; otherwise it is "open" — approved, with the
    PDF and a ready-written email for the seller to send themselves."""
    from backend.core import messaging
    po = supply.get_po(email, po_number)
    if not po:
        raise ValueError("Purchase order not found.")
    if po.get("status") in ("cancelled", "received"):
        raise ValueError(f"This order is {po.get('status')} — nothing to send.")

    draft = email_draft(email, po_number) if not (subject and body) else {}
    subject = (subject or draft.get("subject") or f"Purchase order {po_number}").strip()
    body = (body or draft.get("body") or "").strip()
    to = (to or draft.get("to") or _supplier_email(po)).strip()
    save_email_draft(email, po_number, {"subject": subject, "body": body, "to": to})

    fname, buf = supply.po_pdf_bytes(email, {**po, "status": "open"}, for_supplier=True)
    pdf = buf.getvalue()

    reply_to = supply._email(email)
    sent, reason = False, ""
    if not to:
        reason = "No email address on file for this supplier — add it in the Supplier module."
    elif not _EMAIL_RE.match(to):
        reason = f"“{to}” does not look like an email address."
    else:
        res = messaging.send_with_attachments(
            to, subject, body, attachments=[(fname, pdf, "application/pdf")],
            reply_to=reply_to)
        sent = bool(res.get("email"))
        if not sent:
            reason = res.get("reason") or "The mail server did not accept it."

    hist = list(po.get("history") or [])
    status = "sent" if sent else "open"
    hist.append({"at": _now(), "status": status, "by": "seller",
                 "note": (f"Emailed to {to}" if sent else f"Approved — not emailed: {reason}")[:200]})
    supply.update_po(email, po_number, {"status": status, "history": hist})
    try:
        from backend.core import cache
        cache.clear(email)
    except Exception:  # noqa: BLE001
        pass
    mailto = ""
    if to:
        from urllib.parse import quote
        mailto = f"mailto:{to}?subject={quote(subject)}&body={quote(body[:1800])}"
    return {"sent": sent, "status": status, "to": to, "reason": reason,
            "subject": subject, "body": body, "po_number": po_number,
            "pdf_url": f"/api/supply/po/{po_number}/pdf?supplier=1",
            "mailto": mailto}


def cancel_po(email: str, po_number: str) -> dict | None:
    return supply.set_po_status(email, po_number, "cancelled", note="Cancelled from the Approval panel")
