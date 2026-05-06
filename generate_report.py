"""
generate_report.py
------------------
Generates one polished PDF report using sample data.
No QuickBooks connection needed — great for testing.

Output: reports/{ClientName}/{YYYY-MM}_financial_report.pdf

How to run:
  python generate_report.py
  python generate_report.py blue_oak_consulting
"""

import sys
import os

from src.analysis.sample_data          import SAMPLE_PNL, get_sample_data
from src.analysis.sample_balance_sheet import get_sample_balance_sheet
from src.analysis.sample_cash_flow     import get_sample_cash_flow
from src.analysis.analyzer             import run_analysis
from src.analysis.balance_sheet_analyzer import analyze_balance_sheet
from src.analysis.cash_flow_analyzer   import analyze_cash_flow
from src.claude_insights.insights      import generate_insights
from src.pdf_generator.html_report     import generate_report_pdf


def main(client_id: str = "riverside_home_goods") -> None:

    print("=" * 62)
    print("  FINANCIAL REPORT GENERATOR")
    print(f"  Client  : {client_id}")
    print("=" * 62)

    # ── Step 1: P&L ────────────────────────────────────────────────────
    print("\n[1/5] Running P&L analysis...")
    pnl_data = get_sample_data(client_id)
    analysis = run_analysis(pnl_data)

    latest       = analysis["latest_month"]
    monthly_rev  = float(analysis["summary_df"].loc["Total Revenue",      latest])
    monthly_cogs = float(analysis["summary_df"].loc["Cost of Goods Sold", latest])
    net_profit   = float(analysis["summary_df"].loc["Net Profit",         latest])
    net_margin   = float(analysis["summary_df"].loc["Net Margin %",       latest])

    print(f"     Period     : {analysis['all_months'][0]} -> {latest}")
    print(f"     Revenue    : ${monthly_rev:,.0f}")
    print(f"     Net Profit : ${net_profit:,.0f}  ({net_margin:.1f}% margin)")

    # ── Step 2: Balance Sheet ───────────────────────────────────────────
    print("\n[2/5] Running Balance Sheet analysis...")
    bs_raw      = get_sample_balance_sheet(client_id)
    bs_analysis = analyze_balance_sheet(
        bs_raw,
        monthly_revenue = monthly_rev,
        monthly_cogs    = monthly_cogs,
    )
    print(f"     As of      : {bs_analysis['as_of_date']}")
    print(f"     Assets     : ${bs_analysis['total_assets']:,.0f}")
    print(f"     Current Ratio: {bs_analysis['current_ratio']}"
          f"  |  AR Days: {bs_analysis['ar_days']}")

    # ── Step 3: Cash Flow ───────────────────────────────────────────────
    print("\n[3/5] Running Cash Flow analysis...")
    cf_raw      = get_sample_cash_flow(client_id)
    cf_analysis = analyze_cash_flow(analysis, bs_analysis, cf_raw)
    status      = "POSITIVE" if cf_analysis["is_cash_positive"] else "NEGATIVE"
    print(f"     Operating CF : ${cf_analysis['operating_cash_flow']:,.0f}")
    print(f"     Cash Runway  : {cf_analysis['cash_runway_months']} months")
    print(f"     Status       : {status}")

    # ── Step 4: Claude insights ─────────────────────────────────────────
    print("\n[4/5] Generating Claude insights (claude-sonnet-4-5)...")
    print("      Sending data to Claude — 5-10 seconds...")
    insights = generate_insights(
        analysis    = analysis,
        bs_analysis = bs_analysis,
        cf_analysis = cf_analysis,
    )
    print("      Done.")

    # ── Step 5: Build PDF ───────────────────────────────────────────────
    print("\n[5/5] Building PDF report...")
    pdf_path = generate_report_pdf(
        analysis    = analysis,
        insights    = insights,
        bs_analysis = bs_analysis,
        cf_analysis = cf_analysis,
        logo_path   = "assets/logo.png" if os.path.exists("assets/logo.png") else None,
    )

    print("\n" + "=" * 62)
    print("  DONE")
    print(f"  Report saved to:")
    print(f"  {os.path.abspath(pdf_path)}")
    print("=" * 62)


if __name__ == "__main__":
    client_arg = next(
        (a for a in sys.argv[1:] if not a.startswith("--")),
        "riverside_home_goods"
    )
    main(client_arg)
