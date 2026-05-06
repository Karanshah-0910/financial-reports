"""
anomaly_check.py
----------------
Quality control layer. Run this before approving any client report.

Compares the latest month's data against the prior 6 months and flags
anything suspicious: statistical outliers, missing values, zeros where
there should be numbers, and data integrity issues.

HOW TO USE:
  # Check one client before approving their report
  python anomaly_check.py riverside_home_goods

  # Check all active clients
  python anomaly_check.py --all

  # Check and automatically block reports with CRITICAL flags
  python anomaly_check.py riverside_home_goods --strict

OUTPUT:
  - Prints a QC summary to the screen (pass / review / block)
  - Saves a detailed QC report to reports/{Client}/QC_{YYYY-MM}.txt
  - Returns exit code 0 (pass), 1 (needs review), or 2 (block — critical issue)

INTEGRATED INTO run_monthly_reports.py:
  Pass --qc-check to run_monthly_reports.py and it will call this
  automatically before finalizing each PDF.

FLAG SEVERITY LEVELS:
  CRITICAL  Something is definitely wrong. Do not send the report.
            Example: Revenue is $0. Total assets are negative.
  WARNING   Something looks unusual. Review before sending.
            Example: Revenue dropped 60% month-over-month.
  INFO      Noteworthy but probably fine. Just be aware.
            Example: A new expense category appeared this month.
"""

import sys
import os
import sqlite3
import pathlib
import datetime
import statistics
import math

ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

from src.analysis.sample_data          import get_sample_data
from src.analysis.sample_balance_sheet import get_sample_balance_sheet
from src.analysis.sample_cash_flow     import get_sample_cash_flow
from src.analysis.analyzer             import run_analysis
from src.analysis.balance_sheet_analyzer import analyze_balance_sheet
from src.analysis.cash_flow_analyzer   import analyze_cash_flow


# ═══════════════════════════════════════════════════════════════════════════════
# FLAG SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

CRITICAL = "CRITICAL"
WARNING  = "WARNING"
INFO     = "INFO"


class Flag:
    def __init__(self, severity: str, category: str, message: str,
                 value=None, context: str = ""):
        self.severity = severity   # CRITICAL / WARNING / INFO
        self.category = category   # e.g. "Revenue", "Expenses", "Data Integrity"
        self.message  = message    # Plain-English description
        self.value    = value      # The actual number that triggered this
        self.context  = context    # Extra detail (e.g. "6-month average was $X")

    def __str__(self):
        val_str = f"  (value: {self.value})" if self.value is not None else ""
        ctx_str = f"\n       Context : {self.context}" if self.context else ""
        return f"  [{self.severity}] {self.category}: {self.message}{val_str}{ctx_str}"


class QCResult:
    def __init__(self, client_id: str, business_name: str, period: str):
        self.client_id     = client_id
        self.business_name = business_name
        self.period        = period
        self.flags: list[Flag] = []
        self.checks_run    = 0
        self.timestamp     = datetime.datetime.now()

    def add(self, severity: str, category: str, message: str,
            value=None, context: str = ""):
        self.flags.append(Flag(severity, category, message, value, context))

    @property
    def criticals(self): return [f for f in self.flags if f.severity == CRITICAL]
    @property
    def warnings(self):  return [f for f in self.flags if f.severity == WARNING]
    @property
    def infos(self):     return [f for f in self.flags if f.severity == INFO]

    @property
    def verdict(self) -> str:
        if self.criticals: return "BLOCK"
        if self.warnings:  return "REVIEW"
        return "PASS"

    @property
    def exit_code(self) -> int:
        return {" BLOCK": 2, "REVIEW": 1, "PASS": 0}.get(self.verdict, 0)


# ═══════════════════════════════════════════════════════════════════════════════
# STATISTICAL HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _zscore(value: float, history: list[float]) -> float:
    """
    How many standard deviations is 'value' from the historical average?
    Z-score of 2.0 means the value is 2 standard deviations away — unusual.
    Z-score of 3.0+ means extremely unusual.
    """
    if len(history) < 2:
        return 0.0
    try:
        mean = statistics.mean(history)
        stdev = statistics.stdev(history)
        if stdev == 0:
            return 0.0
        return abs((value - mean) / stdev)
    except Exception:
        return 0.0


def _pct_change(new: float, old: float) -> float:
    """Percentage change from old to new. Returns 0 if old is 0."""
    if old == 0:
        return 0.0
    return ((new - old) / abs(old)) * 100


def _fmt(val: float) -> str:
    """Format a dollar amount."""
    if val < 0:
        return f"(${abs(val):,.0f})"
    return f"${val:,.0f}"


# ═══════════════════════════════════════════════════════════════════════════════
# INDIVIDUAL CHECK FUNCTIONS
# Each returns nothing — they call result.add() to record flags.
# ═══════════════════════════════════════════════════════════════════════════════

def check_revenue(result: QCResult, summary_df, months: list):
    """Revenue checks: zero, negative, large swings, statistical outliers."""
    latest = months[-1]
    rev    = float(summary_df.loc["Total Revenue", latest])

    # -- Hard stop: zero or negative revenue
    if rev <= 0:
        result.add(CRITICAL, "Revenue",
                   f"Revenue is {_fmt(rev)} in {latest}. "
                   f"This is almost certainly a data error.",
                   value=_fmt(rev))
        return   # No point running trend checks on $0

    # -- Needs at least 2 months to compare
    if len(months) < 2:
        result.add(INFO, "Revenue", "Only one month of data — cannot run trend checks.")
        return

    history = [float(summary_df.loc["Total Revenue", m]) for m in months[:-1]]
    prev    = history[-1]
    mom_pct = _pct_change(rev, prev)
    z       = _zscore(rev, history)
    avg     = statistics.mean(history)

    # -- Statistical outlier (> 2 std dev from 6-month average)
    if z >= 3.0:
        result.add(CRITICAL, "Revenue",
                   f"Revenue {_fmt(rev)} is {z:.1f} standard deviations "
                   f"from the {len(history)}-month average.",
                   value=_fmt(rev),
                   context=f"{len(history)}-month average: {_fmt(avg)}")
    elif z >= 2.0:
        result.add(WARNING, "Revenue",
                   f"Revenue {_fmt(rev)} is unusually high or low "
                   f"({z:.1f} std dev from average).",
                   value=_fmt(rev),
                   context=f"{len(history)}-month average: {_fmt(avg)}")

    # -- Large month-over-month drop
    if mom_pct <= -40:
        result.add(CRITICAL, "Revenue",
                   f"Revenue fell {abs(mom_pct):.0f}% vs last month. "
                   f"Confirm this is real before sending.",
                   value=f"{mom_pct:+.1f}%",
                   context=f"Last month: {_fmt(prev)}  |  This month: {_fmt(rev)}")
    elif mom_pct <= -20:
        result.add(WARNING, "Revenue",
                   f"Revenue dropped {abs(mom_pct):.0f}% vs last month.",
                   value=f"{mom_pct:+.1f}%",
                   context=f"Last month: {_fmt(prev)}  |  This month: {_fmt(rev)}")

    # -- Very large spike (possible duplicate transactions)
    if mom_pct >= 80:
        result.add(WARNING, "Revenue",
                   f"Revenue jumped {mom_pct:.0f}% vs last month. "
                   f"Check for duplicate transactions.",
                   value=f"+{mom_pct:.0f}%",
                   context=f"Last month: {_fmt(prev)}  |  This month: {_fmt(rev)}")

    result.checks_run += 3


def check_expenses(result: QCResult, summary_df, months: list):
    """Expense checks: zero total, large swings, growing faster than revenue."""
    latest = months[-1]
    exp    = float(summary_df.loc["Total Expenses", latest])
    rev    = float(summary_df.loc["Total Revenue",  latest])

    # -- Zero expenses is suspicious (almost every business has some)
    if exp == 0:
        result.add(WARNING, "Expenses",
                   "Total expenses are $0. Check that expense accounts are mapped correctly.")

    if len(months) < 2:
        result.checks_run += 1
        return

    history = [float(summary_df.loc["Total Expenses", m]) for m in months[:-1]]
    prev    = history[-1]
    mom_pct = _pct_change(exp, prev)
    z       = _zscore(exp, history)
    avg     = statistics.mean(history) if history else 0

    # -- Statistical outlier
    if z >= 3.0:
        result.add(CRITICAL, "Expenses",
                   f"Total expenses {_fmt(exp)} are {z:.1f} std dev from average. "
                   f"Possible data entry error or one-time charge.",
                   value=_fmt(exp),
                   context=f"{len(history)}-month average: {_fmt(avg)}")
    elif z >= 2.0:
        result.add(WARNING, "Expenses",
                   f"Total expenses {_fmt(exp)} are unusually high ({z:.1f} std dev).",
                   value=_fmt(exp),
                   context=f"{len(history)}-month average: {_fmt(avg)}")

    # -- Expenses exceed revenue (losing money)
    if exp > rev > 0:
        ratio = exp / rev
        if ratio > 1.5:
            result.add(CRITICAL, "Expenses",
                       f"Expenses are {ratio:.1f}x revenue. Business losing money heavily.",
                       context=f"Revenue: {_fmt(rev)}  |  Expenses: {_fmt(exp)}")
        else:
            result.add(WARNING, "Expenses",
                       f"Expenses exceed revenue this month.",
                       context=f"Revenue: {_fmt(rev)}  |  Expenses: {_fmt(exp)}")

    # -- Expense spike
    if mom_pct >= 50:
        result.add(WARNING, "Expenses",
                   f"Expenses jumped {mom_pct:.0f}% vs last month. "
                   f"Check for duplicate or misposted transactions.",
                   value=f"+{mom_pct:.0f}%",
                   context=f"Last month: {_fmt(prev)}  |  This month: {_fmt(exp)}")

    result.checks_run += 3


def check_margins(result: QCResult, summary_df, months: list):
    """Margin checks: negative gross margin, large swings in profitability."""
    latest      = months[-1]
    gross_m     = float(summary_df.loc["Gross Margin %", latest])
    net_m       = float(summary_df.loc["Net Margin %",   latest])
    gross_profit = float(summary_df.loc["Gross Profit",  latest])

    # -- Negative gross margin = selling below cost
    if gross_profit < 0:
        result.add(CRITICAL, "Gross Margin",
                   f"Gross profit is negative ({_fmt(gross_profit)}). "
                   f"Revenue is less than cost of goods — verify COGS mapping.",
                   value=_fmt(gross_profit))

    if len(months) < 2:
        result.checks_run += 2
        return

    history_gm  = [float(summary_df.loc["Gross Margin %", m]) for m in months[:-1]]
    history_nm  = [float(summary_df.loc["Net Margin %",   m]) for m in months[:-1]]
    prev_gm     = history_gm[-1]
    prev_nm     = history_nm[-1]
    z_gm        = _zscore(gross_m, history_gm)
    z_nm        = _zscore(net_m,   history_nm)

    # -- Gross margin collapsed
    gm_drop = prev_gm - gross_m
    if gm_drop >= 15:
        result.add(CRITICAL, "Gross Margin",
                   f"Gross margin fell {gm_drop:.1f} percentage points "
                   f"({prev_gm:.1f}% -> {gross_m:.1f}%). "
                   f"Verify COGS is correct.",
                   context=f"A drop this large usually means a data error, "
                            f"not a real business change.")
    elif gm_drop >= 8:
        result.add(WARNING, "Gross Margin",
                   f"Gross margin dropped {gm_drop:.1f}pp ({prev_gm:.1f}% -> {gross_m:.1f}%).",
                   context=f"Worth understanding why before the report goes out.")

    # -- Net margin outlier
    if z_nm >= 2.0:
        avg_nm = statistics.mean(history_nm)
        result.add(WARNING, "Net Margin",
                   f"Net margin {net_m:.1f}% is {z_nm:.1f} std dev from "
                   f"{len(history_nm)}-month average ({avg_nm:.1f}%).")

    result.checks_run += 2


def check_line_items(result: QCResult, detail_df, months: list):
    """
    Line-item level checks.
    - Flags any single line item that moved > 2 std dev
    - Flags line items that appeared or disappeared vs last month
    - Flags suspiciously round numbers (possible estimates, not actuals)
    """
    if len(months) < 2:
        result.checks_run += 1
        return

    latest = months[-1]
    prev   = months[-2]

    latest_items  = set(detail_df[detail_df[latest] != 0].index.tolist())
    prev_items    = set(detail_df[detail_df[prev]   != 0].index.tolist())

    # -- New line items that didn't exist before
    new_items = latest_items - prev_items
    for item in sorted(new_items):
        val = float(detail_df.loc[item, latest])
        if abs(val) > 500:   # Ignore tiny amounts
            result.add(INFO, "New Line Item",
                       f"'{item}' appeared for the first time this month.",
                       value=_fmt(val),
                       context="Verify this is a real new account, not a mapping error.")

    # -- Line items that vanished
    gone_items = prev_items - latest_items
    for item in sorted(gone_items):
        val = float(detail_df.loc[item, prev])
        if abs(val) > 1000:   # Only flag meaningful amounts
            result.add(INFO, "Missing Line Item",
                       f"'{item}' was {_fmt(val)} last month but is $0 this month.",
                       context="Expected? Or did something stop posting?")

    # -- Per-line statistical outliers (only check items with history)
    history_months = months[:-1]
    if len(history_months) >= 3:
        for item in latest_items:
            try:
                current = float(detail_df.loc[item, latest])
                history = [float(detail_df.loc[item, m])
                           for m in history_months
                           if item in detail_df.index]
                history = [v for v in history if v != 0]

                if len(history) < 2 or current == 0:
                    continue

                z = _zscore(current, history)
                if z >= 3.0 and abs(current) > 1000:
                    avg = statistics.mean(history)
                    result.add(WARNING, "Line Item Spike",
                               f"'{item}' is {z:.1f} std dev from its average.",
                               value=_fmt(current),
                               context=f"Historical average: {_fmt(avg)}")
            except Exception:
                continue

    # -- Suspiciously round numbers (potential manual estimates)
    for item in latest_items:
        val = float(detail_df.loc[item, latest])
        if abs(val) >= 5000 and val % 1000 == 0:
            result.add(INFO, "Round Number",
                       f"'{item}' is exactly {_fmt(val)} — "
                       f"could be an estimate rather than an actual figure.",
                       context="Fine if it's a fixed cost like rent. Worth noting otherwise.")

    result.checks_run += 3


def check_balance_sheet(result: QCResult, bs_analysis: dict):
    """Balance sheet integrity checks."""
    total_assets = bs_analysis.get("total_assets",      0) or 0
    total_liab   = bs_analysis.get("total_liabilities", 0) or 0
    cash         = bs_analysis.get("cash_balance",      0) or 0
    curr_ratio   = bs_analysis.get("current_ratio",     0) or 0
    ar_days      = bs_analysis.get("ar_days",           0) or 0

    # -- Negative total assets = serious data problem
    if total_assets < 0:
        result.add(CRITICAL, "Balance Sheet",
                   f"Total assets are negative ({_fmt(total_assets)}). "
                   f"This is a data error — check account mappings.",
                   value=_fmt(total_assets))

    # -- Cash is negative (possible, but flag it)
    if cash < 0:
        result.add(WARNING, "Cash",
                   f"Cash balance is negative ({_fmt(cash)}). "
                   f"Overdraft or unreconciled transactions?",
                   value=_fmt(cash))

    # -- Current ratio below 1.0 = can't cover short-term bills
    if 0 < curr_ratio < 1.0:
        result.add(WARNING, "Liquidity",
                   f"Current ratio is {curr_ratio:.2f} (below 1.0). "
                   f"Current liabilities exceed current assets.",
                   context="The business may struggle to pay bills due within 90 days.")

    # -- AR days very high = revenue may be overstated (not yet collected)
    if ar_days > 90:
        result.add(WARNING, "Accounts Receivable",
                   f"AR days outstanding = {ar_days:.0f} days. "
                   f"Revenue may include uncollected invoices over 90 days old.",
                   context="High AR days can inflate revenue figures temporarily.")

    # -- Assets = Liabilities + Equity (basic accounting equation)
    equity = bs_analysis.get("total_equity", None)
    if equity is not None and total_assets > 0:
        implied_equity = total_assets - total_liab
        if abs(implied_equity - equity) > 100:   # $100 tolerance for rounding
            result.add(WARNING, "Balance Sheet",
                       f"Balance sheet doesn't balance. "
                       f"Assets ({_fmt(total_assets)}) != "
                       f"Liabilities ({_fmt(total_liab)}) + "
                       f"Equity ({_fmt(equity)}).",
                       context="Could be rounding in QB export or unmapped accounts.")

    result.checks_run += 4


def check_cash_flow(result: QCResult, cf_analysis: dict):
    """Cash flow integrity checks."""
    ocf    = cf_analysis.get("operating_cash_flow", 0) or 0
    fcf    = cf_analysis.get("free_cash_flow",      0) or 0
    runway = cf_analysis.get("cash_runway_months",  0) or 0
    burn   = cf_analysis.get("monthly_burn_rate",   0) or 0

    # -- Cash runway under 2 months = emergency
    if 0 < runway < 2:
        result.add(CRITICAL, "Cash Flow",
                   f"Cash runway is {runway:.1f} months. "
                   f"This needs to be addressed in the report.",
                   value=f"{runway:.1f} months",
                   context="Client may not be able to cover next month's payroll.")

    # -- Burn rate check
    if burn > 0 and ocf < 0:
        result.add(WARNING, "Cash Flow",
                   f"Operating cash flow is negative ({_fmt(ocf)}). "
                   f"Business is burning cash from operations.",
                   value=_fmt(ocf))

    result.checks_run += 2


def check_data_completeness(result: QCResult, detail_df, months: list):
    """
    Data completeness checks.
    - Flags if the number of line items dropped significantly vs last month
    - Flags if a whole month's data looks empty
    - Flags months with suspiciously identical totals (possible copy-paste)
    """
    latest = months[-1]

    # -- Empty month check
    total_vals = detail_df[latest].abs().sum()
    if total_vals == 0:
        result.add(CRITICAL, "Data Completeness",
                   f"All values for {latest} are zero. "
                   f"Data may not have loaded correctly.",
                   context="Re-pull from QuickBooks before proceeding.")
        return

    # -- Line item count dropped significantly
    if len(months) >= 2:
        prev   = months[-2]
        latest_count = (detail_df[latest] != 0).sum()
        prev_count   = (detail_df[prev]   != 0).sum()
        if prev_count > 5 and latest_count < prev_count * 0.5:
            result.add(WARNING, "Data Completeness",
                       f"Number of line items dropped from {prev_count} to "
                       f"{latest_count} vs last month.",
                       context="Half the accounts may be missing. Check QB data pull.")

    # -- Duplicate month check (two months with identical totals)
    if len(months) >= 2:
        month_totals = {m: round(detail_df[m].abs().sum(), 0) for m in months}
        seen = {}
        for m, total in month_totals.items():
            if total in seen and total > 1000:
                result.add(WARNING, "Duplicate Data",
                           f"Months '{seen[total]}' and '{m}' have identical totals "
                           f"({_fmt(total)}). Possible data duplication.",
                           context="Re-pull both months from QuickBooks to verify.")
            seen[total] = m

    result.checks_run += 3


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN QC RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

def run_qc(client_id: str,
           analysis: dict,
           bs_analysis: dict,
           cf_analysis: dict) -> QCResult:
    """
    Run all quality checks on a fully-analyzed client dataset.
    Returns a QCResult with all flags.
    """
    summary_df = analysis["summary_df"]
    detail_df  = analysis["detail_df"]
    months     = analysis["all_months"]
    latest     = analysis["latest_month"]
    biz        = analysis["business_name"]

    result = QCResult(client_id, biz, latest)

    # Run all checks
    check_data_completeness(result, detail_df, months)
    check_revenue(result, summary_df, months)
    check_expenses(result, summary_df, months)
    check_margins(result, summary_df, months)
    check_line_items(result, detail_df, months)
    check_balance_sheet(result, bs_analysis)
    check_cash_flow(result, cf_analysis)

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# QC REPORT — written to file and printed to screen
# ═══════════════════════════════════════════════════════════════════════════════

def _render_report(result: QCResult) -> str:
    """Build the full QC report as a plain-text string."""
    lines = []
    bar   = "=" * 62

    lines += [
        bar,
        f"  QC REPORT — {result.business_name}",
        f"  Period    : {result.period}",
        f"  Run at    : {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
        f"  Checks run: {result.checks_run}",
        bar,
        "",
    ]

    # Verdict banner
    if result.verdict == "PASS":
        lines += [
            "  VERDICT: PASS",
            "  No issues found. Report is safe to finalize.",
            "",
        ]
    elif result.verdict == "REVIEW":
        lines += [
            "  VERDICT: NEEDS REVIEW",
            f"  {len(result.warnings)} warning(s) found. Review before sending.",
            "",
        ]
    else:
        lines += [
            "  VERDICT: BLOCKED",
            f"  {len(result.criticals)} critical issue(s) found.",
            "  DO NOT send this report until issues are resolved.",
            "",
        ]

    # Flags by severity
    for severity, flags, heading in [
        (CRITICAL, result.criticals, "CRITICAL ISSUES — Fix before sending"),
        (WARNING,  result.warnings,  "WARNINGS — Review before sending"),
        (INFO,     result.infos,     "INFO — Notes for your awareness"),
    ]:
        if not flags:
            continue
        lines += ["", f"  {heading}", "  " + "-" * 50]
        for f in flags:
            lines.append(str(f))
        lines.append("")

    if not result.flags:
        lines += ["  All checks passed cleanly.", ""]

    # Summary counts
    lines += [
        bar,
        f"  Summary: {len(result.criticals)} critical  |  "
        f"{len(result.warnings)} warnings  |  "
        f"{len(result.infos)} info",
        bar,
    ]

    return "\n".join(lines)


def save_qc_report(result: QCResult) -> pathlib.Path:
    """Save the QC report to reports/{Client}/QC_{YYYY-MM}.txt"""
    biz_folder = result.business_name.replace(" ", "_")
    folder = ROOT / "reports" / biz_folder
    folder.mkdir(parents=True, exist_ok=True)

    try:
        ym = datetime.datetime.strptime(result.period, "%B %Y").strftime("%Y-%m")
    except Exception:
        ym = result.period.replace(" ", "-")

    path = folder / f"QC_{ym}.txt"
    path.write_text(_render_report(result), encoding="utf-8")
    return path


# ═══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def _load_active_clients() -> list[dict]:
    db = ROOT / "clients.db"
    if not db.exists():
        return []
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM clients WHERE status = 'active'"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _run_for_client(client_id: str) -> QCResult:
    """Load data for one client and run all QC checks."""
    # Try QB tokens first, fall back to sample data
    pnl_data = bs_data = cf_data = None
    try:
        from src.quickbooks.auth      import tokens_exist
        from src.quickbooks.data_pull import get_pnl_last_3_months, get_balance_sheet, get_cash_flow
        import datetime as dt
        today = dt.date.today()
        month = today.month - 1 or 12
        year  = today.year if today.month > 1 else today.year - 1
        if tokens_exist(client_id):
            biz = client_id.replace("_", " ").title()
            pnl_data = get_pnl_last_3_months(client_id, biz, year, month)
            bs_data  = get_balance_sheet(client_id, biz, year, month)
            cf_data  = get_cash_flow(client_id, biz, year, month)
    except Exception:
        pass

    if not pnl_data:
        pnl_data = get_sample_data(client_id)
        bs_data  = get_sample_balance_sheet(client_id)
        cf_data  = get_sample_cash_flow(client_id)

    analysis    = run_analysis(pnl_data)
    latest      = analysis["latest_month"]
    monthly_rev = float(analysis["summary_df"].loc["Total Revenue",      latest])
    monthly_cogs= float(analysis["summary_df"].loc["Cost of Goods Sold", latest])
    bs_analysis = analyze_balance_sheet(bs_data,
                                        monthly_revenue=monthly_rev,
                                        monthly_cogs=monthly_cogs)
    cf_analysis = analyze_cash_flow(analysis, bs_analysis, cf_data)

    return run_qc(client_id, analysis, bs_analysis, cf_analysis)


def main():
    args    = sys.argv[1:]
    run_all = "--all" in args
    strict  = "--strict" in args
    client_id = next((a for a in args if not a.startswith("--")), None)

    if not run_all and not client_id:
        print(__doc__)
        sys.exit(0)

    targets = []
    if run_all:
        targets = _load_active_clients()
        if not targets:
            print("No active clients found in clients.db")
            sys.exit(0)
        client_ids = [c["client_id"] for c in targets]
    else:
        client_ids = [client_id]

    worst_exit = 0
    all_results = []

    for cid in client_ids:
        print(f"\nRunning QC for {cid}...")
        try:
            result = _run_for_client(cid)
        except Exception as e:
            print(f"  ERROR running QC for {cid}: {e}")
            continue

        # Print report
        report_text = _render_report(result)
        print(report_text)

        # Save to file
        path = save_qc_report(result)
        print(f"\n  QC report saved: {path}")

        all_results.append(result)
        worst_exit = max(worst_exit, result.exit_code)

    # Batch summary when running --all
    if run_all and len(all_results) > 1:
        print("\n" + "=" * 62)
        print("  BATCH QC SUMMARY")
        print("=" * 62)
        for r in all_results:
            icon = {"PASS": "OK  ", "REVIEW": "WARN", "BLOCK": "STOP"}.get(r.verdict, "    ")
            print(f"  {icon}  {r.business_name:<30} {r.verdict}")
            if r.criticals:
                print(f"        {len(r.criticals)} critical issue(s)")
        print()

    if strict and worst_exit > 0:
        sys.exit(worst_exit)
    sys.exit(0)


if __name__ == "__main__":
    main()
