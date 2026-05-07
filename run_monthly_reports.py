"""
run_monthly_reports.py
----------------------
Master orchestration script. Runs the full reporting pipeline for every
active client in clients.db, then emails YOU a batch summary.

HOW TO RUN:
  python run_monthly_reports.py                   # All active clients
  python run_monthly_reports.py --dry-run         # Preview only — no reports built
  python run_monthly_reports.py --client riverside_home_goods  # One client only
  python run_monthly_reports.py --sample          # Force sample data (skip QB pull)
  python run_monthly_reports.py --no-email        # Skip ALL emails (owner + clients)
  python run_monthly_reports.py --send-clients    # Also email each client their PDF

PIPELINE PER CLIENT:
  1. Load client profile from clients.db
  2. Pull P&L (3-month), Balance Sheet, Cash Flow from QuickBooks
     (falls back to sample data if QB is not connected)
  3. Run all three analyses (P&L, balance sheet, cash flow)
  4. QC anomaly check — blocks report if critical issues found
  5. Generate Claude AI insights
  6. Build PDF report
  7. Save to reports/{ClientName}/{YYYY-MM}_financial_report.pdf
  8. If --send-clients: email PDF to client's contact_email

OUTPUT:
  - PDF reports in reports/{ClientName}/
  - Log file in logs/{YYYY-MM-DD_HH-MM}_batch.log
  - Summary email to SMTP_USER when batch completes
  - Client emails with PDF attached (only with --send-clients)
"""

import sys
import os
import pathlib
import sqlite3
import logging
import traceback
import smtplib
import datetime
import time
from email.message import EmailMessage
from io import StringIO

# ── Make sure project root is on the path ────────────────────────────────────
ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))

# ── Load .env before any src imports ─────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

# ── Project imports ───────────────────────────────────────────────────────────
from src.analysis.analyzer              import run_analysis
from src.analysis.balance_sheet_analyzer import analyze_balance_sheet
from src.analysis.cash_flow_analyzer    import analyze_cash_flow
from src.analysis.sample_data           import get_sample_data
from src.analysis.sample_balance_sheet  import get_sample_balance_sheet
from src.analysis.sample_cash_flow      import get_sample_cash_flow
from src.claude_insights.insights       import generate_insights
from src.pdf_generator.html_report      import generate_report_pdf


# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING SETUP
# Logs go to both the console AND a file in logs/ so you can debug later.
# ═══════════════════════════════════════════════════════════════════════════════

def _setup_logging() -> tuple[logging.Logger, pathlib.Path]:
    """
    Create a logger that writes to both console and a timestamped log file.
    Returns (logger, log_file_path).
    """
    logs_dir = ROOT / "logs"
    logs_dir.mkdir(exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    log_path  = logs_dir / f"{timestamp}_batch.log"

    logger = logging.getLogger("monthly_reports")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    # File handler — DEBUG level (captures everything)
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S"
    ))

    # Console handler — INFO level (clean progress output)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger, log_path


# ═══════════════════════════════════════════════════════════════════════════════
# CLIENTS.DB — load active clients
# ═══════════════════════════════════════════════════════════════════════════════

DB_PATH = ROOT / "clients.db"


def _load_active_clients(client_id_filter: str = None) -> list[dict]:
    """
    Read active clients from clients.db.
    If client_id_filter is given, return only that one client.
    """
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"clients.db not found at {DB_PATH}\n"
            "Run: python manage_clients.py add"
        )

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    if client_id_filter:
        rows = conn.execute(
            "SELECT * FROM clients WHERE client_id = ?", (client_id_filter,)
        ).fetchall()
        if not rows:
            raise ValueError(
                f"Client '{client_id_filter}' not found in clients.db.\n"
                "Run: python manage_clients.py list"
            )
    else:
        rows = conn.execute(
            "SELECT * FROM clients WHERE status = 'active' ORDER BY business_name"
        ).fetchall()

    conn.close()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════════════════
# DATA PULL — QuickBooks or sample fallback
# ═══════════════════════════════════════════════════════════════════════════════

def _pull_financial_data(client: dict, force_sample: bool,
                         log: logging.Logger) -> tuple[dict, dict, dict, str]:
    """
    Pull P&L (3-month), Balance Sheet, and Cash Flow for this client.
    Returns (pnl_data, bs_data, cf_data, source_label).

    source_label is "QuickBooks" or "sample data" — shown in the log.
    """
    client_id     = client["client_id"]
    business_name = client["business_name"]
    qbo_id        = client.get("qbo_company_id")

    # Determine which month to pull (most recent completed month)
    today = datetime.date.today()
    month = today.month - 1 or 12
    year  = today.year if today.month > 1 else today.year - 1

    if not force_sample and qbo_id:
        try:
            from src.quickbooks.auth      import tokens_exist
            from src.quickbooks.data_pull import (
                get_pnl_last_3_months, get_balance_sheet, get_cash_flow
            )

            if tokens_exist(client_id):
                log.info(f"    Data source  : QuickBooks Online ({year}-{month:02d})")
                pnl = get_pnl_last_3_months(client_id, business_name, year, month)
                bs  = get_balance_sheet(client_id, business_name, year, month)
                cf  = get_cash_flow(client_id, business_name, year, month)
                log.debug(f"    QB pull OK — {sum(len(v) for v in pnl['months'].values())} P&L lines")
                return pnl, bs, cf, "QuickBooks Online"
            else:
                log.warning(f"    No QB tokens for {client_id} — using sample data")
        except Exception as e:
            log.warning(f"    QB pull failed: {e} — falling back to sample data")
            log.debug(traceback.format_exc())

    log.info(f"    Data source  : Sample data (QB not connected)")
    return (
        get_sample_data(client_id),
        get_sample_balance_sheet(client_id),
        get_sample_cash_flow(client_id),
        "Sample data",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLE CLIENT PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def _run_client(client: dict, force_sample: bool,
                dry_run: bool, send_clients: bool,
                log: logging.Logger) -> dict:
    """
    Run the full pipeline for one client.
    Returns a result dict (used in the summary).
    Raises an exception if anything fails — caller handles it.
    """
    name      = client["business_name"]
    client_id = client["client_id"]
    started   = time.time()

    log.info(f"\n  Client : {name}  ({client_id})")
    log.info(f"  {'-' * 54}")

    if dry_run:
        log.info(f"    [DRY RUN] Would pull data, analyze, and build PDF.")
        log.info(f"    [DRY RUN] QB connected   : {bool(client.get('qbo_company_id'))}")
        log.info(f"    [DRY RUN] Client email   : {client.get('contact_email', 'not set')}")
        log.info(f"    [DRY RUN] Would email client: {'Yes' if send_clients else 'No'}")
        return {
            "client_id":      client_id,
            "business":       name,
            "status":         "dry_run",
            "pdf_path":       None,
            "data_source":    "n/a",
            "client_emailed": False,
            "duration_sec":   round(time.time() - started, 1),
            "error":          None,
        }

    # ── Step 1: Pull financial data ─────────────────────────────────────────
    log.info("    [1/4] Pulling financial data...")
    pnl_data, bs_data, cf_data, data_source = _pull_financial_data(
        client, force_sample, log
    )

    # ── Step 2: Run all three analyses ──────────────────────────────────────
    log.info("    [2/4] Running analysis...")

    analysis = run_analysis(pnl_data)
    latest        = analysis["latest_month"]
    monthly_rev   = float(analysis["summary_df"].loc["Total Revenue",      latest])
    monthly_cogs  = float(analysis["summary_df"].loc["Cost of Goods Sold", latest])
    net_profit    = float(analysis["summary_df"].loc["Net Profit",         latest])
    net_margin    = float(analysis["summary_df"].loc["Net Margin %",       latest])

    log.info(f"    Period       : {analysis['all_months'][0]} -> {latest}")
    log.info(f"    Revenue      : ${monthly_rev:,.0f}")
    log.info(f"    Net Profit   : ${net_profit:,.0f}  ({net_margin:.1f}%)")
    log.debug(f"    MoM data rows: {len(analysis.get('mom_df', []))}")

    bs_analysis = analyze_balance_sheet(
        bs_data,
        monthly_revenue=monthly_rev,
        monthly_cogs=monthly_cogs,
    )
    log.info(f"    Balance Sheet: as of {bs_analysis['as_of_date']}")
    log.debug(f"    Current ratio: {bs_analysis.get('current_ratio')}  "
              f"AR days: {bs_analysis.get('ar_days')}")

    cf_analysis = analyze_cash_flow(analysis, bs_analysis, cf_data)
    cf_status   = "POSITIVE" if cf_analysis["is_cash_positive"] else "NEGATIVE"
    log.info(f"    Cash Flow    : {cf_status}  |  "
             f"Runway: {cf_analysis['cash_runway_months']} months")

    # ── Step 2b: Quality control check ─────────────────────────────────────
    log.info("    [2b] Running QC anomaly check...")
    from anomaly_check import run_qc, save_qc_report, _render_report
    qc_result  = run_qc(client_id, analysis, bs_analysis, cf_analysis)
    qc_path    = save_qc_report(qc_result)

    if qc_result.criticals:
        log.error(f"    QC BLOCKED: {len(qc_result.criticals)} critical issue(s)")
        for f in qc_result.criticals:
            log.error(f"      {f.category}: {f.message}")
        log.error(f"    QC report: {qc_path}")
        raise RuntimeError(
            f"QC check BLOCKED this report — {len(qc_result.criticals)} critical "
            f"issue(s) found. Review {qc_path.name} before proceeding."
        )
    elif qc_result.warnings:
        log.warning(f"    QC REVIEW: {len(qc_result.warnings)} warning(s) — check QC report")
        for f in qc_result.warnings:
            log.warning(f"      {f.category}: {f.message}")
        log.warning(f"    QC report: {qc_path}")
    else:
        log.info(f"    QC PASS: all {qc_result.checks_run} checks clean")

    # ── Step 3: Claude insights ─────────────────────────────────────────────
    log.info("    [3/4] Generating Claude insights (10-15 sec)...")
    t0 = time.time()
    insights = generate_insights(
        analysis    = analysis,
        bs_analysis = bs_analysis,
        cf_analysis = cf_analysis,
    )
    log.debug(f"    Claude response: {len(insights)} chars in {time.time()-t0:.1f}s")
    log.info(f"    Insights done  : {time.time()-t0:.1f}s")

    # ── Step 4: Build PDF ───────────────────────────────────────────────────
    log.info("    [4/4] Building PDF report...")
    t0 = time.time()
    pdf_path = generate_report_pdf(
        analysis    = analysis,
        insights    = insights,
        bs_analysis = bs_analysis,
        cf_analysis = cf_analysis,
        output_dir  = str(ROOT / "reports"),
    )
    abs_path = os.path.abspath(pdf_path)
    size_kb  = os.path.getsize(abs_path) / 1024
    log.info(f"    PDF saved      : {abs_path}")
    log.info(f"    PDF size       : {size_kb:.0f} KB  ({time.time()-t0:.1f}s)")

    result = {
        "client_id":      client_id,
        "business":       name,
        "status":         "success",
        "qc_verdict":     qc_result.verdict,
        "qc_warnings":    len(qc_result.warnings),
        "qc_path":        str(qc_path),
        "pdf_path":       abs_path,
        "data_source":    data_source,
        "period":         latest,
        "revenue":        monthly_rev,
        "net_profit":     net_profit,
        "net_margin":     net_margin,
        "client_emailed": False,
        "error":          None,
    }

    # ── Step 5: Generate client HTML dashboard ──────────────────────────────
    try:
        from generate_client_dashboard import _render, _save, _parse_insights
        log.info("    [5/5] Building client HTML dashboard...")
        insights_raw = insights if isinstance(insights, str) else ""
        dash_html    = _render(client, analysis, bs_analysis, cf_analysis, insights_raw)
        dash_path    = _save(client, analysis, dash_html)
        result["dashboard_path"] = str(dash_path)
        log.info(f"    Dashboard saved: {dash_path.name}")
    except Exception as e:
        log.warning(f"    Dashboard skipped: {e}")
        result["dashboard_path"] = None

    # ── Step 6: Email report to client (only if --send-clients) ────────────
    if send_clients:
        log.info("    [6/6] Emailing report to client...")
        _send_client_report(client, result, log)
        result["client_emailed"] = True

    duration = round(time.time() - started, 1)
    log.info(f"    Total time     : {duration}s")
    result["duration_sec"] = duration

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# CLIENT EMAIL — send the PDF report to the individual client
# ═══════════════════════════════════════════════════════════════════════════════

def _send_client_report(client: dict, result: dict, log: logging.Logger):
    """
    Email the client their PDF report for the month.
    Uses the client's contact_email from clients.db.
    Called only when --send-clients flag is set.
    """
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_pass = os.getenv("SMTP_PASSWORD", "").strip()
    company   = os.getenv("COMPANY_NAME",  "Shah Consultant").strip()
    author    = os.getenv("REPORT_AUTHOR", "").strip()

    if not smtp_user or not smtp_pass:
        log.warning("    Client email skipped — SMTP credentials not set in .env")
        return

    to_email = (client.get("contact_email") or "").strip()
    if not to_email:
        log.warning(f"    Client email skipped — no contact_email for {client['business_name']}")
        return

    pdf_path = result.get("pdf_path")
    if not pdf_path or not pathlib.Path(pdf_path).exists():
        log.warning(f"    Client email skipped — PDF not found at {pdf_path}")
        return

    period        = result.get("period", "this month")
    business_name = client["business_name"]

    # ── Subject and body ──────────────────────────────────────────────────
    subject = f"Your Financial Report — {period} | {business_name}"

    # Friendly name: first word of business name, or "there"
    first_name = business_name.split()[0] if business_name else "there"

    body_lines = [
        f"Hi {first_name},",
        "",
        f"Please find attached your financial report for {period}.",
        "",
        "This report includes:",
        "  - Profit & Loss summary with month-over-month comparison",
        "  - Balance sheet highlights and liquidity ratios",
        "  - Cash flow analysis and runway estimate",
        "  - AI-generated insights and key items to watch",
        "",
        "If you have any questions or would like to discuss the numbers,",
        "please don't hesitate to reach out — happy to schedule a call.",
        "",
        "Best regards,",
    ]

    if author:
        body_lines.append(author)
    body_lines.append(company)

    body = "\n".join(body_lines)

    # ── Build email ───────────────────────────────────────────────────────
    msg = EmailMessage()
    msg["From"]    = smtp_user
    msg["To"]      = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    # Attach PDF
    pdf_bytes = pathlib.Path(pdf_path).read_bytes()
    pdf_name  = pathlib.Path(pdf_path).name
    msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf",
                       filename=pdf_name)

    # ── Send ──────────────────────────────────────────────────────────────
    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        log.info(f"    Client email sent  : {to_email}")
    except smtplib.SMTPAuthenticationError:
        log.error("    Client email FAILED: Authentication error. Check SMTP credentials in .env")
    except Exception as e:
        log.error(f"    Client email FAILED: {e}")
        log.debug(traceback.format_exc())


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY EMAIL — sent to YOU, not to clients
# ═══════════════════════════════════════════════════════════════════════════════

def _send_summary_email(results: list[dict], log_path: pathlib.Path,
                        total_sec: int, log: logging.Logger,
                        send_clients: bool = False):
    """
    Email the batch summary to SMTP_USER (you).
    Attaches the full log file.
    Never sends to clients — that's handled by _send_client_report().
    """
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_pass = os.getenv("SMTP_PASSWORD", "").strip()

    if not smtp_user or not smtp_pass:
        log.warning("  Email not sent — SMTP_USER / SMTP_PASSWORD not set in .env")
        return

    run_date   = datetime.date.today().strftime("%B %d, %Y")
    successes  = [r for r in results if r["status"] == "success"]
    failures   = [r for r in results if r["status"] == "error"]
    dry_runs   = [r for r in results if r["status"] == "dry_run"]

    subject = (
        f"[Financial Reports] Batch complete — {len(successes)} OK"
        + (f", {len(failures)} FAILED" if failures else "")
        + f"  |  {run_date}"
    )

    # ── Build plain-text body ─────────────────────────────────────────────
    lines = [
        f"Monthly Report Batch — {run_date}",
        f"Total runtime: {total_sec}s",
        "",
        f"Results: {len(successes)} succeeded  /  {len(failures)} failed  /  {len(dry_runs)} dry-run",
        "",
    ]

    if successes:
        lines.append("REPORTS GENERATED (saved for your review):")
        lines.append("-" * 60)
        for r in successes:
            lines.append(f"  OK   {r['business']}")
            lines.append(f"       Period  : {r.get('period','n/a')}")
            lines.append(f"       Revenue : ${r.get('revenue', 0):,.0f}  |  "
                         f"Net Profit: ${r.get('net_profit', 0):,.0f}  "
                         f"({r.get('net_margin', 0):.1f}%)")
            lines.append(f"       Source  : {r.get('data_source','n/a')}")
            lines.append(f"       File    : {r.get('pdf_path','n/a')}")
            lines.append(f"       Time    : {r.get('duration_sec')}s")
            lines.append("")

    if failures:
        lines.append("FAILURES:")
        lines.append("-" * 60)
        for r in failures:
            lines.append(f"  FAIL  {r['business']}")
            lines.append(f"        Error: {r.get('error','unknown')}")
            lines.append("")

    if dry_runs:
        lines.append("DRY RUN (not generated):")
        for r in dry_runs:
            lines.append(f"  --    {r['business']}")
        lines.append("")

    lines += [
        "-" * 60,
        "Full log file is attached.",
        "",
        f"{'Clients were emailed their reports automatically.' if send_clients else 'NEXT STEP: Review the PDFs above, then send to clients manually.'}",
        "",
        f"{os.getenv('COMPANY_NAME', 'Shah Consultant')} — Automated Reporting System",
    ]

    body = "\n".join(lines)

    # ── Build and send email ──────────────────────────────────────────────
    msg = EmailMessage()
    msg["From"]    = smtp_user
    msg["To"]      = smtp_user          # Sends to yourself — never to clients
    msg["Subject"] = subject
    msg.set_content(body)

    # Attach the log file
    if log_path.exists():
        msg.add_attachment(
            log_path.read_bytes(),
            maintype="text",
            subtype="plain",
            filename=log_path.name,
        )

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        log.info(f"  Summary email sent to {smtp_user}")
    except smtplib.SMTPAuthenticationError:
        log.error("  Summary email FAILED: Authentication error.")
        log.error("  Check SMTP_USER and SMTP_PASSWORD in .env")
        log.error("  Gmail: use an App Password, not your regular password.")
    except Exception as e:
        log.error(f"  Summary email FAILED: {e}")
        log.debug(traceback.format_exc())


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    args         = sys.argv[1:]
    dry_run      = "--dry-run"      in args
    no_email     = "--no-email"     in args
    force_sample = "--sample"       in args
    send_clients = "--send-clients" in args
    client_arg   = next((args[i+1] for i, a in enumerate(args)
                         if a == "--client" and i+1 < len(args)), None)

    log, log_path = _setup_logging()
    batch_start   = time.time()

    # ── Header ──────────────────────────────────────────────────────────────
    log.info("=" * 62)
    log.info("  MONTHLY REPORT BATCH")
    log.info(f"  Started      : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"  Dry run      : {'YES — no reports will be built' if dry_run else 'No'}")
    log.info(f"  Data         : {'Forced sample data' if force_sample else 'QuickBooks (sample fallback)'}")
    log.info(f"  Client emails: {'YES — PDF will be sent to each client' if send_clients else 'No (use --send-clients to enable)'}")
    log.info(f"  Owner email  : {'disabled' if no_email else 'summary to you when done'}")
    log.info(f"  Log file     : {log_path}")
    log.info("=" * 62)

    # ── Load clients ─────────────────────────────────────────────────────────
    try:
        clients = _load_active_clients(client_arg)
    except (FileNotFoundError, ValueError) as e:
        log.error(f"\nError: {e}")
        sys.exit(1)

    if not clients:
        log.info("\nNo active clients found in clients.db.")
        log.info("Add clients with: python manage_clients.py add")
        sys.exit(0)

    log.info(f"\nFound {len(clients)} active client(s):\n")
    for c in clients:
        qb = "QB connected" if c.get("qbo_company_id") else "sample data"
        log.info(f"  - {c['business_name']}  ({qb})")

    # ── Run each client ───────────────────────────────────────────────────────
    results = []

    for i, client in enumerate(clients, 1):
        log.info(f"\n[{i}/{len(clients)}]")
        try:
            result = _run_client(client, force_sample, dry_run, send_clients, log)
            results.append(result)
        except Exception as e:
            log.error(f"\n  !! FAILED: {client['business_name']}")
            log.error(f"     {type(e).__name__}: {e}")
            log.debug(traceback.format_exc())
            results.append({
                "client_id":    client["client_id"],
                "business":     client["business_name"],
                "status":       "error",
                "pdf_path":     None,
                "data_source":  "n/a",
                "duration_sec": 0,
                "error":        f"{type(e).__name__}: {e}",
            })

    # ── Final summary ─────────────────────────────────────────────────────────
    total_sec  = round(time.time() - batch_start)
    successes  = [r for r in results if r["status"] == "success"]
    failures   = [r for r in results if r["status"] == "error"]
    dry_runs   = [r for r in results if r["status"] == "dry_run"]

    log.info(f"\n{'=' * 62}")
    log.info(f"  BATCH COMPLETE")
    log.info(f"  Total time : {total_sec}s")
    log.info(f"  Succeeded  : {len(successes)}")
    log.info(f"  Failed     : {len(failures)}")
    if dry_runs:
        log.info(f"  Dry run    : {len(dry_runs)}")
    log.info(f"{'=' * 62}")

    if successes:
        log.info("\nReports saved:")
        for r in successes:
            emailed = "  [client emailed]" if r.get("client_emailed") else "  [not sent to client]"
            log.info(f"  OK   {r['business']}{emailed}")
            log.info(f"       {r['pdf_path']}")

    if failures:
        log.info("\nFailures:")
        for r in failures:
            log.error(f"  FAIL {r['business']}")
            log.error(f"       {r['error']}")

    log.info(f"\nFull log: {log_path}")

    # ── Send summary email to you ─────────────────────────────────────────────
    if not no_email and not dry_run:
        log.info("\nSending batch summary email to you...")
        _send_summary_email(results, log_path, total_sec, log, send_clients=send_clients)
    elif dry_run:
        log.info("\n[DRY RUN] Summary email skipped.")
    else:
        log.info("\nSummary email skipped (--no-email).")

    # Exit with error code if any clients failed
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
