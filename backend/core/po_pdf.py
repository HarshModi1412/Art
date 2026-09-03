"""
Purchase Order PDF — a proper, professional-looking PO document.

Given a saved PO dict (backend.core.supply.create_po), renders an A4 PDF with:
  * a header band (title, PO number, date, status),
  * a Buyer block and, for each supplier, a Vendor block + its line items,
  * per-supplier subtotals and a grand total (quantity + amount),
  * terms / notes and a disclaimer footer.

The rupee glyph renders when a Unicode TrueType font is available (DejaVu Sans
on most Linux hosts); otherwise it falls back to Helvetica with an "Rs."
currency prefix, so the file is always valid.

Dependency: reportlab (already in requirements.txt).
"""
from __future__ import annotations

import io
import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

# ---- palette -------------------------------------------------------------
INK = colors.HexColor("#111827")
MUT = colors.HexColor("#6b7280")
VIO = colors.HexColor("#6d28d9")
LINE = colors.HexColor("#e5e7eb")
HEADBG = colors.HexColor("#f3f0ff")
ROWALT = colors.HexColor("#fafafa")
GRN = colors.HexColor("#065f46")

DISCLAIMER = ("Data-generated suggestion — confirm quantities, prices and supplier terms before ordering.")

# ---- fonts ---------------------------------------------------------------
_FONT = "Helvetica"
_FONT_B = "Helvetica-Bold"
_RUPEE = "Rs. "

_DEJAVU_CANDIDATES = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
    ("/Library/Fonts/DejaVuSans.ttf", "/Library/Fonts/DejaVuSans-Bold.ttf"),
]


def _init_fonts() -> None:
    global _FONT, _FONT_B, _RUPEE
    if _FONT == "DejaVuSans":  # already initialised
        return
    for reg, bold in _DEJAVU_CANDIDATES:
        try:
            if os.path.exists(reg) and os.path.exists(bold):
                pdfmetrics.registerFont(TTFont("DejaVuSans", reg))
                pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", bold))
                _FONT, _FONT_B, _RUPEE = "DejaVuSans", "DejaVuSans-Bold", "₹"
                return
        except Exception:
            continue


def _money(v) -> str:
    if v is None or v == "":
        return "—"
    try:
        return f"{_RUPEE}{float(v):,.2f}"
    except (TypeError, ValueError):
        return "—"


def _qty(v) -> str:
    try:
        f = float(v)
        return str(int(f)) if f == int(f) else f"{f:g}"
    except (TypeError, ValueError):
        return str(v or "")


def _fmt_date(iso: str) -> str:
    try:
        return datetime.fromisoformat(str(iso)).strftime("%d %b %Y, %H:%M")
    except Exception:
        return str(iso or "")


def _group_by_supplier(lines: list[dict]) -> list[tuple[str, list[dict]]]:
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for l in lines:
        key = (l.get("supplier_name") or "").strip() or "Unspecified supplier"
        if key not in groups:
            groups[key] = []
            order.append(key)
    for l in lines:
        key = (l.get("supplier_name") or "").strip() or "Unspecified supplier"
        groups[key].append(l)
    return [(k, groups[k]) for k in order]


def build_po_pdf(po: dict, buyer_email: str = "", brand: str = "Content Seller") -> io.BytesIO:
    _init_fonts()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=16 * mm, rightMargin=16 * mm,
        topMargin=16 * mm, bottomMargin=18 * mm,
        title=f"Purchase Order {po.get('po_number', '')}",
    )

    body = ParagraphStyle("body", fontName=_FONT, fontSize=9, textColor=INK, leading=12)
    mut = ParagraphStyle("mut", fontName=_FONT, fontSize=8.5, textColor=MUT, leading=12)
    mut_r = ParagraphStyle("mutR", parent=mut, alignment=TA_RIGHT)
    h_title = ParagraphStyle("title", fontName=_FONT_B, fontSize=22, textColor=VIO, leading=24)
    h_block = ParagraphStyle("hblock", fontName=_FONT_B, fontSize=9.5, textColor=INK, leading=13)
    meta_r = ParagraphStyle("metaR", fontName=_FONT, fontSize=9, textColor=INK,
                            leading=14, alignment=TA_RIGHT)
    vend = ParagraphStyle("vend", fontName=_FONT_B, fontSize=10, textColor=colors.white, leading=13)
    cell = ParagraphStyle("cell", fontName=_FONT, fontSize=8.5, textColor=INK, leading=11)
    cell_r = ParagraphStyle("cellR", parent=cell, alignment=TA_RIGHT)
    cell_h = ParagraphStyle("cellH", fontName=_FONT_B, fontSize=8.5, textColor=INK, leading=11)
    cell_hr = ParagraphStyle("cellHR", parent=cell_h, alignment=TA_RIGHT)

    el = []
    content_w = doc.width

    # ---- header band -----------------------------------------------------
    status = str(po.get("status", "open")).upper()
    meta = (f"<b>PO No.</b>  {po.get('po_number', '')}<br/>"
            f"<b>Date</b>  {_fmt_date(po.get('created_at'))}<br/>"
            f"<b>Status</b>  {status}")
    head = Table(
        [[Paragraph("PURCHASE ORDER", h_title), Paragraph(meta, meta_r)]],
        colWidths=[content_w * 0.55, content_w * 0.45])
    head.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    el.append(head)
    el.append(Spacer(1, 4))
    el.append(Table([[""]], colWidths=[content_w], rowHeights=[2],
                    style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), VIO)])))
    el.append(Spacer(1, 10))

    # ---- buyer block -----------------------------------------------------
    buyer = (f"<b>Buyer</b><br/>{brand}"
             + (f"<br/>{buyer_email}" if buyer_email else ""))
    note = f"{po.get('n_items', 0)} item(s) &middot; {len(po.get('suppliers') or [])} supplier(s)"
    buyer_tbl = Table(
        [[Paragraph(buyer, body), Paragraph(note, mut_r)]],
        colWidths=[content_w * 0.6, content_w * 0.4])
    buyer_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    el.append(buyer_tbl)
    el.append(Spacer(1, 12))

    # ---- per-supplier sections ------------------------------------------
    grand_qty, grand_amt, any_cost = 0, 0.0, False
    col_w = [content_w * 0.06, content_w * 0.40, content_w * 0.12,
             content_w * 0.14, content_w * 0.14, content_w * 0.14]

    for supplier, lines in _group_by_supplier(po.get("lines", [])):
        sample = lines[0]
        contact = []
        if sample.get("supplier_phone"):
            contact.append(f"☎ {sample['supplier_phone']}")
        if sample.get("supplier_email"):
            contact.append(f"✉ {sample['supplier_email']}")
        contact_txt = "   ".join(contact) or "No contact on file"
        vend_tbl = Table(
            [[Paragraph(f"Vendor:  {supplier}", vend),
              Paragraph(contact_txt, ParagraphStyle("c", parent=mut_r, textColor=colors.HexColor('#ede9fe')))]],
            colWidths=[content_w * 0.55, content_w * 0.45])
        vend_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), VIO),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        el.append(vend_tbl)

        data = [[Paragraph("#", cell_h), Paragraph("Item", cell_h),
                 Paragraph("Qty", cell_hr), Paragraph("Unit", cell_h),
                 Paragraph("Unit cost", cell_hr), Paragraph("Amount", cell_hr)]]
        sub_qty, sub_amt, sub_cost = 0, 0.0, False
        for i, l in enumerate(lines, 1):
            name = l.get("name", "")
            cat = l.get("category", "")
            name_html = name + (f"<br/><font size=7 color='#6b7280'>{cat}</font>" if cat else "")
            qty = int(l.get("order_qty") or 0)
            amt = l.get("line_amount")
            sub_qty += qty
            if amt is not None:
                sub_amt += float(amt)
                sub_cost = True
            data.append([
                Paragraph(str(i), cell),
                Paragraph(name_html, cell),
                Paragraph(_qty(qty), cell_r),
                Paragraph(l.get("unit_label", "unit"), cell),
                Paragraph(_money(l.get("unit_cost")), cell_r),
                Paragraph(_money(amt), cell_r),
            ])
        # subtotal row
        data.append([
            Paragraph("", cell), Paragraph("Subtotal", cell_h),
            Paragraph(_qty(sub_qty), cell_hr), Paragraph("", cell),
            Paragraph("", cell), Paragraph(_money(sub_amt) if sub_cost else "—", cell_hr)])

        tbl = Table(data, colWidths=col_w, repeatRows=1)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), HEADBG),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, VIO),
            ("LINEBELOW", (0, 1), (-1, -2), 0.4, LINE),
            ("LINEABOVE", (0, -1), (-1, -1), 0.8, INK),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]
        for r in range(1, len(data) - 1):
            if r % 2 == 0:
                style.append(("BACKGROUND", (0, r), (-1, r), ROWALT))
        tbl.setStyle(TableStyle(style))
        el.append(tbl)
        el.append(Spacer(1, 14))

        grand_qty += sub_qty
        if sub_cost:
            grand_amt += sub_amt
            any_cost = True

    # ---- grand total -----------------------------------------------------
    total_amt = po.get("total_amount")
    if total_amt is None and any_cost:
        total_amt = round(grand_amt, 2)
    tot = Table(
        [[Paragraph("TOTAL", ParagraphStyle("t", fontName=_FONT_B, fontSize=11,
                                            textColor=colors.white, alignment=TA_RIGHT)),
          Paragraph(f"{_qty(po.get('total_qty', grand_qty))} units", ParagraphStyle(
              "tq", fontName=_FONT_B, fontSize=11, textColor=colors.white, alignment=TA_RIGHT)),
          Paragraph(_money(total_amt), ParagraphStyle(
              "ta", fontName=_FONT_B, fontSize=11, textColor=colors.white, alignment=TA_RIGHT))]],
        colWidths=[content_w * 0.58, content_w * 0.20, content_w * 0.22])
    tot.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), INK),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    el.append(tot)
    el.append(Spacer(1, 16))

    # ---- terms -----------------------------------------------------------
    terms = ("<b>Terms &amp; notes.</b> Suggested reorder quantities use the reorder point "
             "(daily usage &times; lead time + safety stock) and the Economic Order Quantity, "
             "raised to the supplier's minimum order quantity where set. Please confirm price "
             "and availability with the vendor before dispatch.")
    el.append(Paragraph(terms, mut))

    def _footer(canvas, d):
        canvas.saveState()
        canvas.setFont(_FONT, 7)
        canvas.setFillColor(MUT)
        canvas.drawString(16 * mm, 11 * mm, DISCLAIMER[:105])
        canvas.drawRightString(A4[0] - 16 * mm, 11 * mm,
                               f"{po.get('po_number', '')} · Page {d.page}")
        canvas.restoreState()

    doc.build(el, onFirstPage=_footer, onLaterPages=_footer)
    buf.seek(0)
    return buf
