"""
app.py
------
Flask web app for the client portal.
Clients log in and download their past PDF reports.

Run with:
  python portal/app.py
"""

import os
import json
import hashlib
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, send_file, flash
)
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("PORTAL_SECRET_KEY", "change-this-in-production-123")

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "reports", "output")
CLIENTS_DIR = os.path.join(os.path.dirname(__file__), "..", "clients")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _load_portal_users() -> dict:
    """
    Load portal credentials from clients/*.json files.
    Each client needs a 'portal_password' field added to their config.
    """
    users = {}
    for fname in os.listdir(CLIENTS_DIR):
        if not fname.endswith(".json"):
            continue
        try:
            path = os.path.join(CLIENTS_DIR, fname)
            with open(path) as f:
                client = json.load(f)
            username = client.get("client_id")
            password = client.get("portal_password")
            if username and password:
                users[username] = {
                    "password_hash":  _hash(password),
                    "business_name":  client.get("business_name", username),
                    "owner_name":     client.get("owner_name", ""),
                    "client_id":      username,
                }
        except Exception:
            continue
    return users


def _get_reports(client_id: str) -> list:
    """Return list of PDF reports for this client, newest first."""
    reports = []
    if not os.path.exists(REPORTS_DIR):
        return reports

    # Match files that start with the business name slug
    users  = _load_portal_users()
    user   = users.get(client_id, {})
    name   = user.get("business_name", "").replace(" ", "_")

    for fname in sorted(os.listdir(REPORTS_DIR), reverse=True):
        if fname.endswith(".pdf") and fname.startswith(name):
            fpath    = os.path.join(REPORTS_DIR, fname)
            stat     = os.stat(fpath)
            # Parse month from filename e.g. Riverside_Home_Goods_April_2025_Report.pdf
            parts    = fname.replace(".pdf", "").split("_")
            try:
                month = parts[-3] + " " + parts[-2]
            except IndexError:
                month = fname
            reports.append({
                "filename":  fname,
                "month":     month,
                "size_kb":   round(stat.st_size / 1024, 1),
                "created":   datetime.fromtimestamp(stat.st_mtime).strftime("%b %d, %Y"),
            })
    return reports


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    if "client_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        users    = _load_portal_users()

        user = users.get(username)
        if user and user["password_hash"] == _hash(password):
            session["client_id"]     = username
            session["business_name"] = user["business_name"]
            session["owner_name"]    = user["owner_name"]
            return redirect(url_for("dashboard"))
        else:
            flash("Incorrect username or password. Please try again.")

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    if "client_id" not in session:
        return redirect(url_for("login"))

    reports = _get_reports(session["client_id"])
    return render_template(
        "dashboard.html",
        business_name=session.get("business_name", ""),
        owner_name=session.get("owner_name", ""),
        reports=reports,
        now=datetime.now().strftime("%B %Y"),
    )


@app.route("/download/<filename>")
def download(filename):
    if "client_id" not in session:
        return redirect(url_for("login"))

    # Security: only serve files that belong to this client
    users = _load_portal_users()
    user  = users.get(session["client_id"], {})
    name  = user.get("business_name", "").replace(" ", "_")

    if not filename.startswith(name) or not filename.endswith(".pdf"):
        flash("File not found.")
        return redirect(url_for("dashboard"))

    filepath = os.path.join(REPORTS_DIR, filename)
    if not os.path.exists(filepath):
        flash("Report not found.")
        return redirect(url_for("dashboard"))

    return send_file(filepath, as_attachment=True, download_name=filename)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  CLIENT PORTAL")
    print("  Running at: http://localhost:5000")
    print("=" * 50 + "\n")
    app.run(debug=True, port=5000)
