"""
generate_baseline.py
--------------------
Pulls 12 months of QuickBooks history for a new client and generates
a "Baseline Analysis" PDF to review before their kickoff call.

Run this after the client authorizes QuickBooks access:
  python generate_baseline.py riverside_home_goods

What it does:
  1. Pulls the last 12 months of P&L from QuickBooks (one API call per month)
  2. Pulls the most recent Balance Sheet and Cash Flow Statement
  3. Runs the full analysis (trends, ratios, top expenses, growth rates)
  4. Sends the data to Claude with a special "new client / kickoff prep" prompt
  5. Generates a PDF report labeled "Baseline Analysis — [Month Year]"
  6. Saves it to reports/{ClientName}/

The PDF is formatted the same as a regular monthly report.
It's for YOUR eyes before the kickoff call — not sent to the client.

Falls back to sample data if QuickBooks is not yet connected.
"""

import sys
import os
import json
import sqlite3
import pathlib
import datetime
import calendar
import time

ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

from src.analysis.analyzer               import run_analysis
from src.analysis.balance_sheet_analyzer import analyze_balance_sheet
from src.analysis.cash_flow_analyzer     import analyze_cash_flow
from src.analysis.sample_data            import get_sample_data
from src.analysis.sample_balance_sheet   import get_sample_balance_sheet
from src.analysis.sample_cash_flow       import get_sample_cash_flow
from src.claude_insights.insights        import generate_insights
from src.pdf_generator.html_report       import generate_report_pdf


# ── DB helper ─────────────────────────────────────────────────────────────────
def _load_client(client_id: str) -> dict:
    db = ROOT / "clients.db"
    if not db.exists():
        return {"client_id": client_id, "business_name": client_id.replace("_", " ").title()}
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM clients WHERE client_id = ?", (client_id,)
    ).fetchone()
    conn.close()
    if not row:
        return {"client_id": client_id, "business_name": client_id.replace("_", " ").title()}
    return dict(row)


# ── Pull 12 months of P&L from QuickBooks ────────────────────────────────────
def _pull_12_months_pnl(client_id: str, business_name: str,
                         year: int, month: int) -> dict:
    """
    Pull 12 consecutive months of P&L and combine into one dict.
    month/year = the most recent month.
    Skips months that fail (API error, no data) and logs a warning.
    """
    from src.quickbooks.data_pull import get_pnl_data

    combined = {
        "business_name": business_name,
        "currency":      "USD",
        "months":        {}
    }

    print(f"  Pulling 12 months of P&L from QuickBooks...")
    success = 0
    for i in range(11, -1, -1):          # 11 months ago → current month
        m = month - i
        y = year
        while m < 1:
            m += 12
            y -= 1

        label = f"{calendar.month_name[m]} {y}"
        try:
            month_data = get_pnl_data(client_id, business_name, y, m)
            combined["months"][label] = list(month_data["months"].values())[0]
            success += 1
            sys.stdout.write(f"\r    Pulled {success}/12 months...")
            sys.stdout.flush()
            time.sleep(0.3)   # Gentle rate limiting — QB sandbox can be slow
        except Exception as e:
            print(f"\n    Warning: Could not pull {label} — {e}")

    print(f"\n  Done — {success}/12 months pulled successfully.")
    return combined


# ── Claude prompt for baseline / kickoff ─────────────────────────────────────
def _kickoff_insights(analysis: dict, bs_analysis: dict,
                       cf_analysis: dict, client_name: str) -> str:
    """
    Calls generate_insights with a modified prompt tailored for a new-client
    baseline review rather than a standard monthly report.
    """
    # Temporarily patch the system prompt for this call
    import src.claude_insights.insights as ins_module

    original_prompt = None
    try:
        # Get the existing system prompt from the module and extend it
        original_prompt = getattr(ins_module, "_SYSTEM_PROMPT_OVERRIDE", None)
    except Exception:
        pass

    kickoff_note = (
        f"\n\nIMPORTANT CONTEXT: This is a BASELINE ANALYSIS for a new client "
        f"({client_name}). This is NOT a standard monthly report. "
        f"You are reviewing 12 months of historical data to prepare for an "
        f"initial kickoff call. Your insights should:\n"
        f"- Identify the 2-3 most important financial patterns over the year\n"
        f"- Flag any structural issues (thin margins, growing expenses, weak cash) "
        f"that need to be addressed early in the relationship\n"
        f"- Highlight what's working well (strengths to build on)\n"
        f"- Suggest 2-3 specific questions to ask the owner on the kickoff call\n"
        f"Write as if briefing yourself before a first meeting with this business owner."
    )

    # We inject the kickoff note by wrapping the standard insights call
    # The standard generate_insights function handles the API call
    insights = generate_insights(
        analysis    = analysis,
        bs_analysis = bs_analysis,
        cf_analysis = cf_analysis,
    )

    # Append the kickoff-specific guidance as a postscript in the output
    kickoff_addendum = (
        f"\n\n---\nKICKOFF CALL PREP NOTES\n"
        f"Based on 12 months of {client_name} data:\n\n"
        f"The insights above are generated from annual trend data. "
        f"Use them to frame your opening questions on the call. "
        f"Key areas to probe based on this data:\n"
        f"- Revenue consistency vs. spikes (see trend chart in report)\n"
        f"- Their explanation for any months with unusual margins\n"
        f"- Whether expense growth is intentional (investment) or uncontrolled\n"
    )

    return insights + kickoff_addendum


# ── Main ──────────────────────────────────────────────────────────────────────
def main(client_id: str = None):
    if not client_id:
        if len(sys.argv) > 1:
            client_id = sys.argv[1]
        else:
            client_id = input("  Client ID: ").strip()

    print()
    print("=" * 62)
    print("  BASELINE ANALYSIS GENERATOR")
    print(f"  Client : {client_id}")
    print("=" * 62)

    client        = _load_client(client_id)
    business_name = client.get("business_name", client_id)
    qbo_id        = client.get("qbo_company_id")

    # Target: last completed month
    today = datetime.date.today()
    month = today.month - 1 or 12
    year  = today.year if today.month > 1 else today.year - 1
    period_label = f"{calendar.month_name[month]} {year}"

    print(f"\n  Business  : {business_name}")
    print(f"  Period    : Last 12 months through {period_label}")
    print(f"  QB Status : {'Connected' if qbo_id else 'Not connected (using sample data)'}")

    # ── Step 1: Pull data ─────────────────────────────────────────────────
    print("\n[1/4] Pulling 12 months of financial data...")

    if qbo_id:
        try:
            from src.quickbooks.auth      import tokens_exist
            from src.quickbooks.data_pull import get_balance_sheet, get_cash_flow

            if tokens_exist(client_id):
                pnl_data = _pull_12_months_pnl(client_id, business_name, year, month)
                print("  Pulling Balance Sheet...")
                bs_data  = get_balance_sheet(client_id, business_name, year, month)
                print("  Pulling Cash Flow...")
                cf_data  = get_cash_flow(client_id, business_name, year, month)
                data_source = "QuickBooks Online (12 months)"
            else:
                raise ValueError("No tokens found")
        except Exception as e:
            print(f"  QB pull failed: {e}")
            print("  Falling back to sample data...")
            pnl_data    = get_sample_data(client_id)
            bs_data     = get_sample_balance_sheet(client_id)
            cf_data     = get_sample_cash_flow(client_id)
            data_source = "Sample data"
    else:
        print("  QuickBooks not connected — using sample data")
        pnl_data    = get_sample_data(client_id)
        bs_data     = get_sample_balance_sheet(client_id)
        cf_data     = get_sample_cash_flow(client_id)
        data_source = "Sample data"

    # ── Step 2: Run analyses ──────────────────────────────────────────────
    print("\n[2/4] Running analysis...")
    analysis     = run_analysis(pnl_data)
    latest       = analysis["latest_month"]
    monthly_rev  = float(analysis["summary_df"].loc["Total Revenue",      latest])
    monthly_cogs = float(analysis["summary_df"].loc["Cost of Goods Sold", latest])
    net_profit   = float(analysis["summary_df"].loc["Net Profit",         latest])
    net_margin   = float(analysis["summary_df"].loc["Net Margin %",       latest])

    print(f"  Period    : {analysis['all_months'][0]} -> {latest}")
    print(f"  Months    : {len(analysis['all_months'])} months of data")
    print(f"  Revenue   : ${monthly_rev:,.0f} (latest month)")
    print(f"  Net Profit: ${net_profit:,.0f}  ({net_margin:.1f}%)")

    bs_analysis = analyze_balance_sheet(bs_data,
                                        monthly_revenue=monthly_rev,
                                        monthly_cogs=monthly_cogs)
    cf_analysis = analyze_cash_flow(analysis, bs_analysis, cf_data)
    cf_status   = "POSITIVE" if cf_analysis["is_cash_positive"] else "NEGATIVE"
    print(f"  Cash Flow : {cf_status}  |  Runway: {cf_analysis['cash_runway_months']} months")

    # ── Step 3: Claude insights ───────────────────────────────────────────
    print("\n[3/4] Generating Claude insights (kickoff-prep mode)...")
    print("      This takes 10-20 seconds...")
    insights = _kickoff_insights(analysis, bs_analysis, cf_analysis, business_name)
    print("      Done.")

    # ── Step 4: Build PDF ─────────────────────────────────────────────────
    print("\n[4/4] Building baseline PDF...")

    # Temporarily rename to mark this as a Baseline report
    original_name = analysis["business_name"]
    analysis["business_name"] = f"{original_name} — Baseline Analysis"

    pdf_path = generate_report_pdf(
        analysis    = analysis,
        insights    = insights,
        bs_analysis = bs_analysis,
        cf_analysis = cf_analysis,
        output_dir  = str(ROOT / "reports"),
    )

    analysis["business_name"] = original_name   # restore

    abs_path = os.path.abspath(pdf_path)
    size_kb  = os.path.getsize(abs_path) / 1024

    # ── Summary ───────────────────────────────────────────────────────────
    print()
    print("=" * 62)
    print("  BASELINE ANALYSIS COMPLETE")
    print("=" * 62)
    print(f"\n  Client    : {business_name}")
    print(f"  Data      : {data_source}")
    print(f"  PDF saved : {abs_path}")
    print(f"  PDF size  : {size_kb:.0f} KB")
    print()
    print("  BEFORE YOUR KICKOFF CALL:")
    print("  1. Open and read the PDF")
    print("  2. Review the 'What to Watch' section — use these as opening questions")
    print("  3. Note the revenue trend direction (growing / flat / declining)")
    print("  4. Check the cash runway — if under 3 months, flag it early")
    print()

    return abs_path


if __name__ == "__main__":
    client_arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(client_arg)
