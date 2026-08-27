"""
PDF report — a proper downloadable report of the café's dashboard:
prescriptive actions FIRST, then KPIs, forecast chart, category/product
charts, with the insights disclaimer on every page footer.

Dependencies: reportlab + matplotlib (both in requirements.txt).
"""
import io
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Image, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

INK = colors.HexColor("#111827")
MUT = colors.HexColor("#6b7280")
VIO = colors.HexColor("#6d28d9")
GRN = colors.HexColor("#059669")
AMB = colors.HexColor("#b45309")

DISCLAIMER = ("Cafe_X insights and forecasts are data-generated suggestions meant to support "
              "your judgment, not replace it. Actual results depend on many real-world factors, "
              "and business decisions — and their outcomes — remain yours. We're here to inform, "
              "not to guarantee.")


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica-Oblique", 7)
    canvas.setFillColor(MUT)
    canvas.drawString(18 * mm, 12 * mm, f"💡 {DISCLAIMER}"[:190])
    canvas.drawRightString(A4[0] - 18 * mm, 12 * mm, f"Page {doc.page} · Cafe_X")
    canvas.restoreState()


def _chart_image(fig, width_mm=174, height_mm=62) -> Image:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=width_mm * mm, height=height_mm * mm)


def _fmt_inr(v) -> str:
    return f"Rs {v:,.0f}" if v is not None else "—"


def build_sales_report(analytics: dict, insights_rendered: list[dict],
                       cafe_label: str = "Your Café") -> bytes:
    """analytics = output of analytics.sales_analytics(); insights_rendered =
    i18n.render_all(...) so each has text+action. Returns PDF bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=22 * mm,
                            title="Cafe_X Sales Report")
    ss = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=ss["Title"], fontSize=20, textColor=INK, spaceAfter=2)
    SUB = ParagraphStyle("SUB", parent=ss["Normal"], fontSize=9.5, textColor=MUT, spaceAfter=10)
    H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=13, textColor=VIO, spaceBefore=10, spaceAfter=6)
    BODY = ParagraphStyle("BODY", parent=ss["Normal"], fontSize=9.5, textColor=INK, leading=13)
    WHY = ParagraphStyle("WHY", parent=BODY, fontSize=8.5, textColor=MUT)

    kpis = analytics.get("kpis", {})
    story = [
        Paragraph("Cafe_X — Sales & Growth Report", H1),
        Paragraph(f"{cafe_label} · {kpis.get('date_from','')} to {kpis.get('date_to','')} · "
                  f"generated {datetime.now().strftime('%d %b %Y, %H:%M')}", SUB),
    ]

    # ---- 1. DO THIS NEXT (prescriptive actions first, like everywhere in the product)
    story.append(Paragraph("✅ Do this next", H2))
    actions = [i for i in insights_rendered if i.get("action")]
    if actions:
        rows = []
        for i, ins in enumerate(actions[:6], 1):
            mark = "▲" if ins.get("type") == "positive" else ("●" if ins.get("type") == "neutral" else "▼")
            col = GRN if ins.get("type") == "positive" else (AMB if ins.get("type") == "warning" else MUT)
            rows.append([Paragraph(f'<font color="{col.hexval()}">{mark}</font> <b>{i}.</b>', BODY),
                         [Paragraph(f"<b>{ins['action']}</b>", BODY),
                          Paragraph(f"Why: {ins['text']}", WHY)]])
        t = Table(rows, colWidths=[14 * mm, 160 * mm])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        story.append(t)
    else:
        story.append(Paragraph("Not enough data for actions yet — upload more history.", BODY))

    # ---- 2. KPIs
    story.append(Paragraph("📊 Key numbers", H2))
    kpi_rows = [["Revenue", "Orders", "Customers", "Avg order value"],
                [_fmt_inr(kpis.get("revenue")), f"{kpis.get('orders') or 0:,}",
                 f"{kpis.get('customers') or 0:,}", _fmt_inr(kpis.get("avg_order_value"))]]
    t = Table(kpi_rows, colWidths=[43.5 * mm] * 4)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f0ff")),
        ("TEXTCOLOR", (0, 0), (-1, 0), VIO), ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("FONTSIZE", (0, 1), (-1, 1), 12), ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
    ]))
    story.append(t)

    # ---- 3. Forecast chart (history + next 30 days)
    fc = analytics.get("forecast")
    if fc:
        story.append(Paragraph("🔮 Next 30 days — forecast", H2))
        story.append(Paragraph(
            f"Projected revenue ≈ <b>{_fmt_inr(fc['next_30_total'])}</b> "
            f"({fc['vs_last_30_pct']:+.1f}% vs your last 30 days).", BODY))
        if fc.get("model"):
            story.append(Paragraph(
                f"Method: {len(fc.get('models_tried', {})) or 4} forecasting models were backtested on a "
                f"held-out test window; the most accurate — <b>{fc['model']}</b> "
                f"(backtest error ±{fc.get('backtest_mape_pct','?')}%) — was refit on your full history.", WHY))
        fig, ax = plt.subplots(figsize=(8.6, 2.9))
        ax.plot(range(len(fc["hist_y"])), fc["hist_y"], color="#6d28d9", lw=1.4, label="Actual (last 60 days)")
        x0 = len(fc["hist_y"]) - 1
        ax.plot([x0 + i for i in range(1, len(fc["fcst_y"]) + 1)], fc["fcst_y"],
                color="#059669", lw=1.6, ls="--", label="Forecast (next 30 days)")
        ax.legend(fontsize=7, frameon=False)
        ax.set_ylabel("Daily revenue (Rs)", fontsize=7)
        ax.tick_params(labelsize=6.5)
        ax.spines[["top", "right"]].set_visible(False)
        story.append(_chart_image(fig))

    # ---- 4. Monthly trend + category + top products
    mt = analytics.get("monthly_trend")
    if mt and mt.get("x"):
        story.append(Paragraph("📈 Monthly revenue", H2))
        fig, ax = plt.subplots(figsize=(8.6, 2.6))
        ax.bar(mt["x"], mt["y"], color="#8b5cf6")
        ax.tick_params(labelsize=6.5, rotation=45)
        ax.spines[["top", "right"]].set_visible(False)
        story.append(_chart_image(fig, height_mm=54))

    cat = analytics.get("by_category")
    if cat and cat.get("x"):
        story.append(Paragraph("🧾 Revenue by category", H2))
        fig, ax = plt.subplots(figsize=(8.6, 2.4))
        ax.bar(cat["x"], cat["y"], color="#22c55e")
        ax.tick_params(labelsize=6.5, rotation=30)
        ax.spines[["top", "right"]].set_visible(False)
        story.append(_chart_image(fig, height_mm=50))

    top = analytics.get("top_products")
    if top and top.get("y"):
        story.append(Paragraph("🏆 Top products", H2))
        fig, ax = plt.subplots(figsize=(8.6, 2.6))
        ax.barh(top["y"], top["x"], color="#f59e0b")
        ax.tick_params(labelsize=6.5)
        ax.spines[["top", "right"]].set_visible(False)
        story.append(_chart_image(fig, height_mm=54))

    # ---- Menu engineering: slow-item beverage bundles
    me = analytics.get("menu_engineering")
    if me and me.get("bundles"):
        story.append(Paragraph("🍽️ Move your slow items — bundle them with a drink", H2))
        story.append(Paragraph(
            "Your slowest food items, each paired with the drink customers most often buy alongside it. "
            "Put these combos on the board, priced just below buying the two separately.", BODY))
        rows = [["Slow item", "Sell it with", "Why this pairing"]]
        for b in me["bundles"][:6]:
            rows.append([Paragraph(f"<b>{b['item']}</b> ({b['quadrant']}, {b['units']} units)", WHY),
                         Paragraph(f"<b>{b['pair_with']}</b>", WHY),
                         Paragraph(b["reason"], WHY)])
        t = Table(rows, colWidths=[52 * mm, 42 * mm, 80 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f0ff")),
            ("TEXTCOLOR", (0, 0), (-1, 0), VIO), ("FONTSIZE", (0, 0), (-1, 0), 8.5),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ]))
        story.append(t)

    story.append(Spacer(1, 6))
    story.append(Paragraph(f"<i>{DISCLAIMER}</i>", WHY))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def _doc(buf, title):
    return SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                             topMargin=16 * mm, bottomMargin=22 * mm, title=title)


def _styles():
    ss = getSampleStyleSheet()
    return {
        "H1": ParagraphStyle("H1", parent=ss["Title"], fontSize=20, textColor=INK, spaceAfter=2),
        "SUB": ParagraphStyle("SUB", parent=ss["Normal"], fontSize=9.5, textColor=MUT, spaceAfter=10),
        "H2": ParagraphStyle("H2", parent=ss["Heading2"], fontSize=13, textColor=VIO, spaceBefore=10, spaceAfter=6),
        "BODY": ParagraphStyle("BODY", parent=ss["Normal"], fontSize=9.5, textColor=INK, leading=13),
        "WHY": ParagraphStyle("WHY", parent=ss["Normal"], fontSize=8.5, textColor=MUT, leading=11),
    }


def build_complaints_report(data: dict, cafe_label: str = "Your Café") -> bytes:
    """PDF for the Complaint Trends page: Focus Framework first, monthly volume,
    then the deep table. Mirrors what the screen shows."""
    buf = io.BytesIO()
    doc = _doc(buf, "Cafe_X Complaint Report")
    s = _styles()
    det = data.get("detected", {})
    story = [
        Paragraph("Cafe_X — Complaint Intelligence Report", s["H1"]),
        Paragraph(f"{cafe_label} · {det.get('n_reviews', 0)} reviews · {det.get('n_complaints', 0)} complaints "
                  f"({det.get('complaint_rate', 0)}% rate) · generated {datetime.now().strftime('%d %b %Y')}", s["SUB"]),
    ]

    focus = data.get("focus")
    if focus and focus.get("focus_now"):
        story.append(Paragraph("🎯 Focus here first — don't fix everything at once", s["H2"]))
        story.append(Paragraph(focus.get("principle", ""), s["BODY"]))
        for i, x in enumerate(focus["focus_now"], 1):
            rising = x.get("growth_pct") is not None and x["growth_pct"] > 20
            story.append(Paragraph(
                f"<b>{i}. {x['theme']}</b> ({x['severity']}{', rising' if rising else ''}) — "
                f"{x['count']} complaints, {x['share_pct']}% of all.", s["BODY"]))
            story.append(Paragraph(f"✅ {x['action']}", s["WHY"]))
        if focus.get("watch"):
            story.append(Paragraph("Watch (only after the above): "
                                   + ", ".join(f"{w['theme']} ({w['count']})" for w in focus["watch"]), s["WHY"]))

    m = data.get("monthly")
    if m:
        story.append(Paragraph("📅 Complaints per month", s["H2"]))
        story.append(Paragraph(
            f"Averaging <b>{m['avg_per_month']}/month</b>; latest ({m['latest_month']}): "
            f"<b>{m['latest_count']}</b> — {'up' if m['mom_change_pct'] >= 0 else 'down'} "
            f"{abs(m['mom_change_pct'])}% vs the earlier period.", s["BODY"]))
        fig, ax = plt.subplots(figsize=(8.6, 2.5))
        ax.bar(m["months"], m["counts"], color="#f97316")
        ax.set_ylabel("Complaints", fontsize=7); ax.tick_params(labelsize=6.5, rotation=45)
        ax.spines[["top", "right"]].set_visible(False)
        story.append(_chart_image(fig, height_mm=52))

    deep = data.get("deep", [])
    if deep:
        story.append(Paragraph("🔎 All complaint themes (one-off gripes excluded)", s["H2"]))
        rows = [["Theme", "Count", "Share", "Severity", "Trend"]]
        for r in deep:
            g = "—" if r["growth_pct"] is None else f"{'+' if r['growth_pct'] >= 0 else ''}{r['growth_pct']}%"
            rows.append([r["theme"], str(r["count"]), f"{r['share_pct']}%", r["severity"], g])
        t = Table(rows, colWidths=[54 * mm, 24 * mm, 26 * mm, 44 * mm, 26 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fff1e6")),
            ("TEXTCOLOR", (0, 0), (-1, 0), AMB), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ]))
        story.append(t)

    ig = data.get("ignored")
    if ig and ig.get("themes"):
        story.append(Paragraph(
            f"Set aside {ig['complaints']} one-off complaints across {ig['themes']} minor "
            f"theme(s) ({', '.join(ig['examples'])}) — too few to be a pattern.", s["WHY"]))

    story.append(Spacer(1, 6))
    story.append(Paragraph(f"<i>{DISCLAIMER}</i>", s["WHY"]))
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def build_positioning_report(data: dict, cafe_label: str = "Your Brand") -> bytes:
    """PDF for the Positioning page: actions first, then what your customers talk about."""
    buf = io.BytesIO()
    doc = _doc(buf, "Brand Positioning Report")
    s = _styles()
    quad = (data.get("position") or {}).get("quadrant")
    story = [
        Paragraph("Brand Positioning Report", s["H1"]),
        Paragraph(f"{cafe_label} · {data.get('n_reviews', 0)} reviews analysed"
                  + (f" · position: {quad}" if quad else "")
                  + f" · generated {datetime.now().strftime('%d %b %Y')}", s["SUB"]),
    ]
    story.append(Paragraph("✅ What to do", s["H2"]))
    for i, ins in enumerate([x for x in data.get("insights", []) if x.get("action")][:6], 1):
        story.append(Paragraph(f"<b>{i}.</b> {ins['action']}", s["BODY"]))
        if ins.get("text"):
            story.append(Paragraph(f"Why: {ins['text']}", s["WHY"]))

    sc = data.get("share_chart")
    if sc and sc.get("themes"):
        story.append(Paragraph("📊 What your customers talk about (% of reviews)", s["H2"]))
        fig, ax = plt.subplots(figsize=(8.6, 3.2))
        y = range(len(sc["themes"]))
        ax.barh(list(y), sc["yours"], height=0.55, color="#8b5cf6", label="You")
        ax.set_yticks(list(y)); ax.set_yticklabels(sc["themes"], fontsize=6.5)
        ax.tick_params(labelsize=6.5)
        ax.spines[["top", "right"]].set_visible(False)
        story.append(_chart_image(fig, height_mm=68))

    if data.get("methodology_note"):
        story.append(Paragraph(data["methodology_note"], s["WHY"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"<i>{DISCLAIMER}</i>", s["WHY"]))
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
