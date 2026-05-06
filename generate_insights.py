"""
generate_insights.py
--------------------
Standalone script — runs all three analysis modules on sample data,
sends everything to Claude (claude-sonnet-4-5), and prints the
3-section fractional CFO executive summary to the screen.

Use this to:
  - Test your Anthropic API key is working
  - Preview the insight output before it goes into a PDF
  - Quickly check how a client's numbers read in plain English

How to run:
  python generate_insights.py
  python generate_insights.py blue_oak_consulting
"""

import sys
import os

# ── Analysis imports ────────────────────────────────────────────────────────
from src.analysis.sample_data          import get_sample_data
from src.analysis.sample_balance_sheet import get_sample_balance_sheet
from src.analysis.sample_cash_flow     import get_sample_cash_flow
from src.analysis.analyzer             import run_analysis
from src.analysis.balance_sheet_analyzer import analyze_balance_sheet
from src.analysis.cash_flow_analyzer   import analyze_cash_flow
from src.claude_insights.insights      import generate_insights


def run(client_id: str = "riverside_home_goods") -> None:

    print("=" * 62)
    print("  GENERATE INSIGHTS — Fractional CFO Summary")
    print(f"  Client : {client_id}")
    print("=" * 62)

    # ── Step 1: P&L analysis ─────────────────────────────────────────────
    print("\n[1/4] Running P&L analysis...")
    pnl_data = get_sample_data(client_id)
    analysis = run_analysis(pnl_data)

    latest        = analysis["latest_month"]
    monthly_rev   = float(analysis["summary_df"].loc["Total Revenue",      latest])
    monthly_cogs  = float(analysis["summary_df"].loc["Cost of Goods Sold", latest])
    net_profit    = float(analysis["summary_df"].loc["Net Profit",         latest])
    net_margin    = float(analysis["summary_df"].loc["Net Margin %",       latest])

    print(f"     Period      : {analysis['all_months'][0]} -> {latest}")
    print(f"     Revenue     : ${monthly_rev:,.0f}")
    print(f"     Net Profit  : ${net_profit:,.0f}  ({net_margin:.1f}% margin)")

    # ── Step 2: Balance sheet analysis ───────────────────────────────────
    print("\n[2/4] Running Balance Sheet analysis...")
    bs_raw      = get_sample_balance_sheet(client_id)
    bs_analysis = analyze_balance_sheet(bs_raw,
                                        monthly_revenue = monthly_rev,
                                        monthly_cogs    = monthly_cogs)
    print(f"     As of       : {bs_analysis['as_of_date']}")
    print(f"     Total Assets: ${bs_analysis['total_assets']:,.0f}")
    print(f"     Current Ratio: {bs_analysis['current_ratio']}"
          f"  |  Quick Ratio: {bs_analysis['quick_ratio']}")

    # ── Step 3: Cash flow analysis ────────────────────────────────────────
    print("\n[3/4] Running Cash Flow analysis...")
    cf_raw      = get_sample_cash_flow(client_id)
    cf_analysis = analyze_cash_flow(analysis, bs_analysis, cf_raw)
    status      = "POSITIVE" if cf_analysis["is_cash_positive"] else "NEGATIVE"
    print(f"     Operating CF: ${cf_analysis['operating_cash_flow']:,.0f}")
    print(f"     Free CF     : ${cf_analysis['free_cash_flow']:,.0f}")
    print(f"     Cash Runway : {cf_analysis['cash_runway_months']} months")
    print(f"     Status      : {status}")

    # ── Step 4: Send to Claude ────────────────────────────────────────────
    print("\n[4/4] Sending to Claude (claude-sonnet-4-5)...")
    print("      Please wait — this takes about 5-10 seconds...\n")

    insights = generate_insights(
        analysis      = analysis,
        bs_analysis   = bs_analysis,
        cf_analysis   = cf_analysis,
    )

    # ── Print the output ──────────────────────────────────────────────────
    print("=" * 62)
    print(f"  EXECUTIVE SUMMARY — {analysis['business_name']}, {latest}")
    print("=" * 62)
    print()
    print(insights)
    print()
    print("=" * 62)


if __name__ == "__main__":
    # Accept optional client ID as command-line argument
    # Default: riverside_home_goods
    client_arg = next(
        (a for a in sys.argv[1:] if not a.startswith("--")),
        "riverside_home_goods"
    )
    run(client_arg)
