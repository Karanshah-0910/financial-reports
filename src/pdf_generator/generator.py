"""
generator.py
------------
Builds a professional, fully-designed PDF report with:
  - Styled page backgrounds on every page (header bar, footer, light bg)
  - Cover page with key stats
  - Plain-English executive summary
  - Financial tables with color coding
  - 3D bar chart + 3D pie chart + margin trend line chart
  - Expense detail breakdown page
"""

import os
import io
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, Image as RLImage, KeepTogether
)
from reportlab.platypus.flowables import Flowable
from reportlab.graphics.shapes import Drawing, Rect, String, Circle, Line, Polygon

from .styles import (
    COLOR_NAVY, COLOR_ACCENT, COLOR_LIGHT_BLUE, COLOR_GREEN, COLOR_RED,
    COLOR_WHITE, COLOR_BLACK, COLOR_LIGHT_GRAY, COLOR_MID_GRAY,
    PAGE_MARGIN, SECTION_GAP, ROW_HEIGHT
)

PAGE_W, PAGE_H = letter


# ---------------------------------------------------------------------------
# Page background callbacks (drawn on canvas before flowables)
# ---------------------------------------------------------------------------
def _cover_background(canvas, doc):
    canvas.saveState()

    # Full navy background
    canvas.setFillColor(COLOR_NAVY)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # Diagonal decorative stripe
    canvas.setFillColor(colors.HexColor("#243554"))
    canvas.setStrokeColor(colors.HexColor("#243554"))
    p = canvas.beginPath()
    p.moveTo(0, PAGE_H * 0.42)
    p.lineTo(PAGE_W, PAGE_H * 0.52)
    p.lineTo(PAGE_W, PAGE_H * 0.48)
    p.lineTo(0, PAGE_H * 0.38)
    p.close()
    canvas.drawPath(p, fill=1, stroke=0)

    # Accent bottom bar
    canvas.setFillColor(COLOR_ACCENT)
    canvas.rect(0, 0, PAGE_W, 0.6 * inch, fill=1, stroke=0)

    # Bottom bar text
    canvas.setFillColor(COLOR_WHITE)
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(
        PAGE_W / 2, 0.22 * inch,
        "CONFIDENTIAL — For Authorized Recipients Only"
    )

    # Top thin accent line
    canvas.setFillColor(COLOR_ACCENT)
    canvas.rect(0, PAGE_H - 0.08 * inch, PAGE_W, 0.08 * inch, fill=1, stroke=0)

    canvas.restoreState()


def _page_background(canvas, doc):
    canvas.saveState()

    # Light blue-gray background
    canvas.setFillColor(colors.HexColor("#EEF2F7"))
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # White rounded content card
    canvas.setFillColor(colors.white)
    canvas.setStrokeColor(colors.HexColor("#CDD8E8"))
    canvas.setLineWidth(0.6)
    canvas.roundRect(
        0.45 * inch, 0.55 * inch,
        PAGE_W - 0.9 * inch, PAGE_H - 1.05 * inch,
        radius=6, fill=1, stroke=1
    )

    # Navy top header bar
    canvas.setFillColor(COLOR_NAVY)
    canvas.roundRect(
        0.45 * inch, PAGE_H - 0.65 * inch,
        PAGE_W - 0.9 * inch, 0.42 * inch,
        radius=6, fill=1, stroke=0
    )
    # Square off bottom of header (so it looks like a bar, not a pill)
    canvas.rect(
        0.45 * inch, PAGE_H - 0.65 * inch,
        PAGE_W - 0.9 * inch, 0.20 * inch,
        fill=1, stroke=0
    )

    # Header text
    canvas.setFillColor(COLOR_WHITE)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawString(0.65 * inch, PAGE_H - 0.45 * inch,
                      "CONFIDENTIAL FINANCIAL REPORT")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(PAGE_W - 0.65 * inch, PAGE_H - 0.45 * inch,
                           datetime.now().strftime("%B %Y"))

    # Accent left stripe
    canvas.setFillColor(COLOR_ACCENT)
    canvas.rect(0.45 * inch, 0.55 * inch, 0.04 * inch,
                PAGE_H - 1.05 * inch, fill=1, stroke=0)

    # Navy footer bar
    canvas.setFillColor(COLOR_NAVY)
    canvas.roundRect(
        0.45 * inch, 0.55 * inch,
        PAGE_W - 0.9 * inch, 0.3 * inch,
        radius=6, fill=1, stroke=0
    )
    canvas.rect(
        0.45 * inch, 0.70 * inch,
        PAGE_W - 0.9 * inch, 0.15 * inch,
        fill=1, stroke=0
    )

    # Footer text
    canvas.setFillColor(COLOR_WHITE)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawCentredString(PAGE_W / 2, 0.63 * inch,
                             f"Page {doc.page}   |   Financial Report   |   Confidential")

    canvas.restoreState()


# ---------------------------------------------------------------------------
# Section header with colored icon badge
# ---------------------------------------------------------------------------
def _section_header(story, title, icon_letter, subtitle, styles):
    """
    Draws a colored section header with an icon badge and subtitle.
    icon_letter: single character shown in the badge (e.g. '$', 'i', 'C')
    """
    # Icon badge + title in a table
    icon_cell = Table(
        [[Paragraph(f'<font color="white"><b>{icon_letter}</b></font>',
                    styles["icon_text"])]],
        colWidths=[0.35 * inch],
        rowHeights=[0.35 * inch],
    )
    icon_cell.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), COLOR_ACCENT),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("ROUNDEDCORNERS", [4]),
    ]))

    header_row = Table(
        [[icon_cell, Paragraph(title, styles["section_heading"])]],
        colWidths=[0.45 * inch, 6.3 * inch],
        rowHeights=[0.38 * inch],
    )
    header_row.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",(0, 0), (-1, -1), 0),
        ("TOPPADDING",  (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
    ]))

    story.append(header_row)
    story.append(HRFlowable(width="100%", thickness=1.5,
                            color=COLOR_ACCENT, spaceAfter=4))
    if subtitle:
        story.append(Paragraph(subtitle, styles["section_subtitle"]))
    story.append(Spacer(1, 6))


# ---------------------------------------------------------------------------
# Plain-English term explainer box
# ---------------------------------------------------------------------------
def _term_box(story, terms: dict, styles):
    """
    Renders a light blue box explaining financial terms in plain English.
    terms = {"Term": "Plain-English explanation", ...}
    """
    rows = []
    for term, explanation in terms.items():
        rows.append([
            Paragraph(f"<b>{term}</b>", styles["term_label"]),
            Paragraph(explanation, styles["term_body"]),
        ])

    t = Table(rows, colWidths=[1.4 * inch, 5.35 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#EAF4FB")),
        ("BOX",           (0, 0), (-1, -1), 0.8, COLOR_ACCENT),
        ("LINEAFTER",     (0, 0), (0, -1),  0.6, COLOR_ACCENT),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t)
    story.append(Spacer(1, 8))


# ---------------------------------------------------------------------------
# Text styles
# ---------------------------------------------------------------------------
def _make_styles() -> dict:
    return {
        # Cover
        "cover_eyebrow": ParagraphStyle(
            "cover_eyebrow", fontName="Helvetica", fontSize=11,
            textColor=COLOR_ACCENT, alignment=TA_CENTER, spaceAfter=6,
        ),
        "cover_title": ParagraphStyle(
            "cover_title", fontName="Helvetica-Bold", fontSize=30,
            textColor=COLOR_WHITE, leading=36, alignment=TA_CENTER,
        ),
        "cover_period": ParagraphStyle(
            "cover_period", fontName="Helvetica", fontSize=14,
            textColor=colors.HexColor("#A8C4D8"), alignment=TA_CENTER, spaceAfter=4,
        ),
        "cover_stat_label": ParagraphStyle(
            "cover_stat_label", fontName="Helvetica", fontSize=8.5,
            textColor=colors.HexColor("#A8C4D8"), alignment=TA_CENTER, leading=12,
        ),
        "cover_stat_value": ParagraphStyle(
            "cover_stat_value", fontName="Helvetica-Bold", fontSize=20,
            textColor=COLOR_WHITE, alignment=TA_CENTER, leading=24,
        ),
        "cover_prepared": ParagraphStyle(
            "cover_prepared", fontName="Helvetica", fontSize=9,
            textColor=colors.HexColor("#7A9BB5"), alignment=TA_CENTER,
        ),
        # Section
        "section_heading": ParagraphStyle(
            "section_heading", fontName="Helvetica-Bold", fontSize=13,
            textColor=COLOR_NAVY, leading=18,
        ),
        "section_subtitle": ParagraphStyle(
            "section_subtitle", fontName="Helvetica", fontSize=9.5,
            textColor=colors.HexColor("#555555"), leading=14, spaceAfter=6,
            italics=True,
        ),
        "icon_text": ParagraphStyle(
            "icon_text", fontName="Helvetica-Bold", fontSize=13,
            textColor=COLOR_WHITE, alignment=TA_CENTER,
        ),
        # Body
        "body": ParagraphStyle(
            "body", fontName="Helvetica", fontSize=10,
            textColor=COLOR_BLACK, leading=15, spaceAfter=4,
        ),
        "body_bold": ParagraphStyle(
            "body_bold", fontName="Helvetica-Bold", fontSize=10,
            textColor=COLOR_NAVY, leading=16, spaceAfter=2,
        ),
        "callout": ParagraphStyle(
            "callout", fontName="Helvetica", fontSize=9.5,
            textColor=colors.HexColor("#2C3E50"), leading=14,
            leftIndent=12, spaceAfter=3,
        ),
        # Table
        "table_header": ParagraphStyle(
            "table_header", fontName="Helvetica-Bold", fontSize=9,
            textColor=COLOR_WHITE, alignment=TA_CENTER,
        ),
        "table_label": ParagraphStyle(
            "table_label", fontName="Helvetica", fontSize=9, textColor=COLOR_BLACK,
        ),
        "table_label_bold": ParagraphStyle(
            "table_label_bold", fontName="Helvetica-Bold", fontSize=9, textColor=COLOR_NAVY,
        ),
        "table_number": ParagraphStyle(
            "table_number", fontName="Helvetica", fontSize=9,
            textColor=COLOR_BLACK, alignment=TA_RIGHT,
        ),
        "table_number_bold": ParagraphStyle(
            "table_number_bold", fontName="Helvetica-Bold", fontSize=9,
            textColor=COLOR_NAVY, alignment=TA_RIGHT,
        ),
        # Term explainer
        "term_label": ParagraphStyle(
            "term_label", fontName="Helvetica-Bold", fontSize=8.5,
            textColor=COLOR_NAVY, leading=12,
        ),
        "term_body": ParagraphStyle(
            "term_body", fontName="Helvetica", fontSize=8.5,
            textColor=colors.HexColor("#333333"), leading=12,
        ),
        # Footer / misc
        "footer": ParagraphStyle(
            "footer", fontName="Helvetica", fontSize=8,
            textColor=colors.HexColor("#7A9BB5"), alignment=TA_CENTER,
        ),
        "chart_caption": ParagraphStyle(
            "chart_caption", fontName="Helvetica", fontSize=8.5,
            textColor=colors.HexColor("#555555"), alignment=TA_CENTER,
            leading=12, spaceBefore=4,
        ),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _fmt(value, is_pct=False) -> str:
    if is_pct:
        return f"{value:.1f}%"
    if value < 0:
        return f"(${abs(value):,.0f})"
    return f"${value:,.0f}"


def _mom_text(value) -> str:
    if value != value:
        return "-"
    if value > 0:
        return f'<font color="#27AE60">Up {abs(value):.1f}%</font>'
    elif value < 0:
        return f'<font color="#E74C3C">Down {abs(value):.1f}%</font>'
    return "Flat"


def _embed_chart(buf: io.BytesIO, width_inch: float, height_inch: float) -> RLImage:
    """Wrap a BytesIO image buffer as a ReportLab Image flowable."""
    return RLImage(buf, width=width_inch * inch, height=height_inch * inch)


# ---------------------------------------------------------------------------
# Page 1: Cover
# ---------------------------------------------------------------------------
def _build_cover(story, analysis, styles):
    summary   = analysis["summary_df"]
    latest    = analysis["latest_month"]
    business  = analysis["business_name"]
    all_months = analysis["all_months"]
    generated = datetime.now().strftime("%B %d, %Y")

    revenue    = float(summary.loc["Total Revenue",  latest])
    net_profit = float(summary.loc["Net Profit",     latest])
    net_margin = float(summary.loc["Net Margin %",   latest])

    profit_color = "#27AE60" if net_profit >= 0 else "#E74C3C"

    story.append(Spacer(1, 1.7 * inch))
    story.append(Paragraph("MONTHLY FINANCIAL REPORT", styles["cover_eyebrow"]))
    story.append(Spacer(1, 0.12 * inch))
    story.append(Paragraph(business, styles["cover_title"]))
    story.append(Spacer(1, 0.18 * inch))
    story.append(Paragraph(
        f"{all_months[0]}  to  {latest}", styles["cover_period"]
    ))
    story.append(Spacer(1, 0.45 * inch))

    # Key stats panel
    stats = Table(
        [
            [
                Paragraph("TOTAL REVENUE",  styles["cover_stat_label"]),
                Paragraph("NET PROFIT",     styles["cover_stat_label"]),
                Paragraph("NET MARGIN",     styles["cover_stat_label"]),
            ],
            [
                Paragraph(f"${revenue:,.0f}", styles["cover_stat_value"]),
                Paragraph(
                    f'<font color="{profit_color}">'
                    f'{"+" if net_profit >= 0 else ""}${abs(net_profit):,.0f}</font>',
                    styles["cover_stat_value"]
                ),
                Paragraph(
                    f'<font color="{profit_color}">{net_margin:.1f}%</font>',
                    styles["cover_stat_value"]
                ),
            ],
        ],
        colWidths=[2.33 * inch, 2.33 * inch, 2.33 * inch],
        rowHeights=[0.28 * inch, 0.55 * inch],
    )
    stats.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#243554")),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LINEAFTER",     (0, 0), (1, -1), 0.8, COLOR_ACCENT),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("BOX",           (0, 0), (-1, -1), 1, COLOR_ACCENT),
    ]))
    story.append(stats)
    story.append(Spacer(1, 0.35 * inch))
    story.append(Paragraph(
        f"Prepared on {generated}  |  Confidential",
        styles["cover_prepared"]
    ))
    story.append(PageBreak())


# ---------------------------------------------------------------------------
# Page 2: Executive Summary
# ---------------------------------------------------------------------------
def _build_insights_section(story, insights_text, styles):
    _section_header(
        story, "Executive Summary", "i",
        subtitle=(
            "A plain-English overview of your business performance this month. "
            "No accounting jargon — just the most important things you need to know."
        ),
        styles=styles
    )

    for line in insights_text.strip().split("\n"):
        line = line.strip()
        if not line:
            story.append(Spacer(1, 4))
            continue
        if line[0].isdigit() and ". " in line[:4]:
            story.append(Spacer(1, 8))
            story.append(Paragraph(line, styles["body_bold"]))
        elif line.startswith("-"):
            story.append(Paragraph(
                f'<font color="#2E86AB">&#9656;</font> {line[1:].strip()}',
                styles["callout"]
            ))
        else:
            story.append(Paragraph(line, styles["body"]))

    story.append(Spacer(1, SECTION_GAP))


# ---------------------------------------------------------------------------
# Page 3: Financial Summary Tables
# ---------------------------------------------------------------------------
def _build_summary_table(story, analysis, styles):
    summary = analysis["summary_df"]
    months  = analysis["all_months"]
    mom     = analysis["mom_df"]

    _section_header(
        story, "Financial Summary", "$",
        subtitle=(
            "Key financial totals for each month. "
            "Green = growing. Red = declining. "
            "Scroll to the next section for what these numbers mean in plain English."
        ),
        styles=styles
    )

    # Plain-English term explainer
    _term_box(story, {
        "Gross Profit":  "Revenue minus the direct cost of your products/services. "
                         "This is what's left before paying for rent, staff, and other overhead.",
        "Net Profit":    "What the business actually keeps after ALL expenses are paid. "
                         "This is the bottom line — the real measure of profitability.",
        "Gross Margin":  "Gross Profit as a % of Revenue. Higher = more efficient. "
                         "E.g. 45% means you keep 45 cents of every dollar of sales before overhead.",
        "Net Margin":    "Net Profit as a % of Revenue. E.g. 10% means you keep "
                         "10 cents of every dollar after all costs.",
    }, styles)

    label_w = 2.2 * inch
    month_w = (7.0 * inch - label_w) / len(months)
    BOLD_ROWS = {"Gross Profit", "Net Profit"}
    PCT_ROWS  = {"Gross Margin %", "Net Margin %"}

    header_row = [Paragraph("", styles["table_header"])]
    for m in months:
        header_row.append(Paragraph(m, styles["table_header"]))
    table_data = [header_row]
    row_styles = []

    for i, metric in enumerate(summary.index):
        is_bold = metric in BOLD_ROWS
        is_pct  = metric in PCT_ROWS
        row = [Paragraph(metric,
                         styles["table_label_bold"] if is_bold else styles["table_label"])]
        for m in months:
            val = float(summary.loc[metric, m])
            row.append(Paragraph(_fmt(val, is_pct),
                                 styles["table_number_bold"] if is_bold else styles["table_number"]))
        table_data.append(row)
        bg = COLOR_LIGHT_BLUE if i % 2 == 0 else COLOR_WHITE
        row_styles.append(("BACKGROUND", (0, i + 1), (-1, i + 1), bg))
        if is_bold:
            row_styles.append(("LINEABOVE", (0, i + 1), (-1, i + 1), 1, COLOR_ACCENT))

    t = Table(table_data, colWidths=[label_w] + [month_w] * len(months), rowHeights=ROW_HEIGHT)
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), COLOR_NAVY),
        ("GRID",         (0, 0), (-1, -1), 0.5, COLOR_MID_GRAY),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ] + row_styles))
    story.append(t)
    story.append(Spacer(1, SECTION_GAP))

    # MoM changes table
    story.append(Paragraph(
        "Month-over-Month Changes — How did we do vs last month?",
        styles["body_bold"]
    ))
    story.append(Spacer(1, 6))

    mom_header = [Paragraph("Metric", styles["table_header"])]
    for m in months:
        mom_header.append(Paragraph(m, styles["table_header"]))
    mom_data   = [mom_header]
    mom_styles = []

    for i, metric in enumerate(mom.index):
        row = [Paragraph(metric, styles["table_label"])]
        for m in months:
            val  = float(mom.loc[metric, m]) if mom.loc[metric, m] == mom.loc[metric, m] else float("nan")
            text = _mom_text(val)
            row.append(Paragraph(text, styles["table_number"]))
        mom_data.append(row)
        bg = COLOR_LIGHT_BLUE if i % 2 == 0 else COLOR_WHITE
        mom_styles.append(("BACKGROUND", (0, i + 1), (-1, i + 1), bg))

    mom_table = Table(mom_data, colWidths=[label_w] + [month_w] * len(months), rowHeights=ROW_HEIGHT)
    mom_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), COLOR_NAVY),
        ("GRID",         (0, 0), (-1, -1), 0.5, COLOR_MID_GRAY),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ] + mom_styles))
    story.append(mom_table)


# ---------------------------------------------------------------------------
# Page 4: Charts
# ---------------------------------------------------------------------------
def _build_charts_section(story, analysis, styles):
    from .charts_matplotlib import (
        create_revenue_3d_bar_chart,
        create_expense_3d_pie_chart,
        create_margin_trend_chart,
    )

    story.append(PageBreak())
    _section_header(
        story, "Visual Overview", "C",
        subtitle=(
            "Charts make the numbers easier to understand at a glance. "
            "Each chart tells a different part of your business story."
        ),
        styles=styles
    )

    # 3D Bar Chart
    story.append(Paragraph(
        "Revenue Trend — 3 Months", styles["body_bold"]
    ))
    story.append(Paragraph(
        "This chart shows your total income (Revenue), what's left after product costs "
        "(Gross Profit), and what the business actually kept (Net Profit) — side by side "
        "for each month. Taller bars = more money.",
        styles["callout"]
    ))
    story.append(Spacer(1, 6))
    try:
        bar_buf = create_revenue_3d_bar_chart(analysis)
        story.append(_embed_chart(bar_buf, 7.0, 4.0))
    except Exception as e:
        story.append(Paragraph(f"Chart unavailable: {e}", styles["body"]))

    story.append(Spacer(1, 0.25 * inch))

    # Margin Trend Line Chart
    story.append(Paragraph(
        "Profit Margin Trend", styles["body_bold"]
    ))
    story.append(Paragraph(
        "Margins show efficiency — how much of every dollar you earn actually turns into profit. "
        "A rising line is great news. A falling line means costs are growing faster than revenue.",
        styles["callout"]
    ))
    story.append(Spacer(1, 6))
    try:
        margin_buf = create_margin_trend_chart(analysis)
        story.append(_embed_chart(margin_buf, 7.0, 2.8))
    except Exception as e:
        story.append(Paragraph(f"Chart unavailable: {e}", styles["body"]))

    # Expense Pie Chart — on a new page
    story.append(PageBreak())
    _section_header(
        story, "Expense Breakdown", "%",
        subtitle=(
            "Where is the money going? This chart shows every expense as a slice of the "
            "total spending pie. Bigger slices = bigger costs. Use this to spot where "
            "you might be able to cut back."
        ),
        styles=styles
    )

    try:
        pie_buf = create_expense_3d_pie_chart(analysis)
        story.append(_embed_chart(pie_buf, 7.0, 4.5))
    except Exception as e:
        story.append(Paragraph(f"Chart unavailable: {e}", styles["body"]))


# ---------------------------------------------------------------------------
# Page 6: Expense Detail Table
# ---------------------------------------------------------------------------
def _build_expense_detail(story, analysis, styles):
    story.append(PageBreak())
    latest = analysis["latest_month"]
    detail = analysis["detail_df"]

    _section_header(
        story, f"Expense Detail - {latest}", "#",
        subtitle=(
            "A full line-by-line breakdown of every expense this month, "
            "ranked by size. Use this to track individual cost categories over time."
        ),
        styles=styles
    )

    EXPENSE_LINES = [
        "Rent", "Rent & Office", "Payroll", "Utilities",
        "Marketing & Advertising", "Software & Subscriptions",
        "Shipping & Postage", "Professional Fees",
        "Travel & Entertainment", "Cost of Services", "Miscellaneous",
    ]
    SKIP = {
        "Sales - In Store", "Sales - Online", "Sales - Wholesale",
        "Cost of Goods Sold", "Consulting Fees - Strategy",
        "Consulting Fees - Operations", "Retainer Income",
    }

    # Collect and sort by value descending
    expenses = []
    seen = set()
    for item in EXPENSE_LINES:
        if item in detail.index:
            val = abs(float(detail.loc[item, latest]))
            if val > 0:
                expenses.append((item, val))
                seen.add(item)

    for idx in detail.index:
        if idx not in seen and idx not in EXPENSE_LINES and idx not in SKIP:
            val = abs(float(detail.loc[idx, latest]))
            if val > 0:
                expenses.append((idx, val))

    expenses.sort(key=lambda x: x[1], reverse=True)
    total_exp = sum(v for _, v in expenses)

    rows = [[
        Paragraph("Expense Category", styles["table_header"]),
        Paragraph("Amount", styles["table_header"]),
        Paragraph("% of Total", styles["table_header"]),
        Paragraph("Plain-English Note", styles["table_header"]),
    ]]

    NOTES = {
        "Payroll":                  "Staff wages & salaries",
        "Rent":                     "Office / store lease",
        "Rent & Office":            "Office / store lease",
        "Cost of Goods Sold":       "Direct product costs",
        "Cost of Services":         "Direct service delivery costs",
        "Marketing & Advertising":  "Ads, promotions, campaigns",
        "Utilities":                "Electric, water, internet",
        "Software & Subscriptions": "Apps & online tools",
        "Shipping & Postage":       "Delivery & postage costs",
        "Professional Fees":        "Accountant, lawyer, consultants",
        "Travel & Entertainment":   "Business travel & client meals",
        "Miscellaneous":            "Other small expenses",
    }

    row_styles = []
    for i, (label, val) in enumerate(expenses):
        pct  = (val / total_exp * 100) if total_exp else 0
        note = NOTES.get(label, "")
        rows.append([
            Paragraph(label, styles["table_label"]),
            Paragraph(f"${val:,.0f}", styles["table_number"]),
            Paragraph(f"{pct:.1f}%", styles["table_number"]),
            Paragraph(note, styles["table_label"]),
        ])
        bg = COLOR_LIGHT_BLUE if i % 2 == 0 else COLOR_WHITE
        row_styles.append(("BACKGROUND", (0, i + 1), (-1, i + 1), bg))

    # Total row
    rows.append([
        Paragraph("TOTAL EXPENSES", styles["table_label_bold"]),
        Paragraph(f"${total_exp:,.0f}", styles["table_number_bold"]),
        Paragraph("100.0%", styles["table_number_bold"]),
        Paragraph("", styles["table_label"]),
    ])
    total_row_idx = len(rows) - 1
    row_styles += [
        ("LINEABOVE",  (0, total_row_idx), (-1, total_row_idx), 1.5, COLOR_NAVY),
        ("BACKGROUND", (0, total_row_idx), (-1, total_row_idx), colors.HexColor("#D6E8F5")),
    ]

    col_widths = [2.2 * inch, 1.1 * inch, 1.0 * inch, 2.45 * inch]
    exp_table  = Table(rows, colWidths=col_widths, rowHeights=ROW_HEIGHT)
    exp_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), COLOR_NAVY),
        ("GRID",         (0, 0), (-1, -1), 0.5, COLOR_MID_GRAY),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ] + row_styles))
    story.append(exp_table)
    story.append(Spacer(1, SECTION_GAP))

    # --- Top 5 Expenses ---
    top_expenses = analysis.get("top_expenses", [])
    if top_expenses:
        story.append(Paragraph("Top 5 Expense Categories", styles["body_bold"]))
        story.append(Paragraph(
            "The five biggest costs this month, ranked by size. "
            "Focus here first when looking for savings.",
            styles["callout"]
        ))
        story.append(Spacer(1, 6))

        top_rows = [[
            Paragraph("Rank", styles["table_header"]),
            Paragraph("Category", styles["table_header"]),
            Paragraph("Amount", styles["table_header"]),
            Paragraph("% of Total Expenses", styles["table_header"]),
        ]]
        for i, exp in enumerate(top_expenses):
            bg = COLOR_LIGHT_BLUE if i % 2 == 0 else COLOR_WHITE
            top_rows.append([
                Paragraph(f"#{i+1}", styles["table_number"]),
                Paragraph(exp["name"], styles["table_label"]),
                Paragraph(f"${exp['amount']:,.0f}", styles["table_number"]),
                Paragraph(f"{exp['pct']}%", styles["table_number"]),
            ])

        top_table = Table(top_rows,
                          colWidths=[0.5*inch, 3.0*inch, 1.5*inch, 1.75*inch],
                          rowHeights=ROW_HEIGHT)
        top_table.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0), COLOR_NAVY),
            ("GRID",         (0, 0), (-1, -1), 0.5, COLOR_MID_GRAY),
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ] + [("BACKGROUND", (0, i+1), (-1, i+1),
              COLOR_LIGHT_BLUE if i % 2 == 0 else COLOR_WHITE)
             for i in range(len(top_expenses))]))
        story.append(top_table)
        story.append(Spacer(1, SECTION_GAP))

    # --- Attention Flags ---
    flags = analysis.get("attention_flags", [])
    if flags:
        story.append(Paragraph("Items That Need Attention", styles["body_bold"]))
        story.append(Paragraph(
            "These line items changed by more than 20% compared to last month. "
            "They are not necessarily problems — but they are worth a look.",
            styles["callout"]
        ))
        story.append(Spacer(1, 6))

        flag_rows = [[
            Paragraph("Line Item", styles["table_header"]),
            Paragraph("Last Month", styles["table_header"]),
            Paragraph("This Month", styles["table_header"]),
            Paragraph("Change", styles["table_header"]),
            Paragraph("Direction", styles["table_header"]),
        ]]

        for i, f in enumerate(flags[:8]):
            is_up  = f["direction"] == "up"
            color  = "#27AE60" if is_up else "#E74C3C"
            arrow  = "Up" if is_up else "Down"
            flag_rows.append([
                Paragraph(f["item"], styles["table_label"]),
                Paragraph(f"${f['prev']:,.0f}", styles["table_number"]),
                Paragraph(f"${f['current']:,.0f}", styles["table_number"]),
                Paragraph(
                    f'<font color="{color}"><b>{abs(f["change_pct"]):.1f}%</b></font>',
                    styles["table_number"]
                ),
                Paragraph(
                    f'<font color="{color}"><b>{arrow}</b></font>',
                    styles["table_number"]
                ),
            ])

        flag_table = Table(flag_rows,
                           colWidths=[2.2*inch, 1.2*inch, 1.2*inch, 1.0*inch, 1.15*inch],
                           rowHeights=ROW_HEIGHT)
        flag_table.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor("#7D3C98")),
            ("GRID",         (0, 0), (-1, -1), 0.5, COLOR_MID_GRAY),
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ] + [("BACKGROUND", (0, i+1), (-1, i+1),
              colors.HexColor("#F9F0FF") if i % 2 == 0 else COLOR_WHITE)
             for i in range(min(len(flags), 8))]))
        story.append(flag_table)

    # --- Expense Growth Verdict ---
    growth = analysis.get("expense_growth", {})
    if growth and growth.get("verdict"):
        story.append(Spacer(1, SECTION_GAP))
        verdict = growth["verdict"]
        rev_g   = growth.get("revenue_growth_pct", 0)
        exp_g   = growth.get("expense_growth_pct", 0)
        bg_color = colors.HexColor("#EAFAF1") if "Healthy" in verdict else colors.HexColor("#FEF9E7")
        border_color = COLOR_GREEN if "Healthy" in verdict else colors.HexColor("#F39C12")

        growth_box = Table(
            [[
                Paragraph(
                    f'<b>Expense Growth Trend:</b> {verdict}<br/>'
                    f'Revenue grew <b>{rev_g:+.1f}%</b> vs expenses grew <b>{exp_g:+.1f}%</b> '
                    f'(comparing {analysis["all_months"][0]} to {analysis["latest_month"]})',
                    styles["body"]
                )
            ]],
            colWidths=[6.75 * inch]
        )
        growth_box.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, -1), bg_color),
            ("BOX",         (0, 0), (-1, -1), 1.5, border_color),
            ("TOPPADDING",  (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING",(0, 0), (-1, -1), 12),
        ]))
        story.append(growth_box)


# ---------------------------------------------------------------------------
# Balance Sheet page
# ---------------------------------------------------------------------------
def _build_balance_sheet(story, bs_analysis: dict, styles):
    story.append(PageBreak())

    _section_header(
        story, "Balance Sheet", "B",
        subtitle=(
            "A snapshot of the business's financial health on a single day. "
            "Think of it as a photograph: what the business OWNS (Assets), "
            "what it OWES (Liabilities), and what belongs to the owner (Equity)."
        ),
        styles=styles
    )

    a = bs_analysis

    # Health ratios explained in plain English
    _term_box(story, {
        "Current Ratio":   f"{a['current_ratio']}  —  Can we pay our short-term bills? "
                           f"Above 1.5 is healthy. Below 1.0 means potential cash flow risk.",
        "Quick Ratio":     f"{a['quick_ratio']}  —  Can we pay bills using only cash and "
                           f"money owed to us (no inventory)? Above 1.0 is safe.",
        "Debt-to-Equity":  f"{a['debt_to_equity']}  —  For every $1 the owner has invested, "
                           f"how much is owed to lenders? Below 1.0 is conservative.",
        "Working Capital": f"${a['working_capital']:,.0f}  —  Current Assets minus Current "
                           f"Liabilities. This is the day-to-day cash cushion. Positive = good.",
    }, styles)

    # Health score row
    COLOR_MAP = {"green": "#27AE60", "yellow": "#F39C12", "red": "#E74C3C", "grey": "#95A5A6"}
    LABEL_MAP = {"green": "HEALTHY", "yellow": "WATCH", "red": "ATTENTION", "grey": "N/A"}

    health = a["health"]
    score_data = [[
        _health_badge(metric, health[key], COLOR_MAP, LABEL_MAP, styles)
        for metric, key in [
            ("Current Ratio",   "current_ratio"),
            ("Quick Ratio",     "quick_ratio"),
            ("Debt-to-Equity",  "debt_to_equity"),
            ("Working Capital", "working_capital"),
        ]
    ]]
    score_table = Table(score_data, colWidths=[1.75 * inch] * 4)
    score_table.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 10))

    # Main balance sheet table
    rows = []

    def section_row(title, color):
        return [
            Paragraph(f'<font color="white"><b>{title}</b></font>', styles["table_header"]),
            Paragraph("", styles["table_header"]),
        ]

    def item_row(label, value, bold=False, indent=True):
        prefix = "    " if indent else ""
        lstyle = styles["table_label_bold"] if bold else styles["table_label"]
        nstyle = styles["table_number_bold"] if bold else styles["table_number"]
        return [
            Paragraph(f"{prefix}{label}", lstyle),
            Paragraph(f"${value:,.0f}", nstyle),
        ]

    row_styles = []
    i = 0

    def add_section(title, bg_color, items, subtotal_label, subtotal_value):
        nonlocal i
        rows.append(section_row(title, bg_color))
        row_styles.append(("BACKGROUND", (0, i), (-1, i), bg_color))
        i += 1
        for label, val in items.items():
            rows.append(item_row(label, val))
            row_styles.append(("BACKGROUND", (0, i), (-1, i),
                               COLOR_LIGHT_BLUE if i % 2 == 0 else COLOR_WHITE))
            i += 1
        rows.append(item_row(subtotal_label, subtotal_value, bold=True, indent=False))
        row_styles.append(("BACKGROUND",  (0, i), (-1, i), colors.HexColor("#D6E8F5")))
        row_styles.append(("LINEABOVE",   (0, i), (-1, i), 1, COLOR_ACCENT))
        i += 1

    # ASSETS
    add_section("CURRENT ASSETS — Cash, inventory, and money owed to us",
                COLOR_NAVY, a["current_assets"],
                "Total Current Assets", a["total_current_assets"])

    if a["fixed_assets"]:
        add_section("FIXED ASSETS — Equipment, furniture, and property",
                    colors.HexColor("#2E5A8E"), a["fixed_assets"],
                    "Total Fixed Assets", a["total_fixed_assets"])

    if a["other_assets"]:
        add_section("OTHER ASSETS — Deposits and other long-term items",
                    colors.HexColor("#2E5A8E"), a["other_assets"],
                    "Total Other Assets", a["total_other_assets"])

    rows.append([
        Paragraph("<b>TOTAL ASSETS</b>", styles["table_label_bold"]),
        Paragraph(f"<b>${a['total_assets']:,.0f}</b>", styles["table_number_bold"]),
    ])
    row_styles.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#1B2A4A")))
    row_styles.append(("TEXTCOLOR",  (0, i), (-1, i), COLOR_WHITE))
    i += 1

    # LIABILITIES
    add_section("CURRENT LIABILITIES — Bills due within the next 12 months",
                colors.HexColor("#8B0000"), a["current_liabilities"],
                "Total Current Liabilities", a["total_current_liabilities"])

    if a["long_term_liabilities"]:
        add_section("LONG-TERM LIABILITIES — Loans due beyond 12 months",
                    colors.HexColor("#A52A2A"), a["long_term_liabilities"],
                    "Total Long-term Liabilities", a["total_long_term_liabilities"])

    rows.append([
        Paragraph("<b>TOTAL LIABILITIES</b>", styles["table_label_bold"]),
        Paragraph(f"<b>${a['total_liabilities']:,.0f}</b>", styles["table_number_bold"]),
    ])
    row_styles.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#8B0000")))
    row_styles.append(("TEXTCOLOR",  (0, i), (-1, i), COLOR_WHITE))
    i += 1

    # EQUITY
    add_section("EQUITY — What belongs to the owner after all debts",
                colors.HexColor("#1A5276"), a["equity"],
                "Total Equity", a["total_equity"])

    rows.append([
        Paragraph("<b>TOTAL LIABILITIES + EQUITY</b>", styles["table_label_bold"]),
        Paragraph(f"<b>${a['total_liabilities'] + a['total_equity']:,.0f}</b>",
                  styles["table_number_bold"]),
    ])
    row_styles.append(("BACKGROUND", (0, i), (-1, i), COLOR_ACCENT))
    row_styles.append(("TEXTCOLOR",  (0, i), (-1, i), COLOR_WHITE))

    col_widths = [5.5 * inch, 1.75 * inch]
    bs_table   = Table(rows, colWidths=col_widths, rowHeights=ROW_HEIGHT)
    bs_table.setStyle(TableStyle([
        ("GRID",         (0, 0), (-1, -1), 0.4, COLOR_MID_GRAY),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ] + row_styles))
    story.append(bs_table)


# ---------------------------------------------------------------------------
# Cash Flow page
# ---------------------------------------------------------------------------
def _build_cash_flow(story, cf: dict, styles):
    """
    Builds a full Cash Flow page in the PDF.
    cf : output of analyze_cash_flow() from cash_flow_analyzer.py
    """
    story.append(PageBreak())

    status_word = "POSITIVE" if cf["is_cash_positive"] else "NEGATIVE"
    _section_header(
        story, "Cash Flow Statement", "F",
        subtitle=(
            f"Cash flow answers the most important question in business: "
            f"'Is real money coming in faster than it's going out?' "
            f"Status this month: Cash Flow {status_word}."
        ),
        styles=styles
    )

    # Plain-English explainer box
    _term_box(story, {
        "Operating CF":   "Cash generated by the core business (not counting investments or loans). "
                          "This is the #1 health metric. Positive means the business funds itself.",
        "Free Cash Flow": "Operating Cash Flow minus money spent on equipment. "
                          "Positive = self-funding growth. Negative = needs outside money to grow.",
        "Cash Runway":    f"{cf['cash_runway_months']} months  —  How long the business can survive "
                          f"on current cash if revenue stopped. Above 6 months = comfortable.",
        "Burn Rate":      f"${cf['monthly_burn_rate']:,.0f}/month  —  Monthly operating costs. "
                          f"Divide cash balance by this to get runway.",
    }, styles)

    # Health badges (4 metrics)
    COLOR_MAP = {"green": "#27AE60", "yellow": "#F39C12", "red": "#E74C3C", "grey": "#95A5A6"}
    LABEL_MAP = {"green": "HEALTHY", "yellow": "WATCH",   "red": "ATTENTION", "grey": "N/A"}

    health     = cf["health"]
    badge_data = [[
        _health_badge("Operating CF",   health["operating_cash_flow"],   COLOR_MAP, LABEL_MAP, styles),
        _health_badge("Free Cash Flow", health["free_cash_flow"],        COLOR_MAP, LABEL_MAP, styles),
        _health_badge("Cash Runway",    health["cash_runway"],           COLOR_MAP, LABEL_MAP, styles),
        _health_badge("Cash Cycle",     health["cash_conversion_cycle"], COLOR_MAP, LABEL_MAP, styles),
    ]]
    badge_table = Table(badge_data, colWidths=[1.75 * inch] * 4)
    badge_table.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
    ]))
    story.append(badge_table)
    story.append(Spacer(1, 8))

    # -------------------------------------------------------------------
    # Three-section cash flow statement table
    # -------------------------------------------------------------------
    def cf_row(label, value, bold=False, indent=True, highlight=False):
        prefix = "    " if indent else ""
        if value is None:
            val_text = "N/A"
        elif value >= 0:
            val_text = f"${value:,.0f}"
        else:
            val_text = f"(${abs(value):,.0f})"
        ls = styles["table_label_bold"] if bold else styles["table_label"]
        ns = styles["table_number_bold"] if bold else styles["table_number"]
        color_val = "#27AE60" if (value or 0) >= 0 else "#E74C3C"
        num_para  = (
            Paragraph(f'<font color="{color_val}"><b>{val_text}</b></font>', ns)
            if bold else
            Paragraph(val_text, ns)
        )
        return [Paragraph(f"{prefix}{label}", ls), num_para]

    def section_header_row(title, bg_color):
        return [
            Paragraph(f'<font color="white"><b>{title}</b></font>', styles["table_header"]),
            Paragraph("", styles["table_header"]),
        ]

    rows       = []
    row_styles = []
    i          = 0

    # ---- SECTION 1: Operating Activities ----
    rows.append(section_header_row(
        "SECTION 1: Operating Activities  —  Cash from running the business day-to-day",
        COLOR_NAVY
    ))
    row_styles.append(("BACKGROUND", (0, i), (-1, i), COLOR_NAVY))
    i += 1

    items_op = [
        ("Net Profit (from P&L)",         cf["net_profit"],         False),
        ("Add: Depreciation (non-cash)",   cf["depreciation"],       False),
        ("Change in Accounts Receivable",  -cf.get("ar_change_raw", 0) if "ar_change_raw" in cf else None, False),
        ("Operating Cash Flow",            cf["operating_cash_flow"], True),
    ]
    # Simplified: just show net profit, depreciation add-back, and OCF total
    for label, val, bold in [
        ("Net Profit (from P&L)",        cf["net_profit"],          False),
        ("Add: Depreciation (non-cash)", cf["depreciation"],        False),
        ("Adjustments for Working Capital (AR, AP, Inventory)", None, False),
        ("Operating Cash Flow",          cf["operating_cash_flow"], True),
    ]:
        rows.append(cf_row(label, val, bold=bold, indent=not bold))
        bg = COLOR_LIGHT_BLUE if i % 2 == 0 else COLOR_WHITE
        row_styles.append(("BACKGROUND", (0, i), (-1, i),
                           colors.HexColor("#D6E8F5") if bold else bg))
        if bold:
            row_styles.append(("LINEABOVE", (0, i), (-1, i), 1.2, COLOR_ACCENT))
        i += 1

    # ---- SECTION 2: Investing Activities ----
    rows.append(section_header_row(
        "SECTION 2: Investing Activities  —  Money spent on equipment and assets",
        colors.HexColor("#2E5A8E")
    ))
    row_styles.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#2E5A8E")))
    i += 1

    capex_val = -cf["capex"] if cf["capex"] > 0 else 0
    rows.append(cf_row("Capital Expenditures (equipment, property)", capex_val, indent=True))
    row_styles.append(("BACKGROUND", (0, i), (-1, i), COLOR_LIGHT_BLUE))
    i += 1

    rows.append(cf_row("Free Cash Flow  (Operating CF minus CapEx)", cf["free_cash_flow"], bold=True, indent=False))
    row_styles.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#D6E8F5")))
    row_styles.append(("LINEABOVE", (0, i), (-1, i), 1.2, COLOR_ACCENT))
    i += 1

    # ---- SECTION 3: Financing Activities ----
    rows.append(section_header_row(
        "SECTION 3: Financing Activities  —  Loans, repayments, and owner drawings",
        colors.HexColor("#1A5276")
    ))
    row_styles.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#1A5276")))
    i += 1

    rows.append(cf_row("Financing Cash Flow", cf["financing_cash_flow"], bold=True, indent=False))
    row_styles.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#D6E8F5")))
    row_styles.append(("LINEABOVE", (0, i), (-1, i), 1.2, COLOR_ACCENT))
    i += 1

    # ---- NET TOTAL ----
    rows.append([
        Paragraph("<b>NET CASH CHANGE THIS MONTH</b>", styles["table_label_bold"]),
        Paragraph(
            f'<font color="{"#27AE60" if cf["net_cash_change"] >= 0 else "#E74C3C"}">'
            f'<b>${cf["net_cash_change"]:,.0f}</b></font>',
            styles["table_number_bold"]
        ),
    ])
    row_styles += [
        ("BACKGROUND", (0, i), (-1, i), colors.HexColor("#1B2A4A")),
        ("TEXTCOLOR",  (0, i), (-1, i), COLOR_WHITE),
        ("LINEABOVE",  (0, i), (-1, i), 2, COLOR_ACCENT),
    ]
    i += 1

    cf_table = Table(rows, colWidths=[5.5 * inch, 1.75 * inch], rowHeights=ROW_HEIGHT)
    cf_table.setStyle(TableStyle([
        ("GRID",         (0, 0), (-1, -1), 0.4, COLOR_MID_GRAY),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ] + row_styles))
    story.append(cf_table)
    story.append(Spacer(1, SECTION_GAP))

    # -------------------------------------------------------------------
    # Cash Position summary box
    # -------------------------------------------------------------------
    runway_text = f"{cf['cash_runway_months']} months" if cf['cash_runway_months'] else "N/A"
    runway_color = (
        "#27AE60" if (cf['cash_runway_months'] or 0) >= 6 else
        "#F39C12" if (cf['cash_runway_months'] or 0) >= 3 else
        "#E74C3C"
    )
    ccc_val   = cf['cash_conversion_cycle']
    ccc_color = "#27AE60" if ccc_val <= 30 else "#F39C12" if ccc_val <= 60 else "#E74C3C"

    position_rows = [[
        Paragraph("Cash Position", styles["table_header"]),
        Paragraph("Value", styles["table_header"]),
        Paragraph("What It Means", styles["table_header"]),
    ]]
    pos_items = [
        ("Current Cash Balance",
         f"${cf['cash_balance']:,.0f}",
         "Total cash in the bank right now"),
        ("Monthly Burn Rate",
         f"${cf['monthly_burn_rate']:,.0f}",
         "Average monthly operating costs"),
        ("Cash Runway",
         f'<font color="{runway_color}"><b>{runway_text}</b></font>',
         "Months of expenses covered. Above 6 = comfortable | Below 3 = urgent"),
        ("Cash Conversion Cycle",
         f'<font color="{ccc_color}"><b>{ccc_val:.0f} days</b></font>',
         "Days between paying for inventory and collecting from customers. Lower = better"),
    ]

    for j, (label, val, note) in enumerate(pos_items):
        bg = COLOR_LIGHT_BLUE if j % 2 == 0 else COLOR_WHITE
        position_rows.append([
            Paragraph(label, styles["table_label"]),
            Paragraph(val,   styles["table_number"]),
            Paragraph(note,  styles["table_label"]),
        ])

    pos_table = Table(position_rows, colWidths=[1.9 * inch, 1.4 * inch, 4.45 * inch],
                      rowHeights=ROW_HEIGHT)
    pos_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), COLOR_NAVY),
        ("GRID",         (0, 0), (-1, -1), 0.5, COLOR_MID_GRAY),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ] + [("BACKGROUND", (0, j + 1), (-1, j + 1),
          COLOR_LIGHT_BLUE if j % 2 == 0 else COLOR_WHITE)
         for j in range(len(pos_items))]))
    story.append(pos_table)
    story.append(Spacer(1, SECTION_GAP))

    # -------------------------------------------------------------------
    # OCF Trend (month-by-month)
    # -------------------------------------------------------------------
    ocf_trend = cf.get("ocf_trend", [])
    if ocf_trend:
        story.append(Paragraph(
            "Operating Cash Flow Trend — Month by Month",
            styles["body_bold"]
        ))
        story.append(Paragraph(
            "Is the business generating more cash each month, or less? "
            "A consistent positive trend is the healthiest sign.",
            styles["callout"]
        ))
        story.append(Spacer(1, 6))

        trend_header = [[
            Paragraph("Month", styles["table_header"]),
            Paragraph("Est. Operating Cash Flow", styles["table_header"]),
            Paragraph("Direction", styles["table_header"]),
        ]]
        trend_rows = []
        prev_ocf = None
        for k, entry in enumerate(ocf_trend):
            ocf_val  = entry["ocf"]
            if prev_ocf is not None and prev_ocf != 0:
                direction = "Up" if ocf_val > prev_ocf else ("Down" if ocf_val < prev_ocf else "Flat")
                d_color   = "#27AE60" if ocf_val > prev_ocf else "#E74C3C"
                dir_para  = Paragraph(f'<font color="{d_color}"><b>{direction}</b></font>', styles["table_number"])
            else:
                dir_para = Paragraph("—", styles["table_number"])

            val_color = "#27AE60" if ocf_val >= 0 else "#E74C3C"
            trend_rows.append([
                Paragraph(entry["month"], styles["table_label"]),
                Paragraph(f'<font color="{val_color}">${ocf_val:,.0f}</font>', styles["table_number"]),
                dir_para,
            ])
            prev_ocf = ocf_val

        trend_data = trend_header + trend_rows
        trend_table = Table(trend_data, colWidths=[2.5 * inch, 2.5 * inch, 2.25 * inch],
                            rowHeights=ROW_HEIGHT)
        trend_table.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0), COLOR_NAVY),
            ("GRID",         (0, 0), (-1, -1), 0.5, COLOR_MID_GRAY),
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ] + [("BACKGROUND", (0, k + 1), (-1, k + 1),
              COLOR_LIGHT_BLUE if k % 2 == 0 else COLOR_WHITE)
             for k in range(len(trend_rows))]))
        story.append(trend_table)


def _health_badge(metric, health, color_map, label_map, styles):
    """A colored badge showing the health of one ratio."""
    color = color_map.get(health, "#95A5A6")
    label = label_map.get(health, "N/A")
    cell  = Table(
        [[Paragraph(f'<font color="white"><b>{metric}</b></font>', styles["footer"])],
         [Paragraph(f'<font color="white"><b>{label}</b></font>', styles["body_bold"])]],
        colWidths=[1.6 * inch],
        rowHeights=[0.22 * inch, 0.28 * inch],
    )
    cell.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor(color)),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ROUNDEDCORNERS", [4]),
    ]))
    return cell


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def generate_pdf(analysis: dict, insights: str, bs_analysis: dict = None,
                 cf_analysis: dict = None,
                 output_dir: str = "reports/output") -> str:
    os.makedirs(output_dir, exist_ok=True)

    business    = analysis["business_name"].replace(" ", "_")
    latest      = analysis["latest_month"].replace(" ", "_")
    filename    = f"{business}_{latest}_Report.pdf"
    output_path = os.path.join(output_dir, filename)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=0.65 * inch, rightMargin=0.65 * inch,
        topMargin=0.85 * inch,  bottomMargin=0.75 * inch,
    )

    styles = _make_styles()
    story  = []

    _build_cover(story, analysis, styles)
    _build_insights_section(story, insights, styles)
    _build_summary_table(story, analysis, styles)
    _build_charts_section(story, analysis, styles)
    _build_expense_detail(story, analysis, styles)
    if bs_analysis:
        _build_balance_sheet(story, bs_analysis, styles)
    if cf_analysis:
        _build_cash_flow(story, cf_analysis, styles)

    doc.build(
        story,
        onFirstPage=_cover_background,
        onLaterPages=_page_background,
    )
    return output_path
