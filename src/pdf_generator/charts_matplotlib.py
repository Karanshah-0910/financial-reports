"""
charts_matplotlib.py
--------------------
Generates professional 3D charts using matplotlib.
Each chart is saved to an in-memory image (BytesIO) and embedded in the PDF.

Charts:
  - 3D bar chart : Revenue, Gross Profit, Net Profit across all months
  - 3D pie chart : Expense breakdown for the latest month
"""

import io
import numpy as np
import matplotlib
matplotlib.use("Agg")   # No display needed — runs headless on Windows
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from mpl_toolkits.mplot3d import Axes3D

# Brand colors matching the PDF
NAVY    = "#1B2A4A"
ACCENT  = "#2E86AB"
GREEN   = "#27AE60"
ORANGE  = "#E67E22"
RED     = "#E74C3C"
PURPLE  = "#8E44AD"
TEAL    = "#16A085"
YELLOW  = "#F39C12"
BG      = "#F0F4F8"

CHART_COLORS = [ACCENT, GREEN, ORANGE, RED, PURPLE, TEAL, YELLOW, "#D35400", "#2C3E50"]

EXPENSE_LINES = [
    "Rent", "Rent & Office", "Payroll", "Utilities",
    "Marketing & Advertising", "Software & Subscriptions",
    "Shipping & Postage", "Professional Fees",
    "Travel & Entertainment", "Cost of Services", "Miscellaneous",
]


def _to_image_buffer(fig, dpi=150) -> io.BytesIO:
    """Save a matplotlib figure to a BytesIO buffer."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close(fig)
    return buf


# ---------------------------------------------------------------------------
# 3D Bar Chart — Revenue, Gross Profit, Net Profit
# ---------------------------------------------------------------------------
def create_revenue_3d_bar_chart(analysis: dict) -> io.BytesIO:
    """
    3D bar chart showing Revenue, Gross Profit and Net Profit
    side by side for each month.
    """
    summary = analysis["summary_df"]
    months  = analysis["all_months"]
    short_months = [m.split()[0][:3] + "\n" + m.split()[-1] for m in months]

    revenue      = [float(summary.loc["Total Revenue",  m]) for m in months]
    gross_profit = [float(summary.loc["Gross Profit",   m]) for m in months]
    net_profit   = [float(summary.loc["Net Profit",     m]) for m in months]

    fig = plt.figure(figsize=(9, 4.5), facecolor=BG)
    ax  = fig.add_subplot(111, projection="3d")
    ax.set_facecolor(BG)

    num_months = len(months)
    x = np.arange(num_months)
    width = 0.22
    depth = 0.4

    # Draw three bars per month group
    ax.bar3d(x - width,       [0] * num_months, [0] * num_months,
             width, depth, revenue,      color=ACCENT,  alpha=0.88, shade=True)
    ax.bar3d(x,               [0] * num_months, [0] * num_months,
             width, depth, gross_profit, color=GREEN,   alpha=0.88, shade=True)
    ax.bar3d(x + width,       [0] * num_months, [0] * num_months,
             width, depth, net_profit,   color=ORANGE,  alpha=0.88, shade=True)

    # Axes labels
    ax.set_xticks(x)
    ax.set_xticklabels(short_months, fontsize=8, fontweight="bold", color=NAVY)
    ax.set_yticks([])
    ax.yaxis.set_visible(False)
    ax.zaxis.set_tick_params(labelsize=7)
    ax.zaxis.set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda v, _: f"${v/1000:.0f}k")
    )

    # Styling
    ax.set_title("Revenue vs Gross Profit vs Net Profit — 3-Month Trend",
                 fontsize=11, fontweight="bold", color=NAVY, pad=18)
    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False
    ax.xaxis.pane.set_edgecolor("#CCCCCC")
    ax.yaxis.pane.set_edgecolor("#CCCCCC")
    ax.zaxis.pane.set_edgecolor("#CCCCCC")
    ax.grid(True, color="#DDDDDD", linewidth=0.4)
    ax.view_init(elev=22, azim=-55)

    # Legend
    legend_patches = [
        mpatches.Patch(color=ACCENT,  label="Total Revenue"),
        mpatches.Patch(color=GREEN,   label="Gross Profit"),
        mpatches.Patch(color=ORANGE,  label="Net Profit"),
    ]
    ax.legend(handles=legend_patches, loc="upper left",
              fontsize=8, framealpha=0.85, edgecolor="#CCCCCC")

    plt.tight_layout()
    return _to_image_buffer(fig)


# ---------------------------------------------------------------------------
# 3D-Effect Pie Chart — Expense Breakdown
# ---------------------------------------------------------------------------
def create_expense_3d_pie_chart(analysis: dict) -> io.BytesIO:
    """
    3D-effect pie chart showing what percentage each expense is
    of total spending for the latest month.
    """
    detail       = analysis["detail_df"]
    latest_month = analysis["latest_month"]

    # Collect expenses
    expenses = {}
    for item in EXPENSE_LINES:
        if item in detail.index:
            val = abs(float(detail.loc[item, latest_month]))
            if val > 0:
                expenses[item] = val

    # Catch any QuickBooks line items not in our standard list
    skip = {"Sales - In Store","Sales - Online","Sales - Wholesale",
            "Cost of Goods Sold","Consulting Fees - Strategy",
            "Consulting Fees - Operations","Retainer Income","Cost of Services"}
    for idx in detail.index:
        if idx not in EXPENSE_LINES and idx not in skip:
            val = abs(float(detail.loc[idx, latest_month]))
            if val > 0 and idx not in expenses:
                expenses[idx] = val

    if not expenses:
        fig, ax = plt.subplots(figsize=(1, 1), facecolor=BG)
        return _to_image_buffer(fig)

    labels = list(expenses.keys())
    values = list(expenses.values())
    total  = sum(values)
    colors = CHART_COLORS[:len(labels)]

    # Explode the largest slice slightly
    max_idx = values.index(max(values))
    explode = [0.04] * len(values)
    explode[max_idx] = 0.12

    fig, ax = plt.subplots(figsize=(9, 4.8), facecolor=BG)
    ax.set_facecolor(BG)

    # Draw pie with shadow for 3D effect
    wedges, texts, autotexts = ax.pie(
        values,
        explode=explode,
        colors=colors,
        autopct=lambda p: f"{p:.1f}%" if p > 4 else "",
        pctdistance=0.72,
        startangle=140,
        shadow=True,
        wedgeprops=dict(linewidth=1.8, edgecolor="white"),
        textprops=dict(color="white", fontsize=8, fontweight="bold"),
    )

    # Make the shadow deeper for more 3D look
    for w in wedges:
        w.set_linewidth(1.5)

    ax.set_title(
        f"Expense Breakdown — {latest_month}",
        fontsize=11, fontweight="bold", color=NAVY, pad=14
    )

    # Custom legend with dollar amounts and percentages
    legend_labels = [
        f"{lbl[:20]+'...' if len(lbl)>20 else lbl}  —  ${val:,.0f}  ({val/total*100:.1f}%)"
        for lbl, val in zip(labels, values)
    ]
    legend = ax.legend(
        wedges, legend_labels,
        title="Expense Categories",
        title_fontsize=8,
        loc="center left",
        bbox_to_anchor=(0.98, 0.5),
        fontsize=7.5,
        framealpha=0.9,
        edgecolor="#CCCCCC",
    )
    legend.get_title().set_color(NAVY)
    legend.get_title().set_fontweight("bold")

    plt.tight_layout()
    return _to_image_buffer(fig)


# ---------------------------------------------------------------------------
# Trend Line Chart — Net Profit trend (bonus chart)
# ---------------------------------------------------------------------------
def create_margin_trend_chart(analysis: dict) -> io.BytesIO:
    """
    Simple line chart showing Gross Margin % and Net Margin % trend.
    Easy to read — even for non-finance people.
    """
    summary = analysis["summary_df"]
    months  = analysis["all_months"]
    short   = [m.split()[0][:3] + " " + m.split()[-1] for m in months]

    gross_margins = [float(summary.loc["Gross Margin %", m]) for m in months]
    net_margins   = [float(summary.loc["Net Margin %",   m]) for m in months]

    fig, ax = plt.subplots(figsize=(9, 3.2), facecolor=BG)
    ax.set_facecolor("#FFFFFF")

    x = range(len(months))

    # Gross margin line
    ax.plot(x, gross_margins, "o-", color=ACCENT, linewidth=2.5,
            markersize=8, markerfacecolor="white", markeredgewidth=2.5,
            label="Gross Margin %", zorder=3)

    # Net margin line
    ax.plot(x, net_margins, "s-", color=GREEN, linewidth=2.5,
            markersize=8, markerfacecolor="white", markeredgewidth=2.5,
            label="Net Margin %", zorder=3)

    # Add value labels above each point
    for i, (gm, nm) in enumerate(zip(gross_margins, net_margins)):
        ax.annotate(f"{gm:.1f}%", (i, gm), textcoords="offset points",
                    xytext=(0, 10), ha="center", fontsize=8,
                    color=ACCENT, fontweight="bold")
        ax.annotate(f"{nm:.1f}%", (i, nm), textcoords="offset points",
                    xytext=(0, -18), ha="center", fontsize=8,
                    color=GREEN, fontweight="bold")

    # Shaded area under gross margin
    ax.fill_between(x, gross_margins, alpha=0.08, color=ACCENT)
    ax.fill_between(x, net_margins,   alpha=0.08, color=GREEN)

    ax.set_xticks(x)
    ax.set_xticklabels(short, fontsize=9, fontweight="bold", color=NAVY)
    ax.set_ylabel("Margin %", fontsize=9, color=NAVY)
    ax.set_title("Profit Margin Trend", fontsize=11,
                 fontweight="bold", color=NAVY, pad=12)
    ax.legend(fontsize=9, loc="upper left", framealpha=0.9, edgecolor="#CCCCCC")
    ax.grid(True, linestyle="--", alpha=0.4, color="#AAAAAA")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_ylim(bottom=0)

    plt.tight_layout()
    return _to_image_buffer(fig)
