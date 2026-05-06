"""
qbo_fetch.py
------------
Pull financial reports from a connected QuickBooks Online company.
Run this to test the QB connection or preview the raw data.

The client must be connected first (run qbo_auth.py if not).

HOW TO RUN:
  # Pull all 3 reports for a client (most recent month)
  python qbo_fetch.py riverside_home_goods

  # Pull for a specific month
  python qbo_fetch.py riverside_home_goods --year 2025 --month 4

  # Pull only one report type
  python qbo_fetch.py riverside_home_goods --pnl
  python qbo_fetch.py riverside_home_goods --balance-sheet
  python qbo_fetch.py riverside_home_goods --cash-flow

WHAT THIS PULLS:
  - Profit & Loss   : Revenue, COGS, expenses, net profit for the month
  - Balance Sheet   : Assets, liabilities, equity as of month-end
  - Cash Flow       : Operating, investing, financing cash flows

Data is saved to data/raw/{client_id}/ as JSON files.
The generate_report.py script reads from this data automatically.
"""

import sys
import os
import json
import pathlib
import datetime

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from src.quickbooks.auth      import tokens_exist
from src.quickbooks.data_pull import (
    get_pnl_last_3_months,
    get_balance_sheet,
    get_cash_flow,
)

RAW_DATA_DIR = pathlib.Path(__file__).parent / "data" / "raw"
CLIENTS_DIR  = pathlib.Path(__file__).parent / "clients"


def load_client_profile(client_id: str) -> dict:
    path = CLIENTS_DIR / f"{client_id}.json"
    if not path.exists():
        print(f"Error: No client profile found at {path}")
        print(f"Create one based on clients/riverside_home_goods.json")
        sys.exit(1)
    return json.loads(path.read_text())


def save_raw(client_id: str, report_type: str, data: dict, year: int, month: int):
    """Save raw API response to data/raw/{client_id}/."""
    folder = RAW_DATA_DIR / client_id
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{year}-{month:02d}_{report_type}.json"
    path     = folder / filename
    path.write_text(json.dumps(data, indent=2))
    print(f"  Saved -> {path}")
    return str(path)


def pull_all(client_id: str, business_name: str, year: int, month: int,
             do_pnl: bool = True, do_bs: bool = True, do_cf: bool = True):
    """Pull all requested reports and save to data/raw/."""

    print(f"\nFetching QuickBooks data for: {business_name}")
    print(f"Period : {year}-{month:02d}")
    print("-" * 50)

    results = {}

    if do_pnl:
        print("\n[1/3] Profit & Loss (3-month trend)...")
        pnl = get_pnl_last_3_months(client_id, business_name, year, month)
        path = save_raw(client_id, "pnl", pnl, year, month)
        results["pnl"] = pnl
        print(f"  Line items pulled: {sum(len(v) for v in pnl['months'].values())}")

    if do_bs:
        print("\n[2/3] Balance Sheet...")
        bs = get_balance_sheet(client_id, business_name, year, month)
        path = save_raw(client_id, "balance_sheet", bs, year, month)
        results["balance_sheet"] = bs
        assets = sum(bs["assets"]["current_assets"].values())
        print(f"  Current assets: ${assets:,.0f}")

    if do_cf:
        print("\n[3/3] Cash Flow Statement...")
        cf = get_cash_flow(client_id, business_name, year, month)
        path = save_raw(client_id, "cash_flow", cf, year, month)
        results["cash_flow"] = cf
        operating = sum(cf["operating_activities"].values())
        print(f"  Total operating cash: ${operating:,.0f}")

    print("\n" + "=" * 50)
    print("  All reports fetched successfully.")
    print(f"  Files saved to: data/raw/{client_id}/")
    print("=" * 50)
    return results


def main():
    args = sys.argv[1:]

    if not args or "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    client_id = next((a for a in args if not a.startswith("--")), None)
    if not client_id:
        print("Error: please provide a client_id")
        print("Usage: python qbo_fetch.py <client_id> [--year YYYY] [--month MM]")
        sys.exit(1)

    # Check connection
    if not tokens_exist(client_id):
        print(f"\nError: {client_id} is not connected to QuickBooks.")
        print(f"Run first: python qbo_auth.py {client_id}")
        sys.exit(1)

    # Year / month (default = most recent completed month)
    now   = datetime.date.today()
    year  = int(next((args[i+1] for i, a in enumerate(args) if a == "--year"),  now.year))
    month = int(next((args[i+1] for i, a in enumerate(args) if a == "--month"), now.month - 1 or 12))
    if month == 0:
        month = 12
        year -= 1

    # Which reports?
    any_specific = any(a in args for a in ("--pnl", "--balance-sheet", "--cash-flow"))
    do_pnl = not any_specific or "--pnl"           in args
    do_bs  = not any_specific or "--balance-sheet"  in args
    do_cf  = not any_specific or "--cash-flow"      in args

    profile       = load_client_profile(client_id)
    business_name = profile.get("business_name", client_id.replace("_", " ").title())

    pull_all(client_id, business_name, year, month, do_pnl, do_bs, do_cf)


if __name__ == "__main__":
    main()
