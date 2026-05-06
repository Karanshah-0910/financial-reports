"""
generate_all_reports.py
-----------------------
Full pipeline: QuickBooks (or sample) data -> analysis -> Claude -> PDF -> email.
Now includes Balance Sheet alongside P&L.

How to run:
  python generate_all_reports.py                        <- all clients
  python generate_all_reports.py riverside_home_goods   <- one client
  python generate_all_reports.py --no-email             <- skip email
"""

import sys
import os
import traceback
from datetime import datetime

from src.clients.client_manager import load_all_clients, load_client
from src.analysis.sample_data import get_sample_data
from src.analysis.sample_balance_sheet import get_sample_balance_sheet
from src.analysis.sample_cash_flow import get_sample_cash_flow
from src.analysis.analyzer import run_analysis
from src.analysis.balance_sheet_analyzer import analyze_balance_sheet
from src.analysis.cash_flow_analyzer import analyze_cash_flow
from src.claude_insights.insights import generate_insights
from src.pdf_generator.generator import generate_pdf
from src.email_delivery.emailer import send_report


def get_financial_data(client: dict) -> tuple:
    """
    Returns (pnl_data, balance_sheet_data, cash_flow_data).
    Uses QuickBooks if tokens exist, otherwise sample data.
    """
    client_id     = client["client_id"]
    business_name = client["business_name"]

    try:
        from src.quickbooks.auth import tokens_exist
        from src.quickbooks.data_pull import get_pnl_last_3_months, get_balance_sheet

        if tokens_exist(client_id):
            print(f"  Data source : QuickBooks Online (live data)")
            now = datetime.now()
            pnl = get_pnl_last_3_months(client_id, business_name, now.year, now.month)
            bs  = get_balance_sheet(client_id, business_name, now.year, now.month)
            # Cash flow supplement not yet available from QB — use sample as fallback
            cf  = get_sample_cash_flow(client_id)
            return pnl, bs, cf
    except Exception as e:
        print(f"  QuickBooks pull failed ({e}) — using sample data")

    print(f"  Data source : Sample data (QuickBooks not connected)")
    return (get_sample_data(client_id),
            get_sample_balance_sheet(client_id),
            get_sample_cash_flow(client_id))


def run_for_client(client: dict, send_email: bool = True) -> dict:
    """Run the full pipeline for one client."""
    business  = client["business_name"]
    client_id = client["client_id"]

    print(f"\n  {'-' * 50}")
    print(f"  Client : {business}")
    print(f"  {'-' * 50}")

    # Step 1: Load and analyze financial data
    print(f"  [1/5] Loading financial data...")
    pnl_data, bs_data, cf_data = get_financial_data(client)

    analysis = run_analysis(pnl_data)
    print(f"        P&L period : {analysis['all_months'][0]} -> {analysis['latest_month']}")

    # Pass monthly revenue and COGS so AR/AP days are calculated correctly
    latest       = analysis["latest_month"]
    monthly_rev  = float(analysis["summary_df"].loc["Total Revenue",      latest])
    monthly_cogs = float(analysis["summary_df"].loc["Cost of Goods Sold", latest])
    bs_analysis  = analyze_balance_sheet(bs_data,
                                         monthly_revenue=monthly_rev,
                                         monthly_cogs=monthly_cogs)
    print(f"        Balance Sheet as of: {bs_analysis['as_of_date']}")

    cf_analysis = analyze_cash_flow(analysis, bs_analysis, cf_data)
    status      = "POSITIVE" if cf_analysis["is_cash_positive"] else "NEGATIVE"
    print(f"        Cash Flow : {status}  |  Runway: {cf_analysis['cash_runway_months']} months")

    # Step 2: Claude insights (P&L + Balance Sheet + Cash Flow context)
    print(f"  [2/5] Generating Claude insights...")
    insights = generate_insights(analysis,
                                 client_config=client,
                                 bs_analysis=bs_analysis,
                                 cf_analysis=cf_analysis)

    # Step 3: Build PDF (all three sections)
    print(f"  [3/5] Building PDF...")
    pdf_path = generate_pdf(analysis, insights,
                            bs_analysis=bs_analysis,
                            cf_analysis=cf_analysis)
    abs_path = os.path.abspath(pdf_path)
    print(f"        Saved -> {abs_path}")

    # Step 4: Send email
    if send_email:
        print(f"  [4/5] Sending email to {client['email']}...")
        emailed = send_report(client, analysis, pdf_path)
    else:
        print(f"  [4/5] Skipping email (--no-email flag)")
        emailed = False

    print(f"  [5/5] Done!")

    return {
        "client":   business,
        "pdf_path": abs_path,
        "emailed":  emailed,
    }


def main():
    start_time = datetime.now()
    args       = sys.argv[1:]
    no_email   = "--no-email" in args
    client_arg = next((a for a in args if not a.startswith("--")), None)

    print("=" * 60)
    print("  FINANCIAL REPORTS - MULTI-CLIENT RUN")
    print(f"  Started : {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Email   : {'disabled' if no_email else 'enabled'}")
    print("=" * 60)

    if client_arg:
        try:
            clients = [load_client(client_arg)]
        except ValueError as e:
            print(f"\nError: {e}")
            sys.exit(1)
    else:
        clients = load_all_clients()

    if not clients:
        print("\nNo active clients found.")
        sys.exit(0)

    print(f"\nFound {len(clients)} active client(s).")

    results  = []
    failures = []

    for client in clients:
        try:
            result = run_for_client(client, send_email=not no_email)
            results.append(result)
        except Exception as e:
            failures.append((client["business_name"], str(e)))
            print(f"\n  !! Error for {client['business_name']}:")
            traceback.print_exc()

    elapsed = (datetime.now() - start_time).seconds
    print(f"\n{'=' * 60}")
    print(f"  DONE - {len(results)} report(s) in {elapsed}s")
    print(f"{'=' * 60}")

    for r in results:
        email_status = "emailed" if r["emailed"] else "not sent"
        print(f"  OK  {r['client']}  |  {email_status}")
        print(f"      {r['pdf_path']}")

    if failures:
        print(f"\n  {len(failures)} failure(s):")
        for name, err in failures:
            print(f"  FAIL  {name}: {err}")


if __name__ == "__main__":
    main()
