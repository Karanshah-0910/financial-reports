"""
test_qbo_connection.py
----------------------
Quick smoke test to verify your QuickBooks sandbox connection is working.
Run this after completing qbo_auth.py for the first time.

How to run:
  python test_qbo_connection.py riverside_home_goods

What it checks:
  1. Tokens exist and load correctly
  2. Access token is valid (or can be refreshed)
  3. QuickBooks API responds (company info endpoint)
  4. P&L report can be pulled
  5. Balance Sheet can be pulled
  6. Cash Flow can be pulled

If all 6 pass, your connection is fully working and you're ready to generate real reports.
"""

import sys
import json
import pathlib
import datetime
import requests

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from src.quickbooks.auth      import tokens_exist, load_tokens, get_valid_access_token, get_company_id
from src.quickbooks.data_pull import get_pnl_data, get_balance_sheet, get_cash_flow

import os
from dotenv import load_dotenv
_ROOT = pathlib.Path(__file__).parent
load_dotenv(_ROOT / ".env", override=True)

ENVIRONMENT = os.getenv("QB_ENVIRONMENT", "sandbox")
BASE_URL = (
    "https://sandbox-quickbooks.api.intuit.com"
    if ENVIRONMENT == "sandbox"
    else "https://quickbooks.api.intuit.com"
)


def check(label: str, fn, *args, **kwargs):
    """Run a check, print PASS or FAIL with the result."""
    try:
        result = fn(*args, **kwargs)
        print(f"  PASS  {label}")
        return result
    except Exception as e:
        print(f"  FAIL  {label}")
        print(f"        Error: {e}")
        return None


def main():
    client_id = sys.argv[1] if len(sys.argv) > 1 else "riverside_home_goods"

    print("=" * 58)
    print(f"  QUICKBOOKS CONNECTION TEST")
    print(f"  Client      : {client_id}")
    print(f"  Environment : {ENVIRONMENT.upper()}")
    print("=" * 58)

    # --- Check 1: Tokens exist ---
    print("\n[1] Token file")
    exists = tokens_exist(client_id)
    if not exists:
        print(f"  FAIL  No tokens found for {client_id}")
        print(f"        Run: python qbo_auth.py {client_id}")
        sys.exit(1)
    tokens = load_tokens(client_id)
    print(f"  PASS  Token file found")
    print(f"        Company ID : {tokens.get('company_id', 'missing')}")

    # --- Check 2: Access token is valid or can refresh ---
    print("\n[2] Access token")
    token = check("Get valid access token", get_valid_access_token, client_id)
    if not token:
        sys.exit(1)

    # --- Check 3: Company Info endpoint ---
    print("\n[3] Company Info API call")
    company_id = get_company_id(client_id)
    url     = f"{BASE_URL}/v3/company/{company_id}/companyinfo/{company_id}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        info = resp.json().get("CompanyInfo", {})
        print(f"  PASS  Company Info API responded")
        print(f"        Company name  : {info.get('CompanyName', 'unknown')}")
        print(f"        Fiscal year   : {info.get('FiscalYearStartMonth', 'unknown')}")
        print(f"        Country       : {info.get('Country', 'unknown')}")
    except Exception as e:
        print(f"  FAIL  Company Info API failed: {e}")
        print(f"        This usually means the token expired.")
        print(f"        Re-run: python qbo_auth.py {client_id}")
        sys.exit(1)

    # Use last month as the test period
    today = datetime.date.today()
    month = today.month - 1 or 12
    year  = today.year if today.month > 1 else today.year - 1

    print(f"\n  Test period: {year}-{month:02d}")

    # --- Check 4: Profit & Loss ---
    print("\n[4] Profit & Loss pull")
    pnl = check("P&L report", get_pnl_data, client_id, "Test Company", year, month)
    if pnl:
        items = len(list(pnl["months"].values())[0])
        print(f"        Line items returned: {items}")

    # --- Check 5: Balance Sheet ---
    print("\n[5] Balance Sheet pull")
    bs = check("Balance Sheet report", get_balance_sheet, client_id, "Test Company", year, month)
    if bs:
        ca = sum(bs["assets"]["current_assets"].values())
        print(f"        Current assets: ${ca:,.0f}")

    # --- Check 6: Cash Flow ---
    print("\n[6] Cash Flow Statement pull")
    cf = check("Cash Flow Statement", get_cash_flow, client_id, "Test Company", year, month)
    if cf:
        op = sum(cf["operating_activities"].values())
        print(f"        Operating activities: ${op:,.0f}")

    # --- Summary ---
    print("\n" + "=" * 58)
    if all([token, pnl, bs, cf]):
        print("  ALL CHECKS PASSED")
        print("  Your QuickBooks connection is fully working.")
        print("  You can now run: python generate_report.py")
    else:
        print("  SOME CHECKS FAILED — see errors above.")
    print("=" * 58 + "\n")


if __name__ == "__main__":
    main()
