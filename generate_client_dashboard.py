"""
generate_client_dashboard.py
-----------------------------
Generates a beautiful, self-contained HTML dashboard for a client.
The file is saved alongside their PDF report and can be emailed or opened directly.

HOW TO RUN:
  python generate_client_dashboard.py --client riverside_home_goods
  python generate_client_dashboard.py --client riverside_home_goods --sample
  python generate_client_dashboard.py --client riverside_home_goods --open

OUTPUT:
  reports/{ClientName}/{YYYY-MM}_dashboard.html
"""

import sys
import os
import json
import pathlib
import sqlite3
import datetime
import argparse
import webbrowser

ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)


# ═══════════════════════════════════════════════════════════════════
# DATA HELPERS
# ═══════════════════════════════════════════════════════════════════

def _load_client(client_id: str) -> dict:
    db = ROOT / "clients.db"
    if not db.exists():
        raise FileNotFoundError("clients.db not found. Run: python manage_clients.py add")
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM clients WHERE client_id = ?", (client_id,)).fetchone()
    conn.close()
    if not row:
        raise ValueError(f"Client '{client_id}' not found. Run: python manage_clients.py list")
    return dict(row)


def _pull_data(client: dict, force_sample: bool):
    client_id     = client["client_id"]
    business_name = client["business_name"]
    today         = datetime.date.today()
    month         = today.month - 1 or 12
    year          = today.year if today.month > 1 else today.year - 1

    if not force_sample and client.get("qbo_company_id"):
        try:
            from src.quickbooks.auth      import tokens_exist
            from src.quickbooks.data_pull import (
                get_pnl_last_3_months, get_balance_sheet, get_cash_flow
            )
            if tokens_exist(client_id):
                pnl = get_pnl_last_3_months(client_id, business_name, year, month)
                bs  = get_balance_sheet(client_id, business_name, year, month)
                cf  = get_cash_flow(client_id, business_name, year, month)
                return pnl, bs, cf
        except Exception as e:
            print(f"  QB pull failed ({e}), using sample data")

    from src.analysis.sample_data         import get_sample_data
    from src.analysis.sample_balance_sheet import get_sample_balance_sheet
    from src.analysis.sample_cash_flow     import get_sample_cash_flow
    return (
        get_sample_data(client_id),
        get_sample_balance_sheet(client_id),
        get_sample_cash_flow(client_id),
    )


def _analyze(pnl_data, bs_data, cf_data):
    from src.analysis.analyzer               import run_analysis
    from src.analysis.balance_sheet_analyzer import analyze_balance_sheet
    from src.analysis.cash_flow_analyzer     import analyze_cash_flow

    analysis    = run_analysis(pnl_data)
    latest      = analysis["latest_month"]
    monthly_rev = float(analysis["summary_df"].loc["Total Revenue",      latest])
    monthly_cogs= float(analysis["summary_df"].loc["Cost of Goods Sold", latest])

    bs_analysis = analyze_balance_sheet(bs_data,
                    monthly_revenue=monthly_rev, monthly_cogs=monthly_cogs)
    cf_analysis = analyze_cash_flow(analysis, bs_analysis, cf_data)
    return analysis, bs_analysis, cf_analysis


def _get_insights(analysis, bs_analysis, cf_analysis) -> str:
    from src.claude_insights.insights import generate_insights
    return generate_insights(
        analysis=analysis, bs_analysis=bs_analysis, cf_analysis=cf_analysis
    )


# ═══════════════════════════════════════════════════════════════════
# CHART DATA BUILDERS
# ═══════════════════════════════════════════════════════════════════

def _pnl_chart_data(analysis: dict) -> dict:
    """3-month Revenue / Gross Profit / Net Profit bar data for Chart.js."""
    df     = analysis["summary_df"]
    months = analysis["all_months"]

    def _row(label):
        try:
            return [round(float(df.loc[label, m]), 0) for m in months]
        except Exception:
            return [0] * len(months)

    return {
        "labels":   months,
        "revenue":  _row("Total Revenue"),
        "expenses": _row("Total Expenses"),
        "profit":   _row("Net Profit"),
    }


def _cf_bars(cf_analysis: dict) -> dict:
    return {
        "operating":  round(float(cf_analysis.get("operating_cash_flow",  0) or 0)),
        "investing":  round(float(cf_analysis.get("investing_cash_flow",  0) or 0)),
        "financing":  round(float(cf_analysis.get("financing_cash_flow",  0) or 0)),
    }


# ═══════════════════════════════════════════════════════════════════
# INSIGHT PARSER  — splits insights into the three sections
# ═══════════════════════════════════════════════════════════════════

def _parse_insights(raw: str) -> dict:
    sections = {"what_happened": "", "why_it_matters": "", "what_to_watch": ""}
    current  = None
    buf      = []

    for line in raw.splitlines():
        u = line.strip().upper()
        if "WHAT HAPPENED" in u:
            if current and buf: sections[current] = "\n".join(buf).strip()
            current, buf = "what_happened", []
        elif "WHY IT MATTERS" in u:
            if current and buf: sections[current] = "\n".join(buf).strip()
            current, buf = "why_it_matters", []
        elif "WHAT TO WATCH" in u:
            if current and buf: sections[current] = "\n".join(buf).strip()
            current, buf = "what_to_watch", []
        else:
            if current:
                buf.append(line)

    if current and buf:
        sections[current] = "\n".join(buf).strip()

    # Fallback: dump everything into what_happened if parsing failed
    if not any(sections.values()):
        sections["what_happened"] = raw.strip()

    return sections


def _fmt_insight_html(text: str) -> str:
    """Convert plain insight text to clean HTML paragraphs / bullet lists."""
    if not text:
        return "<p style='color:#9ca3af;font-style:italic;'>No data available.</p>"
    lines  = text.strip().splitlines()
    out    = []
    in_ul  = False
    for line in lines:
        s = line.strip()
        if not s:
            if in_ul: out.append("</ul>"); in_ul = False
            continue
        if s.startswith(("-", "•", "*", "–")):
            if not in_ul: out.append('<ul class="insight-list">'); in_ul = True
            out.append(f"<li>{s.lstrip('-•*– ').strip()}</li>")
        else:
            if in_ul: out.append("</ul>"); in_ul = False
            out.append(f"<p>{s}</p>")
    if in_ul: out.append("</ul>")
    return "\n".join(out)


# ═══════════════════════════════════════════════════════════════════
# HTML RENDERER
# ═══════════════════════════════════════════════════════════════════

def _render(client: dict, analysis: dict, bs: dict, cf: dict,
            insights_raw: str) -> str:

    company  = os.getenv("COMPANY_NAME",  "Shah Consultant")
    author   = os.getenv("REPORT_AUTHOR", company)
    email    = os.getenv("SMTP_USER",     "")

    biz      = client["business_name"]
    period   = analysis["latest_month"]
    industry = client.get("industry") or ""

    # ── KPI values ──────────────────────────────────────────────
    df          = analysis["summary_df"]
    latest      = analysis["latest_month"]
    revenue     = float(df.loc["Total Revenue",  latest])
    net_profit  = float(df.loc["Net Profit",     latest])
    net_margin  = float(df.loc["Net Margin %",   latest])
    runway      = float(cf.get("cash_runway_months", 0) or 0)

    def _usd(v):  return f"${abs(v):,.0f}"
    def _pct(v):  return f"{v:.1f}%"
    def _mo(v):   return f"{v:.1f} mo"

    def _kpi_color(v, positive_is_good=True):
        good = v >= 0 if positive_is_good else v < 0
        return "#22c55e" if good else "#ef4444"

    def _kpi_bg(v, positive_is_good=True):
        good = v >= 0 if positive_is_good else v < 0
        return "rgba(34,197,94,.06)" if good else "rgba(239,68,68,.06)"

    # ── Chart data ───────────────────────────────────────────────
    chart      = _pnl_chart_data(analysis)
    cf_bars    = _cf_bars(cf)
    cf_max     = max(abs(v) for v in cf_bars.values()) or 1

    def _bar_pct(v): return round(abs(v) / cf_max * 100)
    def _bar_col(v): return "#22c55e" if v >= 0 else "#ef4444"

    # ── Balance sheet ────────────────────────────────────────────
    curr_ratio = bs.get("current_ratio", 0) or 0
    ar_days    = bs.get("ar_days",       0) or 0
    quick_ratio= bs.get("quick_ratio",   0) or 0

    def _ratio_status(v, good_above):
        return "#22c55e" if v >= good_above else "#f59e0b"

    # ── Insights ─────────────────────────────────────────────────
    sec     = _parse_insights(insights_raw)
    html_wh = _fmt_insight_html(sec["what_happened"])
    html_wm = _fmt_insight_html(sec["why_it_matters"])
    html_ww = _fmt_insight_html(sec["what_to_watch"])

    # ── Chart.js data ─────────────────────────────────────────────
    months_js   = json.dumps(chart["labels"])
    revenue_js  = json.dumps(chart["revenue"])
    expenses_js = json.dumps(chart["expenses"])
    profit_js   = json.dumps(chart["profit"])

    generated = datetime.datetime.now().strftime("%B %d, %Y")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{biz} — Financial Report {period}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  :root {{
    --navy:   #0f172a;
    --indigo: #6366f1;
    --slate:  #475569;
    --border: #e2e8f0;
    --bg:     #f8fafc;
    --white:  #ffffff;
    --green:  #22c55e;
    --red:    #ef4444;
    --amber:  #f59e0b;
    --text:   #1e293b;
    --muted:  #64748b;
    --radius: 12px;
    --shadow: 0 1px 3px rgba(0,0,0,.08), 0 4px 16px rgba(0,0,0,.04);
  }}

  body {{
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
  }}

  /* ── HEADER ── */
  .header {{
    background: var(--navy);
    padding: 0 40px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 72px;
    position: sticky;
    top: 0;
    z-index: 10;
  }}
  .header-left {{
    display: flex;
    align-items: center;
    gap: 12px;
  }}
  .firm-dot {{
    width: 8px; height: 8px;
    background: var(--indigo);
    border-radius: 50%;
  }}
  .firm-name {{
    font-size: 15px;
    font-weight: 700;
    color: #fff;
    letter-spacing: -.01em;
  }}
  .header-right {{ text-align: right; }}
  .client-name {{
    font-size: 13px;
    font-weight: 600;
    color: rgba(255,255,255,.9);
  }}
  .header-period {{
    font-size: 11px;
    color: rgba(255,255,255,.45);
    margin-top: 1px;
  }}

  /* ── HERO BANNER ── */
  .hero {{
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    padding: 48px 40px 56px;
    position: relative;
    overflow: hidden;
  }}
  .hero::after {{
    content: '';
    position: absolute;
    right: -60px; top: -60px;
    width: 320px; height: 320px;
    border-radius: 50%;
    background: rgba(99,102,241,.08);
  }}
  .hero-label {{
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .1em;
    color: var(--indigo);
    margin-bottom: 8px;
  }}
  .hero-title {{
    font-size: 28px;
    font-weight: 700;
    color: #fff;
    letter-spacing: -.02em;
    margin-bottom: 4px;
  }}
  .hero-sub {{
    font-size: 14px;
    color: rgba(255,255,255,.45);
  }}

  /* ── CONTENT WRAPPER ── */
  .content {{ padding: 32px 40px 64px; max-width: 1100px; margin: 0 auto; }}

  /* ── KPI CARDS ── */
  .kpi-strip {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-top: -28px;
    margin-bottom: 32px;
    position: relative;
    z-index: 2;
  }}
  .kpi {{
    background: var(--white);
    border-radius: var(--radius);
    padding: 22px 24px;
    box-shadow: var(--shadow);
    border-top: 3px solid transparent;
    transition: transform .15s ease;
  }}
  .kpi:hover {{ transform: translateY(-2px); }}
  .kpi-label {{
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .07em;
    color: var(--muted);
    margin-bottom: 10px;
  }}
  .kpi-value {{
    font-size: 26px;
    font-weight: 800;
    letter-spacing: -.03em;
    color: var(--text);
    line-height: 1;
    margin-bottom: 6px;
  }}
  .kpi-tag {{
    display: inline-block;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 20px;
  }}

  /* ── SECTION HEADING ── */
  .section-title {{
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .08em;
    color: var(--muted);
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .section-title::after {{
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border);
  }}

  /* ── CARDS ── */
  .card {{
    background: var(--white);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    padding: 28px;
    margin-bottom: 24px;
    border: 1px solid var(--border);
  }}
  .card-title {{
    font-size: 15px;
    font-weight: 700;
    color: var(--text);
    margin-bottom: 20px;
    letter-spacing: -.01em;
  }}
  .chart-wrap {{ height: 260px; position: relative; }}

  /* ── TWO COL ── */
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }}

  /* ── BALANCE SHEET RATIOS ── */
  .ratio-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 0;
    border-bottom: 1px solid var(--border);
  }}
  .ratio-row:last-child {{ border-bottom: none; padding-bottom: 0; }}
  .ratio-label {{ font-size: 13px; color: var(--muted); }}
  .ratio-value {{
    font-size: 20px;
    font-weight: 700;
    letter-spacing: -.02em;
  }}
  .ratio-bench {{ font-size: 11px; color: var(--muted); text-align: right; margin-top: 1px; }}

  /* ── CASH FLOW BARS ── */
  .cf-row {{ margin-bottom: 18px; }}
  .cf-row:last-child {{ margin-bottom: 0; }}
  .cf-meta {{
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    margin-bottom: 6px;
  }}
  .cf-label {{ color: var(--muted); font-weight: 500; }}
  .cf-amount {{ font-weight: 700; }}
  .cf-track {{
    height: 8px;
    background: var(--bg);
    border-radius: 99px;
    overflow: hidden;
  }}
  .cf-fill {{
    height: 100%;
    border-radius: 99px;
    transition: width .6s ease;
  }}

  /* ── INSIGHTS ── */
  .insight-block {{
    padding: 24px 24px 24px 28px;
    border-left: 3px solid var(--indigo);
    background: #fafbff;
    border-radius: 0 var(--radius) var(--radius) 0;
    margin-bottom: 20px;
  }}
  .insight-block:last-child {{ margin-bottom: 0; }}
  .insight-heading {{
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .1em;
    color: var(--indigo);
    margin-bottom: 12px;
  }}
  .insight-block p {{
    font-size: 14px;
    color: #334155;
    margin-bottom: 8px;
    line-height: 1.7;
  }}
  .insight-block p:last-child {{ margin-bottom: 0; }}
  ul.insight-list {{
    list-style: none;
    padding: 0;
    margin: 0;
  }}
  ul.insight-list li {{
    font-size: 14px;
    color: #334155;
    padding: 5px 0 5px 18px;
    position: relative;
    line-height: 1.6;
  }}
  ul.insight-list li::before {{
    content: '';
    position: absolute;
    left: 0;
    top: 13px;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--indigo);
  }}

  /* ── FOOTER ── */
  .footer {{
    background: var(--navy);
    padding: 32px 40px;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 32px;
    flex-wrap: wrap;
  }}
  .footer-brand {{
    font-size: 14px;
    font-weight: 700;
    color: #fff;
    margin-bottom: 4px;
  }}
  .footer-sub {{
    font-size: 12px;
    color: rgba(255,255,255,.4);
    max-width: 480px;
    line-height: 1.6;
  }}
  .footer-contact {{
    text-align: right;
  }}
  .footer-contact a {{
    color: var(--indigo);
    text-decoration: none;
    font-size: 13px;
    font-weight: 600;
  }}
  .footer-date {{
    font-size: 11px;
    color: rgba(255,255,255,.3);
    margin-top: 4px;
  }}

  @media (max-width: 800px) {{
    .kpi-strip {{ grid-template-columns: 1fr 1fr; }}
    .grid-2    {{ grid-template-columns: 1fr; }}
    .hero, .content, .header, .footer {{ padding-left: 20px; padding-right: 20px; }}
  }}
</style>
</head>
<body>

<!-- ── HEADER ─────────────────────────────────────────────────── -->
<header class="header">
  <div class="header-left">
    <div class="firm-dot"></div>
    <span class="firm-name">{company}</span>
  </div>
  <div class="header-right">
    <div class="client-name">{biz}</div>
    <div class="header-period">Financial Report &nbsp;·&nbsp; {period}{f" &nbsp;·&nbsp; {industry}" if industry else ""}</div>
  </div>
</header>

<!-- ── HERO ───────────────────────────────────────────────────── -->
<div class="hero">
  <div style="max-width:1100px; margin:0 auto;">
    <div class="hero-label">Monthly Financial Report</div>
    <div class="hero-title">{period} Overview</div>
    <div class="hero-sub">{biz}</div>
  </div>
</div>

<!-- ── CONTENT ─────────────────────────────────────────────────── -->
<div class="content">

  <!-- KPI STRIP -->
  <div class="kpi-strip">

    <div class="kpi" style="border-top-color:#6366f1;">
      <div class="kpi-label">Revenue</div>
      <div class="kpi-value">{_usd(revenue)}</div>
      <div class="kpi-tag" style="background:#eef2ff;color:#6366f1;">This Month</div>
    </div>

    <div class="kpi" style="border-top-color:{_kpi_color(net_profit)};">
      <div class="kpi-label">Net Profit</div>
      <div class="kpi-value" style="color:{_kpi_color(net_profit)};">{_usd(net_profit)}</div>
      <div class="kpi-tag" style="background:{_kpi_bg(net_profit)};color:{_kpi_color(net_profit)};">
        {"Profitable" if net_profit >= 0 else "Net Loss"}
      </div>
    </div>

    <div class="kpi" style="border-top-color:{_kpi_color(net_margin)};">
      <div class="kpi-label">Net Margin</div>
      <div class="kpi-value" style="color:{_kpi_color(net_margin)};">{_pct(net_margin)}</div>
      <div class="kpi-tag" style="background:{_kpi_bg(net_margin)};color:{_kpi_color(net_margin)};">
        {"Strong" if net_margin >= 15 else ("Healthy" if net_margin >= 5 else ("Thin" if net_margin >= 0 else "Negative"))}
      </div>
    </div>

    <div class="kpi" style="border-top-color:{_kpi_color(runway - 3)};">
      <div class="kpi-label">Cash Runway</div>
      <div class="kpi-value" style="color:{_kpi_color(runway - 3)};">{_mo(runway)}</div>
      <div class="kpi-tag" style="background:{_kpi_bg(runway - 3)};color:{_kpi_color(runway - 3)};">
        {"Healthy" if runway >= 6 else ("Watch" if runway >= 3 else "Low")}
      </div>
    </div>

  </div>

  <!-- P&L CHART -->
  <div class="section-title">Profit & Loss — 3 Month View</div>
  <div class="card">
    <div class="card-title">Revenue, Expenses &amp; Net Profit</div>
    <div class="chart-wrap">
      <canvas id="pnlChart"></canvas>
    </div>
  </div>

  <!-- BALANCE SHEET + CASH FLOW -->
  <div class="section-title">Balance Sheet &amp; Cash Flow</div>
  <div class="grid-2">

    <!-- Balance Sheet Ratios -->
    <div class="card">
      <div class="card-title">Balance Sheet Highlights</div>

      <div class="ratio-row">
        <div>
          <div class="ratio-label">Current Ratio</div>
          <div class="ratio-bench">Benchmark &gt; 1.5</div>
        </div>
        <div style="text-align:right">
          <div class="ratio-value" style="color:{_ratio_status(curr_ratio, 1.5)};">{curr_ratio:.2f}</div>
        </div>
      </div>

      <div class="ratio-row">
        <div>
          <div class="ratio-label">Quick Ratio</div>
          <div class="ratio-bench">Benchmark &gt; 1.0</div>
        </div>
        <div style="text-align:right">
          <div class="ratio-value" style="color:{_ratio_status(quick_ratio, 1.0)};">{quick_ratio:.2f}</div>
        </div>
      </div>

      <div class="ratio-row">
        <div>
          <div class="ratio-label">AR Days</div>
          <div class="ratio-bench">Benchmark &lt; 45 days</div>
        </div>
        <div style="text-align:right">
          <div class="ratio-value" style="color:{'#22c55e' if ar_days < 45 else '#f59e0b'};">{ar_days:.0f} d</div>
        </div>
      </div>

    </div>

    <!-- Cash Flow Bars -->
    <div class="card">
      <div class="card-title">Cash Flow Breakdown</div>

      <div class="cf-row">
        <div class="cf-meta">
          <span class="cf-label">Operating</span>
          <span class="cf-amount" style="color:{_bar_col(cf_bars['operating'])};">
            {"+" if cf_bars['operating'] >= 0 else ""}{_usd(cf_bars['operating'])}
          </span>
        </div>
        <div class="cf-track">
          <div class="cf-fill" style="width:{_bar_pct(cf_bars['operating'])}%;background:{_bar_col(cf_bars['operating'])};"></div>
        </div>
      </div>

      <div class="cf-row">
        <div class="cf-meta">
          <span class="cf-label">Investing</span>
          <span class="cf-amount" style="color:{_bar_col(cf_bars['investing'])};">
            {"+" if cf_bars['investing'] >= 0 else ""}{_usd(cf_bars['investing'])}
          </span>
        </div>
        <div class="cf-track">
          <div class="cf-fill" style="width:{_bar_pct(cf_bars['investing'])}%;background:{_bar_col(cf_bars['investing'])};"></div>
        </div>
      </div>

      <div class="cf-row">
        <div class="cf-meta">
          <span class="cf-label">Financing</span>
          <span class="cf-amount" style="color:{_bar_col(cf_bars['financing'])};">
            {"+" if cf_bars['financing'] >= 0 else ""}{_usd(cf_bars['financing'])}
          </span>
        </div>
        <div class="cf-track">
          <div class="cf-fill" style="width:{_bar_pct(cf_bars['financing'])}%;background:{_bar_col(cf_bars['financing'])};"></div>
        </div>
      </div>

    </div>
  </div>

  <!-- AI INSIGHTS -->
  <div class="section-title">AI-Generated Insights</div>
  <div class="card">
    <div class="card-title">Monthly Commentary</div>

    <div class="insight-block">
      <div class="insight-heading">&#128200; What Happened</div>
      {html_wh}
    </div>

    <div class="insight-block" style="border-left-color:#f59e0b;background:#fffbf0;">
      <div class="insight-heading" style="color:#d97706;">&#9888; Why It Matters</div>
      {html_wm}
    </div>

    <div class="insight-block" style="border-left-color:#22c55e;background:#f0fdf4;">
      <div class="insight-heading" style="color:#16a34a;">&#128270; What to Watch</div>
      {html_ww}
    </div>

  </div>

</div><!-- /content -->

<!-- ── FOOTER ─────────────────────────────────────────────────── -->
<footer class="footer">
  <div>
    <div class="footer-brand">{author}</div>
    <div class="footer-sub">
      This report is prepared exclusively for {biz} and contains forward-looking statements
      based on available financial data. It is intended for informational purposes only and
      does not constitute investment, tax, or legal advice. Data sourced from QuickBooks Online.
    </div>
  </div>
  <div class="footer-contact">
    {"<a href='mailto:" + email + "'>" + email + "</a>" if email else ""}
    <div class="footer-date">Generated {generated}</div>
  </div>
</footer>

<!-- ── CHART.JS ────────────────────────────────────────────────── -->
<script>
const pnlCtx = document.getElementById('pnlChart').getContext('2d');
new Chart(pnlCtx, {{
  type: 'bar',
  data: {{
    labels: {months_js},
    datasets: [
      {{
        label: 'Revenue',
        data: {revenue_js},
        backgroundColor: 'rgba(99,102,241,.85)',
        borderRadius: 5,
        borderSkipped: false,
      }},
      {{
        label: 'Expenses',
        data: {expenses_js},
        backgroundColor: 'rgba(239,68,68,.7)',
        borderRadius: 5,
        borderSkipped: false,
      }},
      {{
        label: 'Net Profit',
        data: {profit_js},
        backgroundColor: 'rgba(34,197,94,.85)',
        borderRadius: 5,
        borderSkipped: false,
      }},
    ]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{
      legend: {{
        position: 'bottom',
        labels: {{
          color: '#64748b',
          font: {{ size: 12 }},
          boxWidth: 12,
          padding: 20,
        }}
      }},
      tooltip: {{
        callbacks: {{
          label: ctx => ` ${{ctx.dataset.label}}: $` + ctx.parsed.y.toLocaleString()
        }}
      }}
    }},
    scales: {{
      x: {{
        ticks: {{ color: '#64748b', font: {{ size: 12 }} }},
        grid:  {{ display: false }}
      }},
      y: {{
        ticks: {{
          color: '#64748b',
          font: {{ size: 11 }},
          callback: v => '$' + v.toLocaleString()
        }},
        grid: {{ color: '#f1f5f9' }},
        beginAtZero: true,
      }}
    }}
  }}
}});
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════════
# SAVE + OPEN
# ═══════════════════════════════════════════════════════════════════

def _save(client: dict, analysis: dict, html: str) -> pathlib.Path:
    period   = analysis["latest_month"]
    biz_safe = client["business_name"].replace(" ", "_").replace("/", "_")
    out_dir  = ROOT / "reports" / biz_safe
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{period}_dashboard.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


# ═══════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Generate client financial dashboard")
    parser.add_argument("--client", required=True, help="Client ID from clients.db")
    parser.add_argument("--sample", action="store_true",
                        help="Force sample data (skip QuickBooks)")
    parser.add_argument("--open",   action="store_true",
                        help="Open dashboard in browser after generating")
    parser.add_argument("--no-insights", action="store_true",
                        help="Skip Claude insights (faster, for testing layout)")
    args = parser.parse_args()

    print(f"\nGenerating dashboard for: {args.client}")

    client = _load_client(args.client)
    print(f"  Client : {client['business_name']}")

    print("  [1/3] Pulling financial data...")
    pnl, bs_data, cf_data = _pull_data(client, args.sample)

    print("  [2/3] Running analysis...")
    analysis, bs_analysis, cf_analysis = _analyze(pnl, bs_data, cf_data)
    print(f"        Period : {analysis['latest_month']}")
    print(f"        Revenue: ${float(analysis['summary_df'].loc['Total Revenue', analysis['latest_month']]):,.0f}")

    if args.no_insights:
        insights = "WHAT HAPPENED\nSample insights omitted.\nWHY IT MATTERS\nn/a\nWHAT TO WATCH\nn/a"
    else:
        print("  [3/3] Generating Claude insights...")
        insights = _get_insights(analysis, bs_analysis, cf_analysis)

    html     = _render(client, analysis, bs_analysis, cf_analysis, insights)
    out_path = _save(client, analysis, html)

    print(f"\n  Saved: {out_path}")
    print(f"  Size : {out_path.stat().st_size / 1024:.0f} KB")

    if args.open:
        print("  Opening in browser...")
        webbrowser.open(out_path.as_uri())

    return out_path


if __name__ == "__main__":
    main()
