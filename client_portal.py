"""
client_portal.py
----------------
Local client portal. Each client logs in with their client ID + password
and sees their latest financial dashboard.

HOW TO RUN:
  python client_portal.py               # Start on http://localhost:8080
  python client_portal.py --port 5050   # Custom port

SET A CLIENT PASSWORD (run once per client):
  python client_portal.py --set-password riverside_home_goods

WHAT CLIENTS SEE:
  1. Login page  →  enter their ID + password
  2. Their latest HTML dashboard (same design as generate_client_dashboard.py)
  3. Links to download previous months as PDFs

SHARING WITH CLIENTS (local only for now):
  - Run this script on your PC
  - Clients on the SAME network can access: http://<your-PC-IP>:8080
  - To find your IP: ipconfig in CMD → look for IPv4 Address
"""

import sys
import os
import sqlite3
import pathlib
import argparse
import hashlib
import secrets
import datetime
import getpass

ROOT = pathlib.Path(__file__).parent
DB_PATH = ROOT / "clients.db"

# ── Try importing Flask ───────────────────────────────────────────────────────
try:
    from flask import (Flask, request, session, redirect,
                       url_for, render_template_string, send_file, abort)
except ImportError:
    print("\n  Flask not installed. Run:")
    print("  pip install flask")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════
# DATABASE HELPERS
# ═══════════════════════════════════════════════════════════════════

def _ensure_password_column():
    """Add portal_password_hash column if it doesn't exist yet."""
    conn = sqlite3.connect(DB_PATH)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(clients)").fetchall()]
    if "portal_password_hash" not in cols:
        conn.execute("ALTER TABLE clients ADD COLUMN portal_password_hash TEXT")
        conn.commit()
    conn.close()


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h    = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{h}"


def _verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash or ":" not in stored_hash:
        return False
    salt, h = stored_hash.split(":", 1)
    return hashlib.sha256((salt + password).encode()).hexdigest() == h


def _get_client(client_id: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row  = conn.execute(
        "SELECT * FROM clients WHERE client_id = ?", (client_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _set_password(client_id: str, password: str):
    h = _hash_password(password)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE clients SET portal_password_hash = ? WHERE client_id = ?",
        (h, client_id)
    )
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════
# REPORT FILE HELPERS
# ═══════════════════════════════════════════════════════════════════

def _client_folder(client: dict) -> pathlib.Path:
    safe = client["business_name"].replace(" ", "_").replace("/", "_")
    return ROOT / "reports" / safe


def _latest_dashboard(client: dict) -> pathlib.Path | None:
    folder = _client_folder(client)
    if not folder.exists():
        return None
    dashboards = sorted(folder.glob("*_dashboard.html"), reverse=True)
    return dashboards[0] if dashboards else None


def _all_pdfs(client: dict) -> list[dict]:
    folder = _client_folder(client)
    if not folder.exists():
        return []
    pdfs = sorted(folder.glob("*.pdf"), reverse=True)
    result = []
    for p in pdfs:
        result.append({
            "name":  p.name,
            "path":  str(p),
            "size":  f"{p.stat().st_size / 1024:.0f} KB",
            "period": p.name[:7] if len(p.name) >= 7 else p.name,
        })
    return result


# ═══════════════════════════════════════════════════════════════════
# FLASK APP
# ═══════════════════════════════════════════════════════════════════

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)   # Regenerates on restart — sessions clear on server restart


# ── Login page template ───────────────────────────────────────────
LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Client Portal — Login</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: #0f172a;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 24px;
  }
  .logo {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 36px;
  }
  .logo-dot {
    width: 10px; height: 10px;
    background: #6366f1;
    border-radius: 50%;
  }
  .logo-name {
    font-size: 18px;
    font-weight: 700;
    color: #fff;
    letter-spacing: -.01em;
  }
  .card {
    background: #fff;
    border-radius: 16px;
    padding: 40px 44px;
    width: 100%;
    max-width: 420px;
    box-shadow: 0 24px 64px rgba(0,0,0,.35);
  }
  .card-title {
    font-size: 22px;
    font-weight: 800;
    color: #0f172a;
    letter-spacing: -.02em;
    margin-bottom: 6px;
  }
  .card-sub {
    font-size: 14px;
    color: #64748b;
    margin-bottom: 32px;
  }
  label {
    display: block;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .06em;
    color: #475569;
    margin-bottom: 6px;
  }
  input {
    width: 100%;
    padding: 12px 14px;
    border: 1.5px solid #e2e8f0;
    border-radius: 8px;
    font-size: 14px;
    color: #0f172a;
    margin-bottom: 20px;
    outline: none;
    transition: border-color .15s;
    font-family: inherit;
  }
  input:focus { border-color: #6366f1; box-shadow: 0 0 0 3px rgba(99,102,241,.12); }
  input::placeholder { color: #cbd5e1; }
  .btn {
    width: 100%;
    padding: 13px;
    background: #6366f1;
    color: #fff;
    border: none;
    border-radius: 8px;
    font-size: 15px;
    font-weight: 700;
    cursor: pointer;
    letter-spacing: -.01em;
    transition: background .15s, transform .1s;
    font-family: inherit;
    margin-top: 4px;
  }
  .btn:hover  { background: #4f46e5; }
  .btn:active { transform: scale(.98); }
  .error {
    background: #fef2f2;
    border: 1px solid #fecaca;
    color: #dc2626;
    border-radius: 8px;
    padding: 12px 14px;
    font-size: 13px;
    margin-bottom: 20px;
    font-weight: 500;
  }
  .footer-note {
    font-size: 12px;
    color: rgba(255,255,255,.3);
    margin-top: 24px;
    text-align: center;
  }
</style>
</head>
<body>

<div class="logo">
  <div class="logo-dot"></div>
  <span class="logo-name">{{ company }}</span>
</div>

<div class="card">
  <div class="card-title">Client Portal</div>
  <div class="card-sub">Sign in to view your financial reports</div>

  {% if error %}
  <div class="error">{{ error }}</div>
  {% endif %}

  <form method="POST" action="/login">
    <label for="client_id">Client ID</label>
    <input type="text" id="client_id" name="client_id"
           placeholder="e.g. riverside_home_goods"
           value="{{ prefill }}" autocomplete="username">

    <label for="password">Password</label>
    <input type="password" id="password" name="password"
           placeholder="Your portal password"
           autocomplete="current-password">

    <button class="btn" type="submit">Sign In &rarr;</button>
  </form>
</div>

<p class="footer-note">Secure · Private · Powered by {{ company }}</p>

</body>
</html>"""


# ── Dashboard wrapper template ────────────────────────────────────
PORTAL_WRAPPER = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ business }} — Portal</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: #f1f5f9;
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  /* ── TOP NAV ── */
  .portal-nav {
    background: #0f172a;
    padding: 0 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 56px;
    flex-shrink: 0;
    z-index: 100;
    border-bottom: 1px solid rgba(255,255,255,.06);
  }
  .nav-left  { display: flex; align-items: center; gap: 16px; }
  .nav-dot   { width: 8px; height: 8px; background: #6366f1; border-radius: 50%; flex-shrink:0; }
  .nav-brand { font-size: 14px; font-weight: 700; color: #fff; }
  .nav-sep   { color: rgba(255,255,255,.2); font-size: 18px; line-height:1; }
  .nav-client{ font-size: 13px; color: rgba(255,255,255,.55); }
  .nav-right { display: flex; align-items: center; gap: 10px; }
  .nav-btn {
    padding: 7px 16px; border-radius: 7px; font-size: 12px; font-weight: 600;
    cursor: pointer; text-decoration: none; border: none; font-family: inherit;
    transition: background .15s, color .15s;
  }
  .btn-ghost   { background: rgba(255,255,255,.07); color: rgba(255,255,255,.65); }
  .btn-ghost:hover { background: rgba(255,255,255,.13); color: #fff; }

  /* ── BODY LAYOUT — sidebar + main ── */
  .portal-body {
    display: flex;
    flex: 1;
    overflow: hidden;
  }

  /* ── LEFT SIDEBAR ── */
  .sidebar {
    width: 272px;
    flex-shrink: 0;
    background: #fff;
    border-right: 1px solid #e2e8f0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .sidebar-header {
    padding: 20px 20px 14px;
    border-bottom: 1px solid #f1f5f9;
  }
  .sidebar-title {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .08em;
    color: #94a3b8;
    margin-bottom: 2px;
  }
  .sidebar-biz {
    font-size: 15px;
    font-weight: 700;
    color: #0f172a;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* Section label */
  .section-label {
    padding: 16px 20px 8px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .08em;
    color: #94a3b8;
  }

  /* Report cards */
  .report-list { overflow-y: auto; flex: 1; padding-bottom: 16px; }

  .report-card {
    margin: 0 12px 8px;
    background: #f8fafc;
    border: 1.5px solid #e2e8f0;
    border-radius: 10px;
    padding: 14px 16px;
    transition: border-color .15s, box-shadow .15s;
  }
  .report-card:hover { border-color: #6366f1; box-shadow: 0 2px 12px rgba(99,102,241,.1); }
  .report-card.latest {
    background: #eef2ff;
    border-color: #6366f1;
  }

  .rc-top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 10px;
  }
  .rc-period {
    font-size: 15px;
    font-weight: 700;
    color: #0f172a;
    letter-spacing: -.01em;
  }
  .rc-badge {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .06em;
    padding: 2px 7px;
    border-radius: 20px;
    background: #6366f1;
    color: #fff;
  }
  .rc-size {
    font-size: 11px;
    color: #94a3b8;
    margin-bottom: 12px;
  }
  .rc-dl {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    width: 100%;
    padding: 8px 0;
    background: #6366f1;
    color: #fff;
    border-radius: 7px;
    font-size: 12px;
    font-weight: 700;
    text-decoration: none;
    transition: background .15s, transform .1s;
    letter-spacing: .01em;
  }
  .rc-dl:hover  { background: #4f46e5; }
  .rc-dl:active { transform: scale(.97); }
  .rc-dl svg { flex-shrink: 0; }

  /* No PDFs state */
  .no-reports {
    margin: 12px;
    padding: 20px 16px;
    background: #f8fafc;
    border: 1.5px dashed #e2e8f0;
    border-radius: 10px;
    text-align: center;
    color: #94a3b8;
    font-size: 13px;
    line-height: 1.6;
  }
  .no-reports strong { display: block; color: #64748b; margin-bottom: 4px; font-size: 14px; }

  /* ── MAIN DASHBOARD FRAME ── */
  .dash-main { flex: 1; overflow: hidden; }
  .dash-frame { width: 100%; height: 100%; border: none; display: block; }
</style>
</head>
<body>

<!-- TOP NAV -->
<nav class="portal-nav">
  <div class="nav-left">
    <div class="nav-dot"></div>
    <span class="nav-brand">{{ company }}</span>
    <span class="nav-sep">/</span>
    <span class="nav-client">{{ business }}</span>
  </div>
  <div class="nav-right">
    <a href="/logout" class="nav-btn btn-ghost">Sign Out</a>
  </div>
</nav>

<!-- BODY -->
<div class="portal-body">

  <!-- LEFT SIDEBAR -->
  <aside class="sidebar">
    <div class="sidebar-header">
      <div class="sidebar-title">Logged in as</div>
      <div class="sidebar-biz">{{ business }}</div>
    </div>

    <div class="section-label">Monthly Reports</div>

    <div class="report-list">
      {% if pdfs %}
        {% for pdf in pdfs %}
        <div class="report-card {% if loop.first %}latest{% endif %}">
          <div class="rc-top">
            <div class="rc-period">{{ pdf.period }}</div>
            {% if loop.first %}<span class="rc-badge">Latest</span>{% endif %}
          </div>
          <div class="rc-size">PDF &nbsp;·&nbsp; {{ pdf.size }}</div>
          <a href="/download/{{ pdf.name }}" class="rc-dl">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
                 stroke="currentColor" stroke-width="2.5"
                 stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="7 10 12 15 17 10"/>
              <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            Download PDF
          </a>
        </div>
        {% endfor %}
      {% else %}
        <div class="no-reports">
          <strong>No reports yet</strong>
          Your first report will appear here after your advisor runs the monthly batch.
        </div>
      {% endif %}
    </div>
  </aside>

  <!-- MAIN DASHBOARD -->
  <main class="dash-main">
    <iframe class="dash-frame" src="/dashboard-frame"></iframe>
  </main>

</div><!-- /portal-body -->
</body>
</html>"""


# ── No dashboard yet page ─────────────────────────────────────────
NO_DASH_HTML = """<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<style>
  body { font-family: 'Segoe UI', sans-serif; background: #f8fafc;
         display:flex; align-items:center; justify-content:center;
         min-height:100vh; margin:0; }
  .box { text-align:center; }
  h2 { color:#0f172a; margin-bottom:8px; }
  p  { color:#64748b; font-size:14px; }
  .badge { display:inline-block; margin-top:20px; padding:8px 20px;
           background:#eef2ff; color:#6366f1; border-radius:20px;
           font-size:13px; font-weight:600; }
</style>
</head><body>
<div class="box">
  <h2>Your dashboard is being prepared</h2>
  <p>Your first report will appear here after your advisor runs the monthly batch.</p>
  <div class="badge">Check back soon</div>
</div>
</body></html>"""


# ═══════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════

COMPANY = os.getenv("COMPANY_NAME", "Shah Consultant")


@app.route("/")
def index():
    if "client_id" in session:
        return redirect(url_for("portal"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error   = ""
    prefill = ""

    if request.method == "POST":
        client_id = request.form.get("client_id", "").strip().lower()
        password  = request.form.get("password",  "").strip()
        prefill   = client_id

        client = _get_client(client_id)

        if not client:
            error = "Client ID not found. Please check and try again."
        elif not client.get("portal_password_hash"):
            error = "No portal password set for this account. Please contact your advisor."
        elif not _verify_password(password, client["portal_password_hash"]):
            error = "Incorrect password. Please try again."
        else:
            session["client_id"]    = client_id
            session["business"]     = client["business_name"]
            session["logged_in_at"] = datetime.datetime.now().isoformat()
            return redirect(url_for("portal"))

    return render_template_string(LOGIN_HTML,
        company=COMPANY, error=error, prefill=prefill)


@app.route("/portal")
def portal():
    if "client_id" not in session:
        return redirect(url_for("login"))

    client = _get_client(session["client_id"])
    if not client:
        session.clear()
        return redirect(url_for("login"))

    pdfs = _all_pdfs(client)

    return render_template_string(PORTAL_WRAPPER,
        company=COMPANY,
        business=client["business_name"],
        pdfs=pdfs,
    )


@app.route("/dashboard-frame")
def dashboard_frame():
    """Serve the latest dashboard HTML inside the portal iframe."""
    if "client_id" not in session:
        abort(403)

    client = _get_client(session["client_id"])
    if not client:
        abort(403)

    dash = _latest_dashboard(client)
    if not dash:
        return NO_DASH_HTML

    return dash.read_text(encoding="utf-8")


@app.route("/download/<filename>")
def download_pdf(filename: str):
    """Serve a PDF download — only for the logged-in client's own folder."""
    if "client_id" not in session:
        abort(403)

    client = _get_client(session["client_id"])
    if not client:
        abort(403)

    # Security: only serve from this client's own reports folder
    folder   = _client_folder(client)
    pdf_path = folder / filename

    if not pdf_path.exists() or pdf_path.suffix.lower() != ".pdf":
        abort(404)

    # Prevent path traversal
    try:
        pdf_path.resolve().relative_to(folder.resolve())
    except ValueError:
        abort(403)

    return send_file(str(pdf_path), as_attachment=True, download_name=filename)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ═══════════════════════════════════════════════════════════════════
# PASSWORD MANAGEMENT CLI
# ═══════════════════════════════════════════════════════════════════

def cmd_set_password(client_id: str):
    """Interactively set a portal password for a client."""
    client = _get_client(client_id)
    if not client:
        print(f"\n  Client '{client_id}' not found.")
        print("  Run: python manage_clients.py list")
        return

    print(f"\n  Setting portal password for: {client['business_name']}")

    existing = client.get("portal_password_hash")
    if existing:
        print("  (A password is already set — this will replace it)")

    while True:
        pw1 = getpass.getpass("  New password: ")
        if len(pw1) < 6:
            print("  Password must be at least 6 characters. Try again.")
            continue
        pw2 = getpass.getpass("  Confirm password: ")
        if pw1 != pw2:
            print("  Passwords don't match. Try again.")
            continue
        break

    _set_password(client_id, pw1)
    print(f"\n  Password set for {client['business_name']}.")
    print(f"  Client can now log in at http://localhost:8080")
    print(f"  Login: {client_id}  /  (password you just set)")


def cmd_list_passwords():
    """Show which clients have portal passwords set."""
    if not DB_PATH.exists():
        print("\n  clients.db not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT client_id, business_name, status, portal_password_hash FROM clients ORDER BY business_name"
    ).fetchall()
    conn.close()

    print("\n  Client Portal Access")
    print("  " + "-" * 52)
    print(f"  {'Business':<30} {'Status':<10} {'Portal'}")
    print("  " + "-" * 52)
    for r in rows:
        has_pw = "SET" if r["portal_password_hash"] else "no password"
        print(f"  {r['business_name']:<30} {r['status']:<10} {has_pw}")
    print()


# ═══════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def main():
    _ensure_password_column()

    parser = argparse.ArgumentParser(description="Client portal server")
    parser.add_argument("--port",         type=int, default=8080)
    parser.add_argument("--set-password", metavar="CLIENT_ID",
                        help="Set portal password for a client")
    parser.add_argument("--list-access",  action="store_true",
                        help="Show which clients have portal passwords")
    args = parser.parse_args()

    if args.set_password:
        cmd_set_password(args.set_password)
        return

    if args.list_access:
        cmd_list_passwords()
        return

    # ── Start server ─────────────────────────────────────────────
    print(f"\n  Client Portal")
    print(f"  " + "-" * 46)
    print(f"  URL      : http://localhost:{args.port}")
    print(f"  To stop  : Press Ctrl+C")
    print(f"  Passwords: python client_portal.py --set-password <client_id>")
    print(f"  " + "-" * 46)
    print()

    app.run(host="0.0.0.0", port=args.port, debug=False)


if __name__ == "__main__":
    main()
