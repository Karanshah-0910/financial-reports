"""
qbo_auth.py
-----------
Connect a QuickBooks Online company to this system.
Run this ONCE per client — it stores their tokens so you never have to log in again.

HOW OAUTH WORKS (plain English):
  Think of it like a hotel key card system.
  - Your app (the key card machine) says to QuickBooks: "This person wants access."
  - The client logs into QuickBooks directly (you never see their password).
  - QuickBooks gives YOUR app a key card (access token) that works for 1 hour.
  - It also gives you a "master key" (refresh token) that lets you make new key cards
    automatically without bothering the client again — good for 100 days.
  - This system stores both keys in clients/tokens/{client_id}_tokens.json.

WHAT YOU NEED BEFORE RUNNING:
  1. Your QB_CLIENT_ID and QB_CLIENT_SECRET must be in .env
  2. The client's profile must exist in clients/{client_id}.json
  3. QuickBooks Sandbox or Production must be set in .env (QB_ENVIRONMENT)

HOW TO RUN:
  python qbo_auth.py riverside_home_goods
  python qbo_auth.py blue_oak_consulting

WHAT HAPPENS:
  1. Your browser opens the QuickBooks login page
  2. The client (or you, in sandbox) logs in and clicks "Connect"
  3. QuickBooks shows a page with a URL containing code= and realmId=
  4. You copy-paste those two values back here
  5. Done — tokens saved, client is connected

To check if a client is already connected:
  python qbo_auth.py --status riverside_home_goods

To list all connected clients:
  python qbo_auth.py --list
"""

import sys
import os
import json
import pathlib

# Ensure we can import from src/
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from src.quickbooks.auth import (
    run_auth_flow,
    load_tokens,
    tokens_exist,
    get_company_id,
)

CLIENTS_DIR = pathlib.Path(__file__).parent / "clients"
TOKENS_DIR  = CLIENTS_DIR / "tokens"


def list_connected() -> None:
    """Print all clients that have saved tokens."""
    print("\nConnected QuickBooks clients:")
    print("-" * 40)
    if not TOKENS_DIR.exists():
        print("  (none yet)")
        return

    found = False
    for f in sorted(TOKENS_DIR.glob("*_tokens.json")):
        client_id = f.stem.replace("_tokens", "")
        tokens    = json.loads(f.read_text())
        company   = tokens.get("company_id", "unknown")
        import time
        saved_at  = tokens.get("saved_at", 0)
        age_days  = (time.time() - saved_at) / 86400
        print(f"  {client_id:<30}  company: {company}  ({age_days:.0f} days ago)")
        found = True

    if not found:
        print("  (none yet)")
    print()


def show_status(client_id: str) -> None:
    """Show connection status for one client."""
    if tokens_exist(client_id):
        tokens     = load_tokens(client_id)
        company_id = tokens.get("company_id", "unknown")
        import time
        saved_at   = tokens.get("saved_at", 0)
        age_hours  = (time.time() - saved_at) / 3600
        print(f"\n  {client_id}: CONNECTED")
        print(f"  Company ID : {company_id}")
        print(f"  Token age  : {age_hours:.1f} hours")
        print(f"  Token file : {TOKENS_DIR / (client_id + '_tokens.json')}")
    else:
        print(f"\n  {client_id}: NOT connected")
        print(f"  Run: python qbo_auth.py {client_id}")
    print()


def main():
    args = sys.argv[1:]

    if not args or "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    if "--list" in args:
        list_connected()
        sys.exit(0)

    if "--status" in args:
        idx = args.index("--status")
        if idx + 1 >= len(args):
            print("Error: --status requires a client_id")
            sys.exit(1)
        show_status(args[idx + 1])
        sys.exit(0)

    # Default: run auth flow for the given client_id
    client_id = next((a for a in args if not a.startswith("--")), None)
    if not client_id:
        print("Error: please provide a client_id")
        print("Usage: python qbo_auth.py <client_id>")
        sys.exit(1)

    # Check if already connected
    if tokens_exist(client_id):
        tokens = load_tokens(client_id)
        import time
        age_hours = (time.time() - tokens.get("saved_at", 0)) / 3600
        print(f"\n  Note: {client_id} already has tokens ({age_hours:.1f} hours old).")
        ans = input("  Re-authorize? This will replace the existing tokens. [y/N]: ").strip().lower()
        if ans != "y":
            print("  Keeping existing tokens. Nothing changed.")
            sys.exit(0)

    run_auth_flow(client_id)


if __name__ == "__main__":
    main()
