"""
report_charts.py
----------------
Generates all four charts for the HTML financial report.
Each function returns a base64-encoded PNG string ready for embedding
directly in HTML as:  <img src="data:image/png;base64,{string}">

No temp files are written — charts live in memory only.

CHARTS:
  revenue_trend_chart()   — Line: Revenue / Gross Profit / Net Profit per month
  expense_donut_chart()   — Donut: Top expense categories (latest month)
  cash_position_chart()   — Horizontal bar: Cash balance, burn, OCF, free CF
  gross_margin_chart()    — Line: Gross margin % and Net margin % per month

COLOR PALETTE — matches the report's design:
  Navy    #1B2A4A  (primary / dark)
  Accent  #2E86AB  (blue highlight)
  Green   #27AE60  (positive / healthy)
  Red     #E74C3C  (negative / attention)
  Muted   #8895A7  (secondary labels)
"""

import io
import base64
import numpy as np
import matplotlib
matplotlib.use("Agg")   # Headless — no display needed on Windows
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import FuncFormatter


# ── Palette ──────────────────────────────────────────────────────────────────
NAVY    = "#1B2A4A"
ACCENT  = "#2E86AB"
GREEN   = "#27AE60"
RED     = "#E74C3C"
MUTED   = "#8895A7"
BORDER  = "#DDE3ED"
PALETTE = [NAVY, ACCENT, "#3AAFA9", "#5B9BAF", "#6C8EBF", MUTED, "#8B5E83"]


# ── Shared helpers ────────────────────────────────────────────────────────────

def _save(fig) -> str:
    """Render figure → base64 PNG string, then close the figure."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return b64


def _money_fmt(x, _):
    """Axis tick label: $12K or $1.2M"""
    if abs(x) >= 1_000_000:
        return f"${x / 1_000_000:.1f}M"
    if abs(x) >= 1_000:
        return f"${x / 1_000:.0f}K"
    return f"${x:.0f}"


def _short_label(month: str) -> str:
    """'February 2025' → 'Feb 25'"""
    parts = month.split()
    return f"{parts[0][:3]} {parts[1][2:]}" if len(parts) == 2 else month[:6]


def _clean(ax, grid=True):
    """Apply minimal, professional style to an axes object."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(BORDER)
    ax.spines["bottom"].set_color(BORDER)
    ax.tick_params(colors="#5A6A7A", labelsize=8.5, length=3, pad=4)
    ax.set_facecolor("white")
    if grid:
        ax.yaxis.grid(True, color="#EEF2F7", linewidth=0.8,
                      linestyle="--", zorder=0)
        ax.set_axisbelow(True)


# ── Chart 1: Revenue Trend ────────────────────────────────────────────────────

def revenue_trend_chart(analysis: dict) -> str:
    """
    Line chart — Revenue, Gross Profit, and Net Profit for every month.
    Shows the business's income trajectory at a glance.
    """
    summary = analysis["summary_df"]
    months  = analysis["all_months"]
    labels  = [_short_label(m) for m in months]
    x       = np.arange(len(months))

    revenue = [float(summary.loc["Total Revenue",  m]) for m in months]
    gross_p = [float(summary.loc["Gross Profit",   m]) for m in months]
    net_p   = [float(summary.loc["Net Profit",     m]) for m in months]

    fig, ax = plt.subplots(figsize=(8.2, 3.6), facecolor="white")

    # Soft fill under revenue line
    ax.fill_between(x, revenue, alpha=0.06, color=NAVY, zorder=1)

    # Lines with hollow markers
    marker_kw = {"markerfacecolor": "white", "markeredgewidth": 2.2, "zorder": 4}
    ax.plot(x, revenue, "o-", color=NAVY,   lw=2.5, ms=8, label="Revenue",      **marker_kw)
    ax.plot(x, gross_p, "s-", color=ACCENT, lw=2.2, ms=7, label="Gross Profit", **marker_kw)
    ax.plot(x, net_p,   "^-", color=GREEN,  lw=2.0, ms=7, label="Net Profit",   **marker_kw)

    # Value label at last data point for each line
    for vals, color in [(revenue, NAVY), (gross_p, ACCENT), (net_p, GREEN)]:
        ax.annotate(
            f"${vals[-1] / 1000:.1f}K",
            xy=(x[-1], vals[-1]),
            xytext=(8, 0), textcoords="offset points",
            va="center", fontsize=8.5, color=color, fontweight="bold",
        )

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.yaxis.set_major_formatter(FuncFormatter(_money_fmt))
    ax.legend(loc="upper left", frameon=True, fontsize=8.5,
              facecolor="white", edgecolor=BORDER, framealpha=0.95)
    _clean(ax)
    fig.tight_layout(pad=0.8)
    return _save(fig)


# ── Chart 2: Expense Donut ────────────────────────────────────────────────────

def expense_donut_chart(analysis: dict) -> str:
    """
    Donut chart of the top expense categories for the latest month.
    Shows where the money is going at a glance.
    """
    top = analysis.get("top_expenses", [])
    if not top:
        fig, ax = plt.subplots(figsize=(5, 3.8), facecolor="white")
        ax.text(0.5, 0.5, "No expense data", ha="center", va="center",
                color=MUTED, fontsize=10)
        ax.axis("off")
        return _save(fig)

    labels  = [e["name"] for e in top]
    amounts = [e["amount"] for e in top]
    colors  = PALETTE[:len(top)]
    total   = sum(amounts)

    fig, ax = plt.subplots(figsize=(6, 3.8), facecolor="white")
    wedges, _ = ax.pie(
        amounts,
        colors     = colors,
        wedgeprops = {"width": 0.50, "linewidth": 2.5, "edgecolor": "white"},
        startangle = 90,
    )

    # Center annotation
    ax.text(0,  0.10, f"${total / 1000:.0f}K", ha="center", va="center",
            fontsize=15, fontweight="bold", color=NAVY)
    ax.text(0, -0.20, "total spend",           ha="center", va="center",
            fontsize=8,  color=MUTED)

    # Legend with monospace amounts
    patches = [
        mpatches.Patch(color=c, label=f"{lbl[:20]:<20}  ${amt:>8,.0f}")
        for lbl, amt, c in zip(labels, amounts, colors)
    ]
    ax.legend(
        handles        = patches,
        loc            = "center left",
        bbox_to_anchor = (0.98, 0.5),
        frameon        = False,
        fontsize       = 8,
        prop           = {"family": "monospace", "size": 8},
    )

    ax.axis("equal")
    fig.tight_layout(pad=0.5)
    return _save(fig)


# ── Chart 3: Cash Position ────────────────────────────────────────────────────

def cash_position_chart(cf_analysis: dict, _bs_analysis: dict = None) -> str:
    """
    Horizontal bar chart comparing four key cash numbers:
    Cash in Bank, Monthly Costs, Operating CF, Free CF.
    Green = positive/good, red = negative/watch.
    """
    ocf  = cf_analysis.get("operating_cash_flow", 0)
    fcf  = cf_analysis.get("free_cash_flow",      0)
    cash = cf_analysis.get("cash_balance",        0)
    burn = cf_analysis.get("monthly_burn_rate",   0)

    labels = ["Cash in Bank", "Monthly Costs", "Operating CF", "Free CF"]
    values = [cash, burn, ocf, fcf]
    colors = [
        ACCENT,
        MUTED,
        GREEN if ocf >= 0 else RED,
        GREEN if fcf >= 0 else RED,
    ]

    fig, ax = plt.subplots(figsize=(7.2, 3.2), facecolor="white")
    bars = ax.barh(labels, values, color=colors, height=0.52, linewidth=0, zorder=3)

    for bar, val in zip(bars, values):
        offset  = abs(val) * 0.025
        x_pos   = val + offset if val >= 0 else val - offset
        ha      = "left"        if val >= 0 else "right"
        label   = f"  ${val:,.0f}" if val >= 0 else f"  (${abs(val):,.0f})"
        ax.text(x_pos, bar.get_y() + bar.get_height() / 2,
                label, va="center", ha=ha,
                fontsize=9, fontweight="bold", color=NAVY)

    ax.axvline(x=0, color=BORDER, linewidth=1)
    ax.xaxis.set_major_formatter(FuncFormatter(_money_fmt))
    ax.invert_yaxis()
    _clean(ax, grid=False)
    ax.xaxis.grid(True, color="#EEF2F7", linewidth=0.8, linestyle="--", zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", labelsize=9)
    fig.tight_layout(pad=0.8)
    return _save(fig)


# ── Chart 4: Gross Margin Trend ───────────────────────────────────────────────

def gross_margin_chart(analysis: dict) -> str:
    """
    Line chart — Gross Margin % and Net Margin % for every month.
    A rising gross margin line means the business is becoming more efficient.
    """
    summary = analysis["summary_df"]
    months  = analysis["all_months"]
    labels  = [_short_label(m) for m in months]
    x       = np.arange(len(months))

    gross_m = [float(summary.loc["Gross Margin %", m]) for m in months]
    net_m   = [float(summary.loc["Net Margin %",   m]) for m in months]

    fig, ax = plt.subplots(figsize=(8.2, 3.2), facecolor="white")

    ax.fill_between(x, gross_m, alpha=0.08, color=ACCENT, zorder=1)
    ax.fill_between(x, net_m,   alpha=0.08, color=GREEN,  zorder=1)

    marker_kw = {"markerfacecolor": "white", "markeredgewidth": 2.2, "zorder": 4}
    ax.plot(x, gross_m, "o-", color=ACCENT, lw=2.5, ms=8, label="Gross Margin %", **marker_kw)
    ax.plot(x, net_m,   "s-", color=GREEN,  lw=2.2, ms=7, label="Net Margin %",   **marker_kw)

    # Annotate every point
    for i, (g, n) in enumerate(zip(gross_m, net_m)):
        ax.annotate(f"{g:.1f}%", xy=(i, g), xytext=(0, 9),
                    textcoords="offset points",
                    ha="center", fontsize=8, color=ACCENT, fontweight="bold")
        ax.annotate(f"{n:.1f}%", xy=(i, n), xytext=(0, -14),
                    textcoords="offset points",
                    ha="center", fontsize=8, color=GREEN,  fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.legend(frameon=True, fontsize=8.5,
              facecolor="white", edgecolor=BORDER, framealpha=0.95)
    _clean(ax)
    fig.tight_layout(pad=0.8)
    return _save(fig)


# ── Convenience: generate all four at once ────────────────────────────────────

def generate_all_charts(analysis: dict, cf_analysis: dict,
                        bs_analysis: dict = None) -> dict:
    """
    Run all four chart functions and return a dict of base64 PNG strings.
    Keys: revenue_trend, expense_donut, cash_position, gross_margin
    """
    return {
        "revenue_trend":  revenue_trend_chart(analysis),
        "expense_donut":  expense_donut_chart(analysis),
        "cash_position":  cash_position_chart(cf_analysis, bs_analysis),
        "gross_margin":   gross_margin_chart(analysis),
    }
