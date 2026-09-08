"""
Shipping labels — the sticker that goes on the parcel.

Sized 4x6 inches, which is what every thermal label printer in Indian logistics
expects and what a courier pickup executive is trained to read at a glance.
It also prints fine on A4 if the seller has no label printer; the page is just
the label with white around it.

WHAT GOES ON IT, AND WHY
------------------------
The layout follows the courier convention rather than inventing one, because the
label is read by a delivery rider under time pressure, not by the seller:

  * Payment mode is the LARGEST thing on the label after the address. A rider
    who misses "COD Rs 1,499" either fails to collect or wrongly demands money
    from a prepaid customer, and both end in a failed delivery.
  * The return-to address is mandatory, not optional. A parcel with no return
    address that cannot be delivered is destroyed rather than returned, and RTO
    runs around a quarter of COD orders in India.
  * The barcode encodes the order number so a scan resolves it without typing.
"""
from __future__ import annotations

import io
import re

from reportlab.graphics.barcode import code128
from reportlab.lib.colors import black, white
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

W, H = 101.6 * mm, 152.4 * mm          # 4 x 6 inches
PAD = 4 * mm


def _wrap(c: canvas.Canvas, text: str, x: float, y: float, width: float,
          font: str, size: int, leading: float) -> float:
    """Draw wrapped text, return the y below the last line."""
    c.setFont(font, size)
    words, line = str(text or "").split(), ""
    for w in words:
        trial = f"{line} {w}".strip()
        if c.stringWidth(trial, font, size) <= width:
            line = trial
        else:
            if line:
                c.drawString(x, y, line)
                y -= leading
            line = w
    if line:
        c.drawString(x, y, line)
        y -= leading
    return y


def _rule(c: canvas.Canvas, y: float, dash: bool = False) -> None:
    c.setLineWidth(0.6)
    c.setDash(2, 2) if dash else c.setDash()
    c.line(PAD, y, W - PAD, y)
    c.setDash()


def _draw(c: canvas.Canvas, order: dict, seller: dict, site: dict) -> None:
    """Paint one label onto the current page of an open canvas."""
    inner = W - 2 * PAD
    y = H - PAD

    # ---- carrier strip -------------------------------------------------
    c.setFillColor(black)
    c.rect(PAD, y - 9 * mm, inner, 9 * mm, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(PAD + 2 * mm, y - 6 * mm, (site.get("name") or "Store")[:26].upper())
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(W - PAD - 2 * mm, y - 6 * mm, "EXPRESS · FWD")
    c.setFillColor(black)
    y -= 9 * mm + 3 * mm

    # ---- payment mode: the most important line on the label ------------
    pay = (order.get("payment") or "cod").lower()
    due = float(order.get("due_on_delivery") or 0)
    cur = order.get("currency") or "Rs"
    if pay == "prepaid" or due <= 0:
        head, sub = "PREPAID", "Do not collect any amount"
    else:
        head, sub = f"COD  {cur} {due:,.0f}", "Collect this amount on delivery"
    box_h = 15 * mm
    c.setLineWidth(1.4)
    c.rect(PAD, y - box_h, inner, box_h, fill=0, stroke=1)
    c.setFont("Helvetica-Bold", 17)
    c.drawCentredString(W / 2, y - 8.5 * mm, head)
    c.setFont("Helvetica", 7)
    c.drawCentredString(W / 2, y - 13 * mm, sub)
    y -= box_h + 3 * mm

    # ---- barcode -------------------------------------------------------
    order_no = str(order.get("order_no") or order.get("id") or "")[:20]
    bc = code128.Code128(order_no, barHeight=12 * mm, barWidth=0.42 * mm, humanReadable=False)
    bw = bc.width
    bc.drawOn(c, max(PAD, (W - bw) / 2), y - 12 * mm)
    y -= 12 * mm + 1 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(W / 2, y - 3 * mm, order_no)
    y -= 6 * mm
    _rule(c, y); y -= 4 * mm

    # ---- deliver to ----------------------------------------------------
    a = order.get("address") or {}
    c.setFont("Helvetica-Bold", 7)
    c.drawString(PAD, y, "DELIVER TO")
    y -= 5 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(PAD, y, str(order.get("customer_name") or "")[:34])
    y -= 5.5 * mm
    parts = [a.get("line1"), a.get("line2"), a.get("landmark")]
    y = _wrap(c, ", ".join(p for p in parts if p), PAD, y, inner, "Helvetica", 9, 4.4 * mm)
    city = ", ".join(p for p in [a.get("city"), a.get("state")] if p)
    y = _wrap(c, city, PAD, y, inner, "Helvetica", 9, 4.4 * mm)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(PAD, y - 1 * mm, re.sub(r"\D", "", str(a.get("pincode") or "")))
    c.setFont("Helvetica", 9)
    c.drawRightString(W - PAD, y - 1 * mm, f"Ph {order.get('phone') or ''}")
    y -= 7 * mm
    _rule(c, y, dash=True); y -= 4 * mm

    # ---- contents ------------------------------------------------------
    items = order.get("items") or []
    qty = sum(int(i.get("qty") or 0) for i in items)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(PAD, y, f"CONTENTS  ({qty} item{'s' if qty != 1 else ''})")
    y -= 4.5 * mm
    c.setFont("Helvetica", 8)
    for it in items[:5]:
        name = str(it.get("name") or "")[:38]
        var = str(it.get("variant_label") or "")
        label = f"{int(it.get('qty') or 1)} x {name}" + (f" ({var})" if var else "")
        c.drawString(PAD, y, label[:52])
        y -= 4 * mm
    if len(items) > 5:
        c.drawString(PAD, y, f"...and {len(items) - 5} more")
        y -= 4 * mm
    y -= 1 * mm
    _rule(c, y); y -= 4 * mm

    # ---- return to -----------------------------------------------------
    c.setFont("Helvetica-Bold", 7)
    c.drawString(PAD, y, "IF UNDELIVERED, RETURN TO")
    y -= 4.5 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(PAD, y, str(seller.get("business_name") or site.get("name") or "")[:40])
    y -= 4.2 * mm
    ret = seller.get("pickup_address") or {}
    ret_line = ", ".join(str(ret.get(k) or "") for k in ("line1", "line2", "city", "state") if ret.get(k))
    if ret.get("pincode"):
        ret_line = f"{ret_line} - {ret['pincode']}"
    y = _wrap(c, ret_line or "Return address not set in Settings",
              PAD, y, inner, "Helvetica", 8, 4 * mm)
    if seller.get("gstin"):
        c.setFont("Helvetica", 7)
        c.drawString(PAD, y, f"GSTIN {seller['gstin']}")
        y -= 4 * mm

    # ---- footer --------------------------------------------------------
    c.setFont("Helvetica", 6)
    c.drawString(PAD, PAD + 2 * mm,
                 f"Order {order_no} · placed {str(order.get('created_at') or '')[:10]}")
    c.drawRightString(W - PAD, PAD + 2 * mm, "Packed with One Tap Manager")


def build(order: dict, seller: dict, site: dict) -> bytes:
    """One label for one order."""
    return build_many([order], seller, site)


def build_many(orders: list[dict], seller: dict, site: dict) -> bytes:
    """One PDF, one label per page — so a seller printing the morning's dispatch
    presses print once instead of once per order.

    Drawing onto a single shared canvas is the whole point: reportlab has no
    merge, so each label has to be painted onto the same document rather than
    rendered separately and stitched."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    for o in orders:
        _draw(c, o, seller, site)
        c.showPage()
    c.save()
    return buf.getvalue()
