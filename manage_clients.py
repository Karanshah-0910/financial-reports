"""
manage_clients.py
-----------------
Client management system using SQLite.
One file database — no server, no setup, works instantly.

COMMANDS:
  python manage_clients.py add              Add a new client (guided prompts)
  python manage_clients.py list            List all active clients
  python manage_clients.py list --all      List every client (including paused/churned)
  python manage_clients.py show <id>       Show full details for one client
  python manage_clients.py update <id>     Update any field for a client
  python manage_clients.py deactivate <id> Pause or churn a client
  python manage_clients.py search <name>   Search by business name or email

DATABASE:
  Saved to clients.db in the project folder.
  Back it up by just copying clients.db — that's all there is to it.
"""

import sqlite3
import sys
import os
import pathlib
from datetime import date


# ── Database location ────────────────────────────────────────────────────────
DB_PATH = pathlib.Path(__file__).parent / "clients.db"


# ── Connect + auto-create table ──────────────────────────────────────────────
def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row      # lets us access columns by name
    conn.execute("PRAGMA journal_mode=WAL")   # safe for concurrent reads
    _create_table(conn)
    return conn


def _create_table(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            client_id        TEXT PRIMARY KEY,
            business_name    TEXT NOT NULL,
            contact_email    TEXT,
            industry         TEXT,
            monthly_fee      REAL DEFAULT 0,
            qbo_company_id   TEXT,
            qbo_refresh_token TEXT,
            onboarding_date  TEXT,
            status           TEXT DEFAULT 'active'
                             CHECK(status IN ('active','paused','churned')),
            notes            TEXT,
            created_at       TEXT DEFAULT (date('now')),
            updated_at       TEXT DEFAULT (date('now'))
        )
    """)
    conn.commit()


# ── Pretty printing helpers ──────────────────────────────────────────────────
def _divider(char="-", width=70):
    print(char * width)


def _status_badge(status: str) -> str:
    return {"active": "[ACTIVE]", "paused": "[PAUSED]", "churned": "[CHURNED]"}.get(status, status)


def _fee(val) -> str:
    if val is None or val == 0:
        return "n/a"
    return f"${float(val):,.0f}/mo"


def _ask(prompt: str, default: str = "", required: bool = False) -> str:
    """Prompt the user for input with an optional default."""
    hint = f" [{default}]" if default else ""
    while True:
        val = input(f"  {prompt}{hint}: ").strip()
        if val == "" and default:
            return default
        if val == "" and required:
            print("    This field is required.")
            continue
        return val


def _ask_fee(prompt: str, default: str = "") -> float:
    """Prompt for a dollar amount — strips $, commas, etc."""
    hint = f" [{default}]" if default else ""
    while True:
        raw = input(f"  {prompt}{hint}: ").strip()
        if raw == "" and default:
            try:
                return float(default.replace("$", "").replace(",", ""))
            except Exception:
                return 0.0
        if raw == "":
            return 0.0
        try:
            return float(raw.replace("$", "").replace(",", ""))
        except ValueError:
            print("    Enter a number (e.g. 500 or 1500).")


def _make_client_id(business_name: str) -> str:
    """'Riverside Home Goods' → 'riverside_home_goods'"""
    import re
    slug = re.sub(r"[^a-z0-9]+", "_", business_name.lower()).strip("_")
    return slug


# ── COMMAND: add ─────────────────────────────────────────────────────────────
def cmd_add():
    """Guided prompts to add a new client. Under 60 seconds."""
    print()
    _divider("=")
    print("  ADD NEW CLIENT")
    _divider("=")
    print("  Press Enter to skip optional fields.\n")

    business_name = _ask("Business name", required=True)
    suggested_id  = _make_client_id(business_name)
    client_id     = _ask("Client ID (no spaces)", default=suggested_id)
    contact_email = _ask("Contact email")
    industry      = _ask("Industry (e.g. Retail, SaaS, Restaurant)")
    monthly_fee   = _ask_fee("Monthly reporting fee ($)")
    qbo_company_id = _ask("QuickBooks Company ID (realmId) — leave blank if not connected yet")
    onboarding_date = _ask("Onboarding date", default=str(date.today()))
    notes         = _ask("Notes (optional)")

    # Check for duplicate ID
    with _connect() as conn:
        existing = conn.execute(
            "SELECT client_id FROM clients WHERE client_id = ?", (client_id,)
        ).fetchone()
        if existing:
            print(f"\n  Error: A client with ID '{client_id}' already exists.")
            print(f"  Use a different ID or run: python manage_clients.py show {client_id}")
            return

        conn.execute("""
            INSERT INTO clients
                (client_id, business_name, contact_email, industry,
                 monthly_fee, qbo_company_id, onboarding_date, notes, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
        """, (client_id, business_name, contact_email or None, industry or None,
              monthly_fee, qbo_company_id or None, onboarding_date, notes or None))
        conn.commit()

    print()
    _divider()
    print(f"  Client added successfully!")
    print(f"  ID            : {client_id}")
    print(f"  Business      : {business_name}")
    print(f"  Fee           : {_fee(monthly_fee)}")
    print(f"  Status        : ● ACTIVE")
    _divider()

    if not qbo_company_id:
        print(f"\n  Next step — connect QuickBooks:")
        print(f"    python qbo_auth.py {client_id}")


# ── COMMAND: list ────────────────────────────────────────────────────────────
def cmd_list(show_all: bool = False):
    """Print a table of all clients."""
    with _connect() as conn:
        if show_all:
            rows = conn.execute(
                "SELECT * FROM clients ORDER BY status, business_name"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM clients WHERE status = 'active' ORDER BY business_name"
            ).fetchall()

    if not rows:
        msg = "No clients found." if show_all else "No active clients. Run: python manage_clients.py add"
        print(f"\n  {msg}\n")
        return

    print()
    _divider("=")
    label = "ALL CLIENTS" if show_all else "ACTIVE CLIENTS"
    print(f"  {label}  ({len(rows)} total)")
    _divider("=")

    # Header
    print(f"  {'ID':<28} {'Business Name':<26} {'Fee':>8}  {'QB':>4}  Status")
    _divider()

    for r in rows:
        qb_flag = "Y" if r["qbo_company_id"] else "-"
        fee_str = _fee(r["monthly_fee"])
        status  = _status_badge(r["status"])
        name    = r["business_name"][:25]
        cid     = r["client_id"][:27]
        print(f"  {cid:<28} {name:<26} {fee_str:>8}  {qb_flag:>4}  {status}")

    _divider()

    # Revenue summary for active clients
    active = [r for r in rows if r["status"] == "active"]
    if active:
        total_mrr = sum(r["monthly_fee"] or 0 for r in active)
        print(f"  Active clients: {len(active)}   Monthly recurring revenue: ${total_mrr:,.0f}/mo")
    print()


# ── COMMAND: show ─────────────────────────────────────────────────────────────
def cmd_show(client_id: str):
    """Print full details for one client."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM clients WHERE client_id = ?", (client_id,)
        ).fetchone()

    if not row:
        print(f"\n  Client '{client_id}' not found.")
        print(f"  Run 'python manage_clients.py list --all' to see all client IDs.")
        return

    print()
    _divider("=")
    print(f"  CLIENT: {row['business_name']}")
    _divider("=")
    print(f"  Client ID       : {row['client_id']}")
    print(f"  Business Name   : {row['business_name']}")
    print(f"  Contact Email   : {row['contact_email'] or 'n/a'}")
    print(f"  Industry        : {row['industry'] or 'n/a'}")
    print(f"  Monthly Fee     : {_fee(row['monthly_fee'])}")
    print(f"  Status          : {_status_badge(row['status'])}")
    print(f"  Onboarding Date : {row['onboarding_date'] or 'n/a'}")
    print(f"  QB Company ID   : {row['qbo_company_id'] or '(not connected)'}")
    has_token = "Stored" if row["qbo_refresh_token"] else "None"
    print(f"  QB Refresh Token: {has_token}")
    print(f"  Notes           : {row['notes'] or 'n/a'}")
    print(f"  Added           : {row['created_at']}")
    print(f"  Last Updated    : {row['updated_at']}")
    _divider()

    if not row["qbo_company_id"]:
        print(f"\n  QuickBooks not connected. Connect with:")
        print(f"    python qbo_auth.py {row['client_id']}\n")


# ── COMMAND: update ──────────────────────────────────────────────────────────
def cmd_update(client_id: str):
    """Update one or more fields for a client."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM clients WHERE client_id = ?", (client_id,)
        ).fetchone()

        if not row:
            print(f"\n  Client '{client_id}' not found.")
            return

        print()
        _divider("=")
        print(f"  UPDATE: {row['business_name']}")
        _divider("=")
        print("  Press Enter to keep the current value. Type new value to change it.\n")

        fields = {
            "business_name":  ("Business name",        str,   row["business_name"]),
            "contact_email":  ("Contact email",         str,   row["contact_email"] or ""),
            "industry":       ("Industry",              str,   row["industry"] or ""),
            "monthly_fee":    ("Monthly fee ($)",       float, row["monthly_fee"] or 0),
            "qbo_company_id": ("QB Company ID",         str,   row["qbo_company_id"] or ""),
            "notes":          ("Notes",                 str,   row["notes"] or ""),
        }

        updates = {}
        for col, (label, typ, current) in fields.items():
            display = f"${current:,.0f}" if typ == float else str(current)
            if typ == float:
                new_val = _ask_fee(label, default=display)
            else:
                new_val = _ask(label, default=display)
            if str(new_val) != str(current):
                updates[col] = new_val

        if not updates:
            print("\n  No changes made.")
            return

        updates["updated_at"] = str(date.today())
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values     = list(updates.values()) + [client_id]
        conn.execute(f"UPDATE clients SET {set_clause} WHERE client_id = ?", values)
        conn.commit()

    print()
    _divider()
    print(f"  Updated {len(updates) - 1} field(s) for {row['business_name']}.")
    changed = [k for k in updates if k != "updated_at"]
    for k in changed:
        print(f"    {k} → {updates[k]}")
    _divider()


# ── COMMAND: deactivate ──────────────────────────────────────────────────────
def cmd_deactivate(client_id: str):
    """Set a client to paused or churned."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM clients WHERE client_id = ?", (client_id,)
        ).fetchone()

        if not row:
            print(f"\n  Client '{client_id}' not found.")
            return

        print()
        _divider("=")
        print(f"  DEACTIVATE: {row['business_name']}")
        _divider("=")
        print(f"  Current status: {_status_badge(row['status'])}\n")
        print("  What would you like to do?")
        print("    1 — Pause  (temporary, e.g. seasonal break)")
        print("    2 — Churn  (client left, stop all reporting)")
        print("    3 — Cancel (do nothing)\n")

        choice = input("  Enter 1, 2, or 3: ").strip()
        if choice == "1":
            new_status = "paused"
        elif choice == "2":
            new_status = "churned"
        else:
            print("  Cancelled. Nothing changed.")
            return

        conn.execute(
            "UPDATE clients SET status = ?, updated_at = ? WHERE client_id = ?",
            (new_status, str(date.today()), client_id)
        )
        conn.commit()

    print()
    _divider()
    print(f"  {row['business_name']} → {_status_badge(new_status)}")
    if new_status == "paused":
        print(f"  Reactivate later with: python manage_clients.py update {client_id}")
    print()


# ── COMMAND: search ──────────────────────────────────────────────────────────
def cmd_search(query: str):
    """Search clients by name or email (partial match)."""
    with _connect() as conn:
        rows = conn.execute("""
            SELECT * FROM clients
            WHERE lower(business_name) LIKE ?
               OR lower(contact_email) LIKE ?
               OR lower(client_id) LIKE ?
            ORDER BY business_name
        """, (f"%{query.lower()}%",) * 3).fetchall()

    if not rows:
        print(f"\n  No clients found matching '{query}'.\n")
        return

    print(f"\n  Found {len(rows)} match(es) for '{query}':\n")
    for r in rows:
        print(f"  {r['client_id']:<30} {r['business_name']:<28} {_status_badge(r['status'])}")
    print()


# ── COMMAND: reactivate ──────────────────────────────────────────────────────
def cmd_reactivate(client_id: str):
    """Set a paused/churned client back to active."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM clients WHERE client_id = ?", (client_id,)
        ).fetchone()
        if not row:
            print(f"\n  Client '{client_id}' not found.")
            return
        if row["status"] == "active":
            print(f"\n  {row['business_name']} is already active.")
            return
        conn.execute(
            "UPDATE clients SET status = 'active', updated_at = ? WHERE client_id = ?",
            (str(date.today()), client_id)
        )
        conn.commit()
    print(f"\n  {row['business_name']} → ● ACTIVE\n")


# ── Entry point ───────────────────────────────────────────────────────────────
def _usage():
    print("""
Usage:
  python manage_clients.py add                  Add a new client
  python manage_clients.py list                 List active clients
  python manage_clients.py list --all           List all clients (including paused/churned)
  python manage_clients.py show <client_id>     Full details for one client
  python manage_clients.py update <client_id>   Update client fields
  python manage_clients.py deactivate <id>      Pause or churn a client
  python manage_clients.py reactivate <id>      Set client back to active
  python manage_clients.py search <name>        Search by name or email

Examples:
  python manage_clients.py add
  python manage_clients.py show riverside_home_goods
  python manage_clients.py update riverside_home_goods
  python manage_clients.py search "oak"
""")


def main():
    args = sys.argv[1:]
    if not args:
        _usage()
        sys.exit(0)

    cmd = args[0].lower()

    if cmd == "add":
        cmd_add()

    elif cmd == "list":
        show_all = "--all" in args
        cmd_list(show_all=show_all)

    elif cmd == "show":
        if len(args) < 2:
            print("  Usage: python manage_clients.py show <client_id>")
        else:
            cmd_show(args[1])

    elif cmd == "update":
        if len(args) < 2:
            print("  Usage: python manage_clients.py update <client_id>")
        else:
            cmd_update(args[1])

    elif cmd == "deactivate":
        if len(args) < 2:
            print("  Usage: python manage_clients.py deactivate <client_id>")
        else:
            cmd_deactivate(args[1])

    elif cmd == "reactivate":
        if len(args) < 2:
            print("  Usage: python manage_clients.py reactivate <client_id>")
        else:
            cmd_reactivate(args[1])

    elif cmd == "search":
        if len(args) < 2:
            print("  Usage: python manage_clients.py search <name>")
        else:
            cmd_search(args[1])

    else:
        print(f"\n  Unknown command: '{cmd}'")
        _usage()


if __name__ == "__main__":
    main()
