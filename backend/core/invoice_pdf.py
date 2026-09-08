"""
The invoice PDF — A4, and shaped by Rule 46 rather than by taste.

Every block below exists because a clause requires it. The layout is boring on
purpose: an invoice is read by an accountant reconciling it against a return,
not by a shopper admiring it, and anything decorative here is something that can
be mistaken for data.
"""
from __future__ import annotations

from reportlab.lib.colors import HexColor, black
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from backend.core import gst

W, H = A4
M = 16 * mm
MUTED = HexColor("#6c757d")
RULE = HexColor("#dee2e6")


def _money(paise: int) -> str:
    neg = paise < 0
    p = abs(int(paise))
    s = f"{p // 100:,}.{p % 100:02d}"
    return f"-{s}" if neg else s


def _rule(c, y, colour=RULE, width=0.6):
    c.setStrokeColor(colour); c.setLineWidth(width)
    c.line(M, y, W - M, y); c.setStrokeColor(black)


def _block(c, x, y, title, lines, width):
    c.setFont("Helvetica-Bold", 7); c.setFillColor(MUTED)
    c.drawString(x, y, title.upper()); c.setFillColor(black)
    y -= 4.6 * mm
    for i, ln in enumerate(lines):
        if not ln:
            continue
        c.setFont("Helvetica-Bold" if i == 0 else "Helvetica", 9 if i == 0 else 8)
        for chunk in _fit(c, str(ln), width, "Helvetica" if i else "Helvetica-Bold",
                          8 if i else 9):
            c.drawString(x, y, chunk); y -= 4.2 * mm
    return y


def _fit(c, text, width, font, size):
    out, line = [], ""
    for w in text.split():
        t = f"{line} {w}".strip()
        if c.stringWidth(t, font, size) <= width:
            line = t
        else:
            out.append(line); line = w
    if line:
        out.append(line)
    return out or [""]


def build(inv: dict) -> bytes:
    import io
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    doc = inv.get("document") or {}
    seller = inv.get("seller") or {}
    buyer = inv.get("buyer") or {}
    pos = inv.get("place_of_supply") or {}
    inter = pos.get("kind") == "inter"

    y = H - M

    # ---- title. The heading is legally load-bearing: an unregistered seller
    # must NOT put "Tax Invoice" on a document (CGST Sec 32(1)).
    c.setFont("Helvetica-Bold", 16)
    c.drawString(M, y, doc.get("title") or "Invoice")
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(W - M, y, inv.get("number") or "")
    y -= 5.5 * mm
    c.setFont("Helvetica", 8); c.setFillColor(MUTED)
    c.drawString(M, y, seller.get("trade_name") or seller.get("legal_name") or "")
    c.drawRightString(W - M, y, f"Dated {inv.get('date') or ''}")
    c.setFillColor(black)
    y -= 5 * mm
    _rule(c, y, black, 1.0); y -= 7 * mm

    # ---- parties
    half = (W - 2 * M) / 2 - 6 * mm
    sa = seller.get("pickup_address") or {}
    sup = [seller.get("legal_name") or "",
           ", ".join(x for x in [sa.get("line1"), sa.get("line2")] if x),
           ", ".join(x for x in [sa.get("city"), sa.get("state")] if x)
           + (f" - {sa['pincode']}" if sa.get("pincode") else "")]
    if seller.get("gstin"):
        sup.append(f"GSTIN {seller['gstin']}")
    left_end = _block(c, M, y, "Supplier", sup, half)

    ba = buyer.get("address") or {}
    bill = [buyer.get("name") or "",
            ", ".join(x for x in [ba.get("line1"), ba.get("line2")] if x),
            ", ".join(x for x in [ba.get("city"), ba.get("state")] if x)
            + (f" - {ba['pincode']}" if ba.get("pincode") else ""),
            f"Phone {buyer.get('phone')}" if buyer.get("phone") else ""]
    right_end = _block(c, M + half + 12 * mm, y, "Bill to / Ship to", bill, half)
    y = min(left_end, right_end) - 2 * mm

    # ---- Rule 46(n): place of supply with state name, on every invoice.
    c.setFont("Helvetica", 8); c.setFillColor(MUTED)
    c.drawString(M, y, f"Place of supply: {buyer.get('state') or '—'} "
                       f"({buyer.get('state_code') or '—'})   ·   "
                       f"{'Inter-state — IGST' if inter else 'Intra-state — CGST + SGST'}"
                       f"   ·   Reverse charge: No")
    c.setFillColor(black)
    y -= 6 * mm
    _rule(c, y); y -= 7 * mm

    # ---- lines
    cols = [M, M + 78 * mm, M + 100 * mm, M + 114 * mm, M + 140 * mm, W - M]
    c.setFont("Helvetica-Bold", 7); c.setFillColor(MUTED)
    for label, x, align in (("DESCRIPTION", cols[0], "l"), ("HSN", cols[1], "l"),
                            ("QTY", cols[2], "r"), ("RATE", cols[3], "r"),
                            ("TAXABLE", cols[4], "r"), ("AMOUNT", cols[5], "r")):
        (c.drawRightString if align == "r" else c.drawString)(x, y, label)
    c.setFillColor(black)
    y -= 2.5 * mm
    _rule(c, y); y -= 5 * mm

    for ln in inv.get("lines", []):
        c.setFont("Helvetica", 9)
        for i, chunk in enumerate(_fit(c, ln.get("name") or "", 74 * mm, "Helvetica", 9)):
            c.drawString(cols[0], y - i * 4 * mm, chunk)
        c.setFont("Helvetica", 8)
        c.drawString(cols[1], y, ln.get("hsn") or "—")
        c.drawRightString(cols[2], y, str(ln.get("qty") or 0))
        c.drawRightString(cols[3], y, f"{ln.get('rate', 0)}%")
        c.drawRightString(cols[4], y, _money(ln.get("taxable", 0)))
        c.drawRightString(cols[5], y, _money(ln.get("gross", 0)))
        y -= 5.5 * mm
        why = ln.get("rate_why") or ""
        if why and ln.get("rate", 0) and "threshold" in why:
            c.setFont("Helvetica-Oblique", 6.5); c.setFillColor(MUTED)
            c.drawString(cols[0] + 2 * mm, y, why)
            c.setFillColor(black); y -= 4 * mm
        y -= 1 * mm
        if y < 70 * mm:
            c.showPage(); y = H - M

    _rule(c, y + 2 * mm); y -= 4 * mm

    # ---- totals
    tx = W - M - 40 * mm
    def row(label, value, bold=False, size=9):
        nonlocal y
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawRightString(tx, y, label)
        c.drawRightString(W - M, y, value)
        y -= 5 * mm

    row("Taxable value", _money(inv.get("taxable", 0)))
    heads = inv.get("heads") or {}
    if doc.get("charges_tax"):
        if inter:
            row("IGST", _money(heads.get("igst", 0)))
        else:
            row("CGST", _money(heads.get("cgst", 0)))
            row("SGST", _money(heads.get("sgst", 0)))
    if inv.get("shipping"):
        row("Shipping", _money(inv["shipping"]))
    if inv.get("round_off"):
        row("Round off", _money(inv["round_off"]))
    y -= 1 * mm
    _rule(c, y + 3 * mm, black, 0.9)
    row("Total", f"Rs {_money(inv.get('grand_total', 0))}", bold=True, size=11)

    # ---- declarations
    y -= 6 * mm
    c.setFont("Helvetica", 7); c.setFillColor(MUTED)
    notes = []
    if doc.get("declaration"):
        notes.append(doc["declaration"])
    if not doc.get("charges_tax") and doc.get("kind") == "receipt":
        notes.append("Not a tax invoice. This seller is not registered under GST "
                     "and has not collected any amount as tax.")
    if inv.get("inclusive") and doc.get("charges_tax"):
        notes.append("Prices shown include GST. Taxable value is derived from the "
                     "inclusive price.")
    if doc.get("charges_tax"):
        notes.append("Tax amounts are rounded to the nearest rupee per tax head "
                     "(CGST Act, Section 170), so CGST and SGST may differ by Re 1.")
    for n in notes:
        for chunk in _fit(c, n, W - 2 * M, "Helvetica", 7):
            c.drawString(M, y, chunk); y -= 3.6 * mm
    c.setFillColor(black)

    # ---- signature (Rule 46(q))
    c.setFont("Helvetica", 8)
    c.drawRightString(W - M, M + 16 * mm,
                      f"For {seller.get('legal_name') or seller.get('trade_name') or ''}")
    _rule(c, M + 10 * mm)
    c.setFont("Helvetica", 7); c.setFillColor(MUTED)
    c.drawRightString(W - M, M + 6 * mm, "Authorised signatory")
    c.drawString(M, M + 6 * mm, "Generated by One Tap Manager")

    c.showPage(); c.save()
    return buf.getvalue()
