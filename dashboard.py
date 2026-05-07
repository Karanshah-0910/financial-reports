"""
dashboard.py
------------
Internal business dashboard. Reads clients.db, reports/, and logs/
to show a live snapshot. Opens automatically in your browser.

HOW TO RUN:
  python dashboard.py

Refresh the browser tab any time to pull fresh data.
"""

import sqlite3
import pathlib
import datetime
import json
import webbrowser
import re
import os

ROOT        = pathlib.Path(__file__).parent
DB_PATH     = ROOT / "clients.db"
REPORTS_DIR = ROOT / "reports"
LOGS_DIR    = ROOT / "logs"
OUT_HTML    = ROOT / "dashboard.html"


# ═══════════════════════════════════════════════════════════════════
# DATA COLLECTION
# ═══════════════════════════════════════════════════════════════════

def _get_clients() -> list[dict]:
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM clients ORDER BY status ASC, business_name ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _reports_this_month() -> dict[str, list[str]]:
    """
    Scan reports/ for PDFs whose filename matches YYYY-MM for the current month.
    Returns {folder_name: [pdf_path, ...]}
    """
    now = datetime.date.today()
    prefix = f"{now.year}-{now.month:02d}"
    found = {}
    if not REPORTS_DIR.exists():
        return found
    for client_dir in REPORTS_DIR.iterdir():
        if not client_dir.is_dir():
            continue
        pdfs = [p for p in client_dir.glob("*.pdf") if p.name.startswith(prefix)]
        if pdfs:
            found[client_dir.name] = [str(p) for p in pdfs]
    return found


def _all_report_dates() -> dict[str, str]:
    """
    Returns {folder_name: most_recent_report_period_label} for every client folder.
    """
    last = {}
    if not REPORTS_DIR.exists():
        return last
    for client_dir in REPORTS_DIR.iterdir():
        if not client_dir.is_dir():
            continue
        pdfs = sorted(client_dir.glob("*.pdf"), reverse=True)
        if pdfs:
            # filename: 2025-04_financial_report.pdf
            m = re.match(r"(\d{4}-\d{2})", pdfs[0].name)
            last[client_dir.name] = m.group(1) if m else pdfs[0].name
    return last


def _parse_logs() -> tuple[float | None, list[dict]]:
    """
    Parse batch log files for:
      - average time per client report (seconds)
      - last 8 batch runs (date, count, duration)
    Returns (avg_time_sec, recent_runs)
    """
    if not LOGS_DIR.exists():
        return None, []

    log_files = sorted(LOGS_DIR.glob("*_batch.log"))
    client_times = []
    recent_runs  = []

    for log_file in log_files[-20:]:
        try:
            content = log_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        # Per-client times
        times = re.findall(r"Total time\s+:\s+([\d.]+)s", content)
        for t in times:
            client_times.append(float(t))

        # Batch summary
        run_date_m  = re.search(r"Started\s+:\s+(\d{4}-\d{2}-\d{2})", content)
        total_time_m = re.search(r"Total time\s*:\s*(\d+)s", content)
        succeeded_m  = re.search(r"Succeeded\s+:\s+(\d+)",  content)

        if run_date_m:
            recent_runs.append({
                "date":      run_date_m.group(1),
                "succeeded": int(succeeded_m.group(1)) if succeeded_m else 0,
                "duration":  int(total_time_m.group(1)) if total_time_m else 0,
            })

    avg = (sum(client_times) / len(client_times)) if client_times else None
    return avg, recent_runs[-8:]


def _mrr_history(clients: list[dict]) -> tuple[list[str], list[float]]:
    """
    Build month-by-month MRR from onboarding/churn dates.
    Returns (labels, values) for the last 18 months max.
    """
    today = datetime.date.today()
    dates = []
    for c in clients:
        od = c.get("onboarding_date")
        if od:
            try:
                dates.append(datetime.date.fromisoformat(od[:10]))
            except Exception:
                pass

    if not dates:
        return [], []

    start = min(dates).replace(day=1)
    # Cap history at 18 months back
    cutoff = (today.replace(day=1) - datetime.timedelta(days=18*30)).replace(day=1)
    if start < cutoff:
        start = cutoff

    # Generate month sequence
    months = []
    cur = start
    while cur <= today.replace(day=1):
        months.append(cur)
        cur = (cur.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)

    mrr_vals = []
    for month in months:
        mrr = 0.0
        for c in clients:
            od = c.get("onboarding_date")
            if not od:
                continue
            try:
                onboard = datetime.date.fromisoformat(od[:10]).replace(day=1)
            except Exception:
                continue
            if onboard > month:
                continue

            fee = float(c.get("monthly_fee") or 0)
            status = c.get("status", "active")

            if status == "active":
                mrr += fee
            else:
                # Use updated_at as approximate churn month
                upd = c.get("updated_at")
                if upd:
                    try:
                        churn = datetime.date.fromisoformat(upd[:10]).replace(day=1)
                        if month < churn:
                            mrr += fee
                    except Exception:
                        pass

        mrr_vals.append(mrr)

    labels = [m.strftime("%b %Y") for m in months]
    return labels, mrr_vals


# ═══════════════════════════════════════════════════════════════════
# COMPUTE STATS
# ═══════════════════════════════════════════════════════════════════

def _build_stats():
    today          = datetime.date.today()
    clients        = _get_clients()
    active         = [c for c in clients if c["status"] == "active"]
    paused         = [c for c in clients if c["status"] == "paused"]
    churned        = [c for c in clients if c["status"] == "churned"]
    total_mrr      = sum(float(c.get("monthly_fee") or 0) for c in active)
    reports_month  = _reports_this_month()
    all_last        = _all_report_dates()
    avg_time, runs  = _parse_logs()
    mrr_labels, mrr_vals = _mrr_history(clients)

    # Match report folders to clients (folder names are sanitised business names)
    def _folder_name(business: str) -> str:
        return business.replace(" ", "_").replace("/", "_")

    reports_done = sum(
        1 for c in active
        if _folder_name(c["business_name"]) in reports_month
    )

    # Overdue: active client with no report this month
    # Only flag after the 5th so the batch has had time to run
    overdue = []
    if today.day >= 5:
        for c in active:
            fn = _folder_name(c["business_name"])
            if fn not in reports_month:
                last = all_last.get(fn, "never")
                overdue.append({
                    "business": c["business_name"],
                    "client_id": c["client_id"],
                    "last_report": last,
                    "email": c.get("contact_email", ""),
                })

    # Client table rows
    client_rows = []
    for c in clients:
        fn   = _folder_name(c["business_name"])
        last = all_last.get(fn, "—")
        done = fn in reports_month
        client_rows.append({
            "business":   c["business_name"],
            "status":     c["status"],
            "fee":        float(c.get("monthly_fee") or 0),
            "industry":   c.get("industry") or "—",
            "email":      c.get("contact_email") or "—",
            "last_report":last,
            "done_this_month": done,
            "onboarded":  c.get("onboarding_date") or "—",
        })

    return {
        "generated_at":    today.strftime("%B %d, %Y  %A"),
        "today":           today.isoformat(),
        "active_count":    len(active),
        "paused_count":    len(paused),
        "churned_count":   len(churned),
        "total_mrr":       total_mrr,
        "reports_done":    reports_done,
        "reports_total":   len(active),
        "overdue":         overdue,
        "avg_time_sec":    round(avg_time) if avg_time else None,
        "recent_runs":     runs,
        "mrr_labels":      mrr_labels,
        "mrr_values":      mrr_vals,
        "client_rows":     client_rows,
        "annual_run_rate": total_mrr * 12,
    }


# ═══════════════════════════════════════════════════════════════════
# HTML GENERATION
# ═══════════════════════════════════════════════════════════════════

def _render_html(s: dict) -> str:
    def _fmt_usd(v):
        return f"${v:,.0f}"

    def _badge(status):
        colors = {"active": "#22c55e", "paused": "#f59e0b", "churned": "#ef4444"}
        bg     = colors.get(status, "#888")
        return f'<span style="background:{bg};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;">{status.upper()}</span>'

    def _tick(done):
        return '<span style="color:#22c55e;font-size:16px;">&#10003;</span>' if done \
               else '<span style="color:#ef4444;font-size:16px;">&#10007;</span>'

    # ── Overdue rows ────────────────────────────────────────────────
    if s["overdue"]:
        overdue_rows = "".join(
            f"<tr>"
            f"<td>{r['business']}</td>"
            f"<td style='color:#9ca3af;font-size:12px;'>{r['client_id']}</td>"
            f"<td>{r['last_report']}</td>"
            f"<td style='color:#9ca3af;font-size:12px;'>{r['email']}</td>"
            f"</tr>"
            for r in s["overdue"]
        )
        overdue_section = f"""
        <div class="card" style="border-left:3px solid #ef4444;">
          <h2 style="color:#ef4444;">&#9888; Overdue Reports ({len(s['overdue'])})</h2>
          <table>
            <thead><tr>
              <th>Business</th><th>Client ID</th><th>Last Report</th><th>Email</th>
            </tr></thead>
            <tbody>{overdue_rows}</tbody>
          </table>
        </div>"""
    else:
        overdue_section = """
        <div class="card" style="border-left:3px solid #22c55e;">
          <h2 style="color:#22c55e;">&#10003; No Overdue Reports</h2>
          <p style="color:#9ca3af;margin:0;">All active clients have reports this month.</p>
        </div>"""

    # ── Recent batch runs ────────────────────────────────────────────
    if s["recent_runs"]:
        run_rows = "".join(
            f"<tr>"
            f"<td>{r['date']}</td>"
            f"<td>{r['succeeded']} client(s)</td>"
            f"<td>{r['duration']}s</td>"
            f"</tr>"
            for r in reversed(s["recent_runs"])
        )
        runs_section = f"""
        <div class="card">
          <h2>Recent Batch Runs</h2>
          <table>
            <thead><tr><th>Date</th><th>Reports Built</th><th>Duration</th></tr></thead>
            <tbody>{run_rows}</tbody>
          </table>
        </div>"""
    else:
        runs_section = """
        <div class="card">
          <h2>Recent Batch Runs</h2>
          <p style="color:#9ca3af;">No batch logs found yet. Run: python run_monthly_reports.py</p>
        </div>"""

    # ── Client table ─────────────────────────────────────────────────
    client_rows_html = "".join(
        f"<tr>"
        f"<td><strong>{r['business']}</strong></td>"
        f"<td>{_badge(r['status'])}</td>"
        f"<td>{r['industry']}</td>"
        f"<td>{_fmt_usd(r['fee'])}/mo</td>"
        f"<td>{r['last_report']}</td>"
        f"<td style='text-align:center'>{_tick(r['done_this_month']) if r['status']=='active' else '—'}</td>"
        f"</tr>"
        for r in s["client_rows"]
    )

    # ── MRR chart data ───────────────────────────────────────────────
    mrr_labels_js = json.dumps(s["mrr_labels"])
    mrr_values_js = json.dumps(s["mrr_values"])

    avg_time_str = f"{s['avg_time_sec']}s" if s["avg_time_sec"] else "—"
    reports_str  = f"{s['reports_done']} / {s['reports_total']}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Financial Reports — Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: #0f0f13;
    color: #e5e7eb;
    padding: 24px;
    min-height: 100vh;
  }}
  h1 {{ font-size: 20px; font-weight: 700; color: #fff; }}
  h2 {{ font-size: 14px; font-weight: 600; color: #9ca3af;
        text-transform: uppercase; letter-spacing: .05em; margin-bottom: 14px; }}
  .header {{
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 24px; padding-bottom: 16px;
    border-bottom: 1px solid #1f2937;
  }}
  .timestamp {{ font-size: 12px; color: #6b7280; }}
  .refresh-btn {{
    background: #1f2937; color: #9ca3af; border: 1px solid #374151;
    padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 12px;
  }}
  .refresh-btn:hover {{ background: #374151; color: #e5e7eb; }}

  /* Stat cards */
  .stats-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 14px;
    margin-bottom: 24px;
  }}
  .stat {{
    background: #1a1a24;
    border: 1px solid #1f2937;
    border-radius: 10px;
    padding: 18px;
  }}
  .stat-label {{ font-size: 11px; color: #6b7280; text-transform: uppercase;
                 letter-spacing: .06em; margin-bottom: 6px; }}
  .stat-value {{ font-size: 28px; font-weight: 700; color: #fff; line-height: 1; }}
  .stat-sub   {{ font-size: 12px; color: #6b7280; margin-top: 4px; }}

  /* Cards */
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 14px; }}
  .card {{
    background: #1a1a24;
    border: 1px solid #1f2937;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 14px;
  }}
  .card:last-child {{ margin-bottom: 0; }}

  /* Tables */
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{
    text-align: left; color: #6b7280; font-size: 11px;
    text-transform: uppercase; letter-spacing: .05em;
    padding: 0 10px 10px 0; border-bottom: 1px solid #1f2937;
  }}
  td {{ padding: 9px 10px 9px 0; border-bottom: 1px solid #1a1a24; color: #d1d5db; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #1f2937; }}

  /* Chart */
  .chart-wrap {{ position: relative; height: 220px; }}

  @media (max-width: 700px) {{
    .grid-2 {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>Financial Reports Dashboard</h1>
    <p class="timestamp">Generated: {s["generated_at"]}</p>
  </div>
  <button class="refresh-btn" onclick="location.reload()">&#8635; Refresh</button>
</div>

<!-- ── Stat cards ────────────────────────────────────────── -->
<div class="stats-grid">
  <div class="stat">
    <div class="stat-label">Active Clients</div>
    <div class="stat-value">{s["active_count"]}</div>
    <div class="stat-sub">{s["paused_count"]} paused &nbsp;·&nbsp; {s["churned_count"]} churned</div>
  </div>
  <div class="stat">
    <div class="stat-label">Monthly MRR</div>
    <div class="stat-value">{_fmt_usd(s["total_mrr"])}</div>
    <div class="stat-sub">ARR {_fmt_usd(s["annual_run_rate"])}</div>
  </div>
  <div class="stat">
    <div class="stat-label">Reports This Month</div>
    <div class="stat-value">{reports_str}</div>
    <div class="stat-sub">{"All done!" if s["reports_done"] == s["reports_total"] and s["reports_total"] > 0 else f"{s['reports_total'] - s['reports_done']} remaining"}</div>
  </div>
  <div class="stat">
    <div class="stat-label">Avg Report Time</div>
    <div class="stat-value">{avg_time_str}</div>
    <div class="stat-sub">per client</div>
  </div>
</div>

<!-- ── MRR chart ─────────────────────────────────────────── -->
<div class="card">
  <h2>MRR Trend</h2>
  <div class="chart-wrap">
    <canvas id="mrrChart"></canvas>
  </div>
</div>

<!-- ── Overdue + Batch runs ──────────────────────────────── -->
<div class="grid-2">
  {overdue_section}
  {runs_section}
</div>

<!-- ── All clients ───────────────────────────────────────── -->
<div class="card">
  <h2>All Clients</h2>
  <table>
    <thead>
      <tr>
        <th>Business</th>
        <th>Status</th>
        <th>Industry</th>
        <th>Fee</th>
        <th>Last Report</th>
        <th style="text-align:center">This Month</th>
      </tr>
    </thead>
    <tbody>
      {client_rows_html}
    </tbody>
  </table>
</div>

<script>
const ctx = document.getElementById('mrrChart').getContext('2d');
new Chart(ctx, {{
  type: 'line',
  data: {{
    labels: {mrr_labels_js},
    datasets: [{{
      label: 'MRR ($)',
      data: {mrr_values_js},
      borderColor: '#6366f1',
      backgroundColor: 'rgba(99,102,241,0.12)',
      borderWidth: 2,
      pointBackgroundColor: '#6366f1',
      pointRadius: 4,
      fill: true,
      tension: 0.3,
    }}]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{
      legend: {{ display: false }},
      tooltip: {{
        callbacks: {{
          label: ctx => ' $' + ctx.parsed.y.toLocaleString()
        }}
      }}
    }},
    scales: {{
      x: {{
        ticks: {{ color: '#6b7280', font: {{ size: 11 }} }},
        grid:  {{ color: '#1f2937' }}
      }},
      y: {{
        ticks: {{
          color: '#6b7280',
          font: {{ size: 11 }},
          callback: v => '$' + v.toLocaleString()
        }},
        grid: {{ color: '#1f2937' }},
        beginAtZero: true
      }}
    }}
  }}
}});
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def main():
    print("Building dashboard...")
    stats = _build_stats()

    print(f"  Active clients : {stats['active_count']}")
    print(f"  MRR            : ${stats['total_mrr']:,.0f}")
    print(f"  Reports done   : {stats['reports_done']} / {stats['reports_total']}")
    print(f"  Overdue        : {len(stats['overdue'])}")

    html = _render_html(stats)
    OUT_HTML.write_text(html, encoding="utf-8")

    print(f"\nSaved: {OUT_HTML}")
    print("Opening in browser...")
    webbrowser.open(OUT_HTML.as_uri())


if __name__ == "__main__":
    main()
