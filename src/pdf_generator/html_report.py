"""
html_report.py
--------------
Builds a professional 6-page PDF financial report using fpdf2
(pure Python — no GTK, no external runtime required).

PAGES:
  Cover              — Client name, report month, logo, confidential footer
  Executive Summary  — 3-section Claude CFO briefing
  Key Metrics        — 8 metric cards + full P&L table with MoM indicators
  P&L Summary        — Revenue trend chart + top categories + expense donut
  Balance Sheet & CF — Ratio badges, BS table, cash chart, margin chart
  Action Items       — What to Watch bullets + attention flags

USAGE:
  from src.pdf_generator.html_report import generate_report_pdf
  path = generate_report_pdf(analysis, insights, bs_analysis, cf_analysis)
"""

import io
import os
import base64
from datetime import datetime

from fpdf import FPDF

from .report_charts import generate_all_charts


# ── Unicode-safe PDF subclass ─────────────────────────────────────────────────
# fpdf2's built-in Helvetica / core fonts are Latin-1 only.
# This subclass transliterates common Unicode punctuation (em dash, curly
# quotes, etc.) to their ASCII equivalents before fpdf2 sees them, so Claude's
# insight text never causes a UnicodeEncodeError.

_UNICODE_MAP = str.maketrans({
    '—': '--',    # em dash       —
    '–': '-',     # en dash       –
    '‒': '-',     # figure dash
    '―': '--',    # horizontal bar
    '‘': "'",     # left  single curly quote
    '’': "'",     # right single curly quote  '
    '‚': ',',     # low-9 single quote
    '‛': "'",     # reversed single quote
    '“': '"',     # left  double curly quote
    '”': '"',     # right double curly quote
    '„': '"',     # low-9 double quote
    '…': '...',   # ellipsis  …
    '•': '*',     # bullet  •
    '‣': '>',     # triangular bullet
    '→': '->',    # right arrow  →
    '←': '<-',    # left  arrow  ←
    '↑': '^',     # up    arrow  ↑
    '↓': 'v',     # down  arrow  ↓
    ' ': ' ',     # non-breaking space
    '°': 'deg',   # degree  °
    '±': '+/-',   # plus-minus  ±
    '×': 'x',     # multiplication  ×
    '÷': '/',     # division  ÷
    'é': 'e',     # é
    'è': 'e',     # è
    'ê': 'e',     # ê
    'ë': 'e',     # ë
    'à': 'a',     # à
    'â': 'a',     # â
    'ä': 'a',     # ä
    'ü': 'u',     # ü
    'ö': 'o',     # ö
    'ç': 'c',     # ç
    'î': 'i',     # î
    'ï': 'i',     # ï
    'ô': 'o',     # ô
    'û': 'u',     # û
    'ù': 'u',     # ù
})


class _PDF(FPDF):
    """FPDF subclass that sanitizes text to Latin-1 before rendering."""

    def normalize_text(self, text: str) -> str:
        text = text.translate(_UNICODE_MAP)
        # Replace any remaining non-latin-1 characters with '?'
        return text.encode("latin-1", errors="replace").decode("latin-1")


# ── Color palette ─────────────────────────────────────────────────────────────
NAVY   = (27,  42,  74)
ACCENT = (46, 134, 171)
GREEN  = (39, 174,  96)
RED    = (231,  76,  60)
YELLOW = (243, 156,  18)
MUTED  = (136, 149, 167)
LIGHT  = (245, 247, 250)
DARK   = (44,  62,  80)
WHITE  = (255, 255, 255)
BORDER = (221, 227, 237)
LBEIGE = (249, 250, 252)
DNAVY  = (18,  28,  50)

# ── Page geometry (mm, letter size) ──────────────────────────────────────────
PW     = 215.9
PH     = 279.4
M      = 15.0    # Left / right margin
HDR_H  = 18.0    # Height of top nav bar
FTR_H  = 14.0    # Height of bottom bar
ACC_W  = 4.0     # Accent strip width on left of content
CX     = M + ACC_W + 3    # Content left edge  (≈22 mm)
CW     = PW - CX - M      # Usable content width (≈179 mm)
CY     = HDR_H + 7        # Content top y


# ── Low-level drawing helpers ─────────────────────────────────────────────────

def _fc(pdf, rgb): pdf.set_fill_color(*rgb)
def _tc(pdf, rgb): pdf.set_text_color(*rgb)
def _dc(pdf, rgb): pdf.set_draw_color(*rgb)

def _rect(pdf, x, y, w, h, color, style="F"):
    _fc(pdf, color); pdf.rect(x, y, w, h, style)


def _b64_buf(b64: str) -> io.BytesIO:
    return io.BytesIO(base64.b64decode(b64))


def _fmt(val, pct=False) -> str:
    try:
        v = float(val)
        if pct: return f"{v:.1f}%"
        return f"(${abs(v):,.0f})" if v < 0 else f"${v:,.0f}"
    except Exception:
        return str(val) if val is not None else "N/A"


def _mom_str(val, invert=False) -> tuple:
    """Returns (display_string, rgb_color) for a MoM % value."""
    try:
        v = float(val)
        if v != v: return "—", MUTED
        if invert:
            color = RED if v > 0 else (GREEN if v < 0 else MUTED)
        else:
            color = GREEN if v > 0 else (RED if v < 0 else MUTED)
        arrow = "+" if v > 0 else ("" if v < 0 else "")
        return f"{arrow}{v:.1f}%", color
    except Exception:
        return "—", MUTED


def _page_shell(pdf, title: str, biz: str, month: str, page_num: int):
    """Draw the navy header, accent left strip, and footer on the current page."""
    # Header bar
    _rect(pdf, 0, 0, PW, HDR_H, NAVY)
    _tc(pdf, WHITE);  pdf.set_font("Helvetica", "B", 11)
    pdf.set_xy(CX, 5.5); pdf.cell(110, 6, title)
    _tc(pdf, (143, 184, 212)); pdf.set_font("Helvetica", "", 8)
    pdf.set_xy(PW - M - 75, 4); pdf.cell(75, 5, biz, align="R")
    _tc(pdf, (180, 190, 200)); pdf.set_font("Helvetica", "", 7)
    pdf.set_xy(PW - M - 75, 10); pdf.cell(75, 4, f"Page {page_num}", align="R")
    # Accent left strip
    _rect(pdf, M, HDR_H, ACC_W, PH - HDR_H - FTR_H, ACCENT)
    # Footer bar
    _rect(pdf, 0, PH - FTR_H, PW, FTR_H, NAVY)
    _tc(pdf, MUTED); pdf.set_font("Helvetica", "", 6.5)
    pdf.set_xy(0, PH - FTR_H + 4.5)
    pdf.cell(PW, 4.5,
             f"CONFIDENTIAL  |  {biz}  |  {month}  |  "
             f"Generated {datetime.now().strftime('%d %b %Y')}",
             align="C")


def _section_title(pdf, x, y, text) -> float:
    """Draw a bold section heading with accent underline. Returns y after."""
    _tc(pdf, NAVY); pdf.set_font("Helvetica", "B", 9)
    pdf.set_xy(x, y)
    tw = pdf.get_string_width(text.upper()) + 1
    pdf.cell(tw, 5, text.upper())
    _rect(pdf, x, y + 5.5, tw, 0.8, ACCENT)
    return y + 9


def _wrapped(pdf, x, y, w, text, size=10, bold=False, color=DARK,
             lh=5.8) -> float:
    """Write wrapped text, return y after last line."""
    pdf.set_font("Helvetica", "B" if bold else "", size)
    _tc(pdf, color)
    pdf.set_xy(x, y)
    pdf.multi_cell(w, lh, str(text))
    return pdf.get_y()


def _card(pdf, x, y, w, h, label: str, value: str,
          mom_text: str, mom_color, top_color):
    """Draw a metric card (colored top stripe, value, MoM label)."""
    _rect(pdf, x, y, w, 2.2, top_color)
    _rect(pdf, x, y + 2.2, w, h - 2.2, LIGHT)
    _tc(pdf, MUTED); pdf.set_font("Helvetica", "", 5.8)
    pdf.set_xy(x + 2, y + 3.8); pdf.cell(w - 4, 3.5, label.upper())
    _tc(pdf, NAVY);  pdf.set_font("Helvetica", "B", 13)
    pdf.set_xy(x + 2, y + 8.5); pdf.cell(w - 4, 7, value)
    if mom_text:
        _tc(pdf, mom_color); pdf.set_font("Helvetica", "", 6.5)
        pdf.set_xy(x + 2, y + 17); pdf.cell(w - 4, 3.5, mom_text)


def _tbl_hdr(pdf, x, y, cols) -> float:
    """Navy header row. cols = [(label, width, align)]. Returns y after."""
    rh = 6.2
    total_w = sum(c[1] for c in cols)
    _rect(pdf, x, y, total_w, rh, NAVY)
    _tc(pdf, WHITE); pdf.set_font("Helvetica", "B", 7)
    cx = x
    for label, w, align in cols:
        pdf.set_xy(cx + 2, y + 1.2); pdf.cell(w - 4, rh - 2.2, label, align=align)
        cx += w
    return y + rh


def _tbl_row(pdf, x, y, cells, even=True, bold=False, total=False) -> float:
    """Data row. cells = [(text, width, align, color?)]. Returns y after."""
    rh = 5.5
    bg = (230, 240, 248) if total else (LIGHT if even else WHITE)
    _rect(pdf, x, y, sum(c[1] for c in cells), rh, bg)
    pdf.set_font("Helvetica", "B" if (bold or total) else "", 8 if total else 7.8)
    cx = x
    for item in cells:
        text  = str(item[0]) if item[0] is not None else "—"
        w     = item[1]
        align = item[2] if len(item) > 2 else "L"
        color = item[3] if len(item) > 3 else (NAVY if total else DARK)
        _tc(pdf, color)
        pdf.set_xy(cx + 2, y + 1); pdf.cell(w - 4, rh - 2, text, align=align)
        cx += w
    return y + rh


def _badge(pdf, x, y, text: str, color_bg, color_txt):
    """Inline colored badge."""
    _fc(pdf, color_bg); _dc(pdf, color_bg)
    tw = pdf.get_string_width(text) + 6
    pdf.set_font("Helvetica", "B", 6)
    pdf.rect(x, y, tw, 4.5, "F")
    _tc(pdf, color_txt)
    pdf.set_xy(x + 3, y + 0.5); pdf.cell(tw - 6, 3.5, text)
    return x + tw + 2


HEALTH_MAP = {
    "green":  ((234, 250, 241), (30, 132,  73)),
    "yellow": ((254, 249, 231), (212, 172, 13)),
    "red":    ((253, 237, 236), (192,  57, 43)),
    "grey":   ((242, 243, 244), (113, 125, 126)),
}
HEALTH_LABEL = {"green": "HEALTHY", "yellow": "WATCH",
                "red": "ATTENTION", "grey": "N/A"}


def _health_badge(pdf, x, y, score: str):
    bg, fg = HEALTH_MAP.get(score, HEALTH_MAP["grey"])
    label  = HEALTH_LABEL.get(score, "N/A")
    return _badge(pdf, x, y, label, bg, fg)


# ── Insights parser ───────────────────────────────────────────────────────────

def _parse_insights(text: str) -> dict:
    result = {"what_happened": "", "why_it_matters": "", "what_to_watch": []}
    current, buf = None, []

    def flush():
        if current == "what_to_watch":
            for ln in buf:
                clean = ln.lstrip("- ").strip()
                if clean: result["what_to_watch"].append(clean)
        elif current:
            result[current] = " ".join(b.strip() for b in buf if b.strip())

    for raw in text.strip().split("\n"):
        up = raw.strip().upper()
        if "WHAT HAPPENED" in up and len(raw.strip()) < 40:
            flush(); current = "what_happened"; buf = []
        elif "WHY IT MATTERS" in up and len(raw.strip()) < 40:
            flush(); current = "why_it_matters"; buf = []
        elif "WHAT TO WATCH" in up and len(raw.strip()) < 40:
            flush(); current = "what_to_watch"; buf = []
        elif raw.strip():
            buf.append(raw.strip())
    flush()
    return result


# ── Page builders ─────────────────────────────────────────────────────────────

def _build_cover(pdf, analysis, logo_path):
    pdf.add_page()
    # Full navy background
    _rect(pdf, 0, 0, PW, PH, NAVY)
    # Top accent stripe
    _rect(pdf, 0, 0, PW, 3.5, ACCENT)

    biz    = analysis["business_name"]
    months = analysis["all_months"]
    latest = analysis["latest_month"]

    # Logo or initials badge
    logo_y = 38
    if logo_path and os.path.exists(logo_path):
        logo_w = 55
        try:
            pdf.image(logo_path, x=(PW - logo_w) / 2, y=logo_y, w=logo_w)
        except Exception:
            pass
        logo_y += 38
    else:
        # Initials badge
        initials = "".join(w[0].upper() for w in biz.split()[:2])
        _rect(pdf, (PW - 22) / 2, logo_y, 22, 22, ACCENT)
        _tc(pdf, WHITE); pdf.set_font("Helvetica", "B", 14)
        pdf.set_xy((PW - 22) / 2, logo_y + 5)
        pdf.cell(22, 12, initials, align="C")
        logo_y += 32

    # "MONTHLY FINANCIAL REPORT"
    _tc(pdf, ACCENT); pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(0, logo_y); pdf.cell(PW, 5, "MONTHLY FINANCIAL REPORT", align="C")
    logo_y += 8
    # Accent rule
    _rect(pdf, (PW - 30) / 2, logo_y, 30, 1.2, ACCENT)
    logo_y += 7

    # Business name
    _tc(pdf, WHITE); pdf.set_font("Helvetica", "B", 26)
    pdf.set_xy(M, logo_y); pdf.cell(PW - 2 * M, 15, biz, align="C")
    logo_y += 18

    # Period
    _tc(pdf, (143, 184, 212)); pdf.set_font("Helvetica", "", 12)
    pdf.set_xy(0, logo_y)
    pdf.cell(PW, 7, f"{months[0]}  —  {latest}", align="C")
    logo_y += 18

    # Month badge (bordered box)
    badge_w, badge_h = 80, 13
    bx = (PW - badge_w) / 2
    _dc(pdf, ACCENT); pdf.set_line_width(0.5)
    _fc(pdf, NAVY)
    pdf.rect(bx, logo_y, badge_w, badge_h, "DF")
    _tc(pdf, ACCENT); pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(bx, logo_y + 2.5)
    pdf.cell(badge_w, badge_h - 5, latest.upper(), align="C")

    # Bottom confidential bar
    _rect(pdf, 0, PH - 20, PW, 20, DNAVY)
    _tc(pdf, (120, 140, 160)); pdf.set_font("Helvetica", "", 7.5)
    pdf.set_xy(0, PH - 13)
    pdf.cell(PW, 5,
             f"Prepared {datetime.now().strftime('%B %d, %Y')}   |   "
             f"CONFIDENTIAL — For Authorized Recipients Only",
             align="C")


def _build_exec_summary(pdf, analysis, parsed, biz, month):
    pdf.add_page()
    _page_shell(pdf, "Executive Summary", biz, month, 1)
    y = CY

    wh  = parsed.get("what_happened",  "") or "Not available."
    wim = parsed.get("why_it_matters", "") or "Not available."
    wtw = parsed.get("what_to_watch",  [])

    for tag, body in [("What Happened", wh), ("Why It Matters", wim)]:
        y = _section_title(pdf, CX, y, tag)
        y = _wrapped(pdf, CX, y, CW, body, size=10.5, lh=6.2)
        y += 8

    y = _section_title(pdf, CX, y, "What to Watch")
    for i, item in enumerate(wtw[:3]):
        # Numbered circle
        _rect(pdf, CX, y, 6.5, 6.5, NAVY)
        _tc(pdf, WHITE); pdf.set_font("Helvetica", "B", 7.5)
        pdf.set_xy(CX, y + 0.5); pdf.cell(6.5, 5.5, str(i + 1), align="C")
        # Text
        _tc(pdf, DARK); pdf.set_font("Helvetica", "", 10)
        pdf.set_xy(CX + 9, y + 0.5)
        pdf.multi_cell(CW - 9, 5.8, item)
        y = pdf.get_y() + 5
        # Background box
        _rect(pdf, CX, y - pdf.get_y() + y - 5,
              CW, 1, (241, 244, 248))   # subtle separator


def _build_key_metrics(pdf, analysis, bs_analysis, cf_analysis, biz, month):
    pdf.add_page()
    _page_shell(pdf, "Key Metrics Dashboard", biz, month, 2)

    summary = analysis["summary_df"]
    mom     = analysis["mom_df"]
    latest  = analysis["latest_month"]
    months  = analysis["all_months"]

    rev    = float(summary.loc["Total Revenue",   latest])
    gross  = float(summary.loc["Gross Profit",    latest])
    net    = float(summary.loc["Net Profit",       latest])
    gm_pct = float(summary.loc["Gross Margin %",  latest])
    nm_pct = float(summary.loc["Net Margin %",    latest])
    cash   = cf_analysis.get("cash_balance",       0)
    runway = cf_analysis.get("cash_runway_months", None)
    wc     = bs_analysis.get("working_capital",    0)

    def get_mom(metric):
        try:
            v = float(mom.loc[metric, latest])
            return (None, None) if v != v else _mom_str(v)
        except Exception:
            return None, None

    runway_str = f"{runway} mo" if runway else "N/A"
    runway_color = GREEN if (runway or 0) >= 6 else (YELLOW if (runway or 0) >= 3 else RED)
    profit_color = GREEN if net >= 0 else RED

    # ── 8 metric cards in 2 rows of 4 ──────────────────────────────────────
    y  = CY
    cw = CW / 4 - 2    # Card width
    ch = 22             # Card height
    _section_title(pdf, CX, y - 7, "Key Metrics")

    cards = [
        # Row 1
        ("Total Revenue", _fmt(rev),   get_mom("Total Revenue"),  ACCENT),
        ("Gross Profit",  _fmt(gross),  get_mom("Gross Profit"),   NAVY),
        ("Net Profit",    _fmt(net),    get_mom("Net Profit"),     profit_color),
        ("Gross Margin",  _fmt(gm_pct, pct=True), get_mom("Gross Margin %"), NAVY),
        # Row 2
        ("Net Margin",    _fmt(nm_pct, pct=True), get_mom("Net Margin %"),  NAVY),
        ("Cash in Bank",  _fmt(cash),  (None, None),              ACCENT),
        ("Cash Runway",   runway_str,  (None, None),              runway_color),
        ("Working Capital", _fmt(wc),  (None, None),
         GREEN if wc > 10000 else (YELLOW if wc >= 0 else RED)),
    ]

    for i, (label, val, (mtxt, mcol), top_c) in enumerate(cards):
        row = i // 4
        col = i % 4
        cx_ = CX + col * (cw + 2.5)
        cy_ = y + row * (ch + 4)
        _card(pdf, cx_, cy_, cw, ch, label, val,
              mtxt or "", mcol or MUTED, top_c)

    y += 2 * (ch + 4) + 8

    # ── P&L summary table ───────────────────────────────────────────────────
    _section_title(pdf, CX, y, "P&L Summary")
    y += 2

    # Dynamic column widths
    label_w = 48
    num_w   = (CW - label_w) / (len(months) * 2)

    cols = (
        [("", label_w, "L")]
        + [(m, num_w, "R") for m in months]
        + [(f"MoM {months[-1]}", num_w, "R")]
        + [("", num_w * (len(months) - 1), "R")]
    )
    # Simpler: label + one col per month + 1 mom col
    cols2 = [("Metric", label_w, "L")] + [(m, num_w + 2, "R") for m in months]
    mom_col_w = CW - label_w - (num_w + 2) * len(months)
    if mom_col_w > 10:
        cols2.append(("MoM", max(mom_col_w, 18), "R"))

    y = _tbl_hdr(pdf, CX, y, cols2)

    BOLD_ROWS = {"Gross Profit", "Net Profit"}
    PCT_ROWS  = {"Gross Margin %", "Net Margin %", "Operating Margin %"}
    INVERT    = {"Total Expenses", "Cost of Goods Sold"}

    for i, metric in enumerate(summary.index):
        is_bold  = metric in BOLD_ROWS
        is_total = metric in BOLD_ROWS
        is_pct   = metric in PCT_ROWS
        # Mom for latest month
        try:
            mv = float(mom.loc[metric, latest])
        except Exception:
            mv = float("nan")
        mt, mc = _mom_str(mv, invert=(metric in INVERT))

        cells = [
            (metric, label_w, "L", NAVY if is_bold else DARK),
        ]
        for m in months:
            v  = float(summary.loc[metric, m])
            cells.append((_fmt(v, is_pct), num_w + 2, "R", NAVY if is_bold else DARK))
        if mom_col_w > 10:
            cells.append((mt, max(mom_col_w, 18), "R", mc))

        y = _tbl_row(pdf, CX, y, cells, even=(i % 2 == 0),
                     bold=is_bold, total=is_total)
        if y > PH - FTR_H - 6:
            break


def _build_pnl_summary(pdf, analysis, charts, biz, month):
    pdf.add_page()
    _page_shell(pdf, "P&L Summary", biz, month, 3)
    y = CY

    # Revenue trend chart (full width)
    y = _section_title(pdf, CX, y, "Revenue Trend")
    chart_h = 52
    pdf.image(_b64_buf(charts["revenue_trend"]), x=CX, y=y, w=CW, h=chart_h)
    y += chart_h + 6

    # Two columns
    col_w = (CW - 8) / 2

    # ── Left: Revenue sources ──────────────────────────────────────────────
    y_left = _section_title(pdf, CX, y, "Revenue Sources")
    summary = analysis["summary_df"]
    detail  = analysis["detail_df"]
    latest  = analysis["latest_month"]
    total_r = float(summary.loc["Total Revenue", latest])

    rev_lines = [
        "Sales - In Store", "Sales - Online", "Sales - Wholesale",
        "Consulting Fees - Strategy", "Consulting Fees - Operations",
        "Retainer Income", "Service Revenue", "Revenue", "Sales",
    ]
    cols_rev = [("Source", col_w * 0.60, "L"),
                ("Amount", col_w * 0.22, "R"),
                ("% Rev",  col_w * 0.18, "R")]
    y_left = _tbl_hdr(pdf, CX, y_left, cols_rev)
    found = False
    for i, item in enumerate(rev_lines):
        if item in detail.index:
            v = float(detail.loc[item, latest])
            if v > 0:
                pct = v / total_r * 100 if total_r else 0
                y_left = _tbl_row(pdf, CX, y_left, [
                    (item[:22], col_w * 0.60, "L"),
                    (_fmt(v),   col_w * 0.22, "R"),
                    (f"{pct:.0f}%", col_w * 0.18, "R"),
                ], even=(i % 2 == 0))
                found = True
    if not found:
        y_left = _tbl_row(pdf, CX, y_left, [
            ("Total Revenue", col_w * 0.60, "L"),
            (_fmt(total_r),   col_w * 0.40, "R"),
        ])
    y_left = _tbl_row(pdf, CX, y_left,
                      [("Total", col_w * 0.60, "L", NAVY),
                       (_fmt(total_r), col_w * 0.22, "R", NAVY),
                       ("100%",         col_w * 0.18, "R", NAVY)],
                      total=True)
    y_left += 6

    # ── Left: Top expenses ─────────────────────────────────────────────────
    y_left = _section_title(pdf, CX, y_left, "Top Expenses")
    top = analysis.get("top_expenses", [])
    cols_exp = [("Category", col_w * 0.60, "L"),
                ("Amount",   col_w * 0.22, "R"),
                ("% Total",  col_w * 0.18, "R")]
    y_left = _tbl_hdr(pdf, CX, y_left, cols_exp)
    for i, exp in enumerate(top):
        y_left = _tbl_row(pdf, CX, y_left, [
            (exp["name"][:22],   col_w * 0.60, "L"),
            (_fmt(exp["amount"]), col_w * 0.22, "R"),
            (f"{exp['pct']}%",   col_w * 0.18, "R"),
        ], even=(i % 2 == 0))

    # ── Right: Expense donut chart ─────────────────────────────────────────
    rx = CX + col_w + 8
    y_right = _section_title(pdf, rx, y, "Expense Breakdown")
    donut_h = 70
    pdf.image(_b64_buf(charts["expense_donut"]), x=rx, y=y_right, w=col_w, h=donut_h)


def _build_bs_cf(pdf, bs_analysis, cf_analysis, charts, biz, month):
    pdf.add_page()
    _page_shell(pdf, "Balance Sheet & Cash Flow", biz, month, 4)
    a  = bs_analysis
    cf = cf_analysis
    h  = a.get("health", {})
    y  = CY
    col_w = (CW - 8) / 2

    # ── LEFT COLUMN ─────────────────────────────────────────────────────────
    y_l = _section_title(pdf, CX, y, "Balance Sheet Ratios")

    # Ratio boxes (4 across)
    ratios = [
        ("Current Ratio",  a.get("current_ratio",  "N/A"), h.get("current_ratio",  "grey")),
        ("Quick Ratio",    a.get("quick_ratio",    "N/A"), h.get("quick_ratio",    "grey")),
        ("Debt / Equity",  a.get("debt_to_equity", "N/A"), h.get("debt_to_equity", "grey")),
        ("Working Capital",_fmt(a.get("working_capital", 0)), h.get("working_capital", "grey")),
    ]
    rb_w = (col_w - 3) / 4
    for i, (label, val, score) in enumerate(ratios):
        rx = CX + i * (rb_w + 1)
        _rect(pdf, rx, y_l, rb_w, 16, LIGHT)
        _tc(pdf, MUTED); pdf.set_font("Helvetica", "", 6)
        pdf.set_xy(rx + 2, y_l + 1.5); pdf.cell(rb_w - 4, 3.5, label)
        _tc(pdf, NAVY); pdf.set_font("Helvetica", "B", 10)
        pdf.set_xy(rx + 2, y_l + 6); pdf.cell(rb_w - 4, 5, str(val))
        _health_badge(pdf, rx + 2, y_l + 12, score)

    y_l += 22

    # BS summary table
    cols_bs = [("Item",   col_w * 0.60, "L"),
               ("Value",  col_w * 0.25, "R"),
               ("Health", col_w * 0.15, "R")]  # health col drawn manually
    y_l = _tbl_hdr(pdf, CX, y_l, cols_bs[:2])  # header without Health col

    bs_rows = [
        ("Total Assets",          a.get("total_assets",        0), None,  False),
        ("Total Liabilities",     a.get("total_liabilities",   0), None,  False),
        ("Total Equity",          a.get("total_equity",        0), None,  True),
        ("AR Days Outstanding",   a.get("ar_days",       "N/A"),   h.get("ar_days","grey"), False),
        ("AP Days Outstanding",   a.get("ap_days",       "N/A"),   h.get("ap_days","grey"), False),
    ]
    for i, (label, val, score, bold) in enumerate(bs_rows):
        val_str = (f"{val} days" if "Days" in label and val != "N/A"
                   else _fmt(val) if isinstance(val, (int, float)) else str(val))
        y_l = _tbl_row(pdf, CX, y_l, [
            (label,   col_w * 0.60, "L"),
            (val_str, col_w * 0.40, "R"),
        ], even=(i % 2 == 0), bold=bold)
        if score:
            _health_badge(pdf, CX + col_w * 0.62, y_l - 5.5, score)

    y_l += 6
    # Gross margin chart
    y_l = _section_title(pdf, CX, y_l, "Margin Trend")
    mg_h = min(40, PH - FTR_H - y_l - 4)
    if mg_h > 15:
        pdf.image(_b64_buf(charts["gross_margin"]), x=CX, y=y_l, w=col_w, h=mg_h)

    # ── RIGHT COLUMN ────────────────────────────────────────────────────────
    rx   = CX + col_w + 8
    y_r  = _section_title(pdf, rx, y, "Cash Flow Summary")

    status_color = GREEN if cf.get("is_cash_positive") else RED
    status_label = "CASH FLOW POSITIVE" if cf.get("is_cash_positive") else "CASH FLOW NEGATIVE"
    _rect(pdf, rx, y_r, col_w, 6.5, status_color)
    _tc(pdf, WHITE); pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_xy(rx + 2, y_r + 1.5); pdf.cell(col_w - 4, 3.5, status_label, align="C")
    y_r += 9

    runway_str = (f"{cf.get('cash_runway_months')} months"
                  if cf.get("cash_runway_months") else "N/A")
    cf_rows = [
        ("Operating Cash Flow",   cf.get("operating_cash_flow", 0),  False),
        ("Capital Expenditures", -cf.get("capex", 0),                False),
        ("Free Cash Flow",        cf.get("free_cash_flow",      0),  True),
        ("Financing Cash Flow",   cf.get("financing_cash_flow", 0),  False),
        ("Net Cash Change",       cf.get("net_cash_change",     0),  True),
        ("Cash in Bank",          cf.get("cash_balance",        0),  False),
        ("Monthly Burn Rate",     cf.get("monthly_burn_rate",   0),  False),
        ("Cash Runway",           runway_str,                        False),
        ("Cash Conversion Cycle", f"{cf.get('cash_conversion_cycle',0):.0f} days", False),
    ]
    y_r = _tbl_hdr(pdf, rx, y_r,
                   [("Cash Flow Metric", col_w * 0.65, "L"),
                    ("Value",            col_w * 0.35, "R")])
    for i, (label, val, bold) in enumerate(cf_rows):
        val_str = (_fmt(val) if isinstance(val, (int, float)) else str(val))
        v_color = (GREEN if isinstance(val, (int, float)) and val > 0
                   else RED if isinstance(val, (int, float)) and val < 0
                   else DARK)
        y_r = _tbl_row(pdf, rx, y_r, [
            (label,   col_w * 0.65, "L"),
            (val_str, col_w * 0.35, "R", v_color if bold else DARK),
        ], even=(i % 2 == 0), bold=bold)

    y_r += 5
    y_r = _section_title(pdf, rx, y_r, "Cash Position")
    cp_h = min(40, PH - FTR_H - y_r - 4)
    if cp_h > 15:
        pdf.image(_b64_buf(charts["cash_position"]), x=rx, y=y_r, w=col_w, h=cp_h)


def _build_action_items(pdf, analysis, parsed, biz, month):
    pdf.add_page()
    _page_shell(pdf, "Action Items", biz, month, 5)
    y = CY

    y = _section_title(pdf, CX, y, "What to Watch This Month")
    _tc(pdf, MUTED); pdf.set_font("Helvetica", "", 8)
    pdf.set_xy(CX, y); pdf.cell(CW, 4.5, f"3 specific things your CFO recommends monitoring in {month}")
    y += 8

    wtw = parsed.get("what_to_watch", [])
    for i, item in enumerate(wtw[:3]):
        # Action card background
        by = y
        # Draw accent left border
        _rect(pdf, CX, y, 2.5, 22, ACCENT)
        # Number circle
        _rect(pdf, CX + 5, y + 6, 7, 7, NAVY)
        _tc(pdf, WHITE); pdf.set_font("Helvetica", "B", 8)
        pdf.set_xy(CX + 5, y + 7); pdf.cell(7, 5, str(i + 1), align="C")
        # Text
        _tc(pdf, DARK); pdf.set_font("Helvetica", "", 10)
        pdf.set_xy(CX + 15, y + 2)
        pdf.multi_cell(CW - 16, 5.8, item)
        end_y = max(pdf.get_y(), by + 20)
        # Card fill
        _rect(pdf, CX + 2.5, by, CW - 2.5, end_y - by, (248, 250, 252))
        # Redraw text on top of fill
        _rect(pdf, CX, by, 2.5, end_y - by, ACCENT)
        _rect(pdf, CX + 5, by + 6, 7, 7, NAVY)
        _tc(pdf, WHITE); pdf.set_font("Helvetica", "B", 8)
        pdf.set_xy(CX + 5, by + 7); pdf.cell(7, 5, str(i + 1), align="C")
        _tc(pdf, DARK); pdf.set_font("Helvetica", "", 10)
        pdf.set_xy(CX + 15, by + 3)
        pdf.multi_cell(CW - 16, 5.8, item)
        y = pdf.get_y() + 7

    # ── Attention Flags ────────────────────────────────────────────────────
    flags = analysis.get("attention_flags", [])
    if flags and y < PH - FTR_H - 40:
        y = _section_title(pdf, CX, y, "Line Items That Moved >20% Month-over-Month")
        _tc(pdf, MUTED); pdf.set_font("Helvetica", "", 8)
        pdf.set_xy(CX, y); pdf.cell(CW, 4, "Not necessarily problems — just worth a look.")
        y += 7

        flag_w = [50, 30, 30, 25, CW - 135]
        y = _tbl_hdr(pdf, CX, y, [
            ("Line Item",   flag_w[0], "L"),
            ("Last Month",  flag_w[1], "R"),
            ("This Month",  flag_w[2], "R"),
            ("Change",      flag_w[3], "R"),
            ("Direction",   flag_w[4], "R"),
        ])
        for i, f in enumerate(flags[:6]):
            is_up   = f["direction"] == "up"
            color   = GREEN if is_up else RED
            arrow   = "Up" if is_up else "Down"
            y = _tbl_row(pdf, CX, y, [
                (f["item"][:28],         flag_w[0], "L"),
                (_fmt(f["prev"]),         flag_w[1], "R"),
                (_fmt(f["current"]),      flag_w[2], "R"),
                (f"{abs(f['change_pct']):.1f}%", flag_w[3], "R", color),
                (arrow,                   flag_w[4], "R", color),
            ], even=(i % 2 == 0))
            if y > PH - FTR_H - 8:
                break

    # ── Expense growth verdict ──────────────────────────────────────────────
    growth  = analysis.get("expense_growth", {})
    verdict = growth.get("verdict", "")
    if verdict and y < PH - FTR_H - 20:
        y += 6
        rev_g = growth.get("revenue_growth_pct", 0) or 0
        exp_g = growth.get("expense_growth_pct", 0) or 0
        vcolor = GREEN if "Healthy" in verdict else YELLOW
        _rect(pdf, CX, y, CW, 12, (248, 250, 252))
        _rect(pdf, CX, y, 2.5, 12, vcolor)
        _tc(pdf, NAVY); pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_xy(CX + 6, y + 2)
        pdf.cell(CW - 8, 4.5, f"Expense Growth: {verdict}")
        _tc(pdf, MUTED); pdf.set_font("Helvetica", "", 7.5)
        pdf.set_xy(CX + 6, y + 7)
        pdf.cell(CW - 8, 4,
                 f"Revenue grew {rev_g:+.1f}%  vs  Expenses grew {exp_g:+.1f}%  "
                 f"({analysis['all_months'][0]} to {analysis['latest_month']})")


# ── Public entry point ────────────────────────────────────────────────────────

def generate_report_pdf(
    analysis:    dict,
    insights:    str,
    bs_analysis: dict,
    cf_analysis: dict,
    logo_path:   str = None,
    output_dir:  str = "reports",
) -> str:
    """
    Build the complete 6-page PDF and save it.
    Returns the absolute path to the saved PDF.
    Output: reports/{ClientName}/{YYYY-MM}_financial_report.pdf
    """
    biz    = analysis["business_name"]
    latest = analysis["latest_month"]

    # Build output path
    try:
        ym = datetime.strptime(latest, "%B %Y").strftime("%Y-%m")
    except Exception:
        ym = latest.replace(" ", "-")
    folder      = os.path.join(output_dir, biz.replace(" ", "_"))
    filename    = f"{ym}_financial_report.pdf"
    output_path = os.path.join(folder, filename)
    os.makedirs(folder, exist_ok=True)

    # Auto-detect logo
    if logo_path is None:
        for candidate in ["assets/logo.png", "assets/logo.jpg"]:
            if os.path.exists(candidate):
                logo_path = candidate
                break

    # Generate charts
    print("      Generating charts...")
    charts = generate_all_charts(analysis, cf_analysis, bs_analysis)

    # Parse insights
    parsed = _parse_insights(insights)

    # Build PDF
    pdf = _PDF(orientation="P", unit="mm", format="letter")
    pdf.set_auto_page_break(False)
    pdf.set_margins(0, 0, 0)

    _build_cover(pdf, analysis, logo_path)
    _build_exec_summary(pdf, analysis, parsed, biz, latest)
    _build_key_metrics(pdf, analysis, bs_analysis, cf_analysis, biz, latest)
    _build_pnl_summary(pdf, analysis, charts, biz, latest)
    _build_bs_cf(pdf, bs_analysis, cf_analysis, charts, biz, latest)
    _build_action_items(pdf, analysis, parsed, biz, latest)

    pdf.output(output_path)
    return output_path
