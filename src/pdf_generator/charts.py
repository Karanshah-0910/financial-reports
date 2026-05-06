"""
charts.py
---------
Builds charts for the PDF report using ReportLab's built-in graphics.
No extra libraries needed.

Charts included:
  - Revenue trend bar chart (3 months)
  - Expense breakdown pie chart (latest month)
"""

from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics import renderPDF
from reportlab.lib import colors
from reportlab.lib.units import inch

from .styles import (
    COLOR_NAVY, COLOR_ACCENT, COLOR_LIGHT_BLUE,
    COLOR_GREEN, COLOR_WHITE, COLOR_BLACK, COLOR_MID_GRAY
)

# Chart color palette
CHART_COLORS = [
    colors.HexColor("#2E86AB"),
    colors.HexColor("#1B2A4A"),
    colors.HexColor("#27AE60"),
    colors.HexColor("#E67E22"),
    colors.HexColor("#8E44AD"),
    colors.HexColor("#E74C3C"),
    colors.HexColor("#16A085"),
    colors.HexColor("#F39C12"),
]


def build_revenue_bar_chart(analysis: dict) -> Drawing:
    """
    Three-bar chart showing Revenue, Gross Profit, and Net Profit
    for each month side by side.
    """
    summary = analysis["summary_df"]
    months  = analysis["all_months"]

    chart_width  = 6.8 * inch
    chart_height = 2.6 * inch

    drawing = Drawing(chart_width, chart_height)

    # Background
    drawing.add(Rect(
        0, 0, chart_width, chart_height,
        fillColor=colors.HexColor("#F8FAFB"),
        strokeColor=COLOR_MID_GRAY,
        strokeWidth=0.5
    ))

    # Title
    drawing.add(String(
        chart_width / 2, chart_height - 14,
        "Revenue, Gross Profit & Net Profit by Month",
        fontSize=10, fontName="Helvetica-Bold",
        fillColor=COLOR_NAVY, textAnchor="middle"
    ))

    # Build bar chart
    bc = VerticalBarChart()
    bc.x      = 60
    bc.y      = 30
    bc.width  = chart_width - 80
    bc.height = chart_height - 55

    # Data: rows = metric, cols = months
    revenue_row     = [float(summary.loc["Total Revenue",  m]) for m in months]
    gross_row       = [float(summary.loc["Gross Profit",   m]) for m in months]
    net_row         = [float(summary.loc["Net Profit",     m]) for m in months]

    bc.data         = [revenue_row, gross_row, net_row]
    bc.categoryAxis.categoryNames = [m.split(" ")[0][:3] + " " + m.split(" ")[-1] for m in months]

    # Bar colors
    bc.bars[0].fillColor = colors.HexColor("#2E86AB")
    bc.bars[1].fillColor = colors.HexColor("#27AE60")
    bc.bars[2].fillColor = colors.HexColor("#E67E22")

    bc.bars.strokeWidth = 0
    bc.barSpacing       = 2
    bc.groupSpacing     = 8

    # Axes
    bc.valueAxis.labelTextFormat    = lambda v: f"${v/1000:.0f}k" if v >= 1000 else f"${v:.0f}"
    bc.valueAxis.gridStrokeColor    = COLOR_MID_GRAY
    bc.valueAxis.gridStrokeWidth    = 0.3
    bc.valueAxis.strokeWidth        = 0.5
    bc.categoryAxis.strokeWidth     = 0.5
    bc.categoryAxis.labels.fontSize = 8
    bc.categoryAxis.labels.fontName = "Helvetica"
    bc.valueAxis.labels.fontSize    = 8
    bc.valueAxis.labels.fontName    = "Helvetica"

    drawing.add(bc)

    # Legend
    legend_items = [
        ("Revenue",      colors.HexColor("#2E86AB")),
        ("Gross Profit", colors.HexColor("#27AE60")),
        ("Net Profit",   colors.HexColor("#E67E22")),
    ]
    lx = 65
    ly = 8
    for label, color in legend_items:
        drawing.add(Rect(lx, ly, 10, 8, fillColor=color, strokeWidth=0))
        drawing.add(String(lx + 13, ly + 1, label,
                           fontSize=7, fontName="Helvetica", fillColor=COLOR_BLACK))
        lx += 90

    return drawing


def build_expense_pie_chart(analysis: dict) -> Drawing:
    """
    Pie chart showing expense breakdown for the latest month.
    """
    detail       = analysis["detail_df"]
    latest_month = analysis["latest_month"]

    EXPENSE_LINES = [
        "Rent", "Payroll", "Utilities", "Marketing & Advertising",
        "Software & Subscriptions", "Shipping & Postage",
        "Professional Fees", "Miscellaneous",
        # QuickBooks may use these names too
        "Rent & Office", "Travel & Entertainment",
        "Cost of Services",
    ]

    # Collect expense values for the latest month
    expenses = {}
    for item in EXPENSE_LINES:
        if item in detail.index:
            val = abs(float(detail.loc[item, latest_month]))
            if val > 0:
                expenses[item] = val

    if not expenses:
        return Drawing(1, 1)   # Empty drawing if no data

    chart_width  = 6.8 * inch
    chart_height = 2.8 * inch

    drawing = Drawing(chart_width, chart_height)

    # Background
    drawing.add(Rect(
        0, 0, chart_width, chart_height,
        fillColor=colors.HexColor("#F8FAFB"),
        strokeColor=COLOR_MID_GRAY,
        strokeWidth=0.5
    ))

    # Title
    drawing.add(String(
        chart_width / 2, chart_height - 14,
        f"Expense Breakdown — {latest_month}",
        fontSize=10, fontName="Helvetica-Bold",
        fillColor=COLOR_NAVY, textAnchor="middle"
    ))

    # Pie chart
    pie = Pie()
    pie.x      = 20
    pie.y      = 30
    pie.width  = 160
    pie.height = 160

    labels = list(expenses.keys())
    values = list(expenses.values())
    total  = sum(values)

    pie.data   = values
    pie.labels = [f"{v/total*100:.0f}%" for v in values]

    pie.simpleLabels         = 1
    pie.sideLabels           = 0
    pie.slices.strokeWidth   = 0.5
    pie.slices.strokeColor   = COLOR_WHITE
    pie.slices.fontName      = "Helvetica"
    pie.slices.fontSize      = 7
    pie.slices.labelRadius   = 0.65

    for i, _ in enumerate(values):
        pie.slices[i].fillColor = CHART_COLORS[i % len(CHART_COLORS)]

    drawing.add(pie)

    # Legend (right side)
    lx = 205
    ly = chart_height - 35
    for i, (label, val) in enumerate(expenses.items()):
        color = CHART_COLORS[i % len(CHART_COLORS)]
        drawing.add(Rect(lx, ly, 10, 8, fillColor=color, strokeWidth=0))
        short_label = label[:22] + ".." if len(label) > 24 else label
        drawing.add(String(
            lx + 14, ly + 1,
            f"{short_label}  ${val:,.0f}",
            fontSize=7.5, fontName="Helvetica", fillColor=COLOR_BLACK
        ))
        ly -= 16

    return drawing
