"""
onboard_client.py
-----------------
Run this when you sign a new client.

What it does:
  1. Asks you for the client's info (guided prompts)
  2. Adds them to clients.db
  3. Creates their folder structure (reports, data, etc.)
  4. Prints a ready-to-send onboarding email you can copy into Gmail

How to run:
  python onboard_client.py

Takes about 2 minutes. At the end you get a complete email to copy-paste.
"""

import sys
import os
import json
import sqlite3
import pathlib
import datetime
import textwrap

ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

DB_PATH = ROOT / "clients.db"

# ── Your details (pulled from .env) ──────────────────────────────────────────
YOUR_NAME     = os.getenv("REPORT_AUTHOR",  "Karan Shah")
YOUR_EMAIL    = os.getenv("SMTP_USER",       "karanshah0910@gmail.com")
YOUR_COMPANY  = os.getenv("COMPANY_NAME",    "Shah Consultant")

# ── Paste your links here once — they go into every onboarding email ──────────
# Calendly: go to calendly.com, create a free account, make a 30-min event,
#           copy the link. Looks like: https://calendly.com/yourname/30min
CALENDLY_LINK = os.getenv("CALENDLY_LINK", "https://calendly.com/YOUR_LINK_HERE")

# Google Form: make one at forms.google.com, click Share, copy the link
GOOGLE_FORM_LINK = os.getenv("GOOGLE_FORM_LINK", "https://forms.gle/YOUR_FORM_LINK_HERE")

# The URL clients click to authorize QuickBooks
# When qbo_callback.py is running locally with ngrok, this gets replaced automatically.
# Default is the manual copy-paste flow (works without ngrok).
QB_AUTH_BASE  = os.getenv("QB_AUTH_BASE", "manual")


# ── DB helpers ────────────────────────────────────────────────────────────────
def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _client_exists(client_id: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM clients WHERE client_id = ?", (client_id,)
        ).fetchone()
    return bool(row)


def _save_client(data: dict):
    with _connect() as conn:
        conn.execute("""
            INSERT INTO clients
                (client_id, business_name, contact_email, industry,
                 monthly_fee, qbo_company_id, onboarding_date, status, notes)
            VALUES (:client_id, :business_name, :contact_email, :industry,
                    :monthly_fee, NULL, :onboarding_date, 'active', :notes)
        """, data)
        conn.commit()


# ── Input helpers ─────────────────────────────────────────────────────────────
def _ask(prompt: str, default: str = "", required: bool = False) -> str:
    hint = f" [{default}]" if default else ""
    while True:
        val = input(f"  {prompt}{hint}: ").strip()
        if val == "" and default:
            return default
        if val == "" and required:
            print("    This field is required.")
            continue
        return val


def _ask_fee(prompt: str) -> float:
    while True:
        raw = input(f"  {prompt}: ").strip().replace("$", "").replace(",", "")
        if raw == "":
            return 0.0
        try:
            return float(raw)
        except ValueError:
            print("    Enter a number (e.g. 750)")


def _make_id(name: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


# ── Folder creation ───────────────────────────────────────────────────────────
def _create_folders(client_id: str, business_name: str) -> dict:
    """
    Creates the standard folder structure for a new client.
    Returns a dict of paths created.
    """
    safe = business_name.replace(" ", "_")
    folders = {
        "reports":  ROOT / "reports"  / safe,
        "raw_data": ROOT / "data" / "raw" / client_id,
        "processed":ROOT / "data" / "processed" / client_id,
    }
    for label, path in folders.items():
        path.mkdir(parents=True, exist_ok=True)

    # Write a README into the reports folder
    readme = folders["reports"] / "README.txt"
    readme.write_text(
        f"Reports for {business_name}\n"
        f"Client ID: {client_id}\n"
        f"Onboarded: {datetime.date.today()}\n\n"
        f"Files in this folder are ready for your review.\n"
        f"Send to client manually after reviewing.\n",
        encoding="utf-8"
    )
    return folders


# ── QB auth URL builder ───────────────────────────────────────────────────────
def _build_auth_url(client_id: str) -> str:
    """
    Build the QuickBooks authorization URL for this client.
    If QB_AUTH_BASE is set to a real ngrok/server URL, uses the callback flow.
    Otherwise returns 'manual' instructions.
    """
    import urllib.parse
    qb_client_id  = os.getenv("QB_CLIENT_ID", "")
    redirect_uri  = os.getenv("QB_REDIRECT_URI",
                              "https://developer.intuit.com/v2/OAuth2Playground/RedirectUrl")

    if not qb_client_id:
        return "QB_CLIENT_ID not set in .env"

    params = {
        "client_id":     qb_client_id,
        "response_type": "code",
        "scope":         "com.intuit.quickbooks.accounting",
        "redirect_uri":  redirect_uri,
        "state":         client_id,   # We pass client_id as state so callback knows who this is
    }
    return "https://appcenter.intuit.com/connect/oauth2?" + urllib.parse.urlencode(params)


# ── Onboarding email generator ────────────────────────────────────────────────
def _build_email(client: dict, auth_url: str) -> str:
    name      = client["owner_name"].split()[0]   # First name
    business  = client["business_name"]
    manual    = (QB_AUTH_BASE == "manual")

    if manual:
        qb_section = f"""\
To connect your QuickBooks account, please follow these steps:

  1. Click this link to authorize access:
     {auth_url}

  2. Log into QuickBooks when prompted and click "Connect"

  3. You'll land on a page — copy the "code" and "realmId" values
     from the URL and reply to this email with them.
     (I'll complete the connection on my end within 24 hours.)"""
    else:
        qb_section = f"""\
To connect your QuickBooks account, simply click the link below
and log in. The system will handle everything automatically:

  {auth_url}

  This takes about 60 seconds. Once done, you're all set."""

    email = f"""\
Subject: Welcome to {YOUR_COMPANY} — 3 quick steps to get started

Hi {name},

Welcome aboard! I'm excited to start working with you and {business}.

To get your first report ready, I just need three things from you.
Each takes less than 2 minutes:

---

STEP 1 — Connect QuickBooks (so I can pull your financials)
{qb_section}

---

STEP 2 — Fill out a quick business context form (2 min)
This helps me write insights that are specific to your business,
not just generic financial commentary.

  {GOOGLE_FORM_LINK}

Questions include: top KPIs you track, key competitors,
growth goals for this year, and biggest financial pain points.

---

STEP 3 — Book our kickoff call (30 min)
Once QuickBooks is connected, I'll pull your last 12 months of
data and prepare a baseline analysis before we talk.

  {CALENDLY_LINK}

---

Once all three are done, you'll receive your first full report
within 48 hours.

Looking forward to working together.

Best regards,
{YOUR_NAME}
{YOUR_COMPANY}
{YOUR_EMAIL}
"""
    return email


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print()
    print("=" * 60)
    print("  NEW CLIENT ONBOARDING")
    print("=" * 60)
    print("  Press Enter to accept the suggested value in [brackets].\n")

    # ── Collect client info ───────────────────────────────────────────────
    business_name = _ask("Business name", required=True)
    client_id     = _ask("Client ID (no spaces)", default=_make_id(business_name))
    owner_name    = _ask("Owner / main contact name", required=True)
    contact_email = _ask("Their email address", required=True)
    industry      = _ask("Industry (e.g. Retail, Restaurant, SaaS, Construction)")
    monthly_fee   = _ask_fee("Monthly reporting fee ($)")
    notes         = _ask("Notes (optional)")
    today         = str(datetime.date.today())

    # ── Check for duplicate ───────────────────────────────────────────────
    if _client_exists(client_id):
        print(f"\n  Client ID '{client_id}' already exists.")
        print(f"  Use: python manage_clients.py show {client_id}")
        sys.exit(1)

    # ── Confirm before saving ─────────────────────────────────────────────
    print()
    print("-" * 60)
    print(f"  Business  : {business_name}")
    print(f"  Client ID : {client_id}")
    print(f"  Owner     : {owner_name}")
    print(f"  Email     : {contact_email}")
    print(f"  Industry  : {industry or 'n/a'}")
    print(f"  Fee       : ${monthly_fee:,.0f}/mo" if monthly_fee else "  Fee       : n/a")
    print("-" * 60)
    confirm = input("\n  Save this client? [Y/n]: ").strip().lower()
    if confirm == "n":
        print("  Cancelled.")
        sys.exit(0)

    # ── Save to DB ────────────────────────────────────────────────────────
    _save_client({
        "client_id":       client_id,
        "business_name":   business_name,
        "contact_email":   contact_email,
        "industry":        industry or None,
        "monthly_fee":     monthly_fee,
        "onboarding_date": today,
        "notes":           notes or None,
    })
    print(f"\n  Saved to clients.db")

    # ── Create folders ────────────────────────────────────────────────────
    folders = _create_folders(client_id, business_name)
    print(f"  Folders created:")
    for label, path in folders.items():
        print(f"    {path}")

    # ── Build auth URL and email ──────────────────────────────────────────
    auth_url = _build_auth_url(client_id)
    client_data = {
        "client_id":    client_id,
        "business_name": business_name,
        "owner_name":   owner_name,
        "contact_email": contact_email,
    }
    email_text = _build_email(client_data, auth_url)

    # ── Save email to file ────────────────────────────────────────────────
    email_dir  = ROOT / "reports" / business_name.replace(" ", "_")
    email_file = email_dir / f"onboarding_email_{today}.txt"
    email_file.write_text(email_text, encoding="utf-8")

    # ── Print summary ─────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  ONBOARDING COMPLETE")
    print("=" * 60)
    print(f"\n  Client ID : {client_id}")
    print(f"  DB        : clients.db (status = active)")
    print(f"  Folders   : reports/{business_name.replace(' ','_')}/")
    print(f"  Email     : {email_file}")
    print()
    print("  NEXT STEPS:")
    print(f"  1. Copy the email below (or open {email_file.name})")
    print(f"     and send it to {contact_email}")
    print(f"  2. When they authorize QB, run:")
    print(f"     python qbo_auth.py {client_id}")
    print(f"  3. After auth, run the baseline analysis:")
    print(f"     python generate_baseline.py {client_id}")
    print()
    print("=" * 60)
    print("  ONBOARDING EMAIL (copy and paste into Gmail):")
    print("=" * 60)
    print()
    print(email_text)


if __name__ == "__main__":
    main()
